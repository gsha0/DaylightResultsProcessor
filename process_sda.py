"""
process_sda.py
--------------
Scans a folder for files matching *_SDA.wpd, extracts ZoneID, Room Name,
and the 10 MMA values from the FIRST [Sim] block only, and writes a
timestamped CSV to the same folder.

Usage:
    python process_sda.py                     (defaults: script folder, *_SDA.wpd)
    python process_sda.py -f /path/to/folder  (specify input folder)
    python process_sda.py --help              (show all options)

Output:
    <folder_path>/YYYY-MM-DD_sDA_HHMMSS.csv
"""

import argparse
import logging
import os
import re
import sys
from collections import Counter
from datetime import datetime

from sda_utils import load_room_area_lookup, setup_logging, write_csv_safe

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_wpd_file(filepath: str) -> dict[str, str]:
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

def run(
    folder: str,
    output: str | None = None,
    pattern: str = "*_SDA.wpd",
    skip_area: bool = False,
) -> str | None:
    """
    Extract sDA data from WPD files and write to CSV.

    Returns the output CSV path on success, or None if no files found.
    """
    import fnmatch

    wpd_files = sorted(f for f in os.listdir(folder) if fnmatch.fnmatch(f, pattern))

    if not wpd_files:
        log.info("No files matching '%s' found in '%s'.", pattern, folder)
        return None

    if output:
        csv_path = output if os.path.isabs(output) else os.path.join(folder, output)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_sDA_%H%M%S")
        csv_path = os.path.join(folder, f"{timestamp}.csv")

    # Load Room Area lookup
    room_area_lookup = None
    if not skip_area:
        room_area_lookup = load_room_area_lookup(folder)

    fieldnames = (
        ["ZoneID", "Room Name", "Room Area", "sDA Pct"]
        + [f"MMA_{i}" for i in range(1, 11)]
        + ["Error"]
    )

    rows: list[dict[str, str]] = []
    error_count = 0
    total = len(wpd_files)

    for idx, filename in enumerate(wpd_files, start=1):
        filepath = os.path.join(folder, filename)
        try:
            data = parse_wpd_file(filepath)
            room_area_value = ""
            if room_area_lookup is not None and data.get("ZoneID") in room_area_lookup:
                room_area_value = room_area_lookup[data["ZoneID"]]
            data["Room Area"] = room_area_value
            data["Error"] = ""
            rows.append(data)
            log.info("[%d/%d] OK  %s", idx, total, filename)
        except Exception as exc:
            log.warning("[%d/%d] FAIL %s -> %s", idx, total, filename, exc)
            error_count += 1
            rows.append({
                "ZoneID": filename,
                "Room Name": "",
                "Room Area": "",
                "sDA Pct": "",
                **{f"MMA_{i}": "" for i in range(1, 11)},
                "Error": str(exc),
            })

    # Check for duplicate ZoneIDs
    zone_ids = [r["ZoneID"] for r in rows if r.get("Error") == ""]
    dupes = {zid: cnt for zid, cnt in Counter(zone_ids).items() if cnt > 1}
    if dupes:
        log.warning("Duplicate ZoneIDs found (may cause incorrect area lookups):")
        for zid, cnt in dupes.items():
            log.warning("  %s appears %d times", zid, cnt)

    write_csv_safe(csv_path, rows, fieldnames)

    log.info("Processed %d file(s), %d error(s).", total, error_count)
    if room_area_lookup is None and not skip_area:
        log.warning("RoomArea.csv not found in '%s'.", folder)
    log.info("Output: %s", csv_path)

    return csv_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract sDA data from RADIANCE WPD files into CSV.",
    )
    parser.add_argument(
        "-f", "--folder",
        default=os.path.dirname(os.path.abspath(__file__)),
        help="Folder containing WPD files (default: script directory)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output CSV path (default: timestamped file in folder)",
    )
    parser.add_argument(
        "-p", "--pattern",
        default="*_SDA.wpd",
        help="Glob pattern for WPD files (default: *_SDA.wpd)",
    )
    parser.add_argument(
        "--no-area",
        action="store_true",
        help="Skip RoomArea.csv lookup",
    )
    parser.add_argument(
        "--no-postprocess",
        action="store_true",
        help="Skip the post-processing prompt (for scripted/batch use)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress info messages")

    args = parser.parse_args()
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    csv_path = run(
        folder=args.folder,
        output=args.output,
        pattern=args.pattern,
        skip_area=args.no_area,
    )

    if csv_path is None:
        sys.exit(0)

    # Interactive post-processing prompt
    if not args.no_postprocess and sys.stdin.isatty():
        try:
            answer = input("\nRun CSV post-processing now? (y/n): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = "n"
            print()

        if answer in ("y", "yes"):
            from process_csv import run as run_csv
            run_csv(input_path=csv_path)


if __name__ == "__main__":
    main()
