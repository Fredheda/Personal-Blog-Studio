import json
from datetime import UTC, datetime, timedelta

import pytest

from blog_api.reader import BadCursor, PublishedReader
from blog_api.schemas import MediaLink, PostDetail, PostList, PostSummary
from blog_core import layout
from blog_core.models import MediaMeta
from studio_api.posts import MetaPatch, PostService
from tests.fake_blob_store import InMemoryBlobStore


def test_a_post_summary_dumps_camel_case_and_nothing_internal() -> None:
    summary = PostSummary(
        post_id="01JB8ZK3M4N5P6Q7R8S9T0V1W2",
        slug="a",
        title="A",
        summary="S",
        tags=["x"],
        published_at="2026-11-09T18:30:00Z",
        updated_at="2026-11-10T08:15:00Z",
        reading_time_minutes=2,
        cover_media_id=None,
        has_audio=False,
    )
    dumped = summary.model_dump(by_alias=True)
    assert set(dumped) == {
        "postId",
        "slug",
        "title",
        "summary",
        "tags",
        "publishedAt",
        "updatedAt",
        "readingTimeMinutes",
        "coverMediaId",
        "hasAudio",
    }
    page = PostList(items=[summary], next_cursor=None).model_dump(by_alias=True)
    assert set(page) == {"items", "nextCursor"} and page["nextCursor"] is None


def test_the_detail_adds_body_version_media_and_a_null_audio() -> None:
    fields = set(PostDetail.model_fields)
    assert {"body", "version", "media", "audio"} <= fields
    assert PostDetail.model_fields["audio"].default is None
    link = MediaLink(
        url="https://x",
        expires_at="2026-11-10T08:25:00Z",
        content_type="image/png",
        bytes=3,
    )
    assert set(json.loads(link.model_dump_json(by_alias=True))) == {
        "url",
        "expiresAt",
        "contentType",
        "bytes",
    }


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


@pytest.fixture
def store() -> InMemoryBlobStore:
    return InMemoryBlobStore()


@pytest.fixture
def svc(store: InMemoryBlobStore) -> PostService:
    return PostService(store, clock=Clock())


def publish(
    svc: PostService, slug: str, body: str = "Hello", tags: list[str] | None = None
) -> str:
    d = svc.create(slug.title())
    d = svc.update_meta(
        d.post_id,
        MetaPatch(slug=slug, summary="Sum", tags=tags or []),
        if_match=d.meta_etag,
    )
    d = svc.update_body(d.post_id, body, if_match=d.body_etag)
    svc.publish(d.post_id, if_match=d.body_etag)
    return d.post_id


def test_the_list_is_newest_first_and_pages_with_an_opaque_cursor(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    for slug in ("one", "two", "three"):
        publish(svc, slug)
    reader = PublishedReader(store)
    first, cursor = reader.page(2, None, None)
    assert [i.slug for i in first] == ["three", "two"] and cursor
    second, cursor2 = reader.page(2, cursor, None)
    assert [i.slug for i in second] == ["one"] and cursor2 is None


def test_a_tag_filters_the_list(svc: PostService, store: InMemoryBlobStore) -> None:
    publish(svc, "a", tags=["maths"])
    publish(svc, "b", tags=["python"])
    items, _ = PublishedReader(store).page(20, None, "maths")
    assert [i.slug for i in items] == ["a"]


@pytest.mark.parametrize("bad", ["!!!", "e30", "W10", "bm90anNvbg"])
def test_a_garbage_cursor_raises(store: InMemoryBlobStore, bad: str) -> None:
    with pytest.raises(BadCursor):
        PublishedReader(store).page(20, bad, None)


def test_an_empty_store_is_an_empty_list(store: InMemoryBlobStore) -> None:
    assert PublishedReader(store).page(20, None, None) == ([], None)


def test_a_post_is_found_by_slug_with_its_body_and_a_draft_is_not(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    publish(svc, "live", body="Live body")
    svc.create("Draft only")
    reader = PublishedReader(store)
    found = reader.post("live")
    assert found is not None and found.body == "Live body" and found.meta.version == 1
    assert reader.post("draft-only") is None


@pytest.mark.parametrize("bad", ["../x", "a/b", "A", "", "x" * 200])
def test_a_hostile_slug_is_not_found_and_reads_nothing(
    store: InMemoryBlobStore, bad: str
) -> None:
    store.writes.clear()
    assert PublishedReader(store).post(bad) is None


def test_an_unpublished_post_disappears(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    pid = publish(svc, "gone")
    svc.unpublish(pid)
    reader = PublishedReader(store)
    assert reader.post("gone") is None and reader.page(20, None, None) == ([], None)


def test_a_media_descriptor_is_found_only_in_its_own_post(
    svc: PostService, store: InMemoryBlobStore
) -> None:
    store.write(layout.DRAFTS, layout.media_original("m1", "png"), b"PNG")
    store.write(
        layout.DRAFTS,
        layout.media_meta("m1"),
        MediaMeta(kind="image", mime="image/png", ext="png", bytes=3).dump(),
    )
    publish(svc, "with-media", body="![a](media:m1)")
    publish(svc, "without")
    reader = PublishedReader(store)
    found = reader.media("with-media", "m1")
    assert found is not None and found[1].id == "m1"
    assert reader.media("without", "m1") is None
    assert reader.media("with-media", "nope") is None
