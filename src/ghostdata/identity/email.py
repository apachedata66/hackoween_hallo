"""Email normalisation and hashing helpers (task A3).

One rule set for the whole pipeline (docs/DECISIONS.md):
  * compare emails lower-cased and whitespace-stripped;
  * ``plus``-tagging is only ever a *fallback* match key - we never silently
    merge two different addresses;
  * ``email_hash`` in the data is SHA-256 of the normalised email (D6).
"""

from __future__ import annotations

import hashlib
import re


def normalize_email(value: str) -> str:
    """Lower-case and strip an email address."""
    return (value or "").strip().lower()


def plus_stripped(value: str) -> str:
    """Drop a ``+tag`` from the local part (``a+news@x.com`` -> ``a@x.com``).

    Returns the input unchanged when it is not a usable address.
    """
    normalized = normalize_email(value)
    local, sep, domain = normalized.partition("@")
    if not sep or not local or not domain:
        return normalized
    if "+" not in local:
        return normalized
    base = local.split("+", 1)[0]
    return f"{base}@{domain}" if base else normalized


def lookup_keys(value: str) -> list[str]:
    """Match keys for one address, exact first: ``[full, plus-stripped]``."""
    exact = normalize_email(value)
    loose = plus_stripped(exact)
    return [exact] if loose == exact else [exact, loose]


def sha256_hex(value: str) -> str:
    """SHA-256 hex digest of the normalised value (the dataset's hash scheme)."""
    return hashlib.sha256(normalize_email(value).encode("utf-8")).hexdigest()


def contains_identifier(text: str, identifier: str, kind: str = "other") -> bool:
    """Match identifiers without accepting a longer adjacent value.

    Sentence punctuation after an identifier is allowed, while IDs such as
    ``user_010`` do not match ``user_01``.
    """
    haystack = (text or "").casefold()
    needle = (identifier or "").strip().casefold()
    if not haystack or not needle:
        return False
    if kind == "phone":
        digits = re.sub(r"\D", "", needle)
        return len(digits) >= 7 and digits in re.sub(r"\D", "", haystack)
    start = 0
    while (start := haystack.find(needle, start)) >= 0:
        end = start + len(needle)
        prefix = haystack[start - 1] if start else ""
        suffix = haystack[end : end + 2]
        if prefix and (prefix.isalnum() or prefix in "_.+-"):
            start = end
            continue
        if suffix[:1] and (suffix[0].isalnum() or suffix[0] in "_+-"):
            start = end
            continue
        if kind == "email" and suffix.startswith(".") and len(suffix) > 1 and suffix[1].isalnum():
            start = end
            continue
        return True
    return False
