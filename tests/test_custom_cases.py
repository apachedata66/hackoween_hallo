"""Task B8: run every hand-built custom case through the real planner."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

from custom_cases import build_cases, run_cases  # noqa: E402


class CustomCaseTests(unittest.TestCase):
    def test_at_least_ten_custom_cases_exist(self) -> None:
        self.assertGreaterEqual(len(build_cases()), 10)

    def test_every_custom_case_passes(self) -> None:
        for record in run_cases():
            with self.subTest(case=record["case_id"], title=record["title"]):
                self.assertTrue(record["passed"], record["problems"])


if __name__ == "__main__":
    unittest.main()
