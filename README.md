# hackoween_hallo — Ghost Data Still Exists

Team repository for **HackerRank Orchestrate, October 2026**: *Ghost Data Still Exists*.
We build an AI-powered deletion-audit agent that proves whether a user's personal
data was actually deleted, or reports what still remains and the ordered steps to fix it.

> Official challenge repo (dataset, `AGENTS.md`, `problem_statement.md`) lives in a
> separate checkout. This repository holds the solution code only — `dataset/` is
> gitignored and never committed (see `docs/DECISIONS.md`).

## Requirements

- Python **3.11+** (developed on 3.12). Standard library only — `requirements.txt`
  is intentionally empty of runtime deps.
- A local copy of the challenge dataset (kept out of git).

## Setup

```powershell
git clone https://github.com/apachedata66/hackoween_hallo.git
cd hackoween_hallo

# Point the tools at your dataset checkout (optional if you run from a
# checkout that already has dataset/ next to code/):
$env:GHOSTDATA_DATASET = "C:\path\to\challenge\dataset"
```

Paths resolve in this order: `GHOSTDATA_DATASET` env var → `<repo>/dataset`.

## Run

```powershell
# Show CLI commands
python code/main.py --help

# Audit requests (requires Person A's evidence provider)
python code/main.py run

# Audit one case, explain results, or run the public sample requests
python code/main.py run --case case_001 --explain --out output.case.csv
python code/main.py run --samples --out output.samples.csv

# Validate an existing output file
python code/main.py validate output.csv --input dataset/deletion_requests.csv

# Build the evaluation report from the sample scorer and hand-built cases
python code/evaluation/report.py --pred output.samples.csv --failures "..." --improvements "..."

# Package the submission after both required reports exist
python scripts/make_zip.py

# Validate any output file against the official contract.
python scripts/validate_output.py output.csv --requests <requests.csv> --dataset <dataset-dir>

# Run the test suite (contract + validator).
python -m unittest discover -s tests -v
```

The CLI passes request rows to Person A's evidence provider, then sends each
`CaseAuditInput` through the shared planner and validates the complete output
before writing it. That provider is not present yet, so `run` currently stops
with an actionable message rather than writing guessed predictions. The
provider interface is `ghostdata.evidence.pipeline.build_case_audit_inputs`;
it receives requests, the dataset path, worker count, and the `--no-llm` and
`--resume` flags.

## Folder map

| Path | Owner | Purpose |
| --- | --- | --- |
| `code/ghostdata/contract/` | B | Output contract: allowed phase/operation/state triples, `Step`, ordering, CSV I/O |
| `code/ghostdata/policy/` | B | Typed rulebook from `deletion_rules.csv` + per-resource treatment engine |
| `code/ghostdata/planner/` | B | Request authorization, the four completion conditions, ordered step plan |
| `code/ghostdata/validate.py` | B | Strict `output.csv` validator with human-readable fixes |
| `code/main.py` | B | Python entry point for `run` and `validate` CLI commands |
| `scripts/validate_output.py` | B | CLI wrapper for the validator |
| `tests/` | both | Contract and validator tests |
| `code/evaluation/` | B | Scorer and the required evaluation/usage reports |
| `docs/USER_GUIDE.md` | B | Setup, CLI, result interpretation, and troubleshooting |
| `scripts/make_zip.py` | B | Safe code.zip builder with exclusions and secret scan |
| `docs/DECISIONS.md` | both | Decisions and their evidence (working agreement §6/J2) |

Person A owns the evidence engine (`loaders/`, `identity/`, `state/`, `detectors/`),
which produces `CaseAuditInput` for the planner.

## Design rules (non-negotiable)

1. **Evidence over claims.** `reported_status` and logged operation results are
   claims; only evidence establishes the state at `audit_at`.
2. **Deterministic core.** Rule-based where possible; any LLM use is at the
   unstructured edges only, cached and logged for the usage report.
3. **No hardcoding.** No golden labels, no case-family shortcuts, no answers
   copied from `sample_output.csv`.
4. **The UI never changes the verdict.** It only calls the engine.

## Status

| Milestone | State |
| --- | --- |
| B1 Output contract module | ✅ done — invalid triples cannot be constructed |
| B2 Strict validator | ✅ done — sample passes; deliberate mistakes rejected in tests |
| B3 Policy engine | ✅ done — 15 rules typed, unknown categories warn instead of guess |
| B4 Status decision | ✅ done — four conditions as named, unit-testable rules |
| B5/B6 Step generator + sorter | ✅ done — phase → operation → system_id → resource_id, renumbered last |
| B7 Scorer | ✅ done — status/step/field/sequence accuracy, confusion matrix, CI exit code |
| B8 Custom evaluation cases | ✅ done — 16 hand-built fixtures, all pass planner + validator |
| B10 Plain-English explainer | ✅ implemented — deterministic summaries from planner output; omits email addresses |
| B12 Usage tracker | ✅ implemented — records explicit provider/model/token/cost data; does not invent prices |
| Evidence engine (Person A) | ⏳ not started — blocks the 518-case run |
| B9 CLI command layer | ✅ implemented; end-to-end audit blocked on evidence-provider integration |
| B11 UI | ⏳ planned |
| B13 Evaluation report generator | ✅ implemented; final metrics require a prediction run |
| B14 README and user guide | 🟡 CLI guide drafted; UI screenshots wait for B11 |
| B15 Packaging script | ✅ implemented; package creation waits for required evaluation reports |
| B16 Per-case report export, B17 CI | ⏳ planned |

## Troubleshooting

- **`python` not found on Windows** — install from python.org or
  `winget install Python.Python.3.12`, then reopen the terminal.
- **`dataset directory not found`** — set `GHOSTDATA_DATASET` to the dataset
  folder of the official challenge checkout.
- **Validator says steps are "not in official order"** — sorting is plain
  Unicode string order on `system_id`/`resource_id`, not natural/numeric order.

## Submission

The submission (challenge [page](https://www.hackerrank.com/contests/hackerrank-orchestrate-october26/challenges/ghost-data-still-exists))
packages `README.md` + `code/` into `code.zip`, plus the root `output.csv`, the
`log.txt` transcript, and `code/evaluation/evaluation_report.md` +
`code/evaluation/usage_report.md`. Dataset, venvs, caches, and nested archives
are excluded.
