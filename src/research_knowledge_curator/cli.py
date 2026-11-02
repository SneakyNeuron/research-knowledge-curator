"""Command-line interface for ``rkc`` (also installed as ``research-knowledge-curator``)."""

import json
from dataclasses import dataclass
from importlib.metadata import version as _dist_version
from typing import Annotated, Any

import typer

DIST_NAME = "research-knowledge-curator"
PROG_NAME = "rkc"

app = typer.Typer(add_completion=False, invoke_without_command=True)

JsonOption = Annotated[
    bool,
    typer.Option("--json", help="Print machine-readable JSON on stdout."),
]


@dataclass
class CliState:
    """Global options parsed by the app callback, shared with subcommands via ``ctx.obj``."""

    json: bool = False


def package_version() -> str:
    """Return the installed package version (single source: ``[project] version``)."""
    return _dist_version(DIST_NAME)


def version_line() -> str:
    """Return the plain version line, ``rkc <version>``."""
    return f"{PROG_NAME} {package_version()}"


def emit_json(obj: dict[str, Any]) -> None:
    """Write one object to stdout as a single line of plain ``json.dumps`` output."""
    typer.echo(json.dumps(obj))


def json_requested(ctx: typer.Context, local: bool) -> bool:
    """Return True if ``--json`` was given globally (``rkc --json CMD``) or on the command."""
    state = ctx.find_root().obj
    return local or (isinstance(state, CliState) and state.json)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(version_line())
        raise typer.Exit(0)


@app.callback()
def root(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            is_eager=True,
            callback=_version_callback,
            help="Print the version and exit.",
        ),
    ] = False,
    json_output: JsonOption = False,
) -> None:
    """Agent-maintained, evidence-anchored research knowledge base."""
    ctx.obj = CliState(json=json_output)
    if ctx.invoked_subcommand is None:
        # With rich installed, Typer prints the help itself inside get_help() and returns "",
        # so this echo only adds a final newline, keeping the output byte-identical to
        # `rkc --help` (tests/test_cli_version.py checks this).
        typer.echo(ctx.get_help())
        raise typer.Exit(2)


@app.command("version")
def version_command(ctx: typer.Context, json_output: JsonOption = False) -> None:
    """Print the version."""
    if json_requested(ctx, json_output):
        emit_json({"version": package_version()})
    else:
        typer.echo(version_line())


def main() -> None:
    """Console-script entry point for both ``rkc`` and ``research-knowledge-curator``."""
    app(prog_name=PROG_NAME)
