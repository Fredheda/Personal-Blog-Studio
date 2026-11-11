"""Where everything lives in the two containers (spec section 4).

Pure functions from ids to blob paths. Each checks its ids with
`blog_core.ids`, so no caller can build a path outside the intended folder.
"""

from blog_core import ids

DRAFTS = "blog-drafts"
PUBLISHED = "blog-published"
INDEX = "index.json"


def _post(post_id: str) -> str:
    if not ids.is_post_id(post_id):
        raise ValueError(f"not a post id: {post_id!r}")
    return post_id


def _media(media_id: str) -> str:
    if not ids.is_media_id(media_id):
        raise ValueError(f"not a media id: {media_id!r}")
    return media_id


def _ext(ext: str) -> str:
    if not ids.is_extension(ext):
        raise ValueError(f"not a file extension: {ext!r}")
    return ext


def _revision(revision: str) -> str:
    if not revision.isascii() or not revision.isalnum():
        raise ValueError(f"not a revision id: {revision!r}")
    return revision


# blog-drafts ------------------------------------------------------------------


def post_folder(post_id: str) -> str:
    return f"posts/{_post(post_id)}/"


def draft_body(post_id: str) -> str:
    return f"posts/{_post(post_id)}/draft.md"


def draft_meta(post_id: str) -> str:
    return f"posts/{_post(post_id)}/draft.json"


def revision_prefix(post_id: str) -> str:
    return f"posts/{_post(post_id)}/rev/"


def revision_body(post_id: str, revision: str) -> str:
    return f"posts/{_post(post_id)}/rev/{_revision(revision)}.md"


def media_original(media_id: str, ext: str) -> str:
    return f"media/{_media(media_id)}/original.{_ext(ext)}"


def media_meta(media_id: str) -> str:
    return f"media/{_media(media_id)}/meta.json"


# blog-published ---------------------------------------------------------------


def slug_ref(slug: str) -> str:
    if not ids.is_slug(slug):
        raise ValueError(f"not a slug: {slug!r}")
    return f"slugs/{slug}.json"


def versions_prefix(post_id: str) -> str:
    return f"posts/{_post(post_id)}/"


def _version(post_id: str, version: int) -> str:
    if type(version) is not int or version < 1:  # bool and float are not versions
        raise ValueError(f"not a version: {version!r}")
    return f"posts/{_post(post_id)}/v{version}"


def version_body(post_id: str, version: int) -> str:
    return f"{_version(post_id, version)}/post.md"


def version_meta(post_id: str, version: int) -> str:
    return f"{_version(post_id, version)}/meta.json"


def version_media(post_id: str, version: int, media_id: str, ext: str) -> str:
    return f"{_version(post_id, version)}/media/{_media(media_id)}.{_ext(ext)}"
