import json

import jsonschema
import pytest
from conftest import REPO_ROOT

DOC = json.loads((REPO_ROOT / "openapi" / "v1.json").read_text())
LIST_ITEM = {
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
DETAIL = LIST_ITEM | {"body", "version", "media", "audio"}
MEDIA_DESCRIPTOR = {
    "id",
    "kind",
    "mime",
    "bytes",
    "width",
    "height",
    "durationSec",
    "alt",
}
LINK = {"url", "expiresAt", "contentType", "bytes"}


def response(path: str, status: str) -> dict:
    """The response object, following a `$ref` into `components/responses`."""
    found = DOC["paths"][path]["get"]["responses"][status]
    if "$ref" in found:
        prefix = "#/components/responses/"
        assert found["$ref"].startswith(prefix), found["$ref"]
        found = DOC["components"]["responses"][found["$ref"][len(prefix) :]]
    return found


def example(path: str, status: str, name: str = "default") -> dict:
    media = next(iter(response(path, status)["content"].values()))
    return media["examples"][name]["value"]


def test_exactly_the_five_spec_endpoints_all_get_only() -> None:
    assert DOC["openapi"].startswith("3.1")
    assert set(DOC["paths"]) == {
        "/v1/posts",
        "/v1/posts/{slug}",
        "/v1/media/{mediaId}",
        "/v1/posts/{slug}/audio",
        "/healthz",
    }
    assert all(set(item) == {"get"} for item in DOC["paths"].values())


def test_the_list_example_has_the_spec_fields() -> None:
    body = example("/v1/posts", "200")
    assert set(body) == {"items", "nextCursor"}
    assert set(body["items"][0]) == LIST_ITEM


def test_the_detail_example_has_the_spec_fields_and_no_storage_path() -> None:
    body = example("/v1/posts/{slug}", "200")
    assert set(body) == DETAIL and body["audio"] is None
    assert all(set(m) <= MEDIA_DESCRIPTOR for m in body["media"])
    assert "blobPath" not in json.dumps(DOC)


def test_the_media_and_audio_examples_are_short_lived_https_links() -> None:
    link = example("/v1/media/{mediaId}", "200")
    assert set(link) == LINK and link["url"].startswith("https://")
    assert set(example("/v1/posts/{slug}/audio", "200")) == LINK | {"durationSec"}


def test_the_cached_responses_document_etag_and_cache_control() -> None:
    for path in ("/v1/posts", "/v1/posts/{slug}"):
        headers = response(path, "200")["headers"]
        assert {"ETag", "Cache-Control"} <= set(headers), path


def test_not_modified_unauthorized_and_not_found_are_documented() -> None:
    responses = DOC["paths"]["/v1/posts/{slug}"]["get"]["responses"]
    assert {"200", "304", "401", "404"} <= set(responses)
    for path, status in [("/v1/posts/{slug}", "401"), ("/v1/posts/{slug}", "404")]:
        problem = example(path, status)
        assert {"type", "title", "status"} <= set(problem)
        assert problem["status"] == int(status)
    assert "application/problem+json" in response("/v1/posts/{slug}", "404")["content"]


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/v1/posts", "200"),
        ("/v1/posts/{slug}", "200"),
        ("/v1/media/{mediaId}", "200"),
        ("/v1/posts/{slug}/audio", "200"),
        ("/v1/posts/{slug}", "401"),
        ("/v1/posts/{slug}", "404"),
    ],
)
def test_every_example_validates_against_its_schema(path: str, status: str) -> None:
    media = next(iter(response(path, status)["content"].values()))
    schema = {"$ref": media["schema"]["$ref"], "components": DOC["components"]}
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(example(path, status))
