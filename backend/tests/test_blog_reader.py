import json

from blog_api.schemas import MediaLink, PostDetail, PostList, PostSummary


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
