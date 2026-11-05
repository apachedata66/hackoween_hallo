# User Guide

Ghost Data audits deletion requests and explains what evidence supports the result. The command line and React UI use the same planner; the UI does not set or change verdicts.

## Set up

Use Python 3.11 or newer. Keep the organizer dataset outside the solution repository. In PowerShell, point the app at the official dataset checkout:

```powershell
$env:GHOSTDATA_DATASET = "C:\path\to\official\dataset"
```

The path must contain `deletion_requests.csv`, `deletion_rules.csv`, the identity and activity CSV files, and `evidence/`.

## Commands

From the solution repository root:

```powershell
python code/main.py --help
python code/main.py run --samples --out output.samples.csv
python code/main.py run --case case_001 --explain
python code/main.py run --out output.csv --workers 2 --resume
python code/main.py validate output.csv --input "$env:GHOSTDATA_DATASET\deletion_requests.csv"
```

`run` defaults to all requests and writes `output.csv` at the repository root. Sample runs and single-case runs use separate default filenames so they do not overwrite the submission output. Use `--no-llm` to turn off optional model processing. `--resume` asks the evidence provider to reuse its extraction cache. `--workers` controls parallel evidence processing. `--explain` prints the verdict, prior workflow status, timeline, evidence-based reasons, and proposed actions.

The CLI calls the evidence adapter at `code/ghostdata/evidence/pipeline.py`, which loads the participant-facing dataset through the evidence engine. Cases that cannot be represented with evidence-backed steps stop the batch and produce a PII-free `evaluation/manual_review.md`; no prediction file is written.

## Local review interface

Install `.[ui]`, build the React frontend in `ui/` with `npm install` and `npm run build`, then start the local FastAPI service:

```powershell
python -m pip install -e ".[ui]"
Push-Location ui; npm install; npm run build; Pop-Location
python -m uvicorn ghostdata.api.app:app --app-dir code --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. Start a full audit or a public sample run. The progress panel reflects the CLI's reported request counts, elapsed time, estimated remaining time, and warnings. When a run passes validation, filter and search the case list, inspect a case and its evidence, then download the validated CSV. Identifiers are masked by default and can be revealed for the selected case. Evidence created after the case cutoff is not shown as verdict evidence.

## Understanding results

- `COMPLETE` means the planner found evidence-backed verification steps for the required state.
- `INCOMPLETE` includes evidence-backed findings, proposed fixes, and checks to perform afterward.
- `NOT_APPLICABLE` means the request text did not authorize deletion; its steps array is empty.

The previous workflow status is informational. The audit uses evidence at `audit_at` and the policy in `deletion_rules.csv` to make the decision.

## Troubleshooting

| Message | What to check |
| --- | --- |
| Dataset not found | Set `GHOSTDATA_DATASET` to the official `dataset` directory. |
| Manual review report created | Review the listed evidence and resolve unknown or unrepresentable cases before generating a submission file. |
| Output failed validation | Read each reported row and fix ordering, evidence references, or status-specific steps before submission. |
| A case ID was not found | Confirm it exists in the selected request CSV. |

For a contract-only check, run `python -m unittest discover -s tests -v`. The full audit command becomes usable once the evidence provider is integrated.
