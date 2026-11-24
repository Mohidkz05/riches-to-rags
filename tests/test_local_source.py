import os
import shutil
from pathlib import Path

import pytest

from riches_to_rags.sources.base import DocumentNotFoundError, SourceReadError, fingerprint
from riches_to_rags.sources.local import LocalDirectorySource

unreadable = pytest.mark.skipif(
    os.geteuid() == 0, reason="root ignores file permissions, so chmod 0 can't simulate EACCES"
)


def write(root: Path, rel: str, data: bytes | str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, str):
        path.write_text(data, encoding="utf-8")
    else:
        path.write_bytes(data)
    return path


def listed_ids(source: LocalDirectorySource) -> list[str]:
    return [ref.id for ref in source.list_documents()]


def skipped(source: LocalDirectorySource) -> dict[str, str]:
    return {s.id: s.reason for s in source.skipped}


def test_lists_nested_text_files_with_posix_ids_in_sorted_order(tmp_path: Path) -> None:
    write(tmp_path, "b.md", "# b")
    write(tmp_path, "a.txt", "a")
    write(tmp_path, "docs/guide/intro.md", "intro")
    write(tmp_path, "src/app.py", "print(1)")

    assert listed_ids(LocalDirectorySource(tmp_path)) == [
        "a.txt",
        "b.md",
        "docs/guide/intro.md",
        "src/app.py",
    ]


def test_fingerprint_is_sha256_of_content(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "hello")

    (ref,) = LocalDirectorySource(tmp_path).list_documents()

    assert ref.fingerprint == fingerprint(b"hello")


def test_ignores_unlisted_extensions_vendor_and_hidden_dirs(tmp_path: Path) -> None:
    write(tmp_path, "keep.md", "x")
    write(tmp_path, "image.png", b"\x89PNG")
    write(tmp_path, "uv.lock", "x")
    write(tmp_path, ".git/notes.md", "x")
    write(tmp_path, "node_modules/pkg/readme.md", "x")
    write(tmp_path, ".hidden/notes.md", "x")
    write(tmp_path, "pkg/__pycache__/mod.py", "x")

    source = LocalDirectorySource(tmp_path)

    assert listed_ids(source) == ["keep.md"]
    assert source.skipped == []


def test_extension_match_is_case_insensitive(tmp_path: Path) -> None:
    write(tmp_path, "README.MD", "x")

    assert listed_ids(LocalDirectorySource(tmp_path)) == ["README.MD"]


def test_custom_extensions_and_excluded_dirs(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "x")
    write(tmp_path, "b.csv", "x")
    write(tmp_path, "drafts/c.csv", "x")

    source = LocalDirectorySource(tmp_path, extensions={".csv"}, excluded_dirs={"drafts"})

    assert listed_ids(source) == ["b.csv"]


def test_skips_binary_non_utf8_and_oversized_files(tmp_path: Path) -> None:
    write(tmp_path, "ok.txt", "fine")
    write(tmp_path, "binary.txt", b"abc\x00def")
    write(tmp_path, "latin1.txt", "café".encode("latin-1"))
    write(tmp_path, "big.txt", "x" * 101)

    source = LocalDirectorySource(tmp_path, max_bytes=100)

    assert listed_ids(source) == ["ok.txt"]
    assert skipped(source) == {
        "big.txt": "too large",
        "binary.txt": "binary",
        "latin1.txt": "not utf-8",
    }


def test_nul_byte_anywhere_marks_file_binary(tmp_path: Path) -> None:
    write(tmp_path, "late.md", b"a" * 9000 + b"\x00tail")

    source = LocalDirectorySource(tmp_path)

    assert listed_ids(source) == []
    assert skipped(source) == {"late.md": "binary"}


def test_skips_files_whose_names_are_not_utf8(tmp_path: Path) -> None:
    (tmp_path / os.fsdecode(b"\xff.md")).write_text("x", encoding="utf-8")

    source = LocalDirectorySource(tmp_path)

    assert listed_ids(source) == []
    assert [s.reason for s in source.skipped] == ["non-utf-8 name"]


@pytest.mark.parametrize("name", ["a\nfake.md", "a\x1b]0;pwn\x07.md", "a\x7f.md"])
def test_skips_files_whose_names_contain_control_characters(tmp_path: Path, name: str) -> None:
    (tmp_path / name).write_text("x", encoding="utf-8")

    source = LocalDirectorySource(tmp_path)

    assert listed_ids(source) == []
    assert [s.reason for s in source.skipped] == ["unsafe name"]


def test_directory_swapped_for_symlink_mid_listing_never_reads_outside_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    write(root, "d/a.md", "a")
    write(root, "d/b.md", "inside")
    write(tmp_path, "outside/b.md", "SECRET")
    source = LocalDirectorySource(root)

    refs = source.list_documents()
    assert next(refs).id == "d/a.md"
    (root / "d").rename(root / "d_old")
    (root / "d").symlink_to(tmp_path / "outside", target_is_directory=True)
    rest = list(refs)

    assert all(ref.fingerprint != fingerprint(b"SECRET") for ref in rest)


def test_skips_fifos_without_blocking(tmp_path: Path) -> None:
    os.mkfifo(tmp_path / "pipe.md")

    source = LocalDirectorySource(tmp_path)

    assert listed_ids(source) == []
    assert skipped(source) == {"pipe.md": "not a regular file"}


@unreadable
def test_unreadable_directory_fails_the_listing(tmp_path: Path) -> None:
    # A silently partial listing would make every document under `locked/` look deleted.
    write(tmp_path, "a.md", "a")
    locked = write(tmp_path, "locked/b.md", "b").parent
    locked.chmod(0)
    try:
        with pytest.raises(SourceReadError, match="locked"):
            listed_ids(LocalDirectorySource(tmp_path))
    finally:
        locked.chmod(0o755)


@unreadable
def test_unreadable_file_fails_the_listing(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "a")
    write(tmp_path, "secret.md", "s").chmod(0)

    with pytest.raises(SourceReadError, match=r"secret\.md"):
        listed_ids(LocalDirectorySource(tmp_path))


@unreadable
def test_read_of_unreadable_file_raises_source_read_error(tmp_path: Path) -> None:
    write(tmp_path, "secret.md", "s").chmod(0)

    with pytest.raises(SourceReadError):
        LocalDirectorySource(tmp_path).read("secret.md")


def test_file_deleted_mid_listing_is_treated_as_gone(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "a")
    doomed = write(tmp_path, "b.md", "b")
    source = LocalDirectorySource(tmp_path)

    refs = source.list_documents()
    first = next(refs)
    doomed.unlink()

    assert first.id == "a.md"
    assert list(refs) == []
    assert source.skipped == []


def test_directory_deleted_mid_listing_is_treated_as_gone(tmp_path: Path) -> None:
    write(tmp_path, "a.md", "a")
    write(tmp_path, "z/b.md", "b")
    source = LocalDirectorySource(tmp_path)

    refs = source.list_documents()
    assert next(refs).id == "a.md"
    shutil.rmtree(tmp_path / "z")

    assert list(refs) == []


def test_directory_with_a_wanted_extension_is_not_a_document(tmp_path: Path) -> None:
    (tmp_path / "dir.md").mkdir()

    source = LocalDirectorySource(tmp_path)

    assert listed_ids(source) == []
    with pytest.raises(DocumentNotFoundError):
        source.read("dir.md")


@pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="needs /proc to count fds")
def test_failed_reads_do_not_leak_file_descriptors(tmp_path: Path) -> None:
    (tmp_path / "dir.md").mkdir()
    write(tmp_path, "bin.md", b"\x00")
    os.mkfifo(tmp_path / "pipe.md")
    source = LocalDirectorySource(tmp_path)
    before = len(os.listdir("/proc/self/fd"))

    for _ in range(20):
        for doc_id in ("dir.md", "bin.md", "pipe.md", "missing/x.md"):
            with pytest.raises(DocumentNotFoundError):
                source.read(doc_id)
        listed_ids(source)

    assert len(os.listdir("/proc/self/fd")) == before


def test_skips_symlinks_including_ones_pointing_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = write(tmp_path, "outside/secret.md", "secret")
    write(root, "real.md", "real")
    (root / "link.md").symlink_to(outside)
    (root / "linkdir").symlink_to(outside.parent, target_is_directory=True)

    source = LocalDirectorySource(root)

    assert listed_ids(source) == ["real.md"]
    assert skipped(source) == {"link.md": "symlink"}


def test_skipped_resets_on_each_listing(tmp_path: Path) -> None:
    bad = write(tmp_path, "bad.txt", b"\x00")
    source = LocalDirectorySource(tmp_path)
    listed_ids(source)
    bad.unlink()

    listed_ids(source)

    assert source.skipped == []


def test_touching_a_file_keeps_its_fingerprint_but_editing_changes_it(tmp_path: Path) -> None:
    path = write(tmp_path, "a.md", "v1")
    source = LocalDirectorySource(tmp_path)
    (before,) = source.list_documents()

    os.utime(path, (1_000_000, 1_000_000))
    (touched,) = source.list_documents()
    path.write_text("v2", encoding="utf-8")
    (edited,) = source.list_documents()

    assert touched.fingerprint == before.fingerprint
    assert edited.fingerprint != before.fingerprint


def test_read_returns_text_and_fingerprint_of_what_was_read(tmp_path: Path) -> None:
    write(tmp_path, "docs/a.md", "héllo")

    doc = LocalDirectorySource(tmp_path).read("docs/a.md")

    assert doc.text == "héllo"
    assert doc.ref.id == "docs/a.md"
    assert doc.ref.fingerprint == fingerprint("héllo".encode())


@pytest.mark.parametrize(
    "doc_id",
    [
        "missing.md",
        "../outside.md",
        "docs/../../outside.md",
        "/etc/passwd",
        "",
        ".git/notes.md",
        "image.png",
        "link.md",
        "binary.txt",
        "docs/a.md/x.md",
        "docs\\a.md",
        "./docs/a.md",
        "docs//a.md",
    ],
)
def test_read_rejects_ids_that_list_documents_would_never_yield(
    tmp_path: Path, doc_id: str
) -> None:
    root = tmp_path / "root"
    write(tmp_path, "outside.md", "secret")
    write(root, "docs/a.md", "a")
    write(root, ".git/notes.md", "x")
    write(root, "image.png", b"\x89PNG")
    write(root, "binary.txt", b"\x00")
    (root / "link.md").symlink_to(tmp_path / "outside.md")

    with pytest.raises(DocumentNotFoundError):
        LocalDirectorySource(root).read(doc_id)


def test_read_rejects_paths_through_symlinked_dirs(tmp_path: Path) -> None:
    root = tmp_path / "root"
    write(tmp_path, "outside/secret.md", "secret")
    root.mkdir()
    (root / "linkdir").symlink_to(tmp_path / "outside", target_is_directory=True)

    with pytest.raises(DocumentNotFoundError):
        LocalDirectorySource(root).read("linkdir/secret.md")


def test_root_must_be_an_existing_directory(tmp_path: Path) -> None:
    file = write(tmp_path, "a.md", "x")

    with pytest.raises(FileNotFoundError):
        LocalDirectorySource(tmp_path / "nope")
    with pytest.raises(NotADirectoryError):
        LocalDirectorySource(file)
