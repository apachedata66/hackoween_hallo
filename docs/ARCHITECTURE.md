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
                                      CLI <── FastAPI <── React UI
```

## Components

- `code/ghostdata/loaders/`: CSV, PDF, text, JSON, log, image, and SQL evidence loaders.
- `code/ghostdata/identity/`: current and historical identity resolution.
- `code/ghostdata/state/`: time-bounded evidence and activity reconstruction.
- `code/ghostdata/detectors/`, `policy/`, and `planner/`: remaining records, exposed identifiers, active recreation paths, required treatments, and output steps.
- `code/ghostdata/validate.py`: output and evidence-reference validation.
- `code/ghostdata/cli.py`: batch entry point used by both terminal and UI runs.
- `code/ghostdata/api/app.py`: local FastAPI run and case API. It invokes the CLI as a subprocess, validates the result, and never recomputes verdicts.
- `ui/src/`: React and TypeScript review surface. Vite serves it in development and builds local static assets for FastAPI in production.

## Guarantees and limits

1. Workflow-reported status is not used as proof of deletion.
2. Evidence after `audit_at` must not affect the case result.
3. Policy-required retained, redacted, anonymized, and tombstone records receive their prescribed treatment.
4. The UI exports only after the existing validator accepts the CLI output.
5. The engine runs locally and does not transmit case data or make external model calls.

The UI shows an on-demand evidence drawer for cited files, activity claims, and identity-history rows. File excerpts are limited to lines matching the selected subject or resource, mask identifiers from the participant-facing identity files, and remain hidden when the source is after the case cutoff. The UI remains a read-only review and export layer.
