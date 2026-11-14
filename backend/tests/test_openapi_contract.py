import json
import re
from typing import Any

from conftest import REPO_ROOT

from blog_api.app import create_app
from blog_api.reader import PublishedReader
from tests.fake_blob_store import InMemoryBlobStore

COMMITTED = json.loads((REPO_ROOT / "openapi" / "v1.json").read_text())
GENERATED = create_app(PublishedReader(InMemoryBlobStore()), object()).openapi()  # type: ignore[arg-type]
CHANGELOG = (REPO_ROOT / "docs" / "api-changelog.md").read_text()
SCHEMAS = [
    "Problem",
    "PostSummary",
    "PostList",
    "PostDetail",
    "MediaDescriptor",
    "MediaLink",
    "AudioLink",
]


def operations(doc: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (path, method): op
        for path, item in doc["paths"].items()
        for method, op in item.items()
    }


def properties(doc: dict[str, Any], name: str) -> tuple[set[str], set[str]]:
    """Property names and required names, following allOf and $ref."""
    schema = doc["components"]["schemas"][name]
    props: set[str] = set()
    required: set[str] = set()
    for part in schema.get("allOf", [schema]):
        if "$ref" in part:
            sub_props, sub_required = properties(doc, part["$ref"].rsplit("/", 1)[1])
            props |= sub_props
            required |= sub_required
        else:
            props |= set(part.get("properties", {}))
            required |= set(part.get("required", []))
    return props, required


def parameter_names(op: dict[str, Any]) -> set[str]:
    return {p["name"] for p in op.get("parameters", [])}


def test_the_same_paths_methods_parameters_and_status_codes() -> None:
    committed, generated = operations(COMMITTED), operations(GENERATED)
    live = {k: v for k, v in generated.items() if k[0] != "/healthz"}
    assert {k for k in committed if k[0] != "/healthz"} == set(live)
    for key, op in live.items():
        assert parameter_names(op) == parameter_names(committed[key]), key
        codes = set(op["responses"]) - {"422"}
        assert codes == set(committed[key]["responses"]), key


def test_the_same_schema_properties_and_required_fields() -> None:
    for name in SCHEMAS:
        committed_props, committed_required = properties(COMMITTED, name)
        generated_props, generated_required = properties(GENERATED, name)
        assert committed_props == generated_props, name
        assert committed_required <= generated_required, name


def test_the_version_in_the_contract_matches_the_code_and_the_changelog() -> None:
    assert COMMITTED["info"]["version"] == GENERATED["info"]["version"]
    headings = re.findall(r"^## (\S+)", CHANGELOG, re.MULTILINE)
    assert headings and headings[0] == COMMITTED["info"]["version"]
