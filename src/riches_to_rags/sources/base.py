"""The contract every source implements."""

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol


def fingerprint(data: bytes) -> str:
    """Content fingerprint: hex SHA-256 of the raw bytes.

    Content, not mtime: checkouts, copies and editors move mtimes without changing content.
    """
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class DocumentRef:
    """A document's identity and the version of its content, without the content itself."""

    id: str
    fingerprint: str


@dataclass(frozen=True, slots=True)
class Document:
    """A document's text, with the fingerprint of exactly the bytes that were read.

    The fingerprint can differ from the one `list_documents()` reported if the document changed
    in between; callers should store this one, since it describes the text they actually have.
    """

    ref: DocumentRef
    text: str


class DocumentNotFoundError(LookupError):
    """The ID doesn't name a document this source would list."""


class SourceReadError(OSError):
    """The source couldn't be read completely (permissions, I/O errors).

    Sources raise this instead of returning a partial listing: a document missing from a listing
    is treated as deleted, so a silently incomplete listing would wipe it from the index.
    """


class Source(Protocol):
    """A collection of documents with stable IDs and content fingerprints."""

    def list_documents(self) -> Iterator[DocumentRef]:
        """Yield every current document once, in a deterministic order.

        Raise `SourceReadError` rather than yield an incomplete listing.
        """
        ...

    def read(self, doc_id: str) -> Document:
        """Return the document's text.

        Raise `DocumentNotFoundError` if it isn't listable, `SourceReadError` if it can't be read.
        """
        ...
