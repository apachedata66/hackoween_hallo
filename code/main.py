"""Entry point. This phase checks the sample answers and loads the policy.

The 518-case audit runs through the same planner once the evidence engine
supplies a CaseAuditInput for each request.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from ghostdata.paths import dataset_dir  # noqa: E402
from ghostdata.policy.rules import load_rulebook  # noqa: E402
from ghostdata.validate import validate_file  # noqa: E402


def main() -> int:
    dataset = dataset_dir()
    rules = load_rulebook(dataset / "deletion_rules.csv")
    print(f"Loaded {len(rules.rules)} deletion rules.")
    for rule in rules.rules:
        print(f"  {rule.rule_id} {rule.data_category} -> {rule.required_action.value}")

    sample = dataset / "sample_output.csv"
    issues = validate_file(
        sample,
        requests_path=dataset / "sample_deletion_requests.csv",
        dataset_dir=dataset,
    )
    if issues:
        print(f"Sample output failed validation with {len(issues)} problem(s).")
        for issue in issues[:20]:
            print(issue.format())
        return 1
    print("Sample output passed the contract validator.")
    print("Full audit is waiting on the evidence engine (Person A).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
