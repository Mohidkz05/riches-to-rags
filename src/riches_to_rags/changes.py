"""Change detection: compare what a source holds now with what the index last saw."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from riches_to_rags.sources.base import DocumentRef


class DuplicateDocumentError(ValueError):
    """A source yielded the same document ID twice, so the diff would be ambiguous."""


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """Every document ID in either state lands in exactly one bucket. Buckets are sorted by ID."""

    added: tuple[DocumentRef, ...]
    modified: tuple[DocumentRef, ...]
    deleted: tuple[str, ...]
    unchanged: tuple[DocumentRef, ...]

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.modified or self.deleted)


def diff(current: Iterable[DocumentRef], indexed: Mapping[str, str]) -> ChangeSet:
    """Classify documents by comparing the source's refs with the index's {id: fingerprint}."""
    seen: dict[str, DocumentRef] = {}
    for ref in current:
        if ref.id in seen:
            raise DuplicateDocumentError(f"source yielded {ref.id!r} more than once")
        seen[ref.id] = ref

    added: list[DocumentRef] = []
    modified: list[DocumentRef] = []
    unchanged: list[DocumentRef] = []
    for doc_id in sorted(seen):
        ref = seen[doc_id]
        old = indexed.get(doc_id)
        if old is None:
            added.append(ref)
        elif old != ref.fingerprint:
            modified.append(ref)
        else:
            unchanged.append(ref)

    deleted = tuple(sorted(indexed.keys() - seen.keys()))
    return ChangeSet(tuple(added), tuple(modified), deleted, tuple(unchanged))
