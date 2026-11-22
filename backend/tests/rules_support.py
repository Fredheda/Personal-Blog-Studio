import os
import shutil
import subprocess
from pathlib import Path

import shared_block

RULES = Path(__file__).resolve().parents[2] / "scripts" / "rules"
FIXTURES = Path(__file__).parent / "fixtures" / "rules"
GOOD = (FIXTURES / "agents-block-good.md").read_text()
GIT = [
    "git",
    "-c",
    "user.name=t",
    "-c",
    "user.email=t@t",
    "-c",
    "commit.gpgsign=false",
]
FOREIGN_ENV = (
    "PR_NUMBER",
    "GITHUB_REPOSITORY",
    "COMMENTS_REASON",
    "GITHUB_STEP_SUMMARY",
)


def present(value: str | None) -> str:
    assert value is not None
    return value


RECORDED = shared_block.digest(present(shared_block.extract(GOOD)))


def make_repo(tmp_path: Path, agents: str = GOOD) -> Path:
    shutil.copytree(
        RULES,
        tmp_path / "scripts" / "rules",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    (tmp_path / "scripts" / "rules" / "shared-block.sha256").write_text(RECORDED + "\n")
    (tmp_path / "AGENTS.md").write_text(agents)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, check=True)
    commit_all(tmp_path)
    return tmp_path


def commit_all(repo: Path) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "change"], cwd=repo, check=True)


def run_rules(repo: Path, **extra_env: str) -> subprocess.CompletedProcess:
    base = subprocess.run(
        ["git", "rev-parse", "HEAD~1"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    env = {k: v for k, v in os.environ.items() if k not in FOREIGN_ENV}
    return subprocess.run(
        ["bash", "scripts/rules/run.sh"],
        cwd=repo,
        env={**env, "BASE_SHA": base, **extra_env},
        capture_output=True,
        text=True,
    )
