"""Cheap, deterministic checks of one formula's source (BLOG-44).

Not KaTeX: it catches what a paste into a maths block produces (a `$` inside
the formula) and the structural errors that make a formula unrenderable.
"""

import re

HINT = "one formula per maths block"
_TEXT_GROUP = re.compile(r"\\(?:text|textbf|textit|textrm|mbox|hbox)\{")
_ENV = re.compile(r"\\(begin|end)\{([A-Za-z]+\*?)\}")
_DOLLAR = re.compile(r"(?<!\\)\$")
_LEFT = re.compile(r"\\left(?![A-Za-z])")
_RIGHT = re.compile(r"\\right(?![A-Za-z])")


def _without_text_groups(source: str) -> str:
    """Drop the contents of \\text{...} and its siblings: a `$` there is legal."""
    kept: list[str] = []
    position = 0
    while match := _TEXT_GROUP.search(source, position):
        kept.append(source[position : match.start()])
        depth, index = 1, match.end()
        while index < len(source) and depth:
            char = source[index]
            if char == "\\":
                index += 2
                continue
            depth += (char == "{") - (char == "}")
            index += 1
        position = index
    kept.append(source[position:])
    return "".join(kept)


def _structure_problem(source: str) -> str | None:
    depth, index = 0, 0
    while index < len(source):
        char = source[index]
        if char == "\\":
            index += 2
            continue
        depth += (char == "{") - (char == "}")
        if depth < 0:
            return "unbalanced braces"
        index += 1
    if depth:
        return "unbalanced braces"
    open_names: list[str] = []
    for match in _ENV.finditer(source):
        kind, name = match.groups()
        if kind == "begin":
            open_names.append(name)
        elif not open_names or open_names.pop() != name:
            return f"\\end{{{name}}} does not match a \\begin"
    if open_names:
        return f"\\begin{{{open_names[-1]}}} has no \\end"
    if len(_LEFT.findall(source)) != len(_RIGHT.findall(source)):
        return "\\left and \\right do not pair"
    return None


def maths_problem(source: str) -> str | None:
    """The message for a formula that cannot be rendered, or None."""
    if _DOLLAR.search(_without_text_groups(source)):
        return f"maths contains an unescaped $: {HINT}"
    reason = _structure_problem(source)
    return f"maths does not parse ({reason}): {HINT}" if reason else None
