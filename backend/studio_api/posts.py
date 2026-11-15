"""Post authoring: drafts, revisions, publish and unpublish.

All state lives in blob storage (spec section 4). The service holds none.
Concurrency: a draft body and a draft's metadata are written with the ETag the
caller last saw (`if_match`), so two tabs cannot silently overwrite each other.
Publish writes the immutable snapshot first and the shared lookups last, so a
reader never sees a half-published version.
"""

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from blog_core import layout
from blog_core.ids import is_slug, new_id
from blog_core.models import (
    DraftMeta,
    IndexEntry,
    MediaDescriptor,
    MediaMeta,
    PublishedIndex,
    PublishedMeta,
    SlugRef,
    now_iso,
)
from blog_core.store import Blob, BlobStore, PreconditionFailed
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
from studio_api.markdown import MAX_BODY_BYTES, Problem, validate_body

INDEX_RETRIES = 3
WORDS_PER_MINUTE = 200
_FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Draft:
    post_id: str
    meta: DraftMeta
    body: str
    meta_etag: str
    body_etag: str
    edited_at: str  # the later of the last details save and the last body save
    published_version: int | None  # None: not published now
    published_at: str | None  # first publish time; None: not published now
    slug_locked: bool  # published at least once

    @property
    def published(self) -> bool:
        return self.published_version is not None


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    problems: list[Problem]
    body_etag: str
    meta_etag: str


@dataclass(frozen=True)
class _Blockers:
    """Everything publish refuses on, collected without raising."""

    problems: list[Problem]  # title, slug, summary and the Markdown rules
    media_ids: list[str]
    media: dict[str, MediaMeta]
    missing_media: list[str]
    slug_blob: Blob | None
    slug_taken: bool


@dataclass(frozen=True)
class DraftSummary:
    post_id: str
    title: str
    slug: str
    updated_at: str  # the later of the last details save and the last body save
    published_version: int | None
    published_at: str | None

    @property
    def published(self) -> bool:
        return self.published_version is not None


class MetaPatch(BaseModel):
    """The fields of `draft.json` the editor may change; None leaves one alone."""

    title: str | None = None
    slug: str | None = None
    summary: str | None = None
    tags: list[str] | None = None
    cover_media_id: str | None = None
    clear_cover: bool = False


def _reading_minutes(body: str) -> int:
    words = len(re.findall(r"\w+", _FENCE.sub("", body)))
    return max(1, math.ceil(words / WORDS_PER_MINUTE))


def _later(stamp: str, modified: datetime | None) -> str:
    """The later of a stored `updatedAt` and a blob's modified time. Both are in
    `now_iso` form (fixed width), so strings compare in time order."""
    return max(stamp, now_iso(modified)) if modified is not None else stamp


class PostService:
    def __init__(
        self,
        store: BlobStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        new_post_id: Callable[[], str] = new_id,
    ) -> None:
        self._store = store
        self._clock = clock
        self._new_post_id = new_post_id

    # drafts -----------------------------------------------------------------

    def create(self, title: str) -> Draft:
        now = now_iso(self._clock())
        meta = DraftMeta(title=title, created_at=now, updated_at=now)
        post_id = self._new_post_id()
        self._store.write(
            layout.DRAFTS,
            layout.draft_meta(post_id),
            meta.dump(),
            content_type="application/json",
            create_only=True,
        )
        self._store.write(
            layout.DRAFTS,
            layout.draft_body(post_id),
            b"",
            content_type="text/markdown",
            create_only=True,
        )
        return self.get(post_id)

    def get(self, post_id: str) -> Draft:
        meta_blob = self._store.read(layout.DRAFTS, layout.draft_meta(post_id))
        body_blob = self._store.read(layout.DRAFTS, layout.draft_body(post_id))
        if meta_blob is None or body_blob is None:
            raise PostNotFound(post_id)
        meta = DraftMeta.model_validate_json(meta_blob.content)
        body_path = layout.draft_body(post_id)
        modified = self._store.modified_times(layout.DRAFTS, body_path).get(body_path)
        entry = self._index_entries().get(post_id)
        return Draft(
            post_id=post_id,
            meta=meta,
            body=body_blob.content.decode(),
            meta_etag=meta_blob.etag,
            body_etag=body_blob.etag,
            edited_at=_later(meta.updated_at, modified),
            published_version=entry.version if entry else None,
            published_at=entry.published_at if entry else None,
            slug_locked=entry is not None or self._ever_published(post_id),
        )

    def list_drafts(self) -> list[DraftSummary]:
        modified = self._store.modified_times(layout.DRAFTS, "posts/")
        entries = self._index_entries()
        found = []
        for name in sorted(modified):
            if name.endswith("/draft.json"):
                post_id = name.split("/")[1]
                blob = self._store.read(layout.DRAFTS, name)
                if blob is not None:
                    meta = DraftMeta.model_validate_json(blob.content)
                    entry = entries.get(post_id)
                    found.append(
                        DraftSummary(
                            post_id,
                            meta.title,
                            meta.slug,
                            _later(
                                meta.updated_at,
                                modified.get(layout.draft_body(post_id)),
                            ),
                            entry.version if entry else None,
                            entry.published_at if entry else None,
                        )
                    )
        return sorted(found, key=lambda d: d.updated_at, reverse=True)

    def update_body(self, post_id: str, body: str, *, if_match: str) -> Draft:
        self._require(post_id)
        if len(body.encode()) > MAX_BODY_BYTES:  # also bounds restore and the agent
            raise ValidationFailed(
                [Problem(0, f"body is larger than {MAX_BODY_BYTES} bytes")]
            )
        try:
            self._store.write(
                layout.DRAFTS,
                layout.draft_body(post_id),
                body.encode(),
                content_type="text/markdown",
                if_match=if_match,
            )
        except PreconditionFailed as e:
            raise StaleEtag("the draft changed; reload it") from e
        return self.get(post_id)

    def update_meta(self, post_id: str, patch: MetaPatch, *, if_match: str) -> Draft:
        draft = self.get(post_id)
        changes = patch.model_dump(exclude_none=True, exclude={"clear_cover"})
        if patch.clear_cover:
            changes["cover_media_id"] = None
        if "slug" in changes and changes["slug"] != draft.meta.slug:
            if self._ever_published(post_id):
                raise SlugLocked("the slug is fixed once the post has been published")
        try:
            meta = DraftMeta.model_validate(
                {
                    **draft.meta.model_dump(),
                    **changes,
                    "updated_at": now_iso(self._clock()),
                }
            )
        except ValidationError as e:
            raise ValidationFailed(
                [
                    Problem(0, err["msg"].removeprefix("Value error, "))
                    for err in e.errors()
                ]
            ) from e
        try:
            self._store.write(
                layout.DRAFTS,
                layout.draft_meta(post_id),
                meta.dump(),
                content_type="application/json",
                if_match=if_match,
            )
        except PreconditionFailed as e:
            raise StaleEtag("the draft's details changed; reload it") from e
        return self.get(post_id)

    def delete(self, post_id: str) -> None:
        draft = self.get(post_id)
        if self._is_published(draft):
            raise StillPublished("unpublish the post before deleting it")
        for name in self._store.list(layout.DRAFTS, layout.post_folder(post_id)):
            self._store.delete(layout.DRAFTS, name)

    # revisions --------------------------------------------------------------

    def checkpoint(self, post_id: str) -> str:
        """Save the current body as a revision; returns the revision id."""
        draft = self.get(post_id)
        stamp = self._clock().astimezone(UTC).strftime("%Y%m%dT%H%M%S%f")[:-3] + "Z"
        counter = 0
        while True:
            revision = stamp if counter == 0 else f"{stamp}{counter}"
            try:
                self._store.write(
                    layout.DRAFTS,
                    layout.revision_body(post_id, revision),
                    draft.body.encode(),
                    content_type="text/markdown",
                    create_only=True,
                )
                return revision
            except PreconditionFailed:
                counter += 1

    def list_revisions(self, post_id: str) -> list[str]:
        """Revision ids, newest first."""
        self._require(post_id)
        prefix = layout.revision_prefix(post_id)
        names = self._store.list(layout.DRAFTS, prefix)
        return sorted((n[len(prefix) : -len(".md")] for n in names), reverse=True)

    def get_revision(self, post_id: str, revision: str) -> str:
        blob = self._store.read(layout.DRAFTS, layout.revision_body(post_id, revision))
        if blob is None:
            raise PostNotFound(f"{post_id}@{revision}")
        return blob.content.decode()

    def restore_revision(self, post_id: str, revision: str, *, if_match: str) -> Draft:
        draft = self.get(post_id)
        if (
            draft.body_etag != if_match
        ):  # checked first: a stale request leaves no revision
            raise StaleEtag("the draft changed; reload it")
        body = self.get_revision(post_id, revision)
        self.checkpoint(post_id)  # the body being replaced stays recoverable
        return self.update_body(post_id, body, if_match=draft.body_etag)

    # publish ----------------------------------------------------------------

    def publish(self, post_id: str, *, if_match: str) -> PublishedMeta:
        draft = self.get(post_id)
        if draft.body_etag != if_match:
            raise StaleEtag("the draft changed; reload it")
        meta = draft.meta
        blockers = self._blockers(draft)
        if blockers.problems:
            raise ValidationFailed(blockers.problems)
        if blockers.missing_media:
            raise MissingMedia(blockers.missing_media)
        if blockers.slug_taken:
            raise SlugTaken(meta.slug)
        media_ids, media, slug_blob = (
            blockers.media_ids,
            blockers.media,
            blockers.slug_blob,
        )

        version = self._latest_version(post_id) + 1
        self.checkpoint(post_id)
        now = now_iso(self._clock())
        published_at = self._first_published_at(post_id, version) or now

        descriptors = []
        for media_id in media_ids:
            info = media[media_id]
            target = layout.version_media(post_id, version, media_id, info.ext)
            self._store.copy(
                layout.DRAFTS,
                layout.media_original(media_id, info.ext),
                layout.PUBLISHED,
                target,
            )
            descriptors.append(
                MediaDescriptor(
                    id=media_id,
                    kind=info.kind,
                    mime=info.mime,
                    bytes=info.bytes,
                    width=info.width,
                    height=info.height,
                    duration_sec=info.duration_sec,
                    alt=info.alt,
                    blob_path=target,
                )
            )
        published = PublishedMeta(
            post_id=post_id,
            slug=meta.slug,
            version=version,
            title=meta.title,
            summary=meta.summary,
            tags=meta.tags,
            published_at=published_at,
            updated_at=now,
            reading_time_minutes=_reading_minutes(draft.body),
            cover_media_id=meta.cover_media_id,
            media=descriptors,
        )
        self._store.write(
            layout.PUBLISHED,
            layout.version_body(post_id, version),
            draft.body.encode(),
            content_type="text/markdown",
            create_only=True,
        )
        self._store.write(
            layout.PUBLISHED,
            layout.version_meta(post_id, version),
            published.dump(),
            content_type="application/json",
            create_only=True,
        )
        ref = SlugRef(post_id=post_id, version=version).dump()
        try:
            self._store.write(
                layout.PUBLISHED,
                layout.slug_ref(meta.slug),
                ref,
                content_type="application/json",
                create_only=slug_blob is None,
                if_match=slug_blob.etag if slug_blob else None,
            )
        except PreconditionFailed as e:
            raise Conflict("the slug was taken or changed while publishing") from e
        entry = IndexEntry(**published.model_dump(exclude={"media", "audio"}))
        self._update_index(
            lambda items: sorted(
                [i for i in items if i.post_id != post_id] + [entry],
                key=lambda i: (i.published_at, i.post_id),
                reverse=True,
            )
        )
        return published

    def unpublish(self, post_id: str) -> None:
        draft = self.get(post_id)
        if not self._is_published(draft):
            return
        self._update_index(lambda items: [i for i in items if i.post_id != post_id])
        self._store.delete(layout.PUBLISHED, layout.slug_ref(draft.meta.slug))

    def check(self, post_id: str) -> CheckResult:
        """What publish would refuse on, for what is saved. Writes nothing."""
        draft = self.get(post_id)
        blockers = self._blockers(draft)
        problems = list(blockers.problems)
        if blockers.missing_media:
            problems.append(Problem(0, str(MissingMedia(blockers.missing_media))))
        if blockers.slug_taken:
            problems.append(
                Problem(
                    0, f"the slug {draft.meta.slug} is already used by another post"
                )
            )
        return CheckResult(not problems, problems, draft.body_etag, draft.meta_etag)

    # helpers ----------------------------------------------------------------

    def _require(self, post_id: str) -> None:
        if self._store.read(layout.DRAFTS, layout.draft_meta(post_id)) is None:
            raise PostNotFound(post_id)

    def _is_published(self, draft: Draft) -> bool:
        if not draft.meta.slug or not is_slug(draft.meta.slug):
            return False
        blob = self._store.read(layout.PUBLISHED, layout.slug_ref(draft.meta.slug))
        return (
            blob is not None
            and SlugRef.model_validate_json(blob.content).post_id == draft.post_id
        )

    def _ever_published(self, post_id: str) -> bool:
        # meta.json is written after the body and before the slug ref, so a first
        # publish that died halfway leaves no meta.json and does not lock the slug.
        names = self._store.list(layout.PUBLISHED, layout.versions_prefix(post_id))
        return any(name.endswith("/meta.json") for name in names)

    def _latest_version(self, post_id: str) -> int:
        prefix = layout.versions_prefix(post_id)
        versions = [
            int(match.group(1))
            for name in self._store.list(layout.PUBLISHED, prefix)
            if (match := re.match(r"v(\d+)/", name[len(prefix) :]))
        ]
        return max(versions, default=0)

    def _first_published_at(self, post_id: str, version: int) -> str | None:
        for earlier in range(version - 1, 0, -1):
            blob = self._store.read(
                layout.PUBLISHED, layout.version_meta(post_id, earlier)
            )
            if blob is not None:
                return PublishedMeta.model_validate_json(blob.content).published_at
        return None

    def _blockers(self, draft: Draft) -> _Blockers:
        """The one place publish's rules live: publish raises on them, check lists them."""
        meta = draft.meta
        problems = [
            Problem(0, f"{name} is required")
            for name, value in (
                ("title", meta.title),
                ("slug", meta.slug),
                ("summary", meta.summary),
            )
            if not value.strip()
        ]
        checked = validate_body(draft.body)
        problems += checked.problems

        media_ids = list(checked.media_ids)
        if meta.cover_media_id and meta.cover_media_id not in media_ids:
            media_ids.append(meta.cover_media_id)
        media: dict[str, MediaMeta] = {}
        missing = []
        for media_id in media_ids:
            blob = self._store.read(layout.DRAFTS, layout.media_meta(media_id))
            if blob is None:
                missing.append(media_id)
            else:
                media[media_id] = MediaMeta.model_validate_json(blob.content)

        slug_blob = (
            self._store.read(layout.PUBLISHED, layout.slug_ref(meta.slug))
            if meta.slug
            else None
        )
        taken = (
            slug_blob is not None
            and SlugRef.model_validate_json(slug_blob.content).post_id != draft.post_id
        )
        return _Blockers(problems, media_ids, media, missing, slug_blob, taken)

    def _index_entries(self) -> dict[str, IndexEntry]:
        """The published posts by id: one read of `index.json`."""
        blob = self._store.read(layout.PUBLISHED, layout.INDEX)
        if blob is None:
            return {}
        return {
            i.post_id: i for i in PublishedIndex.model_validate_json(blob.content).items
        }

    def _update_index(
        self, change: Callable[[list[IndexEntry]], list[IndexEntry]]
    ) -> None:
        for _ in range(INDEX_RETRIES):
            blob: Blob | None = self._store.read(layout.PUBLISHED, layout.INDEX)
            items = (
                PublishedIndex.model_validate_json(blob.content).items if blob else []
            )
            new = PublishedIndex(items=change(items)).dump()
            try:
                self._store.write(
                    layout.PUBLISHED,
                    layout.INDEX,
                    new,
                    content_type="application/json",
                    create_only=blob is None,
                    if_match=blob.etag if blob else None,
                )
                return
            except PreconditionFailed:
                continue
        raise Conflict("the published index is busy; try again")
