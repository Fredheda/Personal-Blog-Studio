from datetime import UTC, datetime, timedelta


class Clock:
    """A service clock that advances one second on every call."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 10, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=1)
        return self.now
