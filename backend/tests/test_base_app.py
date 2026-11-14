import asyncio
from http import HTTPStatus

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from blog_core.app_factory import MAX_REQUEST_BYTES, BodyLimit, create_base_app


def make_app():
    app = create_base_app("t")
    seen = {"calls": 0, "bytes": 0}

    @app.post("/echo")
    async def echo(request: Request) -> dict:
        seen["calls"] += 1
        body = await request.body()
        seen["bytes"] = len(body)
        return {"bytes": len(body)}

    @app.post("/headers")
    async def headers(request: Request) -> dict:
        return {
            "content_length": request.headers.get("content-length"),
            "transfer_encoding": request.headers.get("transfer-encoding"),
        }

    return app, seen


def is_problem(response, status: int) -> bool:
    return (
        response.status_code == status
        and response.headers["content-type"].startswith("application/problem+json")
        and response.json()["status"] == status
    )


def test_a_declared_body_over_the_cap_is_413_and_the_route_never_runs() -> None:
    app, seen = make_app()
    client = TestClient(app)
    response = client.post("/echo", content=b"x" * (MAX_REQUEST_BYTES + 1))
    assert is_problem(response, 413)
    assert seen["calls"] == 0


def test_a_body_of_exactly_the_cap_is_accepted() -> None:
    app, seen = make_app()
    response = TestClient(app).post("/echo", content=b"x" * MAX_REQUEST_BYTES)
    assert response.status_code == 200
    assert response.json() == {"bytes": MAX_REQUEST_BYTES}


def test_the_test_client_sends_a_generator_body_without_content_length() -> None:
    # Probe: proves the chunked test below does not take the declared-length path.
    app, _ = make_app()

    def chunks():
        yield b"x" * 10

    response = TestClient(app).post("/headers", content=chunks())
    assert response.json() == {"content_length": None, "transfer_encoding": "chunked"}


def test_a_chunked_body_is_aborted_once_it_passes_the_cap() -> None:
    app, seen = make_app()
    total = 3 * MAX_REQUEST_BYTES

    def chunks():
        for _ in range(total // 65536):
            yield b"x" * 65536

    response = TestClient(app).post("/echo", content=chunks())
    assert is_problem(response, 413)
    assert seen["bytes"] == 0  # the handler never got a body


def test_a_chunked_body_stops_being_read_past_the_cap() -> None:
    # Hand-built ASGI: no Content-Length, many messages; the counting path must
    # stop reading once the cap is passed.
    reads = {"n": 0}
    messages = 40
    chunk = b"x" * 65536  # 40 chunks = 2.5 MiB

    async def inner(scope, receive, send):
        while True:
            message = await receive()
            if not message.get("more_body"):
                break
        raise AssertionError("handler must not finish reading")

    async def receive():
        reads["n"] += 1
        return {
            "type": "http.request",
            "body": chunk,
            "more_body": reads["n"] < messages,
        }

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/x",
        "headers": [(b"transfer-encoding", b"chunked")],
    }
    asyncio.run(BodyLimit(inner)(scope, receive, send))
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 413
    assert reads["n"] == MAX_REQUEST_BYTES // 65536 + 1  # 17 reads, not 40


def test_a_request_without_a_body_is_not_affected() -> None:
    app, _ = make_app()
    assert TestClient(app).get("/healthz").json() == {"status": "ok"}


def test_unknown_paths_and_wrong_methods_are_problem_json_with_fixed_text() -> None:
    app, _ = make_app()
    client = TestClient(app)
    missing = client.get("/secret/path")
    assert is_problem(missing, 404)
    assert "secret" not in missing.text
    wrong = client.get("/echo")
    assert is_problem(wrong, 405)
    assert wrong.headers["allow"] == "POST"


@pytest.mark.parametrize("status", [401, 403, 409, 412])
def test_an_http_exception_from_a_route_keeps_its_status_and_headers_but_not_its_text(
    status: int,
) -> None:
    app, _ = make_app()

    @app.get("/boom")
    def boom() -> None:
        raise HTTPException(status, detail="internal detail", headers={"X-Kept": "yes"})

    response = TestClient(app).get("/boom")
    assert is_problem(response, status)
    assert response.headers["x-kept"] == "yes"
    assert response.json()["title"] == HTTPStatus(status).phrase
    assert "internal detail" not in response.text


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_documentation_routes_stay_404(path: str) -> None:
    app, _ = make_app()
    assert is_problem(TestClient(app).get(path), 404)
