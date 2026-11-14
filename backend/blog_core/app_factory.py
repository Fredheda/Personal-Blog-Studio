from http import HTTPStatus

from fastapi import FastAPI, Request
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from blog_core.problem import problem

MAX_REQUEST_BYTES = 1_048_576  # 1 MiB for every request of both APIs


class _TooLarge(Exception):
    """Raised inside `receive` once a body passes the cap."""


class BodyLimit:
    """Refuse a request body over `max_bytes`.

    A declared `Content-Length` over the cap is answered before the app runs.
    A body without one (chunked) is counted as it arrives and aborted past the
    cap, so a client cannot make the server buffer it.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def _refuse(self, scope: Scope, receive: Receive, send: Send) -> None:
        response = problem(413, "Content Too Large", "the request body is too large")
        await response(scope, receive, send)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declared = Headers(scope=scope).get("content-length")
        if (
            declared is not None
            and declared.isdigit()
            and int(declared) > self.max_bytes
        ):
            await self._refuse(scope, receive, send)
            return

        seen = 0
        started = False  # the app began a response before the body overflowed
        overflow = False
        answered = False  # our 413 has been sent

        async def limited_receive() -> Message:
            nonlocal seen, overflow
            message = await receive()
            if message["type"] == "http.request":
                seen += len(message.get("body", b""))
                if seen > self.max_bytes:
                    overflow = not started
                    raise _TooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started, answered
            if overflow:
                # FastAPI turns an exception raised while it parses a body into
                # its own 400 (and a handler may swallow it and answer 200): the
                # answer to an oversize body is always our 413, and the app's own
                # response messages are dropped.
                if not answered:
                    answered = True
                    await self._refuse(scope, receive, send)
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _TooLarge:
            if started:
                raise
        if overflow and not answered:
            answered = True
            await self._refuse(scope, receive, send)


def create_base_app(title: str, *, openapi_url: str | None = None) -> FastAPI:
    """Return a FastAPI app with the shared secure defaults.

    The interactive documentation routes stay off. An app that publishes an
    OpenAPI document passes its own `openapi_url`. The only route is
    `GET /healthz`, which returns no data and needs no authentication. Request
    bodies are capped at `MAX_REQUEST_BYTES`; unknown paths and wrong methods
    answer with problem+json and fixed text.
    """
    app = FastAPI(title=title, docs_url=None, redoc_url=None, openapi_url=openapi_url)
    app.add_middleware(BodyLimit)

    @app.exception_handler(StarletteHTTPException)
    def _http_error(_: Request, e: StarletteHTTPException):
        # Every HTTPException (routing 404 and 405, and any a route or
        # dependency raises, 401/403/409/412 included) becomes problem+json
        # with the standard phrase of its status as the title: the detail the
        # raiser passed is not echoed, its headers (Allow, WWW-Authenticate,
        # ...) are kept.
        try:
            title_text = HTTPStatus(e.status_code).phrase
        except ValueError:
            title_text = "Error"
        # Framing headers are the response's own business: a raiser that passes
        # content-length or content-type must not corrupt the problem body.
        kept = {
            name: value
            for name, value in (e.headers or {}).items()
            if name.lower()
            not in {"content-length", "content-type", "transfer-encoding"}
        }
        return problem(e.status_code, title_text, headers=kept)

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
