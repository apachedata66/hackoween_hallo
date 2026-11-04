"""Typed dataset loaders (task A2).

Design rules (playbook A2 / A14):
  * explicit types for every column;
  * one timestamp policy - ISO-8601, ``Z``/naive treated as UTC (DECISIONS D5);
  * whitespace stripped, emails lower-cased;
  * failures raise :class:`LoaderError` with a plain-language message - never
    a raw traceback. The batch runner catches it and records a warning.
"""

from ghostdata.loaders.activity_csv import ActivityEvent, load_activity
from ghostdata.loaders.errors import LoaderError
from ghostdata.loaders.evidence_csv import EvidenceFile, load_evidence_manifest
from ghostdata.loaders.identity_csv import (
    AUDITED_FIELDS,
    IdentityAuditEvent,
    UserIdentity,
    load_identities,
    load_identity_audit,
)
from ghostdata.loaders.policy_csv import ACTIONS, DeletionRule, load_rules
from ghostdata.loaders.requests import REPORTED_STATUSES, DeletionRequest, load_requests
from ghostdata.loaders.tabular import read_csv_rows
from ghostdata.loaders.timeutil import parse_optional_timestamp, parse_timestamp, to_utc_text

__all__ = [
    "ACTIONS",
    "AUDITED_FIELDS",
    "REPORTED_STATUSES",
    "ActivityEvent",
    "DeletionRequest",
    "DeletionRule",
    "EvidenceFile",
    "IdentityAuditEvent",
    "LoaderError",
    "UserIdentity",
    "load_activity",
    "load_evidence_manifest",
    "load_identities",
    "load_identity_audit",
    "load_requests",
    "load_rules",
    "parse_optional_timestamp",
    "parse_timestamp",
    "read_csv_rows",
    "to_utc_text",
]
