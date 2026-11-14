"""HTTP layer of the studio API. Every rule lives in `PostService`.

Routes are plain `def` so FastAPI runs them in its thread pool: the storage
client is synchronous.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import Field

from blog_core.ids import is_post_id
from blog_core.models import SUMMARY_MAX, TITLE_MAX, CamelModel
from studio_api.errors import PostNotFound
from studio_api.markdown import MAX_BODY_BYTES
from studio_api.posts import Draft, MetaPatch, PostService

_REVISION = re.compile(r"^\d{8}T\d{9}Z\d{0,3}$")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-blog-studio"


class ApiError(Exception):
    def __init__(self, status: int, title: str, detail: str | None = None) -> None:
        super().__init__(title)
        self.status, self.title, self.detail = status, title, detail


class CreateIn(CamelModel):
    title: str = Field(max_length=TITLE_MAX)


class BodyIn(CamelModel):
    # Characters; the service re-checks bytes.
    body: str = Field(max_length=MAX_BODY_BYTES)


class MetaIn(CamelModel):
    title: str | None = Field(default=None, max_length=TITLE_MAX)
    slug: str | None = None
    summary: str | None = Field(default=None, max_length=SUMMARY_MAX)
    tags: list[str] | None = None
    cover_media_id: str | None = None
    clear_cover: bool = False


class DraftOut(CamelModel):
    post_id: str
    title: str
    slug: str
    summary: str
    tags: list[str]
    cover_media_id: str | None
    created_at: str
    updated_at: str
    body: str
    body_etag: str
    meta_etag: str


def _draft_out(draft: Draft) -> dict:
    meta = draft.meta
    return DraftOut(
        post_id=draft.post_id,
        title=meta.title,
        slug=meta.slug,
        summary=meta.summary,
        tags=meta.tags,
        cover_media_id=meta.cover_media_id,
        created_at=meta.created_at,
        updated_at=meta.updated_at,
        body=draft.body,
        body_etag=draft.body_etag,
        meta_etag=draft.meta_etag,
    ).model_dump(by_alias=True)


def guard_same_origin(request: Request) -> None:
    """CSRF defence for state-changing requests (spec section 6)."""
    if request.method in _SAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER) != "1":
        raise ApiError(403, "Forbidden", "missing X-Blog-Studio header")
    allowed = request.app.state.allowed_origins
    origin = request.headers.get("origin")
    if allowed and origin is not None and origin not in allowed:
        raise ApiError(403, "Forbidden", "origin not allowed")


def post_id_param(post_id: str) -> str:
    if not is_post_id(post_id):
        raise PostNotFound(post_id)
    return post_id


def revision_param(revision: str) -> str:
    if not _REVISION.fullmatch(revision):  # `$` would let a trailing newline through
        raise PostNotFound(revision)
    return revision


def require_if_match(if_match: Annotated[str | None, Header()] = None) -> str:
    if not if_match:
        raise ApiError(
            428, "Precondition Required", "send the ETag you last saw in If-Match"
        )
    return if_match


def get_service(request: Request) -> PostService:
    """The app's service; `create_app` builds it lazily on first use."""
    return request.app.state.resolve_service()


# Module-level aliases: pyright rejects a local variable in an annotation.
PostId = Annotated[str, Depends(post_id_param)]
Revision = Annotated[str, Depends(revision_param)]
IfMatch = Annotated[str, Depends(require_if_match)]
Service = Annotated[PostService, Depends(get_service)]


def create_router() -> APIRouter:
    router = APIRouter(dependencies=[Depends(guard_same_origin)])

    @router.post("/posts", status_code=201)
    def create(payload: CreateIn, service: Service, response: Response) -> dict:
        draft = service.create(payload.title)
        response.headers["Location"] = f"/posts/{draft.post_id}"
        return _draft_out(draft)

    @router.get("/posts")
    def list_drafts(service: Service) -> dict:
        return {
            "items": [
                {
                    "postId": d.post_id,
                    "title": d.title,
                    "slug": d.slug,
                    "updatedAt": d.updated_at,
                }
                for d in service.list_drafts()
            ]
        }

    @router.get("/posts/{post_id}")
    def get(post_id: PostId, service: Service) -> dict:
        return _draft_out(service.get(post_id))

    @router.put("/posts/{post_id}/body")
    def put_body(
        post_id: PostId, payload: BodyIn, if_match: IfMatch, service: Service
    ) -> dict:
        return _draft_out(service.update_body(post_id, payload.body, if_match=if_match))

    @router.patch("/posts/{post_id}/meta")
    def patch_meta(
        post_id: PostId, payload: MetaIn, if_match: IfMatch, service: Service
    ) -> dict:
        patch = MetaPatch(**payload.model_dump())
        return _draft_out(service.update_meta(post_id, patch, if_match=if_match))

    @router.delete("/posts/{post_id}", status_code=204)
    def delete(post_id: PostId, service: Service) -> Response:
        service.delete(post_id)
        return Response(status_code=204)

    @router.post("/posts/{post_id}/revisions", status_code=201)
    def checkpoint(post_id: PostId, service: Service) -> dict:
        return {"revision": service.checkpoint(post_id)}

    @router.get("/posts/{post_id}/revisions")
    def revisions(post_id: PostId, service: Service) -> dict:
        return {"items": service.list_revisions(post_id)}

    @router.get("/posts/{post_id}/revisions/{revision}")
    def revision(post_id: PostId, revision: Revision, service: Service) -> dict:
        return {"revision": revision, "body": service.get_revision(post_id, revision)}

    @router.post("/posts/{post_id}/revisions/{revision}/restore")
    def restore(
        post_id: PostId, revision: Revision, if_match: IfMatch, service: Service
    ) -> dict:
        return _draft_out(
            service.restore_revision(post_id, revision, if_match=if_match)
        )

    @router.post("/posts/{post_id}/publish")
    def publish(post_id: PostId, if_match: IfMatch, service: Service) -> dict:
        return service.publish(post_id, if_match=if_match).model_dump(by_alias=True)

    @router.post("/posts/{post_id}/unpublish", status_code=204)
    def unpublish(post_id: PostId, service: Service) -> Response:
        service.unpublish(post_id)
        return Response(status_code=204)

    return router
