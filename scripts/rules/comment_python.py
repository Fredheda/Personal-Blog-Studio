import ast
import io
import re
import tokenize

import comment_model
import directives
from comment_model import Comment

SCOPES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def name_words(name: str) -> set[str]:
    found = re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+", name)
    return {word.lower() for word in found}


def owner_words(node: ast.AST) -> frozenset[str] | None:
    if isinstance(node, ast.Module):
        return None
    words = name_words(getattr(node, "name", ""))
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        arguments = node.args
        every = [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
            *filter(None, [arguments.vararg, arguments.kwarg]),
        ]
        for argument in every:
            words |= name_words(argument.arg)
    return frozenset(words)


def comments(source: str) -> list[Comment]:
    found: list[Comment] = []
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                line = token.start[0]
                found.append(
                    Comment(
                        line,
                        line,
                        token.string,
                        directives.is_directive(token.string, "python"),
                    )
                )
        tree = ast.parse(source)
    except (SyntaxError, tokenize.TokenError) as error:
        raise ValueError(f"cannot read comments: {error}") from error
    for node in ast.walk(tree):
        if isinstance(node, SCOPES):
            text = ast.get_docstring(node, clean=False)
            if text:
                first = node.body[0]
                end = first.end_lineno or first.lineno
                found.append(Comment(first.lineno, end, text, False, owner_words(node)))
    return found


def count(source: str) -> int:
    return len(comment_model.lines(comments(source)))
