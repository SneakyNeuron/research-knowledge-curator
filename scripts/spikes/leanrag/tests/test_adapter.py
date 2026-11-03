"""Model adapter around upstream's InstanceManager, with requests.post faked."""

import asyncio
import json
from typing import Any

import pytest
import requests
import tiktoken
from harness.adapter import ChatAdapter
from harness.settings import Settings

ENV = {
    "LEANRAG_CHAT_URL": "http://127.0.0.1:8001/v1",
    "LEANRAG_CHAT_MODEL": "chat-model",
    "LEANRAG_EMBED_URL": "http://127.0.0.1:8002/v1",
    "LEANRAG_EMBED_MODEL": "embed-model",
    "LEANRAG_SEED": "77",
}
ENC = tiktoken.get_encoding("cl100k_base")


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | None, status: int = 200) -> None:
        self.status_code = status
        self.content = json.dumps(payload).encode() if payload is not None else b""

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")


def reply(text: str) -> FakeResponse:
    return FakeResponse(
        {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 1}}
    )


class FakeTransport:
    """Stands in for requests.post; replays scripted replies and records requests."""

    def __init__(self, *replies: FakeResponse | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, url: str, json: dict[str, Any], timeout: float) -> FakeResponse:
        self.requests.append({"url": url, "json": json})
        item = self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def adapter() -> ChatAdapter:
    return ChatAdapter(Settings.from_env(ENV))


def install(monkeypatch: pytest.MonkeyPatch, transport: FakeTransport) -> None:
    monkeypatch.setattr(requests, "post", transport)


def test_every_call_sends_temperature_zero_seed_and_no_thinking(
    adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport(reply("a"), reply("b"), reply("c"), reply("d"))
    install(monkeypatch, transport)

    adapter.generate_text("plain")
    adapter.generate_text("with system", system_prompt="sys")
    history = [
        {"role": "user", "content": "first"},
        {"role": "assistant", "content": "answer"},
    ]
    asyncio.run(adapter.generate_text_asy("glean", history_messages=history))
    adapter.generate_text("caller asks for heat", temperature=0.9, seed=1)

    assert len(transport.requests) == 4
    for sent in transport.requests:
        assert sent["url"] == "http://127.0.0.1:8001/v1/chat/completions"
        body = sent["json"]
        assert body["model"] == "chat-model"
        assert body["temperature"] == 0
        assert body["seed"] == 77
        assert body["chat_template_kwargs"] == {"enable_thinking": False}


def test_returns_the_model_text(adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeTransport(reply("hello")))

    assert adapter.generate_text("hi") == "hello"
    assert adapter.stats().calls == 1
    assert adapter.stats().empty_responses == 0


def test_errors_and_empty_responses_are_counted(
    adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    over_length = FakeResponse({"error": "maximum context length"}, status=400)
    install(
        monkeypatch,
        FakeTransport(
            requests.ConnectionError("refused"),
            over_length,
            reply(""),
            reply("fine"),
        ),
    )

    results = [adapter.generate_text(p) for p in ("a", "b", "c", "d")]

    assert results == ["", "", "", "fine"]
    stats = adapter.stats()
    assert stats.calls == 4
    assert stats.empty_responses == 3


def test_async_calls_are_counted_too(adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeTransport(requests.Timeout("slow"), reply("ok")))

    async def run() -> list[str]:
        return [await adapter.generate_text_asy("x"), await adapter.generate_text_asy("y")]

    assert asyncio.run(run()) == ["", "ok"]
    assert adapter.stats().calls == 2
    assert adapter.stats().empty_responses == 1


def test_longest_prompt_is_recorded(adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeTransport(reply("a"), reply("b"), reply("c")))
    short = "short prompt"
    long = "a much longer prompt " * 50
    system = "you are a system prompt with several tokens"

    adapter.generate_text(short)
    adapter.generate_text(long, system_prompt=system)
    adapter.generate_text(short)

    expected = len(ENC.encode(system)) + len(ENC.encode(long))
    assert adapter.stats().max_prompt_tokens == expected


def test_longest_prompt_includes_history_as_sent(
    adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, FakeTransport(reply("a")))
    # Upstream truncates the first history message to 3,000 tokens before sending.
    first = "word " * 5000
    history = [
        {"role": "user", "content": first},
        {"role": "assistant", "content": "answer"},
    ]

    adapter.generate_text("continue", history_messages=history)

    expected = 3000 + len(ENC.encode("answer")) + len(ENC.encode("continue"))
    assert adapter.stats().max_prompt_tokens == expected


def test_failed_call_still_records_its_prompt_length(
    adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(monkeypatch, FakeTransport(FakeResponse({}, status=400)))
    prompt = "too long " * 100

    adapter.generate_text(prompt)

    assert adapter.stats().max_prompt_tokens == len(ENC.encode(prompt))


def test_reset_starts_a_new_stage(adapter: ChatAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    install(monkeypatch, FakeTransport(reply(""), reply("ok")))
    adapter.generate_text("first stage prompt")

    adapter.reset_stats()
    adapter.generate_text("x")

    stats = adapter.stats()
    assert stats.calls == 1
    assert stats.empty_responses == 0
    assert stats.max_prompt_tokens == len(ENC.encode("x"))
