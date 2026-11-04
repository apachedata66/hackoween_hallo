"""Output contract: allowed steps, ordering, and the shared audit types.

An invalid phase, operation, and state combination cannot be constructed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class Phase(str, Enum):
    FINDING = "FINDING"
    REMEDIATION = "REMEDIATION"
    VERIFICATION = "VERIFICATION"


class Operation(str, Enum):
    REPORT_REMAINING_RECORD = "REPORT_REMAINING_RECORD"
    REPORT_EXPOSED_PII = "REPORT_EXPOSED_PII"
    REPORT_ACTIVE_DATA_FLOW = "REPORT_ACTIVE_DATA_FLOW"
    REPORT_RESTORE_RISK = "REPORT_RESTORE_RISK"
    DISABLE_DATA_FLOW = "DISABLE_DATA_FLOW"
    BLOCK_RESTORE = "BLOCK_RESTORE"
    DELETE_RECORD = "DELETE_RECORD"
    REDACT_RECORD = "REDACT_RECORD"
    ANONYMIZE_RECORD = "ANONYMIZE_RECORD"
    VERIFY_RECORD_ABSENT = "VERIFY_RECORD_ABSENT"
    VERIFY_RECORD_PRESENT = "VERIFY_RECORD_PRESENT"
    VERIFY_RECORD_REDACTED = "VERIFY_RECORD_REDACTED"
    VERIFY_RECORD_ANONYMIZED = "VERIFY_RECORD_ANONYMIZED"
    VERIFY_DATA_FLOW_DISABLED = "VERIFY_DATA_FLOW_DISABLED"
    VERIFY_RESTORE_BLOCKED = "VERIFY_RESTORE_BLOCKED"


class State(str, Enum):
    PRESENT = "PRESENT"
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    BLOCKED = "BLOCKED"
    ABSENT = "ABSENT"
    REDACTED = "REDACTED"
    ANONYMIZED = "ANONYMIZED"


class DeletionStatus(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


# Official allowed triples. Nothing else is valid.
ALLOWED_STEPS: dict[tuple[Phase, Operation], State] = {
    (Phase.FINDING, Operation.REPORT_REMAINING_RECORD): State.PRESENT,
    (Phase.FINDING, Operation.REPORT_EXPOSED_PII): State.PRESENT,
    (Phase.FINDING, Operation.REPORT_ACTIVE_DATA_FLOW): State.ACTIVE,
    (Phase.FINDING, Operation.REPORT_RESTORE_RISK): State.ACTIVE,
    (Phase.REMEDIATION, Operation.DISABLE_DATA_FLOW): State.DISABLED,
    (Phase.REMEDIATION, Operation.BLOCK_RESTORE): State.BLOCKED,
    (Phase.REMEDIATION, Operation.DELETE_RECORD): State.ABSENT,
    (Phase.REMEDIATION, Operation.REDACT_RECORD): State.REDACTED,
    (Phase.REMEDIATION, Operation.ANONYMIZE_RECORD): State.ANONYMIZED,
    (Phase.VERIFICATION, Operation.VERIFY_RECORD_ABSENT): State.ABSENT,
    (Phase.VERIFICATION, Operation.VERIFY_RECORD_PRESENT): State.PRESENT,
    (Phase.VERIFICATION, Operation.VERIFY_RECORD_REDACTED): State.REDACTED,
    (Phase.VERIFICATION, Operation.VERIFY_RECORD_ANONYMIZED): State.ANONYMIZED,
    (Phase.VERIFICATION, Operation.VERIFY_DATA_FLOW_DISABLED): State.DISABLED,
    (Phase.VERIFICATION, Operation.VERIFY_RESTORE_BLOCKED): State.BLOCKED,
}

PHASE_RANK: dict[Phase, int] = {
    Phase.FINDING: 0,
    Phase.REMEDIATION: 1,
    Phase.VERIFICATION: 2,
}

# Order inside a phase follows the official table, top to bottom.
OPERATION_RANK: dict[Phase, dict[Operation, int]] = {
    phase: {
        operation: index
        for index, (pair_phase, operation) in enumerate(ALLOWED_STEPS)
        if pair_phase is phase
    }
    for phase in Phase
}

STEP_FIELDS = (
    "step_no",
    "phase",
    "system_id",
    "resource_id",
    "operation",
    "state",
    "evidence_id",
)

DIRECT_IDENTIFIERS = ("name", "email", "phone", "email_hash")


def _as_enum(cls: type[Enum], value: object, label: str) -> Enum:
    if isinstance(value, cls):
        return value
    try:
        return cls(str(value))
    except ValueError as exc:
        allowed = ", ".join(item.value for item in cls)  # type: ignore[attr-defined]
        raise ValueError(f"{label} {value!r} is not one of: {allowed}") from exc


@dataclass(frozen=True)
class Step:
    """One finding, remediation, or verification row."""

    step_no: int
    phase: Phase
    system_id: str
    resource_id: str
    operation: Operation
    state: State
    evidence_id: str

    def __post_init__(self) -> None:
        phase = _as_enum(Phase, self.phase, "phase")
        operation = _as_enum(Operation, self.operation, "operation")
        state = _as_enum(State, self.state, "state")
        object.__setattr__(self, "phase", phase)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "state", state)
        expected = ALLOWED_STEPS.get((phase, operation))
        if expected is None or expected is not state:
            raise ValueError(
                f"{phase.value}/{operation.value}/{state.value} is not an allowed "
                "phase, operation, and state combination"
            )
        if not str(self.system_id).strip() or not str(self.resource_id).strip():
            raise ValueError("system_id and resource_id are required")
        object.__setattr__(self, "system_id", str(self.system_id).strip())
        object.__setattr__(self, "resource_id", str(self.resource_id).strip())
        object.__setattr__(self, "evidence_id", "" if self.evidence_id is None else str(self.evidence_id))
        if isinstance(self.step_no, bool) or not isinstance(self.step_no, int):
            raise ValueError("step_no must be an integer")

    def to_dict(self) -> dict[str, object]:
        return {
            "step_no": self.step_no,
            "phase": self.phase.value,
            "system_id": self.system_id,
            "resource_id": self.resource_id,
            "operation": self.operation.value,
            "state": self.state.value,
            "evidence_id": self.evidence_id,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Step":
        missing = [key for key in STEP_FIELDS if key not in raw]
        if missing:
            raise ValueError(f"step is missing {', '.join(missing)}")
        extra = [key for key in raw if key not in STEP_FIELDS]
        if extra:
            raise ValueError(f"step has unknown fields: {', '.join(extra)}")
        return cls(
            step_no=raw["step_no"],
            phase=raw["phase"],
            system_id=raw["system_id"],
            resource_id=raw["resource_id"],
            operation=raw["operation"],
            state=raw["state"],
            evidence_id=raw["evidence_id"],
        )

    def identity(self) -> tuple[str, str, str, str]:
        return (self.phase.value, self.operation.value, self.system_id, self.resource_id)


def sort_key(step: Step) -> tuple[int, int, str, str]:
    """Plain Unicode string order for system_id and resource_id."""

    return (
        PHASE_RANK[step.phase],
        OPERATION_RANK[step.phase][step.operation],
        step.system_id,
        step.resource_id,
    )


def sort_steps(steps: list[Step]) -> list[Step]:
    return sorted(steps, key=sort_key)


def number_steps(steps: list[Step]) -> list[Step]:
    """Sort, then assign step_no from 1 with no gaps."""

    ordered = sort_steps(steps)
    return [
        Step(
            step_no=index,
            phase=step.phase,
            system_id=step.system_id,
            resource_id=step.resource_id,
            operation=step.operation,
            state=step.state,
            evidence_id=step.evidence_id,
        )
        for index, step in enumerate(ordered, start=1)
    ]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    deletion_status: DeletionStatus
    steps: tuple[Step, ...]

    def __post_init__(self) -> None:
        status = _as_enum(DeletionStatus, self.deletion_status, "deletion_status")
        object.__setattr__(self, "deletion_status", status)
        object.__setattr__(self, "case_id", str(self.case_id).strip())
        object.__setattr__(self, "steps", tuple(self.steps))

    def steps_payload(self) -> list[dict[str, object]]:
        return [step.to_dict() for step in self.steps]


@dataclass
class ResolvedIdentity:
    """Every identifier Person A could tie to this case, with proof."""

    case_id: str
    user_ids: list[str]
    emails_current: list[str]
    emails_historical: list[str]
    email_hashes: list[str]
    other_identifiers: dict[str, str] = field(default_factory=dict)
    identity_evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResourceState:
    """One resource as it existed at audit_at."""

    system_id: str
    resource_id: str
    kind: str
    data_category: str
    exists_at_audit: bool
    identifiers_present: list[str]
    is_active_flow: bool
    can_restore_user_data: bool
    replica: str | None
    evidence_id: str
    notes: str
    confidence: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CaseAuditInput:
    """What Person A hands Person B. reported_status is a claim, not an input to the verdict."""

    request: dict
    identity: ResolvedIdentity
    resources: list[ResourceState]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "request": self.request,
            "identity": self.identity.to_dict(),
            "resources": [resource.to_dict() for resource in self.resources],
            "warnings": list(self.warnings),
        }
