import pytest

from studio_api.maths import HINT, maths_problem

OWNER_FORMULAS = [
    r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
    r"\sum_{n=1}^{\infty} \frac{1}{n^2} = \frac{\pi^2}{6}",
    r"\int_{-\infty}^{\infty} e^{-x^2}\,dx = \sqrt{\pi}",
    r"A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}, \quad \det A = -2",
    r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}",
    r"f(x) = \begin{cases} x^2 & x \ge 0 \\ -x & x < 0 \end{cases}",
]


@pytest.mark.parametrize("source", OWNER_FORMULAS)
def test_a_renderable_formula_has_no_problem(source: str) -> None:
    assert maths_problem(source) is None


@pytest.mark.parametrize(
    "source",
    [
        r"a < b > c",
        r"\text{costs $5$ today}",
        r"\mbox{a $x$ b}",
        r"\$5 + \$6",
        r"\leftarrow x \rightarrow y",
        r"\left( \frac{1}{2} \right)",
        r"\begin{aligned} a &= b \\ c &= d \end{aligned}",
        r"\{ x \}",
    ],
)
def test_legal_uses_are_not_flagged(source: str) -> None:
    assert maths_problem(source) is None


def test_an_unescaped_dollar_is_flagged_with_the_hint() -> None:
    message = maths_problem("Euler's identity $e^{i\\pi} + 1 = 0$ links five constants")
    assert message == f"maths contains an unescaped $: {HINT}"


def test_a_pasted_dollar_block_is_flagged() -> None:
    message = maths_problem("$$\nx = 1\n$$\n$$\ny = 2\n$$")
    assert message == f"maths contains an unescaped $: {HINT}"


@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (r"\frac{1}{2", "unbalanced braces"),
        (r"x}", "unbalanced braces"),
        (r"\begin{cases} x", r"\begin{cases} has no \end"),
        (r"x \end{cases}", r"\end{cases} does not match a \begin"),
        (r"\begin{cases} x \end{matrix}", r"\end{matrix} does not match a \begin"),
        (r"\left( x", r"\left and \right do not pair"),
    ],
)
def test_structural_errors_are_flagged_with_their_reason(
    source: str, reason: str
) -> None:
    assert maths_problem(source) == f"maths does not parse ({reason}): {HINT}"
