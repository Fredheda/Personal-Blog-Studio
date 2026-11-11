"""Keeps the pinned npm version in step across the image and the CI jobs.

Dependabot does not see `npm install -g npm@X`, so drift would be silent.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "frontend" / "Dockerfile"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
PIN = re.compile(r"npm install -g npm@(\d+\.\d+\.\d+) && npm --version")


def pins(path: Path) -> list[str]:
    return PIN.findall(path.read_text())


def count(path: Path, pattern: str) -> int:
    return len(re.findall(pattern, path.read_text(), flags=re.MULTILINE))


def test_one_npm_version_everywhere() -> None:
    versions = {v for path in (DOCKERFILE, *WORKFLOWS) for v in pins(path)}
    assert len(versions) == 1, versions


def test_every_docker_stage_pins_npm() -> None:
    assert len(pins(DOCKERFILE)) == count(DOCKERFILE, r"^FROM ") >= 2


def test_every_node_job_in_every_workflow_pins_npm() -> None:
    assert WORKFLOWS
    for workflow in WORKFLOWS:
        assert len(pins(workflow)) == count(workflow, r"uses: actions/setup-node@"), (
            workflow.name
        )
