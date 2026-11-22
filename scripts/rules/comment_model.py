from typing import NamedTuple


class Comment(NamedTuple):
    line: int
    end: int
    text: str
    directive: bool = False
    owner: frozenset[str] | None = None
    own_line: bool = True


def lines(
    found: list[Comment], directive: bool = False, own_line: bool = False
) -> set[int]:
    return {
        number
        for comment in found
        if comment.directive == directive and (comment.own_line or not own_line)
        for number in range(comment.line, comment.end + 1)
    }
