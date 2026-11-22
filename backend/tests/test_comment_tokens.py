import comment_hash
import comment_python
import comment_ts
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


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("const a = 1; // note\n", 1),
        ("// a\n// b\n", 2),
        ("/* one\n two */\nconst a = 1;\n", 2),
        ("const x = <div>{/* jsx */}</div>;\n", 1),
        ("const u = \"https://x.y\"; const v = 'a // b';\n", 0),
        ("const t = `a // b ${x /* c */} d`;\n", 1),
        ("const t = `a ${`b // c`} d`;\n", 0),
        ("const r = /\\/\\/ x/;\n", 0),
        ("const q = b / 2 / 3; // c\n", 1),
        ("function f(s) { return /x/.test(s); } // c\n", 1),
        ("const q = (a) / 2; // c\n", 1),
        ("const p = <p>Don't // no</p>;\n// real\n", 1),
        ("const a = <a>x</a>; // c\n", 1),
        ("const a = <a>x</a>{/* c */};\n", 1),
        ("const a = <b>{/* c */}</b>;\nconst d = <i/>; // d\n", 2),
        ("// eslint-disable-next-line no-console\n", 0),
        ("// we use eslint-disable here\n", 1),
        ("/* istanbul ignore next */\n", 0),
        ("// @ts-expect-error reason\n", 0),
        ('/// <reference types="x" />\n', 0),
        ("#!/usr/bin/env node\n// a\n", 1),
        ("/* // */\n", 1),
        ("// plain\n// eslint-disable-line\n", 1),
        ("/**\n * Header narrative.\n * More.\n */\nexport {};\n", 4),
    ],
)
def test_ts_counts(source, expected):
    assert comment_ts.count(source) == expected
