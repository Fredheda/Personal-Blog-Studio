"""Supply-chain rules (docs/shared/specs/2026-11-16-supply-chain-prevention.md):

1. a 14-day install cooldown beside every package.json and pyproject.toml,
   with no exclusion committed;
2. no pip or pipx install from a version range, one Poetry version in CI and
   the backend images, and Poetry's own dependencies taken inside the same
   14-day window in the images;
3. every GitHub Action pinned by commit, with its release as a comment;
4. no npx download;
5. every Docker image a Dockerfile builds from or a workflow or script runs is
   pinned by digest, with its tag kept beside it.

To bump Poetry or pip: change the pin in .github/workflows/ci.yml,
.github/workflows/security.yml and both backend Dockerfiles together.
Text-based: the CI test env has no YAML or TOML library.
"""

import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

EXACT = re.compile(r"[A-Za-z0-9_.-]+==[0-9][0-9A-Za-z.]*")
INSTALL = re.compile(r"\b(?:pip|pipx) (install|inject)\b(.*)")
ACTION = re.compile(r"uses:\s+\S+@[0-9a-f]{40}\s+#\s+v[0-9]")
POETRY_PIN = re.compile(r"poetry==([0-9][0-9.]*)")
NPX_DOWNLOAD = re.compile(r"\bnpx\s+(?:-y\b|--yes\b|[^\s@-]\S*@\S)")
PINNED_IMAGE = re.compile(r"[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9._-]+@sha256:[0-9a-f]{64}")
FROM = re.compile(r"FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.I)
DOCKER_RUN_VALUE_OPTIONS = {
    "-v",
    "--volume",
    "-w",
    "--workdir",
    "-e",
    "--env",
    "-p",
    "--publish",
    "--name",
}


def tracked(*patterns: str) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", *patterns],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines()]


def workflows() -> list[Path]:
    return tracked(".github/workflows/*.yml")


def dockerfiles() -> list[Path]:
    return tracked("backend/Dockerfile*")


def install_sources() -> list[Path]:
    return [*workflows(), *tracked("scripts/*.sh", "**/Dockerfile*")]


def lines(path: Path) -> Iterator[tuple[int, str]]:
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.lstrip().startswith("#"):
            yield number, line


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def test_every_npm_project_has_the_cooldown() -> None:
    projects = {p.parent for p in tracked("**/package.json")}
    assert projects == {ROOT / "frontend", ROOT / "frontend" / "e2e" / "azurite"}, (
        "a new npm project needs a cooldown and an entry here"
    )
    for project in projects:
        npmrc = project / ".npmrc"
        text = npmrc.read_text() if npmrc.exists() else ""
        assert "min-release-age=14" in text.splitlines(), rel(npmrc)


def test_every_poetry_project_has_the_cooldown() -> None:
    projects = {p.parent for p in tracked("**/pyproject.toml")}
    assert projects == {ROOT / "backend"}, "a new Poetry project needs a cooldown"
    for project in projects:
        poetry_toml = project / "poetry.toml"
        text = poetry_toml.read_text() if poetry_toml.exists() else ""
        assert "[solver]" in text.splitlines(), rel(poetry_toml)
        assert "min-release-age = 14" in text.splitlines(), rel(poetry_toml)


def test_no_cooldown_exclusion_is_committed() -> None:
    files = tracked("**/.npmrc", "**/poetry.toml")
    assert files, "no cooldown files found; the scan is stale"
    for path in files:
        assert "min-release-age-exclude" not in path.read_text(), rel(path)


def test_every_action_is_pinned_by_commit() -> None:
    seen = 0
    offenders = []
    for path in workflows():
        for number, line in lines(path):
            if "uses:" not in line or re.search(r"uses:\s+\./", line):
                continue
            seen += 1
            if not ACTION.search(line):
                offenders.append(f"{rel(path)}:{number}: {line.strip()}")
    assert seen >= 28, "too few uses: lines found; the scan is stale"
    assert offenders == []


def test_pip_and_pipx_installs_are_exact() -> None:
    seen = 0
    offenders = []
    for path in install_sources():
        for number, line in lines(path):
            match = INSTALL.search(line)
            if not match:
                continue
            seen += 1
            verb, rest = match.groups()
            args = re.split(r"&&|;|\|", rest.replace("\\", " "))[0].split()
            targets = []
            after_r = False
            for arg in args:
                arg = arg.strip("\"'")
                if arg.startswith("-"):
                    after_r = arg in ("-r", "--requirement")
                elif after_r:
                    after_r = False
                    if "--hash" not in (ROOT / arg).read_text():
                        offenders.append(f"{rel(path)}:{number}: unhashed -r {arg}")
                else:
                    targets.append(arg)
            if verb == "inject":
                targets = targets[1:]  # the first name is the environment
            offenders += [
                f"{rel(path)}:{number}: {t}" for t in targets if not EXACT.fullmatch(t)
            ]
    assert seen >= 8, "too few install lines found; the scan is stale"
    assert offenders == []


def test_one_poetry_version_in_ci_and_the_backend_images() -> None:
    pins = []
    for path in [*workflows(), *dockerfiles()]:
        pins += [
            (rel(path), v) for _, line in lines(path) for v in POETRY_PIN.findall(line)
        ]
    assert len(pins) >= 6, (
        f"expected 3 in ci.yml, 1 in security.yml, 1 in each Dockerfile: {pins}"
    )
    assert len({v for _, v in pins}) == 1, pins


@pytest.mark.parametrize("name", ["Dockerfile.blogapi", "Dockerfile.studio"])
def test_the_backend_images_install_poetry_inside_the_pip_window(name: str) -> None:
    dockerfile = (ROOT / "backend" / name).read_text()
    assert re.search(r"pip install --no-cache-dir pip==[0-9][0-9.]*", dockerfile)
    assert re.search(
        r"PIP_UPLOADED_PRIOR_TO=P14D pip install [^\n]*poetry==", dockerfile
    )


def test_no_npx_download() -> None:
    offenders = [
        f"{rel(path)}:{number}: {line.strip()}"
        for path in [*workflows(), *tracked("scripts/*.sh")]
        for number, line in lines(path)
        if NPX_DOWNLOAD.search(line)
    ]
    assert offenders == []


def test_the_scan_covers_the_known_install_files() -> None:
    names = {rel(p) for p in install_sources()}
    assert {
        ".github/workflows/ci.yml",
        ".github/workflows/security.yml",
        "scripts/ci-local.sh",
        "backend/Dockerfile.blogapi",
        "backend/Dockerfile.studio",
        "frontend/Dockerfile",
    } <= names


def docker_images() -> Iterator[tuple[str, str]]:
    for path in tracked("**/Dockerfile*"):
        stages: set[str] = set()
        for number, line in lines(path):
            match = FROM.match(line)
            if match:
                image, stage = match.groups()
                if image not in stages:
                    yield f"{rel(path)}:{number}", image
                if stage:
                    stages.add(stage)
    for path in [*workflows(), *tracked("scripts/*.sh")]:
        for line in path.read_text().replace("\\\n", " ").splitlines():
            match = re.search(r"\bdocker run\b(.*)", line)
            if not match or line.lstrip().startswith("#"):
                continue
            takes_value = False
            for arg in match.group(1).split():
                if takes_value:
                    takes_value = False
                elif arg.startswith("-"):
                    takes_value = arg in DOCKER_RUN_VALUE_OPTIONS
                else:
                    yield rel(path), arg
                    break


def test_every_docker_image_is_pinned_by_digest() -> None:
    images = list(docker_images())
    assert len(images) >= 10, f"too few images found; the scan is stale: {images}"
    offenders = [
        f"{at}: {ref}" for at, ref in images if not PINNED_IMAGE.fullmatch(ref)
    ]
    assert offenders == []
    digests: dict[str, set[str]] = {}
    for _, ref in images:
        digests.setdefault(ref.split(":", 1)[0], set()).add(ref)
    assert {name: refs for name, refs in digests.items() if len(refs) > 1} == {}
