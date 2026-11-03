"""``check``: verifies the environment before any build.

Checks, in order: the upstream clone (pinned commit, clean working tree), the
settings from the environment (and writes upstream's ``config.yaml``), a PyMySQL
login with upstream's credentials, the chat model answering through the adapter,
the embedding endpoint returning 1024-length vectors, and both vLLM instances'
``/metrics`` endpoints. Every failure names what is wrong.
"""

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import requests

from harness.paths import (
    EMBEDDING_DIM,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
    UPSTREAM_COMMIT,
    UPSTREAM_DIR,
    WORK_DIR,
)
from harness.settings import Settings, SettingsError
from harness.upstream_config import write_config

# Counters the build driver reads before and after each stage (spec T9).
COST_METRICS = (
    "vllm:request_success_total",
    "vllm:prompt_tokens_total",
    "vllm:generation_tokens_total",
)
# A pooling (embedding) instance generates no tokens; its generation counter is
# not required, only reported when absent.
EMBED_OPTIONAL_METRICS = ("vllm:generation_tokens_total",)
HTTP_TIMEOUT = 60


class CheckFailed(Exception):
    """A check failed; the message names what is wrong."""


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


def _git(*args: str) -> str:
    completed = subprocess.run(  # noqa: S603 - fixed arguments, no untrusted input
        ["git", "-C", str(UPSTREAM_DIR), *args],  # noqa: S607 - git from PATH, as in setup.sh
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise CheckFailed(f"git {' '.join(args)} failed: {completed.stderr.strip()}")
    return completed.stdout


def check_upstream() -> str:
    if not (UPSTREAM_DIR / ".git").is_dir():
        raise CheckFailed(f"no upstream clone at {UPSTREAM_DIR}; run setup.sh")
    head = _git("rev-parse", "HEAD").strip()
    if head != UPSTREAM_COMMIT:
        raise CheckFailed(f"upstream HEAD is {head}, expected {UPSTREAM_COMMIT}")
    changes = _git("status", "--porcelain").strip()
    if changes:
        raise CheckFailed(
            f"upstream working tree has changes (upstream must run unmodified): {changes[:300]}"
        )
    return f"{UPSTREAM_COMMIT}, working tree clean"


def check_mysql() -> str:
    import pymysql  # from the harness venv (upstream's pin)

    where = f"127.0.0.1:{MYSQL_PORT}"
    try:
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            passwd=MYSQL_PASSWORD,
            charset="utf8mb4",
            connect_timeout=5,
        )
    except RuntimeError as exc:  # PyMySQL needs `cryptography` for caching_sha2_password
        raise CheckFailed(
            f"PyMySQL cannot log in to MySQL at {where} as root: {exc}. "
            "root must authenticate with mysql_native_password (see docker-compose.yml)"
        ) from exc
    except pymysql.MySQLError as exc:
        raise CheckFailed(
            f"cannot log in to MySQL at {where} as root: {exc}. "
            "Is the container up (docker compose up -d) and the port free?"
        ) from exc
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION(), CURRENT_USER()")
            version, user = cursor.fetchone()
    finally:
        connection.close()
    return f"logged in at {where} as {user}, MySQL {version}"


def check_chat(settings: Settings) -> str:
    from harness.adapter import ChatAdapter

    adapter = ChatAdapter(settings)
    answer = adapter.generate_text("Reply with the single word OK.")
    if not answer.strip():
        raise CheckFailed(
            f"chat model {settings.chat_model} at {settings.chat.base_url} returned an empty "
            "response (upstream hides the request error; see the printed 'Retry for Error')"
        )
    return f"{settings.chat_model} answered ({answer.strip()[:40]!r})"


def check_embedding(settings: Settings) -> str:
    url = f"{settings.embed.base_url}/embeddings"
    try:
        response = requests.post(
            url,
            json={"model": settings.embed_model, "input": ["embedding check"]},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        vector = response.json()["data"][0]["embedding"]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        raise CheckFailed(f"embedding endpoint {url} failed: {exc}") from exc
    if len(vector) != EMBEDDING_DIM:
        raise CheckFailed(
            f"embedding model {settings.embed_model} returned vectors of length {len(vector)}; "
            f"upstream hard-codes {EMBEDDING_DIM}"
        )
    return f"{settings.embed_model} returned a vector of length {len(vector)}"


def metric_present(text: str, name: str) -> bool:
    return re.search(rf"^{re.escape(name)}[{{ ]", text, flags=re.MULTILINE) is not None


def check_metrics(url: str, optional: tuple[str, ...] = ()) -> str:
    try:
        response = requests.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise CheckFailed(f"metrics endpoint {url} failed: {exc}") from exc
    missing = [name for name in COST_METRICS if not metric_present(response.text, name)]
    required_missing = [name for name in missing if name not in optional]
    if required_missing:
        raise CheckFailed(f"metrics endpoint {url} lacks {', '.join(required_missing)}")
    note = f" (absent, not required here: {', '.join(missing)})" if missing else ""
    return f"{url} exposes the cost counters{note}"


def run_checks(env: dict[str, str] | None = None) -> list[Result]:
    results: list[Result] = []

    def attempt(name: str, func: Callable[[], str]) -> bool:
        try:
            results.append(Result(name, True, func()))
        except CheckFailed as exc:
            results.append(Result(name, False, str(exc)))
            return False
        return True

    attempt("upstream", check_upstream)
    try:
        settings = Settings.from_env(dict(os.environ) if env is None else env)
    except SettingsError as exc:
        results.append(Result("settings", False, str(exc)))
        settings = None
    else:
        path = write_config(settings, WORK_DIR)
        results.append(Result("settings", True, f"wrote {path}"))
    attempt("mysql", check_mysql)
    if settings is not None:
        attempt("chat", lambda: check_chat(settings))
        attempt("embedding", lambda: check_embedding(settings))
        # After the calls above, so labelled counters have been created.
        attempt("chat metrics", lambda: check_metrics(settings.chat_metrics_url))
        attempt(
            "embedding metrics",
            lambda: check_metrics(settings.embed_metrics_url, optional=EMBED_OPTIONAL_METRICS),
        )
    return results
