"""Regression tests for the person-A evidence loaders and state replay."""

from __future__ import annotations

from datetime import datetime

from ghostdata.contract import ResolvedIdentity
from ghostdata.detectors import detect_active_flows, detect_exposed_pii, detect_leftovers
from ghostdata.loaders import (
    ActivityEvent,
    DeletionRule,
    EvidenceFile,
    EvidenceIndex,
    EvidenceMatch,
    EvidenceRecord,
    LoaderError,
    extract_document,
    load_log_text,
    parse_records_text,
    parse_timestamp,
)
from ghostdata.loaders.documents import DocumentExtraction
from ghostdata.loaders.evidence_index import _records_from_text_document
from ghostdata.state import reconstruct_resources, replay_activity


def ts(value: str) -> datetime:
    return parse_timestamp(value, field="test timestamp")


def identity() -> ResolvedIdentity:
    return ResolvedIdentity(
        case_id="case_test",
        user_ids=["user_01"],
        emails_current=["new@example.com"],
        emails_historical=["old@example.com"],
        email_hashes=["a" * 64],
        other_identifiers={"name": "Amina Example", "phone": "+1 202 555 0101"},
        identity_evidence_ids=["audit_01"],
    )


def test_log_parser_handles_app_trace_syslog_and_nested_cloud_message() -> None:
    text = "\n".join(
        [
            (
                "2026-01-02T03:04:05Z [INFO] [support_platform] [tr-1] message_scan: "
                'resource_id="support_8" matched_value="old@example.com"'
            ),
            (
                "2026-01-02T03:04:06Z <15>1 node-1 account_service tr-2 - - level=INFO "
                'event="profile_lookup_completed" resource_id="account_9" rows="0"'
            ),
            (
                r"2026-01-02T03:04:07Z requestId=tr-3 level=DEBUG function=profile_service "
                r'message="resource_id=\"account_10\" '
                r'event=\"profile_lookup_completed\" rows=\"1\""'
            ),
        ]
    )
    parsed = load_log_text(text, evidence_id="evidence_01")
    assert parsed.malformed_lines == 0
    assert [event.system_id for event in parsed.events] == [
        "support_platform",
        "account_service",
        "profile_service",
    ]
    assert [event.resource_id for event in parsed.events] == [
        "support_8",
        "account_9",
        "account_10",
    ]
    assert parsed.events[2].event_type == "PROFILE_LOOKUP_COMPLETED"
    assert parsed.events[2].fields["rows"] == "1"


def test_log_parser_does_not_treat_service_or_event_names_as_resource_ids() -> None:
    parsed = load_log_text(
        "\n".join(
            [
                "2026-01-02T03:04:05Z level=DEBUG service=account_service "
                "event=profile_lookup_started",
                "2026-01-02T03:04:06Z level=INFO service=account_service "
                "event=profile_lookup_completed resource_id=account_19 rows=1",
            ]
        )
    )
    assert [event.resource_id for event in parsed.events] == ["", "account_19"]


def test_json_parser_inherits_snapshot_system_collection_and_time() -> None:
    records = parse_records_text(
        '{"snapshots":[{"captured_at":"2026-03-04T05:06:07Z",'
        '"data_store":"analytics_platform","collection":"customer_analytics_profiles",'
        '"records":[{"resource_id":"analytics_7","user_id":"user_01",'
        '"email":"old@example.com","phone":null}]}]}',
        evidence_id="evidence_02",
        captured_at=ts("2026-03-04T06:00:00Z"),
    )
    assert len(records) == 1
    record = records[0]
    assert record.system_id == "analytics_platform"
    assert record.data_category == "ANALYTICS_PROFILE"
    assert record.observed_at == ts("2026-03-04T05:06:07Z")
    assert record.identifiers_present == ("email",)


def test_log_trace_fields_are_shared_across_start_and_result_lines() -> None:
    parsed = load_log_text(
        "\n".join(
            [
                "2026-01-02T03:04:05Z level=DEBUG service=support_replica "
                "trace_id=tr-1 event=contact_query_started lookup_key=old@example.com "
                "source=legacy_contact_index",
                "2026-01-02T03:04:06Z level=INFO service=support_replica "
                "trace_id=tr-1 event=contact_query_completed resource_id=support_2 rows=1",
            ]
        ),
        evidence_id="evidence_03",
    )
    assert parsed.events[1].fields["lookup_key"] == "old@example.com"
    assert parsed.events[1].fields["source"] == "legacy_contact_index"


def test_json_structured_log_extracts_system_and_flow_state() -> None:
    parsed = load_log_text(
        '2026-04-19T06:53:19Z {"severity":"WARN","logger":"integration_service",'
        '"service":"integration_service","resource_id":"data_flow_8256",'
        '"event":"connector_heartbeat","enabled":"true",'
        '"correlation_key":"subject@example.com"}'
    )
    assert parsed.events[0].system_id == "integration_service"
    assert parsed.events[0].resource_id == "data_flow_8256"
    assert parsed.events[0].fields["enabled"] == "true"


def test_pipe_delimited_log_extracts_service_and_flow_state() -> None:
    parsed = load_log_text(
        "2026-02-03T05:54:19Z | WARN | integration_service | tr-1 | "
        'connector_heartbeat | resource_id="data_flow_9556" enabled="true"'
    )
    assert parsed.events[0].system_id == "integration_service"
    assert parsed.events[0].resource_id == "data_flow_9556"
    assert parsed.events[0].fields["enabled"] == "true"


def test_document_text_cache_and_path_escape_guard(tmp_path) -> None:
    dataset = tmp_path / "dataset"
    evidence = dataset / "evidence" / "documents"
    evidence.mkdir(parents=True)
    source = evidence / "note.txt"
    source.write_text("Resource support_1 is retained.", encoding="utf-8")
    entry = EvidenceFile("evidence_20", "evidence/documents/note.txt", "test", None)
    cache = tmp_path / "cache"
    first = extract_document(entry, dataset, cache_dir=cache)
    second = extract_document(entry, dataset, cache_dir=cache)
    assert first.method == "plain_text"
    assert second.text == first.text
    assert first.content_sha256 == second.content_sha256
    escaped = extract_document(
        EvidenceFile("evidence_21", "../../outside.txt", "test", None), dataset
    )
    assert escaped.text == ""
    assert "outside dataset" in escaped.warnings[0]


def test_malformed_json_is_a_friendly_loader_error() -> None:
    try:
        parse_records_text("{not json", evidence_id="evidence_22")
    except LoaderError as exc:
        assert "malformed" in str(exc).casefold()
    else:
        raise AssertionError("malformed evidence JSON must raise LoaderError")


def test_identifier_matching_respects_resource_id_boundaries_and_audit_cutoff() -> None:
    base = dict(
        evidence_id="evidence_01",
        file_path="evidence/records/records.json",
        source_type="json",
        captured_at=ts("2026-06-01T00:00:00Z"),
        observed_at=ts("2026-06-01T00:00:00Z"),
        system_id="analytics_platform",
        data_category="ANALYTICS_PROFILE",
        kind="record",
        replica=None,
        status="PRESENT",
    )
    index = EvidenceIndex(
        [
            EvidenceRecord(resource_id="analytics_1", raw={"user_id": "user_010"}, **base),
            EvidenceRecord(resource_id="analytics_2", raw={"user_id": "user_01"}, **base),
            EvidenceRecord(
                resource_id="analytics_3",
                raw={"user_id": "user_01"},
                **{**base, "observed_at": ts("2026-08-01T00:00:00Z")},
            ),
        ]
    )
    hits = index.find_records(identity(), ts("2026-07-01T00:00:00Z"))
    assert [hit.record.resource_id for hit in hits] == ["analytics_2"]


def test_replay_includes_events_through_cutoff_and_marks_them_as_claims() -> None:
    activity = [
        ActivityEvent(
            "activity_01",
            ts("2026-01-01T00:00:00Z"),
            "CHECK_DATA_FLOW",
            "deletion_worker",
            "integration_service",
            "data_flow_1",
            "FAILED",
            "Connector check for user_01: data flow data_flow_1 remains enabled.",
        ),
        ActivityEvent(
            "activity_02",
            ts("2026-01-03T00:00:00Z"),
            "CHECK_DATA_FLOW",
            "deletion_worker",
            "integration_service",
            "data_flow_1",
            "SUCCESS",
            "Connector check for user_01: data flow data_flow_1 is disabled.",
        ),
        ActivityEvent(
            "activity_03",
            ts("2026-01-04T00:00:00Z"),
            "CHECK_DATA_FLOW",
            "deletion_worker",
            "integration_service",
            "data_flow_1",
            "SUCCESS",
            "Connector check for user_01: data flow data_flow_1 remains enabled.",
        ),
    ]
    timeline = replay_activity(activity, identity(), ts("2026-01-03T00:00:00Z"))
    events = timeline[("integration_service", "data_flow_1")]
    assert [item["evidence_id"] for item in events] == ["activity_01", "activity_02"]
    assert all(item["claim_only"] for item in events)
    assert events[-1]["state_claim"] == "DISABLED"


def test_resource_reconstruction_uses_explicit_check_text_not_reported_result() -> None:
    event = ActivityEvent(
        "activity_09",
        ts("2026-01-01T00:00:00Z"),
        "CHECK_DATA_FLOW",
        "deletion_worker",
        "integration_service",
        "data_flow_9",
        "FAILED",
        "Data flow data_flow_9 remains enabled for user_01.",
    )
    resources = reconstruct_resources(
        [], identity(), ts("2026-01-02T00:00:00Z"), activity_events=[event]
    )
    assert len(resources) == 1
    assert resources[0].is_active_flow is True
    assert resources[0].evidence_id == "activity_09"
    assert resources[0].confidence == 0.7


def test_identity_link_activity_does_not_claim_resource_presence() -> None:
    event = ActivityEvent(
        "activity_link_only",
        ts("2026-01-01T00:00:00Z"),
        "LINK_RESOURCE_IDENTITY",
        "data_catalog",
        "object_storage",
        "object_19",
        "SUCCESS",
        "Linked user_01 to object_19",
    )
    resources = reconstruct_resources(
        [], identity(), ts("2026-01-02T00:00:00Z"), activity_events=[event]
    )
    assert resources == []


def test_identity_link_joins_independent_cutoff_file_alias_evidence() -> None:
    image = DocumentExtraction(
        evidence_id="evidence_46",
        file_path="evidence/images/object_storage_browser.png",
        content_sha256="fixture-digest",
        method="tesseract_ocr",
        text=(
            "Nimbus Object Storage\n"
            "eu-west-1 / support-attachments\n"
            "delivery_confirmation_19.pdf\n"
        ),
        confidence=0.65,
    )
    index = EvidenceIndex(
        [],
        extractions=[image],
        manifest_times={"evidence_46": ts("2026-02-13T08:00:00Z")},
        manifest_origins={"evidence_46": "object_storage"},
    )
    link = ActivityEvent(
        "activity_4007",
        ts("2026-02-13T08:07:01Z"),
        "LINK_RESOURCE_IDENTITY",
        "data_catalog",
        "object_storage",
        "object_19",
        "SUCCESS",
        "Attachment catalog confirmed object_19 (delivery_confirmation_19.pdf) "
        "belongs only to new@example.com and user_01.",
    )

    linked_ids, matches = index.find_linked_resource_records(
        identity(), [link], ts("2026-02-14T10:00:00Z")
    )

    assert linked_ids == ["object_19"]
    assert len(matches) == 1
    assert matches[0].record.evidence_id == "evidence_46"
    assert matches[0].record.system_id == "object_storage"
    assert matches[0].record.resource_id == "object_19"
    assert matches[0].record.data_category == "SUPPORT_ATTACHMENT"
    assert matches[0].record.status == "PRESENT"


def test_screenshot_origin_and_continuous_sync_set_flow_system_and_state() -> None:
    entry = EvidenceFile(
        "evidence_14",
        "evidence/images/connector_management_console_20260807.png",
        "integration_admin",
        ts("2026-08-07T08:00:00Z"),
    )
    extraction = DocumentExtraction(
        evidence_id="evidence_14",
        file_path=entry.file_path,
        content_sha256="fixture-digest",
        method="tesseract_ocr",
        text=(
            "Connections data_flow_1121 Status Healthy "
            "Selector new@example.com Sync mode Continuous sync"
        ),
        confidence=0.65,
    )

    records = _records_from_text_document(entry, extraction)

    flow = next(record for record in records if record.resource_id == "data_flow_1121")
    assert flow.system_id == "integration_service"
    assert flow.kind == "flow"
    assert flow.status == "ACTIVE"


def test_identity_link_alias_evidence_after_cutoff_is_excluded() -> None:
    image = DocumentExtraction(
        evidence_id="evidence_46",
        file_path="evidence/images/object_storage_browser.png",
        content_sha256="fixture-digest",
        method="tesseract_ocr",
        text="Nimbus Object Storage delivery_confirmation_19.pdf",
        confidence=0.65,
    )
    index = EvidenceIndex(
        [],
        extractions=[image],
        manifest_times={"evidence_46": ts("2026-02-13T08:11:00Z")},
        manifest_origins={"evidence_46": "object_storage"},
    )
    link = ActivityEvent(
        "activity_4007",
        ts("2026-02-13T08:07:01Z"),
        "LINK_RESOURCE_IDENTITY",
        "data_catalog",
        "object_storage",
        "object_19",
        "SUCCESS",
        "object_19 (delivery_confirmation_19.pdf) belongs to new@example.com and user_01.",
    )

    linked_ids, matches = index.find_linked_resource_records(
        identity(), [link], ts("2026-02-13T08:10:00Z")
    )

    assert linked_ids == ["object_19"]
    assert matches == []


def test_resource_status_miss_and_deleted_are_absent_but_hit_is_present() -> None:
    resources = reconstruct_resources(
        [
            EvidenceMatch(
                EvidenceRecord(
                    evidence_id=f"evidence_{index}",
                    file_path="snapshot.json",
                    source_type="json",
                    captured_at=ts("2026-01-01T00:00:00Z"),
                    observed_at=None,
                    system_id="search_service",
                    resource_id=f"search_{index}",
                    data_category="SEARCH_INDEX_ENTRY",
                    kind="index",
                    replica=None,
                    status=status,
                    raw={"result": status},
                ),
                ("user_01",),
            )
            for index, status in enumerate(("MISS", "DELETED", "HIT"), start=1)
        ],
        identity(),
        ts("2026-01-02T00:00:00Z"),
    )
    assert [item.exists_at_audit for item in resources] == [False, False, True]


def test_detectors_separate_delete_redact_and_active_flow_findings() -> None:
    resources = reconstruct_resources(
        [
            EvidenceMatch(
                EvidenceRecord(
                    evidence_id="evidence_10",
                    file_path="snapshot.sql",
                    source_type="sql",
                    captured_at=ts("2026-01-01T00:00:00Z"),
                    observed_at=None,
                    system_id="account_service",
                    resource_id="account_10",
                    data_category="USER_PROFILE",
                    kind="record",
                    replica="primary",
                    status="PRESENT",
                    identifiers_present=("email",),
                    raw={"email": "old@example.com", "user_id": "user_01"},
                ),
                ("old@example.com",),
            ),
            EvidenceMatch(
                EvidenceRecord(
                    evidence_id="evidence_11",
                    file_path="snapshot.json",
                    source_type="json",
                    captured_at=ts("2026-01-01T00:00:00Z"),
                    observed_at=None,
                    system_id="support_platform",
                    resource_id="support_11",
                    data_category="SUPPORT_MESSAGE",
                    kind="record",
                    replica=None,
                    status="PRESENT",
                    identifiers_present=("email",),
                    raw={"requester_email": "old@example.com"},
                ),
                ("old@example.com",),
            ),
        ],
        identity(),
        ts("2026-01-02T00:00:00Z"),
    )
    rules = [
        DeletionRule("r1", "USER_PROFILE", "Always", "DELETE"),
        DeletionRule("r2", "SUPPORT_MESSAGE", "Keep context", "REDACT"),
    ]
    assert [item.resource_id for item in detect_leftovers(resources, rules)] == ["account_10"]
    assert [item.resource_id for item in detect_exposed_pii(resources, rules)] == ["support_11"]
    flow = reconstruct_resources(
        [],
        identity(),
        ts("2026-01-02T00:00:00Z"),
        activity_events=[
            ActivityEvent(
                "activity_12",
                ts("2026-01-01T00:00:00Z"),
                "CHECK_DATA_FLOW",
                "deletion_worker",
                "integration_service",
                "data_flow_12",
                "FAILED",
                "data_flow_12 remains enabled for user_01",
            )
        ],
    )
    assert [item.resource_id for item in detect_active_flows(flow)] == ["data_flow_12"]
