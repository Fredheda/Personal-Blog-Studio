from typing import NamedTuple


class Comment(NamedTuple):
    line: int
    end: int
    text: str
    directive: bool = False
    owner: frozenset[str] | None = None


def lines(found: list[Comment], directive: bool = False) -> set[int]:
    return {
        number
        for comment in found
        if comment.directive == directive
        for number in range(comment.line, comment.end + 1)
    }
