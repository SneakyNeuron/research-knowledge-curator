"""Smoke tests for the packaged CLI: version, console scripts, offline enforcement."""

import importlib
import socket
from typing import Any

import pytest
from pytest_socket import SocketBlockedError
from typer.testing import CliRunner

from research_knowledge_curator import cli
from research_knowledge_curator.cli import app


def test_version_option_prints_name_and_version(runner: CliRunner, expected_version: str) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == f"rkc {expected_version}\n"


def test_both_console_scripts_share_one_entry_point(pyproject: dict[str, Any]) -> None:
    scripts = pyproject["project"]["scripts"]
    assert scripts["rkc"] == scripts["research-knowledge-curator"]
    module_name, _, attr = scripts["rkc"].partition(":")
    assert attr, f"entry point {scripts['rkc']!r} has no ':attr' part"
    assert getattr(importlib.import_module(module_name), attr) is cli.main


@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket")
def test_network_access_is_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
