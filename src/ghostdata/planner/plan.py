"""Build the ordered answer for one case. The UI must call this same function."""

from __future__ import annotations

from dataclasses import dataclass, field

from ghostdata.contract.models import (
    CaseAuditInput,
    CaseResult,
    DeletionStatus,
    Step,
    number_steps,
)
from ghostdata.planner.status import (
    Authorization,
    all_four_conditions,
    classify_request,
)
from ghostdata.policy.engine import Assessment, assess_resource
from ghostdata.policy.rules import Rulebook


@dataclass
class PlanOutcome:
    result: CaseResult
    warnings: list[str] = field(default_factory=list)
    review_required: bool = False


def plan_case(case: CaseAuditInput, rulebook: Rulebook) -> PlanOutcome:
    """reported_status is ignored on purpose. Only evidence and policy count."""

    warnings = list(case.warnings)
    request = case.request
    case_id = str(request.get("case_id") or case.identity.case_id)
    text = str(request.get("request_text") or "")
    authorization, reason = classify_request(text)
    if authorization is Authorization.NOT_AUTHORIZED:
        return PlanOutcome(
            result=CaseResult(case_id, DeletionStatus.NOT_APPLICABLE, ()),
            warnings=warnings + [reason],
        )
    if authorization is Authorization.UNCLEAR:
        warnings.append(reason)

    assessments = [assess_resource(resource, rulebook) for resource in case.resources]
    for item in assessments:
        if item.violation == "unknown_category":
            warnings.append(item.reason)

    included = [item for item in assessments if item.include]
    if not included:
        warnings.append(
            "no in-scope resources were supplied, so this case cannot be marked COMPLETE"
        )
        return PlanOutcome(
            result=CaseResult(case_id, DeletionStatus.INCOMPLETE, ()),
            warnings=warnings,
            review_required=True,
        )

    if any(item.violation == "missing_retain" for item in included):
        warnings.append(
            "a required record is missing and the output contract has no finding "
            "operation for that gap; this case needs review"
        )
        return PlanOutcome(
            result=CaseResult(case_id, DeletionStatus.INCOMPLETE, ()),
            warnings=warnings,
            review_required=True,
        )

    status = DeletionStatus.COMPLETE if all_four_conditions(included) else DeletionStatus.INCOMPLETE
    steps = _steps_for(status, included)
    return PlanOutcome(
        result=CaseResult(case_id, status, tuple(number_steps(steps))),
        warnings=warnings,
    )


def _steps_for(status: DeletionStatus, assessments: list[Assessment]) -> list[Step]:
    drafted: list[Step] = []
    cite_verification = status is DeletionStatus.COMPLETE
    for item in assessments:
        evidence = item.resource.evidence_id
        if status is DeletionStatus.INCOMPLETE and item.finding and item.remediation:
            finding_op, finding_state = item.finding
            remedy_op, remedy_state = item.remediation
            drafted.append(
                Step(
                    0,
                    "FINDING",
                    item.resource.system_id,
                    item.resource.resource_id,
                    finding_op,
                    finding_state,
                    evidence,
                )
            )
            drafted.append(
                Step(
                    0,
                    "REMEDIATION",
                    item.resource.system_id,
                    item.resource.resource_id,
                    remedy_op,
                    remedy_state,
                    "",
                )
            )
        if item.verification:
            verify_op, verify_state = item.verification
            drafted.append(
                Step(
                    0,
                    "VERIFICATION",
                    item.resource.system_id,
                    item.resource.resource_id,
                    verify_op,
                    verify_state,
                    evidence if cite_verification else "",
                )
            )
    # Replica observations may produce several assessments for the same
    # logical resource. The output contract permits one step per operation
    # and resource, so collapse duplicates while preserving a usable citation.
    unique: dict[tuple[str, str, str, str], Step] = {}
    for step in drafted:
        key = step.identity()
        existing = unique.get(key)
        if existing is None or (not existing.evidence_id and step.evidence_id):
            unique[key] = step
    return list(unique.values())
