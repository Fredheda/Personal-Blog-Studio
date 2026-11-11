import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from blog_core.models import (
    DraftMeta,
    IndexEntry,
    PublishedIndex,
    PublishedMeta,
    SlugRef,
    now_iso,
)

T = "2026-11-10T12:00:00Z"


def draft(**kw) -> DraftMeta:
    return DraftMeta(created_at=T, updated_at=T, **kw)


def test_now_iso_is_utc_second_precision_with_z() -> None:
    moment = datetime(2026, 11, 10, 14, 0, 5, 999999, tzinfo=timezone(timedelta(hours=2)))
    assert now_iso(moment) == "2026-11-10T12:00:05Z"
    assert now_iso().endswith("Z") and len(now_iso()) == 20


def test_documents_are_written_camel_case_and_read_back() -> None:
    d = draft(title="T", cover_media_id="m1")
    raw = json.loads(d.dump())
    assert raw["coverMediaId"] == "m1" and raw["createdAt"] == T and "cover_media_id" not in raw
    assert DraftMeta.model_validate_json(d.dump()) == d


def test_unknown_fields_are_ignored() -> None:
    raw = json.dumps({"createdAt": T, "updatedAt": T, "futureField": 1})
    assert DraftMeta.model_validate_json(raw).title == ""


@pytest.mark.parametrize(
    "kw",
    [
        {"title": "x" * 201},
        {"summary": "x" * 501},
        {"slug": "Bad Slug"},
        {"slug": "a--b"},
        {"tags": [f"t{i}" for i in range(11)]},
        {"tags": ["a", "a"]},
        {"tags": ["Not Ok"]},
        {"cover_media_id": "bad/id"},
    ],
)
def test_draft_rejects_bad_values(kw: dict) -> None:
    with pytest.raises(ValidationError):
        draft(**kw)


def test_draft_accepts_limits_and_an_empty_slug() -> None:
    assert draft(title="x" * 200, summary="y" * 500, slug="", tags=[f"t{i}" for i in range(10)])


def test_published_documents_round_trip_with_camel_case_keys() -> None:
    meta = PublishedMeta(
        post_id="01ARZ3NDEKTSV4RRFFQ69G5FAV", slug="s", version=1, title="T", summary="S", tags=[],
        published_at=T, updated_at=T, reading_time_minutes=3,
    )
    raw = json.loads(meta.dump())
    assert raw["readingTimeMinutes"] == 3 and raw["audio"] is None and raw["media"] == []
    entry = IndexEntry(**meta.model_dump(exclude={"media", "audio"}))
    assert json.loads(PublishedIndex(items=[entry]).dump())["items"][0]["hasAudio"] is False
    assert SlugRef(post_id="p", version=2).dump() == b'{\n  "postId": "p",\n  "version": 2\n}'
