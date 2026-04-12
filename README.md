# sDA WPD Processor

Python tools for batch-processing RADIANCE daylight simulation output files (`*_SDA.wpd`) and post-processing the results. This tool is authored by Claude. 

## Workflow

1. **`process_sda.py`** — extracts raw sDA data from `.wpd` files into a timestamped CSV.
2. **`process_csv.py`** — post-processes that CSV to add a floor level column and generate a weighted-average sDA summary.

## Requirements

Python 3.10+ — no third-party dependencies.

---

## Step 1: process_sda.py

Place `process_sda.py` in the same folder as your `*_SDA.wpd` files, then run:

```bash
python3 process_sda.py
```

### CLI Options

```
python3 process_sda.py [OPTIONS]

  -f, --folder FOLDER    Folder containing WPD files (default: script directory)
  -o, --output OUTPUT    Output CSV path (default: timestamped file in folder)
  -p, --pattern PATTERN  Glob pattern for WPD files (default: *_SDA.wpd)
  --no-area              Skip RoomArea.csv lookup
  --no-postprocess       Skip the post-processing prompt (for scripted/batch use)
  -v, --verbose          Verbose output
  -q, --quiet            Suppress info messages
```

After extraction completes, the script will prompt you to run post-processing immediately. Use `--no-postprocess` to skip this prompt in automated workflows.

### Output

A CSV file named `YYYY-MM-DD_sDA_HHMMSS.csv` is created in the same folder.

| Column | Description |
|---|---|
| ZoneID | Zone identifier, e.g. `B100023C` |
| Room Name | Full room description |
| Room Area | Floor area looked up from `RoomArea.csv` by ZoneID; blank if not found |
| sDA Pct | Fraction of valid sensor points achieving sDA (4 decimal places) |
| MMA_1 … MMA_10 | The 10 MMA values from the first `[Sim]` block |
| Error | Empty on success; error message if parsing failed |

### RoomArea.csv (optional)

Place a file named `RoomArea.csv` in the same folder to populate the `Room Area` column. The file must have a `Space ID` column and a floor area column (any column whose name contains "area" is detected automatically). Example:

```
Space ID,Floor Area (m²)
B1000220,42.5
B100023C,18.0
```

If `RoomArea.csv` is not present, a warning is printed and the `Room Area` column is left blank for all rows.

### WPD file format

The script expects plain-text `.wpd` files with this structure:

```
[Zone] [ZONEID] Room description
...
[Sim]
[MMA] v1 v2 v3 v4 v5 v6 v7 v8 v9 v10
[Data] 0 0
<data matrix rows>

[Sim]   ← subsequent blocks are ignored
...
```

`sDA Pct` is calculated from the data matrix: sensor points with value `1.00` divided by all points excluding `-1.00` (inactive sensors).

### Error handling

- If a file cannot be parsed, a warning is printed and the CSV row will contain the filename in ZoneID and a description in Error. Processing continues for all remaining files.
- Duplicate ZoneIDs across WPD files are detected and warned about.
- RoomArea.csv read errors are reported (not silently swallowed).

---

## Step 2: process_csv.py

Run from the same folder after `process_sda.py` has produced a CSV:

```bash
python3 process_csv.py
```

### CLI Options

```
python3 process_csv.py [OPTIONS]

  -i, --input INPUT    Input CSV path (default: auto-detect most recent *_sDA_*.csv)
  -o, --output OUTPUT  Output CSV path (default: <input_stem>_processed.csv)
  -l, --levels LEVELS  Comma-separated level codes (default: GF,MZ,L1,L2,L3,L4)
  -v, --verbose        Verbose output
  -q, --quiet          Suppress info messages
```

### Configuration

Level codes can be set via CLI (`-l GF,MZ,L1,L2,L3,L4,L5`) or by editing `DEFAULT_LEVEL_CODES` at the top of `process_csv.py`. CLI arguments take precedence.

Level matching is **case-insensitive** and uses whole-word boundaries (`L1` will not match `L10` or `AL1`).

### Outputs

**`<input>_processed.csv`** — all original columns plus a `Level` column inserted after `Room Area`:

| Level value | Meaning |
|---|---|
| `GF`, `L1`, etc. | Exactly one level code matched in Room Name |
| `Other` | No level code matched |
| `Multi` | Two or more level codes matched (needs manual review) |

**`<input>_processed_summary.csv`** — area-weighted average sDA per floor and for the whole building:

| Column | Description |
|---|---|
| Level | Floor code, `WHOLE BUILDING`, or `NOTE` |
| Weighted sDA | `SUMPRODUCT(area, sDA) / SUM(area)` |
| Total Area (m²) | Sum of room areas used in the calculation |
| Room Count | Number of rooms included |

`Other` and `Multi` rooms are excluded from per-floor rows but included in the whole-building calculation. Rooms with a blank `Room Area` are skipped from all calculations with a console warning. The final `NOTE` row records the count of `Other` and `Multi` rooms.

---

## Testing

```bash
python3 -m pytest tests/ -v
```

Test fixtures are in `tests/fixtures/`. Tests cover WPD parsing, level detection, weighted averages, and full pipeline integration.

---

## Project Structure

```
process_sda.py      — Step 1: WPD extraction
process_csv.py      — Step 2: CSV post-processing and summary
sda_utils.py        — Shared utilities (CSV I/O, room area lookup, logging)
tests/              — Unit and integration tests
  fixtures/         — Test WPD files and RoomArea.csv
RoomArea.csv        — Room area lookup (project-specific, optional)
```
