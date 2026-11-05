"""Typed loader for ``system_activity.csv`` - the global event stream (task A2).

Rows may describe unrelated people (decoys). ``reported_result`` is a claim,
never proof (AGENTS.md 6.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ghostdata.loaders.tabular import read_csv_rows
from ghostdata.loaders.timeutil import parse_timestamp

_COLUMNS = (
    "activity_id",
    "event_time",
    "event_type",
    "source_system",
    "target_system",
    "resource_id",
    "reported_result",
    "details",
)


@dataclass(frozen=True)
class ActivityEvent:
    """One operational event, citable by ``activity_id``."""

    activity_id: str
    event_time: object  # datetime (UTC)
    event_type: str
    source_system: str
    target_system: str
    resource_id: str
    reported_result: str  # claim: SUCCESS | FAILED | PARTIAL
    details: str

    @classmethod
    def from_row(cls, row: dict[str, str], *, path: str | None = None) -> ActivityEvent:
        return cls(
            activity_id=row.get("activity_id", ""),
            event_time=parse_timestamp(row.get("event_time", ""), field="event_time", path=path),
            event_type=row.get("event_type", "").strip().upper(),
            source_system=row.get("source_system", "").strip(),
            target_system=row.get("target_system", "").strip(),
            resource_id=row.get("resource_id", "").strip(),
            reported_result=row.get("reported_result", "").strip().upper(),
            details=row.get("details", ""),
        )


def load_activity(path: str | Path) -> list[ActivityEvent]:
    """Load the full activity stream, oldest first (stable for replay)."""
    rows = read_csv_rows(path, _COLUMNS)
    events = [ActivityEvent.from_row(row, path=str(path)) for row in rows]
    events.sort(key=lambda event: (event.event_time, event.activity_id))
    return events
