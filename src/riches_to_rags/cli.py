"""Command-line entry point."""

import typer

from riches_to_rags import __version__

app = typer.Typer(
    help="Keep a pgvector index correct as its sources change.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Group commands under one app (sync, status, search, migrate land here)."""


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(__version__)


def main() -> None:
    app()
