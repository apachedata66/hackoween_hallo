# User Guide

Ghost Data audits deletion requests and explains what evidence supports the result. The command line and future UI use the same planner; the UI does not set or change verdicts.

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

The CLI command layer is ready, but end-to-end audit commands require Person A's `ghostdata.evidence.pipeline.build_case_audit_inputs` provider. Until it is available, `run` exits with a clear message and writes no predictions. The web UI is also pending, so this guide has no UI screenshots yet.

## Understanding results

- `COMPLETE` means the planner found evidence-backed verification steps for the required state.
- `INCOMPLETE` includes evidence-backed findings, proposed fixes, and checks to perform afterward.
- `NOT_APPLICABLE` means the request text did not authorize deletion; its steps array is empty.

The previous workflow status is informational. The audit uses evidence at `audit_at` and the policy in `deletion_rules.csv` to make the decision.

## Troubleshooting

| Message | What to check |
| --- | --- |
| Dataset not found | Set `GHOSTDATA_DATASET` to the official `dataset` directory. |
| Evidence engine is not installed | Wait for Person A's provider module, then retry. No output was written. |
| Output failed validation | Read each reported row and fix ordering, evidence references, or status-specific steps before submission. |
| A case ID was not found | Confirm it exists in the selected request CSV. |

For a contract-only check, run `python -m unittest discover -s tests -v`. The full audit command becomes usable once the evidence provider is integrated.
