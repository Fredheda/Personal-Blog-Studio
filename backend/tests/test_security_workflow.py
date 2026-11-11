import re

from conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SEC = (WORKFLOWS / "security.yml").read_text()
CI = (WORKFLOWS / "ci.yml").read_text()
DRAFT_SKIP = "github.event_name != 'pull_request' || !github.event.pull_request.draft"


def job_ids(text: str) -> list[str]:
    jobs = text.split("\njobs:\n", 1)[1]
    return re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", jobs, re.MULTILINE)


def job(name: str) -> str:
    jobs = SEC.split("\njobs:\n", 1)[1]
    match = re.search(
        rf"^  {name}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\s*$|\Z)",
        jobs,
        re.MULTILINE | re.DOTALL,
    )
    assert match, name
    return match.group(1)


def test_it_runs_on_pull_requests_weekly_and_on_demand_never_on_push() -> None:
    on_block = SEC.split("\nconcurrency:")[0]
    assert "pull_request:" in on_block and "ready_for_review" in on_block
    assert "schedule:" in on_block and 'cron: "23 5 * * 1"' in on_block
    assert "workflow_dispatch:" in on_block
    assert "push:" not in on_block


def test_the_jobs_are_the_expected_five() -> None:
    assert job_ids(SEC) == ["gitleaks", "bandit", "pip-audit", "npm-audit", "codeql"]


def test_no_job_repeats_a_ci_job() -> None:
    # A required check name must be unambiguous across workflows.
    assert set(job_ids(SEC)).isdisjoint(job_ids(CI))


def test_the_token_is_read_only_and_only_codeql_may_write_security_events() -> None:
    top, _ = SEC.split("\njobs:\n", 1)
    assert "permissions:\n  contents: read" in top
    assert SEC.count("security-events: write") == 1
    assert "security-events: write" in job("codeql")


def test_the_blocking_scans_cannot_be_advisory_and_the_audits_fail_on_the_weekly_run() -> (
    None
):
    for name in ("gitleaks", "bandit"):
        assert "continue-on-error" not in job(name), name
    for name in ("pip-audit", "npm-audit"):
        assert "continue-on-error: ${{ github.event_name == 'pull_request' }}" in job(
            name
        ), name


def test_gitleaks_uses_a_pinned_image_the_full_history_and_no_inline_expressions() -> (
    None
):
    block = job("gitleaks")
    assert re.search(r"ghcr\.io/gitleaks/gitleaks:v\d+\.\d+\.\d+", block)
    assert "fetch-depth: 0" in block
    assert "if:" not in block  # runs on every push to a PR, drafts included
    for line in block.splitlines():
        if "${{" in line:
            assert re.match(r"\s+[A-Z_]+: \$\{\{", line), line  # env assignments only


def test_every_other_scan_skips_draft_pull_requests() -> None:
    for name in ("bandit", "pip-audit", "npm-audit", "codeql"):
        assert DRAFT_SKIP in job(name), name


def test_bandit_scans_the_three_packages_at_high_severity_and_not_the_tests() -> None:
    block = job("bandit")
    assert "bandit==1.9.4" in block
    assert "-r backend/blog_core backend/studio_api backend/blog_api -lll" in block
    assert "backend/tests" not in block
    assert "python-version-file: backend/.python-version" in block


def test_the_audit_tools_are_pinned_to_exact_versions() -> None:
    assert re.search(r"pip-audit==\d+\.\d+\.\d+", job("pip-audit"))
    assert "npm audit --omit=dev --audit-level=high" in job("npm-audit")
    assert "working-directory: frontend" in job("npm-audit")


def test_codeql_covers_both_languages_and_skips_dependabot() -> None:
    block = job("codeql")
    assert "python" in block and "javascript-typescript" in block
    assert "build-mode: none" in block
    assert "github.actor != 'dependabot[bot]'" in block


def test_only_github_owned_actions_are_used() -> None:
    uses = re.findall(r"^\s*-?\s*uses:\s*(\S+)", SEC, re.MULTILINE)
    assert uses and all(u.startswith(("actions/", "github/")) for u in uses)
