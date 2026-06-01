#!/usr/bin/env python3
"""Shrink DOHMH restaurant inspection CSV (violations + where it happened).

Row filters (defaults):
  - INSPECTION DATE on/after --min-year (default: 2023-01-01).
  - Drop rows with no violation (empty VIOLATION CODE and VIOLATION DESCRIPTION).

Default columns (violation-focused, smallest practical set):
  CAMIS, DBA, BORO, BUILDING, STREET, ZIPCODE, Latitude, Longitude,
  INSPECTION DATE, INSPECTION TYPE, VIOLATION CODE, CRITICAL FLAG.
  Omits VIOLATION DESCRIPTION (very wide in CSV); join codes to text from NYC
  Open Data or use --with-violation-description. Omits cuisine, ACTION,
  SCORE/GRADE/dates that repeat per inspection line.

  --useful-columns   wider “useful” layout (cuisine, ACTION, description, grades).
  --full-columns     all columns from the source export.

Examples:
  python3 filter_dohmh_by_year.py data.csv --out slim.csv
  python3 filter_dohmh_by_year.py data.csv --useful-columns --out useful.csv
  python3 filter_dohmh_by_year.py data.csv --with-violation-description
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d")

# Default: location + stable violation id (code). No free-text description.
VIOLATION_FOCUS_COLUMNS: tuple[str, ...] = (
    "CAMIS",
    "DBA",
    "BORO",
    "BUILDING",
    "STREET",
    "ZIPCODE",
    "Latitude",
    "Longitude",
    "INSPECTION DATE",
    "INSPECTION TYPE",
    "VIOLATION CODE",
    "CRITICAL FLAG",
)

# Previous larger subset (still drops phone / admin GIS vs full export).
USEFUL_COLUMNS_LEGACY: tuple[str, ...] = (
    "CAMIS",
    "DBA",
    "BORO",
    "BUILDING",
    "STREET",
    "ZIPCODE",
    "CUISINE DESCRIPTION",
    "INSPECTION DATE",
    "ACTION",
    "VIOLATION CODE",
    "VIOLATION DESCRIPTION",
    "CRITICAL FLAG",
    "SCORE",
    "GRADE",
    "GRADE DATE",
    "RECORD DATE",
    "INSPECTION TYPE",
    "Latitude",
    "Longitude",
)


def parse_date(s: str) -> datetime | None:
    s = (s or "").strip()
    if not s:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="input CSV (UTF-8, optional BOM)")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output CSV (default: overwrite input)",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=2023,
        metavar="Y",
        help="keep rows with INSPECTION DATE on/after Y-01-01 (default: 2023)",
    )
    parser.add_argument(
        "--keep-no-violation-rows",
        action="store_true",
        help="keep rows with empty violation code and description",
    )
    parser.add_argument(
        "--full-columns",
        action="store_true",
        help="write all original columns instead of a reduced set",
    )
    parser.add_argument(
        "--useful-columns",
        action="store_true",
        help="use the wider legacy layout (cuisine, ACTION, description, grades)",
    )
    parser.add_argument(
        "--with-violation-description",
        action="store_true",
        help="append VIOLATION DESCRIPTION (large); only with default violation layout",
    )
    args = parser.parse_args()

    if args.full_columns and (
        args.useful_columns or args.with_violation_description
    ):
        raise SystemExit(
            "--full-columns cannot be combined with --useful-columns or "
            "--with-violation-description"
        )

    in_path = args.path
    if not in_path.is_file():
        print(f"not found: {in_path}", file=sys.stderr)
        return 1

    out_path = args.out if args.out is not None else in_path
    cutoff = datetime(args.min_year, 1, 1)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")

    kept = total = 0
    dropped_no_violation = 0
    with in_path.open(newline="", encoding="utf-8-sig") as inf, tmp.open(
        "w", newline="", encoding="utf-8"
    ) as outf:
        reader = csv.reader(inf)
        writer = csv.writer(outf, lineterminator="\n")
        header = next(reader)
        try:
            idx_date = header.index("INSPECTION DATE")
            idx_vcode = header.index("VIOLATION CODE")
            idx_vdesc = header.index("VIOLATION DESCRIPTION")
        except ValueError as e:
            raise SystemExit(f"missing expected column: {header}") from e

        if args.full_columns:
            out_header = header
            slim_indices = None
            max_idx = max(idx_date, idx_vcode, idx_vdesc)
        else:
            if args.useful_columns:
                selected: tuple[str, ...] = USEFUL_COLUMNS_LEGACY
            else:
                selected = list(VIOLATION_FOCUS_COLUMNS)
                if args.with_violation_description:
                    i = selected.index("VIOLATION CODE") + 1
                    selected.insert(i, "VIOLATION DESCRIPTION")
                    selected = tuple(selected)
                else:
                    selected = tuple(selected)
            missing = [c for c in selected if c not in header]
            if missing:
                raise SystemExit(f"input missing columns for output mode: {missing}")
            slim_indices = [header.index(c) for c in selected]
            out_header = list(selected)
            max_idx = max(max(idx_date, idx_vcode, idx_vdesc), max(slim_indices))

        writer.writerow(out_header)

        for row in reader:
            total += 1
            if len(row) <= max_idx:
                continue
            if not args.keep_no_violation_rows and not (
                row[idx_vcode].strip() or row[idx_vdesc].strip()
            ):
                dropped_no_violation += 1
                continue
            dt = parse_date(row[idx_date])
            if dt is None or dt < cutoff:
                continue
            if args.full_columns:
                writer.writerow(row)
            else:
                writer.writerow(row[i] for i in slim_indices)
            kept += 1

    tmp.replace(out_path)
    if args.full_columns:
        mode = "all columns"
    elif args.useful_columns:
        mode = "legacy useful columns"
    else:
        mode = "violation-focus columns"
        if args.with_violation_description:
            mode += " + VIOLATION DESCRIPTION"
    print(f"rows read (excl. header): {total}")
    if not args.keep_no_violation_rows:
        print(f"rows dropped (no violation): {dropped_no_violation}")
    print(f"rows kept (inspection date >= {args.min_year}-01-01), {mode}: {kept}")
    print(
        "rows dropped (other):",
        total - kept - (0 if args.keep_no_violation_rows else dropped_no_violation),
    )
    print(f"written: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
