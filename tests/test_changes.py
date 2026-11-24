from collections.abc import Mapping

import pytest
from hypothesis import given
from hypothesis import strategies as st

from riches_to_rags.changes import ChangeSet, DuplicateDocumentError, diff
from riches_to_rags.sources.base import DocumentRef

# Small alphabets force overlap between the two states, so every branch gets exercised.
ids = st.text(alphabet="abcd/", min_size=1, max_size=3)
fingerprints = st.sampled_from(["f1", "f2", "f3"])
states = st.dictionaries(ids, fingerprints, max_size=8)


def refs(state: Mapping[str, str]) -> list[DocumentRef]:
    return [DocumentRef(doc_id, fp) for doc_id, fp in state.items()]


def apply(indexed: Mapping[str, str], changes: ChangeSet) -> dict[str, str]:
    """What the index holds after a sync that applies `changes` to `indexed`."""
    result = dict(indexed)
    for doc_id in changes.deleted:
        del result[doc_id]
    for ref in (*changes.added, *changes.modified):
        result[ref.id] = ref.fingerprint
    return result


@given(current=states, indexed=states)
def test_every_id_lands_in_exactly_one_bucket(
    current: dict[str, str], indexed: dict[str, str]
) -> None:
    changes = diff(refs(current), indexed)

    added = {r.id for r in changes.added}
    modified = {r.id for r in changes.modified}
    unchanged = {r.id for r in changes.unchanged}
    deleted = set(changes.deleted)

    everything = added | modified | unchanged | deleted
    assert len(added) + len(modified) + len(unchanged) + len(deleted) == len(everything)
    assert everything == current.keys() | indexed.keys()


@given(current=states, indexed=states)
def test_classification_matches_definitions(
    current: dict[str, str], indexed: dict[str, str]
) -> None:
    changes = diff(refs(current), indexed)

    assert all(r.id not in indexed for r in changes.added)
    assert all(indexed[r.id] != r.fingerprint for r in changes.modified)
    assert all(indexed[r.id] == r.fingerprint for r in changes.unchanged)
    assert all(d not in current for d in changes.deleted)


@given(current=states, indexed=states)
def test_applying_the_diff_reproduces_the_source(
    current: dict[str, str], indexed: dict[str, str]
) -> None:
    assert apply(indexed, diff(refs(current), indexed)) == current


@given(state=states)
def test_diff_against_itself_has_no_changes(state: dict[str, str]) -> None:
    changes = diff(refs(state), state)

    assert not changes.has_changes
    assert len(changes.unchanged) == len(state)


def test_buckets_are_sorted_by_id() -> None:
    changes = diff(refs({"b": "f1", "a": "f1", "c": "f2"}), {"z": "f1", "y": "f1"})

    assert [r.id for r in changes.added] == ["a", "b", "c"]
    assert changes.deleted == ("y", "z")


def test_duplicate_ids_in_source_are_rejected() -> None:
    with pytest.raises(DuplicateDocumentError, match=r"a\.md"):
        diff([DocumentRef("a.md", "f1"), DocumentRef("a.md", "f2")], {})
