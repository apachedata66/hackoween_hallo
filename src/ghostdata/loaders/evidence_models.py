"""Normalized evidence types shared by the non-CSV evidence loaders."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EvidenceRecord:
    """One participant-visible observation tied to a file and resource."""

    evidence_id: str
    file_path: str
    source_type: str
    captured_at: datetime | None
    observed_at: datetime | None
    system_id: str
    resource_id: str
    data_category: str
    kind: str
    replica: str | None
    status: str
    identifiers_present: tuple[str, ...] = ()
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    text: str = field(default="", repr=False)
    confidence: float = 1.0

    @property
    def effective_time(self) -> datetime | None:
        """The record time, falling back to the file capture time."""
        if self.source_type == "sql":
            return self.captured_at or self.observed_at
        return self.observed_at or self.captured_at


@dataclass(frozen=True)
class EvidenceWarning:
    """A non-fatal parsing or extraction problem safe to surface to users."""

    evidence_id: str
    message: str


_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ACCOUNT_TOMBSTONE", ("tombstone", "deleted_customer_reference")),
    ("BACKUP_ARCHIVE", ("backup", "restore_archive", "restore_entry")),
    ("LEGAL_HOLD_RECORD", ("legal_hold", "legal_retention", "legal retention", "hold record")),
    ("SECURITY_AUDIT_LOG", ("security_audit", "security audit", "audit_record", "audit log")),
    ("SUPPORT_ATTACHMENT", ("support_attachment", "support attachment", "attachment")),
    (
        "SUPPORT_MESSAGE",
        (
            "support_message",
            "support message",
            "support_record",
            "support_platform",
            "conversation",
        ),
    ),
    ("ANALYTICS_PROFILE", ("analytics_profile", "analytics profile", "analytics_platform")),
    ("PRODUCT_TELEMETRY", ("product_telemetry", "telemetry")),
    ("SEARCH_INDEX_ENTRY", ("search_index", "search_document", "search index", "index_entry")),
    ("CACHE_ENTRY", ("cache_entry", "cache record", "cache_service")),
    ("USER_EXPORT", ("user_export", "customer_export", "export_service", "export file")),
    ("MARKETING_PROFILE", ("marketing_profile", "marketing profile")),
    ("EMAIL_DELIVERY_LOG", ("email_delivery", "email delivery", "delivery_log")),
    (
        "SECONDARY_IDENTIFIER",
        ("secondary_identifier", "identity_lookup", "identity_record", "legacy_contact_index"),
    ),
    ("USER_PROFILE", ("user_profile", "customer_profile", "account_service", "account profile")),
)

_DIRECT_FIELD_NAMES = frozenset(
    {
        "name",
        "full_name",
        "display_name",
        "customer_name",
        "requester_name",
        "owner_name",
        "recipient_name",
        "email",
        "customer_email",
        "requester_email",
        "owner_email",
        "recipient_email",
        "phone",
        "customer_phone",
        "requester_phone",
        "owner_phone",
        "recipient_phone",
        "email_hash",
    }
)


def classify_category(*hints: str) -> str:
    """Map evidence labels to the policy category names used by the dataset."""
    text = " ".join(str(item or "") for item in hints).casefold().replace("-", "_")
    for category, terms in _CATEGORY_RULES:
        if any(term.casefold().replace("-", "_") in text for term in terms):
            return category
    return ""


def classify_kind(category: str, resource_id: str = "", event_type: str = "") -> str:
    """Return a stable, UI-friendly resource kind."""
    if event_type in {"CHECK_DATA_FLOW", "DISABLE_DATA_FLOW"} or any(
        token in resource_id.casefold() for token in ("data_flow", "connector")
    ):
        return "flow"
    if event_type in {"CHECK_RESTORE_ACCESS", "BLOCK_RESTORE", "RESTORE_BACKUP"}:
        return "backup"
    if category == "ACCOUNT_TOMBSTONE":
        return "tombstone"
    if category == "BACKUP_ARCHIVE":
        return "backup"
    if category in {"SEARCH_INDEX_ENTRY", "CACHE_ENTRY", "USER_EXPORT"}:
        return {"SEARCH_INDEX_ENTRY": "index", "CACHE_ENTRY": "cache", "USER_EXPORT": "export"}[
            category
        ]
    return "record"


def normalize_system_id(system_id: str) -> str:
    """Normalize service names that point at a policy system's replica."""
    value = (system_id or "").strip()
    return {
        "profile_service": "account_service",
        "search_index_service": "search_service",
        "support_replica": "support_platform",
        "email_service": "email_delivery_service",
    }.get(value.casefold(), value)


def system_for_category(category: str) -> str:
    return {
        "USER_PROFILE": "account_service",
        "SECONDARY_IDENTIFIER": "identity_service",
        "SEARCH_INDEX_ENTRY": "search_service",
        "CACHE_ENTRY": "cache_service",
        "SUPPORT_MESSAGE": "support_platform",
        "SUPPORT_ATTACHMENT": "support_platform",
        "ANALYTICS_PROFILE": "analytics_platform",
        "PRODUCT_TELEMETRY": "analytics_platform",
        "USER_EXPORT": "export_service",
        "MARKETING_PROFILE": "marketing_service",
        "EMAIL_DELIVERY_LOG": "email_delivery_service",
        "SECURITY_AUDIT_LOG": "security_service",
        "LEGAL_HOLD_RECORD": "legal_service",
        "BACKUP_ARCHIVE": "backup_service",
        "ACCOUNT_TOMBSTONE": "identity_service",
    }.get(category, "")


def direct_identifier_fields(raw: Any) -> tuple[str, ...]:
    """List direct-identifier field names populated in a nested record."""
    found: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"[^a-z0-9_]+", "_", str(key).casefold()).strip("_")
                if normalized in _DIRECT_FIELD_NAMES and item not in (None, "", [], {}):
                    found.add("email_hash" if normalized == "email_hash" else normalized)
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)

    walk(raw)
    return tuple(sorted(found))


__all__ = [
    "EvidenceRecord",
    "EvidenceWarning",
    "classify_category",
    "classify_kind",
    "direct_identifier_fields",
    "normalize_system_id",
    "system_for_category",
]
