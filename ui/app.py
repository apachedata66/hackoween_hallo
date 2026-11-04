"""Local Streamlit review UI; all decisions still come from the shared CLI."""

from __future__ import annotations

import atexit
import csv
import html
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ghostdata.contract.csv_io import read_output  # noqa: E402
from ghostdata.explain.explainer import explain_case  # noqa: E402
from ghostdata.identity.resolver import resolve_identity  # noqa: E402
from ghostdata.loaders.errors import LoaderError  # noqa: E402
from ghostdata.loaders.identity_csv import load_identities, load_identity_audit  # noqa: E402
from ghostdata.loaders.timeutil import parse_timestamp  # noqa: E402
from ghostdata.paths import dataset_dir  # noqa: E402
from ghostdata.validate import validate_file  # noqa: E402

st.set_page_config(page_title="Ghost Data Audit", page_icon="GD", layout="wide")
st.markdown(
    """
    <style>
    :root {
      color-scheme:light; --ink:#1C1F23; --muted:#5F6368; --paper:#F7F6F2;
      --brand:#1D3B47; --link:#2B5C8A; --border:#E2DFD6;
    }
    [data-testid="stAppViewContainer"] {
      --text-color:var(--ink); --background-color:var(--paper);
      --secondary-background-color:#ffffff; --primary-color:var(--brand);
    }
    [data-testid="stAppViewContainer"], [data-testid="stMain"] {
      background:var(--paper); color:var(--ink);
    }
    [data-testid="stAppViewContainer"] { font-family:'IBM Plex Sans', Arial, sans-serif; }
    [data-testid="stHeader"] { background:var(--paper); }
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
    [data-testid="stRadio"] label, [data-testid="stWidgetLabel"] p,
    [data-testid="stExpander"] summary { color:var(--ink) !important; }
    [data-testid="stExpander"] summary { background:#ffffff; }
    [data-testid="stMetric"] {
      background:white; border:1px solid var(--border); padding:12px 16px;
      border-radius:2px;
    }
    .stButton button, .stDownloadButton button {
      background:var(--brand); color:white; border:0; border-radius:2px;
    }
    [data-testid="stCaptionContainer"] { color:var(--muted); }
    .run-indicator {
      display:inline-flex; align-items:center; gap:8px; color:var(--brand);
      font-weight:600;
    }
    .run-indicator::before {
      content:""; width:8px; height:8px; border-radius:50%;
      background:var(--brand); animation:run-pulse 1.8s ease-in-out infinite;
    }
    .status-chip {
      display:inline-flex; align-items:center; gap:6px; padding:4px 9px;
      border:1px solid currentColor; border-radius:3px; font-weight:600;
    }
    .status-complete { color:#2F6B4F; background:#E1EFE7; }
    .status-incomplete { color:#A8322D; background:#F6E3E1; }
    .status-na { color:#6B7075; background:#ECEDEE; }
    code, pre, [data-testid="stCode"] {
      font-family:'IBM Plex Mono', ui-monospace, monospace;
    }
    @keyframes run-pulse { 50% { opacity:.42; } }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        scroll-behavior:auto !important; animation:none !important;
        transition:none !important;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Ghost Data deletion audit")
st.caption("Evidence-backed results for privacy operations. The audit engine owns every verdict.")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _masked_email(value: str) -> str:
    return "••••••" if value else "Unavailable"


def _as_datetime(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _at_or_before(value: str, cutoff: str) -> bool:
    timestamp = _as_datetime(value)
    limit = _as_datetime(cutoff)
    return timestamp is not None and limit is not None and timestamp <= limit


@st.cache_data(show_spinner=False)
def _case_identity_values(
    data_path: str, case_id: str, email: str, requested_at: str, audit_at: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return subject identifiers to locate and mask without exposing them in the UI."""
    base = Path(data_path)
    try:
        cutoff = _as_datetime(audit_at)
        requested = parse_timestamp(
            requested_at, field="requested_at", path=str(base / "deletion_requests.csv")
        )
        identities = load_identities(base / "user_identities.csv")
        audit_events = load_identity_audit(base / "user_audit_log.csv")
        if cutoff is not None:
            identities = [item for item in identities if item.updated_at.astimezone(UTC) <= cutoff]
            audit_events = [
                item for item in audit_events if item.event_time.astimezone(UTC) <= cutoff
            ]
        identity = resolve_identity(
            case_id,
            email,
            requested,
            identities,
            audit_events,
        )
    except (LoaderError, OSError, ValueError):
        return ((email,) if email else (), ())

    direct = list(identity.emails_current + identity.emails_historical + identity.email_hashes)
    other = identity.other_identifiers
    direct.extend(str(other[key]) for key in ("name", "phone") if other.get(key))
    direct.extend(str(value) for value in other.get("phone_history", []) if value)
    return tuple(dict.fromkeys(value for value in direct if value)), tuple(identity.user_ids)


@st.cache_data(show_spinner=False)
def _all_direct_identifiers(data_path: str) -> tuple[str, ...]:
    """Load participant-facing identity values so excerpts can mask decoys too."""
    base = Path(data_path)
    values: set[str] = set()
    for user in load_identities(base / "user_identities.csv"):
        values.update(
            value for value in (user.name, user.email, user.phone, user.email_hash) if value
        )
    for event in load_identity_audit(base / "user_audit_log.csv"):
        if event.field_name in {"email", "email_hash", "phone"}:
            values.update(
                value.strip() for value in (event.old_value, event.new_value) if value.strip()
            )
    return tuple(sorted(values, key=lambda item: (-len(item), item.casefold())))


@st.cache_data(show_spinner=False)
def _evidence_catalog(data_path: str) -> tuple[dict[str, dict[str, str]], ...]:
    base = Path(data_path)
    files = {row["file_id"]: row for row in _read_csv(base / "evidence_files.csv")}
    activities = {row["activity_id"]: row for row in _read_csv(base / "system_activity.csv")}
    audits = {row["audit_id"]: row for row in _read_csv(base / "user_audit_log.csv")}
    return files, activities, audits


def _redact_excerpt(text: str, direct_identifiers: tuple[str, ...]) -> str:
    redacted = text
    for value in direct_identifiers:
        if len(value) < 3:
            continue
        escaped = re.escape(value)
        if value[0].isalnum():
            escaped = rf"(?<!\w){escaped}"
        if value[-1].isalnum():
            escaped += r"(?!\w)"
        redacted = re.sub(escaped, "[redacted]", redacted, flags=re.IGNORECASE)
    redacted = re.sub(
        r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[email redacted]", redacted
    )
    sensitive_field = re.compile(
        r"(?i)([\"']?(?:full_name|customer_name|requester_name|owner_name|recipient_name|"
        r"name|email|phone|email_hash)[\"']?\s*[:=]\s*)"
        r"([\"'][^\"']*[\"']|[^,\r\n;|}\]]+)"
    )
    return sensitive_field.sub(r"\1[redacted]", redacted)


def _file_excerpt(
    path: Path,
    selectors: tuple[str, ...],
    direct_identifiers: tuple[str, ...],
    cutoff: str,
) -> str:
    try:
        if path.stat().st_size > 2_000_000:
            return "This source is too large for an inline preview."
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path), strict=False)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif suffix in {".txt", ".log", ".json", ".sql", ".csv", ".md"}:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if suffix == ".json":
                try:
                    text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
                except ValueError:
                    pass
        else:
            return "Inline text preview is unavailable for this file type."
    except (OSError, ValueError, ImportError):
        return "The source could not be read for inline preview."

    lines = text.splitlines()
    terms = tuple(term.casefold() for term in selectors if term and len(term) > 2)
    hits = [
        index for index, line in enumerate(lines) if any(term in line.casefold() for term in terms)
    ]
    if not hits:
        return "No matching subject or resource line was found; source content is hidden."
    limit = _as_datetime(cutoff)
    timestamp_pattern = re.compile(
        r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
        r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b"
    )
    for hit in hits:
        excerpt = "\n".join(lines[max(0, hit - 2) : hit + 3])
        timestamps = timestamp_pattern.findall(excerpt)
        if limit is None or any(
            (parsed := _as_datetime(value)) is None or parsed > limit for value in timestamps
        ):
            continue
        return _redact_excerpt(excerpt[:1800], direct_identifiers)
    return "Matching source lines include timestamps after the audit cutoff and are hidden."


def _show_evidence_detail(
    evidence_id: str,
    request: dict[str, str],
    step: dict[str, object],
    data_path: Path,
    subject_values: tuple[str, ...],
    user_ids: tuple[str, ...],
) -> None:
    files, activities, audits = _evidence_catalog(str(data_path))
    cutoff = request.get("audit_at", "")
    if evidence_id in activities:
        event = activities[evidence_id]
        if not _at_or_before(event.get("event_time", ""), cutoff):
            st.caption("This event is after the audit cutoff and is hidden from the verdict view.")
            return
        st.caption("Operational activity · claim, not proof of the resulting data state")
        st.write("Event time", event.get("event_time", "Unavailable"))
        st.write("Event", event.get("event_type", "Unavailable"))
        st.write(
            "System / resource",
            f"{event.get('target_system', '')} / {event.get('resource_id', '')}",
        )
        st.write("Reported result (claim)", event.get("reported_result", "Unavailable"))
        details = _redact_excerpt(event.get("details", ""), _all_direct_identifiers(str(data_path)))
        st.code(details, language="text")
        return

    if evidence_id in audits:
        event = audits[evidence_id]
        if not _at_or_before(event.get("event_time", ""), cutoff):
            st.caption("This identity event is after the audit cutoff and is hidden.")
            return
        st.caption("Identity history · source row supporting an identity link")
        st.write("Event time", event.get("event_time", "Unavailable"))
        st.write("Changed field", event.get("field_name", "Unavailable"))
        st.write("Old value", "[masked]")
        st.write("New value", "[masked]")
        return

    entry = files.get(evidence_id)
    if not entry:
        st.caption("This reference could not be resolved in the participant-facing evidence index.")
        return
    captured_at = entry.get("captured_at", "")
    if not _at_or_before(captured_at, cutoff):
        st.caption(
            "This file was captured after the audit cutoff and is hidden from the verdict view."
        )
        return
    st.caption("Source file · captured evidence; displayed content is redacted")
    st.write("Captured at", captured_at)
    st.write("Origin", entry.get("origin", "Unavailable"))
    st.code(entry.get("file_path", "Unavailable"), language="text")
    if not st.checkbox(
        "Show matching redacted excerpt", key=f"preview_{request['case_id']}_{evidence_id}"
    ):
        return
    base = data_path.resolve()
    path = (base / entry.get("file_path", "")).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        st.caption("The evidence path is outside the dataset and cannot be opened.")
        return
    selectors = subject_values + user_ids + (str(step.get("resource_id", "")),)
    st.code(
        _file_excerpt(
            path,
            selectors,
            _all_direct_identifiers(str(data_path)),
            request.get("audit_at", ""),
        ),
        language="text",
    )


def _reader(pipe, sink: queue.Queue[str]) -> None:
    for line in iter(pipe.readline, ""):
        sink.put(line.rstrip())
    pipe.close()


def _remove_temp(state: dict) -> None:
    temp_dir = state.get("temp_dir")
    if temp_dir:
        shutil.rmtree(temp_dir, ignore_errors=True)
        state["temp_dir"] = None


def _stop_child_and_remove_temp(state: dict) -> None:
    process = state.get("process")
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    _remove_temp(state)


def _start_run(kind: str, uploaded) -> None:
    st.session_state.pop("output", None)
    data_dir = dataset_dir()
    if kind == "Uploaded requests" and uploaded is None:
        st.error("Choose a request CSV before starting the audit.")
        return
    temp_dir = Path(tempfile.mkdtemp(prefix="ghostdata-ui-"))
    output_path = temp_dir / "output.csv"
    request_path: Path | None = None
    try:
        review_report = ROOT / "evaluation" / "manual_review.md"
        previous_review_mtime = (
            review_report.stat().st_mtime_ns if review_report.is_file() else None
        )
        if kind == "Uploaded requests":
            request_path = temp_dir / "requests.csv"
            request_path.write_bytes(uploaded.getvalue())

        command = [sys.executable, str(ROOT / "code" / "main.py"), "run", "--out", str(output_path)]
        if kind == "Public samples":
            command.append("--samples")
        elif request_path:
            command.extend(["--input", str(request_path)])

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        st.error(f"Could not start the audit: {exc}")
        return
    lines: queue.Queue[str] = queue.Queue()
    thread = threading.Thread(target=_reader, args=(process.stdout, lines), daemon=True)
    thread.start()
    state = {
        "process": process,
        "queue": lines,
        "thread": thread,
        "temp_dir": temp_dir,
        "output": output_path,
        "requests": request_path
        or data_dir
        / ("sample_deletion_requests.csv" if kind == "Public samples" else "deletion_requests.csv"),
        "logs": [],
        "progress": 0.0,
        "processed": None,
        "total": None,
        "eta_seconds": None,
        "message": "Audit process started; waiting for the first progress update",
        "started_at": time.monotonic(),
        "previous_review_mtime": previous_review_mtime,
        "warnings": [],
    }
    st.session_state.run = state
    atexit.register(_stop_child_and_remove_temp, state)


with st.expander("Start an audit", expanded="output" not in st.session_state):
    mode = st.radio(
        "Input", ["Full dataset", "Public samples", "Uploaded requests"], horizontal=True
    )
    uploaded_csv = (
        st.file_uploader("Requests CSV", type=["csv"]) if mode == "Uploaded requests" else None
    )
    start_disabled = "run" in st.session_state and st.session_state.run["process"].poll() is None
    start_type = "secondary" if "output" in st.session_state else "primary"
    if st.button("Start audit", type=start_type, disabled=start_disabled):
        _start_run(mode, uploaded_csv)


def show_progress() -> None:
    state = st.session_state.get("run")
    if not state:
        return
    while True:
        try:
            line = state["queue"].get_nowait()
        except queue.Empty:
            break
        state["logs"].append(line)
        if line.startswith("Warning"):
            state["warnings"].append(line)
        match = re.search(
            r"\[(#+-*)\]\s+(\d+)/(\d+)\s+\((\d+)%\);\s+"
            r"elapsed\s+([\d.]+)s;\s+ETA\s+([\d.]+)s",
            line,
        )
        if match:
            state["progress"] = int(match.group(4)) / 100
            state["processed"] = int(match.group(2))
            state["total"] = int(match.group(3))
            state["eta_seconds"] = float(match.group(6))
            state["message"] = f"Processing requests: {match.group(2)} of {match.group(3)}"
        elif line.startswith("Warning"):
            state["message"] = "Processing continues; evidence warnings need review"
    running = state["process"].poll() is None
    if running:
        elapsed = max(0, int(time.monotonic() - state["started_at"]))
        elapsed_label = f"{elapsed // 60:02d}:{elapsed % 60:02d}"
        st.markdown(
            f"<span class='run-indicator' role='status' aria-label='Audit running'>"
            f"{html.escape(state['message'])}</span> &nbsp; · &nbsp; "
            f"Elapsed {elapsed_label}",
            unsafe_allow_html=True,
        )
        if state["processed"] is not None:
            eta = int(state["eta_seconds"] or 0)
            st.caption(
                f"{state['processed']:,} of {state['total']:,} requests · "
                f"estimated {eta // 60:02d}:{eta % 60:02d} remaining · "
                f"{len(state['warnings'])} evidence warning(s)"
            )
        st.status(state["message"], state="running", expanded=True)
        if state["processed"] is not None:
            st.progress(state["progress"], text=state["message"])
        else:
            st.caption("Waiting for the runner's first progress update…")
        st.code("\n".join(state["logs"][-12:]), language="text")
    elif not state.get("finished"):
        state["finished"] = True
        try:
            if state["process"].returncode != 0:
                state["outcome"] = "failed"
                state["failure_message"] = (
                    "Audit stopped for evidence review. No output is available for export."
                )
                review_report = ROOT / "evaluation" / "manual_review.md"
                review_mtime = review_report.stat().st_mtime_ns if review_report.is_file() else None
                if review_mtime is not None and review_mtime != state["previous_review_mtime"]:
                    state["review_report"] = review_report.read_text(encoding="utf-8")
                state["failure_log"] = "\n".join(state["logs"][-24:])
            elif not state["output"].is_file():
                state["outcome"] = "failed"
                state["failure_message"] = "The CLI finished without creating an output file."
            else:
                issues = validate_file(
                    state["output"], requests_path=state["requests"], dataset_dir=dataset_dir()
                )
                if issues:
                    state["outcome"] = "failed"
                    state["failure_message"] = (
                        "The generated file failed validation. Export is disabled."
                    )
                    state["failure_log"] = "\n".join(issue.format() for issue in issues[:20])
                else:
                    state["outcome"] = "complete"
                    state["output_bytes"] = state["output"].read_bytes()
                    state["rows"] = _read_csv(state["output"])
                    state["results"] = {item.case_id: item for item in read_output(state["output"])}
                    state["request_rows"] = {
                        row["case_id"]: row for row in _read_csv(state["requests"])
                    }
                    st.session_state.output = state
        except (OSError, ValueError) as exc:
            state["outcome"] = "failed"
            state["failure_message"] = f"Run review failed safely: {exc}"
        finally:
            _remove_temp(state)
            state["output"] = None
            state["requests"] = None
        st.rerun(scope="app")
    if state["warnings"]:
        with st.expander(f"Evidence warnings ({len(state['warnings'])})"):
            st.code("\n".join(state["warnings"]), language="text")


current_run = st.session_state.get("run")
if current_run and current_run["process"].poll() is None:
    st.fragment(run_every="1s")(show_progress)()
else:
    show_progress()

result = st.session_state.get("output")
run_state = st.session_state.get("run")
if run_state and run_state.get("outcome") == "failed":
    st.error(run_state["failure_message"])
    if run_state.get("review_report"):
        st.caption("Manual review report")
        st.markdown(run_state["review_report"])
    if run_state.get("failure_log"):
        with st.expander("Run details"):
            st.code(run_state["failure_log"], language="text")
elif run_state and run_state.get("outcome") == "complete":
    st.success(f"Audit complete: {len(run_state['rows'])} rows passed validation.")
if result:
    rows = result["rows"]
    counts = {
        key: sum(row["deletion_status"] == key for row in rows)
        for key in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")
    }
    metric_cols = st.columns(3)
    for col, (label, count) in zip(metric_cols, counts.items(), strict=True):
        col.metric(label.replace("_", " "), count)

    st.download_button(
        "Download validated output.csv",
        data=result["output_bytes"],
        file_name="output.csv",
        mime="text/csv",
        type="primary",
    )
    st.subheader("Case review")
    search_col, filter_col = st.columns([3, 1])
    query = search_col.text_input("Search by case ID or email", placeholder="Search cases")
    status_filter = filter_col.selectbox(
        "Status", ["All", "COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"]
    )
    review_rows = []
    for row in rows:
        request = result["request_rows"].get(row["case_id"], {})
        searchable = f"{row['case_id']} {request.get('email', '')}".lower()
        if query.lower() in searchable and (
            status_filter == "All" or row["deletion_status"] == status_filter
        ):
            steps = json.loads(row["steps_json"])
            review_rows.append(
                {
                    "Case ID": row["case_id"],
                    "Status": row["deletion_status"],
                    "Audit cutoff": request.get("audit_at", ""),
                    "Findings": sum(step["phase"] == "FINDING" for step in steps),
                    "Case state": "Action needed"
                    if row["deletion_status"] == "INCOMPLETE"
                    else "No deletion audit"
                    if row["deletion_status"] == "NOT_APPLICABLE"
                    else "Verified",
                }
            )
    st.dataframe(review_rows, use_container_width=True, hide_index=True)
    case_ids = [row["Case ID"] for row in review_rows]
    if case_ids:
        case_id = st.selectbox("Open a case", case_ids)
        row = next(row for row in rows if row["case_id"] == case_id)
        request = result["request_rows"].get(case_id, {})
        steps = json.loads(row["steps_json"])
        show_raw = st.checkbox("Show raw identifiers", value=False)
        email = request.get("email", "")
        explanation = explain_case(result["results"][case_id], request)
        chips = {
            "COMPLETE": ("✓", "status-complete"),
            "INCOMPLETE": ("!", "status-incomplete"),
            "NOT_APPLICABLE": ("–", "status-na"),
        }
        icon, chip_class = chips[row["deletion_status"]]
        st.markdown(
            f"<span class='status-chip {chip_class}' role='status'>"
            f"<span aria-hidden='true'>{icon}</span> {html.escape(row['deletion_status'])}</span>"
            f" &nbsp; {html.escape(explanation.headline)}",
            unsafe_allow_html=True,
        )
        st.markdown(f"### {html.escape(case_id)}")
        st.write("Reported status:", request.get("reported_status", "Unavailable"))
        st.write("Audit cutoff:", request.get("audit_at", "Unavailable"))
        st.write(
            "Audit scope:",
            "No deletion audit"
            if row["deletion_status"] == "NOT_APPLICABLE"
            else "Deletion request audited",
        )
        st.write("Request email:", email if show_raw else _masked_email(email))
        with st.expander("Request context"):
            if show_raw:
                st.write(request.get("request_text", "Unavailable"))
            else:
                st.caption("Hidden by default because request text can contain direct identifiers.")
        with st.expander("Audit timeline"):
            for event in explanation.timeline:
                st.write(event)
        for reason in explanation.bullet_reasons:
            st.write(f"• {reason}")
        for phase in ("FINDING", "REMEDIATION", "VERIFICATION"):
            phase_steps = [step for step in steps if step["phase"] == phase]
            if not phase_steps:
                continue
            st.markdown(f"#### {phase.title()}")
            display = []
            for step in phase_steps:
                display.append(
                    {
                        "#": step["step_no"],
                        "System / resource": f"{step['system_id']} / {step['resource_id']}",
                        "Action": step["operation"].replace("_", " ").title(),
                        "State": step["state"],
                        "Evidence reference": step["evidence_id"] or "Future work",
                        "Evidence type": "Current evidence"
                        if step["evidence_id"]
                        else "Proposed action or future check",
                    }
                )
            st.dataframe(display, use_container_width=True, hide_index=True)
        evidence_ids = sorted({step["evidence_id"] for step in steps if step["evidence_id"]})
        if evidence_ids:
            with st.expander(f"Evidence details ({len(evidence_ids)} references)"):
                selected_evidence = st.selectbox(
                    "Evidence reference",
                    evidence_ids,
                    key=f"evidence_ref_{case_id}",
                )
                selected_step = next(
                    step for step in steps if step["evidence_id"] == selected_evidence
                )
                subject_values, user_ids = _case_identity_values(
                    str(dataset_dir()),
                    case_id,
                    str(request.get("email", "")),
                    str(request.get("requested_at", "")),
                    str(request.get("audit_at", "")),
                )
                _show_evidence_detail(
                    selected_evidence,
                    request,
                    selected_step,
                    dataset_dir(),
                    subject_values,
                    user_ids,
                )
        with st.expander("Exact output row"):
            st.code(
                f"{row['case_id']},{row['deletion_status']},{row['steps_json']}", language="csv"
            )
