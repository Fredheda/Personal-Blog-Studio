"""One contract for every BlobStore: the in-memory fake always, Azurite when
AZURITE_CONNECTION_STRING is set (a local run; see DEPLOYMENT.md)."""

import os
import uuid

import pytest

from blog_core.store import PreconditionFailed, StoreError
from tests.fake_blob_store import InMemoryBlobStore

AZURITE = os.environ.get("AZURITE_CONNECTION_STRING")


@pytest.fixture(params=["memory", "azurite"])
def stores(request):
    """(store, source container, destination container)."""
    names = (f"t{uuid.uuid4().hex[:12]}a", f"t{uuid.uuid4().hex[:12]}b")
    if request.param == "memory":
        yield InMemoryBlobStore(), *names
        return
    if not AZURITE:
        pytest.skip("AZURITE_CONNECTION_STRING is not set")
    from blog_core.azure_store import AzureBlobStore

    store = AzureBlobStore.from_connection_string(AZURITE)
    for name in names:
        store.service.create_container(name)
    try:
        yield store, *names
    finally:
        for name in names:
            store.service.delete_container(name)


def test_a_missing_blob_reads_as_none(stores) -> None:
    store, a, _ = stores
    assert store.read(a, "nope.txt") is None


def test_write_then_read_returns_the_content_and_the_etag(stores) -> None:
    store, a, _ = stores
    etag = store.write(a, "x/y.txt", b"hello", content_type="text/plain")
    blob = store.read(a, "x/y.txt")
    assert blob is not None and blob.content == b"hello" and blob.etag == etag


def test_an_overwrite_changes_the_etag(stores) -> None:
    store, a, _ = stores
    first = store.write(a, "f", b"1")
    second = store.write(a, "f", b"2")
    assert first != second and store.read(a, "f").content == b"2"


def test_create_only_refuses_an_existing_blob_and_keeps_it(stores) -> None:
    store, a, _ = stores
    store.write(a, "f", b"1", create_only=True)
    with pytest.raises(PreconditionFailed):
        store.write(a, "f", b"2", create_only=True)
    assert store.read(a, "f").content == b"1"


def test_if_match_writes_only_with_the_current_etag(stores) -> None:
    store, a, _ = stores
    first = store.write(a, "f", b"1")
    second = store.write(a, "f", b"2", if_match=first)
    with pytest.raises(PreconditionFailed):
        store.write(a, "f", b"3", if_match=first)  # stale
    assert store.read(a, "f").content == b"2"
    assert store.write(a, "f", b"4", if_match=second)


def test_if_match_on_a_missing_blob_fails(stores) -> None:
    store, a, _ = stores
    with pytest.raises(PreconditionFailed):
        store.write(a, "gone", b"1", if_match='"0x1"')
    assert store.read(a, "gone") is None


def test_delete_removes_and_a_missing_delete_is_quiet(stores) -> None:
    store, a, _ = stores
    store.write(a, "f", b"1")
    store.delete(a, "f")
    store.delete(a, "f")
    assert store.read(a, "f") is None


def test_list_returns_sorted_names_under_a_prefix_only(stores) -> None:
    store, a, b = stores
    for path in ("posts/2/draft.md", "posts/1/draft.md", "posts/1/rev/1.md", "other"):
        store.write(a, path, b"x")
    store.write(b, "posts/1/elsewhere", b"x")
    assert store.list(a, "posts/1/") == ["posts/1/draft.md", "posts/1/rev/1.md"]
    assert store.list(a, "nothing/") == []


def test_copy_duplicates_across_containers_and_keeps_the_source(stores) -> None:
    store, a, b = stores
    store.write(a, "media/m/original.png", b"\x89PNG", content_type="image/png")
    store.copy(a, "media/m/original.png", b, "posts/p/v1/media/m.png")
    assert store.read(b, "posts/p/v1/media/m.png").content == b"\x89PNG"
    assert store.read(a, "media/m/original.png") is not None


def test_copy_of_a_missing_source_raises_store_error_and_writes_nothing(stores) -> None:
    store, a, b = stores
    with pytest.raises(StoreError):
        store.copy(a, "media/none/original.png", b, "posts/p/v1/media/none.png")
    assert store.read(b, "posts/p/v1/media/none.png") is None
