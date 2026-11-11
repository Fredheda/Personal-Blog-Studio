"""Identifier rules shared by the studio and the read API.

Every id or name that ends up in a blob path is checked here first, so a path
can never be built from user input that escapes its folder.
"""

import re

from ulid import ULID

SLUG_MAX_LENGTH = 100
_POST_ID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_MEDIA_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_EXT = re.compile(r"^[a-z0-9]{1,8}$")
_TAG = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


def new_id() -> str:
    """A new ULID: sortable by creation time, not guessable."""
    return str(ULID())


def is_post_id(value: str) -> bool:
    return bool(_POST_ID.fullmatch(value))


def is_media_id(value: str) -> bool:
    return bool(_MEDIA_ID.fullmatch(value))


def is_slug(value: str) -> bool:
    return len(value) <= SLUG_MAX_LENGTH and bool(_SLUG.fullmatch(value))


def is_extension(value: str) -> bool:
    return bool(_EXT.fullmatch(value))


def is_tag(value: str) -> bool:
    return bool(_TAG.fullmatch(value))
