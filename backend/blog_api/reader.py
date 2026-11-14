"""Reads published posts from blog storage. Nothing here can see a draft: it
only reads the published container and takes its paths from `blog_core.layout`."""

import base64
import json
from dataclasses import dataclass

from blog_core import layout
from blog_core.ids import is_media_id, is_slug
from blog_core.models import (
    IndexEntry,
    MediaDescriptor,
    PublishedIndex,
    PublishedMeta,
    SlugRef,
)
from blog_core.store import BlobStore


class BadCursor(ValueError):
    """The paging cursor is not one this API issued."""


@dataclass(frozen=True)
class Published:
    meta: PublishedMeta
    body: str


def _encode(entry: IndexEntry) -> str:
    raw = json.dumps(
        {"p": entry.published_at, "i": entry.post_id}, separators=(",", ":")
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode(cursor: str) -> tuple[str, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        data = json.loads(raw)
        return str(data["p"]), str(data["i"])
    except (ValueError, KeyError, TypeError) as e:
        raise BadCursor("not a cursor") from e


class PublishedReader:
    def __init__(self, store: BlobStore) -> None:
        self._store = store

    def _items(self) -> list[IndexEntry]:
        blob = self._store.read(layout.PUBLISHED, layout.INDEX)
        items = PublishedIndex.model_validate_json(blob.content).items if blob else []
        return sorted(items, key=lambda i: (i.published_at, i.post_id), reverse=True)

    def page(
        self, limit: int, cursor: str | None, tag: str | None
    ) -> tuple[list[IndexEntry], str | None]:
        items = [i for i in self._items() if tag is None or tag in i.tags]
        if cursor is not None:
            after = _decode(cursor)
            items = [i for i in items if (i.published_at, i.post_id) < after]
        chunk = items[:limit]
        more = len(items) > limit
        return chunk, (_encode(chunk[-1]) if more and chunk else None)

    def post(self, slug: str) -> Published | None:
        if not is_slug(slug):
            return None
        ref_blob = self._store.read(layout.PUBLISHED, layout.slug_ref(slug))
        if ref_blob is None:
            return None
        ref = SlugRef.model_validate_json(ref_blob.content)
        meta_blob = self._store.read(
            layout.PUBLISHED, layout.version_meta(ref.post_id, ref.version)
        )
        body_blob = self._store.read(
            layout.PUBLISHED, layout.version_body(ref.post_id, ref.version)
        )
        if meta_blob is None or body_blob is None:
            return None
        return Published(
            PublishedMeta.model_validate_json(meta_blob.content),
            body_blob.content.decode(),
        )

    def media(
        self, slug: str, media_id: str
    ) -> tuple[Published, MediaDescriptor] | None:
        if not is_media_id(media_id):
            return None
        published = self.post(slug)
        if published is None:
            return None
        meta = published.meta
        folder = f"{layout.version_meta(meta.post_id, meta.version).rsplit('/', 1)[0]}/media/"
        for descriptor in meta.media:
            # The path is stored data: only sign what sits in this version's media folder.
            name = descriptor.blob_path.removeprefix(folder)
            inside = descriptor.blob_path.startswith(folder) and not (
                "/" in name or ".." in name or name == ""
            )
            if descriptor.id == media_id and inside:
                return published, descriptor
        return None
