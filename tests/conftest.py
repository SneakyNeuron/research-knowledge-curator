"""Shared fixtures for the CLI tests."""

import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer.rich_utils
from typer.testing import CliRunner

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"


@pytest.fixture(autouse=True)
def plain_help(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Keep Typer's rich help free of ANSI codes so assertions on its text hold.

    Typer sets ``rich_utils.FORCE_TERMINAL = True`` at import time when ``GITHUB_ACTIONS``,
    ``FORCE_COLOR`` or ``PY_COLORS`` is set (as on GitHub Actions). It reads the global each
    time it builds a console, so patching it here is enough; ``CliRunner(env=...)`` is not.
    """
    monkeypatch.setattr(typer.rich_utils, "FORCE_TERMINAL", False)
    yield


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(scope="session")
def pyproject() -> dict[str, Any]:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)


@pytest.fixture(scope="session")
def expected_version(pyproject: dict[str, Any]) -> str:
    version: str = pyproject["project"]["version"]
    return version
