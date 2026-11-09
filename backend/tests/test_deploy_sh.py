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
    "BLOG_OWNER_OBJECT_ID": "owner-1",
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


def test_the_owner_object_id_is_required(fake_az: FakeAz, tmp_path: Path) -> None:
    result = fake_az.run(SCRIPT, SHA, env=env(tmp_path, BLOG_OWNER_OBJECT_ID="UNSET"))
    assert result.returncode == 2
    assert "BLOG_OWNER_OBJECT_ID" in result.stderr
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
    assert params["ownerObjectId"]["value"] == "owner-1"


def test_the_secret_travels_in_a_private_temporary_file_only(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(SCRIPT, SHA, env=env(tmp_path))
    assert result.returncode == 0, result.stderr
    # Never on the az command line, never in jq's arguments (another process
    # could read either from the process list), never in the script output.
    assert "s3cret-value" not in "\n".join(fake_az.calls)
    assert fake_az.jq_calls, "the parameters file is built with jq"
    assert "s3cret-value" not in "\n".join(fake_az.jq_calls)
    assert "s3cret-value" not in result.stdout + result.stderr
    # It is in the parameters file, which is owner-only and gone after the run.
    params = json.loads(fake_az.side_file("params"))["parameters"]
    assert params["webClientSecret"]["value"] == "s3cret-value"
    assert fake_az.side_file("mode") == "-rw-------"
    assert not Path(fake_az.side_file("paramfile")).exists()


DOMAIN = "blog-studio.frederikheda.com"
CERT = "mc-cae-blogstudio-blog-studio-1234"


def test_without_a_custom_domain_both_parameters_are_empty(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(SCRIPT, SHA, env=env(tmp_path))
    assert result.returncode == 0, result.stderr
    params = json.loads(fake_az.side_file("params"))["parameters"]
    assert params["webCustomDomain"]["value"] == ""
    assert params["webCertificateName"]["value"] == ""


def test_the_custom_domain_and_certificate_travel_as_parameters(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(
        SCRIPT,
        SHA,
        env={
            **env(
                tmp_path,
                BLOG_WEB_CUSTOM_DOMAIN=DOMAIN,
                BLOG_WEB_CERTIFICATE_NAME=CERT,
            ),
            "FAKE_CUSTOM_DOMAINS": DOMAIN,
        },
    )
    assert result.returncode == 0, result.stderr
    params = json.loads(fake_az.side_file("params"))["parameters"]
    assert params["webCustomDomain"]["value"] == DOMAIN
    assert params["webCertificateName"]["value"] == CERT


def test_half_a_domain_setting_is_refused_before_azure(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    for only in (
        {"BLOG_WEB_CUSTOM_DOMAIN": DOMAIN},
        {"BLOG_WEB_CERTIFICATE_NAME": CERT},
    ):
        result = fake_az.run(SCRIPT, SHA, env=env(tmp_path, **only))
        assert result.returncode == 2, only
        assert "together" in result.stderr
    assert fake_az.calls == []


def test_a_deploy_that_would_unbind_the_live_domain_is_refused(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    # ARM's PUT treats the ingress as authoritative: deploying without the
    # domain settings while one is bound would silently remove the binding.
    result = fake_az.run(
        SCRIPT, SHA, env={**env(tmp_path), "FAKE_CUSTOM_DOMAINS": DOMAIN}
    )
    assert result.returncode == 1
    assert DOMAIN in result.stderr and "bind-domain.sh" in result.stderr
    assert deployments(fake_az) == []


def test_the_guard_fails_closed_when_azure_cannot_be_read(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    # An auth or network error must not look like "nothing is bound".
    result = fake_az.run(SCRIPT, SHA, env={**env(tmp_path), "FAKE_LIST_FAILS": "1"})
    assert result.returncode != 0
    assert "AuthorizationFailed" in result.stderr
    assert deployments(fake_az) == []


def test_the_first_deploy_has_nothing_to_unbind(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(SCRIPT, SHA, env={**env(tmp_path), "FAKE_NO_WEB_APP": "1"})
    assert result.returncode == 0, result.stderr
    assert len(deployments(fake_az)) == 1


def test_a_deploy_that_would_replace_the_live_domain_is_refused(
    fake_az: FakeAz, tmp_path: Path
) -> None:
    result = fake_az.run(
        SCRIPT,
        SHA,
        env={
            **env(
                tmp_path,
                BLOG_WEB_CUSTOM_DOMAIN=DOMAIN,
                BLOG_WEB_CERTIFICATE_NAME=CERT,
            ),
            "FAKE_CUSTOM_DOMAINS": "other.example.test",
        },
    )
    assert result.returncode == 1
    assert "other.example.test" in result.stderr
    assert deployments(fake_az) == []
