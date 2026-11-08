import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]

IMAGES = [
    ("Dockerfile.studio", "studio_api"),
    ("Dockerfile.blogapi", "blog_api"),
]


def _read(name: str) -> str:
    return (BACKEND / name).read_text()


def _copy_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("COPY")]


def test_blogapi_image_contains_only_blog_code():
    text = _read("Dockerfile.blogapi")
    assert "studio_api" not in text
    copies = " ".join(_copy_lines(text))
    assert "blog_core" in copies and "blog_api" in copies


def test_studio_image_does_not_contain_the_read_api():
    text = _read("Dockerfile.studio")
    assert "blog_api" not in text
    copies = " ".join(_copy_lines(text))
    assert "blog_core" in copies and "studio_api" in copies


@pytest.mark.parametrize("name,package", IMAGES)
def test_images_run_as_a_non_root_user(name: str, package: str):
    text = _read(name)
    users = re.findall(r"^USER (\S+)", text, re.M)
    assert users and users[-1] not in {"root", "0"}


@pytest.mark.parametrize("name,package", IMAGES)
def test_images_install_production_dependencies_only(name: str, package: str):
    assert "poetry install --only main" in _read(name)


@pytest.mark.parametrize("name,package", IMAGES)
def test_images_start_the_right_module_on_port_8000(name: str, package: str):
    text = _read(name)
    assert f'"{package}.app:app"' in text
    assert "EXPOSE 8000" in text
    assert '"--port", "8000"' in text
