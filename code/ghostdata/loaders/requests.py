"""Typed loader for ``deletion_requests.csv`` - the 518 cases (task A2)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ghostdata.loaders.errors import LoaderError
from ghostdata.loaders.tabular import read_csv_rows
from ghostdata.loaders.timeutil import parse_optional_timestamp, parse_timestamp

_REQUIRED = (
    "case_id",
    "email",
    "requested_at",
    "reported_status",
    "reported_at",
    "audit_at",
    "request_text",
)

# The workflow's CLAIM values (never proof - AGENTS.md 6.2).
REPORTED_STATUSES = frozenset({"COMPLETE", "PARTIALLY_COMPLETE", "NOT_STARTED"})


@dataclass(frozen=True)
class DeletionRequest:
    """One audit case, normalised and typed."""

    case_id: str
    email: str  # lower-cased, whitespace-stripped
    requested_at: object  # datetime (UTC)
    reported_status: str
    reported_at: object | None  # datetime (UTC) or None
    audit_at: object  # datetime (UTC) - the cutoff for the answer
    request_text: str

    @classmethod
    def from_row(cls, row: dict[str, str], *, path: str | None = None) -> DeletionRequest:
        case_id = row.get("case_id", "")
        if not case_id:
            raise LoaderError(
                "A request row has an empty case_id", path=path, hint="Re-download dataset/."
            )
        email = row.get("email", "").strip().lower()
        if not email:
            raise LoaderError(
                f"Case {case_id} has no email address",
                path=path,
                hint="Every request needs an email to resolve an identity.",
            )
        reported_status = row.get("reported_status", "").strip().upper()
        if reported_status not in REPORTED_STATUSES:
            raise LoaderError(
                f"Case {case_id} has unknown reported_status '{reported_status}'",
                path=path,
                hint=f"Expected one of: {', '.join(sorted(REPORTED_STATUSES))}.",
            )
        return cls(
            case_id=case_id,
            email=email,
            requested_at=parse_timestamp(
                row.get("requested_at", ""), field="requested_at", path=path
            ),
            reported_status=reported_status,
            reported_at=parse_optional_timestamp(
                row.get("reported_at", ""), field="reported_at", path=path
            ),
            audit_at=parse_timestamp(row.get("audit_at", ""), field="audit_at", path=path),
            request_text=row.get("request_text", "").strip(),
        )


def load_requests(path: str | Path) -> list[DeletionRequest]:
    """Load and type-check every request row. Raises :class:`LoaderError`."""
    rows = read_csv_rows(path, _REQUIRED)
    if not rows:
        raise LoaderError(
            f"{Path(path).name} contains no requests",
            path=str(path),
            hint="The batch needs the 518-row deletion_requests.csv; re-download dataset/.",
        )
    return [DeletionRequest.from_row(row, path=str(path)) for row in rows]
