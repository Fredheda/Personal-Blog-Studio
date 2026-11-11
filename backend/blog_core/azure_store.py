"""BlobStore over Azure Blob Storage (or Azurite).

Production authenticates with the app's managed identity (no key, no
connection string); the connection-string constructor exists for Azurite.
"""

import time

from azure.core import MatchConditions
from azure.core.exceptions import (
    HttpResponseError,
    ResourceExistsError,
    ResourceModifiedError,
    ResourceNotFoundError,
)
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobClient, BlobServiceClient, ContentSettings

from blog_core.store import Blob, PreconditionFailed, StoreError

COPY_TIMEOUT_SECONDS = 120


class AzureBlobStore:
    def __init__(self, service: BlobServiceClient) -> None:
        self.service = service

    @classmethod
    def from_account(
        cls, account_url: str, *, managed_identity_client_id: str | None = None
    ) -> "AzureBlobStore":
        credential = DefaultAzureCredential(
            managed_identity_client_id=managed_identity_client_id
        )
        return cls(BlobServiceClient(account_url, credential=credential))

    @classmethod
    def from_connection_string(cls, connection_string: str) -> "AzureBlobStore":
        return cls(BlobServiceClient.from_connection_string(connection_string))

    def _blob(self, container: str, path: str) -> BlobClient:
        return self.service.get_blob_client(container, path)

    def read(self, container: str, path: str) -> Blob | None:
        try:
            downloader = self._blob(container, path).download_blob()
            return Blob(downloader.readall(), downloader.properties.etag)
        except ResourceNotFoundError:
            return None

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
        settings = ContentSettings(content_type=content_type)
        blob = self._blob(container, path)
        try:
            if create_only:
                result = blob.upload_blob(
                    content, overwrite=False, content_settings=settings
                )
            elif if_match is not None:
                result = blob.upload_blob(
                    content,
                    overwrite=True,
                    content_settings=settings,
                    etag=if_match,
                    match_condition=MatchConditions.IfNotModified,
                )
            else:
                result = blob.upload_blob(
                    content, overwrite=True, content_settings=settings
                )
        except (ResourceExistsError, ResourceModifiedError, ResourceNotFoundError) as e:
            raise PreconditionFailed(f"{container}/{path}") from e
        except HttpResponseError as e:
            if e.status_code in (409, 412):
                raise PreconditionFailed(f"{container}/{path}") from e
            raise
        return result["etag"]

    def delete(self, container: str, path: str) -> None:
        try:
            self._blob(container, path).delete_blob()
        except ResourceNotFoundError:
            pass

    def list(self, container: str, prefix: str) -> list[str]:
        client = self.service.get_container_client(container)
        return sorted(b.name for b in client.list_blobs(name_starts_with=prefix))

    def copy(
        self, src_container: str, src_path: str, dst_container: str, dst_path: str
    ) -> None:
        source = self._blob(src_container, src_path)
        target = self._blob(dst_container, dst_path)
        label = f"copy {src_container}/{src_path} -> {dst_container}/{dst_path}"
        try:
            target.start_copy_from_url(source.url)
        except ResourceNotFoundError as e:
            raise StoreError(f"{label}: source missing") from e
        except HttpResponseError as e:
            if e.status_code == 404:
                raise StoreError(f"{label}: source missing") from e
            raise
        deadline = time.monotonic() + COPY_TIMEOUT_SECONDS
        while True:
            status = target.get_blob_properties().copy.status
            if status == "success":
                return
            if status != "pending" or time.monotonic() > deadline:
                raise StoreError(f"{label}: {status}")
            time.sleep(0.2)
