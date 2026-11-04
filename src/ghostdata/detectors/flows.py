"""Active synchronization, indexing, import, and export flow detector."""

from __future__ import annotations

from collections.abc import Iterable

from ghostdata.contract import ResourceState


def detect_active_flows(resources: Iterable[ResourceState]) -> list[ResourceState]:
    return sorted(
        (
            item
            for item in resources
            if item.kind == "flow" and item.exists_at_audit and item.is_active_flow
        ),
        key=lambda item: (item.system_id, item.resource_id),
    )


__all__ = ["detect_active_flows"]
