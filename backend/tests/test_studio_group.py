import re

from conftest import REPO_ROOT

BACKEND = REPO_ROOT / "backend"
PYPROJECT = (BACKEND / "pyproject.toml").read_text()


def section(name: str) -> str:
    match = re.search(
        rf"^\[{re.escape(name)}\]\n(.*?)(?=^\[|\Z)", PYPROJECT, re.M | re.S
    )
    assert match, name
    return match.group(1)


def test_the_markdown_parser_is_only_in_the_studio_group() -> None:
    studio = section("tool.poetry.group.studio.dependencies")
    assert "markdown-it-py" in studio and "mdit-py-plugins" in studio
    main = PYPROJECT.split("[tool.poetry]")[0]
    assert "markdown-it" not in main and "mdit" not in main


def test_only_the_studio_image_installs_the_studio_group() -> None:
    studio = (BACKEND / "Dockerfile.studio").read_text()
    blogapi = (BACKEND / "Dockerfile.blogapi").read_text()
    assert "poetry install --only main,studio" in studio
    assert "poetry install --only main " in blogapi
    assert "studio" not in blogapi.split("poetry install", 1)[1].split("\n", 1)[0]
