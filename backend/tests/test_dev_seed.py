import importlib
from typing import Any

import pytest
from fastapi.testclient import TestClient

from blog_core import layout
from dev_support import seed as seed_module
from dev_support.seed import SeedRefused, StudioError, seed
from studio_api.app import create_app
from studio_api.posts import PostService
from tests.fake_blob_store import InMemoryBlobStore

TITLES = {"Seed draft", "Seed published", "Seed unpublished"}


class ClientStudio:
    """The seed's Studio over the real studio app, in memory."""

    def __init__(self, store: InMemoryBlobStore) -> None:
        self.client = TestClient(create_app(PostService(store)))

    def call(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        response = self.client.request(
            method,
            path,
            headers={"X-Blog-Studio": "1", **(headers or {})},
            json=body,
        )
        if response.status_code >= 400:
            raise StudioError(f"{method} {path}: HTTP {response.status_code}")
        return response.json() if response.content else None


@pytest.fixture
def dev_layout(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BLOG_DRAFTS_CONTAINER", "blog-drafts-dev")
    monkeypatch.setenv("BLOG_PUBLISHED_CONTAINER", "blog-published-dev")
    importlib.reload(layout)
    yield
    monkeypatch.delenv("BLOG_DRAFTS_CONTAINER")
    monkeypatch.delenv("BLOG_PUBLISHED_CONTAINER")
    importlib.reload(layout)


def listing(studio: ClientStudio) -> list[dict]:
    return studio.call("GET", "/posts")["items"]


def test_it_seeds_a_draft_a_published_post_and_one_published_then_unpublished(
    dev_layout: None,
) -> None:
    store = InMemoryBlobStore()
    studio = ClientStudio(store)
    assert set(seed(studio, store)) == TITLES
    posts = {p["title"]: p for p in listing(studio)}
    assert set(posts) == TITLES
    assert posts["Seed published"]["published"] is True
    assert posts["Seed draft"]["published"] is False
    assert posts["Seed unpublished"]["published"] is False
    assert posts["Seed unpublished"]["slug"] == "seed-unpublished"


def test_a_second_run_creates_nothing(dev_layout: None) -> None:
    store = InMemoryBlobStore()
    studio = ClientStudio(store)
    seed(studio, store)
    assert seed(studio, store) == []
    assert len(listing(studio)) == 3


def test_names_that_are_not_dev_names_write_nothing() -> None:
    store = InMemoryBlobStore()
    studio = ClientStudio(store)
    with pytest.raises(SeedRefused, match="-dev"):
        seed(studio, store)
    assert listing(studio) == []


def test_it_stops_before_writing_when_the_api_points_at_another_store(
    dev_layout: None,
) -> None:
    other = InMemoryBlobStore()
    elsewhere = ClientStudio(other)
    elsewhere.call("POST", "/posts", body={"title": "A real post"})
    dev = InMemoryBlobStore()
    with pytest.raises(SeedRefused, match="differ"):
        seed(elsewhere, dev)
    assert [p["title"] for p in listing(elsewhere)] == ["A real post"]
    assert dev.list(layout.DRAFTS, "") == []


def test_main_refuses_an_api_that_is_not_on_loopback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("STUDIO_API_URL", "https://blog-studio.example")
    assert seed_module.main() == 2
    assert "127.0.0.1" in capsys.readouterr().err
