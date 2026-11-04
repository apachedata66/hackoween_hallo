"""Golden tests for the shared data contract (joint task J1).

The contract is what lets Person A and Person B work in parallel, so any
change that breaks these tests is a change that needs both people's agreement
(see docs/DECISIONS.md).
"""

from __future__ import annotations

import json

from ghostdata.contract import (
    ALLOWED_PAIRS,
    OPERATION_ORDER,
    PHASE_ORDER,
    CaseAuditInput,
    DeletionStatus,
    Operation,
    Phase,
    ResolvedIdentity,
    ResourceState,
    is_allowed,
)


def test_allowed_pairs_are_exactly_the_fifteen_from_the_spec() -> None:
    assert len(ALLOWED_PAIRS) == 15
    # Each of the 15 operations appears in exactly one (phase, state) pair.
    assert len({op for _, op, _ in ALLOWED_PAIRS}) == 15


def test_every_allowed_pair_is_ordered_by_the_official_table() -> None:
    # Phase order and within-phase operation order must match the spec table.
    assert PHASE_ORDER == (Phase.FINDING, Phase.REMEDIATION, Phase.VERIFICATION)
    assert OPERATION_ORDER[Phase.FINDING] == (
        Operation.REPORT_REMAINING_RECORD,
        Operation.REPORT_EXPOSED_PII,
        Operation.REPORT_ACTIVE_DATA_FLOW,
        Operation.REPORT_RESTORE_RISK,
    )
    assert OPERATION_ORDER[Phase.REMEDIATION] == (
        Operation.DISABLE_DATA_FLOW,
        Operation.BLOCK_RESTORE,
        Operation.DELETE_RECORD,
        Operation.REDACT_RECORD,
        Operation.ANONYMIZE_RECORD,
    )
    assert OPERATION_ORDER[Phase.VERIFICATION] == (
        Operation.VERIFY_RECORD_ABSENT,
        Operation.VERIFY_RECORD_PRESENT,
        Operation.VERIFY_RECORD_REDACTED,
        Operation.VERIFY_RECORD_ANONYMIZED,
        Operation.VERIFY_DATA_FLOW_DISABLED,
        Operation.VERIFY_RESTORE_BLOCKED,
    )


def test_is_allowed_rejects_invalid_triples() -> None:
    assert is_allowed("FINDING", "REPORT_REMAINING_RECORD", "PRESENT")
    # Wrong state for this operation.
    assert not is_allowed("FINDING", "REPORT_REMAINING_RECORD", "ABSENT")
    # Right state, wrong phase.
    assert not is_allowed("REMEDIATION", "REPORT_REMAINING_RECORD", "PRESENT")
    # Invented operation / phase / state.
    assert not is_allowed("FINDING", "MAKE_COFFEE", "PRESENT")
    assert not is_allowed("PLANNING", "DELETE_RECORD", "ABSENT")
    assert not is_allowed("FINDING", "DELETE_RECORD", "SOMEWHERE")


def test_deletion_status_values() -> None:
    assert {s.value for s in DeletionStatus} == {"COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"}


def test_dataclasses_round_trip_to_json() -> None:
    identity = ResolvedIdentity(
        case_id="case_001",
        user_ids=["user_01"],
        emails_current=["a@example.com"],
        emails_historical=["old@example.com"],
        email_hashes=["0" * 64],
        other_identifiers={"phone": "+1 555 000 0000"},
        identity_evidence_ids=["audit_01"],
    )
    resource = ResourceState(
        system_id="account_service",
        resource_id="account_005",
        kind="record",
        data_category="USER_PROFILE",
        exists_at_audit=True,
        identifiers_present=["email"],
        is_active_flow=False,
        can_restore_user_data=False,
        replica="primary",
        evidence_id="evidence_54",
        notes="row still present in snapshot",
        confidence=1.0,
    )
    case = CaseAuditInput(
        request={"case_id": "case_001", "email": "a@example.com"},
        identity=identity,
        resources=[resource],
        warnings=["unreadable pdf"],
    )

    payload = json.loads(json.dumps(case.to_dict()))
    assert payload["identity"]["user_ids"] == ["user_01"]
    assert payload["resources"][0]["replica"] == "primary"
    assert payload["warnings"] == ["unreadable pdf"]

    # Defaults: warnings optional.
    minimal = CaseAuditInput(request={}, identity=identity, resources=[])
    assert minimal.warnings == []
