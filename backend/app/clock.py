from datetime import datetime, timezone


def utc_now() -> datetime:
    """Single source of 'now' for the backend. Tests patch this to control time."""
    return datetime.now(timezone.utc)
