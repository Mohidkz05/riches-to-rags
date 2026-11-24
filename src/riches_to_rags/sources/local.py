"""A source backed by a directory on the local filesystem."""

import errno
import os
import stat
import unicodedata
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from riches_to_rags.sources.base import (
    Document,
    DocumentNotFoundError,
    DocumentRef,
    SourceReadError,
    fingerprint,
)

DEFAULT_EXTENSIONS = frozenset(
    {
        # prose
        ".md", ".markdown", ".mdx", ".txt", ".rst", ".adoc",
        # code
        ".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp",
        ".hpp", ".cs", ".rb", ".php", ".swift", ".sh", ".sql",
        # config and markup
        ".toml", ".yaml", ".yml", ".json", ".html", ".css",
    }
)  # fmt: skip
DEFAULT_EXCLUDED_DIRS = frozenset(
    {"node_modules", "__pycache__", "venv", "dist", "build", "target", "site-packages"}
)
DEFAULT_MAX_BYTES = 2 * 1024 * 1024

# O_NOFOLLOW: refuse a symlink. O_NONBLOCK: don't hang opening a FIFO (the fstat check rejects it).
# O_NOCTTY: a tty device under root can't become our controlling terminal.
_FILE_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_NOCTTY | os.O_CLOEXEC
_DIR_OPEN_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


@dataclass(frozen=True, slots=True)
class SkippedFile:
    """A file that matched the filters but can't be indexed as text."""

    id: str
    reason: str


class _SkipError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LocalDirectorySource:
    """Documents are text files under `root`; a document's ID is its POSIX path relative to root.

    Hidden directories and `excluded_dirs` are not descended into, and only files whose suffix is
    in `extensions` are considered. Symlinks are never followed at any path component (reads go
    through directory file descriptors), so nothing outside `root` can be listed or read, except
    via hard links, which are indistinguishable from ordinary files. POSIX only (uses `os.fwalk`
    and `dir_fd`). A renamed file shows up as one deletion plus one addition.

    Files that can never be indexed as text (binary, non-UTF-8, too large, symlinks) are recorded
    in `skipped`. Anything unreadable (permissions, I/O errors) raises `SourceReadError` instead,
    because a document missing from the listing would be treated as deleted.
    """

    def __init__(
        self,
        root: Path,
        *,
        extensions: Iterable[str] = DEFAULT_EXTENSIONS,
        excluded_dirs: Iterable[str] = DEFAULT_EXCLUDED_DIRS,
        max_bytes: int = DEFAULT_MAX_BYTES,
    ) -> None:
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise NotADirectoryError(root)
        self.extensions = frozenset(ext.lower() for ext in extensions)
        self.excluded_dirs = frozenset(excluded_dirs)
        self.max_bytes = max_bytes
        # Files skipped during the most recent `list_documents()` run.
        self.skipped: list[SkippedFile] = []

    def list_documents(self) -> Iterator[DocumentRef]:
        self.skipped = []
        # fwalk hands us an open fd for each directory and never follows symlinks, so a directory
        # swapped for a symlink mid-walk can't redirect reads outside root.
        for dirpath, dirnames, filenames, dir_fd in os.fwalk(self.root, onerror=_raise_unreadable):
            dirnames[:] = sorted(d for d in dirnames if not self._is_excluded_dir(d))
            for name in sorted(filenames):
                if not self._has_wanted_extension(name):
                    continue
                path = Path(dirpath) / name
                doc_id = path.relative_to(self.root).as_posix()
                try:
                    _check_name(doc_id)
                    data = self._read_checked(name, dir_fd)
                except _SkipError as skip:
                    self.skipped.append(SkippedFile(doc_id, skip.reason))
                    continue
                except FileNotFoundError:
                    continue  # deleted since fwalk saw it, so it's genuinely gone
                except OSError as err:
                    raise SourceReadError(f"can't read {path}: {err.strerror}") from err
                yield DocumentRef(doc_id, fingerprint(data))

    def read(self, doc_id: str) -> Document:
        parts = self._parts_for(doc_id)
        try:
            dir_fd = self._open_parent_dir(parts[:-1])
            try:
                data = self._read_checked(parts[-1], dir_fd)
            finally:
                os.close(dir_fd)
        except (_SkipError, FileNotFoundError, NotADirectoryError) as err:
            raise DocumentNotFoundError(doc_id) from err
        except OSError as err:
            if err.errno == errno.ELOOP:  # a symlinked directory along the path
                raise DocumentNotFoundError(doc_id) from err
            raise SourceReadError(f"can't read {doc_id!r}: {err.strerror}") from err
        return Document(DocumentRef(doc_id, fingerprint(data)), data.decode("utf-8"))

    def _is_excluded_dir(self, name: str) -> bool:
        return name.startswith(".") or name in self.excluded_dirs

    def _has_wanted_extension(self, name: str) -> bool:
        return PurePosixPath(name).suffix.lower() in self.extensions

    def _parts_for(self, doc_id: str) -> tuple[str, ...]:
        """Split an ID into path parts, accepting only IDs that `list_documents()` could yield."""
        parts = tuple(doc_id.split("/"))
        try:
            _check_name(doc_id)
        except _SkipError:
            raise DocumentNotFoundError(doc_id) from None
        if (
            "\\" in doc_id
            or "\x00" in doc_id
            or any(part in ("", ".", "..") for part in parts)
            or any(self._is_excluded_dir(part) for part in parts[:-1])
            or not self._has_wanted_extension(parts[-1])
        ):
            raise DocumentNotFoundError(doc_id)
        return parts

    def _open_parent_dir(self, dir_parts: tuple[str, ...]) -> int:
        """Open each directory relative to the previous one's fd, refusing symlinks at each step."""
        dir_fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for part in dir_parts:
                child = os.open(part, _DIR_OPEN_FLAGS, dir_fd=dir_fd)
                os.close(dir_fd)
                dir_fd = child
        except BaseException:
            os.close(dir_fd)
            raise
        return dir_fd

    def _read_checked(self, name: str, dir_fd: int) -> bytes:
        """Read the file `name` inside the open directory `dir_fd`.

        Raise `_SkipError` if it can't be indexed as text. All checks run on the opened file
        descriptor, so swapping the file for a symlink, FIFO or bigger file after it was listed
        can't change what gets read.
        """
        try:
            fd = os.open(name, _FILE_OPEN_FLAGS, dir_fd=dir_fd)
        except OSError as err:
            if err.errno == errno.ELOOP:
                raise _SkipError("symlink") from None
            raise
        try:
            # Check before fdopen: fdopen raises on a directory without closing the fd.
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise _SkipError("not a regular file")
        except BaseException:
            os.close(fd)
            raise
        with os.fdopen(fd, "rb") as f:
            data = f.read(self.max_bytes + 1)
        if len(data) > self.max_bytes:
            raise _SkipError("too large")
        # NUL is valid UTF-8 but marks binary content, and Postgres text can't store it.
        if b"\x00" in data:
            raise _SkipError("binary")
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise _SkipError("not utf-8") from None
        return data


def _check_name(doc_id: str) -> None:
    """Reject IDs that can't be stored or printed safely."""
    # Undecodable filename bytes arrive as lone surrogates, which can't be encoded or stored.
    try:
        doc_id.encode("utf-8")
    except UnicodeEncodeError:
        raise _SkipError("non-utf-8 name") from None
    # Newlines and escape sequences in names would forge output lines or drive the terminal.
    if any(unicodedata.category(ch) == "Cc" for ch in doc_id):
        raise _SkipError("unsafe name")


def _raise_unreadable(err: OSError) -> None:
    if isinstance(err, FileNotFoundError):
        return  # deleted since its parent was listed, so it's genuinely gone
    raise SourceReadError(f"can't read {err.filename}: {err.strerror}") from err
