"""Build a submission archive without datasets, caches, secrets, or nested zips."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    ROOT / "README.md",
    ROOT / "evaluation" / "evaluation_report.md",
    ROOT / "evaluation" / "usage_report.md",
)
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "cache",
    "caches",
    "dataset",
}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}
SECRET_PATTERNS = (
    ("private key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
    (
        "GitHub token",
        re.compile(rb"\b(?:gh[pousr]_[A-Za-z0-9_]{30,}|github_pat_[A-Za-z0-9_]{30,})\b"),
    ),
    ("API token", re.compile(rb"\bsk-[A-Za-z0-9]{24,}\b")),
    (
        "credential assignment",
        re.compile(
            rb"(?im)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b"
            rb"\s*[:=]\s*['\"]?(?!YOUR_|<|\$\{)[A-Za-z0-9_./+=-]{12,}"
        ),
    ),
)


def _included_files() -> list[Path]:
    files: list[Path] = []
    for top in (
        ROOT / "README.md",
        ROOT / "code",
        ROOT / "src",
        ROOT / "evaluation",
        ROOT / "config",
        ROOT / "scripts",
        ROOT / "ui",
        ROOT / "pyproject.toml",
        ROOT / "requirements.txt",
    ):
        if top.is_file():
            files.append(top)
            continue
        if not top.is_dir():
            continue
        for current, dirs, names in os.walk(top, followlinks=False):
            current_path = Path(current)
            dirs[:] = [
                name
                for name in dirs
                if name not in EXCLUDED_DIRS and not (current_path / name).is_symlink()
            ]
            for name in names:
                path = current_path / name
                if (
                    path.is_symlink()
                    or name == ".env"
                    or (name.startswith(".env.") and name != ".env.example")
                    or name == "log.txt"
                    or name == "manual_review.md"
                    or path.suffix.lower() in ARCHIVE_SUFFIXES
                ):
                    continue
                if path.is_file():
                    files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def _secret_findings(files: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        try:
            content = path.read_bytes()
        except OSError as exc:
            findings.append(f"cannot scan {path.relative_to(ROOT)}: {exc}")
            continue
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(content):
                findings.append(f"possible {label} in {path.relative_to(ROOT)}")
    return findings


def make_archive(destination: Path) -> Path:
    missing = [path for path in REQUIRED if not path.is_file()]
    if missing:
        labels = ", ".join(str(path.relative_to(ROOT)) for path in missing)
        raise FileNotFoundError(f"required submission files are missing: {labels}")

    files = _included_files()
    findings = _secret_findings(files)
    if findings:
        raise ValueError("secret scan failed:\n- " + "\n- ".join(findings))

    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".code-", suffix=".zip", dir=destination.parent, delete=False
        ) as temp:
            temp_name = temp.name
        with zipfile.ZipFile(temp_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, path.relative_to(ROOT).as_posix())
        with zipfile.ZipFile(temp_name) as archive:
            names = archive.namelist()
            if any(Path(name).suffix.lower() in ARCHIVE_SUFFIXES for name in names):
                raise ValueError("nested archive detected in generated package")
            if not all(path.relative_to(ROOT).as_posix() in names for path in REQUIRED):
                raise ValueError("generated package is missing a required submission file")
        Path(temp_name).replace(destination)
    except Exception:
        if temp_name and Path(temp_name).exists():
            Path(temp_name).unlink()
        raise
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and inspect the submission code.zip")
    parser.add_argument("--out", type=Path, default=ROOT / "code.zip")
    args = parser.parse_args(argv)
    try:
        archive = make_archive(args.out)
    except (OSError, ValueError) as exc:
        print(f"package: {exc}", file=sys.stderr)
        return 2
    print(f"Created {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
