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

## Full 518-request run and screenshot evidence

The 2026-11-05T00:52Z run processed all 518 requests and safely withheld its
output because local OCR was unavailable for image evidence. It identified
nine cases for review: `case_33`, `case_35`, `case_39`, `case_50`, `case_52`,
`case_53`, `case_55`, `case_61`, and `case_63`. A manual visual inspection of
the participant-facing screenshots found cutoff-eligible state evidence that
the text-only run had not extracted:

| Cases | Source image | Visible state evidence | Cutoff |
| --- | --- | --- | --- |
| `case_33`, `case_52` | `evidence_23` | Export `export_1260` and its owner are visible in the export console. | 2026-06-18T12:00Z capture; both cutoffs are later. |
| `case_35` | `evidence_09` | Search entry `search_428` and its identifying fields are visible. | 2026-09-01T06:00Z capture; cutoff is later. |
| `case_39` | `evidence_14` | Connector `data_flow_1121` is selected; the console shows continuous sync and recent delivery activity. | 2026-08-07T08:00Z capture; cutoff is later. |
| `case_50` | `evidence_19` | Analytics profile `analytics_7438` and its identifying fields are visible. | 2026-07-13T10:00Z capture; cutoff is later. |
| `case_53` | `evidence_28` | Support conversation `support_1034`, customer identifiers, and shared order context are visible. | 2026-05-24T07:00Z capture; cutoff is later. |
| `case_55` | `evidence_32` | Archive `backup_9287` is visible in the recovery console. | 2026-04-29T09:00Z capture; cutoff is later. |
| `case_61` | `evidence_46` | Object storage shows `delivery_confirmation_19.pdf`; pre-cutoff `activity_4007` links that filename and `object_19` to the subject. | 2026-02-13T08:00Z capture and 08:07Z link; cutoff is 2026-02-14T10:00Z. |
| `case_63` | `evidence_60` | Marketing profile `marketing_001` and its identifying fields are visible. | 2026-09-16T07:20Z capture; cutoff is later. |

The seven direct-ID screenshots (eight cases because `evidence_23` applies to
two cases) independently show resource state and identity. For `case_61`, the
screenshot proves the file is present in object storage; the time-bounded link
event supplies the relationship between its filename, resource ID, and
subject. The new generic filename-alias join uses that relationship only when
an independent same-system file listing contains the alias by the cutoff.
`LINK_RESOURCE_IDENTITY` alone still never creates a resource observation.

The later SQL snapshots `evidence_01` and `evidence_02` remain excluded for
these earlier cutoffs. They are not needed to establish the screenshot states.
The current machine has no Tesseract executable, so the new image records and
flow state parser could not yet be exercised against the real screenshots.
Install/configure local Tesseract, rerun the full dataset, review every result,
and validate the exact 518-row file before submission. The checked-in
`output.csv` is from the earlier 2026-11-04 run and predates the link-only
safety fix; it is stale and must not be submitted. Full-set gold labels are
unavailable, so full-set accuracy cannot be measured from supplied files.
