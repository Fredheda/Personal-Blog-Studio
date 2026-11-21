"""Seed the DEV containers with three test posts, through a running local studio API.

Run from `backend/` with the local env file loaded:

    set -a && . ../.env.local && set +a && poetry run python -m dev_support.seed

It writes through the studio API (so the product's own rules apply) and only
after two checks: the container names end in `-dev`, and the posts the API
lists are exactly the posts in the dev drafts container (read directly with the
same login). The second check tests the server's real target, not this
script's environment: a server pointed at the production containers lists
different posts, and nothing is written. Copied by no Dockerfile.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, NamedTuple, Protocol

from blog_core import layout
from blog_core.azure_store import AzureBlobStore
from blog_core.store import BlobStore

LOOPBACK_URL = re.compile(r"http://127\.0\.0\.1:\d{1,5}/?")


class SeedRefused(Exception):
    """The seed would not be safe; nothing was written."""


class StudioError(Exception):
    """The studio API answered with an error."""


class Studio(Protocol):
    def call(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        """The parsed JSON answer, or None for no content. Raises StudioError."""
        ...


class HttpStudio:
    """The studio API over HTTP, always with the same-origin header."""

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def call(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(
            f"{self._base}{path}",
            data=data,
            method=method,
            headers={
                "X-Blog-Studio": "1",
                "Content-Type": "application/json",
                **(headers or {}),
            },
        )
        try:
            # The base URL is checked to be loopback http in main().
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
        except urllib.error.HTTPError as error:
            raise StudioError(f"{method} {path}: HTTP {error.code}") from error
        return json.loads(raw) if raw else None


class Seed(NamedTuple):
    title: str
    slug: str | None
    summary: str
    body: str
    then_unpublish: bool


SEEDS = (
    Seed("Seed draft", None, "", "", False),
    Seed("Seed published", "seed-published", "A published post.", "Hello.\n", False),
    Seed(
        "Seed unpublished",
        "seed-unpublished",
        "Published once, a draft now.",
        "Hello again.\n",
        True,
    ),
)


def draft_ids(store: BlobStore) -> set[str]:
    """Post ids in the drafts container, read directly."""
    return {
        name.split("/")[1]
        for name in store.list(layout.DRAFTS, "posts/")
        if name.endswith("/draft.json")
    }


def seed(studio: Studio, store: BlobStore) -> list[str]:
    """Create the missing seed posts; the titles created. Raises SeedRefused first."""
    if not (layout.DRAFTS.endswith("-dev") and layout.PUBLISHED.endswith("-dev")):
        raise SeedRefused(
            "the container names must end in -dev "
            f"(got {layout.DRAFTS} and {layout.PUBLISHED})"
        )
    listed = studio.call("GET", "/posts")["items"]
    if {item["postId"] for item in listed} != draft_ids(store):
        raise SeedRefused(
            "the posts the studio API lists differ from the dev drafts container: "
            "the API points at another store"
        )
    have = {item["title"] for item in listed}
    created: list[str] = []
    for item in SEEDS:
        if item.title in have:
            continue
        post = studio.call("POST", "/posts", body={"title": item.title})
        created.append(item.title)
        if item.slug is None:
            continue
        post_id = post["postId"]
        studio.call(
            "PATCH",
            f"/posts/{post_id}/meta",
            headers={"If-Match": post["metaEtag"]},
            body={"slug": item.slug, "summary": item.summary},
        )
        saved = studio.call(
            "PUT",
            f"/posts/{post_id}/body",
            headers={"If-Match": post["bodyEtag"]},
            body={"body": item.body},
        )
        studio.call(
            "POST",
            f"/posts/{post_id}/publish",
            headers={"If-Match": saved["bodyEtag"]},
        )
        if item.then_unpublish:
            studio.call("POST", f"/posts/{post_id}/unpublish")
    return created


def main() -> int:
    url = os.environ.get("STUDIO_API_URL", "")
    if not LOOPBACK_URL.fullmatch(url):
        print("seed: STUDIO_API_URL must be http://127.0.0.1:<port>", file=sys.stderr)
        return 2
    account = os.environ.get("BLOG_STORAGE_ACCOUNT_URL")
    if not account:
        print("seed: BLOG_STORAGE_ACCOUNT_URL is not set", file=sys.stderr)
        return 2
    try:
        created = seed(HttpStudio(url), AzureBlobStore.from_account(account))
    except (SeedRefused, StudioError) as error:
        print(f"seed: {error}", file=sys.stderr)
        return 1
    done = ", ".join(created) if created else "nothing (already seeded)"
    print(f"seed: created {done}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
