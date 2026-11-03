"""Config writer: exactly the five keys upstream reads, from the environment, no secret."""

from pathlib import Path

import pytest
import yaml
from harness.settings import API_KEY_PLACEHOLDER, ENV_VARS, Settings, SettingsError
from harness.upstream_config import write_config

BASE_ENV = {
    "LEANRAG_CHAT_URL": "http://127.0.0.1:8001/v1",
    "LEANRAG_CHAT_MODEL": "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ",
    "LEANRAG_EMBED_URL": "http://127.0.0.1:8002/v1",
    "LEANRAG_EMBED_MODEL": "Qwen/Qwen3-Embedding-0.6B",
    "LEANRAG_SEED": "1234",
}


def test_config_has_exactly_the_five_keys_upstream_reads(tmp_path: Path) -> None:
    settings = Settings.from_env(BASE_ENV)

    path = write_config(settings, tmp_path)

    assert path == tmp_path / "config.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data == {
        "deepseek": {
            "model": "stelterlab/Qwen3-30B-A3B-Instruct-2507-AWQ",
            "api_key": API_KEY_PLACEHOLDER,
            "base_url": "http://127.0.0.1:8001/v1",
        },
        "glm": {
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "base_url": "http://127.0.0.1:8002/v1",
        },
    }


def test_config_contains_no_secret_from_the_environment(tmp_path: Path) -> None:
    secret = "sk-test-SECRET-sentinel-0123456789"  # noqa: S105 - fake sentinel, not a secret
    env = {**BASE_ENV, "OPENAI_API_KEY": secret, "DEEPSEEK_API_KEY": secret}
    settings = Settings.from_env(env)

    text = write_config(settings, tmp_path).read_text(encoding="utf-8")

    assert secret not in text
    assert "SECRET" not in text


def test_api_key_is_a_fixed_non_secret_placeholder() -> None:
    assert API_KEY_PLACEHOLDER == "not-a-secret-vllm-runs-without-api-key"


def test_rewriting_replaces_the_file(tmp_path: Path) -> None:
    write_config(Settings.from_env(BASE_ENV), tmp_path)
    other = {**BASE_ENV, "LEANRAG_CHAT_MODEL": "Qwen/Qwen3-4B-Instruct-2507"}

    path = write_config(Settings.from_env(other), tmp_path)

    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["deepseek"]["model"] == "Qwen/Qwen3-4B-Instruct-2507"


@pytest.mark.parametrize("missing", ENV_VARS)
def test_missing_variable_is_named(missing: str) -> None:
    env = {k: v for k, v in BASE_ENV.items() if k != missing}

    with pytest.raises(SettingsError, match=missing):
        Settings.from_env(env)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/v1",  # no port: upstream appends ":<port>/v1" itself
        "http://127.0.0.1:8001",  # upstream always calls <host>:<port>/v1
        "http://127.0.0.1:8001/v2",
        "ftp://127.0.0.1:8001/v1",
        "http://127.0.0.1:8001/v1?x=1",
    ],
)
def test_chat_url_must_be_host_port_v1(url: str) -> None:
    with pytest.raises(SettingsError, match="LEANRAG_CHAT_URL"):
        Settings.from_env({**BASE_ENV, "LEANRAG_CHAT_URL": url})


def test_seed_must_be_an_integer() -> None:
    with pytest.raises(SettingsError, match="LEANRAG_SEED"):
        Settings.from_env({**BASE_ENV, "LEANRAG_SEED": "abc"})


def test_chat_endpoint_parts_for_instance_manager() -> None:
    settings = Settings.from_env(BASE_ENV)

    assert settings.chat_host_url == "http://127.0.0.1"
    assert settings.chat_port == 8001
    assert settings.chat_metrics_url == "http://127.0.0.1:8001/metrics"
    assert settings.embed_metrics_url == "http://127.0.0.1:8002/metrics"
    assert settings.seed == 1234
