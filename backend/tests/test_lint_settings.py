import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"
CODES = ["ERA001", "FIX001", "FIX002", "FIX003", "FIX004"]


def rule_codes(tmp_path: Path, source: str) -> set[str]:
    target = tmp_path / "sample.py"
    target.write_text(source)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--config",
            str(PYPROJECT),
            "--output-format",
            "json",
            str(target),
        ],
        capture_output=True,
        text=True,
    )
    return {found["code"] for found in json.loads(result.stdout)}


@pytest.mark.parametrize(
    ("source", "code"),
    [
        ("# x = compute(1)\n", "ERA001"),
        ("# FIXME later\n", "FIX001"),
        ("# TODO later\n", "FIX002"),
        ("# HACK around it\n", "FIX004"),
        ("# XXX\n", "FIX003"),
    ],
)
def test_commented_out_code_and_marker_comments_are_reported(tmp_path, source, code):
    assert code in rule_codes(tmp_path, source)


def test_an_ordinary_comment_is_left_to_the_rules_job(tmp_path):
    assert rule_codes(tmp_path, "# a constraint\nx = 1\n") == set()


def test_no_ignore_turns_a_comment_rule_off():
    lint = tomllib.loads(PYPROJECT.read_text())["tool"]["ruff"]["lint"]
    ignored = [*lint.get("ignore", []), *lint.get("extend-ignore", [])]
    for codes in [
        *lint.get("per-file-ignores", {}).values(),
        *lint.get("extend-per-file-ignores", {}).values(),
    ]:
        ignored += codes
    assert [c for c in CODES for i in ignored if c.startswith(i) or i == "ALL"] == []
