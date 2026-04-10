"""
process_csv.py
--------------
Post-processes a sDA output CSV by:
  1. Adding a 'Level' column after 'Room Area' (derived from Room Name).
  2. Writing a summary CSV with area-weighted average sDA per floor and for
     the whole building.

Usage:
    python process_csv.py   (run from the folder containing the CSV)

Output:
    <input_stem>_processed.csv         — full row-level data with Level column
    <input_stem>_processed_summary.csv — per-floor and whole-building sDA averages
"""

import os
import re
import csv
import glob
from collections import Counter, defaultdict

# ============================================================
# CONFIGURATION — edit these for each project
# ============================================================

INPUT_CSV = ""   # Path to input CSV. Leave blank to auto-detect the
                 # most-recently-modified *_sDA_*.csv in the script folder.

OUTPUT_CSV = ""  # Path for output CSV. Leave blank to write
                 # <input_stem>_processed.csv alongside the input file.

LEVEL_CODES = ["GF", "MZ", "L1", "L2", "L3", "L4"]
# Add or remove codes above to match your project's floor naming convention.
# Matching is case-sensitive and uses whole-word boundaries so "L1" will not
# match "L10", "AL1", etc.

# ============================================================


def detect_level(room_name, codes):
    """
    Return the level code found in room_name.

    - Exactly one match  -> that code string
    - No match           -> "Other"
    - Two or more matches -> "Multi"
    """
    matched = [code for code in codes if re.search(r"\b" + re.escape(code) + r"\b", room_name)]
    if len(matched) == 0:
        return "Other"
    if len(matched) == 1:
        return matched[0]
    return "Multi"


def resolve_input(script_folder):
    if INPUT_CSV:
        path = INPUT_CSV if os.path.isabs(INPUT_CSV) else os.path.join(script_folder, INPUT_CSV)
        if not os.path.exists(path):
            raise FileNotFoundError(f"INPUT_CSV not found: {path}")
        return path

    candidates = glob.glob(os.path.join(script_folder, "*_sDA_*.csv"))
    # Exclude any previously generated _processed files
    candidates = [c for c in candidates if not c.endswith("_processed.csv")]
    if not candidates:
        raise FileNotFoundError("No *_sDA_*.csv files found in the script folder.")
    return max(candidates, key=os.path.getmtime)


def resolve_output(input_path):
    if OUTPUT_CSV:
        return OUTPUT_CSV if os.path.isabs(OUTPUT_CSV) else os.path.join(
            os.path.dirname(input_path), OUTPUT_CSV
        )
    stem, _ = os.path.splitext(input_path)
    return stem + "_processed.csv"


def weighted_avg_sda(rooms):
    """
    Compute area-weighted average sDA for a list of room dicts.
    Each dict must have numeric 'Room Area' and 'sDA Pct' values.
    Returns (weighted_avg, total_area) or (None, 0) if no valid data.
    """
    total_area = 0.0
    sumproduct = 0.0
    for r in rooms:
        total_area += r["_area"]
        sumproduct += r["_area"] * r["_sda"]
    if total_area == 0:
        return None, 0.0
    return sumproduct / total_area, total_area


def write_summary(summary_path, rows, level_codes):
    """
    Write the summary CSV.

    Columns: Level, Weighted sDA, Total Area (m²), Room Count
    Rows:    one per floor (level_codes order), then whole building,
             then notes for Other/Multi room counts.

    'Other' and 'Multi' rooms are excluded from per-floor rows but
    included in the whole-building row.
    Rooms with blank or non-numeric area are skipped (warned in main).
    """
    # Separate usable rows (have area + sDA) from unusable
    usable = [r for r in rows if r.get("_area") is not None]

    # Group usable rows by level
    by_level = defaultdict(list)
    for r in usable:
        by_level[r["Level"]].append(r)

    fieldnames = ["Level", "Weighted sDA", "Total Area (m²)", "Room Count"]

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Per-floor rows (only named level codes, in order)
        for code in level_codes:
            floor_rooms = by_level.get(code, [])
            avg, area = weighted_avg_sda(floor_rooms)
            writer.writerow({
                "Level": code,
                "Weighted sDA": f"{avg:.4f}" if avg is not None else "",
                "Total Area (m²)": f"{area:.3f}" if area else "",
                "Room Count": len(floor_rooms),
            })

        # Whole-building row (all usable rooms, including Other/Multi)
        avg_all, area_all = weighted_avg_sda(usable)
        writer.writerow({
            "Level": "WHOLE BUILDING",
            "Weighted sDA": f"{avg_all:.4f}" if avg_all is not None else "",
            "Total Area (m²)": f"{area_all:.3f}" if area_all else "",
            "Room Count": len(usable),
        })

        # Notes
        other_count = sum(1 for r in rows if r["Level"] == "Other")
        multi_count = sum(1 for r in rows if r["Level"] == "Multi")
        writer.writerow({})
        writer.writerow({
            "Level": "NOTE",
            "Weighted sDA": f"Other rooms (no level match): {other_count}",
            "Total Area (m²)": f"Multi rooms (multiple matches): {multi_count}",
            "Room Count": "",
        })


def main():
    script_folder = os.path.dirname(os.path.abspath(__file__))

    input_path = resolve_input(script_folder)
    output_path = resolve_output(input_path)
    stem, _ = os.path.splitext(output_path)
    summary_path = stem + "_summary.csv"

    print(f"Input:   {input_path}")
    print(f"Output:  {output_path}")
    print(f"Summary: {summary_path}")

    rows = []
    fieldnames = None
    skipped_area = []

    with open(input_path, "r", newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames) if reader.fieldnames else []

        # Insert 'Level' column immediately after 'Room Area'
        insert_after = "Room Area"
        if insert_after in fieldnames:
            idx = fieldnames.index(insert_after) + 1
        else:
            idx = min(3, len(fieldnames))
        fieldnames.insert(idx, "Level")

        for row in reader:
            room_name = row.get("Room Name", "")
            row["Level"] = detect_level(room_name, LEVEL_CODES)

            # Parse area and sDA for summary calculations (stored as private keys)
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
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Write summary CSV
    write_summary(summary_path, rows, LEVEL_CODES)

    # Console output
    if skipped_area:
        print(f"\nWARNING: {len(skipped_area)} room(s) skipped from calculations (blank Room Area):")
        for name in skipped_area:
            print(f"  {name}")

    level_counts = Counter(row["Level"] for row in rows)
    print(f"\nProcessed {len(rows)} row(s).")
    print("Level breakdown:")
    for code in LEVEL_CODES + ["Other", "Multi"]:
        count = level_counts.get(code, 0)
        if count:
            print(f"  {code:<8} {count}")


if __name__ == "__main__":
    main()
