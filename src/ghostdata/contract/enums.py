"""Output-contract enums and tables (playbook section 3, problem_statement.md
"Allowed Operations", AGENTS.md 6.3-6.4).

Transcribed verbatim from the official spec - no invented operations, states
or phases. Person B owns the output contract (task B1); this is the shared,
machine-readable form agreed in J1 so an invalid pair cannot be constructed.
"""

from __future__ import annotations

from enum import StrEnum


class Phase(StrEnum):
    FINDING = "FINDING"
    REMEDIATION = "REMEDIATION"
    VERIFICATION = "VERIFICATION"


class Operation(StrEnum):
    # FINDING
    REPORT_REMAINING_RECORD = "REPORT_REMAINING_RECORD"
    REPORT_EXPOSED_PII = "REPORT_EXPOSED_PII"
    REPORT_ACTIVE_DATA_FLOW = "REPORT_ACTIVE_DATA_FLOW"
    REPORT_RESTORE_RISK = "REPORT_RESTORE_RISK"
    # REMEDIATION
    DISABLE_DATA_FLOW = "DISABLE_DATA_FLOW"
    BLOCK_RESTORE = "BLOCK_RESTORE"
    DELETE_RECORD = "DELETE_RECORD"
    REDACT_RECORD = "REDACT_RECORD"
    ANONYMIZE_RECORD = "ANONYMIZE_RECORD"
    # VERIFICATION
    VERIFY_RECORD_ABSENT = "VERIFY_RECORD_ABSENT"
    VERIFY_RECORD_PRESENT = "VERIFY_RECORD_PRESENT"
    VERIFY_RECORD_REDACTED = "VERIFY_RECORD_REDACTED"
    VERIFY_RECORD_ANONYMIZED = "VERIFY_RECORD_ANONYMIZED"
    VERIFY_DATA_FLOW_DISABLED = "VERIFY_DATA_FLOW_DISABLED"
    VERIFY_RESTORE_BLOCKED = "VERIFY_RESTORE_BLOCKED"


class State(StrEnum):
    PRESENT = "PRESENT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    BLOCKED = "BLOCKED"
    ABSENT = "ABSENT"
    REDACTED = "REDACTED"
    ANONYMIZED = "ANONYMIZED"


class DeletionStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# Strict sort order of phases in steps_json.
PHASE_ORDER: tuple[Phase, ...] = (Phase.FINDING, Phase.REMEDIATION, Phase.VERIFICATION)

# Operation order WITHIN each phase = the row order of the official table.
OPERATION_ORDER: dict[Phase, tuple[Operation, ...]] = {
    Phase.FINDING: (
        Operation.REPORT_REMAINING_RECORD,
        Operation.REPORT_EXPOSED_PII,
        Operation.REPORT_ACTIVE_DATA_FLOW,
        Operation.REPORT_RESTORE_RISK,
    ),
    Phase.REMEDIATION: (
        Operation.DISABLE_DATA_FLOW,
        Operation.BLOCK_RESTORE,
        Operation.DELETE_RECORD,
        Operation.REDACT_RECORD,
        Operation.ANONYMIZE_RECORD,
    ),
    Phase.VERIFICATION: (
        Operation.VERIFY_RECORD_ABSENT,
        Operation.VERIFY_RECORD_PRESENT,
        Operation.VERIFY_RECORD_REDACTED,
        Operation.VERIFY_RECORD_ANONYMIZED,
        Operation.VERIFY_DATA_FLOW_DISABLED,
        Operation.VERIFY_RESTORE_BLOCKED,
    ),
}

# The only legal (phase, operation, state) combinations - 15 in total.
ALLOWED_PAIRS: frozenset[tuple[Phase, Operation, State]] = frozenset(
    {
        # FINDING
        (Phase.FINDING, Operation.REPORT_REMAINING_RECORD, State.PRESENT),
        (Phase.FINDING, Operation.REPORT_EXPOSED_PII, State.PRESENT),
        (Phase.FINDING, Operation.REPORT_ACTIVE_DATA_FLOW, State.ACTIVE),
        (Phase.FINDING, Operation.REPORT_RESTORE_RISK, State.ACTIVE),
        # REMEDIATION
        (Phase.REMEDIATION, Operation.DISABLE_DATA_FLOW, State.DISABLED),
        (Phase.REMEDIATION, Operation.BLOCK_RESTORE, State.BLOCKED),
        (Phase.REMEDIATION, Operation.DELETE_RECORD, State.ABSENT),
        (Phase.REMEDIATION, Operation.REDACT_RECORD, State.REDACTED),
        (Phase.REMEDIATION, Operation.ANONYMIZE_RECORD, State.ANONYMIZED),
        # VERIFICATION
        (Phase.VERIFICATION, Operation.VERIFY_RECORD_ABSENT, State.ABSENT),
        (Phase.VERIFICATION, Operation.VERIFY_RECORD_PRESENT, State.PRESENT),
        (Phase.VERIFICATION, Operation.VERIFY_RECORD_REDACTED, State.REDACTED),
        (Phase.VERIFICATION, Operation.VERIFY_RECORD_ANONYMIZED, State.ANONYMIZED),
        (Phase.VERIFICATION, Operation.VERIFY_DATA_FLOW_DISABLED, State.DISABLED),
        (Phase.VERIFICATION, Operation.VERIFY_RESTORE_BLOCKED, State.BLOCKED),
    }
)


def is_allowed(phase: str | Phase, operation: str | Operation, state: str | State) -> bool:
    """True when the exact (phase, operation, state) triple is legal."""
    try:
        triple = (Phase(phase), Operation(operation), State(state))
    except ValueError:
        return False
    return triple in ALLOWED_PAIRS


__all__ = [
    "ALLOWED_PAIRS",
    "OPERATION_ORDER",
    "PHASE_ORDER",
    "DeletionStatus",
    "Operation",
    "Phase",
    "State",
    "is_allowed",
]
