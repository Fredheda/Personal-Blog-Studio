"""Errors of the post service. The routes ticket maps each to an HTTP status."""

from studio_api.markdown import Problem


class PostError(Exception):
    """Base class."""


class PostNotFound(PostError):
    """No such post, or no such revision."""


class Conflict(PostError):
    """A shared document was busy or the slug raced. Reload and retry."""


class StaleEtag(Conflict):
    """The caller's If-Match no longer matches (HTTP 412). Reload the draft."""


class ValidationFailed(PostError):
    def __init__(self, problems: list[Problem]) -> None:
        super().__init__("; ".join(p.message for p in problems))
        self.problems = problems


class SlugLocked(PostError):
    """The slug is fixed once a post has been published."""


class SlugTaken(PostError):
    """Another published post owns this slug."""


class StillPublished(PostError):
    """Unpublish before deleting."""


class MissingMedia(PostError):
    def __init__(self, media_ids: list[str]) -> None:
        super().__init__(f"media not found: {', '.join(media_ids)}")
        self.media_ids = media_ids
