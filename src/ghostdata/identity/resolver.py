"""Identity resolver (task A3): from one case email to a complete identity.

What it does
------------
1. Matches the request email against the current snapshot *and* the audit
   history (case-insensitive, whitespace-safe, ``+tag`` as fallback only).
2. Rebuilds an **ownership timeline** for that address from
   ``user_audit_log`` so an address later reused by somebody else never pulls
   in the other person's records (playbook edge case 9).
3. Emits :class:`~ghostdata.contract.ResolvedIdentity` with every identifier
   (current + historical emails, all hash variants, phone, name) and the
   ``audit_id`` values that prove each link.

Rules
-----
* Never guess: an unknown email yields an empty identity plus a plain-language
  warning, not an exception (A14).
* Everything is sorted - the resolver is deterministic (A15).
* Build :class:`IdentityIndex` **once** per run, then resolve per case.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from ghostdata.contract import ResolvedIdentity
from ghostdata.identity.email import lookup_keys, normalize_email, sha256_hex
from ghostdata.loaders.identity_csv import IdentityAuditEvent, UserIdentity

_MIN = datetime.min.replace(tzinfo=UTC)
_MAX = datetime.max.replace(tzinfo=UTC)

# Ownership interval = [start, end); end defaults to "still owns it".
_Interval = tuple[datetime, datetime]


class IdentityIndex:
    """Pre-built lookup tables over identities + audit log (build once, A15)."""

    def __init__(
        self,
        identities: Iterable[UserIdentity],
        audit_events: Iterable[IdentityAuditEvent],
    ) -> None:
        self._snapshot_by_user: dict[str, UserIdentity] = {}
        # email key (exact or plus-stripped) -> snapshot rows
        self._snapshot_by_key: dict[str, list[UserIdentity]] = {}
        for row in identities:
            self._snapshot_by_user[row.user_id] = row
            for key in lookup_keys(row.email):
                self._snapshot_by_key.setdefault(key, []).append(row)

        # email key -> audit events that mention that address in old/new value
        self._audit_by_key: dict[str, list[IdentityAuditEvent]] = {}
        # user_id -> that user's audit events, oldest first
        self._audit_by_user: dict[str, list[IdentityAuditEvent]] = {}
        for event in sorted(audit_events, key=lambda e: (e.event_time, e.audit_id)):
            if event.field_name == "email":
                for key in {normalize_email(event.old_value), normalize_email(event.new_value)} - {
                    ""
                }:
                    for lookup in lookup_keys(key):
                        bucket = self._audit_by_key.setdefault(lookup, [])
                        if event not in bucket:
                            bucket.append(event)
            self._audit_by_user.setdefault(event.user_id, []).append(event)

    # ------------------------------------------------------------------ #
    # matching
    # ------------------------------------------------------------------ #
    def _snapshot_matches(self, email: str) -> tuple[list[UserIdentity], bool]:
        """Exact matches first; ``+tag`` fallback only when exact finds nothing."""
        for key in lookup_keys(email):
            rows = self._snapshot_by_key.get(key, [])
            if rows:
                return sorted(rows, key=lambda r: r.user_id), key != normalize_email(email)
        return [], False

    def _audit_matches(self, email: str) -> tuple[list[IdentityAuditEvent], bool]:
        for key in lookup_keys(email):
            events = self._audit_by_key.get(key, [])
            if events:
                return list(events), key != normalize_email(email)
        return [], False

    # ------------------------------------------------------------------ #
    # ownership timeline
    # ------------------------------------------------------------------ #
    def _ownership_intervals(
        self,
        email: str,
        events: Sequence[IdentityAuditEvent],
        snapshot_owner: str | None,
        warnings: list[str],
    ) -> dict[str, list[_Interval]]:
        """When did each user own this address? Returns user_id -> intervals."""
        keys = set(lookup_keys(email))
        intervals: dict[str, list[_Interval]] = {}
        owner: str | None = None
        open_start: datetime | None = None

        def close(at: datetime) -> None:
            nonlocal owner, open_start
            if owner is not None and open_start is not None:
                intervals.setdefault(owner, []).append((open_start, at))
            owner, open_start = None, None

        email_events = [e for e in events if e.field_name == "email"]
        for event in email_events:  # already sorted oldest-first
            old, new = normalize_email(event.old_value), normalize_email(event.new_value)
            if old in keys:
                if owner == event.user_id:
                    close(event.event_time)
                elif owner is None:
                    # The address predates the audit log: this release opens its
                    # first known ownership window.
                    intervals.setdefault(event.user_id, []).append((_MIN, event.event_time))
            if new in keys:
                if owner is not None and owner != event.user_id:
                    # Transfer recorded without an explicit release.
                    warnings.append(
                        f"Address {email} moved from {owner} to {event.user_id} "
                        f"at {event.event_time:%Y-%m-%d %H:%M} UTC; treated as a handover."
                    )
                    close(event.event_time)
                if owner is None:
                    owner, open_start = event.user_id, event.event_time

        last_event = email_events[-1].event_time if email_events else _MIN
        if snapshot_owner is not None:
            if owner == snapshot_owner:
                intervals.setdefault(snapshot_owner, []).append((open_start or last_event, _MAX))
            else:
                if owner is not None:
                    warnings.append(
                        f"Snapshot disagrees with the audit log about who owns {email}; "
                        "using the current snapshot."
                    )
                    close(last_event)
                elif email_events:
                    warnings.append(
                        f"Audit log shows {email} was released, but the current snapshot "
                        f"still lists it for {snapshot_owner}; using the snapshot."
                    )
                start = last_event if email_events else _MIN
                intervals.setdefault(snapshot_owner, []).append((start, _MAX))
        elif owner is not None and open_start is not None:
            # Audit says the address is still held but the snapshot has moved on.
            intervals.setdefault(owner, []).append((open_start, _MAX))
        return intervals

    @staticmethod
    def _owner_at(
        intervals: dict[str, list[_Interval]],
        moment: datetime,
    ) -> list[str]:
        return sorted(
            user_id
            for user_id, spans in intervals.items()
            if any(start <= moment < end for start, end in spans)
        )

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def resolve(
        self,
        case_id: str,
        email: str,
        requested_at: datetime,
        warnings: list[str] | None = None,
    ) -> ResolvedIdentity:
        """Resolve one case's email into a full, evidence-backed identity."""
        notes = warnings if warnings is not None else []
        target = normalize_email(email)
        snapshot_rows, used_plus = self._snapshot_matches(target)
        audit_events, audit_plus = self._audit_matches(target)
        if used_plus or audit_plus:
            notes.append(f"Matched '{email}' after ignoring its +tag.")

        candidates = {row.user_id for row in snapshot_rows} | {e.user_id for e in audit_events}
        if not candidates:
            notes.append(
                f"No user record found for '{email}'; this case will be audited "
                "with no linked identifiers."
            )
            return ResolvedIdentity(
                case_id=case_id,
                user_ids=[],
                emails_current=[],
                emails_historical=[],
                email_hashes=[],
                other_identifiers={},
                identity_evidence_ids=[],
            )

        snapshot_owner = snapshot_rows[0].user_id if len(snapshot_rows) == 1 else None
        if len(snapshot_rows) > 1:
            notes.append(
                f"'{email}' is listed for several users "
                f"({', '.join(sorted(r.user_id for r in snapshot_rows))}); ambiguity flagged."
            )

        intervals = self._ownership_intervals(target, audit_events, snapshot_owner, notes)
        owners_here = self._owner_at(intervals, requested_at)

        if len(owners_here) == 1:
            owner = owners_here[0]
        elif len(owners_here) > 1:
            owner = snapshot_owner if snapshot_owner in owners_here else sorted(owners_here)[-1]
            notes.append(
                f"'{email}' was owned by several users at the request time "
                f"({', '.join(owners_here)}); kept {owner} and flagged the ambiguity."
            )
        else:
            # Nobody holds it exactly at requested_at (address released, or a gap
            # in the log). Fall back to the most recent owner at or before it.
            def last_seen(user_id: str) -> datetime:
                seen = [
                    moment
                    for start, end in intervals.get(user_id, [])
                    for moment in (start, end)
                    if moment <= requested_at and moment not in (_MIN, _MAX)
                ]
                return max(seen, default=_MIN)

            if len(candidates) == 1:
                # The address has only ever belonged to one user - unambiguous,
                # even though no interval covers the request time exactly.
                owner = next(iter(candidates))
            else:
                ranked = sorted(candidates, key=lambda u: (last_seen(u), u))
                owner = ranked[-1]
                notes.append(
                    f"Could not confirm who owned '{email}' at the request time; "
                    f"used the most recent owner ({owner})."
                )

        return self._build_identity(case_id, owner, snapshot_owner, notes)

    def _build_identity(
        self,
        case_id: str,
        owner: str,
        snapshot_owner: str | None,
        warnings: list[str],
    ) -> ResolvedIdentity:
        snapshot = self._snapshot_by_user.get(owner)
        events = self._audit_by_user.get(owner, [])

        # --- emails: audit chain in order of change, current excluded -------
        chain: list[str] = []
        for event in events:
            if event.field_name != "email":
                continue
            for value in (event.old_value, event.new_value):
                normalized = normalize_email(value)
                if normalized and normalized not in chain:
                    chain.append(normalized)
        current = normalize_email(snapshot.email) if snapshot else ""
        historical = [address for address in chain if address != current]

        # --- hashes: snapshot + audit values + computed for every email -----
        hashes: list[str] = []

        def add_hash(value: str) -> None:
            normalized = (value or "").strip().lower()
            if normalized and normalized not in hashes:
                hashes.append(normalized)

        if snapshot:
            add_hash(snapshot.email_hash)
        for event in events:
            if event.field_name == "email_hash":
                add_hash(event.old_value)
                add_hash(event.new_value)
        for address in ([current] if current else []) + historical:
            add_hash(sha256_hex(address))

        # --- other identifiers --------------------------------------------
        other: dict[str, object] = {}
        if snapshot and snapshot.name:
            other["name"] = snapshot.name
        if snapshot and snapshot.phone:
            other["phone"] = snapshot.phone
        current_phone = snapshot.phone if snapshot else ""
        seen_phones = {current_phone}
        phone_history: list[str] = []
        for event in events:
            if event.field_name != "phone":
                continue
            for value in (event.old_value, event.new_value):
                normalized = value.strip()
                if normalized and normalized not in seen_phones:
                    seen_phones.add(normalized)
                    phone_history.append(normalized)
        if phone_history:
            other["phone_history"] = phone_history

        # --- evidence: every audit row that supports these links -----------
        evidence_ids = [event.audit_id for event in events]

        emails_current = [current] if current else []
        return ResolvedIdentity(
            case_id=case_id,
            user_ids=[owner],
            emails_current=emails_current,
            emails_historical=historical,
            email_hashes=hashes,
            other_identifiers=other,
            identity_evidence_ids=evidence_ids,
        )


def resolve_identity(
    case_id: str,
    email: str,
    requested_at: datetime,
    identities: Iterable[UserIdentity],
    audit_events: Iterable[IdentityAuditEvent],
    warnings: list[str] | None = None,
) -> ResolvedIdentity:
    """One-shot convenience wrapper (builds an index per call).

    The batch pipeline should build one :class:`IdentityIndex` and call
    :meth:`IdentityIndex.resolve` per case instead (A15).
    """
    return IdentityIndex(identities, audit_events).resolve(case_id, email, requested_at, warnings)
