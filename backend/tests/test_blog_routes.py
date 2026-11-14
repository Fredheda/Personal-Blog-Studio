import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from blog_api.app import create_app
from blog_api.reader import PublishedReader
from blog_api.schemas import MediaLink
from blog_core import layout
from blog_core.models import MediaMeta
from studio_api.posts import MetaPatch, PostService
from tests.fake_blob_store import InMemoryBlobStore


def principal(*roles: str) -> dict[str, str]:
    body = {"claims": [{"typ": "roles", "val": r} for r in roles]}
    return {
        "X-MS-CLIENT-PRINCIPAL": base64.b64encode(json.dumps(body).encode()).decode()
    }


READER = principal("Blog.Read")


class FakeLinker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def link(
        self, container: str, path: str, *, content_type: str, size: int
    ) -> MediaLink:
        self.calls.append((container, path))
        return MediaLink(
            url=f"https://example.invalid/{container}/{path}?sig=x",
            expires_at="2026-11-10T08:25:00Z",
            content_type=content_type,
            bytes=size,
        )


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


@pytest.fixture
def store() -> InMemoryBlobStore:
    return InMemoryBlobStore()


@pytest.fixture
def svc(store: InMemoryBlobStore) -> PostService:
    return PostService(store, clock=Clock())


@pytest.fixture
def linker() -> FakeLinker:
    return FakeLinker()


@pytest.fixture
def client(store: InMemoryBlobStore, linker: FakeLinker) -> TestClient:
    return TestClient(create_app(PublishedReader(store), linker), headers=READER)


def publish(
    svc: PostService, slug: str, body: str = "Hello", tags: list[str] | None = None
) -> str:
    d = svc.create(slug.title())
    d = svc.update_meta(
        d.post_id,
        MetaPatch(slug=slug, summary="Sum", tags=tags or []),
        if_match=d.meta_etag,
    )
    d = svc.update_body(d.post_id, body, if_match=d.body_etag)
    svc.publish(d.post_id, if_match=d.body_etag)
    return d.post_id


def add_media(store: InMemoryBlobStore, media_id: str = "m1") -> None:
    store.write(layout.DRAFTS, layout.media_original(media_id, "png"), b"PNG")
    store.write(
        layout.DRAFTS,
        layout.media_meta(media_id),
        MediaMeta(kind="image", mime="image/png", ext="png", bytes=3, alt="alt").dump(),
    )


ROUTES = ["/v1/posts", "/v1/posts/x", "/v1/media/m?post=x", "/v1/posts/x/audio"]


@pytest.mark.parametrize("path", ROUTES)
def test_no_principal_is_401_and_the_wrong_role_is_403_with_problem_json(
    store: InMemoryBlobStore, path: str
) -> None:
    c = TestClient(create_app(PublishedReader(store), FakeLinker()))
    none = c.get(path)
    assert none.status_code == 401
    assert none.headers["content-type"].startswith("application/problem+json")
    other = c.get(path, headers=principal("Other"))
    assert other.status_code == 403


def test_healthz_needs_no_principal(store: InMemoryBlobStore) -> None:
    c = TestClient(create_app(PublishedReader(store), FakeLinker()))
    assert c.get("/healthz").json() == {"status": "ok"}


def test_the_openapi_document_answers_without_the_role_and_lists_the_media_template(
    store: InMemoryBlobStore,
) -> None:
    # Decision (b): the schema is covered by the platform token validation only;
    # the code's role check guards the /v1 data routes.
    c = TestClient(create_app(PublishedReader(store), FakeLinker()))
    response = c.get("/v1/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/v1/media/{mediaId}" in paths and "/v1/posts/{slug}/audio" in paths
    assert c.get("/v1/posts").status_code == 401  # the data routes still need it


def test_the_list_pages_newest_first_with_cache_headers(
    client: TestClient, svc: PostService
) -> None:
    for slug in ("one", "two", "three"):
        publish(svc, slug)
    first = client.get("/v1/posts?limit=2")
    body = first.json()
    assert first.status_code == 200
    assert [i["slug"] for i in body["items"]] == ["three", "two"] and body["nextCursor"]
    assert first.headers["cache-control"] == "private, max-age=60"
    assert first.headers["etag"].startswith('"')
    second = client.get(f"/v1/posts?limit=2&cursor={body['nextCursor']}").json()
    assert [i["slug"] for i in second["items"]] == ["one"]
    assert second["nextCursor"] is None
    assert set(body["items"][0]) == {
        "postId",
        "slug",
        "title",
        "summary",
        "tags",
        "publishedAt",
        "updatedAt",
        "readingTimeMinutes",
        "coverMediaId",
        "hasAudio",
    }


def test_if_none_match_returns_304_and_a_change_changes_the_etag(
    client: TestClient, svc: PostService
) -> None:
    publish(svc, "one")
    first = client.get("/v1/posts")
    etag = first.headers["etag"]
    again = client.get("/v1/posts", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    assert again.headers["etag"] == etag
    assert (
        client.get("/v1/posts", headers={"If-None-Match": '"other"'}).status_code == 200
    )
    publish(svc, "two")
    assert client.get("/v1/posts").headers["etag"] != etag


def test_a_weakened_etag_from_a_proxy_still_matches(
    client: TestClient, svc: PostService
) -> None:
    publish(svc, "one")
    etag = client.get("/v1/posts").headers["etag"]
    for value in (f"W/{etag}", f'"other", W/{etag}', "W/*"):
        assert (
            client.get("/v1/posts", headers={"If-None-Match": value}).status_code == 304
        ), value


def test_a_media_path_that_climbs_out_of_its_folder_is_never_signed(
    client: TestClient,
    svc: PostService,
    store: InMemoryBlobStore,
    linker: FakeLinker,
) -> None:
    add_media(store)
    pid = publish(svc, "with-media", body="![a](media:m1)")
    path = layout.version_meta(pid, 1)
    blob = store.read(layout.PUBLISHED, path)
    assert blob is not None
    meta = json.loads(blob.content)
    meta["media"][0]["blobPath"] = f"posts/{pid}/v1/media/../../v2/media/x.png"
    store.write(layout.PUBLISHED, path, json.dumps(meta).encode())
    assert client.get("/v1/media/m1?post=with-media").status_code == 404
    assert linker.calls == []


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=51",
        "limit=x",
        "cursor=!!!",
        f"tag={'x' * 51}",
        f"cursor={'a' * 201}",
    ],
)
def test_a_bad_limit_or_cursor_is_a_400_problem(client: TestClient, query: str) -> None:
    response = client.get(f"/v1/posts?{query}")
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/problem+json")


def test_the_detail_has_the_body_media_without_paths_and_a_null_audio(
    client: TestClient, svc: PostService, store: InMemoryBlobStore
) -> None:
    add_media(store)
    publish(svc, "with-media", body="Text\n\n![a](media:m1)\n")
    response = client.get("/v1/posts/with-media")
    body = response.json()
    assert response.status_code == 200
    assert body["body"].startswith("Text") and body["version"] == 1
    assert body["audio"] is None and body["hasAudio"] is False
    assert body["media"] == [
        {
            "id": "m1",
            "kind": "image",
            "mime": "image/png",
            "bytes": 3,
            "width": None,
            "height": None,
            "durationSec": None,
            "alt": "alt",
        }
    ]
    text = response.text
    assert "blobPath" not in text and "blog-published" not in text
    again = client.get(
        "/v1/posts/with-media", headers={"If-None-Match": response.headers["etag"]}
    )
    assert again.status_code == 304


def test_drafts_and_unpublished_posts_never_appear(
    client: TestClient, svc: PostService
) -> None:
    svc.create("Only a draft")
    pid = publish(svc, "was-live")
    svc.unpublish(pid)
    assert client.get("/v1/posts").json()["items"] == []
    assert client.get("/v1/posts/was-live").status_code == 404
    assert client.get("/v1/posts/only-a-draft").status_code == 404


@pytest.mark.parametrize("slug", ["..%2Fx", "a%2Fb", "x" * 200, "UPPER"])
def test_a_hostile_slug_is_a_404_problem(client: TestClient, slug: str) -> None:
    response = client.get(f"/v1/posts/{slug}")
    assert response.status_code == 404


def test_media_returns_a_link_for_the_posts_own_media_only(
    client: TestClient,
    svc: PostService,
    store: InMemoryBlobStore,
    linker: FakeLinker,
) -> None:
    add_media(store)
    pid = publish(svc, "with-media", body="![a](media:m1)")
    publish(svc, "without")
    ok = client.get("/v1/media/m1?post=with-media")
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"
    assert set(ok.json()) == {"url", "expiresAt", "contentType", "bytes"}
    assert linker.calls == [(layout.PUBLISHED, f"posts/{pid}/v1/media/m1.png")]
    assert client.get("/v1/media/m1?post=without").status_code == 404
    assert client.get("/v1/media/nope?post=with-media").status_code == 404
    assert client.get("/v1/media/m1").status_code == 400  # `post` is required
    assert len(linker.calls) == 1


def test_a_tampered_blob_path_is_never_signed(
    client: TestClient,
    svc: PostService,
    store: InMemoryBlobStore,
    linker: FakeLinker,
) -> None:
    add_media(store)
    pid = publish(svc, "with-media", body="![a](media:m1)")
    path = layout.version_meta(pid, 1)
    blob = store.read(layout.PUBLISHED, path)
    assert blob is not None
    meta = json.loads(blob.content)
    meta["media"][0]["blobPath"] = "posts/OTHER/v1/media/m9.png"
    store.write(layout.PUBLISHED, path, json.dumps(meta).encode())
    assert client.get("/v1/media/m1?post=with-media").status_code == 404
    assert linker.calls == []


def test_audio_is_a_404_in_v1(client: TestClient, svc: PostService) -> None:
    publish(svc, "one")
    response = client.get("/v1/posts/one/audio")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_unexpected_error_is_a_fixed_500_problem(store: InMemoryBlobStore) -> None:
    class Broken(PublishedReader):
        def page(self, limit, cursor, tag):
            raise RuntimeError("https://acct.blob.core.windows.net/blog-published/x")

    c = TestClient(
        create_app(Broken(store), FakeLinker()),
        headers=READER,
        raise_server_exceptions=False,
    )
    response = c.get("/v1/posts")
    assert response.status_code == 500
    assert "blob.core" not in response.text
    assert set(response.json()) == {"type", "title", "status"}


def test_the_app_imports_without_an_environment_and_an_unconfigured_one_is_a_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BLOG_STORAGE_ACCOUNT_URL", raising=False)
    c = TestClient(create_app(), headers=READER)
    assert c.get("/healthz").status_code == 200
    assert c.get("/v1/posts").status_code == 503
    assert c.get("/openapi.json").status_code == 404
    assert c.get("/docs").status_code == 404
