"""Command-line entry point."""

import unicodedata
from pathlib import Path
from typing import Annotated

import typer

from riches_to_rags import __version__
from riches_to_rags.sources.base import SourceReadError
from riches_to_rags.sources.local import LocalDirectorySource

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


@app.command()
def scan(
    path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=False, dir_okay=True, help="Directory to scan."),
    ],
) -> None:
    """List the documents a directory source would index, with short fingerprints."""
    source = LocalDirectorySource(path)
    count = 0
    try:
        for ref in source.list_documents():
            typer.echo(f"{ref.fingerprint[:12]}  {ref.id}")
            count += 1
    except SourceReadError as err:
        typer.echo(f"error: {_printable(str(err))}", err=True)
        raise typer.Exit(1) from err
    for skip in source.skipped:
        typer.echo(f"skipped  {_printable(skip.id)} ({skip.reason})", err=True)
    noun = "document" if count == 1 else "documents"
    typer.echo(f"{count} {noun}, {len(source.skipped)} skipped")


def _printable(text: str) -> str:
    """Escape control characters so file names can't forge lines or drive the terminal."""
    return "".join(
        ch.encode("unicode_escape").decode("ascii") if unicodedata.category(ch) == "Cc" else ch
        for ch in text
    )


def main() -> None:
    app()
