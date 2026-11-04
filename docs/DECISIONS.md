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

### D5 - Timestamp policy: everything is aware UTC (2026-11-04, A)

`src/ghostdata/loaders/timeutil.py` is the only place time is parsed:
ISO-8601, trailing `Z` -> UTC, **naive timestamps treated as UTC**, output
always an aware UTC datetime. Bad/empty timestamps raise `LoaderError` with a
plain-language message naming the field - never a traceback. All observed
dataset timestamps carry `Z`, so the naive rule is a safety net, not a guess.

### D6 - `email_hash` scheme confirmed: SHA-256 (2026-11-04, A)

Verified against the data: SHA-256 of the normalised (lower-cased, stripped)
email matches `user_identities.email_hash` on 200/200 sampled rows (64-hex
digest; SHA-1/MD5 do not match). The resolver publishes hash variants for
**every** known address (current + historical), computed with this scheme, so
detectors can find a person in evidence that only shows a hash.
*Resolves the "hash scheme" [CONFIRM].*

### D7 - Identity evidence = the owner's `audit_id` rows (2026-11-04, A)

`ResolvedIdentity.identity_evidence_ids` carries the `audit_id` values of the
resolved user's identity events (email / email_hash / phone), oldest first -
these are the participant-visible ids that prove each link. Users with no
audit rows legitimately have an empty list: the current snapshot row has no
citable id of its own. `LINK_RESOURCE_IDENTITY` activity ids are kept for the
resource-linking stage (detectors), not for identity. *[CONFIRM: is an empty
list acceptable for snapshot-only users, or should we cite something else?]*

### D8 - UI stack: React + FastAPI, local-only (2026-11-04, A; user decision)

Decision recorded per the user's explicit direction: the web interface is a
**React** front end talking to a **FastAPI** back end - not Streamlit.
Agreed shape:

- `ui/` holds the React app (Vite scaffold) and `src/ghostdata/api/` holds the
  FastAPI app; both call the same engine functions the CLI calls - the UI can
  never change a verdict or `output.csv` (playbook 10.4).
- **One command** starts everything; FastAPI also serves the built React
  assets from `ui/dist/` so a non-technical user runs a single process on
  `localhost` with no external requests, no telemetry, evidence never leaves
  the machine.
- During development, Vite's dev server proxies `/api` to FastAPI.
- Accessibility/UX requirements of §10 still apply: colour is never the only
  signal, plain-English first, masked emails with reveal toggle, friendly
  errors (never stack traces), phone-width layout, read-only/simulation-only.

### D9 - Identity ownership timeline (2026-11-04, A)

The resolver rebuilds, per address, who owned it and when (from
`user_audit_log` releases/acquires + the current snapshot), then picks the
owner **at `requested_at`**:
- exactly one owner at that moment -> used silently;
- address released before `requested_at` but only ever held by one user ->
  used silently (no warning noise);
- several candidates / genuine ambiguity -> most recent owner wins **and a
  plain-language warning is recorded** (feeds the UI warnings centre);
- unknown address -> empty identity + warning, never an exception.
An address reused by another user resolves to whichever user held it at the
request time, so the other person's records are never touched (playbook
edge case 9 / test case 9).

### D11 - Replica label `"read"` added to contract values (2026-11-04, A)

`problem_statement.md` lists replica values `primary | failover | regional |
reporting`, but `dataset/evidence/databases/` contains
`customer_data_read_replica_*.sql` (5 snapshots). Adding the label `"read"`
for those tables; omitting them would leave real evidence untagged and
unsearchable. No existing contract value changes meaning.

### D10 - Ordering: plain string ascending for system_id / resource_id (2026-11-04, A)

Evidence check run against `dataset/sample_output.csv`: every (phase,
operation) group in all 32 golden samples is consistent with **both** plain
string sort and natural sort (0 violations for each) - no sample group
contains a pair like `account_9` / `account_10` where the two orders
disagree, so the samples cannot discriminate (111 distinct resource ids, 88
id pairs where the two orders would differ, but never within one group).
Decision: use **plain string ascending**, the literal reading of "ascending
order" in `problem_statement.md`. Risk is limited and will be re-checked if a
discriminating case appears in our custom cases.

### D12 - Resource evidence carries a bounded timeline (2026-11-04, A)

`ResourceState.timeline` is an additive contract field for the sequence of
time-bounded observations and activity claims used to reconstruct the resource
at `audit_at`. Existing fields remain unchanged. The engine excludes records
captured or observed after the case cutoff; activity results remain explicitly
marked as claims and cannot by themselves establish a final record state.

### D13 - Local document extraction dependency and OCR fallback (2026-11-04, A)

PDF text extraction uses pinned `pypdf==6.17.0`. Image and scanned-PDF OCR is
optional and runs through a local Tesseract executable only; no evidence is
sent to a remote service. If Tesseract is unavailable, the parser emits a
plain-language warning and preserves the case for manual review instead of
silently treating unreadable evidence as absent.

## Open questions [CONFIRM]

Carried over from playbook section 16 - answer with evidence, then move them
to Decisions.

- [x] ~~Sorting by `system_id` / `resource_id`: plain string or natural order?~~
      Resolved as D10: samples cannot discriminate; plain string ascending.
- [ ] How is `NOT_APPLICABLE` triggered by `request_text`? (AGENTS.md 6.5
      says non-deletion requests - access, correction, export, opt-out.)
- [x] ~~Timezone handling for naive timestamps.~~ Resolved as D5 (treated as UTC).
- [x] ~~Email hash scheme.~~ Resolved as D6 (SHA-256 of the normalised email).
- [ ] Tie-breaking for equal timestamps when replaying `system_activity`.
- [ ] Which log.txt counts for a two-person, two-machine team?
- [ ] Exact deadline / upload portal / size limits - not configured in the
      official repo; do not invent one (AGENTS.md 3.3).
- [ ] Identity evidence for snapshot-only users - is an empty
      `identity_evidence_ids` acceptable? (D7)
