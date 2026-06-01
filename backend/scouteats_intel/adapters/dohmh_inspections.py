"""DOHMH Restaurant Inspection Results adapter (Socrata 43nn-pn8j).

One Socrata row = one cited violation for one inspection. We map:
  - each row -> a violation (target_model="violation")
  - rows whose ACTION marks a closure/re-open -> a compliance event
The establishment (restaurant) is keyed by CAMIS.
"""
from __future__ import annotations

from .. import normalize as N
from ..config import get_settings
from .base import BaseSourceAdapter, NormalizedRecord

# Explicit projection avoids 400s if the dataset's schema drifts.
_SELECT = (
    "camis,dba,boro,building,street,zipcode,phone,cuisine_description,"
    "inspection_date,action,violation_code,violation_description,critical_flag,"
    "score,grade,grade_date,record_date,inspection_type,latitude,longitude,"
    "community_board,council_district,census_tract,bin,bbl,nta"
)

# Catches both "Establishment Closed by DOHMH..." and "Establishment re-closed
# by DOHMH." (SoQL like is case-sensitive, hence lower()).
CLOSED_WHERE = "lower(action) like '%closed by dohmh%'"


def _soql_str(value: str) -> str:
    """Escape a value for a single-quoted SoQL string literal."""
    return value.replace("'", "''")


class DohmhInspectionsAdapter(BaseSourceAdapter):
    source_key = "dohmh_inspections"
    source_name = "DOHMH Restaurant Inspection Results"
    target_model = "violation"
    select = _SELECT

    def __init__(self) -> None:
        self.dataset_id = get_settings().dataset_dohmh

    # -- identity -------------------------------------------------------------

    def get_source_record_id(self, payload: dict) -> str:
        camis = (payload.get("camis") or "").strip()
        date = (payload.get("inspection_date") or "").strip()
        code = (payload.get("violation_code") or "").strip()
        # A single inspection can cite several codes; (camis, date, code) is the
        # natural key. Fall back to the action when there is no violation code.
        suffix = code or f"ACTION:{(payload.get('action') or '')[:24]}"
        return f"{camis}|{date}|{suffix}"

    # -- establishment --------------------------------------------------------

    def build_building_payload(self, payload: dict) -> dict:
        camis = N.normalize_identifier(payload.get("camis"))
        bin_ = N.normalize_identifier(payload.get("bin"))
        bbl = N.normalize_identifier(payload.get("bbl"))
        identifiers: list[tuple[str, str]] = []
        if camis:
            identifiers.append((N.ID_CAMIS, camis))
        if bin_:
            identifiers.append((N.ID_BIN, bin_))
        # DOHMH BBL is already the 10-digit padded form when present.
        if bbl and len(bbl) >= 10:
            identifiers.append((N.ID_BBL, bbl[:10]))

        building = (payload.get("building") or "").strip()
        street = (payload.get("street") or "").strip()
        address = " ".join(f"{building} {street}".split()) or None

        score = payload.get("score")
        try:
            score_i = int(score) if score not in (None, "") else None
        except (TypeError, ValueError):
            score_i = None

        return {
            "camis": (payload.get("camis") or "").strip() or None,
            "display_name": (payload.get("dba") or "").strip().title() or None,
            "address": address,
            "borough": (payload.get("boro") or "").strip() or None,
            "zipcode": (payload.get("zipcode") or "").strip() or None,
            "cuisine": (payload.get("cuisine_description") or "").strip() or None,
            "bin": bin_,
            "bbl": bbl[:10] if bbl and len(bbl) >= 10 else None,
            "latitude": N.to_float(payload.get("latitude")),
            "longitude": N.to_float(payload.get("longitude")),
            "community_board": (payload.get("community_board") or "").strip() or None,
            "council_district": (payload.get("council_district") or "").strip() or None,
            "nta": (payload.get("nta") or "").strip() or None,
            "latest_grade": (payload.get("grade") or "").strip() or None,
            "latest_score": score_i,
            "last_inspection_date": N.parse_socrata_datetime(
                payload.get("inspection_date")
            ),
            "identifiers": identifiers,
        }

    # -- normalized violation + compliance ------------------------------------

    def build_normalized_payload(self, payload: dict) -> NormalizedRecord:
        rid = self.get_source_record_id(payload)
        building = self.build_building_payload(payload)
        issue_date = N.parse_socrata_datetime(payload.get("inspection_date"))
        closure = N.closure_status(payload.get("action"))

        violation = None
        code = (payload.get("violation_code") or "").strip()
        if code:
            critical = (payload.get("critical_flag") or "").strip()
            violation = {
                "violation_number": rid,
                "violation_type": code,
                "source_category": "DOHMH",
                "severity": "critical" if critical == "Critical" else "not_critical",
                "status": "closed" if closure in {"closed", "re-closed"} else "cited",
                "description": (payload.get("violation_description") or "").strip()
                or None,
                "respondent": (payload.get("dba") or "").strip() or None,
                "issue_date": issue_date,
                "disposition_date": None,
                "metadata_json": {
                    "inspection_type": payload.get("inspection_type"),
                    "grade": payload.get("grade"),
                    "score": payload.get("score"),
                    "action": payload.get("action"),
                },
            }

        compliance = None
        if closure is not None:
            compliance = {
                "event_type": closure,
                "event_date": issue_date,
                "action_text": (payload.get("action") or "").strip() or None,
                "metadata_json": {
                    "inspection_type": payload.get("inspection_type"),
                    "violation_code": code or None,
                },
            }

        return NormalizedRecord(
            source_record_id=rid,
            building=building,
            violation=violation,
            compliance_event=compliance,
        )

    # -- search ---------------------------------------------------------------

    def build_search_filters(self, normalized_query: str) -> list[str]:
        q = normalized_query.strip()
        if not q:
            return []
        if q.isdigit():  # CAMIS lookup
            return [f"camis='{_soql_str(q)}'"]
        ql = _soql_str(q.upper())
        return [
            f"upper(dba) like '%{ql}%'",
            f"upper(street) like '%{ql}%'",
            f"zipcode='{_soql_str(q)}'",
        ]
