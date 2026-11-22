"""Keeps the pinned npm version and the Node major in step across the image,
the CI jobs and `@types/node`.

Dependabot does not see `npm install -g npm@X`, so drift would be silent.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "frontend" / "Dockerfile"
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
PACKAGE_JSON = ROOT / "frontend" / "package.json"
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


def test_one_node_major_everywhere() -> None:
    images = re.findall(r"^FROM node:(\d+)-", DOCKERFILE.read_text(), re.MULTILINE)
    jobs = [
        m
        for w in WORKFLOWS
        for m in re.findall(r"node-version: (\d+)$", w.read_text(), re.MULTILINE)
    ]
    types = json.loads(PACKAGE_JSON.read_text())["devDependencies"]["@types/node"]
    assert len(images) == count(DOCKERFILE, r"^FROM ")
    assert len(jobs) == sum(count(w, r"uses: actions/setup-node@") for w in WORKFLOWS)
    assert {*images, *jobs, types.removeprefix("^")} == {images[0]}
