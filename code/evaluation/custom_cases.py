"""Hand-built evaluation cases (task B8).

Each case is a tiny, synthetic fixture with an expected output that follows
directly from the official contract (problem_statement.md / AGENTS.md §6).
Nothing here is derived from the hidden answers: fixtures are invented, and
expectations encode the rules, not any dataset row.

Run:
  python code/evaluation/custom_cases.py           # print pass/fail table
  python -m unittest tests.test_custom_cases       # via the test suite

Coverage (16 cases >= the 10 the playbook asks for):
  NOT_APPLICABLE (access ask, marketing opt-out),
  reported COMPLETE but actually INCOMPLETE,
  truly COMPLETE with evidence (retained record + blocked backup + idle flow),
  replica-only leftover, active sync flow recreating data,
  tombstone with leftover email hash, correctly redacted tombstone,
  must-retain present, must-retain missing (known contract gap),
  restore risk unblocked, restore already blocked,
  unclear request text still audits, unknown category refuses to guess,
  Spanish and French deletion requests.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))

from ghostdata.contract.csv_io import steps_to_json  # noqa: E402
from ghostdata.contract.models import CaseAuditInput, DeletionStatus, ResolvedIdentity, ResourceState  # noqa: E402
from ghostdata.paths import dataset_dir  # noqa: E402
from ghostdata.planner.plan import plan_case  # noqa: E402
from ghostdata.policy.rules import load_rulebook  # noqa: E402
from ghostdata.validate import load_known_ids, validate_rows  # noqa: E402

# (phase, system_id, resource_id, operation, state, evidence_id)
ExpectedStep = tuple[str, str, str, str, str, str]


def _resource(
    system_id: str,
    resource_id: str,
    *,
    category: str,
    exists: bool = True,
    identifiers: tuple[str, ...] = (),
    kind: str = "record",
    active: bool = False,
    restore: bool = False,
    replica: str | None = None,
    evidence: str = "",
    notes: str = "",
) -> ResourceState:
    return ResourceState(
        system_id=system_id,
        resource_id=resource_id,
        kind=kind,
        data_category=category,
        exists_at_audit=exists,
        identifiers_present=list(identifiers),
        is_active_flow=active,
        can_restore_user_data=restore,
        replica=replica,
        evidence_id=evidence,
        notes=notes,
    )


def _identity(case_id: str, email: str) -> ResolvedIdentity:
    return ResolvedIdentity(
        case_id=case_id,
        user_ids=["user_01"],
        emails_current=[email],
        emails_historical=[],
        email_hashes=[],
    )


def _request(case_id: str, email: str, text: str, reported: str = "COMPLETE") -> dict:
    return {
        "case_id": case_id,
        "email": email,
        "requested_at": "2026-08-01T09:00:00Z",
        "reported_status": reported,
        "reported_at": "2026-08-02T09:00:00Z",
        "audit_at": "2026-08-15T09:00:00Z",
        "request_text": text,
    }


@dataclass(frozen=True)
class CustomCase:
    case_id: str
    title: str
    input: CaseAuditInput
    expected_status: str
    expected_steps: tuple[ExpectedStep, ...] = ()
    expect_review: bool = False
    expect_warning_contains: str = ""


def _case(
    case_id: str,
    title: str,
    text: str,
    resources: list[ResourceState],
    expected_status: str,
    expected_steps: list[ExpectedStep] | tuple[ExpectedStep, ...] = (),
    reported: str = "COMPLETE",
    expect_review: bool = False,
    expect_warning_contains: str = "",
    email: str = "subject@example.com",
) -> CustomCase:
    return CustomCase(
        case_id=case_id,
        title=title,
        input=CaseAuditInput(
            request=_request(case_id, email, text, reported),
            identity=_identity(case_id, email),
            resources=resources,
        ),
        expected_status=expected_status,
        expected_steps=tuple(expected_steps),
        expect_review=expect_review,
        expect_warning_contains=expect_warning_contains,
    )


def build_cases() -> list[CustomCase]:
    """All fixtures. Expected steps follow the official ordering rules."""

    cases: list[CustomCase] = []

    # 1. A data-access ask is not a deletion request.
    cases.append(_case(
        "custom_01",
        "access request is NOT_APPLICABLE",
        "I would like a copy of my data.",
        [],
        "NOT_APPLICABLE",
    ))

    # 2. Dashboard said COMPLETE; the profile is still there.
    cases.append(_case(
        "custom_02",
        "reported COMPLETE but profile remains",
        "I deleted this account and received a confirmation, but please check it again.",
        [_resource(
            "account_service", "account_005",
            category="USER_PROFILE",
            identifiers=("name", "email", "phone", "email_hash"),
            evidence="evidence_54",
        )],
        "INCOMPLETE",
        [
            ("FINDING", "account_service", "account_005", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_54"),
            ("REMEDIATION", "account_service", "account_005", "DELETE_RECORD", "ABSENT", ""),
            ("VERIFICATION", "account_service", "account_005", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
        ],
        reported="COMPLETE",
    ))

    # 3. Truly complete: profile gone, audit retained, backup blocked, flow idle.
    cases.append(_case(
        "custom_03",
        "truly COMPLETE with four evidence-backed checks",
        "Please close my account and erase my personal data.",
        [
            _resource("account_service", "account_001", category="USER_PROFILE",
                      exists=False, evidence="evidence_54"),
            _resource("security_service", "audit_record_001", category="SECURITY_AUDIT_LOG",
                      identifiers=("user_id",), evidence="evidence_93"),
            _resource("sync_service", "sync_001", category="SYNC_FLOW",
                      kind="flow", active=False, evidence="evidence_02"),
            _resource("backup_service", "backup_001", category="BACKUP_ARCHIVE",
                      kind="backup", restore=False, evidence="evidence_01"),
        ],
        "COMPLETE",
        [
            ("VERIFICATION", "account_service", "account_001", "VERIFY_RECORD_ABSENT", "ABSENT", "evidence_54"),
            ("VERIFICATION", "security_service", "audit_record_001", "VERIFY_RECORD_PRESENT", "PRESENT", "evidence_93"),
            ("VERIFICATION", "sync_service", "sync_001", "VERIFY_DATA_FLOW_DISABLED", "DISABLED", "evidence_02"),
            ("VERIFICATION", "backup_service", "backup_001", "VERIFY_RESTORE_BLOCKED", "BLOCKED", "evidence_01"),
        ],
    ))

    # 4. Leftover only in a failover replica of the search index.
    cases.append(_case(
        "custom_04",
        "replica-only leftover in search index",
        "Please erase my data everywhere, including any copies.",
        [_resource(
            "search_service", "search_1308",
            category="SEARCH_INDEX_ENTRY",
            replica="failover",
            evidence="evidence_03",
        )],
        "INCOMPLETE",
        [
            ("FINDING", "search_service", "search_1308", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_03"),
            ("REMEDIATION", "search_service", "search_1308", "DELETE_RECORD", "ABSENT", ""),
            ("VERIFICATION", "search_service", "search_1308", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
        ],
    ))

    # 5. An active sync job can recreate deleted data.
    cases.append(_case(
        "custom_05",
        "active sync flow can recreate data",
        "Remove my account and stop any job from bringing it back.",
        [_resource(
            "sync_service", "sync_job_12",
            category="SYNC_FLOW",
            kind="flow",
            active=True,
            evidence="evidence_01",
        )],
        "INCOMPLETE",
        [
            ("FINDING", "sync_service", "sync_job_12", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE", "evidence_01"),
            ("REMEDIATION", "sync_service", "sync_job_12", "DISABLE_DATA_FLOW", "DISABLED", ""),
            ("VERIFICATION", "sync_service", "sync_job_12", "VERIFY_DATA_FLOW_DISABLED", "DISABLED", ""),
        ],
    ))

    # 6. Tombstone kept, but an email hash still identifies the person.
    cases.append(_case(
        "custom_06",
        "tombstone still exposes email hash",
        "Delete my account but keep whatever internal id you need.",
        [_resource(
            "account_service", "tombstone_007",
            category="ACCOUNT_TOMBSTONE",
            kind="tombstone",
            identifiers=("user_id", "email_hash"),
            evidence="evidence_02",
        )],
        "INCOMPLETE",
        [
            ("FINDING", "account_service", "tombstone_007", "REPORT_EXPOSED_PII", "PRESENT", "evidence_02"),
            ("REMEDIATION", "account_service", "tombstone_007", "REDACT_RECORD", "REDACTED", ""),
            ("VERIFICATION", "account_service", "tombstone_007", "VERIFY_RECORD_REDACTED", "REDACTED", ""),
        ],
    ))

    # 7. Tombstone holds only the permitted stable reference.
    cases.append(_case(
        "custom_07",
        "correctly redacted tombstone is COMPLETE",
        "Close my account permanently.",
        [_resource(
            "account_service", "tombstone_008",
            category="ACCOUNT_TOMBSTONE",
            kind="tombstone",
            identifiers=("user_id",),
            evidence="evidence_04",
        )],
        "COMPLETE",
        [
            ("VERIFICATION", "account_service", "tombstone_008", "VERIFY_RECORD_REDACTED", "REDACTED", "evidence_04"),
        ],
    ))

    # 8. A record policy requires us to keep is still available.
    cases.append(_case(
        "custom_08",
        "must-retain record present is COMPLETE",
        "Please delete my account; I understand audit records are kept.",
        [_resource(
            "security_service", "audit_record_4816",
            category="SECURITY_AUDIT_LOG",
            identifiers=("user_id",),
            evidence="evidence_05",
        )],
        "COMPLETE",
        [
            ("VERIFICATION", "security_service", "audit_record_4816", "VERIFY_RECORD_PRESENT", "PRESENT", "evidence_05"),
        ],
    ))

    # 9. KNOWN CONTRACT GAP: a required record is missing, but the output
    # contract has no finding operation for an absent-when-required record.
    # Expected: flagged for review rather than a silently invalid row.
    cases.append(_case(
        "custom_09",
        "must-retain record missing flags review (contract gap)",
        "Please delete my account.",
        [_resource(
            "security_service", "audit_record_4817",
            category="SECURITY_AUDIT_LOG",
            exists=False,
            evidence="evidence_05",
        )],
        "INCOMPLETE",
        [],
        expect_review=True,
        expect_warning_contains="required record is missing",
    ))

    # 10. A backup that can still restore the person's data.
    cases.append(_case(
        "custom_10",
        "unblocked restore path is a finding",
        "Delete my data and make sure backups cannot bring it back.",
        [_resource(
            "backup_service", "backup_4978",
            category="BACKUP_ARCHIVE",
            kind="backup",
            restore=True,
            evidence="evidence_93",
        )],
        "INCOMPLETE",
        [
            ("FINDING", "backup_service", "backup_4978", "REPORT_RESTORE_RISK", "ACTIVE", "evidence_93"),
            ("REMEDIATION", "backup_service", "backup_4978", "BLOCK_RESTORE", "BLOCKED", ""),
            ("VERIFICATION", "backup_service", "backup_4978", "VERIFY_RESTORE_BLOCKED", "BLOCKED", ""),
        ],
    ))

    # 11. The same backup after restore was already blocked.
    cases.append(_case(
        "custom_11",
        "restore already blocked is COMPLETE",
        "Erase my account; backups are already locked down.",
        [_resource(
            "backup_service", "backup_4977",
            category="BACKUP_ARCHIVE",
            kind="backup",
            restore=False,
            evidence="evidence_01",
        )],
        "COMPLETE",
        [
            ("VERIFICATION", "backup_service", "backup_4977", "VERIFY_RESTORE_BLOCKED", "BLOCKED", "evidence_01"),
        ],
    ))

    # 12. Marketing opt-out is not a deletion.
    cases.append(_case(
        "custom_12",
        "marketing opt-out is NOT_APPLICABLE",
        "Please unsubscribe me from your marketing emails.",
        [],
        "NOT_APPLICABLE",
    ))

    # 13. Vague text: audit anyway (a missed deletion is worse than a flag).
    cases.append(_case(
        "custom_13",
        "unclear request still audits with a warning",
        "Please look into my account situation.",
        [_resource(
            "account_service", "account_009",
            category="USER_PROFILE",
            identifiers=("email",),
            evidence="evidence_54",
        )],
        "INCOMPLETE",
        [
            ("FINDING", "account_service", "account_009", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_54"),
            ("REMEDIATION", "account_service", "account_009", "DELETE_RECORD", "ABSENT", ""),
            ("VERIFICATION", "account_service", "account_009", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
        ],
        expect_warning_contains="does not clearly authorize deletion",
    ))

    # 14. Category absent from deletion_rules.csv: warn, never guess.
    cases.append(_case(
        "custom_14",
        "unknown category warns instead of guessing",
        "Please remove my profile and everything tied to it.",
        [
            _resource("search_service", "search_2201", category="SEARCH_INDEX_ENTRY",
                      evidence="evidence_03"),
            _resource("legacy_service", "legacy_77", category="LEGACY_WIDGET",
                      identifiers=("email",), evidence="evidence_03"),
        ],
        "INCOMPLETE",
        [
            ("FINDING", "search_service", "search_2201", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_03"),
            ("REMEDIATION", "search_service", "search_2201", "DELETE_RECORD", "ABSENT", ""),
            ("VERIFICATION", "search_service", "search_2201", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
        ],
        expect_warning_contains="no deletion rule for category LEGACY_WIDGET",
    ))

    # 15. Spanish deletion request still authorizes deletion.
    cases.append(_case(
        "custom_15",
        "Spanish request authorizes deletion",
        "Por favor, eliminen mi cuenta y todos mis datos personales.",
        [_resource(
            "account_service", "account_021",
            category="USER_PROFILE",
            identifiers=("email",),
            evidence="evidence_54",
        )],
        "INCOMPLETE",
        [
            ("FINDING", "account_service", "account_021", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_54"),
            ("REMEDIATION", "account_service", "account_021", "DELETE_RECORD", "ABSENT", ""),
            ("VERIFICATION", "account_service", "account_021", "VERIFY_RECORD_ABSENT", "ABSENT", ""),
        ],
    ))

    # 16. French deletion request authorizes deletion too.
    cases.append(_case(
        "custom_16",
        "French request authorizes deletion",
        "Je demande la suppression définitive du compte associé à cette adresse.",
        [_resource(
            "account_service", "tombstone_031",
            category="ACCOUNT_TOMBSTONE",
            kind="tombstone",
            identifiers=("user_id",),
            evidence="evidence_04",
        )],
        "COMPLETE",
        [
            ("VERIFICATION", "account_service", "tombstone_031", "VERIFY_RECORD_REDACTED", "REDACTED", "evidence_04"),
        ],
    ))

    return cases


def _actual_steps(result) -> tuple[ExpectedStep, ...]:
    return tuple(
        (
            step.phase.value,
            step.system_id,
            step.resource_id,
            step.operation.value,
            step.state.value,
            step.evidence_id,
        )
        for step in result.steps
    )


def run_cases() -> list[dict]:
    """Run every fixture through the real planner. Returns per-case records."""

    rulebook = load_rulebook(dataset_dir() / "deletion_rules.csv")
    known_evidence = load_known_ids(dataset_dir())
    records: list[dict] = []
    for case in build_cases():
        outcome = plan_case(case.input, rulebook)
        result = outcome.result
        problems: list[str] = []
        if result.deletion_status.value != case.expected_status:
            problems.append(
                f"status {result.deletion_status.value} != {case.expected_status}"
            )
        actual = _actual_steps(result)
        if actual != case.expected_steps:
            problems.append(f"steps {actual} != {case.expected_steps}")
        if outcome.review_required != case.expect_review:
            problems.append(
                f"review_required {outcome.review_required} != {case.expect_review}"
            )
        if case.expect_warning_contains and not any(
            case.expect_warning_contains in warning for warning in outcome.warnings
        ):
            problems.append(f"no warning containing {case.expect_warning_contains!r}")
        # The produced row must satisfy the official validator. Cases flagged
        # for review are exempt: their empty output is the documented contract
        # gap (no finding operation exists for an absent-when-required record).
        if not outcome.review_required:
            rows = [{
                "case_id": result.case_id,
                "deletion_status": result.deletion_status.value,
                "steps_json": steps_to_json(result.steps),
            }]
            for issue in validate_rows(rows, known_evidence_ids=known_evidence):
                problems.append(f"validator: {issue.message}")
        records.append({
            "case_id": case.case_id,
            "title": case.title,
            "passed": not problems,
            "problems": problems,
        })
    return records


def main() -> int:
    records = run_cases()
    for record in records:
        mark = "PASS" if record["passed"] else "FAIL"
        print(f"{mark}  {record['case_id']}  {record['title']}")
        for problem in record["problems"]:
            print(f"      {problem}")
    passed = sum(1 for record in records if record["passed"])
    print(f"\n{passed}/{len(records)} custom cases passed")
    return 0 if passed == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
