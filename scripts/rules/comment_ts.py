import comment_model
import directives
from comment_model import Comment

REGEX_KEYWORDS = {
    "return",
    "typeof",
    "case",
    "of",
    "in",
    "delete",
    "void",
    "throw",
    "yield",
    "await",
    "else",
    "do",
    "new",
}
DIVISION_BEFORE = set(")]}\"'`<")


def is_word_char(char: str) -> bool:
    return char.isalnum() or char in "_$"


def skip_quoted(source: str, start: int) -> int:
    quote = source[start]
    i = start + 1
    while i < len(source) and source[i] != "\n":
        if source[i] == "\\":
            i += 2
            continue
        if source[i] == quote:
            return i + 1
        i += 1
    return i


def skip_regex(source: str, start: int) -> int | None:
    i = start + 1
    in_class = False
    while i < len(source) and source[i] != "\n":
        char = source[i]
        if char == "\\":
            i += 2
            continue
        if char == "[":
            in_class = True
        elif char == "]":
            in_class = False
        elif char == "/" and not in_class:
            return i + 1
        i += 1
    return None


def count(source: str) -> int:
    return len(comment_model.lines(comments(source)))


def comments(source: str) -> list[Comment]:
    found: list[Comment] = []
    line = 1
    i = 0
    if source.startswith("#!"):
        i = source.find("\n") if "\n" in source else len(source)
        found.append(Comment(1, 1, source[:i], True))
    depth = 0
    interpolations: list[int] = []
    previous = ""
    previous_word = ""
    in_template = False

    def record(text: str, first_line: int, start: int) -> None:
        end = first_line + text.count("\n")
        before = source[source.rfind("\n", 0, start) + 1 : start]
        found.append(
            Comment(
                first_line,
                end,
                text,
                directives.is_directive(text, "ts"),
                own_line=not before.strip(),
            )
        )

    while i < len(source):
        char = source[i]
        if in_template:
            if char == "\\":
                line += source[i : i + 2].count("\n")
                i += 2
            elif char == "`":
                in_template = False
                previous = "`"
                i += 1
            elif source.startswith("${", i):
                interpolations.append(depth)
                depth += 1
                in_template = False
                previous = "{"
                i += 2
            else:
                line += char == "\n"
                i += 1
            continue
        if char == "\n":
            line += 1
            i += 1
        elif char.isspace():
            i += 1
        elif source.startswith("//", i):
            end = source.find("\n", i)
            end = len(source) if end == -1 else end
            record(source[i:end], line, i)
            i = end
        elif source.startswith("/*", i):
            end = source.find("*/", i + 2)
            end = len(source) if end == -1 else end + 2
            record(source[i:end], line, i)
            line += source.count("\n", i, end)
            i = end
        elif char in "'\"":
            i = skip_quoted(source, i)
            previous = char
        elif char == "`":
            in_template = True
            i += 1
        elif char == "/":
            if previous == "w":
                regex_allowed = previous_word in REGEX_KEYWORDS
            else:
                regex_allowed = previous not in DIVISION_BEFORE
            end = skip_regex(source, i) if regex_allowed else None
            if end is None:
                previous = "/"
                i += 1
            else:
                previous = "w"
                previous_word = ""
                i = end
        elif is_word_char(char):
            start = i
            while i < len(source) and is_word_char(source[i]):
                i += 1
            previous = "w"
            previous_word = source[start:i]
        else:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if interpolations and depth == interpolations[-1]:
                    interpolations.pop()
                    in_template = True
            previous = char
            i += 1
    return found
