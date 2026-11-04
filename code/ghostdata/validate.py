"""Strict checks for output.csv. Messages say what is wrong and how to fix it."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ghostdata.contract.csv_io import HEADER, parse_steps
from ghostdata.contract.models import DeletionStatus, Phase, sort_key
import csv


@dataclass(frozen=True)
class ValidationIssue:
    row: int | None
    case_id: str | None
    message: str
    fix: str

    def format(self) -> str:
        where = f"row {self.row}" if self.row is not None else "file"
        if self.case_id:
            where = f"{where} {self.case_id}"
        return f"{where}: {self.message} Fix: {self.fix}"


def validate_rows(
    rows: list[dict[str, str]],
    *,
    expected_case_ids: list[str] | None = None,
    known_evidence_ids: set[str] | None = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if expected_case_ids is not None:
        expected = list(expected_case_ids)
        if len(rows) != len(expected):
            issues.append(
                ValidationIssue(
                    None,
                    None,
                    f"expected {len(expected)} data rows and found {len(rows)}",
                    "write one row for every request, including NOT_APPLICABLE cases",
                )
            )
        expected_set = set(expected)
        found_ids = [row.get("case_id", "") for row in rows]
        missing = [case_id for case_id in expected if case_id not in set(found_ids)]
        extra = [case_id for case_id in found_ids if case_id not in expected_set]
        if missing:
            preview = ", ".join(missing[:5])
            issues.append(
                ValidationIssue(
                    None,
                    None,
                    f"missing {len(missing)} case ids ({preview})",
                    "add one output row for each request case_id",
                )
            )
        if extra:
            preview = ", ".join(extra[:5])
            issues.append(
                ValidationIssue(
                    None,
                    None,
                    f"unexpected case ids ({preview})",
                    "remove rows that are not in the request file",
                )
            )

    case_ids = [row.get("case_id", "") for row in rows]
    if case_ids != sorted(case_ids):
        issues.append(
            ValidationIssue(
                None,
                None,
                "rows are not sorted by case_id using plain string order",
                "sort the file with an ordinary ascending string sort on case_id",
            )
        )
    duplicates = sorted({case_id for case_id in case_ids if case_ids.count(case_id) > 1})
    if duplicates:
        issues.append(
            ValidationIssue(
                None,
                None,
                f"duplicate case ids: {', '.join(duplicates[:5])}",
                "keep a single row per case_id",
            )
        )

    for index, row in enumerate(rows, start=2):
        issues.extend(_validate_row(index, row, known_evidence_ids))
    return issues


def _validate_row(
    row_number: int,
    row: dict[str, str],
    known_evidence_ids: set[str] | None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    case_id = row.get("case_id") or ""
    status_text = row.get("deletion_status") or ""
    try:
        status = DeletionStatus(status_text)
    except ValueError:
        return [
            ValidationIssue(
                row_number,
                case_id,
                f"deletion_status {status_text!r} is not allowed",
                "use COMPLETE, INCOMPLETE, or NOT_APPLICABLE",
            )
        ]

    raw_steps = row.get("steps_json") or ""
    try:
        parsed = json.loads(raw_steps)
    except json.JSONDecodeError as exc:
        return [
            ValidationIssue(
                row_number,
                case_id,
                f"steps_json is not valid JSON ({exc.msg})",
                "write a JSON array, or [] when the status is NOT_APPLICABLE",
            )
        ]
    if not isinstance(parsed, list):
        return [
            ValidationIssue(
                row_number,
                case_id,
                "steps_json is not a JSON array",
                "wrap the steps in []",
            )
        ]

    try:
        steps = parse_steps(raw_steps)
    except (ValueError, TypeError, KeyError) as exc:
        return [ValidationIssue(row_number, case_id, str(exc), "use only the seven official step fields and an allowed phase/operation/state triple")]

    if status is DeletionStatus.NOT_APPLICABLE:
        if steps:
            issues.append(
                ValidationIssue(
                    row_number,
                    case_id,
                    "NOT_APPLICABLE must use an empty step list",
                    "set steps_json to []",
                )
            )
        return issues

    if not steps:
        issues.append(
            ValidationIssue(
                row_number,
                case_id,
                f"{status.value} has no steps",
                "COMPLETE needs verification steps; INCOMPLETE needs findings, fixes, and checks",
            )
        )
        return issues

    numbers = [step.step_no for step in steps]
    if numbers != list(range(1, len(steps) + 1)):
        issues.append(
            ValidationIssue(
                row_number,
                case_id,
                f"step_no values are {numbers}",
                "number steps from 1 upward with no gaps, after sorting",
            )
        )

    identities = [step.identity() for step in steps]
    if len(identities) != len(set(identities)):
        issues.append(
            ValidationIssue(
                row_number,
                case_id,
                "two steps share the same phase, operation, system, and resource",
                "keep one step for each resource and operation",
            )
        )

    keys = [sort_key(step) for step in steps]
    if keys != sorted(keys):
        issues.append(
            ValidationIssue(
                row_number,
                case_id,
                "steps are not in official order",
                "sort by phase (FINDING, REMEDIATION, VERIFICATION), then by the operation table, then system_id, then resource_id",
            )
        )

    if status is DeletionStatus.COMPLETE:
        for step in steps:
            if step.phase is not Phase.VERIFICATION:
                issues.append(
                    ValidationIssue(
                        row_number,
                        case_id,
                        f"step {step.step_no} is {step.phase.value}, but COMPLETE allows verification only",
                        "drop findings and remediation once the evidence already proves the required state",
                    )
                )
            if not step.evidence_id.strip():
                issues.append(
                    ValidationIssue(
                        row_number,
                        case_id,
                        f"step {step.step_no} is missing evidence_id",
                        "cite the file_id, activity_id, or audit_id that proves this check",
                    )
                )
    else:
        finding_count = 0
        for step in steps:
            if step.phase is Phase.FINDING:
                finding_count += 1
                if not step.evidence_id.strip():
                    issues.append(
                        ValidationIssue(
                            row_number,
                            case_id,
                            f"finding step {step.step_no} has an empty evidence_id",
                            "cite the evidence that shows this problem",
                        )
                    )
            elif step.evidence_id.strip():
                issues.append(
                    ValidationIssue(
                        row_number,
                        case_id,
                        f"step {step.step_no} is a proposed {step.phase.value} but cites evidence",
                        "use an empty evidence_id for remediation and for future verification",
                    )
                )
        if finding_count == 0:
            issues.append(
                ValidationIssue(
                    row_number,
                    case_id,
                    "INCOMPLETE has no findings",
                    "report each remaining record, exposed identifier, active flow, or restore risk",
                )
            )

    if known_evidence_ids is not None:
        for step in steps:
            if step.evidence_id and step.evidence_id not in known_evidence_ids:
                issues.append(
                    ValidationIssue(
                        row_number,
                        case_id,
                        f"step {step.step_no} cites unknown evidence_id {step.evidence_id}",
                        "use a file_id, activity_id, or audit_id that exists in the dataset",
                    )
                )
    return issues


def load_known_ids(dataset_dir: str | Path) -> set[str]:
    root = Path(dataset_dir)
    found: set[str] = set()
    found.update(_column(root / "evidence_files.csv", "file_id"))
    found.update(_column(root / "system_activity.csv", "activity_id"))
    found.update(_column(root / "user_audit_log.csv", "audit_id"))
    return found


def load_request_ids(path: str | Path) -> list[str]:
    return _column(Path(path), "case_id")


def _column(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or column not in reader.fieldnames:
            raise ValueError(f"{path.name} has no {column} column")
        return [(row.get(column) or "").strip() for row in reader if (row.get(column) or "").strip()]


def read_output_rows(path: str | Path) -> tuple[list[str] | None, list[dict[str, str]]]:
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    if tuple(header) != HEADER:
        return header, rows
    return None, rows


def validate_file(
    path: str | Path,
    *,
    requests_path: str | Path | None = None,
    dataset_dir: str | Path | None = None,
) -> list[ValidationIssue]:
    header, rows = read_output_rows(path)
    if header is not None:
        return [
            ValidationIssue(
                1,
                None,
                f"header is {header}",
                "the first line must be exactly case_id,deletion_status,steps_json",
            )
        ]
    expected = load_request_ids(requests_path) if requests_path else None
    known = load_known_ids(dataset_dir) if dataset_dir else None
    return validate_rows(rows, expected_case_ids=expected, known_evidence_ids=known)
