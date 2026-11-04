"""Typed rulebook. Unknown categories are refused instead of guessed."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class RequiredAction(str, Enum):
    DELETE = "DELETE"
    REDACT = "REDACT"
    ANONYMIZE = "ANONYMIZE"
    RETAIN = "RETAIN"


# Identifiers a redacted record may keep. Direct identifiers must be gone.
REDACT_PERMITTED = frozenset({"user_id"})
# Anonymized records must not be linkable, so the internal user id goes too.
ANONYMIZE_PERMITTED = frozenset()


@dataclass(frozen=True)
class DeletionRule:
    rule_id: str
    data_category: str
    condition: str
    required_action: RequiredAction

    @property
    def permitted_identifiers(self) -> frozenset[str] | None:
        """None means the retained record may keep its identifiers."""

        if self.required_action is RequiredAction.REDACT:
            return REDACT_PERMITTED
        if self.required_action is RequiredAction.ANONYMIZE:
            return ANONYMIZE_PERMITTED
        if self.required_action is RequiredAction.DELETE:
            return frozenset()
        return None

    @property
    def blocks_restore(self) -> bool:
        return self.data_category == "BACKUP_ARCHIVE"


class Rulebook:
    def __init__(self, rules: list[DeletionRule]) -> None:
        self.rules = tuple(rules)
        self._by_category = {rule.data_category: rule for rule in rules}

    def rule_for(self, data_category: str) -> DeletionRule | None:
        return self._by_category.get(data_category)

    def categories(self) -> tuple[str, ...]:
        return tuple(rule.data_category for rule in self.rules)


def load_rulebook(path: str | Path) -> Rulebook:
    rules: list[DeletionRule] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        expected = ["rule_id", "data_category", "condition", "required_action"]
        if reader.fieldnames is None or list(reader.fieldnames) != expected:
            raise ValueError(
                "deletion_rules.csv must have columns "
                + ",".join(expected)
            )
        for line_no, row in enumerate(reader, start=2):
            action_text = (row.get("required_action") or "").strip()
            try:
                action = RequiredAction(action_text)
            except ValueError as exc:
                raise ValueError(
                    f"line {line_no}: required_action {action_text!r} is not "
                    "DELETE, REDACT, ANONYMIZE, or RETAIN"
                ) from exc
            category = (row.get("data_category") or "").strip()
            if not category:
                raise ValueError(f"line {line_no}: data_category is empty")
            rules.append(
                DeletionRule(
                    rule_id=(row.get("rule_id") or "").strip(),
                    data_category=category,
                    condition=(row.get("condition") or "").strip(),
                    required_action=action,
                )
            )
    if not rules:
        raise ValueError(f"no rules found in {path}")
    return Rulebook(rules)
