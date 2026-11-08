import json
from pathlib import Path

from conftest import FakeAz

SCRIPT = "infra/deploy.sh"
SHA = "b" * 40
REQUIRED = {
    "BLOG_TENANT_ID": "tenant-1",
    "BLOG_WEB_CLIENT_ID": "web-1",
    "BLOG_STUDIO_API_CLIENT_ID": "sapi-1",
    "BLOG_API_CLIENT_ID": "api-1",
    "BLOG_APPROVED_CLIENT_IDS": "caller-1,caller-2",
    "BLOG_WEB_CLIENT_SECRET": "s3cret-value",
}


def env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    """Settings for one run; a value of UNSET leaves the variable out.

    BLOG_ENV_FILE points at an empty file so a developer's real .env never
    leaks into a test.
    """
    nothing = tmp_path / "empty.env"
    nothing.write_text("")
    values = {**REQUIRED, **overrides}
    return {
        "BLOG_ENV_FILE": str(nothing),
        **{k: v for k, v in values.items() if v != "UNSET"},
    }


def deployments(fake_az: FakeAz) -> list[str]:
    return [c for c in fake_az.calls if c.startswith("deployment group create")]


def test_a_non_sha_is_rejected_before_any_az_call(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(SCRIPT, "main", env=env(tmp_path))
    assert result.returncode == 2
    assert fake_az.calls == []


def test_no_default_tag(fake_az: FakeAz, tmp_path: Path) -> None:
    result = fake_az.run(SCRIPT, env=env(tmp_path))
    assert result.returncode == 2
    assert fake_az.calls == []


def test_a_missing_setting_is_named_and_stops_before_azure(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(SCRIPT, SHA, env=env(tmp_path, BLOG_API_CLIENT_ID="UNSET"))
    assert result.returncode == 2
    assert "BLOG_API_CLIENT_ID" in result.stderr
    assert fake_az.calls == []


def test_an_empty_approved_caller_list_is_refused(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    for value in (",", " ,"):
        result = fake_az.run(
            SCRIPT, SHA, env=env(tmp_path, BLOG_APPROVED_CLIENT_IDS=value)
        )
        assert result.returncode == 2, value
        assert "BLOG_APPROVED_CLIENT_IDS" in result.stderr
    assert deployments(fake_az) == []


def test_a_sha_without_built_images_stops_before_the_deployment(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(
        SCRIPT, SHA, env={**env(tmp_path), "FAKE_MISSING": f"blogapi:{SHA}"}
    )
    assert result.returncode == 1
    assert "blogapi" in result.stderr and "build-push.sh" in result.stderr
    assert deployments(fake_az) == []


def test_a_good_run_deploys_once_with_the_sha_and_the_caller_list(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(SCRIPT, SHA, env=env(tmp_path))
    assert result.returncode == 0, result.stderr
    calls = deployments(fake_az)
    assert len(calls) == 1
    call = calls[0]
    assert "--resource-group rg-chatbot" in call
    assert "--template-file infra/main.bicep" in call
    params = json.loads(fake_az.side_file("params"))["parameters"]
    assert params["imageTag"]["value"] == SHA
    assert params["approvedClientIds"]["value"] == ["caller-1", "caller-2"]
    assert params["webClientId"]["value"] == "web-1"
    assert params["tenantId"]["value"] == "tenant-1"
    assert params["studioApiClientId"]["value"] == "sapi-1"
    assert params["blogApiClientId"]["value"] == "api-1"


def test_the_secret_travels_in_a_private_temporary_file_only(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(SCRIPT, SHA, env=env(tmp_path))
    assert result.returncode == 0, result.stderr
    # Never on the az command line, never in the script output.
    assert "s3cret-value" not in "\n".join(fake_az.calls)
    assert "s3cret-value" not in result.stdout + result.stderr
    # It is in the parameters file, which is owner-only and gone after the run.
    params = json.loads(fake_az.side_file("params"))["parameters"]
    assert params["webClientSecret"]["value"] == "s3cret-value"
    assert fake_az.side_file("mode") == "-rw-------"
    assert not Path(fake_az.side_file("paramfile")).exists()
