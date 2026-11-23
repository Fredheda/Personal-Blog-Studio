from pathlib import Path

import comment_content
import comment_python
import pytest

from tests.rules_support import commit_all, make_repo, run_rules


def content_output(tmp_path: Path, files: dict[str, str]) -> str:
    repo = make_repo(tmp_path)
    for path, text in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    commit_all(repo)
    reasons = "\n".join(f"Comments: {path}: x" for path in files)
    stdout = run_rules(repo, COMMENTS_REASON=reasons).stdout
    return stdout[stdout.index("comment-content:") :]


@pytest.mark.parametrize(
    ("path", "text", "message"),
    [
        ("src.py", "x = 1  # see BLOG-56\n", "names a ticket"),
        ("src.py", "# PAIR-46 decided this\nx = 1\n", "names a ticket"),
        ("src.py", "x = 1  # see docs/plans/a.md\n", "points at a spec or a plan"),
        (
            "src.py",
            f"x = 1  # same as {comment_content.NAMES[0]} does\n",
            "names a project",
        ),
        ("src.py", "x = 1  # this used to be a list\n", "narrates history"),
        ("src.py", "x = 1  # removed in the refactor\n", "narrates history"),
        ("web/a.ts", "export const a = 1; // no longer needed\n", "narrates history"),
        ("web/a.ts", "/* tracked as CKE-7 */\nexport {};\n", "names a ticket"),
        ("run.sh", "# the old script, see git history\nset -e\n", "narrates history"),
        ("src.py", "import os  # noqa: F401 see BLOG-12\n", "names a ticket"),
        (
            "web/a.ts",
            "// eslint-disable-next-line no-console -- see PAIR-3\nexport {};\n",
            "names a ticket",
        ),
        ("src.py", "x = 1  # it used to be a list\n", "narrates history"),
    ],
)
def test_a_comment_with_banned_content_fails_and_the_comments_line_does_not_lift_it(
    tmp_path, path, text, message
):
    output = content_output(tmp_path, {path: text})
    assert output.startswith("comment-content: FAIL 1 problem(s)")
    assert f"  {path}:1: " in output
    assert message in output


def test_an_ordinary_sentence_with_used_to_passes(tmp_path):
    text = "x = 1  # the key used to sign the token\n"
    assert content_output(tmp_path, {"src.py": text}).startswith("comment-content: ok")


def test_the_same_words_in_a_string_or_in_code_pass(tmp_path):
    text = f'LABEL = "BLOG-56 {comment_content.NAMES[0]} used to"\n'
    assert content_output(tmp_path, {"src.py": text}).startswith("comment-content: ok")


def test_the_failure_names_the_line_and_never_echoes_the_comment(tmp_path):
    output = content_output(tmp_path, {"src.py": "x = 1\ny = 2  # see BLOG-56\n"})
    assert "  src.py:2: names a ticket: delete the reference" in output
    assert "BLOG-56" not in output


def test_a_header_of_four_comment_lines_fails_and_three_pass(tmp_path):
    four = "# a\n# b\n# c\n# d\nx = 1\n"
    three = "# a\n# b\n# c\nx = 1\n"
    failing = content_output(tmp_path / "four", {"src.py": four})
    assert "  src.py:1: the file header has 4 comment lines (at most 3)" in failing
    assert content_output(tmp_path / "three", {"src.py": three}).startswith(
        "comment-content: ok"
    )


def test_a_shebang_and_a_directive_do_not_count_toward_the_header(tmp_path):
    text = "#!/usr/bin/env python3\n# ruff: noqa: F401\n# a\n# b\n# c\nx = 1\n"
    assert content_output(tmp_path, {"src.py": text}).startswith("comment-content: ok")


def test_trailing_comments_on_code_lines_are_not_header(tmp_path):
    text = "a = 1  # a\nb = 2  # b\nc = 3  # c\nd = 4  # d\n"
    assert content_output(tmp_path, {"src.py": text}).startswith("comment-content: ok")


def test_a_trailing_comment_ends_the_header(tmp_path):
    text = "# a\n# b\nx = 1  # c\n# d\n# e\n"
    assert content_output(tmp_path, {"src.py": text}).startswith("comment-content: ok")


def test_a_directive_inside_the_header_does_not_hide_its_length(tmp_path):
    text = "# a\n# ruff: noqa: F401\n# b\n# c\n# d\nx = 1\n"
    assert "the file header has 4 comment lines" in content_output(
        tmp_path, {"src.py": text}
    )


def test_comments_after_the_first_code_line_are_not_header(tmp_path):
    text = "x = 1\n# a\n# b\n# c\n# d\ny = 2\n"
    assert content_output(tmp_path, {"src.py": text}).startswith("comment-content: ok")


def test_a_module_docstring_counts_toward_the_header(tmp_path):
    text = '"""one\ntwo\nthree\nfour"""\nx = 1\n'
    assert "the file header has 4 comment lines" in content_output(
        tmp_path, {"src.py": text}
    )


def test_a_docstring_that_only_repeats_the_name_and_parameters_fails(tmp_path):
    text = 'def get_user(user_id):\n    """Get user by id."""\n    return user_id\n'
    output = content_output(tmp_path, {"src.py": text})
    assert "  src.py:2: the docstring only repeats the name and parameters" in output


def test_a_docstring_that_uses_only_some_of_the_name_words_fails(tmp_path):
    text = 'def get_user(user_id):\n    """Get user."""\n    return user_id\n'
    output = content_output(tmp_path, {"src.py": text})
    assert "the docstring only repeats the name and parameters" in output


def test_a_docstring_that_says_more_passes(tmp_path):
    text = 'def get_user(user_id):\n    """Raises when the id is blocked."""\n    return 1\n'
    assert content_output(tmp_path, {"src.py": text}).startswith("comment-content: ok")


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("src.py", "import os  # noqa\n"),
        ("src.py", "import os  # noqa: ERA001\n"),
        ("src.py", "import os  # noqa: F401, FIX002\n"),
        ("src.py", "# ruff: noqa\nx = 1\n"),
        ("src.py", "# flake8: noqa\nx = 1\n"),
        ("src.py", "# flake8: noqa: ERA001\nx = 1\n"),
        ("src.py", "# ruff: disable[ERA001]\nx = 1\n"),
        ("src.py", "# ruff: file-ignore[FIX002]\nx = 1\n"),
        ("web/a.ts", '/* eslint no-warning-comments: "off" */\nexport {};\n'),
        ("web/a.ts", "/* eslint no-warning-comments: 0 */\nexport {};\n"),
        ("web/a.ts", '/*eslint no-warning-comments: ["off"] */\nexport {};\n'),
        ("web/a.ts", "// eslint-disable-next-line\nexport {};\n"),
        ("web/a.ts", "/* eslint-disable */\nexport {};\n"),
        ("web/a.ts", "// eslint-disable-next-line no-warning-comments\nexport {};\n"),
        ("web/a.ts", "/* eslint-disable\nno-warning-comments */\nexport {};\n"),
        ("web/a.ts", "/* eslint-disable -- a\nb */\nexport {};\n"),
        ("web/a.ts", "// eslint-disable-line -- reason\nexport {};\n"),
        ("web/a.ts", "// eslint-disable-next-line no-restricted-imports\nexport {};\n"),
        ("web/a.ts", "/* eslint-disable no-restricted-syntax */\nexport {};\n"),
        ("web/a.ts", '/* eslint no-restricted-syntax: "off" */\nexport {};\n'),
        ("web/a.ts", "/* eslint no-restricted-imports: 0 */\nexport {};\n"),
        ("web/a.ts", "/* eslint-disable\nno-restricted-imports */\nexport {};\n"),
    ],
)
def test_switching_off_a_comment_lint_rule_or_all_rules_fails(tmp_path, path, text):
    output = content_output(tmp_path, {path: text})
    assert output.startswith("comment-content: FAIL")
    assert "lint rule" in output


@pytest.mark.parametrize(
    ("path", "text"),
    [
        ("src.py", "def f(N803):  # noqa: N803\n    return N803\n"),
        ("src.py", "# ruff: disable[E501]\nx = 1\n# ruff: enable[E501]\n"),
        ("web/a.ts", '/* eslint no-console: "off" */\nexport {};\n'),
        (
            "web/a.ts",
            "// eslint-disable-next-line react-hooks/exhaustive-deps\nexport {};\n",
        ),
    ],
)
def test_switching_off_an_unrelated_rule_is_left_alone(tmp_path, path, text):
    assert content_output(tmp_path, {path: text}).startswith("comment-content: ok")


def test_a_file_that_cannot_be_read_fails(tmp_path):
    output = content_output(tmp_path, {"broken.py": "def (:\n"})
    assert "  broken.py: cannot read comments" in output


def test_header_lines_skip_blank_lines_and_stop_at_code():
    source = "\n# a\n\n# b\nx = 1\n# c\n"
    found = comment_python.comments(source)
    assert comment_content.header_lines(source, found) == 2
