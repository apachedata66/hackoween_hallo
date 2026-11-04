# Architecture

## Design

The system uses a deterministic evidence and policy pipeline. It makes no model calls in the current configuration. The runner reads participant-facing data, resolves identity links, reconstructs resource state at each `audit_at`, applies deletion policy, builds ordered steps, validates them, and serializes `output.csv`.

```text
request CSV ── identity resolver ── evidence loaders ── state reconstruction
                                                          │
                                                          v
                                      detectors ── policy ── planner
                                                          │
                                                          v
                                      validator ── CSV output
                                                          ^
                                      CLI <── Streamlit UI
```

## Components

- `src/ghostdata/loaders/`: CSV, PDF, text, JSON, log, image, and SQL evidence loaders.
- `src/ghostdata/identity/`: current and historical identity resolution.
- `src/ghostdata/state/`: time-bounded evidence and activity reconstruction.
- `src/ghostdata/detectors/`, `policy/`, and `planner/`: remaining records, exposed identifiers, active recreation paths, required treatments, and output steps.
- `src/ghostdata/validate.py`: output and evidence-reference validation.
- `src/ghostdata/cli.py`: batch entry point used by both terminal and UI runs.
- `ui/app.py`: local Streamlit review surface. It invokes the CLI as a subprocess, validates the result, and never recomputes verdicts.

## Guarantees and limits

1. Workflow-reported status is not used as proof of deletion.
2. Evidence after `audit_at` must not affect the case result.
3. Policy-required retained, redacted, anonymized, and tombstone records receive their prescribed treatment.
4. The UI exports only after the existing validator accepts the CLI output.
5. The engine runs locally and does not transmit case data or make external model calls.

The UI currently shows evidence references and case timelines; it does not yet provide source excerpts in an evidence drawer. The UI remains a read-only review and export layer.
