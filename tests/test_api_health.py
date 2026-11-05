from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase

if importlib.util.find_spec("fastapi") is None:
    raise SkipTest("install the optional UI dependencies to run API tests")

from ghostdata.api import app as api


class DatasetHealthTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original_dataset_dir = api.dataset_dir
        api.dataset_dir = lambda: self.root

    def tearDown(self) -> None:
        api.dataset_dir = self.original_dataset_dir
        self.temp.cleanup()

    def _create_required_files(self, *, include_samples: bool) -> None:
        files = (
            "deletion_requests.csv",
            "user_identities.csv",
            "user_audit_log.csv",
            "system_activity.csv",
            "deletion_rules.csv",
            "evidence_files.csv",
        )
        for name in files:
            content = "case_id\ncase_01\n" if name == "deletion_requests.csv" else "header\n"
            (self.root / name).write_text(content, encoding="utf-8")
        if include_samples:
            (self.root / "sample_deletion_requests.csv").write_text(
                "case_id\ncase_01\n", encoding="utf-8"
            )
        (self.root / "evidence").mkdir()

    def test_reports_dataset_ready_when_samples_and_evidence_are_present(self) -> None:
        self._create_required_files(include_samples=True)

        result = api.health()

        self.assertTrue(result["ready"])
        self.assertTrue(result["files"]["sample_deletion_requests.csv"])
        self.assertEqual(result["sample_count"], 1)

    def test_missing_public_samples_is_reported_as_not_ready(self) -> None:
        self._create_required_files(include_samples=False)

        result = api.health()

        self.assertFalse(result["ready"])
        self.assertFalse(result["files"]["sample_deletion_requests.csv"])


class CaseSummaryRiskTests(TestCase):
    def test_finding_systems_include_only_evidence_backed_findings(self) -> None:
        run = api.AuditRun("summary-test", "full", Path("requests.csv"))
        run.requests = {"case_01": {"case_id": "case_01", "email": "person@example.test"}}
        steps = [
            {"phase": "FINDING", "system_id": "support_platform", "operation": "REPORT_REMAINING_RECORD"},
            {"phase": "FINDING", "system_id": "primary_store", "operation": "REPORT_RESTORE_RISK"},
            {"phase": "REMEDIATION", "system_id": "billing", "operation": "DELETE_RECORD"},
        ]

        summary = api._case_summary(run, {
            "case_id": "case_01",
            "deletion_status": "INCOMPLETE",
            "steps_json": json.dumps(steps),
        })

        self.assertEqual(summary["finding_systems"], ["primary_store", "support_platform"])
