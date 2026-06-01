#!/usr/bin/env python3
"""Aggregate the DOHMH inspection CSV into one record per restaurant for the
LeaseUp frontend.

Reads the slim "useful" inspection CSV (one row per violation) and rolls it up
to one JSON object per restaurant (CAMIS), enriched with:
  - violation count + critical-violation count
  - violation categories (pests, temperature, hygiene, food protection,
    equipment, administrative) derived from NYC violation codes
  - a risk level (low / medium / high) derived from critical-violation count
  - most recent inspection date and location (borough, zip, lat/lng)

Output: frontend/public/data/inspections.json  (array)  +  a small summary.

Usage:
  python3 build_listings.py            # uses the default CSV in this folder
  python3 build_listings.py path.csv --out frontend/public/data/inspections.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DEFAULT_CSV = "DOHMH_New_York_City_Restaurant_Inspection_Results_20260601_useful.csv"
DEFAULT_OUT = "frontend/public/data/inspections.json"

# NYC violation codes are grouped by their leading two digits. Map each group
# to a friendly, filterable category used by the frontend.
PREFIX_CATEGORY = {
    "02": "temperature",
    "03": "food-protection",
    "04": "pests",
    "05": "food-protection",
    "06": "hygiene",
    "07": "food-protection",
    "08": "pests",
    "09": "equipment",
    "10": "equipment",
}
CATEGORY_LABELS = {
    "pests": "Pests & vermin",
    "temperature": "Temperature control",
    "hygiene": "Personal hygiene",
    "food-protection": "Food protection",
    "equipment": "Equipment & plumbing",
    "administrative": "Administrative",
}
DATE_FORMATS = ("%m/%d/%Y", "%Y-%m-%d")


def category_for(code: str) -> str:
    return PREFIX_CATEGORY.get((code or "").strip()[:2], "administrative")


def parse_date(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def smart_title(name: str) -> str:
    """Title-case an ALL-CAPS business name while keeping short tokens sane."""
    keep_upper = {"NYC", "II", "III", "IV", "BBQ", "LLC", "USA", "NY", "JFK"}
    out = []
    for w in (name or "").split():
        out.append(w if w in keep_upper else w.capitalize())
    return " ".join(out)


def to_float(s: str) -> float | None:
    try:
        v = float(s)
    except (TypeError, ValueError):
        return None
    return None if v == 0 else round(v, 5)


def risk_for(critical: int) -> str:
    if critical == 0:
        return "low"
    if critical <= 2:
        return "medium"
    return "high"


def main() -> int:
    import csv

    csv.field_size_limit(10_000_000)
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", type=Path, default=Path(DEFAULT_CSV))
    ap.add_argument("--out", type=Path, default=Path(DEFAULT_OUT))
    args = ap.parse_args()

    if not args.path.is_file():
        print(f"not found: {args.path}", file=sys.stderr)
        return 1

    # Accumulators keyed by CAMIS (restaurant id).
    info: dict[str, dict] = {}
    cats: dict[str, set[str]] = defaultdict(set)
    vcount: Counter = Counter()
    ccount: Counter = Counter()
    last: dict[str, datetime] = {}

    with args.path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            cid = row["CAMIS"].strip()
            if not cid or row["BORO"].strip() in ("", "0"):
                continue
            vcount[cid] += 1
            if row["CRITICAL FLAG"].strip() == "Critical":
                ccount[cid] += 1
            code = row["VIOLATION CODE"].strip()
            if code:
                cats[cid].add(category_for(code))
            dt = parse_date(row["INSPECTION DATE"])
            if dt and (cid not in last or dt > last[cid]):
                last[cid] = dt
            if cid not in info:
                addr = " ".join(
                    f"{row['BUILDING'].strip()} {row['STREET'].strip()}".split()
                )
                info[cid] = {
                    "id": cid,
                    "name": smart_title(row["DBA"].strip()),
                    "address": addr,
                    "borough": row["BORO"].strip(),
                    "zip": row["ZIPCODE"].strip(),
                    "lat": to_float(row["Latitude"]),
                    "lng": to_float(row["Longitude"]),
                }

    listings = []
    for cid, base in info.items():
        crit = ccount[cid]
        rec = dict(base)
        rec["violations"] = vcount[cid]
        rec["critical"] = crit
        rec["categories"] = sorted(cats[cid])
        rec["risk"] = risk_for(crit)
        rec["lastInspection"] = last[cid].strftime("%Y-%m-%d") if cid in last else None
        listings.append(rec)

    # Stable, useful default order: most-flagged first.
    listings.sort(key=lambda r: (-r["violations"], r["name"]))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        json.dump(listings, fh, separators=(",", ":"), ensure_ascii=False)

    boro = Counter(r["borough"] for r in listings)
    risk = Counter(r["risk"] for r in listings)
    cat = Counter(c for r in listings for c in r["categories"])
    print(f"restaurants written: {len(listings)}")
    print(f"output: {args.out}  ({args.out.stat().st_size/1_000_000:.2f} MB)")
    print("by borough:", dict(boro.most_common()))
    print("by risk:", dict(risk.most_common()))
    print("by category:", {CATEGORY_LABELS[k]: v for k, v in cat.most_common()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
