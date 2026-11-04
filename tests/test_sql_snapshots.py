"""Unit tests for the SQL snapshot loader (task A4 acceptance)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ghostdata.loaders.errors import LoaderError
from ghostdata.loaders.sql_snapshots import (
    SqlSnapshotIndex,
    derive_replica,
    load_snapshot,
    system_of,
)

PRIMARY_VS_FAILOVER = """\
-- Ghost Data Still Exists: point-in-time database snapshot
-- Dialect: SQLite-compatible SQL
-- Captured at: 2026-09-02T23:00:00Z
-- Database topology: failover_replica

BEGIN TRANSACTION;
CREATE TABLE customer_profiles_failover_replica (
    resource_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    full_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL
);
INSERT INTO "customer_profiles_failover_replica" VALUES('account_005','user_05','Leila Haddad','leila.haddad@yahoo.com','+212 600 000 000');
CREATE TABLE customer_profiles_primary (
    resource_id TEXT PRIMARY KEY, user_id TEXT NOT NULL,
    full_name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL
);
INSERT INTO "customer_profiles_primary" VALUES('account_8741','user_8741','Karim','karim@gmail.com','+971 50 000 000');
COMMIT;
"""

INVENTORY = """\
CREATE TABLE snapshot_scope (origin_system TEXT PRIMARY KEY, captured_at TEXT NOT NULL);
INSERT INTO snapshot_scope VALUES ('account_service', '2026-09-16T08:37:39Z');
INSERT INTO snapshot_scope VALUES ('search_service', '2026-09-16T08:37:39Z');
CREATE TABLE customer_profiles (
    resource_id TEXT PRIMARY KEY, customer_reference TEXT NOT NULL,
    full_name TEXT NOT NULL, email TEXT NOT NULL, account_status TEXT NOT NULL
);
INSERT INTO customer_profiles VALUES('account_005','user_05','Leila','leila.haddad@yahoo.com','DELETED');
CREATE TABLE customer_data_primary (
    resource_id TEXT PRIMARY KEY, origin_system TEXT NOT NULL,
    collection_name TEXT NOT NULL, record_json TEXT NOT NULL
);
INSERT INTO customer_data_primary VALUES('analytics_17','analytics_platform','reports','{"user_id":"user_01","email":"x@example.com"}');
INSERT INTO customer_data_primary VALUES('analytics_18','analytics_platform','reports','{"user_id":"user_010","email":"y@example.com"}');
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


class TestTags:
    def test_header_topology_and_capture_time(self, tmp_path: Path) -> None:
        snapshot = load_snapshot(
            _write(tmp_path, "customer_accounts_failover_replica_20260902.sql", PRIMARY_VS_FAILOVER)
        )
        assert snapshot.topology == "failover_replica"
        assert snapshot.captured_at is not None
        assert snapshot.captured_at.year == 2026

    def test_replica_and_system_tags_per_table(self, tmp_path: Path) -> None:
        snapshot = load_snapshot(_write(tmp_path, "snap.sql", PRIMARY_VS_FAILOVER))
        by_table = {row.table: row for row in snapshot.rows}
        failover = by_table["customer_profiles_failover_replica"]
        primary = by_table["customer_profiles_primary"]
        assert failover.replica == "failover"
        assert primary.replica == "primary"
        assert failover.system_id == "account_service"
        assert primary.file_path.endswith("snap.sql")

    def test_inventory_capture_time_from_scope(self, tmp_path: Path) -> None:
        snapshot = load_snapshot(
            _write(tmp_path, "customer_data_inventory_20260916.sql", INVENTORY)
        )
        assert snapshot.captured_at is not None
        assert snapshot.captured_at.isoformat().startswith("2026-09-16T08:37:39")
        # origin_system column wins over the table map
        data_rows = [row for row in snapshot.rows if row.table == "customer_data_primary"]
        assert {row.system_id for row in data_rows} == {"analytics_platform"}

    def test_filename_date_fallback(self, tmp_path: Path) -> None:
        bare = "CREATE TABLE t (a TEXT);\nINSERT INTO t VALUES('x');\n"
        snapshot = load_snapshot(_write(tmp_path, "customer_data_inventory_20260404.sql", bare))
        assert snapshot.captured_at is not None
        assert snapshot.captured_at.isoformat().startswith("2026-04-04")

    def test_derive_replica_labels(self) -> None:
        assert derive_replica("customer_data_primary") == "primary"
        assert derive_replica("customer_data_failover_replica") == "failover"
        assert derive_replica("customer_data_read_replica") == "read"
        assert derive_replica("customer_data_reporting_replica") == "reporting"
        assert derive_replica("customer_data_replica_ap_south") == "regional"
        assert derive_replica("customer_profiles") == "primary"  # inventory table
        assert derive_replica("something_else") is None

    def test_system_of_falls_back_to_table_map(self) -> None:
        assert system_of("support_records", {}) == "support_platform"
        assert system_of("mystery_table", {}) == ""


class TestSearching:
    def _index(self, tmp_path: Path) -> SqlSnapshotIndex:
        a = load_snapshot(
            _write(tmp_path, "a_failover_20260902.sql", PRIMARY_VS_FAILOVER), file_id="evidence_10"
        )
        b = load_snapshot(
            _write(tmp_path, "customer_data_inventory_20260916.sql", INVENTORY),
            file_id="evidence_11",
        )
        return SqlSnapshotIndex([a, b])

    def test_search_spans_all_snapshots_and_replicas(self, tmp_path: Path) -> None:
        index = self._index(tmp_path)
        hits = index.find_rows(["leila.haddad@yahoo.com"])
        # the same person shows up in the failover snapshot AND the inventory
        assert len(hits) == 2
        assert {h.replica for h in hits} == {"failover", "primary"}
        failover_hit = next(h for h in hits if h.replica == "failover")
        assert failover_hit.file_id == "evidence_10"
        assert failover_hit.system_id == "account_service"
        inventory_hit = next(h for h in hits if h.replica == "primary")
        assert inventory_hit.file_id == "evidence_11"
        assert inventory_hit.system_id == "account_service"

    def test_identifiers_inside_json_blobs_match_on_boundaries(self, tmp_path: Path) -> None:
        index = self._index(tmp_path)
        hits = index.find_rows(["user_01"])
        tables_and_ids = {(h.table, h.row["resource_id"]) for h in hits}
        assert ("customer_data_primary", "analytics_17") in tables_and_ids
        # user_01 must NOT match the cell user_010
        assert ("customer_data_primary", "analytics_18") not in tables_and_ids

    def test_find_rows_for_reports_which_identifier_matched(self, tmp_path: Path) -> None:
        index = self._index(tmp_path)
        found = index.find_rows_for(["account_005", "nobody@example.com"])
        assert found
        identifier, row = found[0]
        assert identifier == "account_005"
        assert row.file_id == "evidence_10"

    def test_coverage_lists_every_system_replica_file(self, tmp_path: Path) -> None:
        index = self._index(tmp_path)
        coverage = index.coverage()
        pairs = {(c["system_id"], c["replica"]) for c in coverage}
        assert ("account_service", "failover") in pairs
        assert ("account_service", "primary") in pairs

    def test_empty_identifiers_return_nothing(self, tmp_path: Path) -> None:
        assert self._index(tmp_path).find_rows([]) == []


class TestFailures:
    def test_corrupt_snapshot_raises_friendly_error(self, tmp_path: Path) -> None:
        with pytest.raises(LoaderError) as exc:
            load_snapshot(_write(tmp_path, "broken.sql", "CREATE TABLE (; this is not sql"))
        assert "broken.sql" in str(exc.value)

    def test_missing_snapshot_raises_friendly_error(self, tmp_path: Path) -> None:
        with pytest.raises(LoaderError) as exc:
            load_snapshot(tmp_path / "nope.sql")
        assert "not found" in str(exc.value).lower()

    def test_from_dataset_survives_one_bad_file(self, tmp_path: Path) -> None:
        dataset = tmp_path / "dataset"
        (dataset / "evidence" / "databases").mkdir(parents=True)
        (dataset / "evidence" / "databases" / "good.sql").write_text(
            PRIMARY_VS_FAILOVER, encoding="utf-8", newline=""
        )
        (dataset / "evidence" / "databases" / "bad.sql").write_text(
            "CREATE TABLE (;", encoding="utf-8", newline=""
        )

        class Entry:
            file_id = "evidence_01"
            file_path = "evidence/databases/good.sql"

        class BadEntry:
            file_id = "evidence_02"
            file_path = "evidence/databases/bad.sql"

        index = SqlSnapshotIndex.from_dataset(dataset, [Entry(), BadEntry()])
        assert index.rows  # good file loaded
        assert any("bad.sql" in warning for warning in index.warnings)  # bad file flagged
