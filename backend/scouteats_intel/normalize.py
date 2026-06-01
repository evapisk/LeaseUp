"""Normalization helpers: identifiers, BBL computation, dates, closure status."""
from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

# Identifier types we index for dedup / identity resolution.
ID_CAMIS = "CAMIS"
ID_BIN = "BIN"
ID_BBL = "BBL"
ID_BOROUGH_BLOCK_LOT = "BOROUGH_BLOCK_LOT"

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")

# Borough name/code/alias -> single borough digit.
_BOROUGH_DIGIT = {
    "1": "1", "manhattan": "1", "mn": "1", "new york": "1", "ny": "1",
    "2": "2", "bronx": "2", "bx": "2",
    "3": "3", "brooklyn": "3", "bk": "3", "kings": "3",
    "4": "4", "queens": "4", "qn": "4", "qns": "4",
    "5": "5", "staten island": "5", "si": "5", "richmond": "5",
}

# Inspection-date sentinel meaning "never inspected".
_NULL_DATE_PREFIX = "1900-01-01"


def normalize_identifier(value: object) -> str | None:
    """Strip non-alphanumerics and uppercase. Returns None for empty/zero ids."""
    if value is None:
        return None
    cleaned = _NON_ALNUM.sub("", str(value)).upper()
    if not cleaned or set(cleaned) == {"0"}:
        return None
    return cleaned


def borough_digit(borough: object) -> str | None:
    if borough is None:
        return None
    return _BOROUGH_DIGIT.get(str(borough).strip().lower())


def compute_bbl(borough: object, block: object, lot: object) -> str | None:
    """10-char BBL: 1 borough digit + 5-digit block + 4-digit lot."""
    bdigit = borough_digit(borough)
    if bdigit is None or block in (None, "") or lot in (None, ""):
        return None
    try:
        block_s = str(int(float(block))).zfill(5)
        lot_s = str(int(float(lot))).zfill(4)
    except (TypeError, ValueError):
        return None
    if len(block_s) != 5 or len(lot_s) != 4:
        return None
    return f"{bdigit}{block_s}{lot_s}"


def parse_socrata_datetime(value: object) -> datetime | None:
    """Parse a Socrata floating timestamp; drop the 1900-01-01 'never' sentinel."""
    if not value:
        return None
    s = str(value)
    if s.startswith(_NULL_DATE_PREFIX):
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def to_float(value: object) -> float | None:
    try:
        f = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if f == 0 else f


# -- DOHMH action ("Row looking is action") -----------------------------------

def closure_status(action: object) -> str | None:
    """Map a DOHMH ACTION string to a closure event type, or None.

    Returns "closed", "re-closed", or "re-opened" (case-insensitive match).
    """
    if not action:
        return None
    a = str(action).lower()
    if "re-opened" in a or "reopened" in a:
        return "re-opened"
    if "re-closed" in a or "reclosed" in a:
        return "re-closed"
    if "closed by dohmh" in a:
        return "closed"
    return None


def is_closed_action(action: object) -> bool:
    return closure_status(action) in {"closed", "re-closed"}


# -- violation taxonomy (mirrors build_listings.py for the frontend) -----------

# NYC violation codes are grouped by leading two digits.
_PREFIX_CATEGORY = {
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


def category_for_code(code: object) -> str:
    """Map a violation code to a frontend category."""
    return _PREFIX_CATEGORY.get((str(code or "")).strip()[:2], "administrative")


def category_breakdown(codes: Iterable[object] | None) -> dict[str, int]:
    """Count violation categories for an iterable of codes.

    Single-sources off ``category_for_code`` so the taxonomy stays in one place.
    Returns a ``{category: count}`` dict (only categories that occur).
    """
    counts: dict[str, int] = {}
    for code in codes or ():
        cat = category_for_code(code)
        counts[cat] = counts.get(cat, 0) + 1
    return counts


def risk_for(critical_count: int) -> str:
    """low / medium / high from the number of critical violations."""
    if critical_count == 0:
        return "low"
    if critical_count <= 2:
        return "medium"
    return "high"


# Borough digit -> canonical display name (reuses _BOROUGH_DIGIT for aliases).
_DIGIT_BOROUGH = {
    "1": "Manhattan",
    "2": "Bronx",
    "3": "Brooklyn",
    "4": "Queens",
    "5": "Staten Island",
}


def canonical_borough(value: object) -> str | None:
    """Map any borough name/code/alias to a canonical display name, or None.

    Returns one of ``Manhattan``/``Brooklyn``/``Queens``/``Bronx``/
    ``Staten Island``. Unknown / blank inputs return None.
    """
    digit = borough_digit(value)
    if digit is None:
        return None
    return _DIGIT_BOROUGH.get(digit)
