import re

from conftest import REPO_ROOT

TEXT = (REPO_ROOT / ".github" / "dependabot.yml").read_text()
ENTRIES = {
    block.split("\n", 1)[0].strip(): block
    for block in TEXT.split("\n  - package-ecosystem: ")[1:]
}


def directories(block: str) -> list[str]:
    single = re.findall(r"directory:\s*(/\S*)", block)
    listed = re.findall(r"^\s+- (/\S*)\s*$", block, re.MULTILINE)
    return single + listed


def test_the_four_ecosystems_are_each_configured_once() -> None:
    assert sorted(ENTRIES) == ["docker", "github-actions", "npm", "pip"]
    assert TEXT.count("package-ecosystem:") == 4


def test_every_directory_exists_and_holds_the_manifest_dependabot_reads() -> None:
    expected = {
        "pip": ["/backend"],
        "npm": ["/frontend"],
        "github-actions": ["/"],
        "docker": ["/backend", "/frontend"],
    }
    for ecosystem, block in ENTRIES.items():
        dirs = directories(block)
        assert sorted(dirs) == sorted(expected[ecosystem]), ecosystem
        for directory in dirs:
            path = REPO_ROOT / directory.lstrip("/")
            assert path.is_dir(), directory
            if ecosystem == "pip":
                assert (path / "pyproject.toml").exists()
                assert (path / "poetry.lock").exists()
            elif ecosystem == "npm":
                assert (path / "package.json").exists()
                assert (path / "package-lock.json").exists()
            elif ecosystem == "github-actions":
                assert (path / ".github" / "workflows").is_dir()
            else:
                assert any(p.name.startswith("Dockerfile") for p in path.iterdir()), (
                    directory
                )


def test_every_ecosystem_is_weekly_waits_14_days_and_groups_minor_and_patch() -> None:
    for ecosystem, block in ENTRIES.items():
        assert "interval: weekly" in block, ecosystem
        assert "default-days: 14" in block, ecosystem
        assert "update-types: [minor, patch]" in block, ecosystem
        assert "open-pull-requests-limit: 5" in block, ecosystem
        assert "labels: [dependencies]" in block, ecosystem


def test_major_updates_are_not_grouped_with_the_rest() -> None:
    grouped = re.findall(r"^\s+update-types: \[(.*)\]\s*$", TEXT, re.MULTILINE)
    assert grouped and all("major" not in types for types in grouped)


def test_the_pinned_runtimes_are_not_bumped_by_dependabot() -> None:
    docker = ENTRIES["docker"]
    assert re.search(
        r'dependency-name: node\n\s+update-types: \["version-update:semver-major"\]',
        docker,
    )
    assert re.search(
        r'dependency-name: python\n\s+update-types: \["version-update:semver-major", "version-update:semver-minor"\]',
        docker,
    )
