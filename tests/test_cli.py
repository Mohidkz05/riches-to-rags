import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from riches_to_rags import __version__
from riches_to_rags.cli import app
from riches_to_rags.sources.base import fingerprint

runner = CliRunner()


def test_version_prints_package_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_no_args_shows_help() -> None:
    result = runner.invoke(app, [])

    assert "Usage" in result.stdout
    assert "version" in result.stdout


def test_scan_lists_documents_and_summary(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("hello", encoding="utf-8")
    (tmp_path / "bad.txt").write_bytes(b"\x00")

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert result.exit_code == 0
    assert f"{fingerprint(b'hello')[:12]}  a.md" in result.stdout
    assert "skipped  bad.txt (binary)" in result.stderr
    assert "1 document, 1 skipped" in result.stdout


def test_scan_rejects_missing_directory(tmp_path: Path) -> None:
    result = runner.invoke(app, ["scan", str(tmp_path / "nope")])

    assert result.exit_code != 0


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")
def test_scan_reports_unreadable_directory_without_traceback(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0)
    try:
        result = runner.invoke(app, ["scan", str(tmp_path)])
    finally:
        locked.chmod(0o755)

    assert result.exit_code == 1
    assert "error: can't read locked: Permission denied" in result.stderr
    assert "Traceback" not in result.output


def test_scan_escapes_control_characters_in_names(tmp_path: Path) -> None:
    (tmp_path / "x\x1b]0;pwn\x07.md").write_text("x", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(tmp_path)])

    assert "\x1b" not in result.output
    assert "\x07" not in result.output
    assert r"skipped  x\x1b]0;pwn\x07.md (unsafe name)" in result.stderr
