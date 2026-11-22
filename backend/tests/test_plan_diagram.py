from pathlib import Path

import plan_diagram
import pytest

from tests.rules_support import commit_all, make_repo, run_rules

DIAGRAM = (
    "flowchart TB\n"
    "  classDef new fill:#c8e6c9\n"
    "  classDef changed fill:#ffe0b2\n"
    "  classDef unchanged fill:#e0e0e0\n"
    "  a[A]:::new --> b[B]:::changed\n"
)
PLAN = "# Plan\n\nSource: `docs/plans/diagrams/2026-11-22-x.mmd`.\n"


def plan_output(
    tmp_path: Path, files: dict[str, str], before: dict[str, str] | None = None
) -> str:
    repo = make_repo(tmp_path)
    for path, text in (before or {}).items():
        write(repo, path, text)
    if before:
        commit_all(repo)
    for path, text in files.items():
        write(repo, path, text)
    commit_all(repo)
    stdout = run_rules(repo).stdout
    return stdout[stdout.index("plan-diagram:") :]


def write(repo: Path, path: str, text: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def test_a_plan_with_its_diagram_passes(tmp_path):
    files = {
        "docs/plans/2026-11-22-x.md": PLAN,
        "docs/plans/diagrams/2026-11-22-x.mmd": DIAGRAM,
    }
    assert plan_output(tmp_path, files).startswith(
        "plan-diagram: ok (1 plan(s) checked)"
    )


def test_a_plan_without_a_diagram_fails_and_says_what_to_add(tmp_path):
    output = plan_output(tmp_path, {"docs/plans/2026-11-22-x.md": PLAN})
    assert output.startswith("plan-diagram: FAIL 1 problem(s)")
    assert (
        "  docs/plans/2026-11-22-x.md: add docs/plans/diagrams/2026-11-22-x.mmd"
        in output
    )


@pytest.mark.parametrize(
    ("diagram", "message"),
    [
        ("", "add docs/plans/diagrams/2026-11-22-x.mmd"),
        ("\n  \n", "add docs/plans/diagrams/2026-11-22-x.mmd"),
        (
            DIAGRAM.replace("flowchart TB", "sequenceDiagram"),
            "start the diagram with `flowchart TB` or `graph TB`",
        ),
        (
            DIAGRAM.replace("flowchart TB", "flowchart LR"),
            "start the diagram with `flowchart TB` or `graph TB`",
        ),
        (
            DIAGRAM.replace("  classDef changed fill:#ffe0b2\n", ""),
            "define classDef changed",
        ),
        (
            DIAGRAM.replace("classDef new fill", "classDef newest fill"),
            "define classDef new",
        ),
        (
            "graph TB\n  a --> b\n",
            "define classDef new, changed, unchanged",
        ),
    ],
)
def test_a_diagram_that_is_empty_or_not_a_top_down_flowchart_with_the_classes_fails(
    tmp_path, diagram, message
):
    files = {
        "docs/plans/2026-11-22-x.md": PLAN,
        "docs/plans/diagrams/2026-11-22-x.mmd": diagram,
    }
    output = plan_output(tmp_path, files)
    assert output.startswith("plan-diagram: FAIL 1 problem(s)")
    assert message in output


def test_graph_tb_is_accepted_as_a_header(tmp_path):
    files = {
        "docs/plans/2026-11-22-x.md": PLAN,
        "docs/plans/diagrams/2026-11-22-x.mmd": DIAGRAM.replace("flowchart", "graph"),
    }
    assert plan_output(tmp_path, files).startswith("plan-diagram: ok")


def test_a_plan_that_does_not_link_its_diagram_fails(tmp_path):
    files = {
        "docs/plans/2026-11-22-x.md": "# Plan\n\nNo link here.\n",
        "docs/plans/diagrams/2026-11-22-x.mmd": DIAGRAM,
    }
    output = plan_output(tmp_path, files)
    assert "  docs/plans/2026-11-22-x.md: link diagrams/2026-11-22-x.mmd" in output


def test_a_changed_plan_without_a_diagram_fails_too(tmp_path):
    before = {"docs/plans/2026-11-22-x.md": PLAN}
    files = {"docs/plans/2026-11-22-x.md": PLAN + "\nMore.\n"}
    output = plan_output(tmp_path, files, before)
    assert output.startswith("plan-diagram: FAIL 1 problem(s)")


def test_a_plan_that_the_pr_does_not_touch_is_not_read(tmp_path):
    before = {"docs/plans/2026-11-22-old.md": "# Old plan\n"}
    files = {"README.md": "# Readme\n"}
    assert plan_output(tmp_path, files, before).startswith(
        "plan-diagram: ok (0 plan(s) checked)"
    )


def test_a_deleted_plan_and_files_that_are_not_plans_are_not_read(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "docs/plans/2026-11-22-old.md", "# Old plan\n")
    commit_all(repo)
    (repo / "docs/plans/2026-11-22-old.md").unlink()
    write(repo, "docs/plans/diagrams/2026-11-22-old.mmd", "")
    write(repo, "docs/specs/2026-11-22-old.md", "# Spec\n")
    commit_all(repo)
    stdout = run_rules(repo).stdout
    assert "plan-diagram: ok (0 plan(s) checked)" in stdout


def test_plans_are_found_among_added_changed_and_renamed_paths():
    name_status = (
        "A\tdocs/plans/a.md\nM\tdocs/plans/b.md\nD\tdocs/plans/c.md\n"
        "R090\tdocs/plans/old.md\tdocs/plans/d.md\nA\tdocs/plans/diagrams/a.mmd\n"
        "A\tdocs/specs/a.md\nA\tother/docs/plans/e.md\nA\tdocs/plans/sub/f.md\n"
    )
    assert plan_diagram.plans(name_status) == [
        "docs/plans/a.md",
        "docs/plans/b.md",
        "docs/plans/d.md",
    ]
