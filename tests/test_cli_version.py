"""Tests for the ``version`` subcommand, the global ``--json`` flag, help and bare invocation."""

import json
import re

import pytest
import typer.core
import typer.main
from typer.testing import CliRunner

from research_knowledge_curator.cli import app


def _commands_listed(help_text: str) -> list[str]:
    """Return the command names in the help text's ``Commands`` panel."""
    lines = help_text.splitlines()
    starts = [i for i, line in enumerate(lines) if "─ Commands " in line]
    assert starts, f"no Commands panel in help text:\n{help_text}"
    names: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if line.startswith("╰"):
            break
        match = re.match(r"│\s+(\S+)", line)
        if match:
            names.append(match.group(1))
    return names


def test_only_version_command_is_registered() -> None:
    command = typer.main.get_command(app)
    assert isinstance(command, typer.core.TyperGroup)
    assert list(command.commands) == ["version"]


@pytest.mark.parametrize(
    "args", [["version", "--json"], ["--json", "version"]], ids=["after", "before"]
)
def test_version_json_in_either_position(
    runner: CliRunner, expected_version: str, args: list[str]
) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout.endswith("\n")
    assert result.stdout.count("\n") == 1
    assert json.loads(result.stdout) == {"version": expected_version}


def test_version_plain_is_not_json(runner: CliRunner, expected_version: str) -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stderr == ""
    assert result.stdout == f"rkc {expected_version}\n"
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)


def test_version_option_ignores_json(runner: CliRunner, expected_version: str) -> None:
    result = runner.invoke(app, ["--version", "--json"])
    assert result.exit_code == 0
    assert result.stdout == f"rkc {expected_version}\n"


@pytest.mark.parametrize("args", [[], ["--json"]], ids=["bare", "json-only"])
def test_bare_invocation_shows_help_and_exits_2(runner: CliRunner, args: list[str]) -> None:
    result = runner.invoke(app, args)
    assert result.exit_code == 2
    assert "Usage:" in result.stdout
    assert "--json" in result.stdout
    assert _commands_listed(result.stdout) == ["version"]


def test_bare_invocation_output_equals_help(runner: CliRunner) -> None:
    bare = runner.invoke(app, [])
    help_ = runner.invoke(app, ["--help"])
    assert bare.stdout == help_.stdout


def test_help_lists_only_implemented_options_and_commands(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    out = result.stdout
    for option in ("--version", "--json", "--help"):
        assert option in out
    assert set(re.findall(r"--[a-z][a-z-]*", out)) == {"--version", "--json", "--help"}
    assert "--install-completion" not in out
    assert "--show-completion" not in out
    assert _commands_listed(out) == ["version"]


def test_unknown_option_is_usage_error_on_stderr(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--bogus"])
    assert result.exit_code != 0
    assert result.stdout == ""
    assert "No such option" in result.stderr
    assert "Usage:" in result.stderr
