"""Harness settings, read only from environment variables.

Endpoints and model names come from the environment and nothing else (spec T3).
No key is read: vLLM runs without ``--api-key``, so upstream's ``api_key`` field
gets a fixed, non-secret placeholder.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

API_KEY_PLACEHOLDER = "not-a-secret-vllm-runs-without-api-key"

CHAT_URL = "LEANRAG_CHAT_URL"
CHAT_MODEL = "LEANRAG_CHAT_MODEL"
EMBED_URL = "LEANRAG_EMBED_URL"
EMBED_MODEL = "LEANRAG_EMBED_MODEL"
SEED = "LEANRAG_SEED"
ENV_VARS = (CHAT_URL, CHAT_MODEL, EMBED_URL, EMBED_MODEL, SEED)


class SettingsError(ValueError):
    """A required environment variable is missing or malformed (named in the message)."""


@dataclass(frozen=True)
class Endpoint:
    """An OpenAI-compatible vLLM endpoint of the form ``http(s)://host:port/v1``."""

    base_url: str
    host_url: str
    port: int

    @property
    def metrics_url(self) -> str:
        return f"{self.host_url}:{self.port}/metrics"

    @classmethod
    def parse(cls, variable: str, url: str) -> "Endpoint":
        parts = urlsplit(url)
        problem = None
        if parts.scheme not in ("http", "https"):
            problem = "scheme must be http or https"
        elif parts.hostname is None:
            problem = "host is missing"
        elif parts.port is None:
            problem = "port is missing"
        elif parts.path.rstrip("/") != "/v1":
            problem = "path must be /v1"
        elif parts.query or parts.fragment or parts.username or parts.password:
            problem = "no query, fragment or credentials allowed"
        if problem is not None:
            raise SettingsError(
                f"{variable} must look like http://127.0.0.1:8001/v1 ({problem}); "
                "upstream calls <host>:<port>/v1 itself"
            )
        hostname = parts.hostname or ""
        port = parts.port or 0
        host = f"[{hostname}]" if ":" in hostname else hostname
        host_url = f"{parts.scheme}://{host}"
        return cls(base_url=f"{host_url}:{port}/v1", host_url=host_url, port=port)


@dataclass(frozen=True)
class Settings:
    chat: Endpoint
    chat_model: str
    embed: Endpoint
    embed_model: str
    seed: int

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        missing = [name for name in ENV_VARS if not env.get(name, "").strip()]
        if missing:
            raise SettingsError(
                "missing environment variable(s): " + ", ".join(missing) + " (see README.md)"
            )
        try:
            seed = int(env[SEED].strip())
        except ValueError:
            raise SettingsError(f"{SEED} must be an integer") from None
        return cls(
            chat=Endpoint.parse(CHAT_URL, env[CHAT_URL].strip()),
            chat_model=env[CHAT_MODEL].strip(),
            embed=Endpoint.parse(EMBED_URL, env[EMBED_URL].strip()),
            embed_model=env[EMBED_MODEL].strip(),
            seed=seed,
        )

    # Shorthands used by the adapter and the check command.
    @property
    def chat_host_url(self) -> str:
        return self.chat.host_url

    @property
    def chat_port(self) -> int:
        return self.chat.port

    @property
    def chat_metrics_url(self) -> str:
        return self.chat.metrics_url

    @property
    def embed_metrics_url(self) -> str:
        return self.embed.metrics_url
