"""
process_csv.py
--------------
Post-processes a sDA output CSV by:
  1. Adding a 'Level' column after 'Room Area' (derived from Room Name).
  2. Writing a summary CSV with area-weighted average sDA per floor and for
     the whole building.

Usage:
    python process_csv.py                              (auto-detect input)
    python process_csv.py -i path/to/sda.csv           (specify input)
    python process_csv.py -l GF,MZ,L1,L2,L3,L4,L5     (override levels)
    python process_csv.py --help                       (show all options)

Output:
    <input_stem>_processed.csv         -- full row-level data with Level column
    <input_stem>_processed_summary.csv -- per-floor and whole-building sDA averages
"""

import argparse
import glob
import logging
import os
import re
from collections import Counter, defaultdict
from typing import Any

from sda_utils import read_csv_safe, setup_logging, write_csv_safe

log = logging.getLogger(__name__)

# ============================================================
# DEFAULT CONFIGURATION -- can be overridden via CLI arguments
# ============================================================

DEFAULT_LEVEL_CODES = ["GF", "MZ", "L1", "L2", "L3", "L4"]

# ============================================================


def detect_level(room_name: str, codes: list[str]) -> str:
    """
    Return the level code found in room_name.

    - Exactly one match  -> that code string
    - No match           -> "Other"
    - Two or more matches -> "Multi"

    Matching is case-insensitive and uses whole-word boundaries.
    """
    matched = [code for code in codes if re.search(r"\b" + re.escape(code) + r"\b", room_name, re.IGNORECASE)]
    if len(matched) == 0:
        return "Other"
    if len(matched) == 1:
        return matched[0]
    return "Multi"


def resolve_input(script_folder: str, input_csv: str = "") -> str:
    """Resolve input CSV path from explicit path or auto-detect."""
    if input_csv:
        path = input_csv if os.path.isabs(input_csv) else os.path.join(script_folder, input_csv)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Input CSV not found: {path}")
        return path

    candidates = glob.glob(os.path.join(script_folder, "*_sDA_*.csv"))
    candidates = [c for c in candidates if not c.endswith("_processed.csv")]
    if not candidates:
        raise FileNotFoundError("No *_sDA_*.csv files found in the script folder.")
    return max(candidates, key=os.path.getmtime)


def resolve_output(input_path: str, output_csv: str = "") -> str:
    """Resolve output CSV path from explicit path or derive from input."""
    if output_csv:
        return output_csv if os.path.isabs(output_csv) else os.path.join(
            os.path.dirname(input_path), output_csv
        )
    stem, _ = os.path.splitext(input_path)
    return stem + "_processed.csv"


def weighted_avg_sda(rooms: list[dict[str, Any]]) -> tuple[float | None, float]:
    """
    Compute area-weighted average sDA for a list of room dicts.
    Each dict must have numeric '_area' and '_sda' private keys.
    Returns (weighted_avg, total_area) or (None, 0.0) if no valid data.
    """
    total_area = 0.0
    sumproduct = 0.0
    for r in rooms:
        total_area += r["_area"]
        sumproduct += r["_area"] * r["_sda"]
    if total_area == 0:
        return None, 0.0
    return sumproduct / total_area, total_area


def write_summary(
    summary_path: str,
    rows: list[dict[str, Any]],
    level_codes: list[str],
) -> None:
    """
    Write the summary CSV.

    Columns: Level, Weighted sDA, Total Area (m2), Room Count
    Rows:    one per floor (level_codes order), then whole building,
             then notes for Other/Multi room counts.

    'Other' and 'Multi' rooms are excluded from per-floor rows but
    included in the whole-building row.
    """
    usable = [r for r in rows if r.get("_area") is not None]

    by_level: dict[str, list[dict]] = defaultdict(list)
    for r in usable:
        by_level[r["Level"]].append(r)

    fieldnames = ["Level", "Weighted sDA", "Total Area (m²)", "Room Count"]

    summary_rows: list[dict[str, str]] = []

    # Per-floor rows
    for code in level_codes:
        floor_rooms = by_level.get(code, [])
        avg, area = weighted_avg_sda(floor_rooms)
        summary_rows.append({
            "Level": code,
            "Weighted sDA": f"{avg:.4f}" if avg is not None else "",
            "Total Area (m²)": f"{area:.3f}" if area else "",
            "Room Count": str(len(floor_rooms)),
        })

    # Whole-building row
    avg_all, area_all = weighted_avg_sda(usable)
    summary_rows.append({
        "Level": "WHOLE BUILDING",
        "Weighted sDA": f"{avg_all:.4f}" if avg_all is not None else "",
        "Total Area (m²)": f"{area_all:.3f}" if area_all else "",
        "Room Count": str(len(usable)),
    })

    # Notes
    other_count = sum(1 for r in rows if r["Level"] == "Other")
    multi_count = sum(1 for r in rows if r["Level"] == "Multi")
    summary_rows.append({})
    summary_rows.append({
        "Level": "NOTE",
        "Weighted sDA": f"Other rooms (no level match): {other_count}",
        "Total Area (m²)": f"Multi rooms (multiple matches): {multi_count}",
        "Room Count": "",
    })

    write_csv_safe(summary_path, summary_rows, fieldnames)


def run(
    input_path: str | None = None,
    output_path: str | None = None,
    level_codes: list[str] | None = None,
) -> None:
    """
    Post-process a sDA CSV: add Level column and generate summary.

    All parameters are optional; defaults match the original zero-argument behavior.
    """
    script_folder = os.path.dirname(os.path.abspath(__file__))
    codes = level_codes if level_codes is not None else DEFAULT_LEVEL_CODES

    resolved_input = input_path or resolve_input(script_folder)
    resolved_output = output_path or resolve_output(resolved_input)
    stem, _ = os.path.splitext(resolved_output)
    summary_path = stem + "_summary.csv"

    log.info("Input:   %s", resolved_input)
    log.info("Output:  %s", resolved_output)
    log.info("Summary: %s", summary_path)

    # Read and validate
    required = {"ZoneID", "Room Name", "Room Area", "sDA Pct"}
    fieldnames, raw_rows = read_csv_safe(resolved_input, required_columns=required)

    # Insert 'Level' column immediately after 'Room Area'
    insert_after = "Room Area"
    if insert_after in fieldnames:
        idx = fieldnames.index(insert_after) + 1
    else:
        idx = min(3, len(fieldnames))
    fieldnames.insert(idx, "Level")

    rows: list[dict[str, Any]] = []
    skipped_area: list[str] = []

    for row in raw_rows:
        room_name = row.get("Room Name", "")
        row["Level"] = detect_level(room_name, codes)

        area_str = row.get("Room Area", "").strip()
        sda_str = row.get("sDA Pct", "").strip()
        try:
            row["_area"] = float(area_str)
            row["_sda"] = float(sda_str)
        except (ValueError, TypeError):
            row["_area"] = None
            row["_sda"] = None
            if area_str == "":
                skipped_area.append(row.get("Room Name") or row.get("ZoneID", "unknown"))

        rows.append(row)

    # Write processed CSV (strip private keys)
    write_csv_safe(resolved_output, rows, fieldnames, extrasaction="ignore")

    # Write summary CSV
    write_summary(summary_path, rows, codes)

    # Console output
    if skipped_area:
        log.warning(
            "%d room(s) skipped from calculations (blank Room Area):", len(skipped_area)
        )
        for name in skipped_area:
            log.warning("  %s", name)

    level_counts = Counter(row["Level"] for row in rows)
    log.info("Processed %d row(s).", len(rows))
    log.info("Level breakdown:")
    for code in codes + ["Other", "Multi"]:
        count = level_counts.get(code, 0)
        if count:
            log.info("  %-8s %d", code, count)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-process sDA CSV: add Level column and generate summary.",
    )
    parser.add_argument(
        "-i", "--input",
        default=None,
        help="Input CSV path (default: auto-detect most recent *_sDA_*.csv)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output CSV path (default: <input_stem>_processed.csv)",
    )
    parser.add_argument(
        "-l", "--levels",
        default=None,
        help=f"Comma-separated level codes (default: {','.join(DEFAULT_LEVEL_CODES)})",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress info messages")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    level_codes = args.levels.split(",") if args.levels else None

    run(
        input_path=args.input,
        output_path=args.output,
        level_codes=level_codes,
    )


if __name__ == "__main__":
    main()
