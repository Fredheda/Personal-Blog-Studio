"""The publish-time check of a post body (spec section 4, "Post body format").

Rejects raw HTML and any link or image target outside the allowlist, so every
client can render the body without trusting this repo to have sanitised it.
Studio only: the read API image carries no Markdown parser.

Allowed targets: `https:` URLs, `#anchor`, relative links (no scheme), and
`media:<id>` for images and the `::video` directive. Everything else
(`javascript:`, `data:`, `http:`, `mailto:`, `//host`, ...) is a problem.
"""

import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.dollarmath import dollarmath_plugin

from blog_core.ids import is_media_id

# Parse time grows faster than linearly on adversarial input, so the cap stays
# well below what a long article needs (about 40 pages of text).
MAX_BODY_BYTES = 200_000
_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_ANCHOR = re.compile(r"^#[A-Za-z0-9_-]+$")
_VIDEO = re.compile(r"^::video\{(?P<attrs>.*)\}$")
# Possessive quantifiers (Python 3.11+): a plain nested `*` backtracks
# exponentially on `::video{aaaa...!}` and the body limit is 1 MB.
_ATTRS_OK = re.compile(r'^(?:\s*+\w++(?:="[^"\n]*+")?+)*+\s*+$')
_ATTR = re.compile(r'\s*(\w+)(?:="([^"\n]*)")?')
_VALUE_ATTRS = {"media", "poster", "caption"}
_FLAG_ATTRS = {"loop", "muted", "autoplay"}
_NOT_ALLOWED = "link target not allowed (https:, #anchor and relative links are)"


@dataclass(frozen=True)
class Problem:
    line: int  # 1-based; 0 when it concerns the whole body
    message: str


@dataclass
class Checked:
    problems: list[Problem] = field(default_factory=list)
    media_ids: list[str] = field(default_factory=list)  # first-use order, unique


def _parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"html": True}).enable("table")
    md.use(dollarmath_plugin)
    # markdown-it turns a link it dislikes (javascript:, data:) into plain text.
    # Accept every destination here so it is tokenised and judged below instead.
    md.validateLink = lambda url: True
    return md


def _link_problem(href: str) -> str | None:
    if not href:
        return "empty link target"
    if href.startswith("#"):
        return None if _ANCHOR.match(href) else "malformed #anchor"
    if _SCHEME.match(href):
        parts = urlsplit(href)
        return None if parts.scheme == "https" and parts.netloc else _NOT_ALLOWED
    if href.startswith("//") or "\\" in href:
        return _NOT_ALLOWED
    if ":" in href.split("/", 1)[0]:
        # RFC 3986 section 4.2: a relative path's first segment has no colon.
        # `java%09script:x` would otherwise pass as "relative" and a renderer
        # that decodes it first would see a scheme.
        return _NOT_ALLOWED
    return None  # a relative link


def _image_problem(src: str, found: list[str]) -> str | None:
    if src.startswith("media:"):
        media_id = src[len("media:") :]
        if not is_media_id(media_id):
            return "malformed media id"
        if media_id not in found:
            found.append(media_id)
        return None
    if src.startswith("#"):
        return "image target not allowed"
    return _link_problem(src)


def _directive_problems(content: str, found: list[str]) -> list[str]:
    match = _VIDEO.match(content)
    if not match:
        return ["unknown or malformed directive (only ::video{...} exists)"]
    attrs_text = match.group("attrs")
    if not _ATTRS_OK.match(attrs_text):
        return ["malformed ::video attributes"]
    pairs = [
        (m.group(1), m.group(2)) for m in _ATTR.finditer(attrs_text)
    ]  # None = bare
    names = [name for name, _ in pairs]
    if len(names) != len(set(names)):
        # A client that kept the first value would see an id nothing validated.
        return ["repeated ::video attribute"]
    attrs = dict(pairs)
    problems: list[str] = []
    for name, value in attrs.items():
        if name not in _VALUE_ATTRS | _FLAG_ATTRS:
            problems.append(f"unknown ::video attribute {name!r}")
        elif name in _FLAG_ATTRS and value is not None:
            problems.append(f"::video attribute {name!r} takes no value")
        elif name in _VALUE_ATTRS and value is None:
            problems.append(f"::video attribute {name!r} needs a value")
    if not attrs.get("media"):
        problems.append('::video needs media="<mediaId>"')
    for name in ("media", "poster"):
        value = attrs.get(name)
        if value:
            if not is_media_id(value):
                problems.append(f"::video {name} is not a media id")
            elif value not in found:
                found.append(value)
    return problems


def validate_body(markdown: str) -> Checked:
    """Check a body. `problems` is empty when it may be published."""
    result = Checked()
    if len(markdown.encode()) > MAX_BODY_BYTES:
        result.problems.append(
            Problem(0, f"body is larger than {MAX_BODY_BYTES} bytes")
        )
        return result
    tokens = _parser().parse(markdown)
    for index, token in enumerate(tokens):
        line = (token.map[0] + 1) if token.map else 0
        if token.type == "html_block":
            result.problems.append(Problem(line, "raw HTML is not allowed"))
        elif token.type == "inline":
            _check_inline(token, tokens[index - 1] if index else None, line, result)
    return result


def _check_inline(
    inline: Token, previous: Token | None, line: int, result: Checked
) -> None:
    if (
        previous is not None
        and previous.type == "paragraph_open"
        and inline.content.lstrip().startswith("::")
    ):
        for message in _directive_problems(inline.content.strip(), result.media_ids):
            result.problems.append(Problem(line, message))
        return
    _check_children(inline.children or [], line, result)


def _check_children(children: list[Token], line: int, result: Checked) -> None:
    for child in children:
        message = None
        if child.type == "html_inline":
            message = "raw HTML is not allowed"
        elif child.type == "link_open":
            message = _link_problem(str(child.attrGet("href") or ""))
        elif child.type == "image":
            message = _image_problem(str(child.attrGet("src") or ""), result.media_ids)
            # The alt text is parsed too: a link or HTML inside it counts.
            _check_children(child.children or [], line, result)
        if message:
            result.problems.append(Problem(line, message))
