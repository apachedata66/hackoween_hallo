from __future__ import annotations

from types import SimpleNamespace

from ghostdata.review import write_review_report


def test_review_report_is_sorted_and_omits_direct_identifiers(tmp_path) -> None:
    audit = SimpleNamespace(
        request={"case_id": "case_02", "email": "person@example.com"},
        resources=[
            SimpleNamespace(
                evidence_id="evidence_20",
                system_id="security_service",
                resource_id="audit_record_20",
                data_category="SECURITY_AUDIT_LOG",
            )
        ],
    )
    outcome = SimpleNamespace(warnings=["a required record is missing"])
    destination = tmp_path / "manual_review.md"

    write_review_report(destination, [(audit, outcome)])

    report = destination.read_text(encoding="utf-8")
    assert "case_02" in report
    assert "audit_record_20" in report
    assert "evidence_20" in report
    assert "person@example.com" not in report
    assert "required_retained_record_unavailable" in report
