"""Persistence: raw record upsert, identity resolution, and per-record writes."""
from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from .adapters.base import BaseSourceAdapter, NormalizedRecord
from .models import (
    ScoutEatsComplianceEvent,
    ScoutEatsEstablishment,
    ScoutEatsIdentifier,
    ScoutEatsRawRecord,
    ScoutEatsViolation,
)

logger = logging.getLogger("scouteats.persistence")

# Establishment fields that may be hydrated if currently null.
_HYDRATABLE = (
    "camis", "display_name", "address", "borough", "zipcode", "cuisine",
    "bin", "bbl", "latitude", "longitude", "community_board",
    "council_district", "nta", "latest_grade", "latest_score",
)


def _checksum(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def upsert_raw_record(
    session: Session, source_key: str, source_record_id: str, payload: dict
) -> ScoutEatsRawRecord:
    checksum = _checksum(payload)
    existing = session.scalar(
        select(ScoutEatsRawRecord).where(
            ScoutEatsRawRecord.source_key == source_key,
            ScoutEatsRawRecord.source_record_id == source_record_id,
        )
    )
    if existing is None:
        rec = ScoutEatsRawRecord(
            source_key=source_key,
            source_record_id=source_record_id,
            payload=payload,
            checksum=checksum,
        )
        session.add(rec)
        session.flush()
        return rec
    if existing.checksum != checksum:  # changed -> refresh
        existing.payload = payload
        existing.checksum = checksum
        session.flush()
    return existing


def _find_by_identifiers(
    session: Session, identifiers: list[tuple[str, str]]
) -> ScoutEatsEstablishment | None:
    for id_type, id_value in identifiers:
        ident = session.scalar(
            select(ScoutEatsIdentifier).where(
                ScoutEatsIdentifier.id_type == id_type,
                ScoutEatsIdentifier.id_value == id_value,
            )
        )
        if ident is not None:
            return ident.establishment
    return None


def _index_identifiers(
    session: Session,
    est: ScoutEatsEstablishment,
    identifiers: list[tuple[str, str]],
) -> None:
    have = {(i.id_type, i.id_value) for i in est.identifiers}
    for id_type, id_value in identifiers:
        if (id_type, id_value) in have:
            continue
        # Skip if claimed by another establishment (keeps the unique constraint safe).
        clash = session.scalar(
            select(ScoutEatsIdentifier).where(
                ScoutEatsIdentifier.id_type == id_type,
                ScoutEatsIdentifier.id_value == id_value,
            )
        )
        if clash is not None:
            continue
        session.add(
            ScoutEatsIdentifier(
                establishment=est, id_type=id_type, id_value=id_value
            )
        )
        have.add((id_type, id_value))


def resolve_establishment(
    session: Session, building: dict
) -> ScoutEatsEstablishment:
    """Find by identifiers, then by (name, address); else create. When found,
    hydrate only missing (null) fields — never overwrite existing values."""
    identifiers: list[tuple[str, str]] = building.get("identifiers", [])

    est = _find_by_identifiers(session, identifiers)
    if est is None and building.get("display_name") and building.get("address"):
        est = session.scalar(
            select(ScoutEatsEstablishment).where(
                ScoutEatsEstablishment.display_name == building["display_name"],
                ScoutEatsEstablishment.address == building["address"],
            )
        )

    if est is None:
        est = ScoutEatsEstablishment()
        for field in _HYDRATABLE:
            setattr(est, field, building.get(field))
        est.last_inspection_date = building.get("last_inspection_date")
        session.add(est)
        session.flush()
    else:
        for field in _HYDRATABLE:
            if getattr(est, field) in (None, "") and building.get(field) not in (
                None,
                "",
            ):
                setattr(est, field, building[field])
        # last_inspection_date: keep the most recent.
        new_date = building.get("last_inspection_date")
        if new_date and (
            est.last_inspection_date is None
            or new_date > est.last_inspection_date
        ):
            est.last_inspection_date = new_date

    _index_identifiers(session, est, identifiers)
    session.flush()
    return est


def _upsert_violation(
    session: Session,
    est: ScoutEatsEstablishment,
    adapter: BaseSourceAdapter,
    source_record_id: str,
    raw_id: int,
    data: dict,
) -> None:
    existing = session.scalar(
        select(ScoutEatsViolation).where(
            ScoutEatsViolation.source_key == adapter.source_key,
            ScoutEatsViolation.source_record_id == source_record_id,
        )
    )
    target = existing or ScoutEatsViolation(
        establishment_id=est.id,
        source_key=adapter.source_key,
        source_record_id=source_record_id,
    )
    target.establishment_id = est.id
    target.raw_record_id = raw_id
    for k, v in data.items():
        setattr(target, k, v)
    if existing is None:
        session.add(target)


def _upsert_compliance(
    session: Session,
    est: ScoutEatsEstablishment,
    adapter: BaseSourceAdapter,
    source_record_id: str,
    raw_id: int,
    data: dict,
) -> None:
    existing = session.scalar(
        select(ScoutEatsComplianceEvent).where(
            ScoutEatsComplianceEvent.source_key == adapter.source_key,
            ScoutEatsComplianceEvent.source_record_id == source_record_id,
        )
    )
    target = existing or ScoutEatsComplianceEvent(
        establishment_id=est.id,
        source_key=adapter.source_key,
        source_record_id=source_record_id,
    )
    target.establishment_id = est.id
    target.raw_record_id = raw_id
    for k, v in data.items():
        setattr(target, k, v)
    if existing is None:
        session.add(target)

    # Reflect closure state on the establishment.
    if data.get("event_type") in {"closed", "re-closed"}:
        est.is_closed = True
        ed = data.get("event_date")
        if ed and (est.last_closure_date is None or ed > est.last_closure_date):
            est.last_closure_date = ed
    elif data.get("event_type") == "re-opened":
        est.is_closed = False


def persist_record(
    session: Session, adapter: BaseSourceAdapter, payload: dict
) -> bool:
    """Persist one raw row inside a SAVEPOINT so a single bad row can't fail the
    batch. Returns True on success."""
    source_record_id = adapter.get_source_record_id(payload)
    try:
        with session.begin_nested():
            raw = upsert_raw_record(
                session, adapter.source_key, source_record_id, payload
            )
            normalized: NormalizedRecord = adapter.build_normalized_payload(payload)
            est = resolve_establishment(session, normalized.building)
            if normalized.violation:
                _upsert_violation(
                    session, est, adapter, source_record_id, raw.id,
                    normalized.violation,
                )
            if normalized.compliance_event:
                _upsert_compliance(
                    session, est, adapter, source_record_id, raw.id,
                    normalized.compliance_event,
                )
        return True
    except Exception:  # noqa: BLE001 - isolate one record's failure
        logger.exception(
            "Failed to persist %s record %s", adapter.source_key, source_record_id
        )
        return False
