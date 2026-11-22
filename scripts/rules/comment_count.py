import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import PurePosixPath

import comment_hash
import comment_python
import comment_ts
import common
from pr_size import GENERATED

SUFFIX_COUNTERS: dict[str, Callable[[str], int]] = {
    ".py": comment_python.count,
    ".ts": comment_ts.count,
    ".tsx": comment_ts.count,
    ".js": comment_ts.count,
    ".jsx": comment_ts.count,
    ".mjs": comment_ts.count,
    ".cjs": comment_ts.count,
    ".sh": comment_hash.count,
    ".yml": comment_hash.count,
    ".yaml": comment_hash.count,
    ".toml": comment_hash.count,
}
REASON = re.compile(r"^Comments:[ \t]+(\S+):[ \t]+\S.*$", re.MULTILINE)


def counter_for(path: str) -> Callable[[str], int] | None:
    pure = PurePosixPath(path)
    if path in GENERATED or "fixtures" in pure.parts[:-1]:
        return None
    if pure.name.startswith("Dockerfile"):
        return comment_hash.count
    return SUFFIX_COUNTERS.get(pure.suffix)


def paths_with_reason(text: str | None) -> set[str]:
    return {found.group(1) for found in REASON.finditer(text or "")}


def changed(name_status: str) -> list[tuple[str, str | None]]:
    rows: list[tuple[str, str | None]] = []
    for row in name_status.splitlines():
        status, *names = row.split("\t")
        if status == "A" and counter_for(names[0]):
            rows.append((names[0], None))
        elif status == "M" and counter_for(names[0]):
            rows.append((names[0], names[0]))
        elif status.startswith("R") and counter_for(names[1]):
            rows.append((names[1], names[0]))
    return rows


def code_lines(text: str, comments: int) -> int:
    nonblank = sum(1 for line in text.splitlines() if line.strip())
    return max(nonblank - comments, 0)


def allowance(code: int) -> int:
    return max(2, code // 40)


def tally(
    rows: list[tuple[str, str | None]], base: str
) -> tuple[list[tuple[str, int, int]], dict[str, int], list[str]]:
    counts: list[tuple[str, int, int]] = []
    allowed: dict[str, int] = {}
    unreadable: list[str] = []
    for path, old_path in rows:
        counter = counter_for(path)
        assert counter is not None
        try:
            before = (
                counter(common.git("show", f"{base}:{old_path}")) if old_path else 0
            )
            text = common.git("show", f"HEAD:{path}")
            after = counter(text)
        except ValueError:
            unreadable.append(path)
            continue
        counts.append((path, before, after))
        allowed[path] = allowance(code_lines(text, after))
    return counts, allowed, unreadable


def growth(counts: list[tuple[str, int, int]]) -> list[str]:
    return [path for path, before, after in counts if after > before]


def over_floor(
    counts: list[tuple[str, int, int]], allowed: dict[str, int]
) -> list[str]:
    return [path for path, _, after in counts if after > allowed[path]]


def change(before: int, after: int) -> str:
    if before == 0:
        return "0%" if after == 0 else "new"
    value = round((after - before) * 100 / before)
    return f"{value:+d}%" if value else "0%"


def summary(counts: list[tuple[str, int, int]], allowed: dict[str, int]) -> str:
    lines = [
        "| file | before | after | change | allowed |",
        "|---|---:|---:|---:|---:|",
    ]
    lines += [
        f"| {path} | {before} | {after} | {change(before, after)} | {allowed[path]} |"
        for path, before, after in counts
    ]
    total_before = sum(c[1] for c in counts)
    total_after = sum(c[2] for c in counts)
    lines.append(
        f"| **total** | {total_before} | {total_after} | "
        f"{change(total_before, total_after)} | {sum(allowed.values())} |"
    )
    return "\n".join(lines) + "\n"


def description() -> str | None:
    local = os.environ.get("COMMENTS_REASON")
    if local is not None:
        return local
    number = os.environ.get("PR_NUMBER")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (number and repo):
        return None
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{number}", "--jq", ".body"],
        capture_output=True,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def main() -> int:
    base = common.merge_base()
    rows = changed(common.diff("--name-status", "-M"))
    counts, allowed, unreadable = tally(rows, base)
    flagged = sorted(set(growth(counts)) | set(over_floor(counts, allowed)))
    given = paths_with_reason(description()) if flagged else set()
    missing = [path for path in flagged if path not in given]
    if unreadable:
        print(f"comment-count: FAIL {len(unreadable)} file(s) cannot be read")
        status = 1
    elif missing:
        print(
            f"comment-count: FAIL {len(missing)} file(s) have more comments than "
            "before or than one line per 40 code lines (at least 2) and no "
            "`Comments: <path>: <reason>` line in the PR description; "
            "cut comments, or add the line and re-run this job"
        )
        status = 1
    elif flagged:
        print(f"comment-count: ok ({len(flagged)} file(s) with a reason)")
        status = 0
    else:
        before = sum(c[1] for c in counts)
        after = sum(c[2] for c in counts)
        print(f"comment-count: ok ({before} -> {after})")
        status = 0
    for path, old, new in counts:
        note = " (reason given)" if path in given and path in flagged else ""
        print(f"  {path}: {old} -> {new}{note}")
    for path in unreadable:
        print(f"  {path}: cannot read comments")
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a") as handle:
            handle.write(summary(counts, allowed))
    return status


if __name__ == "__main__":
    sys.exit(main())
