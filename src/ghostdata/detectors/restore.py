"""Backup and restore-path risk detector."""

from __future__ import annotations

from collections.abc import Iterable

from ghostdata.contract import ResourceState


def detect_restore_risks(resources: Iterable[ResourceState]) -> list[ResourceState]:
    return sorted(
        (
            item
            for item in resources
            if item.kind == "backup" and item.exists_at_audit and item.can_restore_user_data
        ),
        key=lambda item: (item.system_id, item.resource_id),
    )


__all__ = ["detect_restore_risks"]
