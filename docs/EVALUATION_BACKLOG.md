# Evaluation Backlog

This checklist tracks evaluation readiness for Ghost Data Still Exists. It
uses participant-facing data and public sample answers only. The hidden answer
set is unavailable, so public-sample metrics are diagnostic and cannot promise
a particular final rank.

## Completed and recorded

- [x] Add `evaluation/evaluation_report.md` with status, step, field, and
  sequence metrics, benchmark failures, limitations, and improvements.
- [x] Add 16 team-authored synthetic cases; the latest recorded run reports
  all 16 passing. This exceeds the requirement of at least three cases.
- [x] Run the deterministic audit over all 518 requests, produce the required
  `output.csv`, and validate its row/output contract.
- [x] Add `evaluation/usage_report.md` for the full run. The engine made no
  model calls, so provider/model are none and token and cost totals are zero.
  Keep this report factual; do not add a model solely to make the report look
  more substantial.

## Next work, in priority order

### P0 — Improve measured public evaluation

- [ ] Reproduce the 32-case public benchmark from a clean checkout and
  investigate the three cases currently reported as missing. Restore coverage
  only when participant-visible evidence supports identity and resource links;
  otherwise document the exact unresolved reason.
- [ ] Raise ordered sequence accuracy (currently reported as 0.2188). Triage
  missing and extra steps by case, then fix general evidence, identity, policy,
  or ordering rules rather than adding case-ID-specific behavior.
- [ ] Review step recall (currently 0.8201) and precision (currently 0.9509)
  together. Focus on recurring missing verification checks and extra findings;
  do not improve recall by emitting unsupported steps.
- [ ] Re-run the public scorer after every behavior change and record before /
  after status accuracy, step precision/recall/F1, per-field accuracy,
  sequence accuracy, and benchmark coverage.

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

- [ ] Provide one documented command that regenerates the public benchmark
  report and custom-case results from a clean environment.
- [ ] Ensure evaluation reports are regenerated from current scorer output
  after engine changes; remove stale metrics or run descriptions.
- [ ] Record full-run provenance in the usage report (run time, command,
  request count, and output checksum) so the zero-token figures are tied to
  the exact `output.csv` produced. Never include secrets or personal data.

### P2 — Final submission gate

- [ ] Run the documented clean-install command and full 518-case CLI from the
  repository root; validate the resulting CSV and confirm exact case coverage.
- [ ] Rebuild `code.zip` after the final code, reports, and React bundle are
  ready. Inspect the archive to confirm it contains runnable code, README,
  configuration, and both evaluation reports, while excluding `dataset/`,
  caches, virtual environments, nested archives, credentials, and secrets.
- [ ] Keep `output.csv` and `log.txt` as the separate submission deliverables
  required by the repository contract; prepare the AI interview explanation
  of architecture, evidence handling, evaluation, limits, and improvements.

## Current public benchmark baseline

The current report records 32 gold cases, 29 scored, and 3 missing; status
accuracy 0.9062; step precision 0.9509; step recall 0.8201; step F1 0.8807;
and sequence accuracy 0.2188. These are public-sample results, not hidden
full-dataset accuracy. Re-check them whenever the evaluation report is
regenerated.
