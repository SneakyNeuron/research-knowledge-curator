"""The ``generate`` command line: ``--retry-temperature`` end to end, with requests.post faked."""

import json
from pathlib import Path
from typing import Any

import pytest
import requests
from harness.__main__ import main
from harness.paths import CORPUS_SPEC

ENV = {
    "LEANRAG_CHAT_URL": "http://127.0.0.1:8001/v1",
    "LEANRAG_CHAT_MODEL": "chat-model",
    "LEANRAG_EMBED_URL": "http://127.0.0.1:8002/v1",
    "LEANRAG_EMBED_MODEL": "embed-model",
    "LEANRAG_SEED": "77",
}
PROSE = "Plain section prose about evaluation.\n\nA second paragraph of it."


class FakeResponse:
    status_code = 200
    content = json.dumps(
        {"choices": [{"message": {"content": PROSE}}], "usage": {"prompt_tokens": 1}}
    ).encode()

    def raise_for_status(self) -> None:
        return None


class Transport:
    """Stands in for requests.post: always replies with plain prose, records bodies."""

    def __init__(self) -> None:
        self.bodies: list[dict[str, Any]] = []

    def __call__(self, url: str, json: dict[str, Any], timeout: float) -> FakeResponse:
        self.bodies.append(json)
        return FakeResponse()


@pytest.fixture
def transport(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Transport:
    fake = Transport()
    monkeypatch.setattr(requests, "post", fake)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    # main() moves into the work directory; chdir here first so it is undone.
    monkeypatch.chdir(tmp_path)
    return fake


def generate(out: Path, *extra: str) -> int:
    spec = str(CORPUS_SPEC)
    return main(
        ["generate", "--model-revision", "abc123", "--spec", spec, "--out", str(out), *extra]
    )


def records(out: Path) -> dict[str, dict[str, Any]]:
    lines = (out / "articles.jsonl").read_text(encoding="utf-8").splitlines()
    return {r["id"]: r for r in map(json.loads, lines)}


def test_retry_temperature_is_sent_and_recorded_and_normal_calls_stay_at_zero(
    transport: Transport, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "corpus"

    assert generate(out, "--only", "synthetic:01", "--only", "synthetic:02") == 0
    normal_calls = len(transport.bodies)
    assert normal_calls > 0
    assert all(body["temperature"] == 0 for body in transport.bodies)

    monkeypatch.setenv("LEANRAG_SEED", "78")
    assert generate(out, "--only", "synthetic:02", "--retry-temperature", "0.6") == 0
    retry_bodies = transport.bodies[normal_calls:]
    assert retry_bodies
    assert all(body["temperature"] == 0.6 for body in retry_bodies)
    assert all(body["seed"] == 78 for body in retry_bodies)

    by_id = records(out)
    assert by_id["synthetic:01"]["generated_by"] == {
        "model": "chat-model",
        "revision": "abc123",
        "seed": 77,
        "temperature": 0,
    }
    assert by_id["synthetic:02"]["generated_by"] == {
        "model": "chat-model",
        "revision": "abc123",
        "seed": 78,
        "temperature": 0.6,
    }


def test_retry_temperature_is_refused_without_only(
    transport: Transport, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exc:
        generate(tmp_path / "corpus", "--retry-temperature", "0.6")

    assert exc.value.code == 2
    assert "--only" in capsys.readouterr().err
    assert transport.bodies == []


@pytest.mark.parametrize("value", ["0", "-0.5", "nan", "inf", "warm"])
def test_retry_temperature_must_be_a_finite_float_above_zero(
    transport: Transport, tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    with pytest.raises(SystemExit) as exc:
        generate(tmp_path / "corpus", "--only", "synthetic:01", "--retry-temperature", value)

    assert exc.value.code == 2
    assert "--retry-temperature" in capsys.readouterr().err
    assert transport.bodies == []


def test_the_failure_message_points_to_retry_temperature(
    transport: Transport,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty = {"choices": [{"message": {"content": ""}}], "usage": {"prompt_tokens": 1}}
    monkeypatch.setattr(FakeResponse, "content", json.dumps(empty).encode())

    assert generate(tmp_path / "corpus", "--only", "synthetic:01") == 1  # empty reply fails it

    assert "--retry-temperature" in capsys.readouterr().err
