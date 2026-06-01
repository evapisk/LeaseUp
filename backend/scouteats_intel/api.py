"""FastAPI app exposing search, detail, rehydrate, and ingestion endpoints."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, select

from . import normalize as N
from .db import SessionLocal, init_db
from .local_sources import load_dohmh_csv, load_manhattan_closed, merge_listings
from .hydration import (
    force_rehydrate,
    hydrate_query,
    ingest_closed,
    seed_data_sources,
)
from .models import (
    ScoutEatsComplianceEvent,
    ScoutEatsDataSource,
    ScoutEatsEstablishment,
    ScoutEatsIngestionRun,
    ScoutEatsViolation,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_data_sources()
    yield


app = FastAPI(title="ScoutEats Intel", version="0.1.0", lifespan=lifespan)

# Allow the Vite dev frontend (localhost:8080) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- serialization ------------------------------------------------------------

def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def serialize_establishment(e: ScoutEatsEstablishment) -> dict:
    return {
        "id": e.id,
        "camis": e.camis,
        "name": e.display_name,
        "address": e.address,
        "borough": e.borough,
        "zipcode": e.zipcode,
        "cuisine": e.cuisine,
        "bin": e.bin,
        "bbl": e.bbl,
        "lat": e.latitude,
        "lng": e.longitude,
        "latest_grade": e.latest_grade,
        "latest_score": e.latest_score,
        "last_inspection_date": _iso(e.last_inspection_date),
        "is_closed": e.is_closed,
        "last_closure_date": _iso(e.last_closure_date),
    }


def serialize_violation(v: ScoutEatsViolation) -> dict:
    return {
        "id": v.id,
        "violation_code": v.violation_type,
        "severity": v.severity,
        "status": v.status,
        "description": v.description,
        "issue_date": _iso(v.issue_date),
        "source_category": v.source_category,
        "metadata": v.metadata_json,
    }


def serialize_compliance(c: ScoutEatsComplianceEvent) -> dict:
    return {
        "id": c.id,
        "event_type": c.event_type,
        "event_date": _iso(c.event_date),
        "action_text": c.action_text,
    }


# -- db helpers ---------------------------------------------------------------

def _search_db(q: str, limit: int, closed_only: bool) -> list[ScoutEatsEstablishment]:
    like = f"%{q}%"
    with SessionLocal() as session:
        stmt = select(ScoutEatsEstablishment).where(
            or_(
                ScoutEatsEstablishment.display_name.ilike(like),
                ScoutEatsEstablishment.address.ilike(like),
                ScoutEatsEstablishment.camis == q,
                ScoutEatsEstablishment.zipcode == q,
            )
        )
        if closed_only:
            stmt = stmt.where(ScoutEatsEstablishment.is_closed.is_(True))
        stmt = stmt.order_by(ScoutEatsEstablishment.last_inspection_date.desc()).limit(
            limit
        )
        return list(session.scalars(stmt))


# -- endpoints ----------------------------------------------------------------

@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/establishments/search")
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(25, ge=1, le=200),
    closed_only: bool = True,
) -> dict:
    """Query the DB first; if empty, hydrate from Socrata inline and re-query."""
    rows = _search_db(q, limit, closed_only)
    hydrated = None
    if not rows:
        hydrated = await hydrate_query(q, closed_only=closed_only, limit=max(limit, 100))
        rows = _search_db(q, limit, closed_only)
    return {
        "query": q,
        "count": len(rows),
        "hydrated": hydrated,
        "results": [serialize_establishment(e) for e in rows],
    }


def _db_listings() -> list[dict]:
    """Live Socrata establishments aggregated into the frontend's listing shape."""
    with SessionLocal() as session:
        ests = list(session.scalars(select(ScoutEatsEstablishment)))
        ids = [e.id for e in ests]
        agg: dict[int, dict] = {
            e.id: {"total": 0, "critical": 0, "categories": set()} for e in ests
        }
        if ids:  # one query for all violations; aggregate in Python (avoids N+1)
            vios = session.scalars(
                select(ScoutEatsViolation).where(
                    ScoutEatsViolation.establishment_id.in_(ids)
                )
            )
            for v in vios:
                a = agg[v.establishment_id]
                a["total"] += 1
                if v.severity == "critical":
                    a["critical"] += 1
                if v.violation_type:
                    a["categories"].add(N.category_for_code(v.violation_type))

        out = []
        for e in ests:
            a = agg[e.id]
            out.append(
                {
                    "id": e.camis or str(e.id),
                    "name": e.display_name,
                    "address": e.address,
                    "borough": e.borough,
                    "zip": e.zipcode,
                    "lat": e.latitude,
                    "lng": e.longitude,
                    "violations": a["total"],
                    "critical": a["critical"],
                    "categories": sorted(a["categories"]),
                    "risk": N.risk_for(a["critical"]),
                    "lastInspection": (
                        e.last_inspection_date.date().isoformat()
                        if e.last_inspection_date
                        else None
                    ),
                    "cuisine": e.cuisine,
                    "grade": e.latest_grade,
                    "is_closed": e.is_closed,
                    "sources": ["socrata_live"],
                }
            )
        return out


@app.get("/listings")
def listings(
    limit: int = Query(40000, ge=1, le=80000),
    closed_only: bool = False,
) -> list[dict]:
    """Unified feed: live Socrata establishments merged with the local datasets
    (full CSV-derived inspections + closed Manhattan list), deduped by CAMIS.

    Each record carries `is_closed` and `sources` (which datasets contributed).
    """
    merged = merge_listings(
        _db_listings(), load_dohmh_csv(), load_manhattan_closed()
    )
    if closed_only:
        merged = [m for m in merged if m.get("is_closed")]
    # Closed first, then most-flagged.
    merged.sort(key=lambda m: (not m.get("is_closed"), -m.get("violations", 0)))
    return merged[:limit]


@app.get("/establishments/{establishment_id}")
def get_establishment(establishment_id: int) -> dict:
    with SessionLocal() as session:
        e = session.get(ScoutEatsEstablishment, establishment_id)
        if e is None:
            raise HTTPException(404, "establishment not found")
        return serialize_establishment(e)


@app.get("/establishments/{establishment_id}/violations")
def get_violations(establishment_id: int) -> dict:
    with SessionLocal() as session:
        stmt = (
            select(ScoutEatsViolation)
            .where(ScoutEatsViolation.establishment_id == establishment_id)
            .order_by(ScoutEatsViolation.issue_date.desc())
        )
        rows = list(session.scalars(stmt))
        return {"count": len(rows), "violations": [serialize_violation(v) for v in rows]}


@app.get("/establishments/{establishment_id}/compliance")
def get_compliance(establishment_id: int) -> dict:
    with SessionLocal() as session:
        stmt = (
            select(ScoutEatsComplianceEvent)
            .where(ScoutEatsComplianceEvent.establishment_id == establishment_id)
            .order_by(ScoutEatsComplianceEvent.event_date.desc())
        )
        rows = list(session.scalars(stmt))
        return {
            "count": len(rows),
            "compliance_events": [serialize_compliance(c) for c in rows],
        }


@app.post("/establishments/{establishment_id}/rehydrate")
async def rehydrate(establishment_id: int) -> dict:
    result = await force_rehydrate(establishment_id)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return result


@app.get("/ingestion/sources")
def list_sources() -> dict:
    with SessionLocal() as session:
        rows = list(session.scalars(select(ScoutEatsDataSource)))
        return {
            "sources": [
                {
                    "source_key": s.source_key,
                    "source_name": s.source_name,
                    "dataset_id": s.dataset_id,
                    "target_model": s.target_model,
                    "enabled": s.enabled,
                }
                for s in rows
            ]
        }


@app.get("/ingestion/runs")
def list_runs(limit: int = Query(25, ge=1, le=200)) -> dict:
    with SessionLocal() as session:
        stmt = (
            select(ScoutEatsIngestionRun)
            .order_by(ScoutEatsIngestionRun.started_at.desc())
            .limit(limit)
        )
        rows = list(session.scalars(stmt))
        return {
            "runs": [
                {
                    "id": r.id,
                    "source_key": r.source_key,
                    "status": r.status,
                    "fetched": r.fetched,
                    "persisted": r.persisted,
                    "failed": r.failed,
                    "detail": r.detail,
                    "started_at": _iso(r.started_at),
                    "finished_at": _iso(r.finished_at),
                }
                for r in rows
            ]
        }


@app.post("/ingestion/run/{source_key}")
async def run_ingestion(
    source_key: str, limit: int | None = Query(None, ge=1)
) -> dict:
    if source_key != "dohmh_inspections":
        raise HTTPException(404, f"unknown source_key: {source_key}")
    return await ingest_closed(limit=limit)
