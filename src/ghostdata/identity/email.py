"""Email normalisation and hashing helpers (task A3).

One rule set for the whole pipeline (docs/DECISIONS.md):
  * compare emails lower-cased and whitespace-stripped;
  * ``plus``-tagging is only ever a *fallback* match key - we never silently
    merge two different addresses;
  * ``email_hash`` in the data is SHA-256 of the normalised email (D6).
"""

from __future__ import annotations

import hashlib


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
