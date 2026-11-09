import subprocess
from pathlib import Path

from conftest import FakeAz


def lib(
    fake_az: FakeAz, tmp_path: Path, snippet: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return fake_az.run_shell(
        f"source scripts/lib/entra.sh; {snippet}",
        env={"BLOG_ENV_FILE": str(tmp_path / ".env"), **env},
    )


def test_set_env_creates_a_private_file_and_replaces_a_key(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = lib(fake_az, tmp_path, "set_env A 1; set_env B 2; set_env A 3")
    assert result.returncode == 0, result.stderr
    env_file = tmp_path / ".env"
    assert env_file.read_text().splitlines() == ["B=2", "A=3"]
    assert oct(env_file.stat().st_mode & 0o777) == "0o600"


def test_get_env_returns_empty_for_a_missing_key(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = lib(
        fake_az, tmp_path, 'set_env A 1; echo "[$(get_env A)][$(get_env NOPE)]"'
    )
    assert result.stdout.strip() == "[1][]"


def test_ensure_app_creates_once_and_reuses(fake_az: FakeAz, tmp_path: Path) -> None:
    result = lib(fake_az, tmp_path, "ensure_app demo; ensure_app demo")
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["appid-demo", "appid-demo"]
    creates = [c for c in fake_az.calls if c.startswith("ad app create")]
    assert len(creates) == 1


def test_ensure_app_stops_when_the_name_is_ambiguous(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = lib(fake_az, tmp_path, "ensure_app demo", FAKE_DUP_APPS="demo")
    assert result.returncode != 0
    assert "2 app registrations" in result.stderr
    assert not [c for c in fake_az.calls if c.startswith("ad app create")]


def test_a_name_that_prefixes_other_apps_is_looked_up_exactly(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    # `--display-name blogapi` also matches blogapi-gate-caller and
    # blogapi-gate-denied; the lookup must still find exactly `blogapi`.
    result = lib(
        fake_az,
        tmp_path,
        "ensure_app blogapi-gate-caller; ensure_app blogapi-gate-denied; "
        "ensure_app blogapi; ensure_app blogapi",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == [
        "appid-blogapi-gate-caller",
        "appid-blogapi-gate-denied",
        "appid-blogapi",
        "appid-blogapi",
    ]
    creates = [c for c in fake_az.calls if c.startswith("ad app create")]
    assert len(creates) == 3


def test_a_name_that_only_prefixes_other_apps_is_not_found(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    # With only blogapi-gate-caller present, `blogapi` does not exist: the
    # lookup must not hand back the other app's client ID.
    result = lib(
        fake_az,
        tmp_path,
        'ensure_app blogapi-gate-caller >/dev/null; echo "[$(app_id blogapi)]"',
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_approve_client_assigns_the_role_once(fake_az: FakeAz, tmp_path: Path) -> None:
    prepare = "ensure_app blogapi >/dev/null; "
    first = lib(fake_az, tmp_path, prepare + "approve_client caller-sp")
    assert first.returncode == 0, first.stderr
    posts = [c for c in fake_az.calls if c.startswith("rest --method POST")]
    assert len(posts) == 1
    assert '"principalId": "caller-sp"' in posts[0]
    assert '"appRoleId": "5d8f2b6e-3a41-4c7e-9f0b-8a1e6c2d4b73"' in posts[0]
    # Already assigned: no second POST.
    again = lib(fake_az, tmp_path, "approve_client caller-sp", FAKE_ASSIGNED_COUNT="1")
    assert "Already approved" in again.stdout
    assert len([c for c in fake_az.calls if c.startswith("rest --method POST")]) == 1


def test_add_approved_client_appends_without_duplicates(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = lib(
        fake_az,
        tmp_path,
        "add_approved_client a; add_approved_client b; add_approved_client a; "
        'echo "$(get_env BLOG_APPROVED_CLIENT_IDS)"',
    )
    assert result.stdout.strip() == "a,b"
