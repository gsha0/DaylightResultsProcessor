# sDA WPD Processor

Python tools for batch-processing RADIANCE daylight simulation output files (`*_SDA.wpd`) and post-processing the results.

## Workflow

1. **`process_sda.py`** — extracts raw sDA data from `.wpd` files into a timestamped CSV.
2. **`process_csv.py`** — post-processes that CSV to add a floor level column and generate a weighted-average sDA summary.

## Requirements

Python 3.x — no third-party dependencies.

---

## Step 1: process_sda.py

Place `process_sda.py` in the same folder as your `*_SDA.wpd` files, then run:

```bash
python3 process_sda.py
```

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

If a file cannot be parsed, a warning is printed to the console and the row in the CSV will contain the filename in the ZoneID column and a description in the Error column. Processing continues for all remaining files.

---

## Step 2: process_csv.py

Run from the same folder after `process_sda.py` has produced a CSV:

```bash
python3 process_csv.py
```

By default it auto-detects the most-recently-modified `*_sDA_*.csv` in the folder. You can also set explicit paths at the top of the file.

### Configuration

Edit the block at the top of `process_csv.py` for each project:

```python
INPUT_CSV  = ""   # leave blank to auto-detect latest *_sDA_*.csv
OUTPUT_CSV = ""   # leave blank to auto-name as <input>_processed.csv

LEVEL_CODES = ["GF", "MZ", "L1", "L2", "L3", "L4"]
```

`LEVEL_CODES` is matched against Room Name using whole-word boundaries (`L1` will not match `L10` or `AL1`). Add or remove codes to suit your project's floor naming convention.

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
