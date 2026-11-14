import base64
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

from azure.storage.blob import UserDelegationKey

from blog_api.media import SAS_TTL, AzureMediaLinker


class FakeService:
    account_name = "acct"
    url = "https://acct.blob.core.windows.net"

    def __init__(self) -> None:
        self.key_requests: list[tuple[datetime, datetime]] = []

    def get_user_delegation_key(
        self, start: datetime, expiry: datetime
    ) -> UserDelegationKey:
        self.key_requests.append((start, expiry))
        key = UserDelegationKey()
        key.signed_oid = "00000000-0000-0000-0000-000000000001"
        key.signed_tid = "00000000-0000-0000-0000-000000000002"
        key.signed_start = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        key.signed_expiry = expiry.strftime("%Y-%m-%dT%H:%M:%SZ")
        key.signed_service = "b"
        key.signed_version = "2025-01-05"
        key.value = base64.b64encode(b"k" * 32).decode()
        return key


class Moving:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


def test_the_link_is_a_read_only_https_ten_minute_sas_for_one_blob() -> None:
    clock = Moving()
    linker = AzureMediaLinker(FakeService(), clock=clock)  # type: ignore[arg-type]
    link = linker.link(
        "blog-published", "posts/P/v1/media/m1.png", content_type="image/png", size=3
    )
    parts = urlsplit(link.url)
    query = parse_qs(parts.query)
    assert parts.scheme == "https"
    assert parts.path == "/blog-published/posts/P/v1/media/m1.png"
    assert query["sp"] == ["r"] and query["spr"] == ["https"] and query["sr"] == ["b"]
    assert query["rsct"] == ["image/png"]
    expected = clock.now + SAS_TTL
    assert SAS_TTL == timedelta(minutes=10)
    assert link.expires_at == expected.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert query["se"] == [expected.strftime("%Y-%m-%dT%H:%M:%SZ")]
    assert (link.content_type, link.bytes) == ("image/png", 3)


def test_the_delegation_key_is_cached_and_refreshed_before_it_runs_out() -> None:
    service, clock = FakeService(), Moving()
    linker = AzureMediaLinker(service, clock=clock)  # type: ignore[arg-type]
    for _ in range(3):
        linker.link("c", "p", content_type="x/y", size=1)
    assert len(service.key_requests) == 1
    clock.now += timedelta(minutes=50)
    linker.link("c", "p", content_type="x/y", size=1)
    assert len(service.key_requests) == 2
