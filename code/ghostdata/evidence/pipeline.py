"""Adapter implementing the provider protocol expected by Person B's CLI."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ghostdata.audit import EvidenceEngine
from ghostdata.contract import CaseAuditInput
from ghostdata.loaders.requests import DeletionRequest


def build_case_audit_inputs(
    requests: list[dict[str, str]],
    dataset: str | Path,
    *,
    workers: int = 1,
    no_llm: bool = True,
    resume: bool = True,
) -> Iterable[CaseAuditInput]:
    """Load the dataset once, then yield evidence audits in requested order.

    Evidence extraction is local and deterministic. The current engine does not
    make model calls; ``workers``, ``no_llm``, and ``resume`` are accepted for
    CLI compatibility and reserved for later extraction backends.
    """
    del workers, no_llm, resume
    base = Path(dataset)
    engine = EvidenceEngine.from_dataset(base)
    for row in requests:
        request = DeletionRequest.from_row(row, path=str(base / "deletion_requests.csv"))
        yield engine.audit_case(request)


__all__ = ["build_case_audit_inputs"]
