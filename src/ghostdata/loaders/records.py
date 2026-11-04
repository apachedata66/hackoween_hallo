"""Parser for nested JSON records and snapshots supplied as evidence."""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from ghostdata.loaders.errors import LoaderError
from ghostdata.loaders.evidence_models import (
    EvidenceRecord,
    classify_category,
    classify_kind,
    direct_identifier_fields,
    normalize_system_id,
    system_for_category,
)
from ghostdata.loaders.timeutil import parse_optional_timestamp

_TIME_FIELDS = (
    "recorded_at",
    "observed_at",
    "event_time",
    "captured_at",
    "updated_at",
    "created_at",
    "recordedAt",
)
_SYSTEM_FIELDS = ("system", "system_id", "data_store", "origin_system", "service", "source_system")
_CONTEXT_KEYS = frozenset(
    {"service_exports", "snapshots", "records", "profiles", "lookups", "events", "entries"}
)


def _time(value: Any, *, path: str, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        return parse_optional_timestamp(str(value), field=field, path=path)
    except LoaderError:
        return None


def _record_time(node: Mapping[str, Any], inherited: datetime | None, path: str) -> datetime | None:
    for key in _TIME_FIELDS:
        if node.get(key) not in (None, ""):
            return _time(node[key], path=path, field=key)
    return inherited


def _flatten_values(node: Any) -> Iterator[str]:
    if isinstance(node, Mapping):
        for value in node.values():
            yield from _flatten_values(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _flatten_values(value)
    elif isinstance(node, (str, int, float)) and not isinstance(node, bool):
        value = str(node).strip()
        if value:
            yield value


def _walk_records(
    node: Any,
    *,
    evidence_id: str,
    file_path: str,
    captured_at: datetime | None,
    system_hint: str = "",
    collection_hint: str = "",
    time_hint: datetime | None = None,
    source_path: str = "",
) -> Iterator[EvidenceRecord]:
    if isinstance(node, list):
        for index, child in enumerate(node):
            yield from _walk_records(
                child,
                evidence_id=evidence_id,
                file_path=file_path,
                captured_at=captured_at,
                system_hint=system_hint,
                collection_hint=collection_hint,
                time_hint=time_hint,
                source_path=f"{source_path}[{index}]",
            )
        return
    if not isinstance(node, Mapping):
        return

    system = next((str(node[key]).strip() for key in _SYSTEM_FIELDS if node.get(key)), system_hint)
    collection = str(
        node.get("collection")
        or node.get("collection_name")
        or node.get("table")
        or collection_hint
    )
    observed = time_hint or _record_time(node, None, file_path)
    if node.get("resource_id"):
        resource_id = str(node.get("resource_id")).strip()
        record_type = str(
            node.get("record_type") or node.get("event_name") or node.get("type") or ""
        )
        status = (
            str(
                node.get("result")
                or node.get("status")
                or node.get("account_status")
                or node.get("state")
                or ""
            )
            .strip()
            .upper()
        )
        category = classify_category(collection, record_type, system, resource_id, file_path)
        system = normalize_system_id(system) or system_for_category(category)
        if status == "" and "restore_allowed" in node:
            status = (
                "ACTIVE"
                if str(node.get("restore_allowed")).casefold() in {"1", "true", "yes"}
                else "BLOCKED"
            )
        elif status == "" and "enabled" in node:
            status = (
                "ACTIVE"
                if str(node.get("enabled")).casefold() in {"1", "true", "yes"}
                else "DISABLED"
            )
        values = tuple(_flatten_values(node))
        kind = (
            "flow"
            if "connector" in collection.casefold() or "data_flow" in resource_id.casefold()
            else classify_kind(category, resource_id)
        )
        yield EvidenceRecord(
            evidence_id=evidence_id,
            file_path=file_path,
            source_type="json",
            captured_at=captured_at,
            observed_at=observed,
            system_id=system,
            resource_id=resource_id,
            data_category=category,
            kind=kind,
            replica=None,
            status=status,
            identifiers_present=direct_identifier_fields(node),
            raw=dict(node),
            text=" ".join(values),
        )

    for key, value in node.items():
        if isinstance(value, (Mapping, list)):
            next_system = system
            if key in {"service_exports", "systems", "services"} and isinstance(value, Mapping):
                for service_name, service_value in value.items():
                    yield from _walk_records(
                        service_value,
                        evidence_id=evidence_id,
                        file_path=file_path,
                        captured_at=captured_at,
                        system_hint=str(service_name),
                        collection_hint=collection,
                        time_hint=observed,
                        source_path=f"{source_path}.{key}.{service_name}",
                    )
                continue
            yield from _walk_records(
                value,
                evidence_id=evidence_id,
                file_path=file_path,
                captured_at=captured_at,
                system_hint=next_system,
                collection_hint=collection or (str(key) if key not in _CONTEXT_KEYS else ""),
                time_hint=observed,
                source_path=f"{source_path}.{key}",
            )


def parse_records_text(
    text: str,
    *,
    evidence_id: str = "",
    file_path: str = "",
    captured_at: datetime | None = None,
) -> list[EvidenceRecord]:
    """Parse JSON text, accepting records at the root or under snapshots."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LoaderError(
            f"Evidence JSON is malformed at line {exc.lineno}, column {exc.colno}",
            path=file_path or None,
            hint="Check the evidence export; the remaining files can still be processed.",
        ) from None
    root_time = None
    if isinstance(payload, Mapping):
        root_time = _record_time(payload, None, file_path)
    records = list(
        _walk_records(
            payload,
            evidence_id=evidence_id,
            file_path=file_path,
            captured_at=captured_at,
            time_hint=root_time,
        )
    )
    # A nested record can be encountered through both a wrapper and its list;
    # collapse only exact same resource/time observations from the same source.
    unique: dict[tuple[str, datetime | None, str], EvidenceRecord] = {}
    for record in records:
        unique[(record.resource_id, record.observed_at, record.system_id)] = record
    return list(unique.values())


def load_records_file(
    path: str | Path,
    *,
    evidence_id: str = "",
    captured_at: datetime | None = None,
) -> list[EvidenceRecord]:
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise LoaderError(f"Could not read evidence JSON ({exc})", path=str(file_path)) from None
    except UnicodeDecodeError:
        raise LoaderError("Evidence JSON is not readable UTF-8 text", path=str(file_path)) from None
    return parse_records_text(
        text,
        evidence_id=evidence_id,
        file_path=str(file_path),
        captured_at=captured_at,
    )


__all__ = ["EvidenceRecord", "load_records_file", "parse_records_text"]
