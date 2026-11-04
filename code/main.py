#!/usr/bin/env python3
"""Official entry point (AGENTS.md 6.10 / README quick start).

Run from the repository root:

    python code/main.py

This stays runnable from a clean clone at every stage: once Person B lands
the CLI (task B9) it delegates to ``ghostdata.cli``; until then it explains
what is missing instead of crashing.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


def main() -> int:
    try:
        cli = importlib.import_module("ghostdata.cli")
    except ImportError:
        print(
            "ghostdata engine not wired yet (src/ghostdata/cli.py is a stub).\n"
            "Project skeleton and data contract are in place - see docs/ARCHITECTURE.md."
        )
        return 0

    entry = getattr(cli, "main", None) or getattr(cli, "run", None)
    if entry is None:
        print("ghostdata.cli exists but exposes neither main() nor run() yet.")
        return 0
    result = entry()
    return int(result) if isinstance(result, int) else 0


if __name__ == "__main__":
    raise SystemExit(main())
