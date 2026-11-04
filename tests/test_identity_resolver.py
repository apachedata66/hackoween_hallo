"""Unit tests for the identity resolver (task A3 acceptance).

Covers the required cases: chains, reuse, case differences, unknown email,
hash variants, plus-addressing, determinism.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ghostdata.contract import ResolvedIdentity
from ghostdata.identity import IdentityIndex, resolve_identity, sha256_hex
from ghostdata.loaders.identity_csv import IdentityAuditEvent, UserIdentity
from ghostdata.loaders.timeutil import parse_timestamp


def ts(text: str) -> datetime:
    return parse_timestamp(text, field="test")


def ident(
    user_id: str, email: str, *, phone: str = "+1 555 000 0000", name: str = "Test User"
) -> UserIdentity:
    return UserIdentity(
        user_id=user_id,
        name=name,
        email=email.strip().lower(),
        phone=phone,
        email_hash=sha256_hex(email),
        updated_at=ts("2026-01-01T00:00:00Z"),
    )


def change(
    audit_id: str,
    user_id: str,
    when: str,
    old: str,
    new: str,
    field: str = "email",
) -> IdentityAuditEvent:
    return IdentityAuditEvent(
        audit_id=audit_id,
        user_id=user_id,
        event_time=ts(when),
        field_name=field,
        old_value=old,
        new_value=new,
    )


# --------------------------------------------------------------------- #
# A. current email, case + whitespace differences
# --------------------------------------------------------------------- #
def test_current_email_case_and_whitespace_difference() -> None:
    warnings: list[str] = []
    result = resolve_identity(
        "case_01",
        "  A@Example.COM ",
        ts("2026-06-01T00:00:00Z"),
        [ident("user_01", "a@example.com")],
        [],
        warnings,
    )
    assert result.user_ids == ["user_01"]
    assert result.emails_current == ["a@example.com"]
    assert warnings == []  # a clean match produces no noise


# --------------------------------------------------------------------- #
# B. historical chain a -> b -> c, order of change
# --------------------------------------------------------------------- #
def test_historical_chain_in_order_of_change() -> None:
    audit = [
        change("audit_01", "user_10", "2026-01-01T00:00:00Z", "a@example.com", "b@example.com"),
        change("audit_02", "user_10", "2026-02-01T00:00:00Z", "b@example.com", "c@example.com"),
    ]
    identities = [ident("user_10", "c@example.com")]

    # Case submitted under the oldest address, before the first change.
    before = resolve_identity(
        "case_a", "a@example.com", ts("2025-12-15T00:00:00Z"), identities, audit
    )
    assert before.user_ids == ["user_10"]
    assert before.emails_current == ["c@example.com"]
    assert before.emails_historical == ["a@example.com", "b@example.com"]
    assert before.identity_evidence_ids == ["audit_01", "audit_02"]

    # Same person, case submitted under the current address.
    after = resolve_identity(
        "case_c", "c@example.com", ts("2026-03-01T00:00:00Z"), identities, audit
    )
    assert after.user_ids == ["user_10"]
    assert after.emails_historical == ["a@example.com", "b@example.com"]


# --------------------------------------------------------------------- #
# C. reuse: old email later owned by a different user
# --------------------------------------------------------------------- #
def test_reused_email_never_touches_the_other_user() -> None:
    # user_x owned e@example.com until 2026-03-01, then moved to x-new@...
    # user_y acquired it on 2026-03-02 and holds it today.
    identities = [
        ident("user_x", "x-new@example.com"),
        ident("user_y", "e@example.com"),
    ]
    audit = [
        change("audit_01", "user_x", "2026-03-01T00:00:00Z", "e@example.com", "x-new@example.com"),
        change("audit_02", "user_y", "2026-03-02T00:00:00Z", "y-old@example.com", "e@example.com"),
    ]

    # Request sent while user_x still owned the address.
    early = resolve_identity(
        "case_early", "e@example.com", ts("2026-02-01T00:00:00Z"), identities, audit
    )
    assert early.user_ids == ["user_x"]
    assert "user_y" not in early.user_ids  # the other person is untouched

    # Same address, request sent after user_y took it over.
    late = resolve_identity(
        "case_late", "e@example.com", ts("2026-06-01T00:00:00Z"), identities, audit
    )
    assert late.user_ids == ["user_y"]
    assert "user_x" not in late.user_ids


# --------------------------------------------------------------------- #
# D. unknown email -> empty identity + warning, never an exception
# --------------------------------------------------------------------- #
def test_unknown_email_returns_empty_identity_with_warning() -> None:
    warnings: list[str] = []
    result = resolve_identity(
        "case_z", "ghost@example.com", ts("2026-06-01T00:00:00Z"), [], [], warnings
    )
    assert result.user_ids == []
    assert result.emails_current == []
    assert result.email_hashes == []
    assert any("No user record found" in w for w in warnings)


# --------------------------------------------------------------------- #
# E. hash variants (snapshot + audit + computed)
# --------------------------------------------------------------------- #
def test_hash_variants_cover_current_and_historical() -> None:
    identities = [ident("user_01", "new@example.com")]
    audit = [
        change("audit_01", "user_01", "2026-01-01T00:00:00Z", "old@example.com", "new@example.com"),
        change(
            "audit_02",
            "user_01",
            "2026-01-01T00:00:00Z",
            "0" * 64,
            "1" * 64,
            field="email_hash",
        ),
    ]
    result = resolve_identity(
        "case_h", "new@example.com", ts("2026-06-01T00:00:00Z"), identities, audit
    )
    assert sha256_hex("new@example.com") in result.email_hashes  # snapshot/current
    assert sha256_hex("old@example.com") in result.email_hashes  # computed for history
    assert "1" * 64 in result.email_hashes  # audit-provided variant
    assert "0" * 64 in result.email_hashes


# --------------------------------------------------------------------- #
# F. plus-addressing as a fallback match key
# --------------------------------------------------------------------- #
def test_plus_addressing_falls_back_to_the_base_address() -> None:
    warnings: list[str] = []
    result = resolve_identity(
        "case_p",
        "A+News@Example.COM",
        ts("2026-06-01T00:00:00Z"),
        [ident("user_01", "a@example.com")],
        [],
        warnings,
    )
    assert result.user_ids == ["user_01"]
    assert any("+tag" in w for w in warnings)


# --------------------------------------------------------------------- #
# G. determinism: same input, byte-identical output
# --------------------------------------------------------------------- #
def test_resolver_is_deterministic() -> None:
    identities = [ident("user_01", "a@example.com")]
    audit = [
        change("audit_01", "user_01", "2026-01-01T00:00:00Z", "z@example.com", "a@example.com")
    ]
    first = resolve_identity(
        "case_d", "a@example.com", ts("2026-06-01T00:00:00Z"), identities, audit
    )
    second = resolve_identity(
        "case_d", "a@example.com", ts("2026-06-01T00:00:00Z"), identities, audit
    )
    assert first == second
    assert isinstance(first, ResolvedIdentity)


# --------------------------------------------------------------------- #
# H. index built once, reused (A15)
# --------------------------------------------------------------------- #
def test_index_reuse_matches_one_shot_resolution() -> None:
    identities = [ident("user_01", "a@example.com"), ident("user_02", "b@example.com")]
    audit = [
        change("audit_01", "user_02", "2026-01-01T00:00:00Z", "old-b@example.com", "b@example.com")
    ]
    index = IdentityIndex(identities, audit)
    via_index = index.resolve("case_i", "b@example.com", ts("2026-06-01T00:00:00Z"))
    via_oneshot = resolve_identity(
        "case_i", "b@example.com", ts("2026-06-01T00:00:00Z"), identities, audit
    )
    assert via_index == via_oneshot
    assert via_index.user_ids == ["user_02"]
    assert via_index.emails_historical == ["old-b@example.com"]


def test_identity_is_json_serialisable() -> None:
    import json

    result = resolve_identity(
        "case_j",
        "a@example.com",
        ts("2026-06-01T00:00:00Z"),
        [ident("user_01", "a@example.com")],
        [],
    )
    payload = json.loads(json.dumps(result.to_dict()))
    assert payload["case_id"] == "case_j"
    assert payload["user_ids"] == ["user_01"]
    assert datetime(2026, 1, 1, tzinfo=UTC).year == 2026  # sanity: aware datetimes


# --------------------------------------------------------------------- #
# I. released address with a single owner: no warning noise
# --------------------------------------------------------------------- #
def test_single_owner_after_release_produces_no_ambiguity_warning() -> None:
    warnings: list[str] = []
    audit = [
        change("audit_01", "user_10", "2026-01-01T00:00:00Z", "a@example.com", "b@example.com"),
    ]
    result = resolve_identity(
        "case_r",
        "a@example.com",
        ts("2026-06-01T00:00:00Z"),
        [ident("user_10", "b@example.com")],
        audit,
        warnings,
    )
    assert result.user_ids == ["user_10"]
    assert warnings == []  # only one user ever owned it - nothing to flag
