"""Unit tests for the typed loaders (task A2 acceptance).

Every failure mode must raise LoaderError with a plain-language message -
never a raw traceback (playbook A2/A14: nothing crashes a batch).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ghostdata.loaders import (
    LoaderError,
    load_activity,
    load_evidence_manifest,
    load_identities,
    load_identity_audit,
    load_requests,
    load_rules,
)

REQUESTS_HEADER = "case_id,email,requested_at,reported_status,reported_at,audit_at,request_text\n"


def _write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8", newline="")
    return path


# --------------------------------------------------------------------- #
# deletion_requests.csv
# --------------------------------------------------------------------- #
def test_load_requests_normalises_and_types(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "deletion_requests.csv",
        REQUESTS_HEADER + "case_01,  User@Example.COM ,2026-07-16T08:00:00Z,COMPLETE,"
        "2026-07-18T02:00:00Z,2026-07-19T13:00:00Z,  Please delete my data.  \n"
        + "case_02,user@example.com,2026-07-16T08:00:00+00:00,NOT_STARTED,,"
        "2026-07-19T13:00:00Z,Second request\n",
    )
    requests = load_requests(path)
    assert [r.case_id for r in requests] == ["case_01", "case_02"]
    first, second = requests
    assert first.email == "user@example.com"  # lower-cased and stripped
    assert first.requested_at.tzinfo is not None  # aware datetime
    assert first.requested_at.utcoffset().total_seconds() == 0  # UTC
    assert first.reported_status == "COMPLETE"
    assert first.request_text == "Please delete my data."  # stripped
    assert second.reported_at is None  # empty optional timestamp


def test_load_requests_missing_column_is_friendly(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "deletion_requests.csv",
        "case_id,email,requested_at,reported_status,reported_at,request_text\n"
        "case_01,a@b.com,2026-07-16T08:00:00Z,COMPLETE,2026-07-18T02:00:00Z,hi\n",
    )
    with pytest.raises(LoaderError) as exc:
        load_requests(path)
    assert "audit_at" in str(exc.value)
    assert "missing" in str(exc.value)


def test_load_requests_bad_timestamp_names_the_field(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "deletion_requests.csv",
        REQUESTS_HEADER + "case_01,a@b.com,not-a-date,COMPLETE,,2026-07-19T13:00:00Z,hi\n",
    )
    with pytest.raises(LoaderError) as exc:
        load_requests(path)
    assert "requested_at" in str(exc.value)
    assert "not-a-date" in str(exc.value)


def test_load_requests_unknown_status_rejected(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "deletion_requests.csv",
        REQUESTS_HEADER + "case_01,a@b.com,2026-07-16T08:00:00Z,MAYBE,,2026-07-19T13:00:00Z,hi\n",
    )
    with pytest.raises(LoaderError) as exc:
        load_requests(path)
    assert "MAYBE" in str(exc.value)
    assert "COMPLETE" in str(exc.value)  # hint lists the allowed values


def test_load_requests_missing_file_is_friendly(tmp_path: Path) -> None:
    with pytest.raises(LoaderError) as exc:
        load_requests(tmp_path / "nope.csv")
    assert "File not found" in str(exc.value)


def test_load_requests_empty_file_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, "deletion_requests.csv", REQUESTS_HEADER)
    with pytest.raises(LoaderError) as exc:
        load_requests(path)
    assert "no requests" in str(exc.value)


# --------------------------------------------------------------------- #
# identity files
# --------------------------------------------------------------------- #
def test_load_identities_and_audit(tmp_path: Path) -> None:
    identities_path = _write(
        tmp_path,
        "user_identities.csv",
        "user_id,name,email,phone,email_hash,updated_at\n"
        "user_01,Amina El-Masri,  Amina@Gmail.com ,+971 50 000 0000,"
        "D4E1F59ABCF9A1E0CDCDC27AD6C07ED4FF88B326A16ED5EED5EC6BC31618C93,"
        "2026-05-28T04:03:00Z\n",
    )
    identities = load_identities(identities_path)
    assert identities[0].email == "amina@gmail.com"
    assert identities[0].email_hash == identities[0].email_hash.lower()  # normalised
    assert identities[0].updated_at.year == 2026

    audit_path = _write(
        tmp_path,
        "user_audit_log.csv",
        "audit_id,user_id,event_time,field_name,old_value,new_value\n"
        "audit_02,user_01,2026-02-01T00:00:00Z,email,b@x.com,c@x.com\n"
        "audit_01,user_01,2026-01-01T00:00:00Z,email,a@x.com,b@x.com\n",
    )
    events = load_identity_audit(audit_path)
    assert [e.audit_id for e in events] == ["audit_01", "audit_02"]  # oldest first


# --------------------------------------------------------------------- #
# activity / rules / evidence
# --------------------------------------------------------------------- #
def test_load_activity_sorted_and_typed(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        "system_activity.csv",
        "activity_id,event_time,event_type,source_system,target_system,resource_id,"
        "reported_result,details\n"
        "activity_02,2026-02-01T00:00:00Z,delete_record,account_service,search_service,"
        "search_1,SUCCESS,done\n"
        "activity_01,2026-01-01T00:00:00Z,sync_record,a,b,flow_1,FAILED,boom\n",
    )
    events = load_activity(path)
    assert [e.activity_id for e in events] == ["activity_01", "activity_02"]
    assert events[1].event_type == "DELETE_RECORD"  # upper-cased


def test_load_rules_and_evidence(tmp_path: Path) -> None:
    rules = load_rules(
        _write(
            tmp_path,
            "deletion_rules.csv",
            "rule_id,data_category,condition,required_action\nrule_01,user_profile,Always,delete\n",
        )
    )
    assert rules[0].required_action == "DELETE"
    assert rules[0].data_category == "USER_PROFILE"

    evidence = load_evidence_manifest(
        _write(
            tmp_path,
            "evidence_files.csv",
            "file_id,file_path,origin,captured_at\n"
            "evidence_01,evidence/logs/x.log,central_export,2026-09-15T11:59:39Z\n",
        )
    )
    assert evidence[0].file_path == "evidence/logs/x.log"
    assert evidence[0].captured_at is not None
