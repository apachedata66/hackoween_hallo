# DECISIONS

Every non-obvious choice, its reason, and the evidence for it (playbook J2,
section 11). Both people append here. Newest entries at the bottom of each
section.

## Decisions

### D1 - Source of truth: official repo wins (2026-11-04, A)

The official files (`AGENTS.md`, `problem_statement.md`, `README.md`,
`agent_trace_instructions.md`, `dataset/`) were copied from
`https://github.com/interviewstreet/hackerrank-orchestrate-october26.git`.
Where the team playbook PDF and the official repo disagree, the official repo
wins (playbook page 2, "Honest caveat"). Examples already noted:

- Evaluation reports must be at `evaluation/evaluation_report.md` and
  `evaluation/usage_report.md` (AGENTS.md 6.8) - a top-level `evaluation/`
  folder is explicitly allowed by the official README packaging section.
- `code/main.py` is the documented Python entry point (AGENTS.md 6.10);
  the playbook's `src/ghostdata/` package is imported by it, not a conflict.

### D2 - Repository and dataset layout (2026-11-04, A)

- Working repo `main` is based on the team repo
  `https://github.com/apachedata66/hackoween_hallo.git` (initial commit).
- `dataset/` was copied from the official repo and is **git-ignored** before
  the first commit (playbook section 4 / AGENTS.md 6.9). Only `.env.example`
  is ever committed for configuration; `.env` is ignored.
- The playbook PDF stays in the repo root as shared team documentation.

### D3 - Data contract drafted by A for B's review (2026-11-04, A) [J1]

`src/ghostdata/contract/` now contains the section-5 dataclasses
(`ResolvedIdentity`, `ResourceState`, `CaseAuditInput`) plus the output
enums and the 15 allowed (phase, operation, state) pairs transcribed
verbatim from `problem_statement.md`. Person B owns `contract/` long-term
(task B1) and should review/extend this file; any rename or removal needs
both people's agreement (section 5 rule).

### D4 - Deterministic core, LLM off by default (2026-11-04, A)

`config/settings.yaml` ships with `llm.enabled: false`. The core pipeline
must produce the same bytes with no LLM configured (`--no-llm` fallback,
playbook section 11). LLM use is restricted to OCR/vision/ambiguous text and
is always cached and tracked in `src/ghostdata/llm/`.

## Open questions [CONFIRM]

Carried over from playbook section 16 - answer with evidence, then move them
to Decisions.

- [ ] Sorting by `system_id` / `resource_id`: plain string order or natural
      order (account_10 vs account_9)? Test against `sample_output.csv`.
- [ ] How is `NOT_APPLICABLE` triggered by `request_text`? (AGENTS.md 6.5
      says non-deletion requests - access, correction, export, opt-out.)
- [ ] Timezone handling for naive timestamps in activity/evidence files
      (normalise to UTC?).
- [ ] Email hash scheme in `user_identities.csv` (reverse-engineer; verify
      against `email_hash` column).
- [ ] Tie-breaking for equal timestamps when replaying `system_activity`.
- [ ] Which log.txt counts for a two-person, two-machine team?
- [ ] Exact deadline / upload portal / size limits - not configured in the
      official repo; do not invent one (AGENTS.md 3.3).
