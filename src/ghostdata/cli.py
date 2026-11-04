"""Command-line runner for the Ghost Data audit (Person B task B9).

The runner owns input selection, planning, serialization, validation, progress,
and summaries. Evidence discovery is supplied through the Person A adapter
``ghostdata.evidence.pipeline.build_case_audit_inputs``.
"""

from __future__ import annotations

import argparse
import csv
import importlib
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from ghostdata.contract.csv_io import steps_to_json, write_output
from ghostdata.contract.models import CaseAuditInput, CaseResult, DeletionStatus
from ghostdata.explain.explainer import explain_case
from ghostdata.llm.usage import UsageTracker
from ghostdata.paths import require_dataset
from ghostdata.planner.plan import plan_case
from ghostdata.policy.rules import load_rulebook
from ghostdata.review import write_review_report
from ghostdata.validate import load_known_ids, validate_file, validate_rows


class EvidenceProvider(Protocol):
    """Person A adapter consumed by this CLI."""

    def build_case_audit_inputs(
        self,
        requests: list[dict[str, str]],
        dataset: Path,
        *,
        workers: int,
        no_llm: bool,
        resume: bool,
    ) -> Iterable[CaseAuditInput]: ...


def _load_provider() -> EvidenceProvider:
    try:
        module = importlib.import_module("ghostdata.evidence.pipeline")
        provider = module.build_case_audit_inputs
    except (ImportError, AttributeError) as exc:
        raise RuntimeError(
            "the evidence engine is not installed yet. Person A must add "
            "code/ghostdata/evidence/pipeline.py with "
            "build_case_audit_inputs(requests, dataset, *, workers, no_llm, resume). "
            "No predictions were written."
        ) from exc
    return _ProviderAdapter(provider)


class _ProviderAdapter:
    def __init__(self, function):
        self.function = function

    def build_case_audit_inputs(self, requests, dataset, *, workers, no_llm, resume):
        return self.function(
            requests,
            dataset,
            workers=workers,
            no_llm=no_llm,
            resume=resume,
        )


def _read_requests(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            expected = [
                "case_id",
                "email",
                "requested_at",
                "reported_status",
                "reported_at",
                "audit_at",
                "request_text",
            ]
            if list(reader.fieldnames or []) != expected:
                raise ValueError(
                    f"{path.name} columns must be {','.join(expected)} in that order; "
                    f"found {reader.fieldnames}"
                )
            rows = [{key: (value or "").strip() for key, value in row.items()} for row in reader]
    except OSError as exc:
        raise ValueError(f"cannot read request file {path}: {exc}") from exc
    ids = [row["case_id"] for row in rows]
    if not rows:
        raise ValueError(f"request file has no data rows: {path}")
    if any(not case_id for case_id in ids):
        raise ValueError("request file contains a blank case_id")
    if len(ids) != len(set(ids)):
        raise ValueError("request file contains duplicate case_id values")
    return rows


def _filter_requests(requests: list[dict[str, str]], case_id: str | None) -> list[dict[str, str]]:
    if not case_id:
        return requests
    selected = [row for row in requests if row["case_id"] == case_id]
    if not selected:
        raise ValueError(f"case_id {case_id!r} was not found in the selected input")
    return selected


def _run(args: argparse.Namespace) -> int:
    dataset = require_dataset()
    request_path = (
        Path(args.input)
        if args.input
        else (
            dataset / ("sample_deletion_requests.csv" if args.samples else "deletion_requests.csv")
        )
    )
    requests = _filter_requests(_read_requests(request_path), args.case)
    provider = _load_provider()
    rulebook = load_rulebook(dataset / "deletion_rules.csv")
    started = time.monotonic()
    outcomes = provider.build_case_audit_inputs(
        requests,
        dataset,
        workers=args.workers,
        no_llm=args.no_llm,
        resume=args.resume,
    )

    requested_by_id = {row["case_id"]: row for row in requests}
    results: list[CaseResult] = []
    review_cases: list[tuple[CaseAuditInput, object]] = []
    warnings = 0
    seen: set[str] = set()
    for index, case_input in enumerate(outcomes, start=1):
        outcome = plan_case(case_input, rulebook)
        if outcome.review_required:
            review_cases.append((case_input, outcome))
        case_id = outcome.result.case_id
        if case_id not in requested_by_id:
            raise ValueError(f"evidence engine returned unexpected case_id {case_id!r}")
        if case_id in seen:
            raise ValueError(f"evidence engine returned case_id {case_id!r} more than once")
        seen.add(case_id)
        results.append(outcome.result)
        warnings += len(outcome.warnings)
        for warning in outcome.warnings:
            print(f"Warning {case_id}: {warning}", file=sys.stderr)
        if args.explain:
            explanation = explain_case(outcome.result, requested_by_id[case_id])
            print(f"\n{explanation.verdict_label}: {explanation.headline}")
            print(
                f"Previous workflow: {explanation.reported_status}; "
                f"audit result: {explanation.actual_status}; "
                f"mismatch: {'yes' if explanation.mismatch else 'no'}"
            )
            print("Timeline:")
            for event in explanation.timeline:
                print(f"  • {event}")
            print("Reasons:")
            for reason in explanation.bullet_reasons:
                print(f"  • {reason}")
            if explanation.remediation_summary:
                print("  Next steps:")
                for item in explanation.remediation_summary:
                    print(f"  • {item}")
        if index % 25 == 0 or index == len(requests):
            elapsed_so_far = time.monotonic() - started
            eta = elapsed_so_far * (len(requests) - index) / index
            percent = 100 * index / len(requests)
            filled = round(20 * index / len(requests))
            bar = "#" * filled + "-" * (20 - filled)
            print(
                f"[{bar}] {index}/{len(requests)} ({percent:.0f}%); "
                f"elapsed {elapsed_so_far:.1f}s; ETA {eta:.1f}s"
            )

    missing = sorted(set(requested_by_id) - seen)
    if missing:
        raise ValueError(
            f"evidence engine returned {len(seen)} of {len(requests)} requested cases; "
            f"missing: {', '.join(missing[:8])}"
        )

    if review_cases:
        report = Path(__file__).resolve().parents[2] / "evaluation" / "manual_review.md"
        write_review_report(report, review_cases)
        print(
            f"Stopped safely: {len(review_cases)} case(s) need evidence review. "
            f"See {report}; no prediction file was written.",
            file=sys.stderr,
        )
        return 2

    default_name = (
        "output.case.csv" if args.case else "output.samples.csv" if args.samples else "output.csv"
    )
    output = Path(args.out) if args.out else Path(__file__).resolve().parents[2] / default_name
    rows = [
        {
            "case_id": result.case_id,
            "deletion_status": result.deletion_status.value,
            "steps_json": steps_to_json(result.steps),
        }
        for result in sorted(results, key=lambda item: item.case_id)
    ]
    issues = validate_rows(
        rows,
        expected_case_ids=list(requested_by_id) if not args.case else None,
        known_evidence_ids=load_known_ids(dataset),
    )
    if issues:
        details = "\n".join(issue.format() for issue in issues[:20])
        raise ValueError(f"generated output failed validation ({len(issues)} issue(s)):\n{details}")
    write_output(output, results)

    full_dataset_run = not args.case and not args.samples and args.input is None
    if full_dataset_run:
        review_report = Path(__file__).resolve().parents[2] / "evaluation" / "manual_review.md"
        try:
            review_report.unlink()
        except FileNotFoundError:
            pass

    usage_report: Path | None = None
    if full_dataset_run:
        tracker = UsageTracker(request_count=len(results))
        usage_report = tracker.write_usage_report(
            Path(__file__).resolve().parents[2] / "evaluation" / "usage_report.md",
            run={
                "command": "python code/main.py run",
                "requests": len(results),
                "model_calls": 0,
                "dataset": "participant-facing dataset/",
            },
        )

    counts = {status.value: 0 for status in DeletionStatus}
    for result in results:
        counts[result.deletion_status.value] += 1
    elapsed = time.monotonic() - started
    print(f"\nWrote and validated {len(results)} rows: {output}")
    print("Status totals: " + ", ".join(f"{key}={value}" for key, value in counts.items()))
    print(
        f"Warnings: {warnings}; runtime: {elapsed:.1f}s; "
        f"usage report: {usage_report if usage_report else 'not updated for partial run'}"
    )
    return 0


def _validate(args: argparse.Namespace) -> int:
    dataset = require_dataset()
    issues = validate_file(
        args.output,
        requests_path=args.input,
        dataset_dir=dataset,
    )
    if issues:
        for issue in issues:
            print(issue.format(), file=sys.stderr)
        return 1
    print(f"Output passed validation: {args.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ghostdata", description="Audit personal-data deletion requests"
    )
    commands = parser.add_subparsers(dest="command")
    run = commands.add_parser("run", help="audit requests and write output.csv")
    run.add_argument("--input", help="request CSV (defaults to the official 518-case file)")
    run.add_argument("--out", help="output CSV (defaults to repository-root output.csv)")
    run.add_argument("--case", help="run one case_id from the selected request file")
    run.add_argument("--samples", action="store_true", help="use the 32 public sample requests")
    run.add_argument("--explain", action="store_true", help="print plain-English case explanations")
    run.add_argument("--no-llm", action="store_true", help="disable optional model calls")
    run.add_argument(
        "--resume", action="store_true", help="reuse cached evidence extraction where supported"
    )
    run.add_argument("--workers", type=int, default=1, help="evidence workers (default: 1)")
    run.set_defaults(handler=_run)

    validate = commands.add_parser("validate", help="validate an output CSV")
    validate.add_argument("output", type=Path)
    validate.add_argument("--input", type=Path, help="request CSV for row and case-id checks")
    validate.set_defaults(handler=_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "run" and args.workers < 1:
        parser.error("--workers must be at least 1")
    try:
        return args.handler(args)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"ghostdata: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
