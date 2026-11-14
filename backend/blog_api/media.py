"""Short-lived read links to published media.

A user-delegation SAS is signed with a key obtained through the app's managed
identity (Storage Blob Delegator on the account); no account key exists. Each
link is read-only, https-only, valid 10 minutes and scoped to one blob.
"""

import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from urllib.parse import quote

from azure.identity import DefaultAzureCredential
from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    UserDelegationKey,
    generate_blob_sas,
)

from blog_api.schemas import MediaLink
from blog_core.models import now_iso

SAS_TTL = timedelta(minutes=10)
KEY_LIFETIME = timedelta(hours=1)
KEY_REFRESH_MARGIN = timedelta(minutes=15)
KEY_CLOCK_SKEW = timedelta(minutes=5)


class MediaLinker(Protocol):
    def link(
        self, container: str, path: str, *, content_type: str, size: int
    ) -> MediaLink: ...


class AzureMediaLinker:
    def __init__(
        self,
        service: BlobServiceClient,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._service = service
        self._clock = clock
        self._lock = threading.Lock()
        self._key: UserDelegationKey | None = None
        self._key_until = datetime.min.replace(tzinfo=UTC)

    @classmethod
    def from_account(
        cls, account_url: str, *, managed_identity_client_id: str | None = None
    ) -> "AzureMediaLinker":
        credential = DefaultAzureCredential(
            managed_identity_client_id=managed_identity_client_id
        )
        return cls(BlobServiceClient(account_url, credential=credential))

    def _delegation_key(self, now: datetime) -> UserDelegationKey:
        with self._lock:
            if self._key is None or now >= self._key_until:
                self._key = self._service.get_user_delegation_key(
                    now - KEY_CLOCK_SKEW, now + KEY_LIFETIME
                )
                self._key_until = now + KEY_LIFETIME - KEY_REFRESH_MARGIN
            return self._key

    def link(
        self, container: str, path: str, *, content_type: str, size: int
    ) -> MediaLink:
        now = self._clock()
        expires = now + SAS_TTL
        token = generate_blob_sas(
            account_name=self._service.account_name or "",
            container_name=container,
            blob_name=path,
            user_delegation_key=self._delegation_key(now),
            permission=BlobSasPermissions(read=True),
            expiry=expires,
            protocol="https",
            content_type=content_type,
        )
        url = f"{self._service.url.rstrip('/')}/{container}/{quote(path, safe='/')}?{token}"
        return MediaLink(
            url=url, expires_at=now_iso(expires), content_type=content_type, bytes=size
        )
