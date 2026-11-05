from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import SkipTest, TestCase

if importlib.util.find_spec("fastapi") is None:
    raise SkipTest("install the optional UI dependencies to run API tests")

from fastapi import HTTPException

from ghostdata.api import app as api


def _run_with_image(
    tmp_path: Path, *, cited: bool = True, captured_at: str = "2026-01-01T00:00:00Z"
) -> tuple[api.AuditRun, Path]:
    image = tmp_path / "evidence" / "images" / "source.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"fixture image bytes")
    with (tmp_path / "evidence_files.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=("file_id", "file_path", "origin", "captured_at")
        )
        writer.writeheader()
        writer.writerow(
            {
                "file_id": "evidence_01",
                "file_path": "evidence/images/source.png",
                "origin": "synthetic test fixture",
                "captured_at": captured_at,
            }
        )

    run = api.AuditRun("run-test", "full", tmp_path / "requests.csv")
    run.state = "complete"
    run.requests = {"case_01": {"case_id": "case_01", "audit_at": "2026-01-02T00:00:00Z"}}
    evidence_id = "evidence_01" if cited else "evidence_02"
    run.rows = [
        {
            "case_id": "case_01",
            "steps_json": json.dumps([{"evidence_id": evidence_id}]),
        }
    ]
    return run, image


class EvidencePreviewTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.original_dataset_dir = api.dataset_dir
        self.original_run = api._runs.get("run-test")
        api.dataset_dir = lambda: self.root

    def tearDown(self) -> None:
        api.dataset_dir = self.original_dataset_dir
        if self.original_run is None:
            api._runs.pop("run-test", None)
        else:
            api._runs["run-test"] = self.original_run
        self.temp.cleanup()

    def test_cited_image_preview_is_cutoff_checked_and_nocache(self) -> None:
        run, image = _run_with_image(self.root)
        api._runs[run.run_id] = run

        metadata = api.get_evidence(run.run_id, "case_01", "evidence_01")
        self.assertTrue(metadata["available_at_cutoff"])
        self.assertTrue(metadata["preview_url"].endswith("/evidence_01/content"))

        response = api.get_evidence_content(run.run_id, "case_01", "evidence_01")
        self.assertEqual(response.media_type, "image/png")
        self.assertEqual(response.body, image.read_bytes())
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_image_preview_rejects_uncited_and_post_cutoff_evidence(self) -> None:
        run, _image = _run_with_image(
            self.root,
            cited=False,
            captured_at="2026-01-03T00:00:00Z",
        )
        api._runs[run.run_id] = run

        with self.assertRaises(HTTPException) as uncited:
            api.get_evidence_content(run.run_id, "case_01", "evidence_01")
        self.assertEqual(uncited.exception.status_code, 404)

        metadata = api.get_evidence(run.run_id, "case_01", "evidence_02")
        self.assertFalse(metadata["available_at_cutoff"])
        self.assertIsNone(metadata["preview_url"])

        with self.assertRaises(HTTPException) as future:
            api.get_evidence_content(run.run_id, "case_01", "evidence_02")
        self.assertEqual(future.exception.status_code, 404)
