import logging
import os
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from blog_api.media import AzureMediaLinker, MediaLinker
from blog_api.principal import ApiError
from blog_api.reader import PublishedReader
from blog_api.routes import create_router
from blog_core.app_factory import create_base_app
from blog_core.azure_store import AzureBlobStore
from blog_core.problem import problem

API_VERSION = "1.0.0"
DEFAULT_ROLE = "Blog.Read"


@dataclass
class Wiring:
    reader: PublishedReader
    linker: MediaLinker


def _wiring_from_env() -> Wiring:
    url = os.environ.get("BLOG_STORAGE_ACCOUNT_URL")
    if not url:
        raise ApiError(503, "Service Unavailable", "storage is not configured")
    client_id = os.environ.get("AZURE_CLIENT_ID")
    store = AzureBlobStore.from_account(url, managed_identity_client_id=client_id)
    linker = AzureMediaLinker.from_account(url, managed_identity_client_id=client_id)
    return Wiring(PublishedReader(store), linker)


def create_app(
    reader: PublishedReader | None = None,
    linker: MediaLinker | None = None,
    required_role: str | None = None,
) -> FastAPI:
    # The OpenAPI document sits behind the platform token validation like every
    # route except /healthz; interactive docs stay off.
    app = create_base_app("blog-api", openapi_url="/v1/openapi.json")
    app.version = API_VERSION
    app.state.required_role = required_role or os.environ.get(
        "BLOG_REQUIRED_ROLE", DEFAULT_ROLE
    )
    injected = (
        Wiring(reader, linker) if reader is not None and linker is not None else None
    )
    app.state.wiring = injected

    def resolve() -> Wiring:
        if app.state.wiring is None:
            app.state.wiring = _wiring_from_env()
        return app.state.wiring

    app.state.resolve = resolve

    @app.exception_handler(ApiError)
    def _api_error(_: Request, e: ApiError):
        return problem(e.status, e.title, e.detail)

    @app.exception_handler(RequestValidationError)
    def _bad_request(_: Request, e: RequestValidationError):
        return problem(400, "Bad Request", "a query or path parameter is not valid")

    @app.exception_handler(Exception)
    def _unexpected(_: Request, e: Exception):
        # Fixed client text; only the exception class is logged (an SDK error
        # can carry the account URL or a blob path).
        logging.getLogger("blog_api").error("unhandled %s", type(e).__name__)
        return problem(500, "Internal Server Error")

    app.include_router(create_router())
    return app


app = create_app()
