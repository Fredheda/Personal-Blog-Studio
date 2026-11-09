import subprocess
from pathlib import Path

from conftest import FakeAz

SCRIPT = "scripts/setup-api-auth.sh"


def run(
    fake_az: FakeAz, tmp_path: Path, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return fake_az.run(
        SCRIPT, *args, env={"BLOG_ENV_FILE": str(tmp_path / ".env"), **env}
    )


def entra_writes(fake_az: FakeAz) -> list[str]:
    prefixes = ("ad app create", "ad app update", "ad sp create", "rest --method")
    return [c for c in fake_az.calls if c.startswith(prefixes)]


def env_values(tmp_path: Path) -> dict[str, str]:
    lines = (tmp_path / ".env").read_text().splitlines()
    return dict(line.split("=", 1) for line in lines)


def test_a_dry_run_reads_but_writes_nothing(fake_az: FakeAz, tmp_path: Path) -> None:
    result = run(fake_az, tmp_path)
    assert result.returncode == 0, result.stderr
    assert entra_writes(fake_az) == []
    assert not (tmp_path / ".env").exists()
    for name in (
        "blogstudio-api",
        "blogapi",
        "blogapi-gate-caller",
        "blogapi-gate-denied",
    ):
        assert name in result.stdout


def test_apply_creates_the_four_apps_and_their_service_principals(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--apply")
    assert result.returncode == 0, result.stderr
    created = [c for c in fake_az.calls if c.startswith("ad app create")]
    assert len(created) == 4
    assert len([c for c in fake_az.calls if c.startswith("ad sp create")]) == 4


def test_both_apis_get_their_audience_and_token_version(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    run(fake_az, tmp_path, "--apply")
    for name in ("blogstudio-api", "blogapi"):
        app = f"appid-{name}"
        assert any(
            c.startswith("ad app update")
            and f"--id {app}" in c
            and f"--identifier-uris api://{app}" in c
            for c in fake_az.calls
        ), name
        assert any(
            "rest --method PATCH" in c
            and f"applications/obj-{app}" in c
            and '"requestedAccessTokenVersion": 2' in c
            for c in fake_az.calls
        ), name


def test_the_read_api_has_the_role_and_requires_assignment(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    run(fake_az, tmp_path, "--apply")
    roles = [c for c in fake_az.calls if "--app-roles" in c]
    assert len(roles) == 1 and "--id appid-blogapi" in roles[0]
    assert '"value":"Blog.Read"' in roles[0]
    assert '"id":"5d8f2b6e-3a41-4c7e-9f0b-8a1e6c2d4b73"' in roles[0]
    assert '"allowedMemberTypes":["Application"]' in roles[0]
    assert any(
        "rest --method PATCH" in c
        and "servicePrincipals/sp-appid-blogapi" in c
        and '"appRoleAssignmentRequired": true' in c
        for c in fake_az.calls
    )


def test_only_the_gate_caller_is_approved(fake_az: FakeAz, tmp_path: Path) -> None:
    run(fake_az, tmp_path, "--apply")
    posts = [c for c in fake_az.calls if c.startswith("rest --method POST")]
    assert len(posts) == 1
    assert '"principalId": "sp-appid-blogapi-gate-caller"' in posts[0]


def test_the_ids_and_the_owner_land_in_the_env_file(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    run(fake_az, tmp_path, "--apply")
    values = env_values(tmp_path)
    assert values["BLOG_TENANT_ID"] == "tenant-1"
    assert values["BLOG_OWNER_OBJECT_ID"] == "owner-oid"
    assert values["BLOG_STUDIO_API_CLIENT_ID"] == "appid-blogstudio-api"
    assert values["BLOG_API_CLIENT_ID"] == "appid-blogapi"
    assert values["BLOG_GATE_CALLER_CLIENT_ID"] == "appid-blogapi-gate-caller"
    assert values["BLOG_GATE_DENIED_CLIENT_ID"] == "appid-blogapi-gate-denied"
    assert values["BLOG_APPROVED_CLIENT_IDS"] == "appid-blogapi-gate-caller"


def test_a_second_run_is_idempotent(fake_az: FakeAz, tmp_path: Path) -> None:
    run(fake_az, tmp_path, "--apply")
    first_env = (tmp_path / ".env").read_text()
    creating = ("ad app create", "ad sp create")
    creates_before = len([c for c in fake_az.calls if c.startswith(creating)])
    run(fake_az, tmp_path, "--apply", FAKE_ASSIGNED_COUNT="1")
    creates_after = len([c for c in fake_az.calls if c.startswith(creating)])
    assert creates_after == creates_before  # nothing created twice
    assert sorted((tmp_path / ".env").read_text().splitlines()) == sorted(
        first_env.splitlines()
    )
    # The properties are re-applied on every run, not only on create.
    updates = [c for c in fake_az.calls if "--identifier-uris" in c]
    assert len(updates) == 4  # two apps, twice
    # And the role is not assigned a second time.
    assert len([c for c in fake_az.calls if c.startswith("rest --method POST")]) == 1


def test_an_ambiguous_app_name_stops_before_any_write(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--apply", FAKE_DUP_APPS="blogapi")
    assert result.returncode != 0
    assert "blogapi" in result.stderr
    assert not [
        c for c in fake_az.calls if c.startswith("ad app create") and "blogapi " in c
    ]
