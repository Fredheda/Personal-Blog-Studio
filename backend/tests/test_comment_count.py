from pathlib import Path

import comment_count
import pytest

from tests.rules_support import commit_all, make_repo, run_rules


def write(repo: Path, path: str, text: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def repo_with(tmp_path: Path, path: str, before: str, after: str) -> Path:
    repo = make_repo(tmp_path)
    write(repo, path, before)
    commit_all(repo)
    write(repo, path, after)
    commit_all(repo)
    return repo


def test_a_new_comment_in_an_existing_file_fails(tmp_path):
    repo = repo_with(tmp_path, "src.py", "x = 1\n", "x = 1  # why\n")
    result = run_rules(repo)
    assert result.returncode == 1
    assert "comment-count: FAIL 1 file(s) have more comments" in result.stdout
    assert "  src.py: 0 -> 1" in result.stdout


def test_a_new_file_starts_at_zero(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "web/a.ts", "// note\nexport const a = 1;\n")
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 1
    assert "  web/a.ts: 0 -> 1" in result.stdout


def test_fewer_comments_pass(tmp_path):
    repo = repo_with(tmp_path, "src.py", "# a\n# b\nx = 1\n", "# a\nx = 1\n")
    result = run_rules(repo)
    assert result.returncode == 0
    assert "comment-count: ok (2 -> 1)" in result.stdout


def test_a_line_naming_the_file_lifts_its_failure(tmp_path):
    repo = repo_with(tmp_path, "src.py", "x = 1\n", "x = 1  # why\n")
    result = run_rules(repo, COMMENTS_REASON="Comments: src.py: a secret reason")
    assert result.returncode == 0
    assert "comment-count: ok (1 file(s) with a reason)" in result.stdout
    assert "  src.py: 0 -> 1 (reason given)" in result.stdout
    assert "a secret reason" not in result.stdout


def test_a_line_for_one_file_does_not_lift_another(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "a.py", "# one\n")
    write(repo, "b.py", "# two\n")
    commit_all(repo)
    result = run_rules(repo, COMMENTS_REASON="Comments: a.py: needed")
    assert result.returncode == 1
    assert "comment-count: FAIL 1 file(s) have more comments" in result.stdout
    assert "  a.py: 0 -> 1 (reason given)" in result.stdout
    assert "  b.py: 0 -> 1\n" in result.stdout


def test_a_line_without_a_reason_or_a_path_does_not_count(tmp_path):
    repo = repo_with(tmp_path, "src.py", "x = 1\n", "x = 1  # why\n")
    assert run_rules(repo, COMMENTS_REASON="Comments: src.py:   ").returncode == 1
    assert run_rules(repo, COMMENTS_REASON="Comments: needed").returncode == 1


def test_a_rename_keeps_its_old_count(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "old.py", "# keep\nx = 1\n")
    commit_all(repo)
    (repo / "old.py").rename(repo / "new.py")
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 0
    assert "  new.py: 1 -> 1" in result.stdout


def test_fixtures_generated_files_and_other_languages_are_not_counted(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "tests/fixtures/sample.py", "# note\n")
    write(repo, "frontend/next-env.d.ts", "// note\n")
    write(repo, "notes.md", "# heading\n")
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 0
    assert "comment-count: ok (0 -> 0)" in result.stdout


@pytest.mark.parametrize(
    "path", ["run.sh", "ci.yml", "deploy.yaml", "pyproject.toml", "Dockerfile.api"]
)
def test_full_line_hash_comments_count_in_scripts_and_config(tmp_path, path):
    repo = make_repo(tmp_path)
    write(repo, path, "# header narrative\nkey = 1\n")
    commit_all(repo)
    result = run_rules(repo)
    assert result.returncode == 1
    assert f"  {path}: 0 -> 1" in result.stdout


def code_with_comments(code: int, comments: int) -> str:
    lines = [f"x{i} = {i}" for i in range(code)]
    notes = [f"# c{i}" for i in range(comments)]
    return "\n".join(lines[:1] + notes + lines[1:]) + "\n"


def test_a_shrinking_file_above_the_floor_still_fails(tmp_path):
    repo = repo_with(
        tmp_path, "big.py", code_with_comments(10, 6), code_with_comments(10, 5)
    )
    result = run_rules(repo)
    assert result.returncode == 1
    assert "comment-count: FAIL 1 file(s) have more comments" in result.stdout
    assert "  big.py: 6 -> 5" in result.stdout


def test_a_file_at_one_comment_line_per_40_code_lines_passes(tmp_path):
    repo = repo_with(
        tmp_path, "big.py", code_with_comments(400, 12), code_with_comments(400, 10)
    )
    result = run_rules(repo)
    assert result.returncode == 0
    assert "  big.py: 12 -> 10" in result.stdout


def test_a_file_one_comment_line_over_the_floor_fails(tmp_path):
    repo = repo_with(
        tmp_path, "big.py", code_with_comments(400, 12), code_with_comments(400, 11)
    )
    assert run_rules(repo).returncode == 1


def test_a_line_naming_the_file_lifts_the_floor(tmp_path):
    repo = repo_with(
        tmp_path, "big.py", code_with_comments(400, 12), code_with_comments(400, 11)
    )
    result = run_rules(repo, COMMENTS_REASON="Comments: big.py: legacy, cut later")
    assert result.returncode == 0
    assert "  big.py: 12 -> 11 (reason given)" in result.stdout


@pytest.mark.parametrize(
    ("code", "expected"), [(0, 2), (79, 2), (80, 2), (119, 2), (120, 3), (400, 10)]
)
def test_the_allowance_is_one_line_per_40_code_lines_and_at_least_two(code, expected):
    assert comment_count.allowance(code) == expected


def test_code_lines_leave_out_blank_lines_and_comment_lines():
    assert comment_count.code_lines("x = 1\n\n# c\ny = 2\n", 1) == 2


def test_a_file_that_cannot_be_read_fails_even_with_a_reason(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "broken.py", "def (:\n")
    commit_all(repo)
    result = run_rules(repo, COMMENTS_REASON="Comments: broken.py: anything")
    assert result.returncode == 1
    assert "  broken.py: cannot read comments" in result.stdout


def test_the_job_summary_shows_the_change_per_file_and_in_total(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "a.py", "# a\n# b\nx = 1\n")
    write(repo, "b.py", "x = 1\n")
    commit_all(repo)
    write(repo, "a.py", "# a\nx = 1\n")
    write(repo, "b.py", "# new\nx = 1\n")
    write(repo, "c.py", "x = 1\n")
    commit_all(repo)
    summary = tmp_path / "summary.md"
    run_rules(
        repo, GITHUB_STEP_SUMMARY=str(summary), COMMENTS_REASON="Comments: b.py: x"
    )
    assert summary.read_text().splitlines() == [
        "| file | before | after | change | allowed |",
        "|---|---:|---:|---:|---:|",
        "| a.py | 2 | 1 | -50% | 2 |",
        "| b.py | 0 | 1 | new | 2 |",
        "| c.py | 0 | 0 | 0% | 2 |",
        "| **total** | 2 | 2 | 0% | 6 |",
    ]


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Comments: src/a.py: needed for X\n", {"src/a.py"}),
        ("text\n\nComments: a.py: why\nComments: b.ts: also: this\n", {"a.py", "b.ts"}),
        ("Comments: a.py: why\r\n", {"a.py"}),
        ("Comments: a.py:\n", set()),
        ("Comments: a.py:   \n", set()),
        ("Comments: just a reason\n", set()),
        ("see Comments: a.py: why\n", set()),
        ("", set()),
        (None, set()),
    ],
)
def test_paths_with_a_reason_come_from_lines_of_the_description(body, expected):
    assert comment_count.paths_with_reason(body) == expected


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [(4, 1, "-75%"), (2, 3, "+50%"), (3, 3, "0%"), (0, 0, "0%"), (0, 2, "new")],
)
def test_change_is_a_signed_percent(before, after, expected):
    assert comment_count.change(before, after) == expected


def test_only_added_modified_and_renamed_countable_files_are_read():
    name_status = (
        "A\tnew.py\nM\tweb/a.tsx\nD\tgone.py\nR100\told.py\tmoved.py\n"
        "A\tREADME.md\nA\tx/fixtures/f.py\nM\tci.yml\nA\tDockerfile.api\n"
        "A\tfrontend/next-env.d.ts\n"
    )
    assert comment_count.changed(name_status) == [
        ("new.py", None),
        ("web/a.tsx", "web/a.tsx"),
        ("moved.py", "old.py"),
        ("ci.yml", "ci.yml"),
        ("Dockerfile.api", None),
    ]
