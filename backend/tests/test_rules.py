from pathlib import Path

import pr_size
import shared_block

RULES = Path(__file__).resolve().parents[2] / "scripts" / "rules"
FIXTURES = Path(__file__).parent / "fixtures" / "rules"
GOOD = (FIXTURES / "agents-block-good.md").read_text()
RECORDED = shared_block.digest(shared_block.extract(GOOD))


def test_the_block_runs_from_the_start_marker_to_the_end_marker():
    block = shared_block.extract(GOOD)
    assert block.startswith("<!-- shared:start -->\n")
    assert block.endswith("<!-- shared:end -->\n")
    assert "Repo facts." not in block


def test_an_untouched_block_passes():
    assert shared_block.check(GOOD, RECORDED) is None


def test_text_outside_the_block_may_change():
    assert shared_block.check(GOOD + "\nMore repo facts.\n", RECORDED) is None


def test_an_edited_block_fails():
    edited = (FIXTURES / "agents-block-edited.md").read_text()
    assert "differs" in shared_block.check(edited, RECORDED)


def test_missing_markers_fail():
    text = (FIXTURES / "agents-no-markers.md").read_text()
    assert "no shared block" in shared_block.check(text, RECORDED)


def test_the_hash_file_in_a_diff_is_noticed():
    assert shared_block.hash_file_changed(["a.py", "scripts/rules/shared-block.sha256"]) is True
    assert shared_block.hash_file_changed(["AGENTS.md"]) is False


def rows(count: int, lines: int = 1, path: str = "src/file{}.py") -> str:
    return "".join(f"{lines}\t0\t{path.format(i)}\n" for i in range(count))


def test_26_files_fail():
    assert "26 files" in pr_size.check(rows(26), override=False)


def test_25_files_pass():
    assert pr_size.check(rows(25), override=False) is None


def test_5001_lines_fail():
    assert "5001 lines" in pr_size.check("5001\t0\tsrc/big.py\n", override=False)


def test_5000_lines_pass():
    assert pr_size.check("2500\t2500\tsrc/big.py\n", override=False) is None


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


def test_an_override_lifts_the_limit():
    assert pr_size.check(rows(26), override=True) is None


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
