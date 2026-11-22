import re
import sys
from pathlib import Path

import comment_count
import comment_model
import common
from comment_model import Comment

DATA = Path(__file__).with_name("comment-content-patterns.txt")
HEADER_LIMIT = 3
STOP_WORDS = {
    "a",
    "an",
    "the",
    "of",
    "to",
    "for",
    "by",
    "in",
    "on",
    "and",
    "or",
    "is",
    "are",
    "this",
    "that",
    "with",
    "from",
    "return",
    "returns",
    "args",
    "arg",
    "param",
    "parameter",
    "parameters",
    "self",
    "cls",
}
LANGUAGES = {"comment_python": "python", "comment_ts": "ts", "comment_hash": "hash"}


def load() -> list[tuple[str, str, re.Pattern[str], str]]:
    rows = []
    for row in DATA.read_text().splitlines():
        if row.strip():
            kind, language, regex, message = row.split("\t", 3)
            rows.append((kind, language, re.compile(regex), message))
    return rows


PATTERNS = load()
NAMES = Path(__file__).with_name("comment-projects.txt").read_text().split()
PROJECT_NAME = re.compile(r"(?i)\b(" + "|".join(map(re.escape, NAMES)) + r")\b")


def header_lines(source: str, found: list[Comment]) -> int:
    covered = comment_model.lines(found, own_line=True)
    skipped = comment_model.lines(found, directive=True)
    total = 0
    for number, text in enumerate(source.splitlines(), 1):
        if not text.strip() or number in skipped:
            continue
        if number not in covered:
            break
        total += 1
    return total


def repeats_owner(comment: Comment) -> bool:
    if comment.owner is None:
        return False
    words = set(re.findall(r"[a-z]+", comment.text.lower())) - STOP_WORDS
    return bool(words) and words <= comment.owner


def problems(path: str, source: str, language: str, found: list[Comment]) -> list[str]:
    out: list[str] = []
    for comment in found:
        for kind, scope, pattern, message in PATTERNS:
            applies = kind == "content" or comment.directive
            if not applies or scope not in ("all", language):
                continue
            if pattern.search(comment.text):
                out.append(f"{path}:{comment.line}: {message}")
        if PROJECT_NAME.search(comment.text):
            out.append(
                f"{path}:{comment.line}: names a project: "
                "state the constraint on its own"
            )
        if repeats_owner(comment):
            out.append(
                f"{path}:{comment.line}: the docstring only repeats the name "
                "and parameters: delete it"
            )
    header = header_lines(source, found)
    if header > HEADER_LIMIT:
        out.append(
            f"{path}:1: the file header has {header} comment lines "
            f"(at most {HEADER_LIMIT}): delete the narration"
        )
    return out


def main() -> int:
    rows = comment_count.changed(common.diff("--name-status", "-M"))
    found_problems: list[str] = []
    unreadable: list[str] = []
    read = 0
    for path, _ in rows:
        module = comment_count.module_for(path)
        if module is None:
            continue
        source = common.git("show", f"HEAD:{path}")
        try:
            found = module.comments(source)
        except ValueError:
            unreadable.append(path)
            continue
        read += 1
        language = LANGUAGES[module.__name__]
        found_problems += problems(path, source, language, found)
    if found_problems or unreadable:
        total = len(found_problems) + len(unreadable)
        print(f"comment-content: FAIL {total} problem(s)")
        for line in found_problems:
            print(f"  {line}")
        for path in unreadable:
            print(f"  {path}: cannot read comments")
        return 1
    print(f"comment-content: ok ({read} file(s) read)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
