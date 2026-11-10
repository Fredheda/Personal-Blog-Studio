import json
import re

from conftest import FakeAz

SCRIPT = "scripts/setup-github-deploy.sh"
REPO = "Fredheda/Personal-Blog-Studio"
SUBJECT = f"repo:{REPO}:environment:production"
BUILD = "id-blogstudio-gh-build"
DEPLOY = "id-blogstudio-gh-deploy"
APPS = ("ca-blogstudio-web", "ca-blogstudio-api", "ca-blogapi")
ATTACHED = (
    "id-blogstudio-acrpull",
    "id-blogstudio-web",
    "id-blogstudio-api",
    "id-blogapi",
)
REGISTRY = (
    "/subscriptions/sub-1/resourceGroups/rg-chatbot/providers/"
    "Microsoft.ContainerRegistry/registries/acrchatbotfredheda"
)


def azure_writes(fake_az: FakeAz) -> list[str]:
    prefixes = (
        "identity create",
        "role assignment create",
        "identity federated-credential create",
    )
    return [c for c in fake_az.calls if c.startswith(prefixes)]


def github_writes(fake_az: FakeAz) -> list[str]:
    return [
        c
        for c in fake_az.gh_calls
        if "-X PUT" in c or "-X POST" in c or c.startswith("secret set")
    ]


def grants(fake_az: FakeAz, identity: str) -> list[tuple[str, str]]:
    """(role, scope) of every role assignment made to this identity."""
    out = []
    for call in fake_az.calls:
        m = re.match(
            r"role assignment create --assignee-object-id (\S+) .*?--role (.+?) --scope (\S+)",
            call,
        )
        if m and m.group(1) == f"principal-{identity}":
            out.append((m.group(2), m.group(3)))
    return out


def branch_policy_posts(fake_az: FakeAz) -> list[str]:
    return [
        c
        for c in fake_az.gh_calls
        if "-X POST" in c and "deployment-branch-policies" in c
    ]


def test_a_dry_run_changes_nothing_and_prints_the_plan(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT)
    assert result.returncode == 0, result.stderr
    assert azure_writes(fake_az) == [] and github_writes(fake_az) == []
    assert BUILD in result.stdout and DEPLOY in result.stdout
    assert "Dry run" in result.stdout


def test_an_unknown_flag_is_refused(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--yes")
    assert result.returncode == 2
    assert fake_az.calls == []


def test_apply_creates_both_identities_once(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--apply")
    assert result.returncode == 0, result.stderr
    created = [c for c in fake_az.calls if c.startswith("identity create")]
    assert len(created) == 2
    assert any(f"-n {BUILD} " in c for c in created)
    assert any(f"-n {DEPLOY} " in c for c in created)


def test_the_build_identity_can_push_images_but_not_change_container_apps(
    fake_az: FakeAz,
) -> None:
    fake_az.run(SCRIPT, "--apply")
    assert sorted(grants(fake_az, BUILD)) == sorted(
        [("AcrPush", REGISTRY), ("Container Registry Tasks Contributor", REGISTRY)]
    )


def test_the_deploy_identity_gets_exactly_the_listed_roles(fake_az: FakeAz) -> None:
    fake_az.run(SCRIPT, "--apply")
    got = grants(fake_az, DEPLOY)
    assert len(got) == 8
    assert ("AcrPush", REGISTRY) in got
    for app in APPS:
        assert any(
            r == "Container Apps Contributor" and s.endswith(f"/containerApps/{app}")
            for r, s in got
        ), app
    for name in ATTACHED:
        assert any(
            r == "Managed Identity Operator"
            and s.endswith(f"/userAssignedIdentities/{name}")
            for r, s in got
        ), name


def test_both_federated_credentials_trust_only_the_production_environment(
    fake_az: FakeAz,
) -> None:
    fake_az.run(SCRIPT, "--apply")
    creates = [
        c for c in fake_az.calls if c.startswith("identity federated-credential create")
    ]
    assert len(creates) == 2
    for call in creates:
        assert "--name github-production" in call
        assert f"--subject {SUBJECT}" in call
        assert "--audiences api://AzureADTokenExchange" in call
        assert "--issuer https://token.actions.githubusercontent.com" in call
        assert "refs/heads" not in call


def test_the_environment_is_main_only_with_the_owner_as_required_reviewer(
    fake_az: FakeAz,
) -> None:
    fake_az.run(SCRIPT, "--apply")
    body = json.loads(fake_az.side_file("gh-input"))
    assert body["deployment_branch_policy"] == {
        "protected_branches": False,
        "custom_branch_policies": True,
    }
    assert body["reviewers"] == [{"type": "User", "id": 4242}]
    assert body["prevent_self_review"] is False
    assert body["can_admins_bypass"] is False
    (put,) = [c for c in fake_az.gh_calls if "-X PUT" in c]
    assert f"repos/{REPO}/environments/production" in put and "--input -" in put


def test_the_main_branch_policy_is_added_when_it_is_missing(fake_az: FakeAz) -> None:
    fake_az.run(SCRIPT, "--apply")
    (post,) = branch_policy_posts(fake_az)
    assert "name=main" in post and "type=branch" in post


def test_the_main_branch_policy_is_not_added_twice(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--apply", env={"FAKE_POLICY_NAMES": "main\n"})
    assert result.returncode == 0, result.stderr
    assert branch_policy_posts(fake_az) == []


def test_another_admitted_branch_is_flagged(fake_az: FakeAz) -> None:
    result = fake_az.run(
        SCRIPT, "--apply", env={"FAKE_POLICY_NAMES": "main\nfeature-x\n"}
    )
    assert result.returncode == 0, result.stderr
    assert "WARNING" in result.stderr and "feature-x" in result.stderr


def test_the_azure_ids_become_secrets_through_stdin_not_arguments(
    fake_az: FakeAz,
) -> None:
    fake_az.run(SCRIPT, "--apply")
    expected = {
        "AZURE_TENANT_ID": "tenant-1",
        "AZURE_SUBSCRIPTION_ID": "sub-1",
        "AZURE_BUILD_CLIENT_ID": f"client-{BUILD}",
        "AZURE_DEPLOY_CLIENT_ID": f"client-{DEPLOY}",
    }
    for name, value in expected.items():
        assert f"secret set {name} -R {REPO}" in fake_az.gh_calls, name
        assert fake_az.side_file(f"secret-{name}") == value, name
        assert not any(value in c for c in fake_az.gh_calls), name
    assert not any(c.startswith("variable set") for c in fake_az.gh_calls)


def test_a_rerun_creates_no_identity_and_no_credential(fake_az: FakeAz) -> None:
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env={
            "FAKE_HAS_IDENTITIES": f"{BUILD},{DEPLOY}",
            "FAKE_HAS_CRED": f"{BUILD}/github-production,{DEPLOY}/github-production",
        },
    )
    assert result.returncode == 0, result.stderr
    assert not [c for c in fake_az.calls if c.startswith("identity create")]
    assert not [
        c for c in fake_az.calls if c.startswith("identity federated-credential create")
    ]
