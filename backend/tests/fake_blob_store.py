"""In-memory BlobStore for unit tests. Same contract as the Azure store."""

from itertools import count

from blog_core.store import Blob, PreconditionFailed, StoreError


class InMemoryBlobStore:
    def __init__(self) -> None:
        self._blobs: dict[tuple[str, str], Blob] = {}
        self._etags = count(1)
        self.writes: list[tuple[str, str]] = []  # (container, path) in order

    def read(self, container: str, path: str) -> Blob | None:
        return self._blobs.get((container, path))

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
        current = self._blobs.get((container, path))
        if create_only and current is not None:
            raise PreconditionFailed(f"{container}/{path}")
        if if_match is not None and (current is None or current.etag != if_match):
            raise PreconditionFailed(f"{container}/{path}")
        etag = f'"0x{next(self._etags):016X}"'
        self._blobs[(container, path)] = Blob(content, etag)
        self.writes.append((container, path))
        return etag

    def delete(self, container: str, path: str) -> None:
        self._blobs.pop((container, path), None)

    def list(self, container: str, prefix: str) -> list[str]:
        return sorted(p for c, p in self._blobs if c == container and p.startswith(prefix))

    def copy(self, src_container: str, src_path: str, dst_container: str, dst_path: str) -> None:
        source = self._blobs.get((src_container, src_path))
        if source is None:
            raise StoreError(f"copy source missing: {src_container}/{src_path}")
        self.write(dst_container, dst_path, source.content)
