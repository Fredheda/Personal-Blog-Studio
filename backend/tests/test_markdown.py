import time

import pytest

from studio_api.markdown import MAX_BODY_BYTES, Problem, validate_body

GOOD = """# Title

Some *text*, a [link](https://example.com/a?b=1), an [anchor](#intro),
a [relative](../other-post) one and a <https://example.com/auto> autolink.

| a | b |
|---|---|
| 1 | 2 |

Inline maths $a<b>c$ and display maths:

$$
x < y > z
$$

```python
print("<script>alert(1)</script> [x](javascript:alert(1))")
```

![alt](media:01HZZZMEDIA)

::video{media="vid1" poster="pic1" loop muted autoplay caption="A caption"}
"""


def messages(markdown: str) -> list[str]:
    return [p.message for p in validate_body(markdown).problems]


def test_a_good_body_has_no_problems_and_lists_its_media_in_order() -> None:
    result = validate_body(GOOD)
    assert result.problems == []
    assert result.media_ids == ["01HZZZMEDIA", "vid1", "pic1"]


@pytest.mark.parametrize(
    "target",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "javascript&colon;alert(1)",
        "java%09script:alert(1)",
        "data:text/html;base64,AAAA",
        "http://example.com",
        "mailto:a@example.com",
        "//example.com/x",
        "vbscript:x",
        "file:///etc/passwd",
    ],
)
def test_a_link_target_outside_the_allowlist_is_a_problem(target: str) -> None:
    assert messages(f"[x]({target})")
    assert messages(f"[x][ref]\n\n[ref]: {target}")


def test_a_scheme_split_by_a_tab_never_becomes_a_link() -> None:
    # CommonMark refuses whitespace in a destination, so the parser leaves
    # plain text and there is no link target to judge.
    from studio_api.markdown import _parser

    for source in (
        "[x](java\tscript:alert(1))",
        "[x][ref]\n\n[ref]: java\tscript:alert(1)",
    ):
        types = [c.type for t in _parser().parse(source) for c in t.children or []]
        assert "link_open" not in types


@pytest.mark.parametrize(
    "target",
    ["javascript:alert(1)", "data:image/png;base64,AAAA", "http://x.test/a.png"],
)
def test_an_image_target_outside_the_allowlist_is_a_problem(target: str) -> None:
    assert messages(f"![x]({target})")


def test_raw_html_is_a_problem_block_and_inline() -> None:
    assert messages("<div>hi</div>")
    assert messages("text <b>bold</b> text")
    assert messages("<img src=x onerror=alert(1)>")
    assert messages("<!-- comment -->")


def test_html_looking_text_inside_code_or_maths_is_fine() -> None:
    assert messages("`<b>`") == []
    assert messages("$a<b>c$") == []
    assert messages("```\n<div>\n```") == []


def test_problems_carry_the_line_number() -> None:
    result = validate_body("fine\n\n[bad](javascript:x)\n\nalso fine")
    assert [p.line for p in result.problems] == [3]


@pytest.mark.parametrize(
    "line",
    [
        "::video{}",
        '::video{poster="p"}',
        '::video{media="bad id"}',
        '::video{media="v" onclick="x"}',
        '::video{media="v" loop="true"}',
        "::video{media}",
        '::video{media="v" caption="x}',
        '::audio{media="v"}',
        "::video",
    ],
)
def test_a_malformed_video_directive_is_a_problem(line: str) -> None:
    assert messages(line)


def test_a_link_or_html_inside_image_alt_text_is_checked_too() -> None:
    assert messages("![[a](javascript:x)](media:m1)")
    assert messages("![a <b>x</b>](media:m1)")


def test_a_repeated_video_attribute_is_a_problem() -> None:
    # A client that kept the first value would see an id nothing validated.
    assert messages('::video{media="a1" media="b2"}')
    assert messages('::video{media="a1" poster="p1" poster="p2"}')
    assert messages('::video{media="a1" loop loop}')


def test_a_pathological_video_directive_is_refused_quickly() -> None:
    # Exponential backtracking in the attribute pattern made this take minutes.
    start = time.monotonic()
    assert messages("::video{" + "a" * 5000 + "!}")
    assert time.monotonic() - start < 1.0


def test_the_media_ids_of_images_and_videos_are_checked() -> None:
    assert messages("![x](media:bad.id)")
    assert messages("![x](media:)")


def test_an_oversized_body_is_a_problem() -> None:
    assert messages("a" * (MAX_BODY_BYTES + 1))


HINT = "one formula per maths block"
# Synthetic copy of the owner's saved body. 1-based lines: 3-6 a code fence,
# 8 inline maths (fine), 10-12 a maths block holding a sentence with $...$,
# 16 and 23 a $$$ fence pair around two pasted $$ blocks.
PASTED = (
    "\n\n```Python\ndef f():\n  pass\n```\n\n"
    "Euler's identity $e^{i\\pi} + 1 = 0$ links five, and $\\sqrt{2} \\approx 1.414$\n\n"
    "$$\nEuler's identity $e^{i\\pi} + 1 = 0$ links five constants\n$$\n\n\n\n"
    "$$$\n$$\nx = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\n$$\n$$\n"
    "\\sum_{n=1}^{\\infty} \\frac{1}{n^2} = \\frac{\\pi^2}{6}\n$$\n$$$\n"
)


def test_pasted_maths_is_flagged_once_per_block_with_its_line() -> None:
    assert validate_body(PASTED).problems == [
        Problem(10, f"maths contains an unescaped $: {HINT}"),
        Problem(16, f"maths fence of three or more $ signs: {HINT}"),
    ]


def test_a_dollar_fence_inside_a_code_fence_is_code() -> None:
    assert validate_body("```\n$$$\n```\n").problems == []


def test_an_unpaired_dollar_fence_is_reported_once() -> None:
    assert validate_body("a\n\n$$$\n$$\nx\n$$\n").problems == [
        Problem(3, f"maths fence of three or more $ signs: {HINT}")
    ]


def test_inline_and_block_maths_with_a_structural_error_report_their_line() -> None:
    body = "ok $\\frac{1}{2$ here\n\n$$\n\\begin{cases} x\n$$\n"
    assert validate_body(body).problems == [
        Problem(1, f"maths does not parse (unbalanced braces): {HINT}"),
        Problem(3, f"maths does not parse (\\begin{{cases}} has no \\end): {HINT}"),
    ]


def test_one_formula_per_block_is_fine() -> None:
    body = "A $x^2$ and\n\n$$\nx = \\frac{1}{2}\n$$\n\n$$\ny = \\sqrt{2}\n$$\n"
    assert validate_body(body).problems == []
