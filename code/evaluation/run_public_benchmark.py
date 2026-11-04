"""Reproduce public-sample scoring using the current evidence engine.

This harness intentionally omits cases the engine marks for manual review.
Those cases count as missing predictions in the scorer. It never reads hidden
answers during prediction; the public sample output is read only by the
evaluation report after predictions have been produced.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "code"))

from evaluation.report import render_report  # noqa: E402
from ghostdata.audit import EvidenceEngine  # noqa: E402
from ghostdata.contract.csv_io import write_output  # noqa: E402
from ghostdata.loaders import load_requests  # noqa: E402
from ghostdata.paths import dataset_dir  # noqa: E402
from ghostdata.planner.plan import plan_case  # noqa: E402
from ghostdata.policy.rules import load_rulebook  # noqa: E402


def main() -> int:
    dataset = dataset_dir()
    requests = load_requests(dataset / "sample_deletion_requests.csv")
    engine = EvidenceEngine.from_dataset(dataset)
    rulebook = load_rulebook(dataset / "deletion_rules.csv")

    predictions = []
    review_cases: list[tuple[str, list[str]]] = []
    for request in requests:
        outcome = plan_case(engine.audit_case(request), rulebook)
        if outcome.review_required:
            review_cases.append((request.case_id, outcome.warnings))
        else:
            predictions.append(outcome.result)

    if review_cases:
        case_notes = "; ".join(
            f"{case_id}: {', '.join(warnings) or 'manual review required'}"
            for case_id, warnings in review_cases
        )
        failures = (
            f"The evidence engine withheld {len(review_cases)} public sample cases "
            f"for manual review ({case_notes}). Their public gold steps name "
            "resources not linked to the resolved identities by cutoff-eligible "
            "participant evidence. Do not infer resource IDs from case numbering."
        )
    else:
        failures = "All public sample cases produced evidence-supported predictions."

    improvements = (
        "Corrected evaluation accounting so missing predictions count as false "
        "negatives for step recall and field accuracy, while extra-case steps "
        "count as false positives. The earlier step recall/F1 (0.8201/0.8807) "
        "omitted the expected steps for missing cases; the corrected values "
        "are reported below. Added regression coverage and a one-command "
        "benchmark harness. Prediction behavior was not changed by the scorer fix."
    )
    with tempfile.TemporaryDirectory(prefix=".public-benchmark-", dir=ROOT / "evaluation") as work:
        prediction_path = Path(work) / "predictions.csv"
        write_output(prediction_path, predictions)
        report = render_report(
            prediction_path,
            dataset / "sample_output.csv",
            failures,
            improvements,
            prediction_label=(
                f"generated in memory by this harness; {len(predictions)} of "
                f"{len(requests)} cases predicted, {len(review_cases)} held for review"
            ),
        )

    destination = ROOT / "evaluation" / "evaluation_report.md"
    destination.write_text(report, encoding="utf-8", newline="\n")
    print(f"Wrote {destination}")
    print(f"Predictions: {len(predictions)}/{len(requests)}; manual review: {len(review_cases)}")
    for case_id, warnings in review_cases:
        print(f"Manual review {case_id}: {'; '.join(warnings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
