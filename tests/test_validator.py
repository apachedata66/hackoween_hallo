"""The validator must accept the official samples and reject deliberate mistakes."""

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from ghostdata.paths import dataset_dir  # noqa: E402
from ghostdata.validate import validate_file  # noqa: E402

DATASET = dataset_dir()
SAMPLE = DATASET / "sample_output.csv"
REQUESTS = DATASET / "sample_deletion_requests.csv"


def _write(rows: list[dict[str, str]]) -> Path:
    handle = tempfile.NamedTemporaryFile(
        "w", newline="", suffix=".csv", delete=False, encoding="utf-8"
    )
    writer = csv.DictWriter(
        handle, fieldnames=["case_id", "deletion_status", "steps_json"], lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(rows)
    handle.close()
    return Path(handle.name)


class ValidatorTests(unittest.TestCase):
    def test_official_sample_passes(self) -> None:
        issues = validate_file(SAMPLE, requests_path=REQUESTS, dataset_dir=DATASET)
        self.assertEqual([issue.format() for issue in issues], [])

    def test_bad_header_is_explained(self) -> None:
        path = _write([])
        path.write_text("id,status,steps\n", encoding="utf-8")
        issues = validate_file(path)
        self.assertTrue(any("header" in issue.message for issue in issues))

    def test_bad_status_and_unsorted_steps_are_caught(self) -> None:
        steps = [
            {
                "step_no": 1,
                "phase": "VERIFICATION",
                "system_id": "search_service",
                "resource_id": "search_1",
                "operation": "VERIFY_RECORD_ABSENT",
                "state": "ABSENT",
                "evidence_id": "",
            },
            {
                "step_no": 2,
                "phase": "FINDING",
                "system_id": "account_service",
                "resource_id": "account_1",
                "operation": "REPORT_REMAINING_RECORD",
                "state": "PRESENT",
                "evidence_id": "evidence_01",
            },
        ]
        path = _write(
            [
                {
                    "case_id": "case_02",
                    "deletion_status": "DONE",
                    "steps_json": "[]",
                },
                {
                    "case_id": "case_01",
                    "deletion_status": "INCOMPLETE",
                    "steps_json": json.dumps(steps),
                },
            ]
        )
        issues = validate_file(path, requests_path=REQUESTS)
        messages = " ".join(issue.message for issue in issues)
        self.assertIn("not allowed", messages)
        self.assertIn("not sorted", messages)
        self.assertIn("not in official order", messages)

    def test_complete_without_evidence_is_caught(self) -> None:
        step = {
            "step_no": 1,
            "phase": "VERIFICATION",
            "system_id": "account_service",
            "resource_id": "account_1",
            "operation": "VERIFY_RECORD_ABSENT",
            "state": "ABSENT",
            "evidence_id": "",
        }
        path = _write(
            [
                {
                    "case_id": "case_01",
                    "deletion_status": "COMPLETE",
                    "steps_json": json.dumps([step]),
                }
            ]
        )
        issues = validate_file(path)
        self.assertTrue(any("evidence_id" in issue.message for issue in issues))


if __name__ == "__main__":
    unittest.main()
