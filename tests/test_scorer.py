"""Scorer tests: perfect score, and a deliberately broken prediction by known amounts."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

from score_samples import score  # noqa: E402

from ghostdata.contract.csv_io import read_output  # noqa: E402
from ghostdata.paths import dataset_dir  # noqa: E402

SAMPLE = dataset_dir() / "sample_output.csv"


class ScorerTests(unittest.TestCase):
    def test_gold_against_itself_is_perfect(self) -> None:
        gold = read_output(SAMPLE)
        result = score(gold, gold)
        self.assertEqual(result["status_accuracy"], 1.0)
        self.assertEqual(result["step_f1"], 1.0)
        self.assertEqual(result["sequence_accuracy"], 1.0)
        self.assertEqual(result["missing_cases"], [])
        self.assertEqual(result["extra_cases"], [])
        for field, value in result["field_accuracy"].items():
            self.assertEqual(value, 1.0, field)

    def test_wrong_status_lowers_only_status_and_keeps_steps(self) -> None:
        gold = read_output(SAMPLE)
        first = gold[0]
        flipped_type = type(first)(
            case_id=first.case_id,
            deletion_status="INCOMPLETE"
            if first.deletion_status.value != "INCOMPLETE"
            else "COMPLETE",
            steps=first.steps,
        )
        pred = [flipped_type if item.case_id == first.case_id else item for item in gold]
        result = score(gold, pred)
        self.assertLess(result["status_accuracy"], 1.0)
        self.assertAlmostEqual(
            result["status_accuracy"],
            (len(gold) - 1) / len(gold),
            places=6,
        )
        # Steps were untouched: step F1 and sequence accuracy stay perfect
        # (sequence accuracy measures step order, not status).
        self.assertEqual(result["step_f1"], 1.0)
        self.assertEqual(result["sequence_accuracy"], 1.0)

    def test_missing_case_is_reported_not_ignored(self) -> None:
        gold = read_output(SAMPLE)
        result = score(gold, gold[:-1])
        self.assertEqual(len(result["missing_cases"]), 1)
        self.assertEqual(result["case_count"], len(gold))
        self.assertEqual(result["scored_cases"], len(gold) - 1)

    def test_report_is_deterministic(self) -> None:
        gold = read_output(SAMPLE)
        first = score(gold, gold)
        second = score(gold, gold)
        strip = lambda r: {k: v for k, v in r.items() if k != "cases"}  # noqa: E731
        self.assertEqual(strip(first), strip(second))


if __name__ == "__main__":
    unittest.main()
