# AI Interview Preparation

Use this as a rehearsal outline. Explain the implementation in your own words
and be precise about what has and has not been measured.

## 60-second overview

Ghost Data Still Exists is a local, deterministic deletion-audit agent. It
resolves current and historical identifiers, reconstructs resource state from
participant-facing records at each request's `audit_at`, applies the supplied
retention policy, and produces ordered, evidence-cited findings and remediation
plans. The React review screen shows actual run progress and lets an operator
inspect the evidence behind a case. The tool proposes remediation; it does not
execute deletions.

## Architecture and evidence flow

1. Load requests, current identities, identity history, activity, policies,
   and the evidence manifest from `dataset/`.
2. Resolve the request email to a subject using the current snapshot and
   historical ownership intervals.
3. Extract text from participant evidence. Images use local Tesseract OCR;
   SQL snapshots are parsed as structured records. Extraction caches account
   for OCR-tool availability so an earlier failed OCR attempt cannot mask a
   later successful one.
4. Match evidence to the subject and reconstruct state using only observations
   available by `audit_at`. Workflow statuses and activity events are claims;
   an independent observation is required to prove that a resource exists.
5. Apply category rules and order the findings, proposed actions, and
   verification steps. Validate IDs, fields, allowed operations, ordering, and
   one output row per request before publishing the CSV.

## Safety and judgment

- A request for access, correction, or opt-out is not treated as a deletion
  request.
- A stable account tombstone may remain, but direct identifiers must be
  removed when policy requires it.
- Retained records are preserved; shared messages are redacted when policy
  requires retention; unsafe sync and restore paths are handled before dependent
  records.
- Evidence after the audit cutoff is excluded. A link event can associate a
  resource with a subject but cannot prove that the resource still exists.
- When evidence cannot support a valid answer, hold the case for review instead
  of guessing an ID or emitting an unsupported step.

## Evaluation results to state accurately

- The current full run produced and validated 518 rows in 56.02 seconds.
- The deterministic audit made 0 model calls and used 0 model tokens; local
  Tesseract 5.5.3 handled screenshot OCR.
- All 17 participant-created synthetic cases pass. The Python suite, Ruff, and
  React production build pass.
- On the 32-case public sample, status accuracy is 90.62%, step precision
  95.68%, step recall 80.31%, step F1 87.32%, and exact sequence accuracy
  21.88%. The sequence score improved by one exact case after removing a
  future disable check for an already inactive flow. Three public cases are held because the engine cannot link the gold
  resource IDs to cutoff-eligible participant evidence.
- These public-sample metrics do not measure hidden full-dataset accuracy.
  The OCR-enabled benchmark also exposes one disagreement: public gold omits a
  record supported by a pre-cutoff identity-link event and an independent
  screenshot. We retain the supported finding and disclose the mismatch.

## Likely questions

**Why use a deterministic engine instead of sending everything to an LLM?**

Deletion status depends on temporal identity links, policy conditions, and
resource evidence that must be auditable. Deterministic replay makes those
decisions reproducible and keeps personal data local. OCR is local too. A model
could help with ambiguous language in a future version, but it should not
replace evidence checks or policy enforcement.

**How do you prevent a false `COMPLETE` result?**

We ignore reported workflow status as proof, reconstruct the state at the
cutoff, require evidence-backed checks, account for active data flows and
restore paths, and stop when a case cannot be represented safely.

**What are the largest remaining risks?**

Sequence and step recall are materially below the status score. Three public
sample cases lack participant-visible links to resources named by the sample
gold. There is also a public-gold disagreement on the OCR-supported
`object_19` attachment. The 32-case sample is not enough to estimate hidden
accuracy, so these results should not be presented as a win prediction.

**What makes this useful to an operator?**

It gives a cutoff-specific audit trail, explains each finding with a visible
evidence reference, surfaces background progress and warnings, and produces a
safe ordered plan for a human to review. It does not claim that proposed
remediation has already happened.

## Demo sequence

1. Run the full audit against the provided dataset and show live case progress.
2. Open a case marked incomplete; inspect its identity, evidence, and cutoff.
3. Show the finding, ordered remediation, and verification steps.
4. Open a completed case and point to the evidence-backed checks.
5. Show the output validation and usage report, then state the measured public
   metrics and limitations above.
