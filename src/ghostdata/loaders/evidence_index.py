"""Load participant evidence once and link it to a resolved identity per case."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ghostdata.contract import ResolvedIdentity
from ghostdata.identity.email import contains_identifier
from ghostdata.loaders.activity_csv import ActivityEvent
from ghostdata.loaders.documents import DocumentExtraction, extract_document
from ghostdata.loaders.errors import LoaderError
from ghostdata.loaders.evidence_csv import EvidenceFile
from ghostdata.loaders.evidence_models import (
    EvidenceRecord,
    EvidenceWarning,
    classify_category,
    classify_kind,
    direct_identifier_fields,
    normalize_system_id,
    system_for_category,
)
from ghostdata.loaders.logs import LogEvent, load_log_file
from ghostdata.loaders.records import load_records_file
from ghostdata.loaders.sql_snapshots import SqlRow, SqlSnapshotIndex
from ghostdata.loaders.timeutil import parse_optional_timestamp

_RESOURCE_RE = re.compile(
    r"\b(?:account|analytics|support|search|cache|export|backup|tombstone|audit_record|"
    r"email_delivery|data_flow|connector|marketing|telemetry|statement|legal_hold)_"
    r"(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]+\b",
    re.I,
)
_FILENAME_RE = re.compile(
    r"(?<![A-Za-z0-9_-])[A-Za-z0-9][A-Za-z0-9_. -]*\.(?:pdf|csv|zip|json|jpg|jpeg|png|"
    r"txt|log|sql|xml|parquet|avro)(?![A-Za-z0-9_-])",
    re.I,
)
_TEXT_ROW = re.compile(
    r"^\s*-\s*(?P<time>\S+)\s*\|\s*(?P<system>[^|]+)\|\s*(?P<resource>[^|]+)\|"
    r"\s*(?P<category>[^|]+)\|\s*(?P<status>[^|]+)\|\s*(?P<subject>.+?)\s*$",
    re.I,
)
_ORIGIN_SYSTEMS = {
    "account_admin_portal": "account_service",
    "account_history_service": "identity_service",
    "customer_account_service": "account_service",
    "customer_export_service": "export_service",
    "customer_search_primary_capture": "search_service",
    "downstream_delivery_service": "email_delivery_service",
    "integration_admin": "integration_service",
    "integration_management_service": "integration_service",
    "legal_retention_service": "legal_service",
    "search_index_admin": "search_service",
    "security_audit_service": "security_service",
}


def _normalized_origin_system(origin: str) -> str:
    normalized = origin.strip().casefold()
    return _ORIGIN_SYSTEMS.get(normalized, normalize_system_id(normalized))


def _document_system(entry: EvidenceFile, category: str) -> str:
    origin = entry.origin.strip().casefold()
    if origin in _ORIGIN_SYSTEMS:
        return _ORIGIN_SYSTEMS[origin]
    normalized = _normalized_origin_system(origin)
    if normalized.endswith(("_service", "_platform")) or normalized in {
        "object_storage",
        "object_store",
    }:
        return normalized
    return system_for_category(category)


def _document_status(text: str, kind: str) -> str:
    """Read explicit flow state from a cutoff-bounded evidence document."""
    if kind != "flow":
        return "PRESENT"
    if re.search(r"\b(?:disabled|inactive|paused|stopped)\b", text, re.IGNORECASE):
        return "DISABLED"
    if re.search(
        r"\b(?:continuous\s+sync|continuous\s+delivery|sync\s+enabled|active|running)\b",
        text,
        re.IGNORECASE,
    ):
        return "ACTIVE"
    return "PRESENT"


@dataclass(frozen=True)
class EvidenceMatch:
    record: EvidenceRecord
    matched_identifiers: tuple[str, ...]


def _all_string_values(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        for child in value.values():
            yield from _all_string_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _all_string_values(child)
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        cleaned = str(value).strip()
        if cleaned:
            yield cleaned


def _identity_values(identity: ResolvedIdentity) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    values.extend(
        (value, "email") for value in identity.emails_current + identity.emails_historical
    )
    values.extend((value, "email_hash") for value in identity.email_hashes)
    values.extend((value, "user_id") for value in identity.user_ids)
    other = identity.other_identifiers
    values.extend((str(value), "phone") for value in other.get("phone_history", []) if value)
    if other.get("phone"):
        values.append((str(other["phone"]), "phone"))
    if other.get("name"):
        values.append((str(other["name"]), "name"))
    dedup: dict[str, tuple[str, str]] = {}
    for value, kind in values:
        normalized = value.strip().casefold()
        if normalized:
            dedup.setdefault(normalized, (value.strip(), kind))
    return [dedup[key] for key in sorted(dedup)]


def _contains(haystack: str, needle: str, kind: str) -> bool:
    return contains_identifier(haystack, needle, kind)


def _status(raw: dict[str, Any]) -> str:
    status = (
        str(
            raw.get("result")
            or raw.get("status")
            or raw.get("account_status")
            or raw.get("state")
            or ""
        )
        .strip()
        .upper()
    )
    if status:
        return status
    if "restore_allowed" in raw:
        return (
            "ACTIVE"
            if str(raw["restore_allowed"]).casefold() in {"1", "true", "yes"}
            else "BLOCKED"
        )
    if "deletion_block" in raw:
        if str(raw["deletion_block"]).casefold() in {"1", "true", "yes"}:
            return "BLOCKED"
        if str(raw.get("eligible", "")).casefold() in {"1", "true", "yes"}:
            return "ACTIVE"
    if "eligible" in raw:
        return "ACTIVE" if str(raw["eligible"]).casefold() in {"1", "true", "yes"} else "BLOCKED"
    if "enabled" in raw:
        return "ACTIVE" if str(raw["enabled"]).casefold() in {"1", "true", "yes"} else "DISABLED"
    if raw.get("status_code") is not None:
        try:
            return "PRESENT" if int(raw["status_code"]) < 400 else "NOT_FOUND"
        except (TypeError, ValueError):
            pass
    if raw.get("http_status") is not None:
        try:
            return "PRESENT" if int(raw["http_status"]) < 400 else "NOT_FOUND"
        except (TypeError, ValueError):
            pass
    if raw.get("rows") is not None:
        try:
            return "PRESENT" if int(raw["rows"]) > 0 else "NOT_FOUND"
        except (TypeError, ValueError):
            pass
    return ""


def _record_for_sql(row: SqlRow, captured_at: datetime | None = None) -> EvidenceRecord:
    raw = dict(row.row)
    category = classify_category(
        row.table,
        row.system_id,
        row.row.get("collection_name", ""),
        row.row.get("record_type", ""),
        row.row.get("record_json", ""),
    )
    observed_at = None
    for field in ("updated_at", "recorded_at", "observed_at"):
        if raw.get(field):
            try:
                observed_at = parse_optional_timestamp(raw[field], field=field, path=row.file_path)
            except LoaderError:
                observed_at = None
            break
    status = _status(raw)
    fields_for_pii: Any = raw
    if "record_json" in raw:
        try:
            nested = __import__("json").loads(raw["record_json"])
            if isinstance(nested, dict):
                fields_for_pii = nested
                status = status or _status(nested)
        except (ValueError, TypeError):
            pass
    return EvidenceRecord(
        evidence_id=row.file_id,
        file_path=row.file_path,
        source_type="sql",
        captured_at=row.captured_at or captured_at,
        observed_at=observed_at,
        system_id=normalize_system_id(row.system_id) or system_for_category(category),
        resource_id=str(raw.get("resource_id", "")),
        data_category=category,
        kind=(
            "flow"
            if "connector_subscriptions" in row.table.casefold()
            or "data_flow" in str(raw.get("resource_id", "")).casefold()
            else classify_kind(category, str(raw.get("resource_id", "")))
        ),
        replica=row.replica,
        status=status,
        identifiers_present=direct_identifier_fields(fields_for_pii),
        raw=raw,
        text=" ".join(_all_string_values(raw)),
    )


def _record_for_log(event: LogEvent, manifest_entry: EvidenceFile) -> EvidenceRecord:
    hints = [
        event.system_id,
        event.resource_id,
        event.event_type,
        manifest_entry.file_path,
        event.message,
    ]
    hints.extend(str(value) for value in event.fields.values())
    category = classify_category(*hints)
    if any("legacy_contact_index" in str(value).casefold() for value in event.fields.values()):
        category = "SECONDARY_IDENTIFIER"
    system_id = normalize_system_id(event.system_id) or system_for_category(category)
    raw = dict(event.fields)
    status = _status(raw)
    if not status:
        for key in ("result", "status", "enabled", "restore_allowed"):
            if key in raw:
                status = _status({key: raw[key]})
                if status:
                    break
    return EvidenceRecord(
        evidence_id=event.evidence_id,
        file_path=event.file_path,
        source_type="log",
        captured_at=manifest_entry.captured_at,
        observed_at=event.event_time,
        system_id=system_id,
        resource_id=event.resource_id,
        data_category=category,
        kind=classify_kind(category, event.resource_id, event.event_type),
        replica=None,
        status=status,
        identifiers_present=direct_identifier_fields(raw),
        raw=raw,
        text=" ".join([event.message, *_all_string_values(raw)]),
    )


def _records_from_text_document(
    entry: EvidenceFile,
    extraction: DocumentExtraction,
) -> list[EvidenceRecord]:
    records: list[EvidenceRecord] = []
    for line in extraction.text.splitlines():
        matched = _TEXT_ROW.match(line)
        if not matched:
            continue
        try:
            observed = parse_optional_timestamp(
                matched.group("time"), field="record timestamp", path=entry.file_path
            )
        except LoaderError:
            observed = None
        resource = matched.group("resource").strip()
        category = classify_category(matched.group("category"), matched.group("system"), resource)
        raw = {
            "subject_reference": matched.group("subject").strip(),
            "result": matched.group("status").strip(),
        }
        records.append(
            EvidenceRecord(
                evidence_id=entry.file_id,
                file_path=entry.file_path,
                source_type="text",
                captured_at=entry.captured_at,
                observed_at=observed,
                system_id=normalize_system_id(matched.group("system").strip()),
                resource_id=resource,
                data_category=category,
                kind=classify_kind(category, resource),
                replica=None,
                status=matched.group("status").strip().upper(),
                identifiers_present=(),
                raw=raw,
                text=line.strip(),
            )
        )
    if records:
        return records
    # Reports without a pipe-delimited table may still contain resource ids.
    category = classify_category(entry.file_path, extraction.text)
    system = _document_system(entry, category)
    ids = sorted(set(_RESOURCE_RE.findall(extraction.text)), key=str.casefold)
    for resource in ids:
        records.append(
            EvidenceRecord(
                evidence_id=entry.file_id,
                file_path=entry.file_path,
                source_type="document",
                captured_at=entry.captured_at,
                observed_at=None,
                system_id=system,
                resource_id=resource,
                data_category=classify_category(category, resource, entry.file_path),
                kind=classify_kind(category, resource),
                replica=None,
                status=_document_status(
                    extraction.text, classify_kind(category, resource)
                ),
                identifiers_present=(),
                raw={"document_text": extraction.text},
                text=extraction.text,
                confidence=extraction.confidence,
            )
        )
    return records


class EvidenceIndex:
    """Immutable run-level index of SQL and file evidence.

    Evidence is loaded once and then linked to a case through that case's
    current and historical identifiers. Bad files generate warnings and do
    not interrupt the rest of the run.
    """

    def __init__(
        self,
        records: Sequence[EvidenceRecord],
        *,
        sql_index: SqlSnapshotIndex | None = None,
        extractions: Sequence[DocumentExtraction] = (),
        warnings: Sequence[EvidenceWarning] = (),
        coverage: Sequence[dict[str, Any]] = (),
        manifest_times: dict[str, datetime | None] | None = None,
        manifest_origins: dict[str, str] | None = None,
    ) -> None:
        self.records = list(records)
        self._search_texts = [
            "\n".join((record.text, *_all_string_values(record.raw))).casefold()
            for record in self.records
        ]
        self._phone_search_texts = [re.sub(r"\D", "", value) for value in self._search_texts]
        self.sql_index = sql_index
        self._records_by_resource: dict[str, list[EvidenceRecord]] = {}
        for record in self.records:
            if record.resource_id:
                self._records_by_resource.setdefault(record.resource_id.casefold(), []).append(
                    record
                )
        self._sql_rows_by_resource: dict[str, list[SqlRow]] = {}
        if sql_index:
            for row in sql_index.rows:
                resource_id = str(row.row.get("resource_id", "")).strip()
                if resource_id:
                    self._sql_rows_by_resource.setdefault(resource_id.casefold(), []).append(row)
        self.extractions = list(extractions)
        self.warnings = list(warnings)
        self._coverage = list(coverage)
        self._manifest_times = dict(manifest_times or {})
        self._manifest_origins = dict(manifest_origins or {})

    @classmethod
    def from_dataset(
        cls,
        dataset_dir: str | Path,
        manifest: Sequence[EvidenceFile],
        *,
        cache_dir: str | Path | None = None,
    ) -> EvidenceIndex:
        base = Path(dataset_dir)
        records: list[EvidenceRecord] = []
        warnings: list[EvidenceWarning] = []
        extractions: list[DocumentExtraction] = []
        sql_index = SqlSnapshotIndex.from_dataset(base, manifest)
        warnings.extend(EvidenceWarning("", message) for message in sql_index.warnings)
        for entry in manifest:
            path = base / entry.file_path
            suffix = path.suffix.casefold()
            if suffix == ".sql":
                continue
            try:
                path.resolve().relative_to(base.resolve())
            except ValueError:
                warnings.append(
                    EvidenceWarning(
                        entry.file_id,
                        "The manifest path resolves outside dataset/ and was skipped.",
                    )
                )
                continue
            try:
                if suffix == ".json":
                    records.extend(
                        load_records_file(
                            path,
                            evidence_id=entry.file_id,
                            captured_at=entry.captured_at,
                        )
                    )
                elif suffix == ".log":
                    parsed = load_log_file(path, evidence_id=entry.file_id)
                    records.extend(
                        _record_for_log(event, entry)
                        for event in parsed.events
                        if event.resource_id
                    )
                    warnings.extend(
                        EvidenceWarning(entry.file_id, message) for message in parsed.warnings
                    )
                elif suffix in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".txt"}:
                    extraction = extract_document(entry, base, cache_dir=cache_dir)
                    extractions.append(extraction)
                    warnings.extend(
                        EvidenceWarning(entry.file_id, message) for message in extraction.warnings
                    )
                    records.extend(_records_from_text_document(entry, extraction))
            except LoaderError as exc:
                warnings.append(EvidenceWarning(entry.file_id, str(exc)))
            except (OSError, ValueError, TypeError) as exc:
                warnings.append(
                    EvidenceWarning(
                        entry.file_id, f"Evidence could not be parsed ({type(exc).__name__})."
                    )
                )
        coverage = sql_index.coverage()
        coverage.extend(
            {
                "system_id": record.system_id,
                "replica": record.replica,
                "file_id": record.evidence_id,
                "captured_at": record.captured_at,
                "rows": sum(
                    1
                    for item in records
                    if item.evidence_id == record.evidence_id and item.system_id == record.system_id
                ),
            }
            for record in records
            if record.system_id
        )
        unique_coverage = {
            (
                str(item.get("system_id", "")),
                item.get("replica"),
                str(item.get("file_id", "")),
            ): item
            for item in coverage
        }
        return cls(
            records,
            sql_index=sql_index,
            extractions=extractions,
            warnings=warnings,
            coverage=list(unique_coverage.values()),
            manifest_times={entry.file_id: entry.captured_at for entry in manifest},
            manifest_origins={entry.file_id: entry.origin for entry in manifest},
        )

    def coverage(self) -> list[dict[str, Any]]:
        """All system/replica/file partitions searched, including no-hit ones."""
        return sorted(
            self._coverage,
            key=lambda item: (
                str(item.get("system_id", "")),
                str(item.get("replica") or ""),
                str(item.get("file_id", "")),
            ),
        )

    @staticmethod
    def _record_matches(
        text: str,
        phone_text: str,
        values: Sequence[tuple[str, str]],
    ) -> tuple[str, ...]:
        matches: list[str] = []
        for value, kind in values:
            if kind == "phone":
                digits = re.sub(r"\D", "", value)
                if len(digits) >= 7 and digits in phone_text:
                    matches.append(value)
            elif _contains(text, value, kind):
                matches.append(value)
        return tuple(matches)

    def find_records(
        self,
        identity: ResolvedIdentity,
        audit_at: datetime,
    ) -> list[EvidenceMatch]:
        values = _identity_values(identity)
        hits: list[EvidenceMatch] = []
        for record, text, phone_text in zip(
            self.records, self._search_texts, self._phone_search_texts, strict=True
        ):
            if record.captured_at is not None and record.captured_at > audit_at:
                continue
            if record.observed_at is not None and record.observed_at > audit_at:
                continue
            matched = self._record_matches(text, phone_text, values)
            if matched:
                hits.append(EvidenceMatch(record, matched))
        if self.sql_index:
            identifiers = [value for value, _kind in values]
            # SQL file captures usually include a header; rows without one use
            # the capture time from their manifest entry (assigned on load).
            for _identifier, row in self.sql_index.find_rows_for(identifiers):
                record = _record_for_sql(row, self._manifest_times.get(row.file_id))
                if record.captured_at is not None and record.captured_at > audit_at:
                    continue
                if record.observed_at is not None and record.observed_at > audit_at:
                    continue
                searchable_text = "\n".join(
                    (record.text, *_all_string_values(record.raw))
                ).casefold()
                matched = self._record_matches(
                    searchable_text,
                    re.sub(r"\D", "", searchable_text),
                    values,
                )
                if matched:
                    hits.append(EvidenceMatch(record, matched))
        hits.sort(
            key=lambda hit: (
                hit.record.system_id,
                hit.record.resource_id,
                hit.record.replica or "",
                hit.record.effective_time or datetime.min.replace(tzinfo=audit_at.tzinfo),
                hit.record.evidence_id,
            )
        )
        return hits

    def find_linked_resource_records(
        self,
        identity: ResolvedIdentity,
        events: Iterable[ActivityEvent],
        audit_at: datetime,
    ) -> tuple[list[str], list[EvidenceMatch]]:
        """Join identity-link events to independent, time-bounded resource evidence.

        A link event can establish which resource belongs to an identity, but it
        is not itself a reliable observation of that resource's current state.
        The exact resource ID and target system must also appear in a participant-
        visible record before that record is added to the case. If a link names
        a file alias, the alias may be joined to an independently captured file
        listing in the same source system; the link alone still proves no state.
        """

        values = _identity_values(identity)
        phone_text_cache: dict[str, str] = {}
        links: dict[tuple[str, str], tuple[str, set[str]]] = {}
        for event in events:
            if event.event_type != "LINK_RESOURCE_IDENTITY" or event.event_time > audit_at:
                continue
            resource_id = event.resource_id.strip()
            target_system = normalize_system_id(event.target_system).strip()
            if not resource_id or not target_system:
                continue
            details = event.details.casefold()
            phone_text = phone_text_cache.setdefault(details, re.sub(r"\D", "", details))
            if not self._record_matches(details, phone_text, values):
                continue
            link_key = (target_system.casefold(), resource_id.casefold())
            existing = links.get(link_key)
            if existing:
                existing[1].add(event.details)
            else:
                links[link_key] = (resource_id, {event.details})

        matches_by_key: dict[tuple[str, str, str, str | None, datetime | None], EvidenceMatch] = {}
        for (target_system, resource_key), (resource_id, event_details) in sorted(links.items()):
            matched_exact_record = False
            candidates = list(self._records_by_resource.get(resource_key, ()))
            for record in candidates:
                system_id = normalize_system_id(record.system_id).casefold()
                if system_id != target_system:
                    continue
                if record.captured_at is not None and record.captured_at > audit_at:
                    continue
                if record.observed_at is not None and record.observed_at > audit_at:
                    continue
                key = (
                    record.evidence_id,
                    record.system_id,
                    record.resource_id,
                    record.replica,
                    record.effective_time,
                )
                matches_by_key[key] = EvidenceMatch(record, ())
                matched_exact_record = True

            if self.sql_index:
                for row in self._sql_rows_by_resource.get(resource_key, ()):
                    system_id = normalize_system_id(row.system_id).casefold()
                    if system_id != target_system:
                        continue
                    record = _record_for_sql(row, self._manifest_times.get(row.file_id))
                    if record.captured_at is not None and record.captured_at > audit_at:
                        continue
                    if record.observed_at is not None and record.observed_at > audit_at:
                        continue
                    key = (
                        record.evidence_id,
                        record.system_id,
                        record.resource_id,
                        record.replica,
                        record.effective_time,
                    )
                    matches_by_key[key] = EvidenceMatch(record, ())
                    matched_exact_record = True

            if matched_exact_record:
                continue

            aliases = {
                match.group(0).strip().rstrip(".,;:")
                for details in event_details
                for match in _FILENAME_RE.finditer(details)
            }
            for alias in sorted(aliases, key=str.casefold):
                alias_pattern = re.compile(
                    rf"(?<![\w.-]){re.escape(alias)}(?![\w.-])", re.IGNORECASE
                )
                for extraction in self.extractions:
                    source_system = _normalized_origin_system(
                        self._manifest_origins.get(extraction.evidence_id, "")
                    ).casefold()
                    captured_at = self._manifest_times.get(extraction.evidence_id)
                    if (
                        source_system != target_system
                        or captured_at is None
                        or captured_at > audit_at
                    ):
                        continue
                    if not alias_pattern.search(extraction.text):
                        continue
                    category = classify_category(
                        target_system, alias, extraction.file_path, extraction.text
                    )
                    if not category:
                        continue
                    record = EvidenceRecord(
                        evidence_id=extraction.evidence_id,
                        file_path=extraction.file_path,
                        source_type="document",
                        captured_at=captured_at,
                        observed_at=None,
                        system_id=target_system,
                        resource_id=resource_id,
                        data_category=category,
                        kind=classify_kind(category, resource_id),
                        replica=None,
                        status="PRESENT",
                        identifiers_present=(),
                        raw={"linked_filename": alias},
                        text=extraction.text,
                        confidence=extraction.confidence,
                    )
                    key = (
                        record.evidence_id,
                        record.system_id,
                        record.resource_id,
                        record.replica,
                        record.effective_time,
                    )
                    matches_by_key[key] = EvidenceMatch(record, ())

        linked_ids = sorted({value[0] for value in links.values()}, key=str.casefold)
        hits = list(matches_by_key.values())
        hits.sort(
            key=lambda hit: (
                hit.record.system_id,
                hit.record.resource_id,
                hit.record.replica or "",
                hit.record.effective_time or datetime.min.replace(tzinfo=audit_at.tzinfo),
                hit.record.evidence_id,
            )
        )
        return linked_ids, hits


__all__ = ["EvidenceIndex", "EvidenceMatch"]
