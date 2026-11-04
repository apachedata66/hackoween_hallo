# Person B Follow-on: Evidence Linkage and Sequence Audit

## Baseline and method

Base: `origin/codex/integration` at `61f8690` when this branch was created.
Dataset: the official participant-facing dataset, supplied at runtime through
`GHOSTDATA_DATASET`. The benchmark read public `sample_output.csv` only after
prediction generation for scoring. No organizer-only files or labels were
used.

Command: `python code/evaluation/run_public_benchmark.py`.

| Metric | Before | After |
| --- | ---: | ---: |
| Public cases predicted | 29/32 | 29/32 |
| Status accuracy | 0.9062 | 0.9062 |
| Step precision | 0.9509 | 0.9748 |
| Step recall | 0.8031 | 0.8031 |
| Step F1 | 0.8708 | 0.8807 |
| Sequence accuracy | 0.2188 | 0.2188 |

The held cases stayed `case_01`, `case_02`, and `case_04`. The precision and
F1 gains came from removing unsupported steps described below. Sequence
accuracy did not change because the remaining sequence differences are not
resolved by the link-only false-positive fix.

## Investigation findings

The audit was performed at each request's `audit_at`; only resources already
reconstructed from participant-visible, cutoff-eligible evidence were treated
as resource observations. Activity IDs may link a subject to a resource, but a
`LINK_RESOURCE_IDENTITY` relationship alone does not prove that the resource
exists or establish its state.

| Case | Current linked evidence at cutoff | Public-sample difference and conclusion |
| --- | --- | --- |
| `case_01` | No identity-linked resources or citable identity-history IDs. Cutoff: 2026-09-03 11:30Z. | Held for review. The public answer asks for an account absence check citing `evidence_54`, but the engine cannot independently link a resource observation to the resolved identity by cutoff. No resource ID is inferred. |
| `case_02` | No identity-linked resources or citable identity-history IDs. Cutoff: 2026-09-04 15:00Z. | Same unresolved account-link gap; no supported resource observation is available for a `COMPLETE` verdict. |
| `case_03` | Account and security records from `evidence_94`, both before the 2026-09-26 11:00Z cutoff. | The expected analytics anonymization check has no identity-linked analytics resource in the reconstructed state. The account and retained security checks are present; the unlinked analytics ID is not added. |
| `case_04` | No identity-linked resources or citable identity-history IDs. Cutoff: 2026-09-07 10:20Z. | Held for review. The public answer names account and analytics checks (`evidence_54`, `evidence_56`), but neither resource is linked to the identity by independent cutoff-eligible evidence. |
| `case_06` | `search_001` from SQL evidence `evidence_57`, captured 2026-09-10 08:45Z, before cutoff 09:15Z. | Search finding, deletion plan, and search verification are supported. The extra expected account verification has no reconstructed account resource or identity-linked resource evidence. |
| `case_07` | `support_001` from `evidence_58`, captured 07:30Z, before cutoff 08:00Z. `activity_4007` is a resource-link claim. | The prior engine promoted the link claim into a present object-storage record, adding unsupported finding, deletion, and verification steps. The fix keeps the link in activity context but does not infer record presence. The extra account verification remains unlinked. |
| `case_08` | `export_001` from JSON evidence `evidence_59`, captured 15:40Z, before cutoff 16:10Z. | Export actions are supported. No account resource was reconstructed to support the additional account verification. |
| `case_09` | Backup `backup_4978` from activity `activity_3709` and SQL `evidence_93`; both precede the 2026-09-16 09:00Z cutoff. | Restore-risk finding and block/verification plan are supported. The extra account-absence and retained-security checks lack linked resources in the current reconstruction. |
| `case_10` | `support_002` from `evidence_61`, before cutoff 2026-09-18 12:25Z; identity history includes `audit_121`, `audit_122`, `audit_238`, `audit_239`. | Support finding/remediation/verification are supported. No account resource is reconstructed for the extra verification. |
| `case_12` | Account, analytics, and security observations from `evidence_01`, before cutoff 2026-09-15 12:00Z; identity history `audit_282` and `audit_283`. | The analytics record contains an email hash and is still attributable. Supplied rule `rule_07` prescribes `ANONYMIZE` for an attributable analytics profile, matching the engine's plan. The public gold expects deletion; no policy-backed reason for changing the engine to delete was found. |
| `case_17` | Account `account_6523` from `evidence_67`; tombstone is linked by activity `activity_4011`; other observations use `evidence_01`. All eligible by cutoff 2026-09-15 12:00Z. | The sequence difference is an additional account-absence verification in the prediction. The linked account evidence supports the planned check; the public gold omits it. No general rule justified dropping a supported future verification. |
| `case_18` | Analytics, flow, search, and support resources from `evidence_94`, before cutoff 2026-09-26 11:00Z; identity history `audit_169`. | The missing account absence and retained-security checks have no corresponding linked account/security resources in the reconstructed inputs. No resource is inferred. |
| `case_20` | Flow and search resources from `evidence_94`, before cutoff 2026-09-26 11:00Z. | The additional account and retained-security checks are not backed by reconstructed resources. |
| `case_21` | Retained security record `audit_record_3737` from `evidence_92`, before cutoff 2026-09-15 12:00Z. | The public gold's account-absence and analytics-anonymization checks have no linked observations in the case input. The engine returns only the supported security verification. |
| `case_22` | Analytics, search, and security records from `evidence_05`, before cutoff 2026-09-21 10:00Z. | The additional account-absence verification has no linked account resource. Existing resource checks remain. |
| `case_23` | Export and search resources from `evidence_92`, before cutoff 2026-09-15 12:00Z. | The expected account-absence and retained-security checks are not present in reconstructed resources. |
| `case_24` | Account and search resources from `evidence_92`, before cutoff 2026-09-15 12:00Z. | The retained-security verification is not linked to a reconstructed security record. |
| `case_25` | Retained security record from `evidence_92`; identity history `audit_220`, before cutoff 2026-09-15 12:00Z. | The expected account-absence and analytics-anonymization checks lack linked records in the engine input. |
| `case_26` | Backup, flow, security, and support resources from `evidence_92`, before cutoff 2026-09-15 12:00Z. | The account-absence and analytics-anonymization checks have no linked resource observations. Existing backup, flow, security, and support steps are retained. |
| `case_27` | Backup, flow, security, and support resources from `evidence_92`, before cutoff 2026-09-15 12:00Z. | Same missing account and analytics links; no additional checks are inferred. |

## Retained behavior change

`reconstruct_resources` no longer promotes a `LINK_RESOURCE_IDENTITY` activity
to a present resource when independent record evidence is absent. The activity
remains available to the timeline. Added a fictional regression test proving a
link-only event yields no resource state. This is supported by the distinction
between relationship evidence and resource-state evidence and is consistent
with the existing cross-file join behavior.

## Remaining limits

The three withheld cases need participant-visible evidence that links a
resource to the resolved identity; case numbering and public expected IDs are
not used to guess those links. Most remaining sequence mismatches are missing
future verification steps for resources that are not reconstructed, plus the
case 12 policy disagreement and case 17 extra supported verification. No
general evidence-backed rule was found to change those safely. Hidden full-set
accuracy is unknown.

## Full 518-request run on this branch

Command:

```powershell
python code/main.py run --input "$env:GHOSTDATA_DATASET\deletion_requests.csv" --out .pytest-tmp/current-full.csv
```

The engine processed all 518 requests but stopped safely without writing a
prediction file because nine cases require manual review:
`case_33`, `case_35`, `case_39`, `case_50`, `case_52`, `case_53`, `case_55`,
`case_61`, and `case_63`. The participant-facing trace shows why these must not
be forced to a verdict:

| Cases | Cutoff finding | Safe disposition |
| --- | --- | --- |
| `case_33`, `case_35`, `case_39`, `case_50`, `case_52`, `case_53`, `case_55` | Each has an identity-linked activity row, but its matching independent record is from `evidence_01` (captured 2026-09-15 11:59:39Z) or `evidence_02` (captured 2026-09-17 12:00:00Z), after that case's `audit_at`. Embedded record times precede capture in some files, but the evidence item itself was captured after the cutoff. | Exclude the observation under the temporal rule; the activity link alone cannot prove the record state. Keep for manual review. |
| `case_61`, `case_63` | Identity-linked activity rows `activity_4007` and `activity_4008` name resources, but the evidence index has no independent record candidate for either resource. | Treat the activity as relationship evidence only; do not infer presence or state. Keep for manual review. |

Thus the current code cannot produce a complete current-run `output.csv` for
all 518 cases. The checked-in `output.csv` is a prior artifact; its structural
validation is separate from recomputing predictions or proving their
accuracy. Full-set gold labels are unavailable, so full-set accuracy cannot be
measured from the supplied files. Do not fill these nine rows with guesses.
