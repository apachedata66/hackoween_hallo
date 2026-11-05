"""SQLite-compatible snapshot loader (task A4).

The ``.sql`` evidence files are SQLite scripts, optionally with header
comments::

    -- Captured at: 2026-09-02T23:00:00Z
    -- Database topology: failover_replica

Design:
  * every file is executed into an **in-memory** database - the evidence file
    itself is never opened for writing (read-only evidence, quality list);
  * each row is tagged with ``system_id``, ``replica`` and ``file_id`` so one
    search returns hits across ALL snapshots and replicas (A4 acceptance);
  * corrupt files raise :class:`LoaderError` with a plain-language message;
    :meth:`SqlSnapshotIndex.from_dataset` collects those as warnings and
    keeps going (A14 - one bad file never aborts the batch).
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ghostdata.loaders.errors import LoaderError
from ghostdata.loaders.timeutil import parse_optional_timestamp

# Inventory tables (customer_data_inventory_*.sql) -> the system they describe.
TABLE_SYSTEM: dict[str, str] = {
    "customer_profiles": "account_service",
    "customer_search_documents": "search_service",
    "customer_analytics_profiles": "analytics_platform",
    "support_records": "support_platform",
    "customer_exports": "export_service",
    "connector_subscriptions": "integration_service",
    "backup_restore_entries": "backup_service",
    "security_audit_records": "security_service",
    "customer_profiles_primary": "account_service",
    "customer_profiles_failover_replica": "account_service",
    "search_documents_primary": "search_service",
}
_INVENTORY_TABLES = frozenset(
    {
        "customer_profiles",
        "customer_search_documents",
        "customer_analytics_profiles",
        "support_records",
        "customer_exports",
        "connector_subscriptions",
        "backup_restore_entries",
        "security_audit_records",
        "snapshot_scope",
    }
)

_HEADER_CAPTURED = re.compile(r"--\s*Captured at:\s*(\S+)")
_HEADER_TOPOLOGY = re.compile(r"--\s*Database topology:\s*(\S+)")
_FILENAME_DATE = re.compile(r"_(\d{4})(\d{2})(\d{2})(?:\.sql)$")


def derive_replica(table: str) -> str | None:
    """Which copy of the data a table represents (contract replica labels)."""
    if table in _INVENTORY_TABLES:
        return "primary"
    if table.endswith("_primary"):
        return "primary"
    if table.endswith("_failover_replica"):
        return "failover"
    if table.endswith("_read_replica"):
        return "read"
    if table.endswith("_reporting_replica"):
        return "reporting"
    if "_replica_" in table:  # customer_data_replica_ap_south / _eu_west
        return "regional"
    return None


def system_of(table: str, row: dict[str, str]) -> str:
    """Owning system for one row: the row's own origin_system wins."""
    origin = (row.get("origin_system") or "").strip()
    if origin:
        return origin
    return TABLE_SYSTEM.get(table, "")


@dataclass
class SqlRow:
    """One row from one snapshot, fully tagged for the evidence trail."""

    file_id: str
    file_path: str
    system_id: str
    replica: str | None
    table: str
    captured_at: datetime | None
    row: dict[str, str]
    cells_lower: tuple[str, ...] = field(default_factory=tuple, repr=False)

    def matches(self, identifier: str, pattern: re.Pattern[str]) -> bool:
        needle = identifier.lower()
        for cell in self.cells_lower:
            if cell == needle:
                return True
            if len(cell) >= len(needle) and pattern.search(cell):
                return True
        return False


@dataclass
class SqlSnapshot:
    """Everything one snapshot file contains."""

    file_id: str
    file_path: str
    captured_at: datetime | None
    topology: str | None
    tables: dict[str, list[dict[str, str]]]
    rows: list[SqlRow]


def load_snapshot(path: str | Path, *, file_id: str = "") -> SqlSnapshot:
    """Parse one ``.sql`` snapshot into memory. Raises :class:`LoaderError`."""
    file_path = Path(path)
    if not file_path.exists():
        raise LoaderError(f"Snapshot not found: {file_path.name}", path=str(file_path))
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise LoaderError(
            f"{file_path.name} is not readable text",
            path=str(file_path),
            hint="The snapshot may be corrupt; re-download dataset/.",
        ) from None

    captured_match = _HEADER_CAPTURED.search(text)
    topology_match = _HEADER_TOPOLOGY.search(text)
    captured_at = (
        parse_optional_timestamp(captured_match.group(1), field="Captured at", path=str(file_path))
        if captured_match
        else None
    )

    try:
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript(text)
            table_names = sorted(
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            )
            tables: dict[str, list[dict[str, str]]] = {}
            for name in table_names:
                cursor = connection.execute(f'SELECT * FROM "{name}"')
                columns = [description[0] for description in cursor.description or []]
                tables[name] = [
                    {
                        column: "" if value is None else str(value)
                        for column, value in zip(columns, values, strict=False)
                    }
                    for values in cursor.fetchall()
                ]
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise LoaderError(
            f"{file_path.name} could not be opened as a SQLite snapshot ({exc})",
            path=str(file_path),
            hint="Re-download dataset/; the snapshot may be truncated.",
        ) from None

    # Capture time: header comment -> snapshot_scope rows -> filename date.
    if captured_at is None and "snapshot_scope" in tables:
        stamps = [
            parse_optional_timestamp(
                row.get("captured_at", ""), field="captured_at", path=str(file_path)
            )
            for row in tables["snapshot_scope"]
        ]
        present = [stamp for stamp in stamps if stamp is not None]
        captured_at = max(present) if present else None
    if captured_at is None:
        date_match = _FILENAME_DATE.search(file_path.name)
        if date_match:
            captured_at = datetime(
                int(date_match.group(1)),
                int(date_match.group(2)),
                int(date_match.group(3)),
                tzinfo=UTC,
            )

    rows: list[SqlRow] = []
    for table, table_rows in tables.items():
        for row in table_rows:
            rows.append(
                SqlRow(
                    file_id=file_id,
                    file_path=str(file_path),
                    system_id=system_of(table, row),
                    replica=derive_replica(table),
                    table=table,
                    captured_at=captured_at,
                    row=row,
                    cells_lower=tuple(
                        value.strip().lower() for value in row.values() if isinstance(value, str)
                    ),
                )
            )
    return SqlSnapshot(
        file_id=file_id,
        file_path=str(file_path),
        captured_at=captured_at,
        topology=topology_match.group(1).strip() if topology_match else None,
        tables=tables,
        rows=rows,
    )


class SqlSnapshotIndex:
    """All snapshots, loaded once, searchable across every replica (A4/A15)."""

    def __init__(self, snapshots: Sequence[SqlSnapshot], warnings: Sequence[str] = ()) -> None:
        self.snapshots = list(snapshots)
        self.warnings = list(warnings)
        self.rows: list[SqlRow] = [row for snapshot in self.snapshots for row in snapshot.rows]

    @classmethod
    def from_dataset(cls, dataset_dir: str | Path, manifest: Sequence[object]) -> SqlSnapshotIndex:
        """Load every ``.sql`` file listed in the evidence manifest.

        ``manifest`` is the list of :class:`EvidenceFile` rows. Files that fail
        to parse become warnings, not exceptions (A14).
        """
        base = Path(dataset_dir)
        snapshots: list[SqlSnapshot] = []
        warnings: list[str] = []
        loaded: set[Path] = set()

        for entry in manifest:
            relative = getattr(entry, "file_path", "")
            if not str(relative).lower().endswith(".sql"):
                continue
            path = base / str(relative)
            try:
                path.resolve().relative_to(base.resolve())
            except ValueError:
                warnings.append(
                    f"Manifest path for {getattr(entry, 'file_id', '')} escapes dataset/; skipped."
                )
                continue
            file_id = str(getattr(entry, "file_id", ""))
            try:
                snapshots.append(load_snapshot(path, file_id=file_id))
                loaded.add(path.resolve())
            except LoaderError as exc:
                warnings.append(str(exc))

        # Robustness: snapshots present on disk but missing from the manifest.
        for path in sorted((base / "evidence" / "databases").glob("*.sql")):
            if path.resolve() not in loaded:
                try:
                    snapshots.append(load_snapshot(path, file_id=""))
                    warnings.append(
                        f"{path.name} is not listed in evidence_files.csv; cited without a file_id."
                    )
                except LoaderError as exc:
                    warnings.append(str(exc))
        return cls(snapshots, warnings)

    # ------------------------------------------------------------------ #
    def find_rows(self, identifiers: Iterable[str]) -> list[SqlRow]:
        """All rows, in ANY snapshot or replica, matching any identifier.

        Matching is case-insensitive; inside long text cells (``record_json``,
        excerpts) an identifier must sit on a word boundary so ``user_01`` can
        never match ``user_010``.
        """
        needles = [str(value).strip() for value in identifiers if str(value or "").strip()]
        if not needles or not self.rows:
            return []
        patterns = {
            needle: re.compile(r"(?<![\w.+-])" + re.escape(needle.lower()) + r"(?![\w.+-])")
            for needle in needles
        }
        hits: list[SqlRow] = []
        for row in self.rows:
            for needle in needles:
                if row.matches(needle, patterns[needle]):
                    hits.append(row)
                    break  # one hit per row; the identifier is recorded by the caller
        return hits

    def find_rows_for(self, identifiers: Iterable[str]) -> list[tuple[str, SqlRow]]:
        """Like :meth:`find_rows` but also reports WHICH identifier matched."""
        needles = [str(value).strip() for value in identifiers if str(value or "").strip()]
        patterns = {
            needle: re.compile(r"(?<![\w.+-])" + re.escape(needle.lower()) + r"(?![\w.+-])")
            for needle in needles
        }
        found: list[tuple[str, SqlRow]] = []
        for row in self.rows:
            for needle in needles:
                if row.matches(needle, patterns[needle]):
                    found.append((needle, row))
                    break
        return found

    def coverage(self) -> list[dict[str, object]]:
        """Every (system, replica, file) searched - feeds the A11 coverage report."""
        seen: dict[tuple[str, str | None, str], dict[str, object]] = {}
        for row in self.rows:
            key = (row.system_id, row.replica, row.file_id)
            if key not in seen:
                seen[key] = {
                    "system_id": row.system_id,
                    "replica": row.replica,
                    "file_id": row.file_id,
                    "captured_at": row.captured_at,
                    "rows": 0,
                }
            seen[key]["rows"] = int(seen[key]["rows"]) + 1
        return [seen[key] for key in sorted(seen, key=lambda k: (k[0], k[1] or "", k[2]))]
