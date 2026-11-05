"""Tolerant parser for the five operational log formats in evidence/."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from ghostdata.loaders.errors import LoaderError
from ghostdata.loaders.evidence_models import classify_category
from ghostdata.loaders.timeutil import parse_optional_timestamp

_TIMESTAMP = re.compile(
    r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)\s*(.*)$"
)
_BRACKET = re.compile(r"\[([^\]]+)\]")
_KV = re.compile(
    r"([A-Za-z_][A-Za-z0-9_.-]*)=(?:\"((?:\\.|[^\"\\])*)\"|'((?:\\.|[^'\\])*)'|([^\s]+))"
)
_RESOURCE = re.compile(
    r"\b(?:account|analytics|support|search|cache|export|backup|tombstone|audit_record|email_delivery|data_flow|connector|marketing|telemetry)_(?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]+\b",
    re.I,
)
_TRACE_CONTEXT_FIELDS = frozenset(
    {
        "account_id",
        "correlation_key",
        "customer_email",
        "customer_id",
        "email",
        "email_hash",
        "lookup_key",
        "match_key",
        "owner_key",
        "phone",
        "scan_key",
        "source",
        "sources",
        "subject_key",
        "subject_ref",
        "user_id",
    }
)


@dataclass(frozen=True)
class LogEvent:
    evidence_id: str
    file_path: str
    line_no: int
    event_time: datetime
    system_id: str
    event_type: str
    resource_id: str
    trace_id: str
    fields: dict[str, str]
    message: str

    @property
    def data_category(self) -> str:
        return classify_category(self.system_id, self.resource_id, self.event_type, self.message)


@dataclass(frozen=True)
class LogParseResult:
    events: list[LogEvent]
    warnings: list[str]
    malformed_lines: int


def _decode_value(value: str) -> str:
    return value.replace(r"\"", '"').replace(r"\\", "\\")


def _pairs(text: str) -> dict[str, str]:
    return {
        match.group(1).casefold(): _decode_value(
            next((x for x in match.groups()[1:] if x is not None), "")
        )
        for match in _KV.finditer(text)
    }


def parse_log_line(
    line: str,
    *,
    evidence_id: str = "",
    file_path: str = "",
    line_no: int = 1,
) -> LogEvent | None:
    """Parse one log line. Lines without a valid timestamp are skipped."""
    matched = _TIMESTAMP.match(line.strip())
    if not matched:
        return None
    event_time = parse_optional_timestamp(matched.group(1), field="log timestamp", path=file_path)
    body = matched.group(2).strip()
    fields = _pairs(body)
    if "|" in body:
        columns = [part.strip() for part in body.split("|")]
        offset = 1 if columns and not columns[0] else 0
        if len(columns) >= offset + 5:
            fields.setdefault("level", columns[offset])
            fields.setdefault("service", columns[offset + 1])
            fields.setdefault("trace_id", columns[offset + 2])
            fields.setdefault("event", columns[offset + 3])
            fields.update(_pairs(" ".join(columns[offset + 4 :])))
    if body.startswith("{"):
        try:
            structured = json.loads(body)
        except json.JSONDecodeError:
            structured = None
        if isinstance(structured, dict):
            fields.update({str(key).casefold(): str(value) for key, value in structured.items()})
    system = (
        fields.get("service")
        or fields.get("system")
        or fields.get("app")
        or fields.get("function")
        or ""
    )
    trace = (
        fields.get("trace")
        or fields.get("trace_id")
        or fields.get("requestid")
        or fields.get("request_id")
        or ""
    )
    event = fields.get("event") or fields.get("event_name") or ""
    message = fields.get("message") or fields.get("msg") or ""

    # Application traces: [LEVEL] [service] [trace] event_name: key="value".
    brackets = _BRACKET.findall(body)
    if brackets:
        if len(brackets) >= 2:
            system = system or brackets[1]
        if len(brackets) >= 3:
            trace = trace or brackets[2]
        before_fields = body.split(":", 1)[0]
        if not event:
            tokens = _BRACKET.sub(" ", before_fields).strip().split()
            if tokens:
                event = tokens[-1]

    # In the structured cloud export, message itself contains a second kv layer.
    if message:
        nested = _pairs(message)
        for key, value in nested.items():
            fields.setdefault(key, value)
        event = event or nested.get("event", "")
        system = system or nested.get("service", "")

    if not system:
        # RFC5424 places the application name after the host in its fixed header.
        syslog = re.match(r"<\d+>\d+\s+\S+\s+(\S+)\s+(\S+)", body)
        if syslog:
            system = syslog.group(1)
            trace = trace or syslog.group(2)

    if not event:
        event_match = re.search(r"\bevent\s*:\s*([A-Za-z0-9_.-]+)", body, re.I)
        if event_match:
            event = event_match.group(1)

    resource = fields.get("resource_id") or fields.get("resource") or ""
    if not resource:
        resource_match = _RESOURCE.search(body)
        resource = resource_match.group(0) if resource_match else ""
    return LogEvent(
        evidence_id=evidence_id,
        file_path=file_path,
        line_no=line_no,
        event_time=event_time,
        system_id=system.strip(),
        event_type=re.sub(r"[^A-Za-z0-9]+", "_", event.strip()).strip("_").upper(),
        resource_id=resource.strip(),
        trace_id=trace.strip(),
        fields=fields,
        message=message or body,
    )


def load_log_text(
    text: str,
    *,
    evidence_id: str = "",
    file_path: str = "",
) -> LogParseResult:
    """Parse a whole log, retaining good lines when others are malformed."""
    events: list[LogEvent] = []
    malformed = 0
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = parse_log_line(
                line, evidence_id=evidence_id, file_path=file_path, line_no=line_no
            )
        except LoaderError:
            malformed += 1
            continue
        if event is None:
            malformed += 1
            continue
        events.append(event)
    # Keep only identity and source context from other events on the same trace.
    # Operational result/state fields must remain event-local: for example, a
    # cache lookup's result="miss" must not override rows="1" on a later read.
    trace_fields: dict[str, dict[str, str]] = {}
    ambiguous_trace_fields: dict[str, set[str]] = {}
    for event in events:
        if event.trace_id:
            context = {
                key: value for key, value in event.fields.items() if key in _TRACE_CONTEXT_FIELDS
            }
            shared = trace_fields.setdefault(event.trace_id, {})
            ambiguous = ambiguous_trace_fields.setdefault(event.trace_id, set())
            for key, value in context.items():
                if key in ambiguous:
                    continue
                previous = shared.get(key)
                if previous is None:
                    shared[key] = value
                elif previous.casefold() != value.casefold():
                    # A trace ID can cover a batch or be reused across subjects.
                    # Do not let the last identity value silently attach every
                    # resource event in that trace to one person.
                    shared.pop(key, None)
                    ambiguous.add(key)
    events = [
        replace(event, fields={**trace_fields.get(event.trace_id, {}), **event.fields})
        if event.trace_id
        else event
        for event in events
    ]
    warnings = []
    if malformed:
        warnings.append(f"{malformed} malformed or timestamp-free log line(s) were skipped.")
    return LogParseResult(events, warnings, malformed)


def load_log_file(path: str | Path, *, evidence_id: str = "") -> LogParseResult:
    """Read and parse one UTF-8 log file, raising a friendly error on I/O failure."""
    file_path = Path(path)
    try:
        text = file_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise LoaderError(f"Could not read log file ({exc})", path=str(file_path)) from None
    except UnicodeDecodeError:
        raise LoaderError("Log file is not readable UTF-8 text", path=str(file_path)) from None
    return load_log_text(text, evidence_id=evidence_id, file_path=str(file_path))


__all__ = ["LogEvent", "LogParseResult", "load_log_file", "load_log_text", "parse_log_line"]
