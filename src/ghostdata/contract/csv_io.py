"""Read and write output.csv. steps_json is quoted because it contains commas and quotes."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from ghostdata.contract.models import STEP_FIELDS, CaseResult, DeletionStatus, Step

HEADER = ("case_id", "deletion_status", "steps_json")


def steps_to_json(steps: list[Step] | tuple[Step, ...]) -> str:
    payload = [step.to_dict() for step in steps]
    return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


def parse_steps(raw: str) -> list[Step]:
    parsed = json.loads(raw)
    if not isinstance(parsed, list):
        raise ValueError("steps_json must be a JSON array")
    return [Step.from_dict(item) for item in parsed]


def read_output(path: str | Path) -> list[CaseResult]:
    results: list[CaseResult] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or tuple(reader.fieldnames) != HEADER:
            found = reader.fieldnames
            raise ValueError(f"header must be {','.join(HEADER)} in that order; found {found}")
        for row in reader:
            results.append(
                CaseResult(
                    case_id=row["case_id"],
                    deletion_status=DeletionStatus(row["deletion_status"]),
                    steps=tuple(parse_steps(row["steps_json"])),
                )
            )
    return results


def write_output(path: str | Path, results: list[CaseResult]) -> None:
    ordered = sorted(results, key=lambda item: item.case_id)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        for result in ordered:
            writer.writerow(
                {
                    "case_id": result.case_id,
                    "deletion_status": result.deletion_status.value,
                    "steps_json": steps_to_json(result.steps),
                }
            )


def step_field_names() -> tuple[str, ...]:
    return STEP_FIELDS
