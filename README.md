# sDA WPD Processor

A single-file Python tool that batch-processes RADIANCE daylight simulation output files (`*_SDA.wpd`) and writes the results to a CSV.

## What it does

Scans the folder it lives in for files named `*_SDA.wpd`, extracts the zone ID, room name, room area (from an optional `RoomArea.csv`), sDA percentage, and the 10 MMA values from the first `[Sim]` block of each file, and writes everything to a timestamped CSV in the same folder.

## Requirements

Python 3.x — no third-party dependencies.

## Usage

Place `process_sda.py` in the same folder as your `*_SDA.wpd` files, then run:

```bash
python3 process_sda.py
```

## Output

A CSV file named `YYYY-MM-DD_sDA_HHMMSS.csv` is created in the same folder.

| Column | Description |
|---|---|
| ZoneID | Zone identifier, e.g. `B100023C` |
| Room Name | Full room description |
| Room Area | Floor area looked up from `RoomArea.csv` by ZoneID; blank if not found |
| sDA Pct | Fraction of valid sensor points achieving sDA (4 decimal places) |
| MMA_1 … MMA_10 | The 10 MMA values from the first `[Sim]` block |
| Error | Empty on success; error message if parsing failed |

## RoomArea.csv (optional)

Place a file named `RoomArea.csv` in the same folder to populate the `Room Area` column. The file must have a `Space ID` column and a floor area column (any column whose name contains "area" is detected automatically). Example:

```
Space ID,Floor Area (m²)
B1000220,42.5
B100023C,18.0
```

If `RoomArea.csv` is not present, a warning is printed and the `Room Area` column is left blank for all rows.

## WPD file format

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

## Error handling

If a file cannot be parsed, a warning is printed to the console and the row in the CSV will contain the filename in the ZoneID column and a description in the Error column. Processing continues for all remaining files.
