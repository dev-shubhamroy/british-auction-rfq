from datetime import datetime, timezone


def utc_now() -> datetime:
    # All backend code reads time through here so tests can patch it.
    return datetime.now(timezone.utc)
