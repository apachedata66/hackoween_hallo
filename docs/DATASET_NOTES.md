# DATASET_NOTES - first pass (task A1, 2026-11-04, A)

Profile of every participant-facing file so both teammates can answer "what is
in each file" without opening it. Source: `dataset/` copied from the official
repo (see docs/DECISIONS.md D1). Row counts verified by script.

## CSV files

| File | Rows | Columns |
|---|---|---|
| `deletion_requests.csv` | **518** | case_id, email, requested_at, reported_status, reported_at, audit_at, request_text |
| `sample_deletion_requests.csv` | 32 | same as above |
| `sample_output.csv` | 32 | case_id, deletion_status, steps_json (golden answers for the samples only) |
| `user_identities.csv` | 850 | user_id, name, email, phone, email_hash, updated_at |
| `user_audit_log.csv` | 306 | audit_id, user_id, event_time, field_name, old_value, new_value |
| `system_activity.csv` | 4011 | activity_id, event_time, event_type, source_system, target_system, resource_id, reported_result, details |
| `deletion_rules.csv` | 15 | rule_id, data_category, condition, required_action |
| `evidence_files.csv` | 94 | file_id, file_path, origin, captured_at |
| `output.csv` | 0 (blank template) | case_id, deletion_status, steps_json |

### deletion_requests.csv (the 518 cases)

- Timestamps are ISO-8601 with `Z` (UTC). `requested_at` range
  2026-01-05 -> 2026-09-24; `audit_at` range 2026-01-29 -> 2026-10-01.
- `reported_status` distribution: COMPLETE 254, PARTIALLY_COMPLETE 152,
  NOT_STARTED 112. **These are claims, never proof.**
- **517 distinct emails across 518 rows** - one email is used by two cases
  (edge case: reuse / second person). Must be handled by the identity
  resolver, not by assuming 1 email = 1 case.
- Input rows are **not sorted by case_id**; output must be sorted.
- `request_text` may be non-deletion (access, correction, export, opt-out) ->
  `NOT_APPLICABLE` (AGENTS.md 6.5).

### user_identities.csv (current snapshot)

- `email_hash` is 64 hex chars (SHA-256 shaped). Scheme still to be
  reverse-engineered from known email/hash pairs [CONFIRM].
- One row per `user_id`; a person may own several user_ids (duplicate
  accounts).

### user_audit_log.csv (historical identity changes)

- Only three fields are ever changed: `email` (107), `email_hash` (107),
  `phone` (92). Walk `old_value -> new_value` chains in `event_time` order to
  recover historical identifiers.
- `audit_id` values here double as citable evidence ids.

### system_activity.csv (global event stream)

- Event types: DELETE_RECORD 890, UPDATE_RECORD 672, SYNC_RECORD 447,
  INDEX_RECORD 400, SEND_EMAIL 368, REFRESH_CACHE 284, RETAIN_RECORD 206,
  ANONYMIZE_RECORD 204, REDACT_RECORD 173, CREATE_EXPORT 155,
  CHECK_DATA_FLOW 89, DISABLE_DATA_FLOW 36, BLOCK_RESTORE 36,
  CHECK_RESTORE_ACCESS 28, LINK_RESOURCE_IDENTITY 12, CLASSIFY_REQUEST 10,
  RESTORE_BACKUP 1.
- Source systems: deletion_worker 1466, account_service 1100,
  profile_service 440, notification_service 368, security_service 196,
  export_service 155, support_platform 232, integration_service 31,
  privacy_intake 10, data_catalog 12, backup_service 1.
- `reported_result`: SUCCESS 2914, FAILED 721, PARTIAL 376 - all claims;
  cross-check against snapshots.
- Rows may describe unrelated people (decoys); tie resources to user_id,
  never to email alone.

### deletion_rules.csv (policy, 15 rules)

| data_category | required_action | condition (short) |
|---|---|---|
| USER_PROFILE | DELETE | Always |
| SECONDARY_IDENTIFIER | DELETE | Always |
| SEARCH_INDEX_ENTRY | DELETE | Always |
| CACHE_ENTRY | DELETE | Always |
| SUPPORT_MESSAGE | REDACT | conversation context must be retained |
| SUPPORT_ATTACHMENT | DELETE | attachment belongs only to the subject |
| ANALYTICS_PROFILE | ANONYMIZE | still attributable to a user |
| PRODUCT_TELEMETRY | ANONYMIZE | still attributable to a user |
| USER_EXPORT | DELETE | Always |
| MARKETING_PROFILE | DELETE | Always |
| EMAIL_DELIVERY_LOG | REDACT | log contains a user email address |
| SECURITY_AUDIT_LOG | RETAIN | within supplied retention period |
| LEGAL_HOLD_RECORD | RETAIN | supplied legal hold active |
| BACKUP_ARCHIVE | RETAIN | restore access can be blocked |
| ACCOUNT_TOMBSTONE | REDACT | keep stable internal user_id only |

Tombstone rule: keep `user_id`, strip name, email, phone, email hash.

### evidence_files.csv (manifest, 94 files)

`file_id, file_path, origin, captured_at` - the manifest does **not** say which
case/user a file belongs to; link through contents (AGENTS.md 6.6). Evidence
capture times cluster around 2026-09-15..2026-09-17; anything captured after a
case's `audit_at` must not be cited for that case.

| Folder | Count | Format |
|---|---|---|
| `evidence/databases/` | 24 | `.sql` (SQLite-compatible, readable as text) |
| `evidence/documents/` | 4 | `.pdf` |
| `evidence/images/` | 11 | `.png` (screenshots - may need OCR) |
| `evidence/logs/` | 26 | `.log` |
| `evidence/records/` | 28 | `.json` + 1 `.txt` |

## Evidence deep-dive (A4/A5 profiling)

### `evidence/databases/*.sql` (24 files, loaded by `loaders/sql_snapshots.py`)

- SQLite scripts, often with header comments: `-- Captured at: <ISO>` and
  `-- Database topology: failover_replica`.
- Two families:
  - **Point-in-time replica comparisons** (`*_primary` + `*_failover_replica`
    / `*_read_replica` / `*_reporting_replica` / `*_replica_ap_south` tables in
    one file) - the classic drift proof: the same `resource_id` present in a
    replica but gone from primary.
  - **Inventory snapshots** (`customer_data_inventory_YYYYMMDD.sql`, 11 dated
    files) with `snapshot_scope(origin_system, captured_at)` plus one table per
    system: `customer_profiles`, `customer_search_documents`,
    `customer_analytics_profiles`, `support_records`, `customer_exports`,
    `connector_subscriptions`, `backup_restore_entries`,
    `security_audit_records`.
- Generic `customer_data_*` tables carry `record_json` (full record as JSON
  text) - identifier search must match on word boundaries (`user_01` must not
  match `user_010`).
- Repro on real data: 24 snapshots / 969 rows / 0 warnings;
  `leila.haddad@yahoo.com` found only in the **failover** replica
  (`evidence_54`) while absent from every inventory - live drift example.

### `evidence/logs/*.log` (26 files, parsed by `loaders/logs.py`)

Five formats in the wild (all start with an ISO timestamp):

1. `ts [LEVEL] [service] [trace] event: k="v" k="v"` (application traces)
2. RFC5424 syslog: `ts <15>1 host app trace - - level=... event="..." ...`
3. `ts requestId=... level=... function=... message="nested k=\"v\" pairs"`
   (cloud runtime export - the `message` value re-parses as kv pairs)
4. `ts LEVEL service=... event=... k=v` (operations streams)
5. bare `ts LEVEL tenant=... event=... k=v` (support replica)

`LINK_RESOURCE_IDENTITY` events link `resource_id` <-> email <-> `user_id`
and carry a citable `activity_id`.

### `evidence/records/*.json` (28 files, normalized by `loaders/records.py`)

- Top level object; the payload is either `records[]` directly or nested
  `snapshots[].records[]` (each snapshot has `captured_at`, `data_store`,
  `collection`).
- Record fields seen: `recorded_at`, `system`, `resource_id`, `record_type`,
  `result`, `subject_reference`; analytics-style records instead carry
  `user_id`, `email`, `phone`, `email_hash` inline.
- Malformed JSON must become a warning, never a crash (A14).

## Known edge cases to plan for (from this profile)

1. One email shared by two cases - never attach another person's records.
2. `case_id` unsorted in input, sorted required in output.
3. Naive/`Z` timestamp mix to be confirmed per file during A2 loader work.
4. `email_hash` scheme unknown until reverse-engineered (A3).
5. Evidence captured after `audit_at` must be excluded per case.

*This is a first pass. Full A1 deliverable: column types, nulls, duplicates,
date-format checks per file, per-replica SQL table listing.*
