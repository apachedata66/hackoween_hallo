"""Format-level regression tests for evidence provenance and time handling."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ghostdata.loaders import EvidenceFile, LoaderError, documents, extract_document, load_log_text
from ghostdata.loaders.records import parse_records_text
from ghostdata.loaders.sql_snapshots import load_snapshot


def test_nested_json_keeps_file_provenance_and_manifest_capture() -> None:
    record = parse_records_text(
        '{"records":[{"resource_id":"support_17","email":null}]}',
        evidence_id="evidence_fixture",
        file_path="evidence/records.json",
        captured_at=datetime(2026, 9, 1, tzinfo=UTC),
    )[0]
    assert record.evidence_id == "evidence_fixture"
    assert record.file_path == "evidence/records.json"
    assert record.captured_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert record.identifiers_present == ()


def test_json_record_time_overrides_enclosing_snapshot_time() -> None:
    records = parse_records_text(
        '{"captured_at":"2026-09-02T00:00:00Z","system":"search_service",'
        '"records":[{"resource_id":"search_18","observed_at":"2026-08-31T00:00:00Z"}]}',
        evidence_id="evidence_fixture",
    )
    assert records[0].observed_at == datetime(2026, 8, 31, tzinfo=UTC)
    assert records[0].system_id == "search_service"


def test_json_nested_record_inherits_context_timestamp_when_missing() -> None:
    records = parse_records_text(
        '{"observed_at":"2026-08-30T12:00:00Z","snapshots":[{"records":['
        '{"resource_id":"analytics_19"}]}]}',
        evidence_id="evidence_fixture",
    )
    assert records[0].observed_at == datetime(2026, 8, 30, 12, tzinfo=UTC)


def test_json_null_and_empty_identifier_fields_are_not_reported() -> None:
    records = parse_records_text(
        '{"resource_id":"account_20","email":null,"name":"","phone":"+1 202 555 0100"}',
        evidence_id="evidence_fixture",
    )
    assert records[0].identifiers_present == ("phone",)


def test_malformed_json_timestamp_fails_with_loader_error() -> None:
    with pytest.raises(LoaderError, match="observed_at"):
        parse_records_text(
            '{"resource_id":"search_21","observed_at":"not-a-time"}',
            evidence_id="evidence_fixture",
            file_path="records.json",
        )


def test_log_parser_retains_good_events_and_warns_on_malformed_lines() -> None:
    parsed = load_log_text(
        "not a timestamp\n"
        "2026-08-01T00:00:00Z service=search_service "
        "event=lookup resource_id=search_22"
    )
    assert len(parsed.events) == 1
    assert parsed.events[0].resource_id == "search_22"
    assert parsed.malformed_lines == 1
    assert parsed.warnings


def test_missing_document_is_a_warning_with_provenance(tmp_path: Path) -> None:
    result = extract_document(
        EvidenceFile("evidence_missing", "evidence/missing.txt", "fixture", None), tmp_path
    )
    assert result.evidence_id == "evidence_missing"
    assert result.text == ""
    assert result.warnings


def test_corrupt_document_cache_reextracts_original_content(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    source = dataset / "fixture.txt"
    source.write_text("resource support_23", encoding="utf-8")
    entry = EvidenceFile("evidence_cache", "fixture.txt", "fixture", None)
    cache = tmp_path / "cache"
    first = extract_document(entry, dataset, cache_dir=cache)
    cache_file = next(cache.glob("*.json"))
    cache_file.write_text("{corrupt", encoding="utf-8")
    second = extract_document(entry, dataset, cache_dir=cache)
    assert second.text == first.text == "resource support_23"
    assert second.evidence_id == first.evidence_id


def test_image_without_tesseract_returns_deterministic_warning(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "scan.png"
    image.write_bytes(b"fictional image fixture")
    monkeypatch.setattr(documents.shutil, "which", lambda _name: None)
    result = extract_document(EvidenceFile("evidence_image", "scan.png", "fixture", None), tmp_path)
    assert result.method == "none"
    assert result.confidence == 0.0
    assert result.warnings == (
        "Local OCR is unavailable; install Tesseract or set TESSERACT_CMD to read this image.",
    )


def test_sql_snapshot_preserves_source_id_replica_and_escaped_json(tmp_path: Path) -> None:
    path = tmp_path / "snapshot_read_replica.sql"
    path.write_text(
        "CREATE TABLE telemetry_read_replica (resource_id TEXT, record_json TEXT);\n"
        "INSERT INTO telemetry_read_replica VALUES "
        "('telemetry_24', '{\"email\":\"fiction@example.test\"}');\n",
        encoding="utf-8",
    )
    snapshot = load_snapshot(path, file_id="evidence_sql")
    row = snapshot.rows[0]
    assert row.file_id == "evidence_sql"
    assert row.replica == "read"
    assert json.loads(row.row["record_json"])["email"] == "fiction@example.test"


def test_corrupt_sql_snapshot_fails_safely(tmp_path: Path) -> None:
    path = tmp_path / "broken.sql"
    path.write_text("CREATE TABLE broken (id TEXT;", encoding="utf-8")
    with pytest.raises(LoaderError, match="SQLite snapshot"):
        load_snapshot(path, file_id="evidence_broken")
