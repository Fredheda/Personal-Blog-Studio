import os
import subprocess


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def merge_base() -> str:
    return git("merge-base", os.environ.get("BASE_SHA") or "origin/main", "HEAD").strip()
