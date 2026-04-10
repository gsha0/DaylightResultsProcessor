"""
process_sda.py
--------------
Scans a folder for files matching *_SDA.wpd, extracts ZoneID, Room Name,
and the 10 MMA values from the FIRST [Sim] block only, and writes a
timestamped CSV to the same folder.

Usage:
    python process_sda.py   (run from the folder containing the .wpd files)

Output:
    <folder_path>/YYYY-MM-DD_sDA_HHMMSS.csv
"""

import sys
import os
import re
import csv
from datetime import datetime


# ---------------------------------------------------------------------------
# Room Area Lookup
# ---------------------------------------------------------------------------

def load_room_area_lookup(folder):
    """
    Load Room Area data from RoomArea.csv in the given folder.

    Returns a dict mapping Space ID -> Floor Area value, or None if file not found.
    Auto-detects the Floor Area column (looks for "Floor Area" pattern).
    """
    room_area_path = os.path.join(folder, "RoomArea.csv")

    if not os.path.exists(room_area_path):
        return None

    lookup = {}
    try:
        with open(room_area_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)

            # Auto-detect the Floor Area column (looks for "Floor Area" in header)
            if not reader.fieldnames:
                return lookup

            floor_area_col = None
            for col in reader.fieldnames:
                if "floor area" in col.lower() or "area" in col.lower():
                    floor_area_col = col
                    break

            if not floor_area_col:
                # Fallback: use second column if we can't find it by name
                floor_area_col = reader.fieldnames[1] if len(reader.fieldnames) > 1 else None

            if floor_area_col:
                for row in reader:
                    space_id = row.get("Space ID", "").strip()
                    area_value = row.get(floor_area_col, "").strip()
                    if space_id and area_value:
                        lookup[space_id] = area_value
    except Exception:
        pass

    return lookup


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_wpd_file(filepath):
    """
    Parse a single *_SDA.wpd file.

    Returns a dict with keys:
        ZoneID, Room Name, sDA Pct, MMA_1 ... MMA_10

    Raises ValueError with a descriptive message if any expected field is
    missing or malformed.
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    # --- ZoneID and Room Name ---
    zone_match = re.search(r"\[Zone\]\s+\[(\S+)\]\s+(.+)", content)
    if not zone_match:
        raise ValueError("Could not find [Zone] line")

    zone_id = zone_match.group(1).strip()
    room_name = zone_match.group(2).strip()

    # --- First [Sim] block ---
    sim_match = re.search(r"\[Sim\]", content)
    if not sim_match:
        raise ValueError("Could not find any [Sim] block")

    # Isolate just the first [Sim] block (up to the next [Sim] or end of file)
    sim_content = content[sim_match.start():]
    next_sim = re.search(r"\[Sim\]", sim_content[len("[Sim]"):])
    first_sim_block = sim_content[:len("[Sim]") + next_sim.start()] if next_sim else sim_content

    # --- [MMA] line (end-of-line match only — avoids cross-line bleed) ---
    mma_match = re.search(r"\[MMA\]\s+([^\n]+)", first_sim_block)
    if not mma_match:
        raise ValueError("Could not find [MMA] line in first [Sim] block")

    mma_values = mma_match.group(1).split()
    if len(mma_values) != 10:
        raise ValueError(
            f"Expected 10 MMA values, got {len(mma_values)}: {mma_values}"
        )

    # --- sDA Pct: from [Data] matrix in first [Sim] block ---
    data_match = re.search(r"\[Data\][^\n]*\n([\s\S]+)", first_sim_block)
    if not data_match:
        raise ValueError("Could not find [Data] section in first [Sim] block")

    all_values = [float(v) for v in data_match.group(1).split()]
    valid_values = [v for v in all_values if v != -1.0]
    if not valid_values:
        raise ValueError("No valid data points in [Data] section")

    sda_pct = round(sum(1 for v in valid_values if v == 1.0) / len(valid_values), 4)

    result = {"ZoneID": zone_id, "Room Name": room_name, "sDA Pct": f"{sda_pct:.4f}"}
    for i, val in enumerate(mma_values, start=1):
        result[f"MMA_{i}"] = val

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    folder = os.path.dirname(os.path.abspath(__file__))

    wpd_files = sorted(f for f in os.listdir(folder) if f.endswith("_SDA.wpd"))

    if not wpd_files:
        print(f"No files matching '*_SDA.wpd' found in '{folder}'.")
        sys.exit(0)

    timestamp = datetime.now().strftime("%Y-%m-%d_sDA_%H%M%S")
    csv_path = os.path.join(folder, f"{timestamp}.csv")

    # Load Room Area lookup
    room_area_lookup = load_room_area_lookup(folder)
    room_area_missing = room_area_lookup is None

    fieldnames = ["ZoneID", "Room Name", "Room Area", "sDA Pct"] + [f"MMA_{i}" for i in range(1, 11)] + ["Error"]

    rows = []
    error_count = 0

    for filename in wpd_files:
        filepath = os.path.join(folder, filename)
        try:
            data = parse_wpd_file(filepath)
            # Look up Room Area by ZoneID
            room_area_value = ""
            if room_area_lookup is not None and data.get("ZoneID") in room_area_lookup:
                room_area_value = room_area_lookup[data["ZoneID"]]
            data["Room Area"] = room_area_value
            data["Error"] = ""
            rows.append(data)
            print(f"  OK  {filename}")
        except Exception as exc:
            print(f"WARNING: {filename} -> {exc}")
            error_count += 1
            rows.append({
                "ZoneID": filename,
                "Room Name": "",
                "Room Area": "",
                "sDA Pct": "",
                **{f"MMA_{i}": "" for i in range(1, 11)},
                "Error": str(exc),
            })

    with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nProcessed {len(wpd_files)} file(s), {error_count} error(s).")
    if room_area_missing:
        print("WARNING: RoomArea.csv not found in current folder")
    print(f"Output: {csv_path}")


if __name__ == "__main__":
    main()
