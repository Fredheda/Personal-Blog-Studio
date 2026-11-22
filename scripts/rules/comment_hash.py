import comment_model
import directives
from comment_model import Comment


def comments(source: str) -> list[Comment]:
    return [
        Comment(number, number, line.strip(), directives.is_directive(line, "hash"))
        for number, line in enumerate(source.splitlines(), 1)
        if line.lstrip().startswith("#")
    ]


def count(source: str) -> int:
    return len(comment_model.lines(comments(source)))
