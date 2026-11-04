"""Typed loaders for ``user_identities.csv`` and ``user_audit_log.csv`` (A2/A3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ghostdata.loaders.tabular import read_csv_rows
from ghostdata.loaders.timeutil import parse_timestamp

_IDENTITY_COLUMNS = ("user_id", "name", "email", "phone", "email_hash", "updated_at")
_AUDIT_COLUMNS = ("audit_id", "user_id", "event_time", "field_name", "old_value", "new_value")

# Fields the audit log is allowed to change (observed: email, email_hash, phone).
AUDITED_FIELDS = frozenset({"email", "email_hash", "phone"})


@dataclass(frozen=True)
class UserIdentity:
    """Current identity snapshot for one user_id."""

    user_id: str
    name: str
    email: str  # lower-cased
    phone: str
    email_hash: str  # lower-cased hex (SHA-256 of the email - see DECISIONS D6)
    updated_at: object  # datetime (UTC)

    @classmethod
    def from_row(cls, row: dict[str, str], *, path: str | None = None) -> UserIdentity:
        return cls(
            user_id=row.get("user_id", ""),
            name=row.get("name", ""),
            email=row.get("email", "").strip().lower(),
            phone=row.get("phone", ""),
            email_hash=row.get("email_hash", "").strip().lower(),
            updated_at=parse_timestamp(row.get("updated_at", ""), field="updated_at", path=path),
        )


@dataclass(frozen=True)
class IdentityAuditEvent:
    """One historical identity change (citable by ``audit_id``)."""

    audit_id: str
    user_id: str
    event_time: object  # datetime (UTC)
    field_name: str  # email | email_hash | phone
    old_value: str
    new_value: str

    @classmethod
    def from_row(cls, row: dict[str, str], *, path: str | None = None) -> IdentityAuditEvent:
        return cls(
            audit_id=row.get("audit_id", ""),
            user_id=row.get("user_id", ""),
            event_time=parse_timestamp(row.get("event_time", ""), field="event_time", path=path),
            field_name=row.get("field_name", "").strip().lower(),
            old_value=row.get("old_value", ""),
            new_value=row.get("new_value", ""),
        )


def load_identities(path: str | Path) -> list[UserIdentity]:
    """Load the current identity snapshot."""
    rows = read_csv_rows(path, _IDENTITY_COLUMNS)
    return [UserIdentity.from_row(row, path=str(path)) for row in rows]


def load_identity_audit(path: str | Path) -> list[IdentityAuditEvent]:
    """Load historical identity changes, oldest first."""
    rows = read_csv_rows(path, _AUDIT_COLUMNS)
    events = [IdentityAuditEvent.from_row(row, path=str(path)) for row in rows]
    events.sort(key=lambda event: (event.event_time, event.audit_id))
    return events
