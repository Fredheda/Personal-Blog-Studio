import re

from conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
DEPLOY = (WORKFLOWS / "deploy.yml").read_text()
CI = (WORKFLOWS / "ci.yml").read_text()


def test_deploy_is_manual_only_and_only_runs_on_main() -> None:
    on_block = DEPLOY.split("\nconcurrency:")[0]
    assert "workflow_dispatch:" in on_block
    for trigger in ("push:", "pull_request", "schedule:", "workflow_run:"):
        assert trigger not in on_block, trigger
    assert "if: github.ref == 'refs/heads/main'" in DEPLOY
    assert "environment: production" in DEPLOY


def test_two_deploys_never_run_at_once() -> None:
    assert "group: deploy-production" in DEPLOY
    assert "cancel-in-progress: false" in DEPLOY


def test_only_the_deploy_job_may_ask_for_an_oidc_token() -> None:
    top, job = DEPLOY.split("\njobs:")
    assert "id-token" not in top
    assert "permissions:\n  contents: read" in top
    assert DEPLOY.count("id-token: write") == 1 and "id-token: write" in job


def test_checkout_keeps_the_git_token_off_disk_and_fetches_the_history() -> None:
    assert "persist-credentials: false" in DEPLOY
    assert "fetch-depth: 0" in DEPLOY


def test_the_dispatch_input_reaches_the_shell_only_through_an_environment_variable() -> (
    None
):
    lines = [ln.strip() for ln in DEPLOY.splitlines() if "inputs.sha" in ln]
    assert lines == ["INPUT_SHA: ${{ inputs.sha }}"]


def test_only_github_owned_actions_are_used() -> None:
    uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)", DEPLOY, re.MULTILINE)
    assert uses and all(u.startswith("actions/") for u in uses)
    assert "azure/login" not in DEPLOY


def test_the_pipeline_validates_then_builds_then_rolls_then_waits() -> None:
    resolve = DEPLOY.index("Resolve and validate")
    build_login = DEPLOY.index("secrets.AZURE_BUILD_CLIENT_ID")
    build = DEPLOY.index('./scripts/build-push.sh "$SHA"')
    deploy_login = DEPLOY.index("secrets.AZURE_DEPLOY_CLIENT_ID")
    roll = DEPLOY.index('./scripts/redeploy.sh "$SHA"')
    wait = DEPLOY.index("./scripts/wait-healthy.sh")
    assert resolve < build_login < build < deploy_login < roll < wait
    # The SHA is checked before the first Azure login.
    assert "git merge-base --is-ancestor" in DEPLOY[resolve:build_login]


def test_the_azure_ids_come_from_secrets_never_from_variables() -> None:
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        assert "vars.AZURE_" not in workflow.read_text(), workflow.name
    for name in (
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_BUILD_CLIENT_ID",
        "AZURE_DEPLOY_CLIENT_ID",
    ):
        assert f"secrets.{name}" in DEPLOY, name


def test_ci_runs_on_pull_requests_only_and_never_builds_or_logs_in() -> None:
    on_block = CI.split("\njobs:")[0]
    assert "push:" not in on_block
    assert "build-push.sh" not in CI and "AZURE_" not in CI
