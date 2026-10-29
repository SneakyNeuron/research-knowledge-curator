"""Smoke tests for the packaged CLI: version, console scripts, offline enforcement."""

import socket
import tomllib
from pathlib import Path
from typing import Any

import pytest
from pytest_socket import SocketBlockedError
from typer.testing import CliRunner

from research_knowledge_curator.cli import app

PYPROJECT = Path(__file__).resolve().parent.parent / "pyproject.toml"

runner = CliRunner()


def _pyproject() -> dict[str, Any]:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)


def test_version_option_prints_name_and_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == "rkc {}\n".format(_pyproject()["project"]["version"])


def test_both_console_scripts_share_one_entry_point() -> None:
    scripts = _pyproject()["project"]["scripts"]
    assert scripts["rkc"] == scripts["research-knowledge-curator"]
    assert scripts["rkc"].startswith("research_knowledge_curator.cli:")


@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket")
def test_network_access_is_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
