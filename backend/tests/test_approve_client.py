import subprocess
from pathlib import Path

from conftest import FakeAz

SCRIPT = "scripts/approve-client.sh"
CLIENT = "11111111-2222-3333-4444-555555555555"


def run(
    fake_az: FakeAz, tmp_path: Path, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return fake_az.run(
        SCRIPT, *args, env={"BLOG_ENV_FILE": str(tmp_path / ".env"), **env}
    )


def prepare(fake_az: FakeAz, tmp_path: Path) -> None:
    fake_az.run_shell(
        "source scripts/lib/entra.sh; ensure_app blogapi >/dev/null",
        env={"BLOG_ENV_FILE": str(tmp_path / ".env")},
    )
    fake_az.log.write_text("")  # forget the preparation calls


def posts(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("rest --method POST")]


def test_anything_but_a_guid_is_refused(fake_az: FakeAz, tmp_path: Path) -> None:
    for bad in ("", "not-a-guid", "sp-123", CLIENT[:-1], "$(whoami)"):
        result = run(fake_az, tmp_path, *([bad] if bad else []), "--apply")
        assert result.returncode == 2, bad
    assert fake_az.calls == []


def test_a_dry_run_writes_nothing(fake_az: FakeAz, tmp_path: Path) -> None:
    prepare(fake_az, tmp_path)
    result = run(fake_az, tmp_path, CLIENT)
    assert result.returncode == 0, result.stderr
    assert posts(fake_az) == []
    assert not (tmp_path / ".env").exists()
    assert CLIENT in result.stdout


def test_apply_assigns_the_role_and_records_the_client(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    prepare(fake_az, tmp_path)
    result = run(fake_az, tmp_path, CLIENT, "--apply")
    assert result.returncode == 0, result.stderr
    assert len(posts(fake_az)) == 1
    assert f'"principalId": "sp-{CLIENT}"' in posts(fake_az)[0]
    assert f"BLOG_APPROVED_CLIENT_IDS={CLIENT}" in (tmp_path / ".env").read_text()
    assert "deploy.sh" in result.stdout


def test_approving_twice_assigns_once_and_lists_once(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    prepare(fake_az, tmp_path)
    run(fake_az, tmp_path, CLIENT, "--apply")
    again = run(fake_az, tmp_path, CLIENT, "--apply", FAKE_ASSIGNED_COUNT="1")
    assert again.returncode == 0, again.stderr
    assert len(posts(fake_az)) == 1
    assert (tmp_path / ".env").read_text().count(CLIENT) == 1


def test_it_stops_when_the_apis_were_never_set_up(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, CLIENT, "--apply")
    assert result.returncode != 0
    assert "setup-api-auth.sh" in result.stderr
    assert posts(fake_az) == []
