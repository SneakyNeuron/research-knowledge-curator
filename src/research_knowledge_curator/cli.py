"""Command-line interface for ``rkc`` (also installed as ``research-knowledge-curator``)."""

from importlib.metadata import version as _dist_version
from typing import Annotated

import typer

DIST_NAME = "research-knowledge-curator"
PROG_NAME = "rkc"

app = typer.Typer(add_completion=False)


def package_version() -> str:
    """Return the installed package version (single source: ``[project] version``)."""
    return _dist_version(DIST_NAME)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"{PROG_NAME} {package_version()}")
        raise typer.Exit(0)


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            is_eager=True,
            callback=_version_callback,
            help="Print the version and exit.",
        ),
    ] = False,
) -> None:
    """Agent-maintained, evidence-anchored research knowledge base."""


def main() -> None:
    """Console-script entry point for both ``rkc`` and ``research-knowledge-curator``."""
    app(prog_name=PROG_NAME)
