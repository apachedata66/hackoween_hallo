"""Resolve dataset and output paths without hardcoding a machine path.

Order: GHOSTDATA_DATASET environment variable, then <repo root>/dataset.
AGENTS.md §8: resolve relative to the repository root so the solution works
on macOS, Linux, and Windows.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "GHOSTDATA_DATASET"

# <this file> -> ghostdata/ -> code/ -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]


def dataset_dir() -> Path:
    """Directory holding deletion_requests.csv, evidence/, and friends."""

    override = os.environ.get(ENV_VAR, "").strip()
    if override:
        return Path(override).expanduser()
    return REPO_ROOT / "dataset"


def output_path() -> Path:
    """Where the completed output.csv is written (repo root, per contract)."""

    return REPO_ROOT / "output.csv"


def require_dataset() -> Path:
    """dataset_dir(), but fail with a fixable message when it is missing."""

    path = dataset_dir()
    required = path / "deletion_requests.csv"
    if not required.is_file():
        raise FileNotFoundError(
            f"dataset not found: {required}. Set {ENV_VAR} to the dataset "
            "directory of the official challenge checkout, or place dataset/ "
            f"next to code/ at {REPO_ROOT}"
        )
    return path
