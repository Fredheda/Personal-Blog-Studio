import json
import os
import re
import subprocess
import sys
from pathlib import Path

import common

MAX_FILES = 25
MAX_LINES = 5000
LABEL = "size-override"
LOCKFILES = {"package-lock.json", "poetry.lock"}
GENERATED = set(Path(__file__).with_name("pr-size-generated.txt").read_text().split())


def new_path(path: str) -> str:
    braces = re.fullmatch(r"(.*)\{(.*) => (.*)\}(.*)", path)
    if braces:
        return re.sub("/+", "/", braces[1] + braces[3] + braces[4])
    if " => " in path:
        return path.split(" => ", 1)[1]
    return path


def excluded(path: str) -> bool:
    parts = path.split("/")
    return (
        parts[-1] in LOCKFILES
        or "fixtures" in parts[:-1]
        or parts[0] == "docs"
        or path in GENERATED
    )


def measure(numstat: str) -> tuple[int, int]:
    files = lines = 0
    for row in numstat.splitlines():
        added, deleted, path = row.split("\t", 2)
        if excluded(new_path(path)):
            continue
        files += 1
        lines += sum(int(n) for n in (added, deleted) if n != "-")
    return files, lines


def label_granted(events: list[dict], owner: str) -> bool:
    granted = False
    for event in events:
        if event["label"] == LABEL and event["event"] in ("labeled", "unlabeled"):
            granted = event["event"] == "labeled" and event["actor"] == owner
    return granted


def check(files: int, lines: int) -> str | None:
    if files <= MAX_FILES and lines <= MAX_LINES:
        return None
    return (
        f"{files} files and {lines} lines (limit {MAX_FILES} and {MAX_LINES}); "
        f"split the PR, or the owner sets the label {LABEL} and re-runs this job"
    )


def override_granted() -> bool:
    number = os.environ.get("PR_NUMBER")
    repo = os.environ.get("GITHUB_REPOSITORY")
    owner = os.environ.get("GITHUB_REPOSITORY_OWNER")
    if not (number and repo and owner):
        return False
    pick = (
        '.[] | select(.event == "labeled" or .event == "unlabeled")'
        " | {event: .event, label: .label.name, actor: .actor.login}"
    )
    result = subprocess.run(
        [
            "gh",
            "api",
            "--paginate",
            f"repos/{repo}/issues/{number}/events",
            "--jq",
            pick,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return label_granted(events, owner)


def main() -> int:
    files, lines = measure(common.diff("--numstat", "-M"))
    problem = check(files, lines)
    if problem and override_granted():
        problem = None
    if problem:
        print(f"pr-size: FAIL {problem}")
        return 1
    print(f"pr-size: ok ({files} files, {lines} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
