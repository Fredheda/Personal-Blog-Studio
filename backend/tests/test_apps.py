import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blog_api.app import create_app as create_blog_api
from studio_api.app import create_app as create_studio_api

BACKEND = Path(__file__).resolve().parents[1]

APPS = [("studio_api", create_studio_api), ("blog_api", create_blog_api)]


@pytest.fixture(params=APPS, ids=[name for name, _ in APPS])
def client(request) -> TestClient:
    _, factory = request.param
    return TestClient(factory())


def test_healthz_returns_ok_and_nothing_else(client: TestClient):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_is_get_only(client: TestClient):
    assert client.post("/healthz").status_code == 405


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_no_default_documentation_routes(client: TestClient, path: str):
    assert client.get(path).status_code == 404


def test_unknown_path_is_a_plain_404(client: TestClient):
    response = client.get("/nope")
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def _modules_after_import(module: str) -> set[str]:
    """Import `module` in a fresh interpreter with an empty environment."""
    code = f"import json, sys; import {module}; print(json.dumps(sorted(sys.modules)))"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND,
        env={},
        capture_output=True,
        text=True,
        check=True,
    )
    return set(json.loads(result.stdout))


def test_apps_import_with_an_empty_environment():
    for module in ("studio_api.app", "blog_api.app"):
        assert module in _modules_after_import(module)


def test_blog_api_does_not_import_studio_code():
    loaded = _modules_after_import("blog_api.app")
    forbidden = ("studio_api", "langgraph", "langchain", "anthropic", "elevenlabs")
    top_level = {name.split(".")[0] for name in loaded}
    assert not [name for name in top_level if name.startswith(forbidden)]
