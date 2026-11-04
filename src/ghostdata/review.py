"""Build a PII-free report for cases that cannot be serialized safely."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any


def write_review_report(path: str | Path, cases: list[tuple[Any, Any]]) -> None:
    """Write case IDs, evidence references, and resource categories only."""
    counts: Counter[str] = Counter()
    sections: list[str] = []
    for audit, outcome in sorted(cases, key=lambda pair: pair[0].request["case_id"]):
        case_id = str(audit.request["case_id"])
        missing_retained = any(
            "required record is missing" in warning for warning in outcome.warnings
        )
        reason = (
            "required_retained_record_unavailable"
            if missing_retained
            else "no_linked_resource_evidence"
        )
        counts[reason] += 1
        evidence_ids = sorted(
            {resource.evidence_id for resource in audit.resources if resource.evidence_id}
        )
        resources = sorted(
            {
                f"{resource.system_id}/{resource.resource_id} ({resource.data_category})"
                for resource in audit.resources
            }
        )
        details = resources or ["No identity-linked resources were reconstructed."]
        sections.append(
            f"### {case_id}\n\n"
            f"Reason: `{reason}`\n\n"
            f"Resources: {'; '.join(details)}\n\n"
            f"Evidence references: {', '.join(evidence_ids) if evidence_ids else 'none'}\n"
        )

    summary = "\n".join(f"- `{key}`: {value}" for key, value in sorted(counts.items()))
    content = (
        "# Manual review required\n\n"
        "The run found cases that cannot be represented as valid output steps "
        "from the available evidence. No prediction file was written. Review "
        "the cited participant-facing evidence before rerunning. This report "
        "contains no direct identifiers.\n\n"
        f"Cases requiring review: {len(cases)}\n\n"
        "## Summary\n\n"
        f"{summary or '- None'}\n\n"
        "## Cases\n\n" + "\n".join(sections)
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8", newline="\n")


__all__ = ["write_review_report"]
