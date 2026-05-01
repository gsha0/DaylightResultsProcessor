# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Two-step CLI pipeline for batch-processing RADIANCE daylight simulation output (`.wpd` files) into sDA (Spatial Daylight Autonomy) summary CSVs:

1. **`process_sda.py`** — scans a folder for `*_SDA.wpd` files, parses each one, and writes a timestamped `YYYY-MM-DD_sDA_HHMMSS.csv`.
2. **`process_csv.py`** — reads that CSV, appends a `Level` column (floor assignment), and writes `*_processed.csv` + `*_processed_summary.csv` (area-weighted sDA per floor and whole building).

No third-party dependencies. Requires Python 3.10+.

## Commands

```bash
# Run tests
python3 -m pytest tests/ -v
python3 -m unittest tests/test_process_sda.py          # single test file
python3 -m unittest tests.test_process_csv.TestDetectLevel  # single test class

# Run the pipeline (interactive: prompts to chain step 2 after step 1)
python3 process_sda.py -f /path/to/wpd/files

# Run steps independently
python3 process_sda.py -f /path/to/wpd/files --no-postprocess
python3 process_csv.py -i /path/to/sDA_output.csv

# Scripted/batch (no interactive prompts)
python3 process_sda.py -f /path/to/folder --no-postprocess -q
python3 process_csv.py -i output.csv -l GF,MZ,L1,L2,L3,L4,L5 -q
```

## Architecture

### Data flow

```
*_SDA.wpd files  →  process_sda.py  →  YYYY-MM-DD_sDA_HHMMSS.csv
                                              ↓
                     RoomArea.csv  ──→  (Room Area column populated by ZoneID lookup)
                                              ↓
                     process_csv.py  →  *_processed.csv  +  *_processed_summary.csv
```

### `sda_utils.py` — shared module

All file I/O goes through this module:
- `read_csv_safe` / `write_csv_safe` — always use `utf-8-sig` encoding (Excel BOM compatibility). `write_csv_safe` accepts `extrasaction="ignore"` to strip private processing keys.
- `load_room_area_lookup(folder)` — reads `RoomArea.csv` from the given folder; auto-detects the area column by looking for `"area"` in the header (case-insensitive); returns `None` if the file is absent.
- `setup_logging(verbose, quiet)` — configures the root logger; all modules use `logging.getLogger(__name__)`.

### WPD parsing (`parse_wpd_file` in `process_sda.py`)

Each `.wpd` file is read as plain text. Only the **first** `[Sim]` block is used; subsequent blocks are ignored. Extraction order:
1. `[Zone] [ZONEID] Room description` line → `ZoneID`, `Room Name`
2. `[MMA]` line → exactly 10 space-separated floats → `MMA_1`…`MMA_10`
3. `[Data]` matrix → sDA % = `count(v == 1.0) / count(v != -1.0)` (values of `-1.0` are inactive sensors, excluded from denominator)

Parsing errors raise `ValueError` with a descriptive message. The `run()` function catches all exceptions per file and continues processing — failed files appear as rows with `ZoneID=filename` and a populated `Error` column.

### Level detection (`detect_level` in `process_csv.py`)

Whole-word, case-insensitive regex match against `DEFAULT_LEVEL_CODES = ["GF", "MZ", "L1", "L2", "L3", "L4"]`. Returns the matched code, `"Other"` (no match), or `"Multi"` (two or more matches). `"L1"` will not match `"L10"` or `"AL1"`. Override codes via `-l` CLI flag or by editing `DEFAULT_LEVEL_CODES` at the top of the file.

### Summary calculation

`write_summary` in `process_csv.py` uses private dict keys `_area` and `_sda` (populated during row processing, stripped before writing to CSV via `extrasaction="ignore"`). Rooms with a blank `Room Area` are excluded from all calculations. `Other` and `Multi` rooms are excluded from per-floor rows but included in the whole-building row.

## Test fixtures

Tests expect real `.wpd` files in `tests/fixtures/` and a `RoomArea.csv` there too. Both `*.wpd` and `*.csv` are gitignored, so fixtures must be sourced from actual project data. The integration test (`TestIntegration.test_full_pipeline`) copies fixtures to a temp dir and runs the full two-step pipeline end-to-end.
