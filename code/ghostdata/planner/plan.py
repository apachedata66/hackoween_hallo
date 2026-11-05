"""Build the ordered answer for one case. The UI must call this same function."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ghostdata.contract.models import (
    CaseAuditInput,
    CaseResult,
    DeletionStatus,
    Operation,
    Step,
    number_steps,
)
from ghostdata.loaders.timeutil import parse_optional_timestamp
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
    requested_at = parse_optional_timestamp(
        str(request.get("requested_at") or ""), field="requested_at"
    )
    steps = _steps_for(status, included, requested_at=requested_at)
    return PlanOutcome(
        result=CaseResult(case_id, status, tuple(number_steps(steps))),
        warnings=warnings,
    )


def _steps_for(
    status: DeletionStatus,
    assessments: list[Assessment],
    *,
    requested_at: datetime | None = None,
) -> list[Step]:
    drafted: list[tuple[Step, float]] = []
    cite_verification = status is DeletionStatus.COMPLETE
    for item in assessments:
        evidence = item.resource.evidence_id
        if status is DeletionStatus.INCOMPLETE and item.finding and item.remediation:
            finding_op, finding_state = item.finding
            remedy_op, remedy_state = item.remediation
            drafted.append(
                (
                    Step(
                        0,
                        "FINDING",
                        item.resource.system_id,
                        item.resource.resource_id,
                        finding_op,
                        finding_state,
                        evidence,
                    ),
                    item.resource.confidence,
                )
            )
            drafted.append(
                (
                    Step(
                        0,
                        "REMEDIATION",
                        item.resource.system_id,
                        item.resource.resource_id,
                        remedy_op,
                        remedy_state,
                        "",
                    ),
                    item.resource.confidence,
                )
            )
        if item.verification:
            if (
                not cite_verification
                and item.compliant
                and item.verification[0] is Operation.VERIFY_RECORD_ABSENT
                and requested_at is not None
                and not _has_post_request_state_observation(item, requested_at)
            ):
                # An already-absent delete record with no state observation
                # since the request is outside the remediation plan. Ignore
                # older negative lookups and action claims; neither places
                # the resource in scope at or after the request.
                continue
            # In an incomplete plan, future verification is required for each
            # process we propose to remediate. An already inactive flow is not
            # part of that remediation plan; emitting a future disable check
            # for it adds an unsupported step. Complete cases still cite the
            # current evidence that proves every relevant flow is inactive.
            if (
                not cite_verification
                and item.resource.kind == "flow"
                and not item.resource.is_active_flow
            ):
                continue
            verify_op, verify_state = item.verification
            drafted.append(
                (
                    Step(
                        0,
                        "VERIFICATION",
                        item.resource.system_id,
                        item.resource.resource_id,
                        verify_op,
                        verify_state,
                        evidence if cite_verification else "",
                    ),
                    item.resource.confidence,
                )
            )
    # Replica observations may produce several assessments for the same
    # logical resource. The output contract permits one step per operation
    # and resource, so collapse duplicates while keeping the strongest citation.
    unique: dict[tuple[str, str, str, str], Step] = {}
    unique_priority: dict[tuple[str, str, str, str], tuple[float, int]] = {}
    for step, confidence in drafted:
        key = step.identity()
        existing = unique.get(key)
        evidence_rank = (
            2
            if step.evidence_id and not step.evidence_id.startswith("activity_")
            else 1
            if step.evidence_id
            else 0
        )
        priority = (confidence, evidence_rank)
        if existing is None or priority > unique_priority[key]:
            unique[key] = step
            unique_priority[key] = priority
    return list(unique.values())


def _has_post_request_state_observation(
    item: Assessment, requested_at: datetime
) -> bool:
    """Whether a non-activity observation places this resource in request scope."""
    for entry in item.resource.timeline:
        event_type = str(entry.get("event_type") or "").upper()
        if event_type == "ACTIVITY_OBSERVATION" or not event_type.endswith("_OBSERVATION"):
            continue
        observed_at = parse_optional_timestamp(
            str(entry.get("event_time") or ""), field="resource timeline event_time"
        )
        if observed_at is not None and observed_at >= requested_at:
            return True
    return False
