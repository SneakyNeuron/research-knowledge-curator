"""Writes upstream's ``config.yaml`` into the work directory.

Exactly the keys upstream reads at import time (``build_graph.py`` and
``query_graph.py``): ``deepseek.model``, ``deepseek.api_key``,
``deepseek.base_url``, ``glm.model`` and ``glm.base_url``. Nothing else, and no
secret: ``api_key`` is a fixed placeholder because vLLM runs without a key.
"""

from pathlib import Path

import yaml

from harness.settings import API_KEY_PLACEHOLDER, Settings

CONFIG_NAME = "config.yaml"


def build_config(settings: Settings) -> dict[str, dict[str, str]]:
    return {
        "deepseek": {
            "model": settings.chat_model,
            "api_key": API_KEY_PLACEHOLDER,
            "base_url": settings.chat.base_url,
        },
        "glm": {
            "model": settings.embed_model,
            "base_url": settings.embed.base_url,
        },
    }


def write_config(settings: Settings, work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / CONFIG_NAME
    path.write_text(yaml.safe_dump(build_config(settings), sort_keys=True), encoding="utf-8")
    return path
