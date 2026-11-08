"""Structural checks on infra/*.bicep: no Azure call, no Bicep compiler.

They pin the rules that fail quietly: an optional auth config, an empty allow
list, a write role for the read API, a secret that leaks to another app.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN = (REPO_ROOT / "infra" / "main.bicep").read_text()
STORAGE = (REPO_ROOT / "infra" / "storage.bicep").read_text()


def block(text: str, name: str) -> str:
    """The text of one top-level `resource <name> ...` block."""
    start = re.search(rf"^resource {name} ", text, re.MULTILINE)
    assert start, f"resource {name} not found"
    nxt = re.search(r"^(resource|module|output) ", text[start.end() :], re.MULTILINE)
    end = start.end() + nxt.start() if nxt else len(text)
    return text[start.start() : end]


APPS = ("web", "studioApi", "blogApi")
AUTHS = ("webAuth", "studioApiAuth", "blogApiAuth")


def test_every_app_scales_to_zero_and_stays_small() -> None:
    for app in APPS:
        text = block(MAIN, app)
        assert "minReplicas: 0" in text and "maxReplicas: 1" in text, app
        assert "cpu: json('0.25')" in text and "memory: '0.5Gi'" in text, app


def test_ingress_matches_the_design() -> None:
    assert "external: true" in block(MAIN, "web")
    assert "external: false" in block(MAIN, "studioApi")
    assert "external: true" in block(MAIN, "blogApi")
    assert "targetPort: 3000" in block(MAIN, "web")
    assert "targetPort: 8000" in block(MAIN, "studioApi")
    assert "targetPort: 8000" in block(MAIN, "blogApi")


def test_no_log_analytics_and_one_api_version() -> None:
    code = "\n".join(
        line for line in MAIN.splitlines() if not line.lstrip().startswith("//")
    )
    assert "appLogsConfiguration" not in code
    versions = set(re.findall(r"Microsoft\.App/\w+(?:/\w+)?@([\w-]+)", MAIN))
    assert versions == {"2025-01-01"}


def test_auth_is_never_optional_and_always_enabled() -> None:
    for auth in AUTHS:
        text = block(MAIN, auth)
        assert not re.search(r"=\s*if\s*\(", text.splitlines()[0]), auth
        assert re.search(r"platform:\s*\{\s*enabled: true\s*\}", text), auth
        assert "excludedPaths: [\n        '/healthz'\n      ]" in text, auth


def test_the_apis_return_401_and_the_web_app_redirects() -> None:
    assert "unauthenticatedClientAction: 'Return401'" in block(MAIN, "studioApiAuth")
    assert "unauthenticatedClientAction: 'Return401'" in block(MAIN, "blogApiAuth")
    assert "unauthenticatedClientAction: 'RedirectToLoginPage'" in block(
        MAIN, "webAuth"
    )


def test_the_allow_lists_are_set_and_the_read_api_list_cannot_be_empty() -> None:
    assert re.search(r"@minLength\(1\)\s*\nparam approvedClientIds array", MAIN)
    assert "allowedApplications: approvedClientIds" in block(MAIN, "blogApiAuth")
    studio = block(MAIN, "studioApiAuth")
    assert (
        "allowedApplications: [\n              webIdentity.properties.clientId\n            ]"
        in studio
    )


def test_the_audiences_are_the_api_app_ids() -> None:
    assert "'api://${studioApiClientId}'" in block(MAIN, "studioApiAuth")
    assert "'api://${blogApiClientId}'" in block(MAIN, "blogApiAuth")


def test_the_only_secure_parameter_is_the_easy_auth_client_secret() -> None:
    assert len(re.findall(r"@secure\(\)", MAIN)) == 1
    assert re.search(r"@secure\(\)\s*\nparam webClientSecret string", MAIN)
    assert "webClientSecret" not in block(MAIN, "studioApi")
    assert "webClientSecret" not in block(MAIN, "blogApi")


def test_no_credentials_anywhere() -> None:
    for text in (MAIN, STORAGE):
        assert not re.search(
            r"listKeys|AccountKey|connectionString|adminUserEnabled", text, re.I
        )


def test_images_come_from_the_shared_registry_by_sha_through_a_pull_identity() -> None:
    for app, repo in (
        ("web", "blogstudio-web"),
        ("studioApi", "blogstudio-api"),
        ("blogApi", "blogapi"),
    ):
        text = block(MAIN, app)
        assert f"image: '${{loginServer}}/{repo}:${{imageTag}}'" in text, app
        assert "identity: acrPullIdentity.id" in text, app
        # The AcrPull role assignment exists before the app tries to pull.
        assert re.search(r"dependsOn:\s*\[\s*acrPull\s*\]", text), app


def test_each_app_runs_with_its_own_runtime_identity() -> None:
    assert "webIdentity.properties.clientId" in block(MAIN, "web")
    assert "studioApiIdentity.properties.clientId" in block(MAIN, "studioApi")
    assert "blogApiIdentity.properties.clientId" in block(MAIN, "blogApi")
    for app in APPS:
        assert "AZURE_CLIENT_ID" in block(MAIN, app), app


# --- storage.bicep -------------------------------------------------------------

ROLE_ASSIGNMENTS = (
    "studioApiDrafts",
    "studioApiPublished",
    "blogApiPublished",
    "studioApiDelegator",
    "blogApiDelegator",
)


def test_exactly_five_role_assignments_exist() -> None:
    assert len(re.findall(r"Microsoft\.Authorization/roleAssignments@", STORAGE)) == 5
    for name in ROLE_ASSIGNMENTS:
        block(STORAGE, name)


def test_the_studio_api_can_write_both_containers() -> None:
    for name, container in (
        ("studioApiDrafts", "drafts"),
        ("studioApiPublished", "published"),
    ):
        text = block(STORAGE, name)
        assert "contributorRoleId" in text and f"scope: {container}" in text
        assert "studioApiPrincipalId" in text


def test_the_read_api_can_only_read_the_published_container() -> None:
    text = block(STORAGE, "blogApiPublished")
    assert "readerRoleId" in text and "scope: published" in text
    assert "contributorRoleId" not in text
    # The read API principal appears in exactly its two assignments.
    users = [n for n in ROLE_ASSIGNMENTS if "blogApiPrincipalId" in block(STORAGE, n)]
    assert sorted(users) == ["blogApiDelegator", "blogApiPublished"]
    assert "drafts" not in block(STORAGE, "blogApiDelegator")


def test_both_identities_get_the_delegator_role_at_account_scope() -> None:
    for name in ("studioApiDelegator", "blogApiDelegator"):
        text = block(STORAGE, name)
        assert "delegatorRoleId" in text and "scope: account" in text


def test_role_ids_are_the_verified_built_in_ids() -> None:
    assert "'ba92f5b4-2d11-453d-a403-e96b0029c9fe'" in STORAGE
    assert "'2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'" in STORAGE
    assert "'db58b8e5-c6ad-4a2a-8342-4190687cbf4a'" in STORAGE


def test_the_containers_are_private() -> None:
    for name in ("drafts", "published"):
        assert "publicAccess: 'None'" in block(STORAGE, name)
