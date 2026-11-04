"""Rebuild per-resource state and an evidence timeline at ``audit_at``."""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

from ghostdata.contract import ResolvedIdentity, ResourceState
from ghostdata.identity.email import contains_identifier
from ghostdata.loaders.activity_csv import ActivityEvent
from ghostdata.loaders.evidence_index import EvidenceMatch
from ghostdata.loaders.evidence_models import EvidenceRecord, classify_category, classify_kind

_RESOURCE_RE = re.compile(
    r"\b(?:account|analytics|support|search|cache|export|backup|tombstone|audit_record|"
    r"email_delivery|data_flow|connector|marketing|telemetry|legal_hold)_"
    r"(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]+\b",
    re.I,
)
_ABSENT = frozenset(
    {
        "NOT FOUND",
        "NOT PRESENT",
        "ABSENT",
        "MISSING",
        "NO RECORD",
        "404",
        "0 ROWS",
        "MISS",
        "DELETED",
        "REMOVED",
        "PURGED",
    }
)
_PRESENT = frozenset(
    {"FOUND", "HIT", "PRESENT", "IDENTIFIABLE", "REDACTED", "ANONYMIZED", "RETAINED"}
)


def _identity_tokens(identity: ResolvedIdentity) -> list[str]:
    values = (
        identity.user_ids
        + identity.emails_current
        + identity.emails_historical
        + identity.email_hashes
        + (
            [str(identity.other_identifiers["name"])]
            if identity.other_identifiers.get("name")
            else []
        )
        + (
            [str(identity.other_identifiers["phone"])]
            if identity.other_identifiers.get("phone")
            else []
        )
        + [str(value) for value in identity.other_identifiers.get("phone_history", [])]
    )
    return sorted({value.strip().casefold() for value in values if value and value.strip()})


def _contains_identifier(text: str, identifiers: Sequence[str]) -> bool:
    for identifier in identifiers:
        if contains_identifier(text, identifier):
            return True
    return False


def _claim_for_event(event: ActivityEvent) -> str:
    """Summarize the event's stated result without treating it as verified."""
    detail = event.details.casefold()
    if event.event_type == "CHECK_DATA_FLOW":
        if any(term in detail for term in ("remains enabled", "still enabled", "is enabled")):
            return "ACTIVE"
        if any(term in detail for term in ("disabled", "not enabled", "inactive")):
            return "DISABLED"
    elif event.event_type == "CHECK_RESTORE_ACCESS":
        if any(
            term in detail
            for term in ("can still be restored", "restore is allowed", "can be restored")
        ):
            return "ACTIVE"
        if any(term in detail for term in ("blocked", "cannot be restored", "not restorable")):
            return "BLOCKED"
    elif event.event_type == "RESTORE_BACKUP":
        return "RESTORED"
    elif event.event_type == "LINK_RESOURCE_IDENTITY":
        return "LINKED"
    if event.event_type in {
        "DISABLE_DATA_FLOW",
        "BLOCK_RESTORE",
        "DELETE_RECORD",
        "REDACT_RECORD",
        "ANONYMIZE_RECORD",
    }:
        return "ACTION_REPORTED"
    if event.event_type in {
        "SYNC_RECORD",
        "INDEX_RECORD",
        "UPDATE_RECORD",
        "CREATE_EXPORT",
        "REFRESH_CACHE",
    }:
        return "WRITE_REPORTED"
    return ""


def _activity_observations(
    events: Iterable[ActivityEvent],
    identity: ResolvedIdentity,
    audit_at: datetime,
    linked_resource_ids: Iterable[str],
) -> list[EvidenceMatch]:
    """Promote explicit flow/restore checks and resource links to observations.

    These remain marked as operational claims and receive lower confidence;
    they never override stronger SQL/JSON evidence at the same timestamp.
    """
    tokens = _identity_tokens(identity)
    linked = {resource.casefold() for resource in linked_resource_ids if resource}
    matches: list[EvidenceMatch] = []
    for event in events:
        if event.event_time > audit_at:
            continue
        direct = _contains_identifier(event.details, tokens)
        if not direct and event.resource_id.casefold() not in linked:
            continue
        claim = _claim_for_event(event)
        if event.event_type == "CHECK_DATA_FLOW" and claim in {"ACTIVE", "DISABLED"}:
            kind, category, system = "flow", "UNKNOWN", event.target_system or event.source_system
        elif event.event_type == "CHECK_RESTORE_ACCESS" and claim in {"ACTIVE", "BLOCKED"}:
            kind, category, system = (
                "backup",
                "BACKUP_ARCHIVE",
                event.target_system or event.source_system,
            )
        elif event.event_type == "LINK_RESOURCE_IDENTITY" and event.resource_id:
            category = classify_category(event.target_system, event.resource_id, event.details)
            kind = classify_kind(category, event.resource_id)
            system = event.target_system or event.source_system
            claim = "PRESENT"
        else:
            continue
        resource_id = event.resource_id
        raw = {
            "state_claim": claim,
            "details": event.details,
            "reported_result": event.reported_result,
        }
        record = EvidenceRecord(
            evidence_id=event.activity_id,
            file_path="system_activity.csv",
            source_type="activity",
            captured_at=event.event_time,
            observed_at=event.event_time,
            system_id=system,
            resource_id=resource_id,
            data_category=category,
            kind=kind,
            replica=None,
            status=claim,
            raw=raw,
            text=event.details,
            confidence=0.7,
        )
        # The matched identifier is useful when the activity is the only
        # participant-visible linkage between a person and a resource. A link
        # event establishes association, not that an identifier is stored in
        # the resource itself, so it must not become a direct-PII field label.
        values = [token for token in tokens if _contains_identifier(event.details, [token])]
        matched_identifiers = () if event.event_type == "LINK_RESOURCE_IDENTITY" else tuple(values)
        matches.append(EvidenceMatch(record, matched_identifiers))
    return matches


def replay_activity(
    events: Iterable[ActivityEvent],
    identity: ResolvedIdentity,
    audit_at: datetime,
    *,
    linked_resource_ids: Iterable[str] = (),
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Return the identity-linked, time-bounded activity timeline.

    ``reported_result`` is retained as a claim field. It never controls the
    resource state returned by :func:`reconstruct_resources`.
    """
    tokens = _identity_tokens(identity)
    linked = {item.casefold() for item in linked_resource_ids if item}
    timeline: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    ordered = sorted(events, key=lambda item: (item.event_time, item.activity_id))
    for event in ordered:
        if event.event_time > audit_at:
            continue
        related_ids = {event.resource_id.casefold()} if event.resource_id else set()
        related_ids.update(resource.casefold() for resource in _RESOURCE_RE.findall(event.details))
        direct_link = _contains_identifier(event.details, tokens)
        resource_link = bool(related_ids & linked)
        if not direct_link and not resource_link:
            continue
        claim = _claim_for_event(event)
        entry = {
            "evidence_id": event.activity_id,
            "event_time": event.event_time.isoformat().replace("+00:00", "Z"),
            "event_type": event.event_type,
            "source_system": event.source_system,
            "target_system": event.target_system,
            "resource_id": event.resource_id,
            "reported_result": event.reported_result,
            "state_claim": claim,
            "claim_only": True,
        }
        # A restore can repopulate a distinct downstream resource; include the
        # same event in its timeline as well as the named backup resource.
        targets = {(event.target_system or event.source_system, event.resource_id)}
        if event.event_type == "RESTORE_BACKUP":
            for resource in related_ids:
                if resource != event.resource_id.casefold():
                    targets.add((event.target_system, resource))
        for key in targets:
            if key[1]:
                timeline[key].append(entry)
    return {
        key: sorted(items, key=lambda item: (item["event_time"], item["evidence_id"]))
        for key, items in timeline.items()
    }


def _observation_exists(record: EvidenceRecord) -> bool | None:
    status = record.status.strip().upper().replace("_", " ")
    if (
        record.data_category == "ACCOUNT_TOMBSTONE"
        and str(record.raw.get("account_status", "")).strip().upper() == "DELETED"
    ):
        # This field describes the account's lifecycle, not the existence of
        # the deleted-customer-reference row that preserves retained links.
        return True
    if status in _ABSENT:
        return False
    if status in _PRESENT:
        return True
    if record.kind == "flow" and status in {"ACTIVE", "ENABLED", "TRUE", "1"}:
        return True
    if record.kind == "backup" and status in {"ACTIVE", "RESTORABLE", "ALLOWED", "TRUE", "1"}:
        return True
    # A captured row, log entry, or identified attachment is itself present.
    if record.resource_id and (record.raw or record.text):
        return True
    return None


def _is_true(value: Any) -> bool:
    return str(value or "").strip().casefold() in {
        "1",
        "true",
        "yes",
        "enabled",
        "active",
        "allowed",
    }


def _matched_pii_labels(match: EvidenceMatch, identity: ResolvedIdentity) -> set[str]:
    labels = set(match.record.identifiers_present)
    lower_matches = {value.casefold() for value in match.matched_identifiers}
    if lower_matches & {
        email.casefold() for email in identity.emails_current + identity.emails_historical
    }:
        labels.add("email")
    if lower_matches & {value.casefold() for value in identity.email_hashes}:
        labels.add("email_hash")
    other = identity.other_identifiers
    phones = [str(other.get("phone", "")), *[str(x) for x in other.get("phone_history", [])]]
    if lower_matches & {value.casefold() for value in phones if value}:
        labels.add("phone")
    if other.get("name") and str(other["name"]).casefold() in lower_matches:
        labels.add("name")
    return labels


def _source_priority(record: EvidenceRecord) -> int:
    return {"sql": 5, "json": 4, "document": 3, "text": 3, "log": 2, "activity": 1}.get(
        record.source_type, 0
    )


def reconstruct_resources(
    matches: Sequence[EvidenceMatch],
    identity: ResolvedIdentity,
    audit_at: datetime,
    *,
    activity_events: Iterable[ActivityEvent] = (),
) -> list[ResourceState]:
    """Choose each resource's latest direct observation at or before audit time."""
    activity_events = list(activity_events)
    eligible = [
        match
        for match in matches
        if (match.record.captured_at is None or match.record.captured_at <= audit_at)
        and (match.record.observed_at is None or match.record.observed_at <= audit_at)
        and match.record.resource_id
    ]
    linked_ids = [match.record.resource_id for match in eligible]
    eligible.extend(_activity_observations(activity_events, identity, audit_at, linked_ids))
    # Activity observations can refer to identifiers in resource-linked events.
    linked_ids = [match.record.resource_id for match in eligible]
    timelines = replay_activity(activity_events, identity, audit_at, linked_resource_ids=linked_ids)
    groups: dict[tuple[str, str, str | None], list[EvidenceMatch]] = defaultdict(list)
    for match in eligible:
        record = match.record
        groups[(record.system_id, record.resource_id, record.replica)].append(match)

    resources: list[ResourceState] = []
    for (system_id, resource_id, replica), history in sorted(
        groups.items(), key=lambda item: (item[0][0], item[0][1], item[0][2] or "")
    ):
        history.sort(
            key=lambda match: (
                match.record.effective_time or datetime.min.replace(tzinfo=audit_at.tzinfo),
                _source_priority(match.record),
                match.record.evidence_id,
            )
        )
        selected = history[-1]
        record = selected.record
        exists = _observation_exists(record)
        if exists is None:
            exists = True
        category = record.data_category or "UNKNOWN"
        kind = record.kind or classify_kind(category, resource_id)
        is_flow = kind == "flow"
        is_backup = kind == "backup"
        status = record.status.upper()
        active = is_flow and (
            status in {"ACTIVE", "ENABLED", "TRUE", "1"} or _is_true(record.raw.get("enabled"))
        )
        restore = is_backup and (
            status in {"ACTIVE", "RESTORABLE", "ALLOWED", "TRUE", "1"}
            or _is_true(record.raw.get("restore_allowed"))
        )
        direct_fields = set(record.identifiers_present)
        coeval_hits = [hit for hit in history if hit.record.effective_time == record.effective_time]
        for hit in coeval_hits:
            direct_fields.update(_matched_pii_labels(hit, identity))
        history_timeline = [
            {
                "evidence_id": hit.record.evidence_id,
                "event_time": (hit.record.effective_time or audit_at)
                .isoformat()
                .replace("+00:00", "Z"),
                "event_type": f"{hit.record.source_type.upper()}_OBSERVATION",
                "state_claim": hit.record.status
                or ("PRESENT" if _observation_exists(hit.record) else "UNKNOWN"),
                "claim_only": hit.record.source_type in {"log", "activity"},
            }
            for hit in history
        ]
        for (_activity_system, activity_resource), entries in timelines.items():
            if activity_resource == resource_id:
                history_timeline.extend(entries)
        history_timeline.sort(key=lambda item: (item["event_time"], item["evidence_id"]))
        notes = (
            f"Latest matching evidence is {record.source_type} captured at "
            f"{(record.effective_time or record.captured_at or audit_at).isoformat()} UTC."
        )
        if category == "UNKNOWN":
            notes += " The data category could not be mapped to a supplied deletion rule."
        if record.source_type in {"log", "activity"}:
            notes += (
                " The source is an operational log and may describe a claim rather than "
                "a verified store state."
            )
        resources.append(
            ResourceState(
                system_id=system_id,
                resource_id=resource_id,
                kind=kind,
                data_category=category,
                exists_at_audit=bool(exists),
                identifiers_present=sorted(direct_fields),
                is_active_flow=active,
                can_restore_user_data=restore,
                replica=replica,
                evidence_id=record.evidence_id,
                notes=notes,
                confidence=record.confidence,
                timeline=history_timeline,
            )
        )
    return sorted(
        resources, key=lambda item: (item.system_id, item.resource_id, item.replica or "")
    )


__all__ = ["reconstruct_resources", "replay_activity"]
