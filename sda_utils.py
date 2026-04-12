"""
sda_utils.py
------------
Shared utilities for the sDA WPD processing pipeline.
"""

import csv
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV I/O helpers
# ---------------------------------------------------------------------------

def read_csv_safe(
    path: str,
    required_columns: set[str] | None = None,
) -> tuple[list[str], list[dict[str, str]]]:
    """
    Read a CSV file with consistent encoding (utf-8-sig) and optional
    column validation.

    Returns (fieldnames, rows).
    Raises SystemExit if required columns are missing.
    """
    with open(path, "r", newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []

        if required_columns:
            missing = required_columns - set(fieldnames)
            if missing:
                raise SystemExit(f"ERROR: {path} is missing required columns: {missing}")

        rows = list(reader)

    return fieldnames, rows


def write_csv_safe(
    path: str,
    rows: list[dict[str, Any]],
    fieldnames: list[str],
    extrasaction: str = "raise",
) -> None:
    """Write a CSV file with consistent utf-8-sig encoding."""
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction=extrasaction)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Room Area Lookup
# ---------------------------------------------------------------------------

def load_room_area_lookup(folder: str) -> dict[str, str] | None:
    """
    Load Room Area data from RoomArea.csv in the given folder.

    Returns a dict mapping Space ID -> Floor Area value, or None if file not found.
    Auto-detects the Floor Area column (looks for "Floor Area" or "Area" in header).
    """
    room_area_path = os.path.join(folder, "RoomArea.csv")

    if not os.path.exists(room_area_path):
        return None

    lookup: dict[str, str] = {}
    try:
        with open(room_area_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                return lookup

            floor_area_col = None
            for col in reader.fieldnames:
                if "floor area" in col.lower() or "area" in col.lower():
                    floor_area_col = col
                    break

            if not floor_area_col:
                floor_area_col = reader.fieldnames[1] if len(reader.fieldnames) > 1 else None

            if floor_area_col:
                for row in reader:
                    space_id = row.get("Space ID", "").strip()
                    area_value = row.get(floor_area_col, "").strip()
                    if space_id and area_value:
                        lookup[space_id] = area_value
    except Exception as exc:
        log.warning("Could not read RoomArea.csv: %s", exc)

    return lookup


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure root logger based on verbosity flags."""
    if quiet:
        level = logging.WARNING
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )
