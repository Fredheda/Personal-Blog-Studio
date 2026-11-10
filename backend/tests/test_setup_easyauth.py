import subprocess
from pathlib import Path

from conftest import FakeAz

SCRIPT = "scripts/setup-easyauth.sh"
CUSTOM = "https://blog-studio.frederikheda.com/.auth/login/aad/callback"
DEFAULT = "https://app.example.test/.auth/login/aad/callback"


def run(
    fake_az: FakeAz, tmp_path: Path, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return fake_az.run(
        SCRIPT, *args, env={"BLOG_ENV_FILE": str(tmp_path / ".env"), **env}
    )


def env_text(tmp_path: Path) -> str:
    path = tmp_path / ".env"
    return path.read_text() if path.exists() else ""


def entra_writes(fake_az: FakeAz) -> list[str]:
    prefixes = (
        "ad app create",
        "ad app update",
        "ad app credential reset",
        "ad sp create",
        "rest --method",
    )
    return [c for c in fake_az.calls if c.startswith(prefixes)]


def test_a_dry_run_writes_nothing(fake_az: FakeAz, tmp_path: Path) -> None:
    result = run(fake_az, tmp_path)
    assert result.returncode == 0, result.stderr
    assert entra_writes(fake_az) == []
    assert env_text(tmp_path) == ""
    assert "blogstudio-easyauth" in result.stdout


def test_an_unknown_flag_is_refused(fake_az: FakeAz, tmp_path: Path) -> None:
    result = run(fake_az, tmp_path, "--yes")
    assert result.returncode == 2
    assert entra_writes(fake_az) == []


def test_apply_registers_both_redirects_once_the_web_app_exists(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--apply")
    assert result.returncode == 0, result.stderr
    update = [c for c in fake_az.calls if "--web-redirect-uris" in c]
    assert len(update) == 1
    assert CUSTOM in update[0] and DEFAULT in update[0]
    assert "--enable-id-token-issuance true" in update[0]


def test_apply_says_which_redirect_uris_it_set(fake_az: FakeAz, tmp_path: Path) -> None:
    # The update itself is silent (--output none), so the script reports it.
    both = run(fake_az, tmp_path, "--apply")
    assert both.returncode == 0, both.stderr
    line = next(
        x for x in both.stdout.splitlines() if x.startswith("Redirect URIs set:")
    )
    assert CUSTOM in line and DEFAULT in line
    only = run(fake_az, tmp_path, "--apply", FAKE_NO_WEB_APP="1")
    line = next(
        x for x in only.stdout.splitlines() if x.startswith("Redirect URIs set:")
    )
    assert CUSTOM in line and DEFAULT not in line


def test_a_dry_run_does_not_claim_to_have_set_redirect_uris(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path)
    assert "Redirect URIs set:" not in result.stdout


def test_before_the_first_deploy_only_the_custom_domain_is_registered(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--apply", FAKE_NO_WEB_APP="1")
    assert result.returncode == 0, result.stderr
    update = [c for c in fake_az.calls if "--web-redirect-uris" in c][0]
    assert CUSTOM in update and DEFAULT not in update
    assert "Re-run" in result.stdout


def test_assignment_is_required_and_the_owner_is_assigned(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    run(fake_az, tmp_path, "--apply")
    assert any(
        "rest --method PATCH" in c
        and "servicePrincipals/sp-appid-blogstudio-easyauth" in c
        and '"appRoleAssignmentRequired": true' in c
        for c in fake_az.calls
    )
    posts = [c for c in fake_az.calls if c.startswith("rest --method POST")]
    assert len(posts) == 1
    assert '"principalId": "owner-oid"' in posts[0]
    assert '"appRoleId": "00000000-0000-0000-0000-000000000000"' in posts[0]


def test_the_client_secret_goes_to_a_private_env_file_and_nowhere_else(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--apply")
    assert "BLOG_WEB_CLIENT_SECRET=secret-1" in env_text(tmp_path)
    assert "BLOG_WEB_CLIENT_ID=appid-blogstudio-easyauth" in env_text(tmp_path)
    assert oct((tmp_path / ".env").stat().st_mode & 0o777) == "0o600"
    assert "secret-1" not in result.stdout + result.stderr
    # The secret is created with an expiry of two years and appended, so a
    # running deployment keeps working during a rotation.
    reset = [c for c in fake_az.calls if c.startswith("ad app credential reset")][0]
    assert "--years 2" in reset and "--append" in reset


def test_a_second_run_changes_nothing_and_keeps_the_secret(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    run(fake_az, tmp_path, "--apply")
    run(fake_az, tmp_path, "--apply", FAKE_ASSIGNED_COUNT="1")
    resets = [c for c in fake_az.calls if c.startswith("ad app credential reset")]
    assert len(resets) == 1
    assert len([c for c in fake_az.calls if c.startswith("ad app create")]) == 1
    assert len([c for c in fake_az.calls if c.startswith("rest --method POST")]) == 1
    assert "BLOG_WEB_CLIENT_SECRET=secret-1" in env_text(tmp_path)
    # Properties are re-applied every run.
    assert len([c for c in fake_az.calls if "--web-redirect-uris" in c]) == 2


def test_rotate_replaces_the_secret(fake_az: FakeAz, tmp_path: Path) -> None:
    run(fake_az, tmp_path, "--apply")
    run(fake_az, tmp_path, "--apply", "--rotate", FAKE_ASSIGNED_COUNT="1")
    assert "BLOG_WEB_CLIENT_SECRET=secret-2" in env_text(tmp_path)
    assert "secret-1" not in env_text(tmp_path)
