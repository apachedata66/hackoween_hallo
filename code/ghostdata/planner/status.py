"""Named checks for the four completion conditions, plus request authorization."""

from __future__ import annotations

from enum import Enum

from ghostdata.policy.engine import Assessment


class Authorization(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    NOT_AUTHORIZED = "NOT_AUTHORIZED"
    UNCLEAR = "UNCLEAR"


# Strong signals that the person asked for deletion. Matched as substrings, lowercased.
_DELETE_MARKERS = (
    "delet",
    "eras",
    "erase",
    "erasure",
    "remove my",
    "remove the profile",
    "remove any",
    "close my account",
    "close this account",
    "close the account",
    "closed my account",
    "supprim",
    "elimin",
    "exclus",
    "apagar",
    "borrar",
    "löschen",
    "loesch",
    "削除",
    "cancel my account",
    "right to be forgotten",
)

# Requests that are not deletion, used only when no deletion marker is present.
_NON_DELETE_MARKERS = (
    "unsubscribe",
    "opt out",
    "opt-out",
    "stop marketing",
    "marketing email",
    "do not delete",
    "don't delete",
    "do not erase",
    "access my data",
    "copy of my data",
    "what data do you",
    "correct my",
    "update my address",
    "change my name",
    "change my email",
)


def classify_request(request_text: str) -> tuple[Authorization, str]:
    """Decide whether the text authorizes deletion.

    Unclear text is not treated as NOT_APPLICABLE. The caller records a warning
    and still audits, because a missed deletion is worse than a review flag.
    """

    text = (request_text or "").strip().lower()
    if not text:
        return Authorization.UNCLEAR, "request_text is empty"
    if any(marker in text for marker in _DELETE_MARKERS):
        return Authorization.AUTHORIZED, "the request asks for deletion"
    if any(marker in text for marker in _NON_DELETE_MARKERS):
        return (
            Authorization.NOT_AUTHORIZED,
            "the request asks for something other than deletion",
        )
    return Authorization.UNCLEAR, "request_text does not clearly authorize deletion"


def copies_have_required_treatment(assessments: list[Assessment]) -> bool:
    return all(item.violation != "treatment" for item in assessments if item.include)


def no_active_recreation_path(assessments: list[Assessment]) -> bool:
    return all(item.violation not in {"flow", "restore"} for item in assessments if item.include)


def retained_identifiers_permitted(assessments: list[Assessment]) -> bool:
    return all(item.violation != "identifiers" for item in assessments if item.include)


def required_records_available(assessments: list[Assessment]) -> bool:
    return all(item.violation != "missing_retain" for item in assessments if item.include)


def all_four_conditions(assessments: list[Assessment]) -> bool:
    return (
        copies_have_required_treatment(assessments)
        and no_active_recreation_path(assessments)
        and retained_identifiers_permitted(assessments)
        and required_records_available(assessments)
    )
