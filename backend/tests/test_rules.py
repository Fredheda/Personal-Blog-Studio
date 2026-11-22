import pr_size
import shared_block
import spec_location

from tests.rules_support import (
    FIXTURES,
    GOOD,
    RECORDED,
    commit_all,
    make_repo,
    present,
    run_rules,
)


def test_the_block_runs_from_the_start_marker_to_the_end_marker():
    block = present(shared_block.extract(GOOD))
    assert block.startswith("<!-- shared:start -->\n")
    assert block.endswith("<!-- shared:end -->\n")
    assert "Repo facts." not in block


def test_an_untouched_block_passes():
    assert shared_block.check(GOOD, RECORDED) is None


def test_text_outside_the_block_may_change():
    assert shared_block.check(GOOD + "\nMore repo facts.\n", RECORDED) is None


def test_an_edited_block_fails():
    edited = (FIXTURES / "agents-block-edited.md").read_text()
    assert "differs" in present(shared_block.check(edited, RECORDED))


def test_missing_markers_fail():
    text = (FIXTURES / "agents-no-markers.md").read_text()
    assert "no shared block" in present(shared_block.check(text, RECORDED))


def test_the_hash_file_in_a_diff_is_noticed():
    assert (
        shared_block.hash_file_changed(["a.py", "scripts/rules/shared-block.sha256"])
        is True
    )
    assert shared_block.hash_file_changed(["AGENTS.md"]) is False


def rows(count: int, lines: int = 1, path: str = "src/file{}.py") -> str:
    return "".join(f"{lines}\t0\t{path.format(i)}\n" for i in range(count))


def test_26_files_fail():
    assert "26 files" in present(pr_size.check(*pr_size.measure(rows(26))))


def test_25_files_pass():
    assert pr_size.check(*pr_size.measure(rows(25))) is None


def test_5001_lines_fail():
    problem = pr_size.check(*pr_size.measure("5001\t0\tsrc/big.py\n"))
    assert "5001 lines" in present(problem)


def test_5000_lines_pass():
    assert pr_size.check(*pr_size.measure("2500\t2500\tsrc/big.py\n")) is None


def test_lockfiles_fixtures_docs_and_generated_files_do_not_count():
    numstat = (
        rows(10, 900, "frontend/package-lock.json")
        + rows(10, 900, "docs/specs/s{}.md")
        + rows(10, 900, "backend/tests/fixtures/f{}.md")
        + "9000\t0\tbackend/poetry.lock\n"
        + "9000\t0\topenapi/v1.json\n"
        + "9000\t0\tfrontend/next-env.d.ts\n"
    )
    assert pr_size.measure(numstat) == (0, 0)


def test_a_binary_file_is_a_file_without_lines():
    assert pr_size.measure("-\t-\tlogo.png\n") == (1, 0)


def test_a_rename_counts_once_at_its_new_path():
    assert pr_size.measure("0\t0\tsrc/{old => new}/x.py\n") == (1, 0)
    assert pr_size.measure("0\t0\tCLAUDE.md => AGENTS.md\n") == (1, 0)
    assert pr_size.measure("0\t0\tdocs/{a.md => b.md}\n") == (0, 0)


def label(event: str, actor: str, name: str = "size-override") -> dict:
    return {"event": event, "label": name, "actor": actor}


def test_the_owners_label_counts():
    assert pr_size.label_granted([label("labeled", "owner")], "owner") is True


def test_a_label_from_another_account_does_not_count():
    assert pr_size.label_granted([label("labeled", "agent")], "owner") is False


def test_a_removed_label_does_not_count():
    events = [label("labeled", "owner"), label("unlabeled", "owner")]
    assert pr_size.label_granted(events, "owner") is False


def test_other_labels_do_not_count():
    assert pr_size.label_granted([label("labeled", "owner", "bug")], "owner") is False


def test_a_dated_spec_outside_the_spec_folders_fails():
    assert spec_location.misplaced(["docs/shared/2026-11-22-idea.md"]) == [
        "docs/shared/2026-11-22-idea.md"
    ]


def test_a_markdown_file_in_a_folder_named_specs_elsewhere_fails():
    assert spec_location.misplaced(["notes/specs/idea.md"]) == ["notes/specs/idea.md"]


def test_specs_plans_and_diagrams_in_their_folders_pass():
    paths = [
        "docs/specs/2026-11-22-idea.md",
        "docs/plans/2026-11-22-idea.md",
        "docs/plans/diagrams/2026-11-22-idea.mmd",
    ]
    assert spec_location.misplaced(paths) == []


def test_ordinary_files_pass():
    paths = [
        "README.md",
        "docs/api-changelog.md",
        "backend/tests/fixtures/rules/agents-block-good.md",
    ]
    assert spec_location.misplaced(paths) == []


def test_added_and_renamed_to_paths_are_read_from_name_status():
    rows = "A\tx.md\nM\ty.md\nD\tz.md\nR100\told.md\tdocs/shared/2026-11-22-new.md\n"
    assert spec_location.added_paths(rows) == ["x.md", "docs/shared/2026-11-22-new.md"]


def test_a_clean_change_passes_every_rule(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "src.py").write_text("x = 1\n")
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 0
    assert result.stdout.splitlines() == [
        "pr-size: ok (1 files, 1 lines)",
        "spec-location: ok",
        "shared-block: ok",
        "comment-count: ok (0 -> 0)",
        "  src.py: 0 -> 0",
    ]


def test_an_oversized_change_fails_pr_size_only(tmp_path):
    repo = make_repo(tmp_path)
    for i in range(26):
        (repo / f"f{i}.py").write_text("x = 1\n")
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 1
    assert "pr-size: FAIL 26 files" in result.stdout
    assert "spec-location: ok" in result.stdout
    assert "shared-block: ok" in result.stdout


def test_a_spec_in_the_wrong_place_fails_spec_location_only(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "notes").mkdir()
    (repo / "notes" / "2026-11-22-idea.md").write_text("# idea\n")
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 1
    assert "spec-location: FAIL" in result.stdout
    assert "  notes/2026-11-22-idea.md" in result.stdout
    assert "pr-size: ok" in result.stdout


def test_an_edited_shared_block_fails_shared_block_only(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "AGENTS.md").write_text((FIXTURES / "agents-block-edited.md").read_text())
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 1
    assert "shared-block: FAIL" in result.stdout
    assert "spec-location: ok" in result.stdout


def test_a_block_and_its_hash_changed_together_are_flagged(tmp_path):
    repo = make_repo(tmp_path)
    edited = (FIXTURES / "agents-block-edited.md").read_text()
    (repo / "AGENTS.md").write_text(edited)
    (repo / "scripts" / "rules" / "shared-block.sha256").write_text(
        shared_block.digest(present(shared_block.extract(edited))) + "\n"
    )
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 0
    assert "shared-block: ok (hash file changed in this PR)" in result.stdout
