# Evaluation Report

## Sample benchmark

Metrics below compare the supplied prediction file with the public gold sample. They do not represent hidden full-dataset accuracy.

```text
Cases: 32 gold, 29 scored, 3 missing, 0 extra
Status accuracy:      0.8750
Step precision:       0.9245
Step recall:          0.7778
Step F1:              0.8448
Sequence accuracy:    0.2188
Field accuracy:
  phase          0.7824
  system_id      0.5596
  resource_id    0.5596
  operation      0.5959
  state          0.6166
  evidence_id    0.7824
Confusion (rows = gold, cols = predicted):
  gold\pred         COMPLETE       INCOMPLETE   NOT_APPLICABLE
  COMPLETE                 7                0                0
  INCOMPLETE               1               21                0
  NOT_APPLICABLE               0                0                0
Failures: 22
  case_03: status COMPLETE (gold COMPLETE), steps 2 (gold 3)
    missing: VERIFICATION/analytics_platform/analytics_9406/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/evidence_94
  case_06: status INCOMPLETE (gold INCOMPLETE), steps 3 (gold 4)
    missing: VERIFICATION/account_service/account_006/VERIFY_RECORD_ABSENT/ABSENT/
  case_07: status INCOMPLETE (gold INCOMPLETE), steps 6 (gold 4)
    missing: VERIFICATION/account_service/account_007/VERIFY_RECORD_ABSENT/ABSENT/
    extra:   FINDING/object_storage/object_19/REPORT_REMAINING_RECORD/PRESENT/activity_4007
    extra:   REMEDIATION/object_storage/object_19/DELETE_RECORD/ABSENT/
    extra:   VERIFICATION/object_storage/object_19/VERIFY_RECORD_ABSENT/ABSENT/
  case_08: status INCOMPLETE (gold INCOMPLETE), steps 3 (gold 4)
    missing: VERIFICATION/account_service/account_008/VERIFY_RECORD_ABSENT/ABSENT/
  case_09: status INCOMPLETE (gold INCOMPLETE), steps 3 (gold 5)
    missing: FINDING/backup_service/backup_4978/REPORT_RESTORE_RISK/ACTIVE/evidence_93
    missing: VERIFICATION/account_service/account_3960/VERIFY_RECORD_ABSENT/ABSENT/
    missing: VERIFICATION/security_service/audit_record_4902/VERIFY_RECORD_PRESENT/PRESENT/
    extra:   FINDING/backup_service/backup_4978/REPORT_RESTORE_RISK/ACTIVE/activity_3709
  case_10: status INCOMPLETE (gold INCOMPLETE), steps 3 (gold 4)
    missing: VERIFICATION/account_service/account_010/VERIFY_RECORD_ABSENT/ABSENT/
  case_12: status INCOMPLETE (gold INCOMPLETE), steps 5 (gold 5)
    missing: FINDING/analytics_platform/analytics_9914/REPORT_REMAINING_RECORD/PRESENT/evidence_01
    missing: REMEDIATION/analytics_platform/analytics_9914/DELETE_RECORD/ABSENT/
    missing: VERIFICATION/analytics_platform/analytics_9914/VERIFY_RECORD_ABSENT/ABSENT/
    extra:   FINDING/analytics_platform/analytics_9914/REPORT_EXPOSED_PII/PRESENT/evidence_01
    extra:   REMEDIATION/analytics_platform/analytics_9914/ANONYMIZE_RECORD/ANONYMIZED/
    extra:   VERIFICATION/analytics_platform/analytics_9914/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/
  case_17: status INCOMPLETE (gold INCOMPLETE), steps 7 (gold 5)
    missing: FINDING/backup_service/backup_3245/REPORT_RESTORE_RISK/ACTIVE/evidence_01
    missing: REMEDIATION/backup_service/backup_3245/BLOCK_RESTORE/BLOCKED/
    extra:   FINDING/identity_service/tombstone_17/REPORT_EXPOSED_PII/PRESENT/activity_4011
    extra:   REMEDIATION/identity_service/tombstone_17/REDACT_RECORD/REDACTED/
    extra:   VERIFICATION/account_service/account_6523/VERIFY_RECORD_ABSENT/ABSENT/
    extra:   VERIFICATION/identity_service/tombstone_17/VERIFY_RECORD_REDACTED/REDACTED/
  case_18: status INCOMPLETE (gold INCOMPLETE), steps 12 (gold 14)
    missing: VERIFICATION/account_service/account_5521/VERIFY_RECORD_ABSENT/ABSENT/
    missing: VERIFICATION/security_service/audit_record_6645/VERIFY_RECORD_PRESENT/PRESENT/
  case_20: status INCOMPLETE (gold INCOMPLETE), steps 6 (gold 8)
    missing: VERIFICATION/account_service/account_5037/VERIFY_RECORD_ABSENT/ABSENT/
    missing: VERIFICATION/security_service/audit_record_5569/VERIFY_RECORD_PRESENT/PRESENT/
  case_21: status COMPLETE (gold COMPLETE), steps 1 (gold 3)
    missing: VERIFICATION/account_service/account_6440/VERIFY_RECORD_ABSENT/ABSENT/evidence_92
    missing: VERIFICATION/analytics_platform/analytics_5335/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/evidence_92
  case_22: status INCOMPLETE (gold INCOMPLETE), steps 7 (gold 8)
    missing: VERIFICATION/account_service/account_4990/VERIFY_RECORD_ABSENT/ABSENT/
  case_23: status INCOMPLETE (gold INCOMPLETE), steps 6 (gold 8)
    missing: VERIFICATION/account_service/account_410/VERIFY_RECORD_ABSENT/ABSENT/
    missing: VERIFICATION/security_service/audit_record_4128/VERIFY_RECORD_PRESENT/PRESENT/
  case_24: status INCOMPLETE (gold INCOMPLETE), steps 6 (gold 7)
    missing: VERIFICATION/security_service/audit_record_7095/VERIFY_RECORD_PRESENT/PRESENT/
  case_25: status COMPLETE (gold COMPLETE), steps 1 (gold 3)
    missing: VERIFICATION/account_service/account_3136/VERIFY_RECORD_ABSENT/ABSENT/evidence_92
    missing: VERIFICATION/analytics_platform/analytics_1895/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/evidence_92
  case_26: status COMPLETE (gold COMPLETE), steps 4 (gold 6)
    missing: VERIFICATION/account_service/account_5684/VERIFY_RECORD_ABSENT/ABSENT/evidence_92
    missing: VERIFICATION/analytics_platform/analytics_4566/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/evidence_92
  case_27: status COMPLETE (gold COMPLETE), steps 4 (gold 6)
    missing: VERIFICATION/account_service/account_3866/VERIFY_RECORD_ABSENT/ABSENT/evidence_92
    missing: VERIFICATION/analytics_platform/analytics_4574/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/evidence_92
  case_28: status COMPLETE (gold COMPLETE), steps 4 (gold 6)
    missing: VERIFICATION/account_service/account_5482/VERIFY_RECORD_ABSENT/ABSENT/evidence_92
    missing: VERIFICATION/analytics_platform/analytics_6077/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/evidence_92
  case_29: status INCOMPLETE (gold INCOMPLETE), steps 12 (gold 14)
    missing: VERIFICATION/account_service/account_7012/VERIFY_RECORD_ABSENT/ABSENT/
    missing: VERIFICATION/security_service/audit_record_3954/VERIFY_RECORD_PRESENT/PRESENT/
  case_30: status INCOMPLETE (gold INCOMPLETE), steps 12 (gold 14)
    missing: VERIFICATION/account_service/account_4163/VERIFY_RECORD_ABSENT/ABSENT/
    missing: VERIFICATION/security_service/audit_record_1707/VERIFY_RECORD_PRESENT/PRESENT/
  ... 2 more (raise --show)
```

## Custom evaluation cases

Ran 16 hand-built cases; 16 passed.

| Case | Scenario | Result | Details |
| --- | --- | --- | --- |
| custom_01 | access request is NOT_APPLICABLE | PASS | Expected status and steps matched; output validated. |
| custom_02 | reported COMPLETE but profile remains | PASS | Expected status and steps matched; output validated. |
| custom_03 | truly COMPLETE with four evidence-backed checks | PASS | Expected status and steps matched; output validated. |
| custom_04 | replica-only leftover in search index | PASS | Expected status and steps matched; output validated. |
| custom_05 | active sync flow can recreate data | PASS | Expected status and steps matched; output validated. |
| custom_06 | tombstone still exposes email hash | PASS | Expected status and steps matched; output validated. |
| custom_07 | correctly redacted tombstone is COMPLETE | PASS | Expected status and steps matched; output validated. |
| custom_08 | must-retain record present is COMPLETE | PASS | Expected status and steps matched; output validated. |
| custom_09 | must-retain record missing flags review (contract gap) | PASS | Expected status and steps matched; output validated. |
| custom_10 | unblocked restore path is a finding | PASS | Expected status and steps matched; output validated. |
| custom_11 | restore already blocked is COMPLETE | PASS | Expected status and steps matched; output validated. |
| custom_12 | marketing opt-out is NOT_APPLICABLE | PASS | Expected status and steps matched; output validated. |
| custom_13 | unclear request still audits with a warning | PASS | Expected status and steps matched; output validated. |
| custom_14 | unknown category warns instead of guessing | PASS | Expected status and steps matched; output validated. |
| custom_15 | Spanish request authorizes deletion | PASS | Expected status and steps matched; output validated. |
| custom_16 | French request authorizes deletion | PASS | Expected status and steps matched; output validated. |

## Failures found

Three public absence-only cases (case_01, case_02, case_04) remain unscored because the linked evidence does not identify the missing resource IDs. The benchmark reports 29 of 32 public cases scored and 3 missing.

## Improvements made

Fixed trace-local state contamination, explicit non-deletion classification, search/marketing category mapping, lexical output sorting, and NOT_FOUND normalization. Full hidden-set accuracy remains unavailable.

## Run metadata

- Prediction file: `ghostdata-reviewable-samples-output.csv`
- Gold file: `dataset/sample_output.csv`
- Full-dataset accuracy: not measured here; the challenge does not provide full-dataset gold labels.
