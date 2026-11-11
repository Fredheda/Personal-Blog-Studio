"""The stored JSON documents. Field names are camelCase on disk and in the API.

Readers ignore unknown fields, so adding a field is never a breaking change.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel

from blog_core import ids

TITLE_MAX = 200
SUMMARY_MAX = 500
TAGS_MAX = 10


def now_iso(moment: datetime | None = None) -> str:
    """UTC, second precision, `Z` suffix (ISO 8601)."""
    moment = moment or datetime.now(UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    def dump(self) -> bytes:
        return self.model_dump_json(by_alias=True, indent=2).encode()


class DraftMeta(CamelModel):
    """`blog-drafts/posts/{postId}/draft.json`."""

    title: str = ""
    slug: str = ""
    summary: str = ""
    tags: list[str] = []
    cover_media_id: str | None = None
    created_at: str
    updated_at: str

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        if len(value) > TITLE_MAX:
            raise ValueError(f"title is longer than {TITLE_MAX} characters")
        return value

    @field_validator("summary")
    @classmethod
    def _summary(cls, value: str) -> str:
        if len(value) > SUMMARY_MAX:
            raise ValueError(f"summary is longer than {SUMMARY_MAX} characters")
        return value

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str) -> str:
        if value and not ids.is_slug(value):
            raise ValueError("slug must be lowercase letters, digits and single dashes")
        return value

    @field_validator("tags")
    @classmethod
    def _tags(cls, value: list[str]) -> list[str]:
        if len(value) > TAGS_MAX or len(set(value)) != len(value):
            raise ValueError(f"at most {TAGS_MAX} distinct tags")
        if not all(ids.is_tag(t) for t in value):
            raise ValueError("a tag is lowercase letters, digits and dashes, 50 at most")
        return value

    @field_validator("cover_media_id")
    @classmethod
    def _cover(cls, value: str | None) -> str | None:
        if value is not None and not ids.is_media_id(value):
            raise ValueError("cover media id is not a media id")
        return value


class MediaMeta(CamelModel):
    """`blog-drafts/media/{mediaId}/meta.json`, written by the upload ticket."""

    kind: Literal["image", "video"]
    mime: str
    ext: str
    bytes: int
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    alt: str = ""
    sha256: str = ""


class MediaDescriptor(CamelModel):
    """One entry of `media[]` in a published `meta.json`."""

    id: str
    kind: Literal["image", "video"]
    mime: str
    bytes: int
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    alt: str = ""
    blob_path: str


class PublishedMeta(CamelModel):
    """`blog-published/posts/{postId}/v{n}/meta.json`. Immutable once written."""

    post_id: str
    slug: str
    version: int
    title: str
    summary: str
    tags: list[str]
    published_at: str
    updated_at: str
    reading_time_minutes: int
    cover_media_id: str | None = None
    media: list[MediaDescriptor] = []
    audio: None = None  # read-aloud is out of v1; the field stays for later


class IndexEntry(CamelModel):
    """One published post in `blog-published/index.json` (summaries only)."""

    post_id: str
    slug: str
    version: int
    title: str
    summary: str
    tags: list[str]
    published_at: str
    updated_at: str
    reading_time_minutes: int
    cover_media_id: str | None = None
    has_audio: bool = False


class PublishedIndex(CamelModel):
    items: list[IndexEntry] = []  # newest first


class SlugRef(CamelModel):
    """`blog-published/slugs/{slug}.json`."""

    post_id: str
    version: int
