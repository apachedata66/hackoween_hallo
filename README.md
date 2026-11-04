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
# Load the deletion rules and validate the official sample output.
python code/main.py

# Validate any output file against the official contract.
python scripts/validate_output.py output.csv --requests <requests.csv> --dataset <dataset-dir>

# Run the test suite (contract + validator).
python -m unittest discover -s tests -v
```

The full 518-case audit runs through the same planner once the evidence engine
(Person A) supplies a `CaseAuditInput` per request. See **Status** below.

## Folder map

| Path | Owner | Purpose |
| --- | --- | --- |
| `code/ghostdata/contract/` | B | Output contract: allowed phase/operation/state triples, `Step`, ordering, CSV I/O |
| `code/ghostdata/policy/` | B | Typed rulebook from `deletion_rules.csv` + per-resource treatment engine |
| `code/ghostdata/planner/` | B | Request authorization, the four completion conditions, ordered step plan |
| `code/ghostdata/validate.py` | B | Strict `output.csv` validator with human-readable fixes |
| `code/main.py` | B | Entry point: loads rules, validates samples, runs the audit |
| `scripts/validate_output.py` | B | CLI wrapper for the validator |
| `tests/` | both | Contract and validator tests |
| `code/evaluation/` | B | Scorer and the required evaluation/usage reports |
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
| Evidence engine (Person A) | ⏳ not started — blocks the 518-case run |
| B7 Scorer, B8 custom cases | ⏳ next |
| B9 CLI, B10 explainer, B11 UI | ⏳ planned |
| B12–B15 reports, README, packaging | ⏳ planned |

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
