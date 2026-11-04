# ARCHITECTURE

Design principle (playbook section 4): **deterministic core, optional LLM at
the edges, thin UI on top.** Most of the problem is rule-based (look up,
replay, apply rules, sort), so deterministic code is more accurate,
reproducible, free and testable. An LLM is only justified for unstructured
input (scanned PDFs, images, free-text `request_text`), and every LLM call is
cached and logged for `evaluation/usage_report.md`.

## Repository layout

```text
hackoween_hallo/
  AGENTS.md                 transcript rules - do not edit
  log.txt                   append-only transcript (one machine owns final version)
  problem_statement.md      official spec (source of truth with AGENTS.md)
  pyproject.toml / requirements.txt
  .env.example              variable NAMES only, never values
  config/
    settings.yaml           paths, model names, timeouts, feature flags
    prompts/                every LLM prompt as a versioned file
  src/ghostdata/
    contract/               enums, dataclasses, allowed pairs        (A drafted, B owns)
    loaders/                csv, sqlite, log, json, pdf, image       (A)
    identity/               identity resolver                        (A)
    state/                  state-at-audit_at reconstructor          (A)
    detectors/              leftover, exposed-PII, flow, restore     (A)
    policy/                 rules parser, treatment, tombstones      (B)
    planner/                status decision, steps, sorter           (B)
    explain/                plain-English explanations               (B)
    llm/                    client wrapper, cache, cost tracker      (shared)
    cli.py                  one-command batch runner                 (B)
  code/main.py              official entry point (imports ghostdata)
  ui/                       Streamlit app - calls src only           (B)
  evaluation/               scorer, custom cases, required reports   (B + A)
  tests/                    unit + integration + golden tests        (both)
  docs/                     DATASET_NOTES, DECISIONS, USER_GUIDE, ARCHITECTURE
  scripts/                  validate_output.py, make_zip.py
  dataset/                  git-ignored, from the official repo
```

## Data flow per case

```text
case row -> identity resolver -> all identifiers (current + historical)
        -> evidence loaders (SQL replicas, logs, JSON, PDF/image) -> normalized records
        -> state reconstructor (replay system_activity up to audit_at) -> resource states
        -> detectors (leftovers, exposed PII, active flows, restore risks)
        -> policy engine (required treatment per resource)
        -> status decision -> step generator -> sorter -> validator
        -> output row  (+ explanation object for the UI)
```

## Invariants

1. **One code path.** CLI, UI download and scorer all call the same function;
   the UI can never change a verdict or `output.csv` (playbook 10.4).
2. **Evidence, not claims.** `reported_status` and `reported_result` are never
   used to decide a case - only for the reported-vs-actual diff in the UI.
3. **Time box.** Only information at or before `audit_at` decides the case.
4. **Never crash a batch.** A bad case gets a safe, flagged result plus a
   warning; chaos tests prove it (A14).
5. **Deterministic.** Same input -> byte-identical `output.csv`; sorted
   everything, no wall-clock in output, LLM cached by content hash.
