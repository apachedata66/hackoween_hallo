#!/usr/bin/env python3
"""Evaluation entry point (starter layout: code/evaluation/main.py).

The scorer itself lives in evaluation/score_samples.py (task B7). Once it
exists, running this file prints the sample accuracy report:

    python code/evaluation/main.py
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "evaluation"))


def main() -> int:
    try:
        scorer = importlib.import_module("score_samples")
    except ImportError:
        print("scorer not built yet (evaluation/score_samples.py, task B7).")
        return 0
    entry = getattr(scorer, "main", None)
    if entry is None:
        print("score_samples.py exists but exposes no main() yet.")
        return 0
    result = entry()
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
