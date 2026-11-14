"""RFC 9457 problem responses, shared by the studio API and the read API."""

from typing import Any

from fastapi.responses import JSONResponse

PROBLEM_JSON = "application/problem+json"


def problem(
    status: int, title: str, detail: str | None = None, **extra: Any
) -> JSONResponse:
    body: dict[str, Any] = {"type": "about:blank", "title": title, "status": status}
    if detail is not None:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON)
