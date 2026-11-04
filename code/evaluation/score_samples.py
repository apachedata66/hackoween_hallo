"""Score an output.csv against a gold file (B7).

Usage:
  python code/evaluation/score_samples.py --pred my_output.csv
  python code/evaluation/score_samples.py --pred output.csv --gold path/to/gold.csv --show 10

Metrics (all deterministic, documented the same way in evaluation_report.md):
  * status accuracy      - fraction of cases whose deletion_status matches.
  * step-level accuracy  - micro precision / recall / F1 over full step tuples
                           (phase, system_id, resource_id, operation, state,
                           evidence_id); step_no is excluded because it is
                           derived from ordering and checked by the validator.
  * field-level accuracy - per field, positional comparison over the longer of
                           the two step lists; a missing or extra step counts
                           as a mismatch for every field at that position.
  * sequence accuracy     - fraction of cases whose ordered step list matches
                           exactly (same steps, same order).
  * confusion matrix      - 3x3 counts of predicted vs gold status.

Nothing here reads golden answers at prediction time: the scorer only compares
two finished outputs. It is safe to run in CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ghostdata.contract.csv_io import read_output  # noqa: E402
from ghostdata.contract.models import STEP_FIELDS, DeletionStatus  # noqa: E402
from ghostdata.paths import dataset_dir  # noqa: E402

# step_no is intentionally excluded: it is derived from order.
SCORING_FIELDS = tuple(f for f in STEP_FIELDS if f != "step_no")

STATUSES = tuple(status.value for status in DeletionStatus)


def step_key(step) -> tuple[str, ...]:
    """Identity of a step for set comparison."""

    return tuple(
        getattr(step, field)
        if field not in {"phase", "operation", "state"}
        else getattr(step, field).value
        for field in SCORING_FIELDS
    )


def _field_values(step) -> dict[str, str]:
    return {
        field: (
            getattr(step, field).value
            if field in {"phase", "operation", "state"}
            else str(getattr(step, field))
        )
        for field in SCORING_FIELDS
    }


def score_case(gold, pred) -> dict:
    gold_keys = [step_key(step) for step in gold.steps]
    pred_keys = [step_key(step) for step in pred.steps]
    gold_counts = Counter(gold_keys)
    pred_counts = Counter(pred_keys)
    overlap = sum((gold_counts & pred_counts).values())

    length = max(len(gold_keys), len(pred_keys))
    field_matches = {field: 0 for field in SCORING_FIELDS}
    for index in range(length):
        if index >= len(gold_keys) or index >= len(pred_keys):
            continue
        gold_values = _field_values(gold.steps[index])
        pred_values = _field_values(pred.steps[index])
        for field in SCORING_FIELDS:
            if gold_values[field] == pred_values[field]:
                field_matches[field] += 1

    return {
        "case_id": gold.case_id,
        "status_ok": gold.deletion_status == pred.deletion_status,
        "gold_status": gold.deletion_status.value,
        "pred_status": pred.deletion_status.value,
        "gold_steps": len(gold_keys),
        "pred_steps": len(pred_keys),
        "overlap": overlap,
        "field_matches": field_matches,
        "field_total": length,
        "sequence_ok": gold_keys == pred_keys,
        "gold_keys": gold_keys,
        "pred_keys": pred_keys,
    }


def score(gold_results, pred_results) -> dict:
    gold_by_id = {item.case_id: item for item in gold_results}
    pred_by_id = {item.case_id: item for item in pred_results}
    shared = sorted(set(gold_by_id) & set(pred_by_id))
    missing = sorted(set(gold_by_id) - set(pred_by_id))
    extra = sorted(set(pred_by_id) - set(gold_by_id))

    cases = [score_case(gold_by_id[case_id], pred_by_id[case_id]) for case_id in shared]

    total_cases = len(gold_by_id)
    status_hits = sum(1 for case in cases if case["status_ok"])
    sequence_hits = sum(1 for case in cases if case["sequence_ok"])

    true_positives = sum(case["overlap"] for case in cases)
    pred_step_total = sum(case["pred_steps"] for case in cases)
    gold_step_total = sum(case["gold_steps"] for case in cases)
    precision = true_positives / pred_step_total if pred_step_total else 0.0
    recall = true_positives / gold_step_total if gold_step_total else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    field_accuracy = {}
    for field in SCORING_FIELDS:
        matches = sum(case["field_matches"][field] for case in cases)
        totals = sum(case["field_total"] for case in cases)
        field_accuracy[field] = matches / totals if totals else 0.0

    confusion = {
        gold_status: {pred_status: 0 for pred_status in STATUSES} for gold_status in STATUSES
    }
    for case in cases:
        confusion[case["gold_status"]][case["pred_status"]] += 1

    return {
        "case_count": total_cases,
        "scored_cases": len(shared),
        "missing_cases": missing,
        "extra_cases": extra,
        "status_accuracy": status_hits / total_cases if total_cases else 0.0,
        "step_precision": precision,
        "step_recall": recall,
        "step_f1": f1,
        "field_accuracy": field_accuracy,
        "sequence_accuracy": sequence_hits / total_cases if total_cases else 0.0,
        "confusion": confusion,
        "cases": cases,
    }


def format_report(result: dict, show: int = 0) -> str:
    lines = [
        f"Cases: {result['case_count']} gold, {result['scored_cases']} scored, "
        f"{len(result['missing_cases'])} missing, {len(result['extra_cases'])} extra",
        f"Status accuracy:      {result['status_accuracy']:.4f}",
        f"Step precision:       {result['step_precision']:.4f}",
        f"Step recall:          {result['step_recall']:.4f}",
        f"Step F1:              {result['step_f1']:.4f}",
        f"Sequence accuracy:    {result['sequence_accuracy']:.4f}",
        "Field accuracy:",
    ]
    for field in SCORING_FIELDS:
        lines.append(f"  {field:<14} {result['field_accuracy'][field]:.4f}")
    lines.append("Confusion (rows = gold, cols = predicted):")
    lines.append("  gold\\pred  " + "  ".join(f"{status:>15}" for status in STATUSES))
    for gold_status in STATUSES:
        row = result["confusion"][gold_status]
        lines.append(
            f"  {gold_status:<10} " + "  ".join(f"{row[status]:>15}" for status in STATUSES)
        )

    failures = [case for case in result["cases"] if not (case["status_ok"] and case["sequence_ok"])]
    lines.append(f"Failures: {len(failures)}")
    for case in failures[:show]:
        lines.append(
            f"  {case['case_id']}: status {case['pred_status']} (gold {case['gold_status']}), "
            f"steps {case['pred_steps']} (gold {case['gold_steps']})"
        )
        if not case["sequence_ok"]:
            gold_set = set(case["gold_keys"])
            pred_set = set(case["pred_keys"])
            for key in sorted(gold_set - pred_set):
                lines.append(f"    missing: {'/'.join(key)}")
            for key in sorted(pred_set - gold_set):
                lines.append(f"    extra:   {'/'.join(key)}")
    if failures and len(failures) > show:
        lines.append(f"  ... {len(failures) - show} more (raise --show)")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score a Ghost Data output.csv against a gold file"
    )
    parser.add_argument("--pred", type=Path, required=True, help="predicted output.csv to score")
    parser.add_argument(
        "--gold",
        type=Path,
        default=dataset_dir() / "sample_output.csv",
        help="gold output.csv (default: dataset/sample_output.csv)",
    )
    parser.add_argument("--show", type=int, default=10, help="number of failing cases to diff")
    parser.add_argument(
        "--json", type=Path, help="also write machine-readable metrics to this path"
    )
    args = parser.parse_args()

    gold_results = read_output(args.gold)
    pred_results = read_output(args.pred)
    result = score(gold_results, pred_results)
    print(format_report(result, show=args.show))

    if args.json:
        payload = {key: value for key, value in result.items() if key != "cases"}
        payload["failures"] = [
            case["case_id"]
            for case in result["cases"]
            if not (case["status_ok"] and case["sequence_ok"])
        ]
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Wrote {args.json}")

    # Non-zero when not perfect so CI can gate on it.
    return 0 if (result["status_accuracy"] == 1.0 and result["sequence_accuracy"] == 1.0) else 1


if __name__ == "__main__":
    raise SystemExit(main())
