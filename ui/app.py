"""Local Streamlit review UI; all decisions still come from the shared CLI."""

from __future__ import annotations

import csv
import html
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ghostdata.paths import dataset_dir  # noqa: E402
from ghostdata.contract.csv_io import read_output  # noqa: E402
from ghostdata.explain.explainer import explain_case  # noqa: E402
from ghostdata.validate import validate_file  # noqa: E402


st.set_page_config(page_title="Ghost Data Audit", page_icon="GD", layout="wide")
st.markdown(
    """
    <style>
    :root { --ink:#1c1f23; --muted:#5f6368; --paper:#f7f6f2; --brand:#1d3b47; --link:#2b5c8a; }
    .stApp { background:var(--paper); color:var(--ink); }
    [data-testid="stMetric"] { background:white; border:1px solid #dedbd2; padding:14px; border-radius:8px; }
    .stButton button, .stDownloadButton button { background:var(--brand); color:white; border:0; }
    [data-testid="stCaptionContainer"] { color:var(--muted); }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior:auto !important; animation:none !important; transition:none !important; } }
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


def _reader(pipe, sink: queue.Queue[str]) -> None:
    for line in iter(pipe.readline, ""):
        sink.put(line.rstrip())
    pipe.close()


def _start_run(kind: str, uploaded) -> None:
    st.session_state.pop("output", None)
    data_dir = dataset_dir()
    temp_dir = Path(tempfile.mkdtemp(prefix="ghostdata-ui-"))
    output_path = temp_dir / "output.csv"
    request_path: Path | None = None
    if kind == "Uploaded requests":
        if uploaded is None:
            st.error("Choose a request CSV before starting the audit.")
            return
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
    lines: queue.Queue[str] = queue.Queue()
    thread = threading.Thread(target=_reader, args=(process.stdout, lines), daemon=True)
    thread.start()
    st.session_state.run = {
        "process": process,
        "queue": lines,
        "thread": thread,
        "temp_dir": temp_dir,
        "output": output_path,
        "requests": request_path or data_dir / (
            "sample_deletion_requests.csv" if kind == "Public samples" else "deletion_requests.csv"
        ),
        "logs": [],
        "progress": 0.0,
        "message": "Starting audit",
        "warnings": [],
    }


with st.expander("Start an audit", expanded="output" not in st.session_state):
    mode = st.radio("Input", ["Full dataset", "Public samples", "Uploaded requests"], horizontal=True)
    uploaded_csv = st.file_uploader("Requests CSV", type=["csv"]) if mode == "Uploaded requests" else None
    start_disabled = "run" in st.session_state and st.session_state.run["process"].poll() is None
    if st.button("Start audit", type="primary", disabled=start_disabled):
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
        match = re.search(r"\[(#+-*)\]\s+(\d+)/(\d+)\s+\((\d+)%\)", line)
        if match:
            state["progress"] = int(match.group(4)) / 100
            state["message"] = f"Processed {match.group(2)} of {match.group(3)} requests"
        elif line.startswith("Warning"):
            state["message"] = "Audit is continuing with evidence warnings"
    running = state["process"].poll() is None
    if running:
        st.status(state["message"], state="running", expanded=True)
        st.progress(state["progress"], text=state["message"])
        st.code("\n".join(state["logs"][-12:]), language="text")
    elif not state.get("finished"):
        state["finished"] = True
        if state["process"].returncode != 0:
            st.error("Audit failed. No output is available for export.")
            st.code("\n".join(state["logs"][-24:]), language="text")
        elif not state["output"].is_file():
            st.error("The CLI finished without creating an output file.")
        else:
            issues = validate_file(
                state["output"], requests_path=state["requests"], dataset_dir=dataset_dir()
            )
            if issues:
                st.error("The generated file failed validation. Export is disabled.")
                st.code("\n".join(issue.format() for issue in issues[:20]), language="text")
            else:
                state["output_bytes"] = state["output"].read_bytes()
                state["rows"] = _read_csv(state["output"])
                state["results"] = {item.case_id: item for item in read_output(state["output"])}
                state["request_rows"] = {
                    row["case_id"]: row for row in _read_csv(state["requests"])
                }
                st.session_state.output = state
                st.success(f"Audit complete: {len(state['rows'])} rows passed validation.")
                st.rerun()
    if state["warnings"]:
        with st.expander(f"Evidence warnings ({len(state['warnings'])})"):
            st.code("\n".join(state["warnings"]), language="text")


current_run = st.session_state.get("run")
if current_run and current_run["process"].poll() is None:
    st.fragment(run_every="1s")(show_progress)()
else:
    show_progress()

result = st.session_state.get("output")
if result:
    rows = result["rows"]
    counts = {key: sum(row["deletion_status"] == key for row in rows)
              for key in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE")}
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
            review_rows.append({
                "Case ID": row["case_id"],
                "Status": row["deletion_status"],
                "Audit cutoff": request.get("audit_at", ""),
                "Findings": sum(step["phase"] == "FINDING" for step in steps),
                "Case state": "Action needed" if row["deletion_status"] == "INCOMPLETE" else "No deletion audit" if row["deletion_status"] == "NOT_APPLICABLE" else "Verified",
            })
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
        colors = {"COMPLETE": "#2f6b4f", "INCOMPLETE": "#a8322d", "NOT_APPLICABLE": "#6b7075"}
        color = colors[row["deletion_status"]]
        st.markdown(
            f"<span style='background:{color};color:white;padding:5px 10px;border-radius:999px' "
            f"aria-label='Audit status {html.escape(row['deletion_status'])}'>"
            f"{html.escape(row['deletion_status'])}</span> &nbsp; {html.escape(explanation.headline)}",
            unsafe_allow_html=True,
        )
        st.markdown(f"### {html.escape(case_id)}")
        st.write("Reported status:", request.get("reported_status", "Unavailable"))
        st.write("Audit cutoff:", request.get("audit_at", "Unavailable"))
        st.write("Audit scope:", "No deletion audit" if row["deletion_status"] == "NOT_APPLICABLE" else "Deletion request audited")
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
                display.append({
                    "#": step["step_no"],
                    "System / resource": f"{step['system_id']} / {step['resource_id']}",
                    "Action": step["operation"].replace("_", " ").title(),
                    "State": step["state"],
                    "Evidence reference": step["evidence_id"] or "Future work",
                    "Evidence type": "Current evidence" if step["evidence_id"] else "Proposed action or future check",
                })
            st.dataframe(display, use_container_width=True, hide_index=True)
        with st.expander("Exact output row"):
            st.code(f"{row['case_id']},{row['deletion_status']},{row['steps_json']}", language="csv")
