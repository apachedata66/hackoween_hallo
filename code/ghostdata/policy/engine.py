"""Decide the required treatment for one resource. Does not invent categories."""

from __future__ import annotations

from dataclasses import dataclass

from ghostdata.contract.models import DIRECT_IDENTIFIERS, Operation, ResourceState, State
from ghostdata.policy.rules import RequiredAction, Rulebook


@dataclass(frozen=True)
class Assessment:
    """How one resource compares with the rule that covers it."""

    resource: ResourceState
    include: bool
    compliant: bool
    violation: str | None
    finding: tuple[Operation, State] | None
    remediation: tuple[Operation, State] | None
    verification: tuple[Operation, State] | None
    reason: str


def _prohibited(resource: ResourceState, permitted: frozenset[str] | None) -> list[str]:
    if permitted is None:
        return []
    present = []
    for identifier in resource.identifiers_present:
        if identifier in permitted:
            continue
        if identifier in DIRECT_IDENTIFIERS or identifier not in permitted:
            present.append(identifier)
    return present


def assess_resource(resource: ResourceState, rulebook: Rulebook) -> Assessment:
    """Map a resource to finding, remediation, and verification operations.

    Flows and backups are judged by their live risk, then the category rule.
    A category that is not in deletion_rules.csv produces a warning and no guess.
    """

    rule = rulebook.rule_for(resource.data_category)
    if rule is None and resource.kind not in {"flow", "backup"}:
        return Assessment(
            resource=resource,
            include=False,
            compliant=False,
            violation="unknown_category",
            finding=None,
            remediation=None,
            verification=None,
            reason=f"no deletion rule for category {resource.data_category}",
        )

    if resource.kind == "flow" or resource.is_active_flow:
        if resource.is_active_flow:
            return Assessment(
                resource=resource,
                include=True,
                compliant=False,
                violation="flow",
                finding=(Operation.REPORT_ACTIVE_DATA_FLOW, State.ACTIVE),
                remediation=(Operation.DISABLE_DATA_FLOW, State.DISABLED),
                verification=(Operation.VERIFY_DATA_FLOW_DISABLED, State.DISABLED),
                reason="an active flow can copy or recreate this person's data",
            )
        if resource.exists_at_audit:
            return Assessment(
                resource=resource,
                include=True,
                compliant=True,
                violation=None,
                finding=None,
                remediation=None,
                verification=(Operation.VERIFY_DATA_FLOW_DISABLED, State.DISABLED),
                reason="the data flow is inactive at audit time",
            )
        return Assessment(
            resource=resource,
            include=False,
            compliant=True,
            violation=None,
            finding=None,
            remediation=None,
            verification=None,
            reason="no data flow is in scope",
        )

    if resource.kind == "backup" or (rule is not None and rule.blocks_restore):
        if resource.can_restore_user_data:
            return Assessment(
                resource=resource,
                include=True,
                compliant=False,
                violation="restore",
                finding=(Operation.REPORT_RESTORE_RISK, State.ACTIVE),
                remediation=(Operation.BLOCK_RESTORE, State.BLOCKED),
                verification=(Operation.VERIFY_RESTORE_BLOCKED, State.BLOCKED),
                reason="a backup can still restore this person's data",
            )
        if resource.exists_at_audit:
            return Assessment(
                resource=resource,
                include=True,
                compliant=True,
                violation=None,
                finding=None,
                remediation=None,
                verification=(Operation.VERIFY_RESTORE_BLOCKED, State.BLOCKED),
                reason="restore from this backup is already blocked",
            )
        return Assessment(
            resource=resource,
            include=False,
            compliant=True,
            violation=None,
            finding=None,
            remediation=None,
            verification=None,
            reason="no restorable backup is in scope",
        )

    if rule is None:
        return Assessment(
            resource=resource,
            include=False,
            compliant=False,
            violation="unknown_category",
            finding=None,
            remediation=None,
            verification=None,
            reason=f"no deletion rule for category {resource.data_category}",
        )

    return _assess_record(resource, rule.required_action, rule.permitted_identifiers)


def _assess_record(
    resource: ResourceState,
    action: RequiredAction,
    permitted: frozenset[str] | None,
) -> Assessment:
    if action is RequiredAction.DELETE:
        if resource.exists_at_audit:
            return Assessment(
                resource=resource,
                include=True,
                compliant=False,
                violation="treatment",
                finding=(Operation.REPORT_REMAINING_RECORD, State.PRESENT),
                remediation=(Operation.DELETE_RECORD, State.ABSENT),
                verification=(Operation.VERIFY_RECORD_ABSENT, State.ABSENT),
                reason="a record that must be deleted still exists",
            )
        return Assessment(
            resource=resource,
            include=True,
            compliant=True,
            violation=None,
            finding=None,
            remediation=None,
            verification=(Operation.VERIFY_RECORD_ABSENT, State.ABSENT),
            reason="the record is already absent",
        )

    if action is RequiredAction.REDACT:
        # A missing tombstone is not automatically a violation. Person A includes
        # one only when a stable reference is actually required.
        if resource.kind == "tombstone" and not resource.exists_at_audit:
            return Assessment(
                resource=resource,
                include=False,
                compliant=True,
                violation=None,
                finding=None,
                remediation=None,
                verification=None,
                reason="no tombstone is present, and none is required",
            )
        if not resource.exists_at_audit:
            return Assessment(
                resource=resource,
                include=True,
                compliant=False,
                violation="missing_retain",
                finding=None,
                remediation=None,
                verification=(Operation.VERIFY_RECORD_REDACTED, State.REDACTED),
                reason="a record that must stay in redacted form is missing",
            )
        prohibited = _prohibited(resource, permitted)
        if prohibited:
            names = ", ".join(prohibited)
            return Assessment(
                resource=resource,
                include=True,
                compliant=False,
                violation="identifiers",
                finding=(Operation.REPORT_EXPOSED_PII, State.PRESENT),
                remediation=(Operation.REDACT_RECORD, State.REDACTED),
                verification=(Operation.VERIFY_RECORD_REDACTED, State.REDACTED),
                reason=f"direct identifiers still present: {names}",
            )
        return Assessment(
            resource=resource,
            include=True,
            compliant=True,
            violation=None,
            finding=None,
            remediation=None,
            verification=(Operation.VERIFY_RECORD_REDACTED, State.REDACTED),
            reason="only permitted identifiers remain",
        )

    if action is RequiredAction.ANONYMIZE:
        if not resource.exists_at_audit:
            return Assessment(
                resource=resource,
                include=True,
                compliant=True,
                violation=None,
                finding=None,
                remediation=None,
                verification=(Operation.VERIFY_RECORD_ABSENT, State.ABSENT),
                reason="the record is gone, so it can no longer be linked to the user",
            )
        prohibited = _prohibited(resource, permitted)
        if prohibited:
            names = ", ".join(prohibited)
            return Assessment(
                resource=resource,
                include=True,
                compliant=False,
                violation="identifiers",
                finding=(Operation.REPORT_EXPOSED_PII, State.PRESENT),
                remediation=(Operation.ANONYMIZE_RECORD, State.ANONYMIZED),
                verification=(Operation.VERIFY_RECORD_ANONYMIZED, State.ANONYMIZED),
                reason=f"the record can still be linked to the user via {names}",
            )
        return Assessment(
            resource=resource,
            include=True,
            compliant=True,
            violation=None,
            finding=None,
            remediation=None,
            verification=(Operation.VERIFY_RECORD_ANONYMIZED, State.ANONYMIZED),
            reason="the record can no longer be linked to the user",
        )

    # RETAIN
    if not resource.exists_at_audit:
        return Assessment(
            resource=resource,
            include=True,
            compliant=False,
            violation="missing_retain",
            finding=None,
            remediation=None,
            verification=(Operation.VERIFY_RECORD_PRESENT, State.PRESENT),
            reason="a record the policy requires us to keep is missing",
        )
    return Assessment(
        resource=resource,
        include=True,
        compliant=True,
        violation=None,
        finding=None,
        remediation=None,
        verification=(Operation.VERIFY_RECORD_PRESENT, State.PRESENT),
        reason="the required record is still available",
    )
