"""Local datasets merged into /listings alongside the live Socrata feed.

Sources:
  - dohmh_csv:        frontend/public/data/inspections.json (full CSV-derived
                      per-restaurant aggregate, ~27k restaurants, all actions)
  - manhattan_closed: MANHATTAN_CLOSED.json (closed Manhattan restaurants)

Everything is normalized to the frontend "listing" shape and deduplicated by id
(CAMIS) together with the live establishments.
"""
from __future__ import annotations

import functools
import json
import logging
import re

from . import normalize as N
from .config import get_settings

logger = logging.getLogger("scouteats.local_sources")

_ZIP_RE = re.compile(r"\b(\d{5})\b")

# Listing-shape keys we merge across sources.
_LISTING_KEYS = (
    "id", "name", "address", "borough", "zip", "lat", "lng",
    "violations", "critical", "categories", "risk", "lastInspection",
    "cuisine", "grade",
)


def _blank_listing() -> dict:
    return {
        "violations": 0, "critical": 0, "categories": [], "risk": "low",
        "is_closed": False, "sources": [],
    }


@functools.lru_cache(maxsize=1)
def load_dohmh_csv() -> list[dict]:
    """Full CSV-derived dataset (already in listing shape)."""
    path = get_settings().local_inspections_path
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        logger.warning("local inspections file not found: %s", path)
        return []
    out = []
    for r in data:
        rec = {**_blank_listing(), **r}
        rec["id"] = str(r.get("id"))
        rec["is_closed"] = False  # CSV aggregate carries no closure signal
        rec["sources"] = ["dohmh_csv"]
        out.append(rec)
    return out


@functools.lru_cache(maxsize=1)
def load_manhattan_closed() -> list[dict]:
    """Closed Manhattan restaurants (sparse: name/address/cuisine/grade)."""
    path = get_settings().manhattan_closed_path
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        logger.warning("manhattan closed file not found: %s", path)
        return []
    out = []
    for r in data:
        camis = (r.get("permit_number") or "").strip()
        address = r.get("address") or ""
        zip_match = _ZIP_RE.search(address)
        out.append(
            {
                **_blank_listing(),
                "id": camis or (r.get("restaurant_name") or "").strip(),
                "name": (r.get("restaurant_name") or "").strip().title() or None,
                "address": address or None,
                "borough": "Manhattan",
                "zip": zip_match.group(1) if zip_match else None,
                "lat": None,
                "lng": None,
                "cuisine": r.get("food_type"),
                "grade": r.get("grade"),
                "lastInspection": None,
                "is_closed": True,
                "sources": ["manhattan_closed"],
            }
        )
    return out


def merge_listings(*pools: list[dict]) -> list[dict]:
    """Deduplicate listing dicts by id (CAMIS), combining fields across sources.

    - is_closed: True if any source marks it closed.
    - violations / critical: max across sources (richest count wins).
    - categories / sources: union.
    - scalar fields: first non-null wins; lastInspection takes the latest.
    - risk: recomputed from the merged critical count.
    """
    merged: dict[str, dict] = {}
    for pool in pools:
        for rec in pool:
            rid = str(rec.get("id") or "").strip()
            if not rid:
                continue
            cur = merged.get(rid)
            if cur is None:
                merged[rid] = {**rec, "id": rid}
                continue
            cur["is_closed"] = cur.get("is_closed") or rec.get("is_closed", False)
            cur["violations"] = max(cur.get("violations", 0), rec.get("violations", 0))
            cur["critical"] = max(cur.get("critical", 0), rec.get("critical", 0))
            cur["categories"] = sorted(
                set(cur.get("categories") or []) | set(rec.get("categories") or [])
            )
            cur["sources"] = sorted(
                set(cur.get("sources") or []) | set(rec.get("sources") or [])
            )
            for key in _LISTING_KEYS:
                if key in ("id", "violations", "critical", "categories"):
                    continue
                if cur.get(key) in (None, "") and rec.get(key) not in (None, ""):
                    cur[key] = rec[key]
            a, b = cur.get("lastInspection"), rec.get("lastInspection")
            if b and (not a or b > a):
                cur["lastInspection"] = b

    for rec in merged.values():
        rec["risk"] = N.risk_for(rec.get("critical", 0))
    return list(merged.values())
