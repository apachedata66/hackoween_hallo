"""Generic CSV reading with column validation and whitespace normalisation (A2).

Every dataset CSV goes through :func:`read_csv_rows`: missing files, missing
columns and malformed rows all raise :class:`LoaderError` with a plain-language
message instead of a traceback.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from pathlib import Path

from ghostdata.loaders.errors import LoaderError

_REDOWNLOAD_HINT = "Restore dataset/ from the official challenge repository."


def read_csv_rows(path: str | Path, required_columns: Sequence[str]) -> list[dict[str, str]]:
    """Read a CSV into a list of dicts with whitespace-stripped values.

    ``required_columns`` must all exist in the header; otherwise
    :class:`LoaderError` names the missing columns. Extra columns are kept.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise LoaderError(
            f"File not found: {file_path.name}", path=str(file_path), hint=_REDOWNLOAD_HINT
        )
    try:
        with file_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            header = list(reader.fieldnames or [])
            missing = [column for column in required_columns if column not in header]
            if missing:
                raise LoaderError(
                    f"{file_path.name} is missing column(s): {', '.join(missing)}",
                    path=str(file_path),
                    hint=_REDOWNLOAD_HINT,
                )
            rows: list[dict[str, str]] = []
            for row in reader:
                cleaned: dict[str, str] = {}
                for key, value in row.items():
                    if key is None:  # overflow columns from a longer-than-header row
                        continue
                    cleaned[key] = value.strip() if isinstance(value, str) else (value or "")
                rows.append(cleaned)
            return rows
    except UnicodeDecodeError:
        raise LoaderError(
            f"{file_path.name} is not readable text",
            path=str(file_path),
            hint="The file may be corrupt; re-download dataset/.",
        ) from None
    except csv.Error as exc:
        raise LoaderError(
            f"{file_path.name} is not valid CSV ({exc})",
            path=str(file_path),
            hint="The file may be corrupt; re-download dataset/.",
        ) from None


def require_non_empty(rows: Iterable[dict[str, str]], *, path: str | Path) -> list[dict[str, str]]:
    """Fail loudly when a file that must have rows contains none."""
    collected = list(rows)
    if not collected:
        raise LoaderError(
            f"{Path(path).name} contains no data rows",
            path=str(path),
            hint="A required dataset file is empty; re-download dataset/.",
        )
    return collected
