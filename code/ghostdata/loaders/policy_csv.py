"""Typed loader for ``deletion_rules.csv`` - the policy table (task A2/B3 input)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ghostdata.loaders.tabular import read_csv_rows

_COLUMNS = ("rule_id", "data_category", "condition", "required_action")

# Allowed actions in the supplied policy.
ACTIONS = frozenset({"DELETE", "REDACT", "ANONYMIZE", "RETAIN"})


@dataclass(frozen=True)
class DeletionRule:
    """One row of the supplied policy."""

    rule_id: str
    data_category: str
    condition: str
    required_action: str  # DELETE | REDACT | ANONYMIZE | RETAIN

    @classmethod
    def from_row(cls, row: dict[str, str]) -> DeletionRule:
        return cls(
            rule_id=row.get("rule_id", ""),
            data_category=row.get("data_category", "").strip().upper(),
            condition=row.get("condition", "").strip(),
            required_action=row.get("required_action", "").strip().upper(),
        )


def load_rules(path: str | Path) -> list[DeletionRule]:
    """Load the deletion rules table (unknown actions surface in policy, B3)."""
    rows = read_csv_rows(path, _COLUMNS)
    return [DeletionRule.from_row(row) for row in rows]
