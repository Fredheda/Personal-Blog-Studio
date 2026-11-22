import comment_hash
import comment_python
import pytest


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x = 1  # note\n", 1),
        ("# a\n# b\n", 2),
        ('x = "# not"\n', 0),
        ('def f():\n    """one\n    two"""\n    return 1\n', 2),
        ('"""doc"""\nx = 1\n', 1),
        ('x = 1\n"""not a docstring"""\n', 0),
        ("import os  # noqa: F401\n", 0),
        ("#!/usr/bin/env python3\nx = 1\n", 0),
        ("x = f()  # type: ignore\n", 0),
        ("# -*- coding: utf-8 -*-\nx = 1\n", 0),
        ("# fmt: off\nx = 1\n# fmt: on\n", 0),
        ("# plain\nimport os  # noqa\n", 1),
        ("# ruff is strict here\n", 1),
        ("# ruff: noqa\n", 0),
        ("# we use noqa here\n", 1),
        ("# pragma: no cover\n", 0),
    ],
)
def test_python_counts(source, expected):
    assert comment_python.count(source) == expected


def test_python_unreadable_source_raises():
    with pytest.raises(ValueError, match="cannot read comments"):
        comment_python.count("def (:\n")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("# a\n# b\n", 2),
        ("  # indented\nkey: value\n", 1),
        ("key: value  # trailing\n", 0),
        ("#!/usr/bin/env bash\nset -e\n", 0),
        ("# shellcheck disable=SC2086\n", 0),
        ("# syntax=docker/dockerfile:1\nFROM x\n", 0),
        ("# yaml-language-server: $schema=x\n", 0),
        ("# shellcheck is strict here\n", 1),
        ("[tool]\n# note\nname = 1\n", 1),
    ],
)
def test_hash_counts(source, expected):
    assert comment_hash.count(source) == expected
