"""Print a privacy-conscious evidence timeline for one case (Person A A16)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from ghostdata.audit import EvidenceEngine  # noqa: E402


def _mask_email(value: str) -> str:
    local, separator, domain = value.partition("@")
    if not separator:
        return "[masked]"
    return f"{local[:1]}{'*' * max(3, len(local) - 1)}@{domain}"


def _mask_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    return f"***{digits[-2:]}" if digits else "[masked]"


def _safe_identity(identity: Any, reveal: bool) -> dict[str, Any]:
    if reveal:
        current = identity.emails_current
        historical = identity.emails_historical
        phone = identity.other_identifiers.get("phone", "")
        phone_history = identity.other_identifiers.get("phone_history", [])
    else:
        current = [_mask_email(item) for item in identity.emails_current]
        historical = [_mask_email(item) for item in identity.emails_historical]
        phone_value = identity.other_identifiers.get("phone", "")
        phone = _mask_phone(str(phone_value)) if phone_value else ""
        phone_history = [
            _mask_phone(str(item)) for item in identity.other_identifiers.get("phone_history", [])
        ]
    return {
        "user_ids": identity.user_ids,
        "emails_current": current,
        "emails_historical": historical,
        "email_hash_count": len(identity.email_hashes),
        "phone": phone,
        "phone_history": phone_history,
        "identity_evidence_ids": identity.identity_evidence_ids,
    }


def case_report(engine: EvidenceEngine, case_id: str, *, reveal: bool = False) -> dict[str, Any]:
    request = next((item for item in engine.requests if item.case_id == case_id), None)
    if request is None:
        raise ValueError(f"Unknown case_id: {case_id}")
    audit = engine.audit_case(request)
    return {
        "case_id": case_id,
        "audit_at": audit.request["audit_at"],
        "identity": _safe_identity(audit.identity, reveal),
        "dataset_warnings": engine.evidence_warnings,
        "resources": [
            {
                "system_id": item.system_id,
                "resource_id": item.resource_id,
                "kind": item.kind,
                "data_category": item.data_category,
                "exists_at_audit": item.exists_at_audit,
                "identifiers_present": item.identifiers_present,
                "is_active_flow": item.is_active_flow,
                "can_restore_user_data": item.can_restore_user_data,
                "replica": item.replica,
                "evidence_id": item.evidence_id,
                "confidence": item.confidence,
                "timeline": item.timeline,
                "notes": item.notes,
            }
            for item in audit.resources
        ],
        "warnings": audit.warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect one case's reconstructed evidence timeline; identifiers are masked."
    )
    parser.add_argument("case_id", help="case_id from dataset/deletion_requests.csv")
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=ROOT / "dataset",
        help="participant-facing dataset directory (default: ./dataset)",
    )
    parser.add_argument(
        "--show-identifiers",
        action="store_true",
        help="show email and phone values in this local terminal output",
    )
    args = parser.parse_args()
    try:
        engine = EvidenceEngine.from_dataset(
            args.dataset_dir, cache_dir=ROOT / "cache" / "evidence-text"
        )
        print(json.dumps(case_report(engine, args.case_id, reveal=args.show_identifiers), indent=2))
    except (OSError, ValueError) as exc:
        print(f"Could not inspect case: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
