from pathlib import Path

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
