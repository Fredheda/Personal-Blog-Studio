import re
import sys

import common

ALLOWED = ("docs/specs/", "docs/plans/")
DATED = re.compile(r"(^|/)\d{4}-\d{2}-\d{2}-[^/]+\.(md|mmd)$")
SPEC_FOLDERS = {"spec", "specs", "plan", "plans", "superpowers"}


def misplaced(paths: list[str]) -> list[str]:
    bad = []
    for path in paths:
        if path.startswith(ALLOWED):
            continue
        in_spec_folder = bool(
            SPEC_FOLDERS & set(path.split("/")[:-1])
        ) and path.endswith((".md", ".mmd"))
        if DATED.search(path) or in_spec_folder:
            bad.append(path)
    return bad


def added_paths(name_status: str) -> list[str]:
    paths = []
    for row in name_status.splitlines():
        status, *names = row.split("\t")
        if status == "A" or status.startswith("R"):
            paths.append(names[-1])
    return paths


def main() -> int:
    bad = misplaced(added_paths(common.diff("--name-status", "-M")))
    if bad:
        print("spec-location: FAIL specs and plans belong in docs/specs and docs/plans")
        for path in bad:
            print(f"  {path}")
        return 1
    print("spec-location: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
