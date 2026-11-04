"""Identity resolution (task A3)."""

from ghostdata.identity.email import (
    contains_identifier,
    lookup_keys,
    normalize_email,
    plus_stripped,
    sha256_hex,
)
from ghostdata.identity.resolver import IdentityIndex, resolve_identity

__all__ = [
    "IdentityIndex",
    "contains_identifier",
    "lookup_keys",
    "normalize_email",
    "plus_stripped",
    "resolve_identity",
    "sha256_hex",
]
