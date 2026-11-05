"""Generate the required evaluation report from scorer output and custom cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "code"))

from evaluation.custom_cases import run_cases  # noqa: E402
from evaluation.score_samples import format_report, score  # noqa: E402
from ghostdata.contract.csv_io import read_output  # noqa: E402
from ghostdata.paths import dataset_dir  # noqa: E402


def _display_path(path: Path) -> str:
    """Keep report metadata portable instead of recording temporary absolute paths."""
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def render_report(
    predicted: Path,
    gold: Path,
    failures: str,
    improvements: str,
    prediction_label: str | None = None,
) -> str:
    metrics = score(read_output(gold), read_output(predicted))
    custom = run_cases()
    lines = [
        "# Evaluation Report",
        "",
        "## Sample benchmark",
        "",
        "Metrics compare public sample harness predictions with public gold. "
        "Missing prediction cases count as false negatives for step recall and field accuracy. "
        "They do not represent hidden full-dataset accuracy.",
        "",
        "```text",
        format_report(metrics, show=20),
        "```",
        "",
        "## Custom evaluation cases",
        "",
        f"Ran {len(custom)} hand-built cases; {sum(row['passed'] for row in custom)} passed.",
        "",
        "| Case | Scenario | Result | Details |",
        "| --- | --- | --- | --- |",
    ]
    for row in custom:
        details = (
            "; ".join(row["problems"]) or "Expected status and steps matched; output validated."
        )
        lines.append(
            f"| {row['case_id']} | {row['title']} | "
            f"{'PASS' if row['passed'] else 'FAIL'} | {details} |"
        )
    lines.extend(
        [
            "",
            "## Failures found",
            "",
            failures.strip()
            or (
                "No failure notes were supplied. Add the observed failures from the "
                "latest run before submission."
            ),
            "",
            "## Improvements made",
            "",
            improvements.strip()
            or (
                "No improvement notes were supplied. Add the fixes made in response "
                "to measured failures before submission."
            ),
            "",
            "## Run metadata",
            "",
            f"- Prediction file: `{prediction_label or _display_path(predicted)}`",
            f"- Gold file: `{_display_path(gold)}`",
            "- Full-dataset accuracy: not measured here; the challenge does not "
            "provide full-dataset gold labels.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate evaluation_report.md")
    parser.add_argument("--pred", type=Path, required=True, help="prediction CSV to score")
    parser.add_argument("--gold", type=Path, default=dataset_dir() / "sample_output.csv")
    parser.add_argument("--out", type=Path, default=ROOT / "evaluation" / "evaluation_report.md")
    parser.add_argument("--failures", default="", help="honest narrative of failures observed")
    parser.add_argument("--improvements", default="", help="fixes made in response to evaluation")
    parser.add_argument(
        "--prediction-label",
        help="description to record instead of the prediction file path",
    )
    args = parser.parse_args(argv)
    try:
        report = render_report(
            args.pred,
            args.gold,
            args.failures,
            args.improvements,
            prediction_label=args.prediction_label,
        )
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"evaluation report: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
