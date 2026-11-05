"""Policy-aware detectors over reconstructed resources."""

from __future__ import annotations

from collections.abc import Iterable

from ghostdata.contract import ResourceState
from ghostdata.loaders.policy_csv import DeletionRule


def _actions(rules: Iterable[DeletionRule]) -> dict[str, str]:
    return {rule.data_category.upper(): rule.required_action.upper() for rule in rules}


def detect_leftovers(
    resources: Iterable[ResourceState], rules: Iterable[DeletionRule]
) -> list[ResourceState]:
    """Records present where policy requires whole-record deletion."""
    actions = _actions(rules)
    return sorted(
        (
            item
            for item in resources
            if item.exists_at_audit
            and item.kind not in {"flow", "backup"}
            and actions.get(item.data_category, "") == "DELETE"
        ),
        key=lambda item: (item.system_id, item.resource_id),
    )


def detect_exposed_pii(
    resources: Iterable[ResourceState], rules: Iterable[DeletionRule]
) -> list[ResourceState]:
    """Records with direct identifiers that policy says must be redacted or removed.

    Tombstones are strict: only the stable subject reference may remain.
    Categories whose rule is DELETE are reported as remaining records instead.
    """
    actions = _actions(rules)
    return sorted(
        (
            item
            for item in resources
            if item.exists_at_audit
            and item.kind not in {"flow", "backup"}
            and item.identifiers_present
            and (
                actions.get(item.data_category, "") in {"REDACT", "ANONYMIZE"}
                or item.data_category == "ACCOUNT_TOMBSTONE"
            )
        ),
        key=lambda item: (item.system_id, item.resource_id),
    )


def detect_required_retained(
    resources: Iterable[ResourceState], rules: Iterable[DeletionRule]
) -> list[ResourceState]:
    """Present resources whose applicable rule says they must be retained."""
    actions = _actions(rules)
    return sorted(
        (
            item
            for item in resources
            if item.exists_at_audit and actions.get(item.data_category, "") == "RETAIN"
        ),
        key=lambda item: (item.system_id, item.resource_id),
    )


__all__ = ["detect_exposed_pii", "detect_leftovers", "detect_required_retained"]
