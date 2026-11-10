import os
import shutil
import subprocess
from pathlib import Path

from conftest import REPO_ROOT

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.test",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.test",
}


def make_repo(tmp_path: Path) -> Path:
    """A throwaway git repo holding ship.sh and stub build and redeploy scripts."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "scripts" / "ship.sh", repo / "scripts" / "ship.sh")
    for name in ("build-push.sh", "redeploy.sh"):
        stub = repo / "scripts" / name
        stub.write_text(f'#!/usr/bin/env bash\necho "{name} $*" >> "$SHIP_LOG"\n')
        stub.chmod(0o755)
    for cmd in (
        ["init", "-q", "-b", "main"],
        ["add", "-A"],
        ["commit", "-q", "-m", "x"],
    ):
        subprocess.run(["git", *cmd], cwd=repo, env=GIT_ENV, check=True)
    return repo


def ship(repo: Path, log: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", "scripts/ship.sh"],
        cwd=repo,
        env={**GIT_ENV, "SHIP_LOG": str(log)},
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_a_dirty_tree_is_refused_before_anything_is_built(tmp_path: Path) -> None:
    repo, log = make_repo(tmp_path), tmp_path / "ship.log"
    (repo / "uncommitted.txt").write_text("x")
    result = ship(repo, log)
    assert result.returncode == 1
    assert "dirty" in result.stderr
    assert not log.exists()


def test_a_clean_tree_builds_then_rolls_the_head_commit(tmp_path: Path) -> None:
    repo, log = make_repo(tmp_path), tmp_path / "ship.log"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        env=GIT_ENV,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    result = ship(repo, log)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        f"build-push.sh {head}",
        f"redeploy.sh {head}",
    ]
