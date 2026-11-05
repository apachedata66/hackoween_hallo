"""Local-only API that runs and presents the same validated CLI output."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ghostdata.paths import REPO_ROOT, dataset_dir
from ghostdata.validate import validate_file

app = FastAPI(title="Ghost Data Review", docs_url=None, redoc_url=None)
_cors_origins = [
    origin.strip()
    for origin in os.environ.get("GHOSTDATA_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
_runs: dict[str, AuditRun] = {}
_lock = threading.Lock()
_email = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_phone = re.compile(r"(?<!\w)(?:\+?\d[\d .()/-]{7,}\d)(?!\w)")


def _mask(value: str) -> str:
    value = _email.sub(
        lambda match: match.group(0)[:1] + "•••@" + match.group(0).split("@", 1)[1], value
    )
    return _phone.sub("••••••••", value)


def _identifiers_for_request(root: Path, email: str) -> list[str]:
    identifiers = [email]
    identities_path = root / "user_identities.csv"
    audits_path = root / "user_audit_log.csv"
    try:
        identities = _read_csv(identities_path)
        audits = _read_csv(audits_path)
    except OSError:
        return identifiers
    normalized_email = email.casefold()
    user_ids = {
        row.get("user_id", "")
        for row in identities
        if row.get("email", "").casefold() == normalized_email
    }
    for event in audits:
        if normalized_email in {
            event.get("old_value", "").casefold(),
            event.get("new_value", "").casefold(),
        }:
            user_ids.add(event.get("user_id", ""))
    for identity in identities:
        if identity.get("user_id") in user_ids:
            identifiers.extend(
                identity.get(key, "") for key in ("name", "email", "phone", "email_hash")
            )
    for event in audits:
        if event.get("user_id") in user_ids:
            identifiers.extend((event.get("old_value", ""), event.get("new_value", "")))
    return sorted({value for value in identifiers if value}, key=len, reverse=True)


def _redact_identifiers(value: str, identifiers: list[str]) -> str:
    for identifier in identifiers:
        value = re.sub(re.escape(identifier), "[redacted]", value, flags=re.IGNORECASE)
    return _mask(value)


def _at_or_before(timestamp: str, cutoff: str) -> bool:
    try:
        left = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        right = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
        if left.tzinfo is None and right.tzinfo is not None:
            left = left.replace(tzinfo=right.tzinfo)
        if right.tzinfo is None and left.tzinfo is not None:
            right = right.replace(tzinfo=left.tzinfo)
        return left <= right
    except (TypeError, ValueError):
        return False


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"COMPLETE": 0, "INCOMPLETE": 0, "NOT_APPLICABLE": 0}
    for row in rows:
        status = str(row.get("deletion_status", ""))
        if status in counts:
            counts[status] += 1
    return counts


@dataclass
class AuditRun:
    run_id: str
    mode: str
    input_path: Path
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    started_monotonic: float = field(default_factory=time.monotonic)
    state: str = "queued"
    stage: str = "Preparing audit"
    processed: int = 0
    total: int = 0
    warnings: list[str] = field(default_factory=list)
    error: str = ""
    output_bytes: bytes = b""
    rows: list[dict[str, Any]] = field(default_factory=list)
    requests: dict[str, dict[str, str]] = field(default_factory=dict)
    validation_issues: list[str] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        elapsed = time.monotonic() - self.started_monotonic
        eta = (elapsed * (self.total - self.processed) / self.processed) if self.processed else None
        return {
            "run_id": self.run_id,
            "mode": self.mode,
            "state": self.state,
            "stage": self.stage,
            "processed": self.processed,
            "total": self.total,
            "elapsed_seconds": round(elapsed, 1),
            "eta_seconds": round(eta, 1) if eta is not None and self.state == "running" else None,
            "warning_count": len(self.warnings),
            "warnings": self.warnings[-20:],
            "error": self.error,
            "counts": _status_counts(self.rows),
            "export_ready": self.state == "complete" and not self.validation_issues,
            "validation_issues": self.validation_issues,
            "started_at": self.started_at,
        }


class RunRequest(BaseModel):
    mode: str = Field(default="full", pattern="^(full|samples|saved)$")


class SearchRequest(BaseModel):
    query: str = Field(default="", max_length=120)


@app.get("/api/health")
def health() -> dict[str, Any]:
    root = dataset_dir()
    required = [
        "deletion_requests.csv",
        "sample_deletion_requests.csv",
        "user_identities.csv",
        "user_audit_log.csv",
        "system_activity.csv",
        "deletion_rules.csv",
        "evidence_files.csv",
        "evidence",
    ]
    present = {
        name: (root / name).is_dir() if name == "evidence" else (root / name).is_file()
        for name in required
    }
    request_file = root / "deletion_requests.csv"
    sample_file = root / "sample_deletion_requests.csv"
    request_count = len(_read_csv(request_file)) if request_file.is_file() else 0
    sample_count = len(_read_csv(sample_file)) if sample_file.is_file() else 0
    return {
        "ready": all(present.values()) and request_count > 0 and sample_count > 0,
        "dataset_label": root.name if root.exists() else "Dataset not found",
        "files": present,
        "request_count": request_count,
        "sample_count": sample_count,
    }


def _execute(run: AuditRun) -> None:
    output_path: Path | None = None
    try:
        run.state = "running"
        run.stage = "Reading participant-facing evidence"
        run.requests = {row["case_id"]: row for row in _read_csv(run.input_path)}
        run.total = len(run.requests)
        output_path = Path(tempfile.gettempdir()) / f"ghostdata-{run.run_id}.csv"
        command = [
            sys.executable,
            str(REPO_ROOT / "code" / "main.py"),
            "run",
            "--input",
            str(run.input_path),
            "--out",
            str(output_path),
            "--workers",
            "1",
        ]
        process = subprocess.Popen(
            command,
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None and process.stderr is not None

        def read_stderr() -> None:
            for line in process.stderr:
                cleaned = line.strip()
                if cleaned.startswith("Warning "):
                    run.warnings.append(_mask(cleaned)[:300])
                elif cleaned.startswith("Stopped safely:"):
                    run.stage = "Evidence review required"
                    run.warnings.append(_mask(cleaned)[:300])

        error_reader = threading.Thread(target=read_stderr, daemon=True)
        error_reader.start()
        progress_re = re.compile(r"(\d+)/(\d+) \((\d+)%\)")
        for line in process.stdout:
            cleaned = line.strip()
            match = progress_re.search(cleaned)
            if match:
                run.processed = int(match.group(1))
                run.total = int(match.group(2))
                run.stage = "Checking evidence and policy"
            elif cleaned.startswith("Wrote and validated"):
                run.stage = "Validating output"
        return_code = process.wait()
        error_reader.join(timeout=1)
        if return_code != 0:
            run.state = "review_required" if run.stage == "Evidence review required" else "failed"
            run.error = (
                "The audit stopped before producing a validated result. Review the safe run "
                "messages and source evidence, then rerun."
            )
            return
        issues = validate_file(output_path, requests_path=run.input_path, dataset_dir=dataset_dir())
        if issues:
            run.validation_issues = [issue.format() for issue in issues[:20]]
            run.state = "failed"
            run.error = (
                "The generated file did not pass the output contract. It cannot be downloaded."
            )
            return
        run.output_bytes = output_path.read_bytes()
        run.rows = _read_csv(output_path)
        run.processed = run.total
        run.stage = "Audit complete and output validated"
        run.state = "complete"
    except Exception as exc:  # UI receives a plain error, details stay in process logs.
        run.state = "failed"
        run.error = (
            f"Could not complete the audit: {type(exc).__name__}. "
            "Check dataset setup and try again."
        )
    finally:
        if output_path is not None:
            output_path.unlink(missing_ok=True)


@app.post("/api/runs", status_code=202)
def start_run(body: RunRequest) -> dict[str, Any]:
    root = dataset_dir()
    if not (root / "deletion_requests.csv").is_file():
        raise HTTPException(
            400, "Dataset not found. Set GHOSTDATA_DATASET to the participant dataset folder."
        )
    with _lock:
        if any(run.state in {"queued", "running"} for run in _runs.values()):
            raise HTTPException(
                409, "An audit is already running. Wait for it to finish before starting another."
            )
        source = root / (
            "sample_deletion_requests.csv" if body.mode == "samples" else "deletion_requests.csv"
        )
        run = AuditRun(uuid.uuid4().hex, body.mode, source)
        _runs[run.run_id] = run
        if body.mode == "saved":
            saved_output = REPO_ROOT / "output.csv"
            if not saved_output.is_file():
                _runs.pop(run.run_id, None)
                raise HTTPException(404, "No validated output.csv is available yet.")
            issues = validate_file(saved_output, requests_path=source, dataset_dir=root)
            if issues:
                _runs.pop(run.run_id, None)
                raise HTTPException(
                    409,
                    "The saved output is not valid for this dataset. Run a fresh audit first.",
                )
            run.requests = {row["case_id"]: row for row in _read_csv(source)}
            run.rows = _read_csv(saved_output)
            run.output_bytes = saved_output.read_bytes()
            run.total = run.processed = len(run.requests)
            run.stage = "Loaded and validated the saved output"
            run.state = "complete"
            return run.payload()
        threading.Thread(target=_execute, args=(run,), daemon=True).start()
    return run.payload()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found. It may have ended when the local app restarted.")
    return run.payload()


def _require_complete(run_id: str) -> AuditRun:
    run = _runs.get(run_id)
    if not run:
        raise HTTPException(404, "Run not found.")
    if run.state != "complete":
        raise HTTPException(
            409, "Case results are available after the audit finishes and validates."
        )
    return run


@app.get("/api/runs/{run_id}/cases")
def list_cases(run_id: str, status: str = "", offset: int = 0, limit: int = 50) -> dict[str, Any]:
    run = _require_complete(run_id)
    limit = min(max(limit, 1), 1000)
    rows = [row for row in run.rows if not status or row["deletion_status"] == status]
    page = rows[max(offset, 0) : max(offset, 0) + limit]
    cases = [_case_summary(run, row) for row in page]
    return {"cases": cases, "total": len(rows), "offset": max(offset, 0), "limit": limit}


@app.post("/api/runs/{run_id}/search")
def search_cases(run_id: str, body: SearchRequest) -> dict[str, Any]:
    run = _require_complete(run_id)
    query = body.query.strip().casefold()
    if not query:
        return {"case_ids": []}
    matches = []
    for row in run.rows:
        case_id = row["case_id"]
        request = run.requests.get(case_id, {})
        if query in case_id.casefold() or query in request.get("email", "").casefold():
            matches.append(_case_summary(run, row))
    return {"cases": matches[:500]}


def _case_summary(run: AuditRun, row: dict[str, Any]) -> dict[str, Any]:
    request = run.requests.get(row["case_id"], {})
    steps = json.loads(row["steps_json"])
    return {
        "case_id": row["case_id"],
        "deletion_status": row["deletion_status"],
        "requested_at": request.get("requested_at", ""),
        "audit_at": request.get("audit_at", ""),
        "reported_status": request.get("reported_status", ""),
        "step_count": len(steps),
        "finding_count": sum(step["phase"] == "FINDING" for step in steps),
        "recreation_count": sum(
            step["operation"] in {"REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK"}
            for step in steps
        ),
        "email_masked": _mask(request.get("email", "")),
    }


@app.get("/api/runs/{run_id}/cases/{case_id}")
def get_case(run_id: str, case_id: str, reveal: bool = False) -> dict[str, Any]:
    run = _require_complete(run_id)
    request = run.requests.get(case_id)
    row = next((item for item in run.rows if item["case_id"] == case_id), None)
    if not request or not row:
        raise HTTPException(404, "Case not found in this run.")
    payload = dict(request)
    if not reveal:
        identifiers = _identifiers_for_request(dataset_dir(), payload.get("email", ""))
        payload["email"] = _redact_identifiers(payload.get("email", ""), identifiers)
        payload["request_text"] = _redact_identifiers(payload.get("request_text", ""), identifiers)
    return {
        "case_id": case_id,
        "deletion_status": row["deletion_status"],
        "request": payload,
        "steps": json.loads(row["steps_json"]),
        "warnings": [],
        "revealed": reveal,
    }


@app.get("/api/runs/{run_id}/cases/{case_id}/evidence/{evidence_id}")
def get_evidence(run_id: str, case_id: str, evidence_id: str) -> dict[str, Any]:
    run = _require_complete(run_id)
    request = run.requests.get(case_id)
    row = next((item for item in run.rows if item["case_id"] == case_id), None)
    if not request or not row:
        raise HTTPException(404, "Case not found.")
    steps = json.loads(row["steps_json"])
    if not any(step["evidence_id"] == evidence_id for step in steps):
        raise HTTPException(404, "This evidence reference is not part of the selected case.")

    root = dataset_dir().resolve()
    cutoff = request.get("audit_at", "")
    evidence_rows = _read_csv(root / "evidence_files.csv")
    manifest = next((item for item in evidence_rows if item.get("file_id") == evidence_id), None)
    if manifest:
        captured = manifest.get("captured_at", "")
        response: dict[str, Any] = {
            "evidence_id": evidence_id,
            "kind": "Source file",
            "source": manifest.get("file_path", manifest.get("origin", "Evidence file")),
            "captured_at": captured,
            "available_at_cutoff": _at_or_before(captured, cutoff),
            "excerpt": "",
            "preview_url": None,
        }
        if not captured or not _at_or_before(captured, cutoff):
            return response
        candidate = (root / manifest.get("file_path", "")).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            return response
        if candidate.suffix.casefold() in {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"}:
            response["kind"] = "Image evidence"
            response["preview_url"] = (
                f"/api/runs/{run_id}/cases/{case_id}/evidence/{evidence_id}/content"
            )
            return response
        text = ""
        try:
            if candidate.suffix.lower() == ".pdf":
                from pypdf import PdfReader

                text = "\n".join(
                    (page.extract_text() or "") for page in PdfReader(candidate).pages[:12]
                )
            elif candidate.stat().st_size <= 2_000_000:
                text = candidate.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = ""
        resource_ids = {step["resource_id"] for step in steps if step["evidence_id"] == evidence_id}
        selected_lines = [
            line.strip()
            for line in text.splitlines()
            if any(token.casefold() in line.casefold() for token in resource_ids)
        ]
        excerpt = "\n".join(selected_lines[:16])[:1800]
        identifiers = _identifiers_for_request(root, request.get("email", ""))
        response["excerpt"] = _redact_identifiers(excerpt, identifiers)
        return response

    for filename, id_column, time_column, kind in (
        ("system_activity.csv", "activity_id", "event_time", "Operational activity claim"),
        ("user_audit_log.csv", "audit_id", "event_time", "Identity history"),
    ):
        path = root / filename
        if path.is_file():
            event = next(
                (item for item in _read_csv(path) if item.get(id_column) == evidence_id), None
            )
            if event:
                timestamp = event.get(time_column, "")
                allowed = _at_or_before(timestamp, cutoff)
                identifiers = _identifiers_for_request(root, request.get("email", ""))
                safe_event = {
                    key: _redact_identifiers(value, identifiers)
                    for key, value in event.items()
                    if key not in {"old_value", "new_value"}
                }
                if kind == "Identity history":
                    safe_event["changed_field"] = event.get("field_name", "")
                    safe_event["old_value"] = "[masked]"
                    safe_event["new_value"] = "[masked]"
                return {
                    "evidence_id": evidence_id,
                    "kind": kind,
                    "source": filename,
                    "captured_at": timestamp,
                    "available_at_cutoff": allowed,
                    "excerpt": json.dumps(safe_event, ensure_ascii=False, indent=2)
                    if allowed
                    else "",
                }
    raise HTTPException(404, "Evidence source was not found in the participant dataset.")


@app.get("/api/runs/{run_id}/cases/{case_id}/evidence/{evidence_id}/content")
def get_evidence_content(run_id: str, case_id: str, evidence_id: str) -> Response:
    """Serve a cited raster image only when it was available at this case's cutoff."""
    run = _require_complete(run_id)
    request = run.requests.get(case_id)
    row = next((item for item in run.rows if item["case_id"] == case_id), None)
    if not request or not row:
        raise HTTPException(404, "Case not found.")
    steps = json.loads(row["steps_json"])
    if not any(step["evidence_id"] == evidence_id for step in steps):
        raise HTTPException(404, "This evidence reference is not part of the selected case.")

    root = dataset_dir().resolve()
    manifest_rows = _read_csv(root / "evidence_files.csv")
    manifest = next((item for item in manifest_rows if item.get("file_id") == evidence_id), None)
    if not manifest:
        raise HTTPException(404, "Image evidence was not found in the participant manifest.")
    if not _at_or_before(manifest.get("captured_at", ""), request.get("audit_at", "")):
        raise HTTPException(404, "Image evidence was captured after this case's audit cutoff.")

    candidate = (root / manifest.get("file_path", "")).resolve()
    if not candidate.is_relative_to(root) or not candidate.is_file():
        raise HTTPException(404, "Image evidence was not found in the participant dataset.")
    media_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
    }
    media_type = media_types.get(candidate.suffix.casefold())
    if not media_type:
        raise HTTPException(415, "This evidence item is not a supported raster image.")
    if candidate.stat().st_size > 15_000_000:
        raise HTTPException(413, "This image is too large to preview in the local review app.")
    try:
        content = candidate.read_bytes()
    except OSError as exc:
        raise HTTPException(404, "Image evidence could not be read.") from exc
    return Response(
        content,
        media_type=media_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.get("/api/runs/{run_id}/output")
def download_output(run_id: str) -> Response:
    run = _require_complete(run_id)
    if not run.output_bytes:
        raise HTTPException(409, "Validated output is unavailable.")
    return Response(
        run.output_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{run.mode}-output.csv"',
            "Cache-Control": "no-store",
        },
    )


_dist = REPO_ROOT / "ui" / "dist"
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        requested = (_dist / path).resolve()
        if not requested.is_relative_to(_dist.resolve()) or not requested.is_file():
            requested = _dist / "index.html"
        return FileResponse(requested)
