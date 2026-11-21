import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", path], cwd=REPO_ROOT, check=False
    )
    return result.returncode == 0


def test_the_local_run_examples_are_tracked_and_the_real_files_are_not() -> None:
    assert not ignored(".env.local.example")
    assert not ignored("frontend/.env.local.example")
    assert ignored(".env.local")
    assert ignored("frontend/.env.local")


def test_the_examples_hold_names_and_loopback_urls_only() -> None:
    for name in (".env.local.example", "frontend/.env.local.example"):
        text = (REPO_ROOT / name).read_text()
        assert "STUDIO_API_URL=http://127.0.0.1:8300" in text
        settings = [line for line in text.splitlines() if not line.startswith("#")]
        assert not any(line.startswith("STUDIO_API_AUDIENCE=") for line in settings)
    root = (REPO_ROOT / ".env.local.example").read_text()
    assert "BLOG_DRAFTS_CONTAINER=blog-drafts-dev" in root
    assert "BLOG_PUBLISHED_CONTAINER=blog-published-dev" in root
    assert "BLOG_STUDIO_ORIGINS=http://127.0.0.1:3300" in root
