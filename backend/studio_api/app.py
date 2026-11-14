import os
from collections.abc import Iterable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from blog_core.app_factory import create_base_app
from blog_core.azure_store import AzureBlobStore
from blog_core.problem import problem
from studio_api import errors
from studio_api.posts import PostService
from studio_api.routes import ApiError, create_router

_STATUS = {
    errors.PostNotFound: (404, "Not Found"),
    errors.StaleEtag: (412, "Precondition Failed"),
    errors.Conflict: (409, "Conflict"),
    errors.SlugLocked: (409, "Conflict"),
    errors.SlugTaken: (409, "Conflict"),
    errors.StillPublished: (409, "Conflict"),
}


def _service_from_env() -> PostService:
    url = os.environ.get("BLOG_STORAGE_ACCOUNT_URL")
    if not url:
        raise ApiError(503, "Service Unavailable", "storage is not configured")
    store = AzureBlobStore.from_account(
        url, managed_identity_client_id=os.environ.get("AZURE_CLIENT_ID")
    )
    return PostService(store)


def _origins_from_env() -> frozenset[str]:
    raw = os.environ.get("BLOG_STUDIO_ORIGINS", "")
    return frozenset(o.strip() for o in raw.split(",") if o.strip())


def create_app(
    service: PostService | None = None, allowed_origins: Iterable[str] | None = None
) -> FastAPI:
    app = create_base_app("blog-studio-api")
    app.state.service = service
    app.state.allowed_origins = (
        frozenset(allowed_origins)
        if allowed_origins is not None
        else _origins_from_env()
    )

    def resolve_service() -> PostService:
        if app.state.service is None:
            app.state.service = _service_from_env()
        return app.state.service

    app.state.resolve_service = resolve_service

    @app.exception_handler(ApiError)
    def _api_error(_: Request, e: ApiError):
        return problem(e.status, e.title, e.detail)

    @app.exception_handler(errors.PostError)
    def _post_error(_: Request, e: errors.PostError):
        if isinstance(e, errors.ValidationFailed):
            return problem(
                422,
                "Unprocessable Content",
                str(e),
                problems=[{"line": p.line, "message": p.message} for p in e.problems],
            )
        if isinstance(e, errors.MissingMedia):
            return problem(422, "Unprocessable Content", str(e), mediaIds=e.media_ids)
        status, title = _STATUS.get(type(e), (500, "Internal Server Error"))
        return problem(status, title, str(e))

    @app.exception_handler(RequestValidationError)
    def _request_invalid(_: Request, e: RequestValidationError):
        return problem(
            422,
            "Unprocessable Content",
            "the request body is not valid",
            problems=[{"line": 0, "message": err["msg"]} for err in e.errors()],
        )

    app.include_router(create_router())
    return app


app = create_app()
