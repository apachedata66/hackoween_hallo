"""Deterministic, plain-language explanations for audit results (task B10)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ghostdata.contract.models import CaseResult, DeletionStatus, Phase


@dataclass(frozen=True)
class CaseExplanation:
    case_id: str
    verdict_label: str
    verdict_badge: str  # green | red | grey
    headline: str
    bullet_reasons: list[str]
    timeline: list[str]
    reported_status: str
    actual_status: str
    mismatch: bool
    remediation_summary: list[str]


def _before_or_at(timestamp: str, cutoff: str) -> bool:
    """Compare ISO timestamps when possible; retain entries if formats differ."""
    try:
        left = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        right = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        if left.tzinfo is None and right.tzinfo is not None:
            left = left.replace(tzinfo=right.tzinfo)
        if right.tzinfo is None and left.tzinfo is not None:
            right = right.replace(tzinfo=left.tzinfo)
        return left <= right
    except (TypeError, ValueError):
        return True


def _event_label(operation: str) -> str:
    labels = {
        "REPORT_REMAINING_RECORD": "A record that should be removed remains",
        "REPORT_EXPOSED_PII": "A retained record still exposes identifying details",
        "REPORT_ACTIVE_DATA_FLOW": "A process can copy or recreate the data",
        "REPORT_RESTORE_RISK": "A restore path can bring the data back",
    }
    return labels.get(operation, operation.replace("_", " ").capitalize())


def explain_case(
    result: CaseResult,
    request_row: dict | None = None,
) -> CaseExplanation:
    """Explain the engine's result without repeating the person's email address.

    The explanation is a view of the result only. It never recalculates or changes
    the verdict, and it describes only the ordered steps supplied by the planner.
    """
    request_row = request_row or {}
    reported = str(request_row.get("reported_status") or "UNKNOWN")
    actual = result.deletion_status.value
    requested_at = str(request_row.get("requested_at") or "")
    reported_at = str(request_row.get("reported_at") or "")
    audit_at = str(request_row.get("audit_at") or "")

    timeline: list[str] = []
    if requested_at:
        timeline.append(f"Deletion request received at {requested_at}.")
    if reported != "UNKNOWN":
        if not reported_at or not audit_at or _before_or_at(reported_at, audit_at):
            when = f" at {reported_at}" if reported_at else ""
            timeline.append(f"The previous workflow reported {reported}{when}.")
    if audit_at:
        timeline.append(f"Evidence was assessed as of {audit_at}.")
    if not timeline:
        timeline.append("The audit result was produced from the supplied evidence.")

    findings = [step for step in result.steps if step.phase is Phase.FINDING]
    remediations = [step for step in result.steps if step.phase is Phase.REMEDIATION]
    verifications = [step for step in result.steps if step.phase is Phase.VERIFICATION]

    if result.deletion_status is DeletionStatus.COMPLETE:
        label, badge = "Fully deleted - proven", "green"
        headline = f"Fully deleted and proven by {len(verifications)} verification check(s)."
        reasons = [
            f"{step.operation.value.replace('_', ' ').capitalize()} for "
            f"{step.system_id} / {step.resource_id} (evidence: {step.evidence_id})."
            for step in verifications
        ]
        if not reasons:
            reasons = [
                "The planner returned no verification steps; review is needed "
                "to support this verdict."
            ]
        remedy_summary = ["No remediation is required based on the evidence reviewed."]
    elif result.deletion_status is DeletionStatus.INCOMPLETE:
        label, badge = f"Not fully deleted - {len(findings)} problem(s)", "red"
        headline = (
            f"Not fully deleted. {len(findings)} issue(s) need attention, "
            f"with {len(remediations)} planned fix(es)."
        )
        reasons = [
            f"{_event_label(step.operation.value)} at {step.system_id} / "
            f"{step.resource_id} (evidence: {step.evidence_id})."
            for step in findings
        ]
        if not reasons:
            reasons = ["The planner flagged a policy or evidence gap that needs review."]
        remedy_summary = [
            f"Step {step.step_no}: {step.operation.value.replace('_', ' ').lower()} "
            f"at {step.system_id} / {step.resource_id}."
            for step in remediations
        ]
        if not remedy_summary:
            remedy_summary = ["Review the case warnings and resolve the policy or evidence gap."]
    else:
        label, badge = "Nothing to delete", "grey"
        headline = "Not applicable. The request did not authorize a deletion audit."
        reasons = ["No deletion findings or verification steps were generated."]
        remedy_summary = ["No deletion action is required for this request."]

    mismatch = reported != "UNKNOWN" and reported != actual
    return CaseExplanation(
        case_id=result.case_id,
        verdict_label=label,
        verdict_badge=badge,
        headline=headline,
        bullet_reasons=reasons,
        timeline=timeline,
        reported_status=reported,
        actual_status=actual,
        mismatch=mismatch,
        remediation_summary=remedy_summary,
    )
