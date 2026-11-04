"""Person A's one-pass evidence engine for building ``CaseAuditInput``."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ghostdata.contract import CaseAuditInput, ResolvedIdentity
from ghostdata.identity import IdentityIndex
from ghostdata.loaders import (
    ActivityEvent,
    DeletionRequest,
    EvidenceFile,
    EvidenceIndex,
    IdentityAuditEvent,
    UserIdentity,
    load_activity,
    load_evidence_manifest,
    load_identities,
    load_identity_audit,
    load_requests,
    load_rules,
    to_utc_text,
)
from ghostdata.state import reconstruct_resources


def request_as_dict(request: DeletionRequest) -> dict[str, Any]:
    """Serialize a request while keeping timestamps in the dataset's UTC form."""
    return {
        "case_id": request.case_id,
        "email": request.email,
        "requested_at": to_utc_text(request.requested_at),
        "reported_status": request.reported_status,
        "reported_at": to_utc_text(request.reported_at) if request.reported_at else "",
        "audit_at": to_utc_text(request.audit_at),
        "request_text": request.request_text,
    }


class EvidenceEngine:
    """Run-scoped loaders and indexes; ``audit_case`` is safe to reuse."""

    def __init__(
        self,
        *,
        dataset_dir: str | Path,
        requests: Iterable[DeletionRequest],
        identities: Iterable[UserIdentity],
        identity_audit: Iterable[IdentityAuditEvent],
        activity: Iterable[ActivityEvent],
        manifest: Iterable[EvidenceFile],
        rules: Iterable[Any],
        evidence_index: EvidenceIndex,
    ) -> None:
        self.dataset_dir = Path(dataset_dir)
        self.requests = list(requests)
        self.identities = list(identities)
        self.identity_audit = list(identity_audit)
        self.activity = list(activity)
        self.manifest = list(manifest)
        self.rules = list(rules)
        self.evidence_index = evidence_index
        self.identity_index = IdentityIndex(self.identities, self.identity_audit)
        self._activity_ids = {event.activity_id for event in self.activity if event.activity_id}
        self._audit_ids = {event.audit_id for event in self.identity_audit if event.audit_id}
        self._file_ids = {entry.file_id for entry in self.manifest if entry.file_id}

    @classmethod
    def from_dataset(
        cls,
        dataset_dir: str | Path,
        *,
        cache_dir: str | Path | None = None,
    ) -> EvidenceEngine:
        base = Path(dataset_dir)
        requests = load_requests(base / "deletion_requests.csv")
        identities = load_identities(base / "user_identities.csv")
        identity_audit = load_identity_audit(base / "user_audit_log.csv")
        activity = load_activity(base / "system_activity.csv")
        manifest = load_evidence_manifest(base / "evidence_files.csv")
        rules = load_rules(base / "deletion_rules.csv")
        extraction_cache = cache_dir or (base.parent / "cache" / "evidence-text")
        evidence_index = EvidenceIndex.from_dataset(base, manifest, cache_dir=extraction_cache)
        return cls(
            dataset_dir=base,
            requests=requests,
            identities=identities,
            identity_audit=identity_audit,
            activity=activity,
            manifest=manifest,
            rules=rules,
            evidence_index=evidence_index,
        )

    @property
    def valid_evidence_ids(self) -> frozenset[str]:
        """Participant-visible IDs accepted for a cited finding or verification."""
        return frozenset(self._file_ids | self._activity_ids | self._audit_ids)

    @property
    def evidence_warnings(self) -> list[dict[str, str]]:
        """Dataset-wide parser warnings, kept separate to avoid per-case noise."""
        return [
            {"evidence_id": item.evidence_id, "message": item.message}
            for item in self.evidence_index.warnings
        ]

    def resolve_identity(
        self,
        request: DeletionRequest,
        warnings: list[str] | None = None,
    ) -> ResolvedIdentity:
        return self.identity_index.resolve(
            request.case_id,
            request.email,
            request.requested_at,
            warnings,
        )

    def audit_case(self, request: DeletionRequest) -> CaseAuditInput:
        warnings: list[str] = []
        try:
            identity = self.resolve_identity(request, warnings)
            matches = self.evidence_index.find_records(identity, request.audit_at)
            linked_resource_ids, linked_matches = (
                self.evidence_index.find_linked_resource_records(
                    identity, self.activity, request.audit_at
                )
            )
            matches.extend(linked_matches)
            resources = reconstruct_resources(
                matches,
                identity,
                request.audit_at,
                activity_events=self.activity,
                linked_resource_ids=linked_resource_ids,
            )
        except Exception as exc:
            # A corrupt or unusual case should not abort a whole 518-case run.
            identity = ResolvedIdentity(
                case_id=request.case_id,
                user_ids=[],
                emails_current=[],
                emails_historical=[],
                email_hashes=[],
                other_identifiers={},
                identity_evidence_ids=[],
            )
            resources = []
            warnings.append(
                "Case evidence could not be fully reconstructed "
                f"({type(exc).__name__}); manual review is required."
            )
        warnings = list(dict.fromkeys(warnings))
        result = CaseAuditInput(request_as_dict(request), identity, resources, warnings)
        result.warnings.extend(self.validate_evidence_ids(result))
        return result

    def validate_evidence_ids(self, result: CaseAuditInput) -> list[str]:
        """Check each resource and identity citation against participant data."""
        invalid = sorted(
            {
                item.evidence_id
                for item in result.resources
                if item.evidence_id and item.evidence_id not in self.valid_evidence_ids
            }
            | {
                item
                for item in result.identity.identity_evidence_ids
                if item and item not in self.valid_evidence_ids
            }
        )
        if invalid:
            return [
                "Evidence reference(s) are absent from participant manifests: "
                f"{', '.join(invalid)}."
            ]
        empty = [item.resource_id for item in result.resources if not item.evidence_id]
        if empty:
            return [
                f"{len(empty)} matching resource(s) have no citable evidence ID; "
                "manual review is required."
            ]
        return []

    def audit_all(self) -> list[CaseAuditInput]:
        return [self.audit_case(request) for request in self.requests]

    def coverage(self) -> list[dict[str, Any]]:
        return self.evidence_index.coverage()


__all__ = ["EvidenceEngine", "request_as_dict"]
