"""Hydration pipeline: turn a query (or a bulk request) into persisted data."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .adapters import ADAPTERS, ADAPTERS_BY_KEY
from .adapters.base import BaseSourceAdapter
from .adapters.dohmh_inspections import CLOSED_WHERE
from .config import get_settings
from .db import SessionLocal
from .models import ScoutEatsEstablishment, ScoutEatsIngestionRun
from .persistence import persist_record
from .socrata import FetchSpec, SocrataClient

logger = logging.getLogger("scouteats.hydration")


def _combine_where(filters: list[str], closed_only: bool) -> str | None:
    clauses: list[str] = []
    if filters:
        clauses.append("(" + " OR ".join(filters) + ")")
    if closed_only:
        clauses.append(CLOSED_WHERE)
    return " AND ".join(clauses) if clauses else None


def _persist_rows(
    session: Session, adapter: BaseSourceAdapter, rows: list[dict]
) -> tuple[int, int]:
    persisted = failed = 0
    for row in rows:
        if persist_record(session, adapter, row):
            persisted += 1
        else:
            failed += 1
    return persisted, failed


def _start_run(session: Session, source_key: str) -> ScoutEatsIngestionRun:
    run = ScoutEatsIngestionRun(source_key=source_key, status="running")
    session.add(run)
    session.flush()
    return run


def _finish_run(
    run: ScoutEatsIngestionRun,
    *,
    fetched: int,
    persisted: int,
    failed: int,
    detail: str | None = None,
    status: str = "success",
) -> None:
    run.fetched = fetched
    run.persisted = persisted
    run.failed = failed
    run.detail = detail
    run.status = status
    run.finished_at = datetime.now(timezone.utc)


# -- inline query hydration ---------------------------------------------------

async def hydrate_query(
    query: str, *, closed_only: bool = True, limit: int = 200
) -> dict:
    """Fetch matching DOHMH rows for a free-text/identifier query and persist."""
    fetched = persisted = failed = 0
    async with SocrataClient() as client:
        results: list[tuple[BaseSourceAdapter, list[dict]]] = []
        for adapter in ADAPTERS:
            where = _combine_where(
                adapter.build_search_filters(query), closed_only
            )
            rows = await client.fetch_where(
                adapter.dataset_id, where, limit, select=adapter.select,
                order="inspection_date DESC",
            )
            results.append((adapter, rows))
            fetched += len(rows)

    with SessionLocal() as session:
        for adapter, rows in results:
            run = _start_run(session, adapter.source_key)
            p, f = _persist_rows(session, adapter, rows)
            persisted += p
            failed += f
            _finish_run(run, fetched=len(rows), persisted=p, failed=f,
                        detail=f"query={query!r} closed_only={closed_only}")
        session.commit()
    return {"query": query, "fetched": fetched, "persisted": persisted, "failed": failed}


# -- bulk closed ingest -------------------------------------------------------

async def ingest_closed(limit: int | None = None) -> dict:
    """Bulk-ingest every closed-by-DOHMH inspection row."""
    adapter = ADAPTERS_BY_KEY["dohmh_inspections"]
    async with SocrataClient() as client:
        rows = await client.fetch_all(
            adapter.dataset_id, limit=limit, where=CLOSED_WHERE,
            select=adapter.select,
        )
    with SessionLocal() as session:
        run = _start_run(session, adapter.source_key)
        p, f = _persist_rows(session, adapter, rows)
        _finish_run(run, fetched=len(rows), persisted=p, failed=f,
                    detail=f"ingest_closed limit={limit}")
        session.commit()
    return {"fetched": len(rows), "persisted": p, "failed": f}


# -- parallel rehydrate -------------------------------------------------------

async def force_rehydrate(establishment_id: int) -> dict:
    """Two-phase parallel refresh of one establishment's full inspection history.

    Phase 1 fans out every adapter's lookup (keyed by CAMIS) in a single parallel
    fetch_many batch over one shared client. Phase 2 is reserved for queries that
    depend on phase-1 output (e.g. enrichment datasets keyed by BBL).
    """
    with SessionLocal() as session:
        est = session.get(ScoutEatsEstablishment, establishment_id)
        if est is None:
            return {"error": "not found", "establishment_id": establishment_id}
        camis = est.camis

    if not camis:
        return {"error": "establishment has no CAMIS", "establishment_id": establishment_id}

    async with SocrataClient() as client:
        # Phase 1: all adapters in parallel (full history for this CAMIS).
        specs = [
            FetchSpec(
                dataset_id=a.dataset_id,
                where=f"camis='{camis}'",
                select=a.select,
                limit=5000,
                order="inspection_date DESC",
                tag=a.source_key,
            )
            for a in ADAPTERS
        ]
        phase1 = await client.fetch_many(specs)
        # Phase 2 placeholder: dependent enrichment specs derived from phase 1
        # would be issued here as a second fetch_many batch.

    fetched = persisted = failed = 0
    with SessionLocal() as session:
        for tag, result in phase1:
            adapter = ADAPTERS_BY_KEY[tag]
            run = _start_run(session, adapter.source_key)
            if isinstance(result, Exception):
                _finish_run(run, fetched=0, persisted=0, failed=0,
                            detail=f"rehydrate error: {result}", status="error")
                continue
            p, f = _persist_rows(session, adapter, result)
            fetched += len(result)
            persisted += p
            failed += f
            _finish_run(run, fetched=len(result), persisted=p, failed=f,
                        detail=f"rehydrate camis={camis}")
        session.commit()
    return {
        "establishment_id": establishment_id,
        "camis": camis,
        "fetched": fetched,
        "persisted": persisted,
        "failed": failed,
    }


# -- data source registry -----------------------------------------------------

def seed_data_sources() -> None:
    from .models import ScoutEatsDataSource

    settings = get_settings()  # noqa: F841 - kept for parity / future use
    with SessionLocal() as session:
        for adapter in ADAPTERS:
            exists = session.scalar(
                select(ScoutEatsDataSource).where(
                    ScoutEatsDataSource.source_key == adapter.source_key
                )
            )
            if exists is None:
                session.add(
                    ScoutEatsDataSource(
                        source_key=adapter.source_key,
                        source_name=adapter.source_name,
                        dataset_id=adapter.dataset_id,
                        target_model=adapter.target_model,
                    )
                )
        session.commit()
