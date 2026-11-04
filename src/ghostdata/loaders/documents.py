"""Text-first PDF and image extraction with optional local OCR and caching."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ghostdata.loaders.evidence_csv import EvidenceFile

_CACHE_VERSION = "evidence-text-v1"


@dataclass(frozen=True)
class DocumentExtraction:
    evidence_id: str
    file_path: str
    content_sha256: str
    method: str
    text: str
    confidence: float
    warnings: tuple[str, ...] = ()


def _inside(base: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def _ocr_image(path: Path, timeout_seconds: int = 45) -> tuple[str, str | None]:
    executable = os.environ.get("TESSERACT_CMD", "").strip() or shutil.which("tesseract") or ""
    if not executable:
        return (
            "",
            "Local OCR is unavailable; install Tesseract or set TESSERACT_CMD to read this image.",
        )
    try:
        result = subprocess.run(
            [executable, str(path), "stdout", "--psm", "6"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "", "OCR could not finish for this image; review it manually."
    if result.returncode != 0:
        return "", "OCR returned an error for this image; review it manually."
    text = result.stdout.strip()
    return text, None if text else "OCR found no readable text in this image."


def _ocr_pdf_pages(path: Path, timeout_seconds: int = 90) -> tuple[str, list[str]]:
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        return "", ["The PDF has no text layer and local PDF rendering is unavailable."]
    warnings: list[str] = []
    pieces: list[str] = []
    with tempfile.TemporaryDirectory(prefix="ghostdata-pdf-") as temp:
        prefix = Path(temp) / "page"
        try:
            result = subprocess.run(
                [pdftoppm, "-png", "-r", "200", str(path), str(prefix)],
                capture_output=True,
                timeout=timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "", ["The PDF could not be rendered for local OCR."]
        if result.returncode != 0:
            return "", ["The PDF could not be rendered for local OCR."]
        for page in sorted(Path(temp).glob("page-*.png")):
            text, warning = _ocr_image(page)
            if text:
                pieces.append(text)
            if warning:
                warnings.append(warning)
    return "\n\n".join(pieces), list(dict.fromkeys(warnings))


def _extract_uncached(path: Path) -> tuple[str, str, float, list[str]]:
    suffix = path.suffix.casefold()
    warnings: list[str] = []
    if suffix in {".txt", ".log"}:
        try:
            return path.read_text(encoding="utf-8-sig"), "plain_text", 1.0, warnings
        except (OSError, UnicodeDecodeError):
            return "", "none", 0.0, ["The text evidence could not be decoded as UTF-8."]
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return "", "none", 0.0, ["PDF extraction requires the pypdf dependency."]
        try:
            reader = PdfReader(str(path), strict=False)
            pages: list[str] = []
            for page in reader.pages:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    pages.append("")
                    warnings.append("At least one PDF page could not be read.")
            text = "\n\n".join(part for part in pages if part.strip()).strip()
        except Exception:
            return "", "none", 0.0, ["The PDF could not be opened; review the evidence manually."]
        if text:
            return text, "embedded_text", 1.0, warnings
        ocr, ocr_warnings = _ocr_pdf_pages(path)
        if ocr:
            return ocr, "tesseract_ocr", 0.65, warnings + ocr_warnings
        return "", "none", 0.0, warnings + ocr_warnings
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}:
        text, warning = _ocr_image(path)
        return (
            text,
            "tesseract_ocr" if text else "none",
            0.65 if text else 0.0,
            [warning] if warning else [],
        )
    return (
        "",
        "unsupported",
        0.0,
        [f"No text extractor is configured for {suffix or 'this file type'}."],
    )


def extract_document(
    entry: EvidenceFile,
    dataset_dir: str | Path,
    *,
    cache_dir: str | Path | None = None,
) -> DocumentExtraction:
    """Extract text from one manifest entry without modifying source evidence.

    Cache entries are content-addressed and live outside ``dataset/``. Files
    that are missing or escape the dataset root become warnings, not crashes.
    """
    base = Path(dataset_dir)
    path = base / Path(entry.file_path)
    if not _inside(base, path):
        return DocumentExtraction(
            entry.file_id,
            entry.file_path,
            "",
            "none",
            "",
            0.0,
            ("The evidence path resolves outside dataset/ and was skipped.",),
        )
    try:
        content = path.read_bytes()
    except OSError:
        return DocumentExtraction(
            entry.file_id,
            entry.file_path,
            "",
            "none",
            "",
            0.0,
            ("The evidence file is missing or unreadable.",),
        )
    digest = hashlib.sha256(content).hexdigest()
    cache_path = Path(cache_dir) / f"{_CACHE_VERSION}-{digest}.json" if cache_dir else None
    if cache_path and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            return DocumentExtraction(
                entry.file_id,
                entry.file_path,
                digest,
                cached["method"],
                cached["text"],
                float(cached["confidence"]),
                tuple(cached.get("warnings", ())),
            )
        except (OSError, ValueError, KeyError, TypeError):
            pass
    text, method, confidence, warnings = _extract_uncached(path)
    extraction = DocumentExtraction(
        entry.file_id,
        entry.file_path,
        digest,
        method,
        text,
        confidence,
        tuple(warnings),
    )
    if cache_path:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "method": method,
                        "text": text,
                        "confidence": confidence,
                        "warnings": warnings,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        except OSError:
            # The cache is an optimization; extraction results remain usable.
            pass
    return extraction


__all__ = ["DocumentExtraction", "extract_document"]
