import re
import subprocess
import sys
from pathlib import PurePosixPath

import common

HEADER = re.compile(r"(flowchart|graph)\s+TB\b")
CLASSES = ("new", "changed", "unchanged")
PLANS = PurePosixPath("docs/plans")


def plans(name_status: str) -> list[str]:
    found = []
    for row in name_status.splitlines():
        status, *names = row.split("\t")
        path = PurePosixPath(names[-1])
        if status[0] in "AMR" and path.parent == PLANS and path.suffix == ".md":
            found.append(names[-1])
    return found


def read(path: str) -> str | None:
    try:
        return common.git("show", f"HEAD:{path}")
    except subprocess.CalledProcessError:
        return None


def problems(plan: str, plan_text: str, diagram_text: str | None) -> list[str]:
    slug = PurePosixPath(plan).stem
    diagram = f"docs/plans/diagrams/{slug}.mmd"
    out: list[str] = []
    if diagram_text is None or not diagram_text.strip():
        out.append(f"{plan}: add {diagram}")
    else:
        first = next(line for line in diagram_text.splitlines() if line.strip())
        if not HEADER.match(first.strip()):
            out.append(f"{plan}: start the diagram with `flowchart TB` or `graph TB`")
        missing = [
            name
            for name in CLASSES
            if not re.search(rf"^\s*classDef\s+{name}\b", diagram_text, re.MULTILINE)
        ]
        if missing:
            out.append(f"{plan}: define classDef {', '.join(missing)}")
    if f"diagrams/{slug}.mmd" not in plan_text:
        out.append(f"{plan}: link diagrams/{slug}.mmd")
    return out


def main() -> int:
    checked = plans(common.diff("--name-status", "-M"))
    found: list[str] = []
    for plan in checked:
        diagram = f"docs/plans/diagrams/{PurePosixPath(plan).stem}.mmd"
        found += problems(plan, read(plan) or "", read(diagram))
    if found:
        print(f"plan-diagram: FAIL {len(found)} problem(s)")
        for line in found:
            print(f"  {line}")
        return 1
    print(f"plan-diagram: ok ({len(checked)} plan(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
