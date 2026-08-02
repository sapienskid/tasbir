"""Datetime serialization helpers — UTC-aware ISO output for the API."""

from __future__ import annotations

from datetime import datetime, timezone


def iso_utc(dt: datetime | None) -> str | None:
    """Serialize a datetime as UTC ISO with an explicit offset.

    SQLite drops the timezone on storage, so values read back are naive.
    Treat naive values as UTC and always emit an offset so clients can
    convert to their local timezone.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
