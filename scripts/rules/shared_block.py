import hashlib
import sys
from pathlib import Path

import common

START = "<!-- shared:start -->"
END = "<!-- shared:end -->"
HASH_FILE = "scripts/rules/shared-block.sha256"
RECORDED = Path(__file__).with_name("shared-block.sha256")


def extract(text: str) -> str | None:
    lines = text.splitlines()
    if START not in lines or END not in lines:
        return None
    first, last = lines.index(START), lines.index(END)
    if last < first:
        return None
    return "\n".join(lines[first : last + 1]) + "\n"


def digest(block: str) -> str:
    return hashlib.sha256(block.encode()).hexdigest()


def check(agents_text: str, recorded: str) -> str | None:
    block = extract(agents_text)
    if block is None:
        return "AGENTS.md has no shared block between the markers"
    if digest(block) != recorded.strip():
        return "the shared block differs from the owner's template (hash mismatch)"
    return None


def hash_file_changed(changed: list[str]) -> bool:
    return HASH_FILE in changed


def main(argv: list[str]) -> int:
    if argv[1:2] == ["--print-hash"]:
        block = extract(Path(argv[2]).read_text())
        if block is None:
            print("no shared block", file=sys.stderr)
            return 1
        print(digest(block))
        return 0
    problem = check(Path("AGENTS.md").read_text(), RECORDED.read_text())
    if problem:
        print(f"shared-block: FAIL {problem}")
        return 1
    changed = common.git("diff", "--name-only", "-M", common.merge_base(), "HEAD").splitlines()
    print("shared-block: ok (hash file changed in this PR)" if hash_file_changed(changed) else "shared-block: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
