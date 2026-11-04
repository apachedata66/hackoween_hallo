"""Check an output.csv against the official contract.

Examples:
  python scripts/validate_output.py dataset/sample_output.csv \
    --requests dataset/sample_deletion_requests.csv --dataset dataset
  python scripts/validate_output.py output.csv \
    --requests dataset/deletion_requests.csv --dataset dataset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from ghostdata.paths import dataset_dir  # noqa: E402
from ghostdata.validate import validate_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Ghost Data output.csv")
    parser.add_argument("output", type=Path, help="CSV to check")
    parser.add_argument(
        "--requests",
        type=Path,
        help="Request CSV whose case_ids must match (default: dataset/deletion_requests.csv)",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        help=(
            "Dataset directory used to check evidence ids "
            "(default: GHOSTDATA_DATASET or <repo>/dataset)"
        ),
    )
    args = parser.parse_args()
    data = args.dataset or dataset_dir()
    requests = args.requests or data / "deletion_requests.csv"
    issues = validate_file(args.output, requests_path=requests, dataset_dir=data)
    if not issues:
        print(f"PASS {args.output}")
        return 0
    print(f"FAIL {args.output}: {len(issues)} problem(s)")
    for issue in issues:
        print(issue.format())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
