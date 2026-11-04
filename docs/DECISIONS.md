# DECISIONS

Working-agreement log (playbook §6, task J2): every decision that affects the
shared contract or the answer format, with the evidence behind it. Both people
agree before code changes; add a row, do not edit history.

Format: date — decision — evidence — who.

---

## Observed conventions in the official sample_output.csv (task J5, inferred — never copied)

Read programmatically to infer rules; no sample answer was copied into code.

- 32 samples: 10 COMPLETE, 22 INCOMPLETE, 0 NOT_APPLICABLE.
- COMPLETE rows contain VERIFICATION steps only, every step citing an evidence id.
- INCOMPLETE rows: findings cite evidence; remediation and future-verification
  steps use an empty evidence id (empty count always == steps minus findings).
- INCOMPLETE rows also verify records that require no remediation (retained
  audit records, already-absent records) — verification covers the required
  final state, not only what was just fixed.
- Reported workflow status frequently disagrees with the gold status
  (e.g. case_05 reported COMPLETE → gold INCOMPLETE).

---

## 2026-11-04 — Repository split: code here, dataset in the official checkout

**Decision.** Solution code lives in this repository (`hackoween_hallo`). The
challenge dataset, `AGENTS.md`, `problem_statement.md`, and the `log.txt`
transcript stay in the official challenge checkout and are never committed here.

**Evidence.** Playbook §6: ".gitignore must exclude dataset/, .env, caches,
venvs and zips BEFORE the first big commit"; §16/J6: "Datasets stay out of git
and zip." The official README requires the final `output.csv` at the root of the
*challenge* checkout, and `log.txt` next to the official `AGENTS.md`.

**Resolution order for dataset paths.** `GHOSTDATA_DATASET` environment variable,
then `<repo>/dataset`. No absolute paths hardcoded in source.

## 2026-11-04 — Package layout follows the official repo, not the playbook sketch

**Decision.** Code lives in `code/ghostdata/...` (import package `ghostdata`),
matching the official starter layout, rather than the playbook's `src/ghostdata/`
sketch.

**Evidence.** Official README: "Build your solution in `code/main.py`"; AGENTS.md
§6.10: "If using Python, `code/main.py` is a good entry point." Playbook §1:
"If the official repo and this playbook disagree, the official repo wins."

## 2026-11-04 — Ordering is plain string order

**Decision.** Within a phase: official operation table order, then `system_id`,
then `resource_id`, all compared as plain Unicode strings (so `search_10` sorts
before `search_9`).

**Evidence.** problem_statement.md §Rules: "follow the operation order in the
table above, then `system_id` and `resource_id` in ascending order."
`tests/test_contract.py::test_sample_steps_already_follow_string_order` passes
against the official `sample_output.csv`, which is the tie-breaker for the
string-vs-natural ambiguity the playbook flagged as `[CONFIRM]`.

## 2026-11-04 — `reported_status` is never an input to the verdict

**Decision.** `plan_case()` reads request text, identity, resources, and the
rulebook only. `reported_status` may be shown later in the UI diff, never in the
decision path.

**Evidence.** AGENTS.md §6.5: "do not accept `reported_status` or
`reported_result` as proof"; §1 golden rule in the playbook.

## 2026-11-04 — Unclear request text audits, it does not guess NOT_APPLICABLE

**Decision.** `classify_request()` returns AUTHORIZED / NOT_AUTHORIZED /
UNCLEAR. UNCLEAR text is audited with a warning recorded, not classified as
NOT_APPLICABLE.

**Evidence.** AGENTS.md §6.5: a request for access/correction/export/marketing
opt-out is NOT_APPLICABLE — those are known non-deletion asks (the
`_NON_DELETE_MARKERS` list). Absence of a deletion marker is not proof that no
deletion was requested; a missed deletion is worse than a review flag. The
final accuracy of this heuristic is measured by the scorer (task B7) against the
official samples before it is trusted.

## Open questions

- Exact trigger distribution for NOT_APPLICABLE across the 518 cases — confirm
  with the scorer once the evidence engine can run the samples (playbook J5:
  infer conventions from samples, never copy answers).
- Which machine owns the final `log.txt` for a two-person team (playbook §6) —
  currently the official checkout on this machine; confirm with organisers
  whether a combined transcript is accepted.
