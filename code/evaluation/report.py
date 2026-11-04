"""Generate the required evaluation report from scorer output and custom cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from ghostdata.paths import dataset_dir
from evaluation.custom_cases import run_cases
from evaluation.score_samples import format_report, score
from ghostdata.contract.csv_io import read_output


def render_report(predicted: Path, gold: Path, failures: str, improvements: str) -> str:
    metrics = score(read_output(gold), read_output(predicted))
    custom = run_cases()
    lines = [
        "# Evaluation Report", "",
        "## Sample benchmark", "",
        "Metrics below compare the supplied prediction file with the public gold sample. "
        "They do not represent hidden full-dataset accuracy.", "",
        "```text", format_report(metrics, show=20), "```", "",
        "## Custom evaluation cases", "",
        f"Ran {len(custom)} hand-built cases; {sum(row['passed'] for row in custom)} passed.", "",
        "| Case | Scenario | Result | Details |", "| --- | --- | --- | --- |",
    ]
    for row in custom:
        details = "; ".join(row["problems"]) or "Expected status and steps matched; output validated."
        lines.append(f"| {row['case_id']} | {row['title']} | {'PASS' if row['passed'] else 'FAIL'} | {details} |")
    lines.extend([
        "", "## Failures found", "", failures.strip() or
        "No failure notes were supplied. Add the observed failures from the latest run before submission.",
        "", "## Improvements made", "", improvements.strip() or
        "No improvement notes were supplied. Add the fixes made in response to measured failures before submission.",
        "", "## Run metadata", "",
        f"- Prediction file: `{predicted}`",
        f"- Gold file: `{gold}`",
        "- Full-dataset accuracy: not measured here; the challenge does not provide full-dataset gold labels.",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate evaluation_report.md")
    parser.add_argument("--pred", type=Path, required=True, help="prediction CSV to score")
    parser.add_argument("--gold", type=Path, default=dataset_dir() / "sample_output.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "code" / "evaluation" / "evaluation_report.md")
    parser.add_argument("--failures", default="", help="honest narrative of failures observed")
    parser.add_argument("--improvements", default="", help="fixes made in response to evaluation")
    args = parser.parse_args(argv)
    try:
        report = render_report(args.pred, args.gold, args.failures, args.improvements)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"evaluation report: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
