# Evaluation Backlog

This checklist tracks evaluation readiness for Ghost Data Still Exists. It
uses participant-facing data and public sample answers only. The hidden answer
set is unavailable, so public-sample metrics are diagnostic and cannot promise
a particular final rank.

## Completed and recorded

- [x] Add `evaluation/evaluation_report.md` with status, step, field, and
  sequence metrics, benchmark failures, limitations, and improvements.
- [x] Add 17 team-authored synthetic cases; the latest recorded run reports
  all 17 passing. The rule is a minimum of three, with no upper limit, so keep
  them for wider coverage.
- [x] Run the deterministic audit over all 518 requests and validate the
  output contract. The current root `output.csv` was regenerated with local
  OCR after the link-only safety fix and contains exactly 518 sorted cases.
- [x] Record current full-run provenance and zero model usage. The latest run
  completed in 56.02 seconds with 0 model calls, tokens, or cost; its output
  checksum is recorded in `evaluation/usage_report.md`.
- [x] Integrate Person B's JSON timestamp-precedence fix and loader regression
  tests. Re-running the benchmark showed no public prediction changes; the
  fix addresses explicit nested timestamps that can affect hidden cases.
- [x] Correct link-only resource promotion: `LINK_RESOURCE_IDENTITY` proves an
  association, not current resource presence. Require independent resource
  evidence before planning a state finding; regression coverage also confirms
  a filename alias can join a relationship to an independent same-system
  listing without letting the relationship alone prove presence.
- [x] Configure local Tesseract 5.5.3 and rerun all 518 requests. OCR linked
  the nine screenshot cases that had previously been held; the final run
  emitted no manual-review cases and validated the CSV.
- [x] Make extraction-cache keys sensitive to OCR/tool availability so empty
  results cached before Tesseract installation cannot hide newly readable
  evidence. A regression test covers the no-OCR-then-OCR transition.
- [x] Do not add a future disable verification for an already inactive flow
  to an incomplete case when that flow is not being remediated. Public case_15
  now matches exactly; a custom regression covers this contract rule.
- [x] In incomplete plans, omit a future absence check when the only negative
  state observation predates the deletion request and no later state observation
  exists. Public case_17 now matches exactly in the OCR-enabled benchmark.
- [x] Run the Python suite (83 tests), Ruff, and the React production build.

## Next work, in priority order

### P0 — Improve measured public evaluation

- [x] Reproduce the 32-case public benchmark and investigate the three missing
  cases. `case_01`, `case_02`, and `case_04` have no in-scope participant
  evidence linked by the current engine. The public gold names account and
  analytics resource IDs that are absent from the relevant pre-cutoff SQL
  observations and have no identity-linked activity resource event. Keep these
  cases in manual review; do not infer IDs from sequential case numbering.
- [ ] Raise ordered sequence accuracy (currently 0.2500 with OCR enabled). Triage
  remaining missing and extra steps by case, then fix general evidence,
  identity, policy, or ordering rules rather than adding case-ID-specific
  behavior. Do not emit steps without participant-visible linkage.
- [ ] Review step recall (currently 0.8031) and precision (currently 0.9627)
  together. Focus on recurring missing verification checks and extra findings;
  do not improve recall by emitting unsupported steps.
- [ ] Review the OCR-enabled public sample mismatch in `case_07`: the engine
  finds `object_19` through cutoff-eligible `activity_4007` plus independent
  screenshot evidence `evidence_46`; public gold omits it. Keep the supported
  finding while investigating the mismatch; do not add a case-specific filter.
- [x] Correct the scorer so missing prediction cases count as false negatives
  and extra prediction cases count as false positives in step and field
  metrics. Add regression coverage for both cases and rerun the scorer.
- [x] Add `python code/evaluation/run_public_benchmark.py` to reproduce the
  predictions, 16 synthetic cases, metrics, and evidence-gap notes from the
  current engine and participant-facing public sample.
- [x] Re-run the public scorer and refresh `evaluation/evaluation_report.md`
  after the scorer correction.

### P1 — Expand regression coverage

- [ ] Add targeted synthetic cases for audit-time cutoffs, evidence captured
  after `audit_at`, historical identifiers, decoy records, conflicting
  operational claims versus direct evidence, SQL replica drift, and
  downstream-copy / restore ordering where not already covered.
- [ ] Add ingestion-level fixtures for PDF, image, log, JSON, and SQL evidence.
  Planner-only fixtures do not establish that real evidence parsing and
  identity linking work end to end.
- [ ] Resolve and document the must-retain-record-missing case: confirm the
  expected status and safe behavior from the contract, and add a regression
  that prevents silent success or invented remediation.
- [ ] For every custom case, assert the complete serialized result, allowed
  fields and enum values, evidence references, consecutive numbering, and
  exact phase/operation/system/resource ordering.

### P1 — Make evaluation repeatable and auditable

- [x] Provide one documented command that regenerates the public benchmark
  report and custom-case results from a clean environment.
- [x] Regenerate the evaluation report from current scorer output after the
  teammate's engine change and remove stale benchmark metrics.
- [x] Record full-run provenance in the usage report (UTC start/completion,
  duration, command, request count, output path, and SHA-256 checksum) so the
  zero-token figures are tied to the exact `output.csv` produced. Never include
  secrets or personal data.

### P2 — Final submission gate

- [x] Run the full 518-case CLI from the repository root with OCR available;
  validate the resulting CSV and confirm exact case coverage.
- [ ] Repeat the run from a clean dependency install to verify the README
  setup path independently of the existing Python environment.
- [x] Rebuild `code.zip` after the final code, reports, interview notes, and React bundle are
  ready. Inspect the archive to confirm it contains runnable code, README,
  configuration, and both evaluation reports, while excluding `dataset/`,
  caches, virtual environments, nested archives, credentials, and secrets.
- [x] Keep `output.csv` and `log.txt` as the separate submission deliverables
  required by the repository contract; add `evaluation/interview_prep.md` with
  the architecture, evidence handling, demo, measured results, and limitations.

## Current public benchmark baseline

The latest OCR-enabled report records 32 gold cases, 29 predicted, and 3 held
for manual review; status accuracy 0.9062; step precision 0.9627; step recall
0.8031; step F1 0.8757; sequence accuracy 0.2500. Field accuracy is phase
0.8000, system 0.5846, resource 0.5846, operation 0.6205, state 0.6359, and
evidence 0.8051. These public-sample results are diagnostic, not hidden
full-dataset accuracy. Earlier no-OCR metrics did not include the supported
`object_19` finding in case_07; keep the current evidence-grounded output and
review the public-gold disagreement before drawing conclusions. Re-check all
metrics whenever the report is regenerated.
