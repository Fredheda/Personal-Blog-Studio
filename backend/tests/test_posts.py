from datetime import UTC, datetime, timedelta

import pytest

from blog_core import layout
from blog_core.models import MediaMeta
from studio_api.errors import (
    Conflict,
    MissingMedia,
    PostNotFound,
    SlugLocked,
    SlugTaken,
    StaleEtag,
    StillPublished,
    ValidationFailed,
)
from studio_api.markdown import MAX_BODY_BYTES
from studio_api.posts import MetaPatch, PostService
from tests.fake_blob_store import InMemoryBlobStore


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now


@pytest.fixture
def store() -> InMemoryBlobStore:
    return InMemoryBlobStore()


@pytest.fixture
def svc(store: InMemoryBlobStore) -> PostService:
    return PostService(store, clock=Clock())


def published_bytes(store: InMemoryBlobStore, path: str) -> bytes:
    blob = store.read(layout.PUBLISHED, path)
    assert blob is not None, path
    return blob.content


def ready(svc: PostService, slug: str = "hello", body: str = "Hello **world**.") -> str:
    d = svc.create("Hello")
    d = svc.update_meta(
        d.post_id, MetaPatch(slug=slug, summary="Sum"), if_match=d.meta_etag
    )
    svc.update_body(d.post_id, body, if_match=d.body_etag)
    return d.post_id


def test_create_makes_an_empty_draft(svc: PostService) -> None:
    d = svc.create("Hi")
    assert d.meta.title == "Hi" and d.body == "" and len(d.post_id) == 26


def test_get_unknown_post(svc: PostService) -> None:
    with pytest.raises(PostNotFound):
        svc.get("01ARZ3NDEKTSV4RRFFQ69G5FAV")


def test_stale_body_etag_conflicts_and_keeps_the_newer_body(svc: PostService) -> None:
    d = svc.create("t")
    svc.update_body(d.post_id, "one", if_match=d.body_etag)
    with pytest.raises(Conflict):
        svc.update_body(d.post_id, "two", if_match=d.body_etag)
    assert svc.get(d.post_id).body == "one"


def test_an_oversized_save_is_refused_and_leaves_the_draft_unchanged(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    d = svc.create("t")
    d = svc.update_body(d.post_id, "small", if_match=d.body_etag)
    store.writes.clear()
    with pytest.raises(ValidationFailed) as e:
        svc.update_body(d.post_id, "a" * (MAX_BODY_BYTES + 1), if_match=d.body_etag)
    assert "larger than" in str(e.value)
    assert store.writes == []
    assert svc.get(d.post_id).body == "small"


def test_meta_validation_reports_problems(svc: PostService) -> None:
    d = svc.create("t")
    with pytest.raises(ValidationFailed):
        svc.update_meta(d.post_id, MetaPatch(slug="Bad Slug"), if_match=d.meta_etag)


def test_cover_can_be_cleared(svc: PostService) -> None:
    d = svc.create("t")
    d = svc.update_meta(d.post_id, MetaPatch(cover_media_id="m1"), if_match=d.meta_etag)
    assert d.meta.cover_media_id == "m1"
    d = svc.update_meta(d.post_id, MetaPatch(clear_cover=True), if_match=d.meta_etag)
    assert d.meta.cover_media_id is None


def test_checkpoints_list_newest_first_and_restore_keeps_the_replaced_body(
    svc: PostService,
) -> None:
    d = svc.create("t")
    d = svc.update_body(d.post_id, "v1", if_match=d.body_etag)
    first = svc.checkpoint(d.post_id)
    d = svc.update_body(d.post_id, "v2", if_match=d.body_etag)
    second = svc.checkpoint(d.post_id)
    assert svc.list_revisions(d.post_id) == [second, first]
    d = svc.get(d.post_id)
    restored = svc.restore_revision(d.post_id, first, if_match=d.body_etag)
    assert restored.body == "v1"
    assert len(svc.list_revisions(d.post_id)) == 3


def test_two_checkpoints_in_the_same_millisecond_do_not_collide(
    store: InMemoryBlobStore,
) -> None:
    frozen = datetime(2026, 1, 1, tzinfo=UTC)
    svc = PostService(store, clock=lambda: frozen)
    d = svc.create("t")
    a, b = svc.checkpoint(d.post_id), svc.checkpoint(d.post_id)
    assert a != b


def test_publish_requires_title_slug_summary_and_clean_body(svc: PostService) -> None:
    d = svc.create("T")
    with pytest.raises(ValidationFailed) as e:
        svc.publish(d.post_id, if_match=d.body_etag)
    assert "slug is required" in str(e.value) and "summary is required" in str(e.value)
    pid = ready(svc, body="<script>x</script>")
    d = svc.get(pid)
    with pytest.raises(ValidationFailed):
        svc.publish(pid, if_match=d.body_etag)


def test_publish_with_stale_etag_conflicts(svc: PostService) -> None:
    pid = ready(svc)
    with pytest.raises(StaleEtag):
        svc.publish(pid, if_match='"stale"')


def test_a_stale_etag_is_a_conflict_subclass_and_every_stale_path_raises_it(
    svc: PostService,
) -> None:
    assert issubclass(StaleEtag, Conflict)
    d = svc.create("t")
    svc.update_body(d.post_id, "one", if_match=d.body_etag)
    with pytest.raises(StaleEtag):
        svc.update_body(d.post_id, "two", if_match=d.body_etag)
    with pytest.raises(StaleEtag):
        svc.update_meta(d.post_id, MetaPatch(summary="s"), if_match='"stale"')


def test_a_stale_restore_leaves_no_extra_revision(svc: PostService) -> None:
    d = svc.create("t")
    d = svc.update_body(d.post_id, "v1", if_match=d.body_etag)
    revision = svc.checkpoint(d.post_id)
    with pytest.raises(StaleEtag):
        svc.restore_revision(d.post_id, revision, if_match='"stale"')
    assert svc.list_revisions(d.post_id) == [revision]


def test_publish_writes_snapshot_slug_and_index_in_that_order(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = ready(svc)
    store.writes.clear()
    meta = svc.publish(pid, if_match=svc.get(pid).body_etag)
    published = [p for c, p in store.writes if c == layout.PUBLISHED]
    assert published == [
        f"posts/{pid}/v1/post.md",
        f"posts/{pid}/v1/meta.json",
        "slugs/hello.json",
        "index.json",
    ]
    assert meta.version == 1 and meta.reading_time_minutes == 1
    assert published_bytes(store, f"posts/{pid}/v1/post.md") == b"Hello **world**."


def test_publish_copies_media_and_records_descriptors(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = ready(svc, body="![a](media:m1)")
    store.write(layout.DRAFTS, layout.media_original("m1", "png"), b"PNG")
    store.write(
        layout.DRAFTS,
        layout.media_meta("m1"),
        MediaMeta(kind="image", mime="image/png", ext="png", bytes=3).dump(),
    )
    meta = svc.publish(pid, if_match=svc.get(pid).body_etag)
    assert [m.id for m in meta.media] == ["m1"]
    assert published_bytes(store, meta.media[0].blob_path) == b"PNG"


def test_publish_with_unknown_media_changes_nothing(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = ready(svc, body="![a](media:nope)")
    store.writes.clear()
    with pytest.raises(MissingMedia):
        svc.publish(pid, if_match=svc.get(pid).body_etag)
    assert [w for w in store.writes if w[0] == layout.PUBLISHED] == []


def test_republish_adds_a_version_keeps_published_at_and_replaces_the_index_entry(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = ready(svc)
    first = svc.publish(pid, if_match=svc.get(pid).body_etag)
    d = svc.get(pid)
    svc.update_body(pid, "Changed", if_match=d.body_etag)
    second = svc.publish(pid, if_match=svc.get(pid).body_etag)
    assert second.version == 2 and second.published_at == first.published_at
    assert second.updated_at > first.updated_at
    assert published_bytes(store, f"posts/{pid}/v1/post.md") == b"Hello **world**."
    index = published_bytes(store, layout.INDEX).decode()
    assert index.count(pid) == 1 and '"version": 2' in index


def test_another_posts_slug_is_taken(svc: PostService) -> None:
    first = ready(svc, slug="same")
    svc.publish(first, if_match=svc.get(first).body_etag)
    other = ready(svc, slug="same")
    with pytest.raises(SlugTaken):
        svc.publish(other, if_match=svc.get(other).body_etag)


def test_a_half_written_first_publish_does_not_lock_the_slug(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = ready(svc)
    # A first publish that died after the body but before meta.json.
    store.write(layout.PUBLISHED, f"posts/{pid}/v1/post.md", b"x")
    d = svc.get(pid)
    renamed = svc.update_meta(pid, MetaPatch(slug="other"), if_match=d.meta_etag)
    assert renamed.meta.slug == "other"


def test_slug_is_locked_after_first_publish(svc: PostService) -> None:
    pid = ready(svc)
    svc.publish(pid, if_match=svc.get(pid).body_etag)
    with pytest.raises(SlugLocked):
        svc.update_meta(pid, MetaPatch(slug="other"), if_match=svc.get(pid).meta_etag)


def test_index_update_retries_on_a_concurrent_change(store: InMemoryBlobStore) -> None:
    svc = PostService(store, clock=Clock())
    pid = ready(svc)
    real_read = store.read
    state = {"n": 0}

    def racing_read(container: str, path: str):
        blob = real_read(container, path)
        if path == layout.INDEX and state["n"] == 0:
            state["n"] += 1
            store.write(container, path, b'{"items": []}')  # someone else wrote first
        return blob

    store.read = racing_read  # type: ignore[method-assign]
    svc.publish(pid, if_match=svc.get(pid).body_etag)
    assert pid in published_bytes(store, layout.INDEX).decode()


def test_unpublish_removes_index_and_slug_but_keeps_versions(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = ready(svc)
    svc.publish(pid, if_match=svc.get(pid).body_etag)
    svc.unpublish(pid)
    assert store.read(layout.PUBLISHED, "slugs/hello.json") is None
    assert pid not in published_bytes(store, layout.INDEX).decode()
    assert store.read(layout.PUBLISHED, f"posts/{pid}/v1/post.md") is not None
    svc.unpublish(pid)  # idempotent


def test_delete_refuses_while_published_then_removes_the_draft_folder(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = ready(svc)
    svc.publish(pid, if_match=svc.get(pid).body_etag)
    with pytest.raises(StillPublished):
        svc.delete(pid)
    svc.unpublish(pid)
    svc.delete(pid)
    assert store.list(layout.DRAFTS, f"posts/{pid}/") == []
    assert svc.list_drafts() == []
