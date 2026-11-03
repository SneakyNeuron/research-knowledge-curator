"""Model adapter: upstream's own ``InstanceManager``, wrapped for measurement.

Upstream's request shape and prompt truncation are kept by calling its
``tools.utils.InstanceManager`` unchanged. The wrapper only:

- adds ``temperature=0`` (or the adapter's configured temperature, used only to
  retry a failed corpus article) and the configured ``seed`` to every call (as
  request kwargs, which upstream forwards into the request body next to its own
  ``enable_thinking: False``), overriding whatever the caller passes;
- logs each call's prompt length in tokens and keeps the maximum;
- counts empty responses. Upstream catches every request error (including vLLM
  rejecting an over-length prompt), prints it and returns ``""``, so an empty
  string is the only trace a failed call leaves.

Prompt length is counted with ``cl100k_base`` (the tokenizer upstream truncates
with, not the served model's), over the messages as sent: it is measured after
the call, because upstream truncates the history messages in place, and the
first message is capped where upstream caps it.
"""

import logging
import math
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import tiktoken

from harness.paths import make_upstream_importable
from harness.settings import Settings

logger = logging.getLogger(__name__)

# Upstream truncates the first message it sends to this many cl100k tokens.
UPSTREAM_FIRST_MESSAGE_CAP = 31000


@dataclass(frozen=True)
class CallStats:
    calls: int = 0
    empty_responses: int = 0
    max_prompt_tokens: int = 0


class ChatAdapter:
    """Drop-in for ``InstanceManager.generate_text`` and ``generate_text_asy``."""

    def __init__(self, settings: Settings, temperature: float = 0) -> None:
        if not math.isfinite(temperature) or temperature < 0:
            raise ValueError(f"temperature must be a finite number >= 0, not {temperature}")
        make_upstream_importable()
        from tools.utils import InstanceManager  # upstream, imported from the clone

        self.seed = settings.seed
        self.temperature = temperature
        self.model = settings.chat_model
        self._manager = InstanceManager(
            url=settings.chat.host_url,
            ports=[settings.chat.port],
            gpus=[0],
            generate_model=settings.chat_model,
            startup_delay=0,
        )
        self._encoding = tiktoken.get_encoding("cl100k_base")
        self._lock = threading.Lock()
        self._stats = CallStats()

    def stats(self) -> CallStats:
        with self._lock:
            return self._stats

    def reset_stats(self) -> None:
        with self._lock:
            self._stats = CallStats()

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> str:
        history = history_messages if history_messages is not None else []
        response = self._manager.generate_text(
            prompt, system_prompt=system_prompt, history_messages=history, **self._kwargs(kwargs)
        )
        return self._record(prompt, system_prompt, history, response)

    async def generate_text_asy(
        self,
        prompt: str,
        system_prompt: str | None = None,
        history_messages: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> str:
        history = history_messages if history_messages is not None else []
        response = await self._manager.generate_text_asy(
            prompt, system_prompt=system_prompt, history_messages=history, **self._kwargs(kwargs)
        )
        return self._record(prompt, system_prompt, history, response)

    def _kwargs(self, kwargs: dict[str, Any]) -> dict[str, Any]:
        return {**kwargs, "temperature": self.temperature, "seed": self.seed}

    def _prompt_tokens(
        self, prompt: str, system_prompt: str | None, history: Sequence[dict[str, str]]
    ) -> int:
        contents = [system_prompt] if system_prompt else []
        contents += [str(message.get("content", "")) for message in history]
        contents.append(prompt)
        counts = [len(self._encoding.encode(text, disallowed_special=())) for text in contents]
        counts[0] = min(counts[0], UPSTREAM_FIRST_MESSAGE_CAP)
        return sum(counts)

    def _record(
        self,
        prompt: str,
        system_prompt: str | None,
        history: Sequence[dict[str, str]],
        response: object,
    ) -> str:
        text = response if isinstance(response, str) else ""
        tokens = self._prompt_tokens(prompt, system_prompt, history)
        empty = not text.strip()
        with self._lock:
            old = self._stats
            self._stats = CallStats(
                calls=old.calls + 1,
                empty_responses=old.empty_responses + int(empty),
                max_prompt_tokens=max(old.max_prompt_tokens, tokens),
            )
        logger.info("chat call: prompt_tokens=%d empty=%s", tokens, empty)
        if empty:
            logger.warning("empty chat response (prompt_tokens=%d)", tokens)
        return text
