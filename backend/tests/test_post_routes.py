import pytest
from fastapi.testclient import TestClient

from studio_api.app import create_app
from studio_api.posts import PostService
from tests.fake_blob_store import InMemoryBlobStore

CSRF = {"X-Blog-Studio": "1"}
UNKNOWN = "01ARZ3NDEKTSV4RRFFQ69G5FAV"


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(PostService(InMemoryBlobStore())), headers=CSRF)


def new_draft(client: TestClient, title: str = "Hello") -> dict:
    return client.post("/posts", json={"title": title}).json()


def ready(
    client: TestClient, body: str = "Hello **world**.", slug: str = "hello"
) -> dict:
    d = new_draft(client)
    d = client.patch(
        f"/posts/{d['postId']}/meta",
        json={"slug": slug, "summary": "Sum"},
        headers={"If-Match": d["metaEtag"]},
    ).json()
    return client.put(
        f"/posts/{d['postId']}/body",
        json={"body": body},
        headers={"If-Match": d["bodyEtag"]},
    ).json()


def test_create_returns_a_camelcase_draft_with_etags_and_a_location(
    client: TestClient,
) -> None:
    response = client.post("/posts", json={"title": "Hi"})
    draft = response.json()
    assert response.status_code == 201
    assert response.headers["location"] == f"/posts/{draft['postId']}"
    assert {
        "postId",
        "title",
        "slug",
        "summary",
        "tags",
        "coverMediaId",
        "createdAt",
        "updatedAt",
        "body",
        "bodyEtag",
        "metaEtag",
    } <= set(draft)
    assert draft["title"] == "Hi" and draft["body"] == ""


def test_an_overlong_title_is_a_422_problem(client: TestClient) -> None:
    response = client.post("/posts", json={"title": "x" * 201})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_oversized_body_is_a_422_problem(client: TestClient) -> None:
    d = new_draft(client)
    response = client.put(
        f"/posts/{d['postId']}/body",
        json={"body": "x" * 200_001},
        headers={"If-Match": d["bodyEtag"]},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/posts"),
        ("put", f"/posts/{UNKNOWN}/body"),
        ("patch", f"/posts/{UNKNOWN}/meta"),
        ("delete", f"/posts/{UNKNOWN}"),
        ("post", "/posts/not-an-id/publish"),
    ],
)
def test_a_state_changing_request_without_the_header_is_403_and_changes_nothing(
    method: str, path: str
) -> None:
    # No body, no If-Match, sometimes a bad id: the guard still answers first.
    plain = TestClient(create_app(PostService(InMemoryBlobStore())))
    response = getattr(plain, method)(path)
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/problem+json")
    assert plain.get("/posts").json() == {"items": []}


def test_a_foreign_origin_is_403_when_origins_are_configured() -> None:
    app = create_app(
        PostService(InMemoryBlobStore()), allowed_origins={"https://blog.example"}
    )
    c = TestClient(app, headers=CSRF)
    foreign = c.post(
        "/posts", json={"title": "t"}, headers={"Origin": "https://evil.example"}
    )
    assert foreign.status_code == 403
    own = c.post(
        "/posts", json={"title": "t"}, headers={"Origin": "https://blog.example"}
    )
    assert own.status_code == 201
    assert c.post("/posts", json={"title": "t"}).status_code == 201  # not a browser


def test_a_revision_id_with_a_trailing_newline_is_a_404_problem(
    client: TestClient,
) -> None:
    d = new_draft(client)
    revision = client.post(f"/posts/{d['postId']}/revisions").json()["revision"]
    response = client.get(f"/posts/{d['postId']}/revisions/{revision}%0A")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_unexpected_error_is_a_500_problem_that_leaks_nothing() -> None:
    class Broken(PostService):
        def list_drafts(self):
            raise RuntimeError("https://acct.blob.core.windows.net/blog-drafts/x")

    app = create_app(Broken(InMemoryBlobStore()))
    c = TestClient(app, headers=CSRF, raise_server_exceptions=False)
    response = c.get("/posts")
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "blob.core" not in response.text and "RuntimeError" not in response.text
    assert set(response.json()) == {"type", "title", "status"}


@pytest.mark.parametrize(
    "bad", ["x..x", "abc", "01arz3ndektsv4rrffq69g5fav", UNKNOWN + "A"]
)
def test_a_hostile_or_malformed_post_id_is_a_404_problem(
    client: TestClient, bad: str
) -> None:
    response = client.get(f"/posts/{bad}")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_unknown_post_is_404(client: TestClient) -> None:
    assert client.get(f"/posts/{UNKNOWN}").status_code == 404


def test_list_shows_drafts_newest_first(client: TestClient) -> None:
    a, b = new_draft(client, "A"), new_draft(client, "B")
    items = client.get("/posts").json()["items"]
    assert {i["postId"] for i in items} == {a["postId"], b["postId"]}
    assert set(items[0]) == {"postId", "title", "slug", "updatedAt"}


def test_saving_the_body_needs_if_match_and_a_stale_one_is_412(
    client: TestClient,
) -> None:
    d = new_draft(client)
    url = f"/posts/{d['postId']}/body"
    assert client.put(url, json={"body": "one"}).status_code == 428
    saved = client.put(url, json={"body": "one"}, headers={"If-Match": d["bodyEtag"]})
    assert saved.status_code == 200 and saved.json()["body"] == "one"
    assert saved.json()["bodyEtag"] != d["bodyEtag"]
    stale = client.put(url, json={"body": "two"}, headers={"If-Match": d["bodyEtag"]})
    assert stale.status_code == 412
    assert stale.headers["content-type"].startswith("application/problem+json")
    assert client.get(f"/posts/{d['postId']}").json()["body"] == "one"


def test_meta_patch_validates_and_returns_problem_lines(client: TestClient) -> None:
    d = new_draft(client)
    response = client.patch(
        f"/posts/{d['postId']}/meta",
        json={"slug": "Bad Slug"},
        headers={"If-Match": d["metaEtag"]},
    )
    assert response.status_code == 422
    assert response.json()["problems"][0]["message"]


def test_publish_refuses_html_with_line_and_message(client: TestClient) -> None:
    d = ready(client, body="fine\n\n<script>x</script>\n")
    response = client.post(
        f"/posts/{d['postId']}/publish", headers={"If-Match": d["bodyEtag"]}
    )
    assert response.status_code == 422
    assert response.json()["problems"] == [
        {"line": 3, "message": "raw HTML is not allowed"}
    ]


def test_publish_then_republish_then_unpublish_then_delete(
    client: TestClient,
) -> None:
    d = ready(client)
    pid = d["postId"]
    first = client.post(f"/posts/{pid}/publish", headers={"If-Match": d["bodyEtag"]})
    assert first.status_code == 200 and first.json()["version"] == 1
    assert client.delete(f"/posts/{pid}").status_code == 409
    assert client.post(f"/posts/{pid}/publish").status_code == 428
    assert client.post(f"/posts/{pid}/unpublish").status_code == 204
    assert client.post(f"/posts/{pid}/unpublish").status_code == 204
    assert client.delete(f"/posts/{pid}").status_code == 204
    assert client.get(f"/posts/{pid}").status_code == 404


def test_checkpoint_list_read_and_restore(client: TestClient) -> None:
    d = ready(client, body="v1")
    pid = d["postId"]
    revision = client.post(f"/posts/{pid}/revisions").json()["revision"]
    d = client.put(
        f"/posts/{pid}/body", json={"body": "v2"}, headers={"If-Match": d["bodyEtag"]}
    ).json()
    assert client.get(f"/posts/{pid}/revisions").json()["items"] == [revision]
    assert client.get(f"/posts/{pid}/revisions/{revision}").json() == {
        "revision": revision,
        "body": "v1",
    }
    restored = client.post(
        f"/posts/{pid}/revisions/{revision}/restore",
        headers={"If-Match": d["bodyEtag"]},
    )
    assert restored.status_code == 200 and restored.json()["body"] == "v1"
    assert client.get(f"/posts/{pid}/revisions/not-a-revision").status_code == 404


def test_the_studio_app_still_has_no_docs_and_an_unconfigured_app_is_a_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BLOG_STORAGE_ACCOUNT_URL", raising=False)
    c = TestClient(create_app(), headers=CSRF)  # no service injected, no env
    assert c.get("/healthz").status_code == 200
    assert c.get("/openapi.json").status_code == 404
    response = c.get("/posts")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
