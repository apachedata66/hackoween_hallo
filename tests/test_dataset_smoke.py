"""Smoke test against the real dataset (skipped when dataset/ is absent).

The dataset is git-ignored, so this test only runs locally where it has been
copied from the official repository. It proves the loaders handle the real
files end to end (task A1/A2).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ghostdata.loaders import (
    load_activity,
    load_evidence_manifest,
    load_identities,
    load_identity_audit,
    load_requests,
    load_rules,
)

DATASET = Path(__file__).resolve().parents[1] / "dataset"

pytestmark = pytest.mark.skipif(
    not (DATASET / "deletion_requests.csv").exists(),
    reason="dataset/ not present (copied locally from the official repo)",
)


def test_requests_load_with_expected_scale() -> None:
    requests = load_requests(DATASET / "deletion_requests.csv")
    assert len(requests) == 518
    assert len({r.case_id for r in requests}) == 518
    # 517 distinct emails - one address is used by two cases (see DATASET_NOTES).
    assert len({r.email for r in requests}) == 517


def test_identity_files_load() -> None:
    identities = load_identities(DATASET / "user_identities.csv")
    audit = load_identity_audit(DATASET / "user_audit_log.csv")
    assert len(identities) == 850
    assert len(audit) == 306
    assert all(len(row.email_hash) == 64 for row in identities)  # SHA-256 shaped
    # every audit row is sorted oldest-first
    assert [e.event_time for e in audit] == sorted(e.event_time for e in audit)


def test_activity_rules_evidence_load() -> None:
    activity = load_activity(DATASET / "system_activity.csv")
    rules = load_rules(DATASET / "deletion_rules.csv")
    evidence = load_evidence_manifest(DATASET / "evidence_files.csv")
    assert len(activity) == 4011
    assert len(rules) == 15
    assert len(evidence) == 94
    assert {r.required_action for r in rules} == {"DELETE", "REDACT", "ANONYMIZE", "RETAIN"}


def test_every_request_email_resolves_to_a_user() -> None:
    """A1/A3 acceptance: all 518 case emails are covered by identities/audit."""
    from ghostdata.identity import IdentityIndex

    index = IdentityIndex(
        load_identities(DATASET / "user_identities.csv"),
        load_identity_audit(DATASET / "user_audit_log.csv"),
    )
    unresolved = [
        r.case_id
        for r in load_requests(DATASET / "deletion_requests.csv")
        if not index.resolve(r.case_id, r.email, r.requested_at).user_ids
    ]
    assert unresolved == []
