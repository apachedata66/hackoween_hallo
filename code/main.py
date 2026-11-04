"""Run the deterministic full-dataset deletion audit from the repository root."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ghostdata.audit import EvidenceEngine  # noqa: E402
from ghostdata.contract.csv_io import write_output  # noqa: E402
from ghostdata.paths import dataset_dir, output_path  # noqa: E402
from ghostdata.planner.plan import plan_case  # noqa: E402
from ghostdata.policy.rules import load_rulebook  # noqa: E402
from ghostdata.validate import validate_file  # noqa: E402


def main() -> int:
    dataset = dataset_dir()
    rules = load_rulebook(dataset / "deletion_rules.csv")
    engine = EvidenceEngine.from_dataset(dataset)
    results = [plan_case(case, rules).result for case in engine.audit_all()]
    destination = output_path()
    write_output(destination, results)
    issues = validate_file(
        destination,
        requests_path=dataset / "deletion_requests.csv",
        dataset_dir=dataset,
    )
    if issues:
        print(f"Output failed validation with {len(issues)} problem(s).")
        for issue in issues[:20]:
            print(issue.format())
        return 1
    print(f"Wrote and validated {len(results)} cases: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
