import subprocess
from pathlib import Path

from conftest import FakeAz

SCRIPT = "scripts/live-gate.sh"


def env_file(tmp_path: Path) -> Path:
    path = tmp_path / ".env"
    path.write_text(
        "BLOG_TENANT_ID=tenant-1\n"
        "BLOG_API_CLIENT_ID=appid-blogapi\n"
        "BLOG_GATE_CALLER_CLIENT_ID=appid-blogapi-gate-caller\n"
        "BLOG_GATE_DENIED_CLIENT_ID=appid-blogapi-gate-denied\n"
    )
    return path


def run(
    fake_az: FakeAz, tmp_path: Path, *args: str, **env: str
) -> subprocess.CompletedProcess[str]:
    return fake_az.run(
        SCRIPT,
        *args,
        env={
            "BLOG_ENV_FILE": str(env_file(tmp_path)),
            "GATE_RETRY_SLEEP": "0",
            **env,
        },
    )


def resets(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("ad app credential reset")]


def deletes(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("ad app credential delete")]


def test_without_the_run_flag_nothing_happens(fake_az: FakeAz, tmp_path: Path) -> None:
    result = run(fake_az, tmp_path)
    assert result.returncode == 0, result.stderr
    assert fake_az.calls == [] and fake_az.curl_calls == []
    assert "--run" in result.stdout


def test_all_three_steps_pass(fake_az: FakeAz, tmp_path: Path) -> None:
    result = run(fake_az, tmp_path, "--run")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.count("PASS") == 3 and "FAIL" not in result.stdout


def test_step_1_fails_when_an_unauthenticated_request_gets_through(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--run", FAKE_UNAUTH_CODE="200")
    assert result.returncode == 1
    assert "FAIL  1" in result.stdout


def test_step_2_passes_when_the_denied_caller_is_refused_a_token(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--run", FAKE_DENIED_TOKEN="refused")
    assert result.returncode == 0, result.stdout
    assert "PASS  2" in result.stdout


def test_step_2_passes_when_the_denied_caller_gets_a_token_but_a_403(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--run", FAKE_DENIED_CODE="403")
    assert result.returncode == 0, result.stdout
    assert "PASS  2" in result.stdout


def test_step_2_fails_when_the_denied_caller_reaches_the_app(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--run", FAKE_DENIED_CODE="200")
    assert result.returncode == 1
    assert "FAIL  2" in result.stdout


def test_step_2_does_not_pass_on_a_failure_that_is_not_a_refusal(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    # No token and no assignment-required refusal: could be anything, so not a pass.
    result = run(fake_az, tmp_path, "--run", FAKE_DENIED_TOKEN="none")
    assert result.returncode == 1
    assert "FAIL  2" in result.stdout


def test_step_3_passes_on_a_2xx_or_the_apps_own_404(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    for code in ("404", "200"):
        result = run(fake_az, tmp_path, "--run", FAKE_APPROVED_CODE=code)
        assert result.returncode == 0, (code, result.stdout)
        assert "PASS  3" in result.stdout


def test_step_3_fails_when_the_approved_caller_is_rejected_or_the_answer_is_odd(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    for code in ("401", "403", "500", "000"):
        result = run(fake_az, tmp_path, "--run", FAKE_APPROVED_CODE=code)
        assert result.returncode == 1, code
        assert "FAIL  3" in result.stdout


def test_step_3_fails_on_an_ingress_404_for_a_stopped_app(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    # Container Apps answers 404 with its own body when the app is stopped or
    # missing; that must not count as "reached the app".
    result = run(
        fake_az,
        tmp_path,
        "--run",
        FAKE_APPROVED_CODE="404",
        FAKE_APPROVED_BODY="Container App is stopped or does not exist",
    )
    assert result.returncode == 1
    assert "FAIL  3" in result.stdout
    assert "did not come" in result.stdout


def test_a_secret_that_has_not_propagated_yet_is_retried(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--run", FAKE_APPROVED_TOKEN="notready")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS  3" in result.stdout


def test_every_temporary_credential_is_removed(fake_az: FakeAz, tmp_path: Path) -> None:
    run(fake_az, tmp_path, "--run")
    assert len(resets(fake_az)) == 2
    assert len(deletes(fake_az)) == 2
    assert all("--key-id key-" in c for c in deletes(fake_az))


def test_credentials_are_removed_even_when_a_step_fails(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(
        fake_az, tmp_path, "--run", FAKE_APPROVED_TOKEN="none", GATE_TOKEN_TRIES="1"
    )
    assert result.returncode == 1
    assert len(deletes(fake_az)) == len(resets(fake_az)) == 2


def test_a_stale_credential_from_an_interrupted_run_is_cleared_first(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    stale = "appid-blogapi-gate-caller:stale-1"
    result = run(fake_az, tmp_path, "--run", FAKE_STALE_KEYS=stale)
    assert result.returncode == 0, result.stdout + result.stderr
    caller_calls = [c for c in fake_az.calls if "--id appid-blogapi-gate-caller" in c]
    stale_delete = next(
        i for i, c in enumerate(caller_calls) if "--key-id stale-1" in c
    )
    reset = next(
        i for i, c in enumerate(caller_calls) if c.startswith("ad app credential reset")
    )
    assert stale_delete < reset  # cleared before the new secret is created
    # Stale one plus this run's one for the caller, this run's one for the other app.
    assert len(deletes(fake_az)) == 3


def test_a_new_credential_is_removed_when_the_one_credential_check_fails(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    # A blog-gate credential that cannot be deleted makes the count two; the
    # script stops, but the credential it just created must still be removed.
    result = run(
        fake_az,
        tmp_path,
        "--run",
        FAKE_PERSISTENT_KEYS="appid-blogapi-gate-denied:ghost",
    )
    assert result.returncode == 1
    assert "expected exactly one" in result.stderr
    assert any("--key-id key-1" in c for c in deletes(fake_az))


def test_the_credentials_are_short_lived(fake_az: FakeAz, tmp_path: Path) -> None:
    run(fake_az, tmp_path, "--run")
    for call in resets(fake_az):
        assert "--end-date" in call and "--append" in call


def test_no_secret_reaches_a_command_line_or_the_output(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = run(fake_az, tmp_path, "--run")
    everything = "\n".join(fake_az.calls + fake_az.curl_calls + fake_az.jq_calls)
    assert "secret-" not in everything
    assert "secret-" not in result.stdout + result.stderr
    assert "tok-" not in everything
