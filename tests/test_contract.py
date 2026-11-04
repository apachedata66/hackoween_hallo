"""Contract tests: invalid steps cannot be built, and sample_output.csv round-trips."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from ghostdata.contract.csv_io import read_output, write_output  # noqa: E402
from ghostdata.contract.models import Step  # noqa: E402
from ghostdata.paths import dataset_dir  # noqa: E402

SAMPLE = dataset_dir() / "sample_output.csv"


class ContractTests(unittest.TestCase):
    def test_invalid_pair_cannot_be_constructed(self) -> None:
        with self.assertRaises(ValueError):
            Step(1, "FINDING", "account_service", "account_1", "DELETE_RECORD", "ABSENT", "evidence_01")

    def test_sample_round_trip_preserves_meaning(self) -> None:
        original = read_output(SAMPLE)
        self.assertGreaterEqual(len(original), 32)
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "output.csv"
            write_output(destination, original)
            again = read_output(destination)
        self.assertEqual(
            [(item.case_id, item.deletion_status, item.steps_payload()) for item in original],
            [(item.case_id, item.deletion_status, item.steps_payload()) for item in again],
        )

    def test_sample_steps_already_follow_string_order(self) -> None:
        from ghostdata.contract.models import number_steps

        for result in read_output(SAMPLE):
            renumbered = number_steps(list(result.steps))
            self.assertEqual(
                result.steps_payload(),
                [step.to_dict() for step in renumbered],
                result.case_id,
            )


if __name__ == "__main__":
    unittest.main()
