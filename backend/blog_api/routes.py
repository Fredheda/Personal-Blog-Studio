"""The four read routes of API v1. Plain `def` handlers: FastAPI runs them in
its thread pool because the storage client is synchronous."""

import hashlib
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response

from blog_api.media import MediaLinker
from blog_api.principal import ApiError, require_role
from blog_api.reader import BadCursor, PublishedReader
from blog_api.schemas import (
    AudioLink,
    MediaDescriptor,
    MediaLink,
    PostDetail,
    PostList,
    PostSummary,
    Problem,
)
from blog_core import layout
from blog_core.ids import is_media_id, is_slug

CACHE_CONTROL = "private, max-age=60"
PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": Problem, "description": "No valid token."},
    403: {"model": Problem, "description": "The caller lacks the Blog.Read role."},
}


def get_reader(request: Request) -> PublishedReader:
    return request.app.state.resolve().reader


def get_linker(request: Request) -> MediaLinker:
    return request.app.state.resolve().linker


Reader = Annotated[PublishedReader, Depends(get_reader)]
Linker = Annotated[MediaLinker, Depends(get_linker)]


def cached_json(request: Request, payload: dict[str, Any]) -> Response:
    body = json.dumps(
        payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False
    ).encode()
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    wanted = [v.strip() for v in request.headers.get("if-none-match", "").split(",")]
    if etag in wanted or "*" in wanted:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def create_router() -> APIRouter:
    router = APIRouter(prefix="/v1", dependencies=[Depends(require_role)])

    @router.get(
        "/posts",
        response_model=PostList,
        responses={
            **PROBLEM_RESPONSES,
            304: {"description": "Not modified."},
            400: {"model": Problem},
        },
    )
    def list_posts(
        request: Request,
        reader: Reader,
        limit: Annotated[int, Query(ge=1, le=50)] = 20,
        cursor: Annotated[str | None, Query(max_length=200)] = None,
        tag: Annotated[
            str | None, Query(max_length=50)
        ] = None,  # TAG max, blog_core.ids
    ) -> Response:
        try:
            items, next_cursor = reader.page(limit, cursor, tag)
        except BadCursor:
            raise ApiError(400, "Bad Request", "the cursor is not valid") from None
        page = PostList(
            items=[
                PostSummary(**item.model_dump()) for item in items
            ],  # IndexEntry fields match
            next_cursor=next_cursor,
        )
        return cached_json(request, page.model_dump(by_alias=True))

    @router.get(
        "/posts/{slug}",
        response_model=PostDetail,
        responses={
            **PROBLEM_RESPONSES,
            304: {"description": "Not modified."},
            404: {"model": Problem},
        },
    )
    def get_post(slug: str, request: Request, reader: Reader) -> Response:
        published = reader.post(slug)
        if published is None:
            raise ApiError(404, "Not Found", "no published post with this slug")
        meta = published.meta
        detail = PostDetail(
            **meta.model_dump(exclude={"media", "audio"}),
            has_audio=False,
            audio=None,
            body=published.body,
            media=[
                MediaDescriptor(**d.model_dump(exclude={"blob_path"}))
                for d in meta.media
            ],
        )
        return cached_json(request, detail.model_dump(by_alias=True))

    # The template and the argument are `mediaId`, exactly as in the committed
    # contract: FastAPI takes the path parameter name from the template.
    @router.get(
        "/media/{mediaId}",
        response_model=MediaLink,
        responses={
            **PROBLEM_RESPONSES,
            400: {"model": Problem},
            404: {"model": Problem},
        },
    )
    def get_media(  # noqa: N803
        mediaId: str,
        post: str,
        reader: Reader,
        linker: Linker,
    ) -> Response:
        if not is_slug(post) or not is_media_id(mediaId):
            raise ApiError(404, "Not Found", "no such media")
        found = reader.media(post, mediaId)
        if found is None:
            raise ApiError(404, "Not Found", "no such media for this post")
        _, descriptor = found
        link = linker.link(
            layout.PUBLISHED,
            descriptor.blob_path,
            content_type=descriptor.mime,
            size=descriptor.bytes,
        )
        return Response(
            link.model_dump_json(by_alias=True),
            media_type="application/json",
            headers={"Cache-Control": "no-store"},
        )

    # response_model documents the shape clients will get once audio ships; in
    # v1 the route always answers 404.
    @router.get(
        "/posts/{slug}/audio",
        response_model=AudioLink,
        responses={**PROBLEM_RESPONSES, 404: {"model": Problem}},
    )
    def get_audio(slug: str) -> Response:
        raise ApiError(404, "Not Found", "this post has no audio")

    return router
