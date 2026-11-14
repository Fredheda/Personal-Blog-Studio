"""Response models of the read API v1. Field names are camelCase on the wire."""

from typing import Literal

from pydantic import BaseModel

from blog_core.models import CamelModel


class PostSummary(CamelModel):
    post_id: str
    slug: str
    title: str
    summary: str
    tags: list[str]
    published_at: str
    updated_at: str
    reading_time_minutes: int
    cover_media_id: str | None
    has_audio: bool


class PostList(CamelModel):
    items: list[PostSummary]
    next_cursor: str | None


class MediaDescriptor(CamelModel):
    """A media file of a post, without any URL or storage path."""

    id: str
    kind: Literal["image", "video"]
    mime: str
    bytes: int
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    alt: str = ""


class PostDetail(PostSummary):
    body: str
    version: int
    media: list[MediaDescriptor]
    audio: dict | None = None  # always null in v1


class MediaLink(CamelModel):
    url: str
    expires_at: str
    content_type: str
    bytes: int


class AudioLink(MediaLink):
    duration_sec: float


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str | None = None
