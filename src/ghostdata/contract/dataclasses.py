"""Shared data contract between Person A and Person B (playbook section 5, J1).

A (Data & Evidence Engine) produces these objects; B (Policy, Output &
Experience) consumes them.

Rules of change (agreed in docs/DECISIONS.md):
  * Add fields freely.
  * Never rename or remove a field silently - both people must agree and the
    change must be recorded in docs/DECISIONS.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from ghostdata.contract.enums import (
    ALLOWED_PAIRS,
    PHASE_ORDER,
    DeletionStatus,
    Operation,
    Phase,
    State,
    is_allowed,
)


@dataclass
class ResolvedIdentity:
    """Every identifier that belongs to the person behind one case."""

    case_id: str
    user_ids: list[str]  # internal ids (may be more than one)
    emails_current: list[str]
    emails_historical: list[str]  # from user_audit_log, in order of change
    email_hashes: list[str]  # all hash variants found
    other_identifiers: dict[str, Any] = field(default_factory=dict)  # phone, name, etc.
    identity_evidence_ids: list[str] = field(default_factory=list)  # audit ids supporting each link

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResourceState:
    """One resource's true state at the case's audit_at."""

    system_id: str  # e.g. account_service
    resource_id: str  # e.g. account_005
    kind: str  # record | tombstone | flow | backup | index | export ...
    data_category: str  # matches a data_category in deletion_rules.csv
    exists_at_audit: bool
    identifiers_present: list[str]  # direct identifiers still present (email, phone, ...)
    is_active_flow: bool  # for sync/import/export jobs
    can_restore_user_data: bool  # for backups/restore paths
    replica: str | None  # primary | regional | reporting | failover | None
    evidence_id: str  # file_id / activity_id / audit_id that proves this state
    notes: str  # human-readable reason (feeds the UI explanation)
    confidence: float = 1.0  # lower when evidence is inferred from OCR etc.
    timeline: list[dict[str, Any]] = field(default_factory=list)  # time-bounded evidence and claims

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseAuditInput:
    """Everything the rest of the pipeline (and the UI) needs for one case."""

    request: dict[str, Any]  # the original deletion_requests.csv row
    identity: ResolvedIdentity
    resources: list[ResourceState]
    warnings: list[str] = field(default_factory=list)  # unreadable files, ambiguity

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": dict(self.request),
            "identity": self.identity.to_dict(),
            "resources": [r.to_dict() for r in self.resources],
            "warnings": list(self.warnings),
        }


__all__ = [
    "ALLOWED_PAIRS",
    "PHASE_ORDER",
    "CaseAuditInput",
    "DeletionStatus",
    "Operation",
    "Phase",
    "ResolvedIdentity",
    "ResourceState",
    "State",
    "is_allowed",
]
