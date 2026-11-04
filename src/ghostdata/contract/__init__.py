"""Shared data contract (A <-> B). See dataclasses.py and enums.py."""

from ghostdata.contract.dataclasses import (
    CaseAuditInput,
    ResolvedIdentity,
    ResourceState,
)
from ghostdata.contract.enums import (
    ALLOWED_PAIRS,
    OPERATION_ORDER,
    PHASE_ORDER,
    DeletionStatus,
    Operation,
    Phase,
    State,
    is_allowed,
)

__all__ = [
    "ALLOWED_PAIRS",
    "OPERATION_ORDER",
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
