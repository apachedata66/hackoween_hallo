"""Typed loader for ``evidence_files.csv`` - the evidence manifest (task A2).

The manifest maps ``file_id`` -> path/origin/capture time. It does NOT say
which case or user a file concerns - linkage comes from file contents
(AGENTS.md 6.6).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ghostdata.loaders.tabular import read_csv_rows
from ghostdata.loaders.timeutil import parse_optional_timestamp

_COLUMNS = ("file_id", "file_path", "origin", "captured_at")


@dataclass(frozen=True)
class EvidenceFile:
    """One manifest row."""

    file_id: str
    file_path: str  # relative to dataset/
    origin: str
    captured_at: object | None  # datetime (UTC) or None

    @classmethod
    def from_row(cls, row: dict[str, str], *, path: str | None = None) -> EvidenceFile:
        return cls(
            file_id=row.get("file_id", ""),
            file_path=row.get("file_path", "").strip().replace("\\", "/"),
            origin=row.get("origin", ""),
            captured_at=parse_optional_timestamp(
                row.get("captured_at", ""), field="captured_at", path=path
            ),
        )


def load_evidence_manifest(path: str | Path) -> list[EvidenceFile]:
    """Load the evidence manifest."""
    rows = read_csv_rows(path, _COLUMNS)
    return [EvidenceFile.from_row(row, path=str(path)) for row in rows]
