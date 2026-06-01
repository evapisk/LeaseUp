#!/usr/bin/env python3
"""Extract DOHMH inspection rows whose ACTION indicates closure lifecycle events.

The source ACTION field (full CSV) includes phrases such as:
  - Establishment Closed by DOHMH ...
  - Establishment re-closed by DOHMH.
  - Establishment re-opened by DOHMH.

This script matches those (case-insensitive) and writes matching rows to a CSV,
with an added column ``closure_action`` labeling the event type.

Examples:
  python3 dohmh_closed_restaurant_rows.py DOHMH_New_York_City_Restaurant_Inspection_Results_20260601.csv
  python3 dohmh_closed_restaurant_rows.py data.csv --out closures.csv
  python3 dohmh_closed_restaurant_rows.py data.csv --no-reopened
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def classify_action(action: str) -> str | None:
    """Return closure_action label, or None if this row is not a selected closure event."""
    a = (action or "").strip().lower()
    if not a:
        return None
    # Order matters: check re-closed before generic "closed by dohmh".
    if "establishment re-closed by dohmh" in a:
        return "re_closed"
    if "establishment closed by dohmh" in a:
        return "closed"
    if "establishment re-opened by dohmh" in a:
        return "re_opened"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_csv",
        type=Path,
        help="full DOHMH CSV (UTF-8, optional BOM)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output CSV (default: <input_stem>_closure_actions.csv)",
    )
    parser.add_argument(
        "--no-reopened",
        action="store_true",
        help="exclude rows whose ACTION is only re-opened (keep closed + re-closed)",
    )
    args = parser.parse_args()

    in_path = args.input_csv
    if not in_path.is_file():
        print(f"not found: {in_path}", file=sys.stderr)
        return 1

    out_path = args.out
    if out_path is None:
        out_path = in_path.with_name(f"{in_path.stem}_closure_actions{in_path.suffix}")

    matched: dict[str, int] = {"closed": 0, "re_closed": 0, "re_opened": 0}
    written = 0
    total = 0

    with in_path.open(newline="", encoding="utf-8-sig") as inf, out_path.open(
        "w", newline="", encoding="utf-8"
    ) as outf:
        reader = csv.DictReader(inf)
        if reader.fieldnames is None:
            print("empty or invalid CSV", file=sys.stderr)
            return 1
        if "ACTION" not in reader.fieldnames:
            raise SystemExit(f"CSV has no ACTION column. Columns: {reader.fieldnames}")

        out_fields = list(reader.fieldnames) + ["closure_action"]
        writer = csv.DictWriter(outf, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()

        for row in reader:
            total += 1
            label = classify_action(row.get("ACTION", ""))
            if label is None:
                continue
            matched[label] += 1
            if args.no_reopened and label == "re_opened":
                continue
            row["closure_action"] = label
            writer.writerow(row)
            written += 1

    print(f"rows scanned: {total}")
    print(
        "ACTION matched (all):",
        ", ".join(f"{k}={v}" for k, v in sorted(matched.items()) if v),
    )
    print(f"rows written: {written}")
    print(f"output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
