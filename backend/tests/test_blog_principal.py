import base64
import json

import pytest
from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from blog_api.principal import ApiError, require_role, roles_from_principal


def header(*claims: tuple[str, str]) -> str:
    body = {"auth_typ": "aad", "claims": [{"typ": t, "val": v} for t, v in claims]}
    return base64.b64encode(json.dumps(body).encode()).decode()


def test_roles_are_read_from_every_role_claim_type() -> None:
    value = header(
        ("roles", "Blog.Read"),
        ("http://schemas.microsoft.com/ws/2008/06/identity/claims/role", "Other"),
        ("appid", "not-a-role"),
    )
    assert roles_from_principal(value) == {"Blog.Read", "Other"}


@pytest.mark.parametrize(
    "bad",
    [
        None,
        "",
        "not base64 !!",
        base64.b64encode(b"not json").decode(),
        base64.b64encode(b"[]").decode(),
        base64.b64encode(b'{"claims": 3}').decode(),
    ],
)
def test_a_missing_or_malformed_principal_is_401(bad: str | None) -> None:
    with pytest.raises(ApiError) as e:
        roles_from_principal(bad)
    assert e.value.status == 401


def make_client(required: str = "Blog.Read") -> TestClient:
    app = FastAPI()
    app.state.required_role = required

    @app.get("/x", dependencies=[Depends(require_role)])
    def x() -> dict:
        return {"ok": True}

    @app.exception_handler(ApiError)
    def handle(_, e: ApiError):
        return JSONResponse({"status": e.status}, status_code=e.status)

    return TestClient(app)


def test_the_required_role_is_enforced() -> None:
    client = make_client()
    ok = client.get(
        "/x", headers={"X-MS-CLIENT-PRINCIPAL": header(("roles", "Blog.Read"))}
    )
    assert ok.status_code == 200
    other = client.get(
        "/x", headers={"X-MS-CLIENT-PRINCIPAL": header(("roles", "Other"))}
    )
    assert other.status_code == 403
    assert client.get("/x").status_code == 401
