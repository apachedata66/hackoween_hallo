"""Timestamp parsing with one documented policy (task A2).

Policy (docs/DECISIONS.md D5): parse ISO-8601, treat ``Z`` as UTC, treat
naive timestamps as UTC, and always return an aware datetime in UTC so every
comparison later in the pipeline is timezone-safe.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ghostdata.loaders.errors import LoaderError

_ISO_HINT = "Expected ISO-8601, for example 2026-07-19T13:00:00Z."


def parse_timestamp(value: str, *, field: str, path: str | None = None) -> datetime:
    """Parse one timestamp into an aware UTC datetime.

    Raises :class:`LoaderError` with a user-readable message on bad input -
    never a raw ``ValueError`` traceback.
    """
    raw = (value or "").strip()
    if not raw:
        raise LoaderError(
            f"Missing timestamp in field '{field}'",
            path=path,
            hint=f"{_ISO_HINT} The value was empty.",
        )
    normalized = raw[:-1] + "+00:00" if raw[-1] in "Zz" else raw
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise LoaderError(
            f"Field '{field}' does not look like a date/time: '{raw}'", path=path, hint=_ISO_HINT
        ) from None
    if parsed.tzinfo is None:
        # Documented policy: a timestamp without a zone means UTC (D5).
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def parse_optional_timestamp(value: str, *, field: str, path: str | None = None) -> datetime | None:
    """Like :func:`parse_timestamp` but returns ``None`` for empty values."""
    if not (value or "").strip():
        return None
    return parse_timestamp(value, field=field, path=path)


def to_utc_text(value: datetime) -> str:
    """Render a datetime the way the dataset does: ``...Z`` in UTC."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
