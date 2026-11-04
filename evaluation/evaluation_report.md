# Evaluation Report

## Sample benchmark

Metrics below compare the supplied prediction file with the public gold sample. They do not represent hidden full-dataset accuracy.

```text
Cases: 32 gold, 29 scored, 3 missing, 0 extra
Status accuracy:      0.8438
Step precision:       0.8192
Step recall:          0.7672
Step F1:              0.7923
Sequence accuracy:    0.0625
Field accuracy:
  phase          0.6095
  system_id      0.3286
  resource_id    0.3286
  operation      0.3762
  state          0.4190
  evidence_id    0.6810
Confusion (rows = gold, cols = predicted):
  gold\pred         COMPLETE       INCOMPLETE   NOT_APPLICABLE
  COMPLETE                 6                1                0
  INCOMPLETE               1               21                0
  NOT_APPLICABLE               0                0                0
Failures: 27
  case_03: status INCOMPLETE (gold COMPLETE), steps 4 (gold 3)
    missing: VERIFICATION/account_service/account_7566/VERIFY_RECORD_ABSENT/ABSENT/evidence_94
    missing: VERIFICATION/analytics_platform/analytics_9406/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/evidence_94
    missing: VERIFICATION/security_service/audit_record_2016/VERIFY_RECORD_PRESENT/PRESENT/evidence_94
    extra:   FINDING/account_service/account_7566/REPORT_REMAINING_RECORD/PRESENT/evidence_94
    extra:   REMEDIATION/account_service/account_7566/DELETE_RECORD/ABSENT/
    extra:   VERIFICATION/account_service/account_7566/VERIFY_RECORD_ABSENT/ABSENT/
    extra:   VERIFICATION/security_service/audit_record_2016/VERIFY_RECORD_PRESENT/PRESENT/
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
  case_11: status INCOMPLETE (gold INCOMPLETE), steps 16 (gold 14)
    extra:   FINDING/account_service/account_4248/REPORT_REMAINING_RECORD/PRESENT/evidence_03
    extra:   REMEDIATION/account_service/account_4248/DELETE_RECORD/ABSENT/
  case_12: status INCOMPLETE (gold INCOMPLETE), steps 7 (gold 5)
    missing: FINDING/analytics_platform/analytics_9914/REPORT_REMAINING_RECORD/PRESENT/evidence_01
    missing: REMEDIATION/analytics_platform/analytics_9914/DELETE_RECORD/ABSENT/
    missing: VERIFICATION/analytics_platform/analytics_9914/VERIFY_RECORD_ABSENT/ABSENT/
    extra:   FINDING/account_service/account_9797/REPORT_REMAINING_RECORD/PRESENT/evidence_01
    extra:   FINDING/analytics_platform/analytics_9914/REPORT_EXPOSED_PII/PRESENT/evidence_01
    extra:   REMEDIATION/account_service/account_9797/DELETE_RECORD/ABSENT/
    extra:   REMEDIATION/analytics_platform/analytics_9914/ANONYMIZE_RECORD/ANONYMIZED/
    extra:   VERIFICATION/analytics_platform/analytics_9914/VERIFY_RECORD_ANONYMIZED/ANONYMIZED/
  case_13: status INCOMPLETE (gold INCOMPLETE), steps 10 (gold 8)
    extra:   FINDING/account_service/account_9335/REPORT_REMAINING_RECORD/PRESENT/evidence_03
    extra:   REMEDIATION/account_service/account_9335/DELETE_RECORD/ABSENT/
  case_14: status INCOMPLETE (gold INCOMPLETE), steps 7 (gold 5)
    extra:   FINDING/account_service/account_3677/REPORT_REMAINING_RECORD/PRESENT/evidence_03
    extra:   REMEDIATION/account_service/account_3677/DELETE_RECORD/ABSENT/
  case_15: status INCOMPLETE (gold INCOMPLETE), steps 7 (gold 5)
    extra:   FINDING/account_service/account_4745/REPORT_REMAINING_RECORD/PRESENT/evidence_01
    extra:   REMEDIATION/account_service/account_4745/DELETE_RECORD/ABSENT/
  case_17: status INCOMPLETE (gold INCOMPLETE), steps 11 (gold 5)
    missing: FINDING/backup_service/backup_3245/REPORT_RESTORE_RISK/ACTIVE/evidence_01
    missing: REMEDIATION/backup_service/backup_3245/BLOCK_RESTORE/BLOCKED/
    extra:   FINDING/account_service/account_4092/REPORT_REMAINING_RECORD/PRESENT/evidence_01
    extra:   FINDING/account_service/account_6523/REPORT_REMAINING_RECORD/PRESENT/evidence_67
    extra:   FINDING/identity_service/tombstone_17/REPORT_EXPOSED_PII/PRESENT/activity_4011
    extra:   REMEDIATION/account_service/account_4092/DELETE_RECORD/ABSENT/
    extra:   REMEDIATION/account_service/account_6523/DELETE_RECORD/ABSENT/
    extra:   REMEDIATION/identity_service/tombstone_17/REDACT_RECORD/REDACTED/
    extra:   VERIFICATION/account_service/account_6523/VERIFY_RECORD_ABSENT/ABSENT/
    extra:   VERIFICATION/identity_service/tombstone_17/VERIFY_RECORD_REDACTED/REDACTED/
  case_18: status INCOMPLETE (gold INCOMPLETE), steps 12 (gold 14)
    missing: VERIFICATION/account_service/account_5521/VERIFY_RECORD_ABSENT/ABSENT/
    missing: VERIFICATION/security_service/audit_record_6645/VERIFY_RECORD_PRESENT/PRESENT/
  case_19: status INCOMPLETE (gold INCOMPLETE), steps 10 (gold 8)
    extra:   FINDING/account_service/account_9102/REPORT_REMAINING_RECORD/PRESENT/evidence_01
    extra:   REMEDIATION/account_service/account_9102/DELETE_RECORD/ABSENT/
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
  ... 7 more (raise --show)
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

Three public cases (case_01, case_02, case_04) were not scored because this evidence engine cannot link their requested absent profiles to specific resources without inventing resource IDs. The benchmark therefore reports 29 of 32 public cases scored and 3 missing.

## Improvements made

Fixed trace-local state contamination, explicit non-deletion classification, service-to-policy category mapping, and lexical output sorting. Custom scenarios are also reported separately; full hidden-set accuracy remains unavailable.

## Run metadata

- Prediction file: `C:\Users\Asus\AppData\Local\Packages\sandbox.{a62baadd-8aba-428a-b505-27d0559f5455}\AC\Temp\ghostdata-reviewable-samples-output.csv`
- Gold file: `dataset\sample_output.csv`
- Full-dataset accuracy: not measured here; the challenge does not provide full-dataset gold labels.
