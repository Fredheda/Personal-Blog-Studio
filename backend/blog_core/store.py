"""The blob storage the blog code talks to, as a small interface.

Two implementations: `AzureBlobStore` (production, Azurite locally) and the
in-memory fake used by the unit tests. Both obey the same contract
(`tests/test_store_contract.py` runs against each).
"""

from dataclasses import dataclass
from typing import Protocol


class StoreError(Exception):
    """Base class for storage errors the blog code handles."""


class PreconditionFailed(StoreError):
    """A conditional write did not hold: the blob changed, or it exists, or it is missing."""


@dataclass(frozen=True)
class Blob:
    content: bytes
    etag: str


class BlobStore(Protocol):
    def read(self, container: str, path: str) -> Blob | None:
        """The blob, or None when it does not exist."""
        ...

    def write(
        self,
        container: str,
        path: str,
        content: bytes,
        *,
        content_type: str = "application/octet-stream",
        if_match: str | None = None,
        create_only: bool = False,
    ) -> str:
        """Write the blob and return its new ETag.

        `if_match`: write only when the blob exists with this ETag.
        `create_only`: write only when the blob does not exist.
        Both unset: overwrite. Raises PreconditionFailed when a condition fails.
        """
        ...

    def delete(self, container: str, path: str) -> None:
        """Delete the blob; a missing blob is not an error."""
        ...

    def list(self, container: str, prefix: str) -> list[str]:
        """Names of the blobs whose name starts with `prefix`, sorted."""
        ...

    def copy(self, src_container: str, src_path: str, dst_container: str, dst_path: str) -> None:
        """Server-side copy inside the account. Overwrites the destination."""
        ...
