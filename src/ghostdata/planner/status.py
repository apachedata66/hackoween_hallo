"""Named checks for the four completion conditions, plus request authorization."""

from __future__ import annotations

from enum import StrEnum

from ghostdata.policy.engine import Assessment


class Authorization(StrEnum):
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
    "promotional emails",
    "remove me from marketing",
    "marketing lists only",
    "do not delete",
    "don't delete",
    "do not erase",
    "access my data",
    "copy of my data",
    "download my account information",
    "portable format",
    "resetting the login",
    "reset the login",
    "reset my login",
    "misspelled",
    "correct it without removing",
    "what data do you",
    "what personal information do you hold",
    "copy of last year's invoices",
    "copy of invoices",
    "leave my profile",
    "change the email address",
    "send me a copy of the information",
    "copy of the information held",
    "correct my",
    "update my address",
    "change my name",
    "change my email",
)

# Negated deletion language must be removed before looking for positive markers:
# words such as "erase" and "delete" also occur in explicit non-deletion asks.
_NEGATED_DELETE_MARKERS = (
    "not asking for deletion",
    "not a request to delete",
    "not a request to erase",
    "not asking to delete",
    "not asking to erase",
    "not requesting deletion",
    "not requesting erasure",
    "do not delete",
    "don't delete",
    "do not erase",
    "don't erase",
    "do not close the account",
    "don't close the account",
    "do not remove",
    "don't remove",
)


def classify_request(request_text: str) -> tuple[Authorization, str]:
    """Decide whether the text authorizes deletion.

    Unclear text is not treated as NOT_APPLICABLE. The caller records a warning
    and still audits, because a missed deletion is worse than a review flag.
    """

    text = (request_text or "").strip().lower()
    if not text:
        return Authorization.UNCLEAR, "request_text is empty"

    negated = [marker for marker in _NEGATED_DELETE_MARKERS if marker in text]
    positive_text = text
    for marker in negated:
        positive_text = positive_text.replace(marker, " ")
    has_positive_deletion = any(marker in positive_text for marker in _DELETE_MARKERS)
    if negated and has_positive_deletion:
        return Authorization.UNCLEAR, "the request contains conflicting deletion instructions"
    if negated:
        return (
            Authorization.NOT_AUTHORIZED,
            "the request explicitly says not to delete or asks for a different action",
        )
    if has_positive_deletion:
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
