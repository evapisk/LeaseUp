# ScoutEats Intel — NYC inspection scraper & enrichment backend

Async Socrata scraper for NYC Open Data's **DOHMH Restaurant Inspection Results**
dataset (`43nn-pn8j`). It fetches inspection rows, normalizes them, deduplicates
them into restaurant **establishment** entities (keyed by CAMIS), and persists
**violations** plus **closure (compliance) events** derived from the `action`
column — the focus being restaurants **Closed by DOHMH**.

It follows a proven property-intel architecture (async `httpx` client with
retry/backoff, parallel batch fetch, adapter pattern, identity resolution,
per-record SAVEPOINTs, ingestion-run observability), adapted from buildings to
restaurants.

## Architecture

| Piece | File |
|------|------|
| Env config (`SCOUTEATS_*`) | [config.py](scouteats_intel/config.py) |
| Async Socrata client + `FetchSpec` | [socrata.py](scouteats_intel/socrata.py) |
| Normalization (ids, BBL, dates, closure status) | [normalize.py](scouteats_intel/normalize.py) |
| ORM models (JSONB on Postgres) | [models.py](scouteats_intel/models.py) |
| Adapter base + DOHMH adapter | [adapters/](scouteats_intel/adapters/) |
| Identity resolution + persistence | [persistence.py](scouteats_intel/persistence.py) |
| Hydration pipeline + parallel rehydrate | [hydration.py](scouteats_intel/hydration.py) |
| FastAPI app | [api.py](scouteats_intel/api.py) |
| CLI | [scripts/ingest_closed.py](scripts/ingest_closed.py) |

**Closure detection.** SoQL `like` is case-sensitive, so closures are matched
with `lower(action) like '%closed by dohmh%'`, which catches both
*"Establishment Closed by DOHMH…"* and *"Establishment re-closed by DOHMH."*

**Socrata client methods:** `fetch_where` (single page, with `$select`
projection), `fetch_all` (paginated bulk), `fetch_many` (parallel batch over one
shared client via `asyncio.gather(..., return_exceptions=True)`).

**Identity resolution.** `resolve_establishment` matches by identifier
(CAMIS → BIN → BBL), then by (name, address); on a hit it hydrates only missing
(null) fields and never overwrites existing values.

**Rehydrate** (`force_rehydrate`) is a two-phase parallel refresh: phase 1 fans
out every adapter's CAMIS lookup in one `fetch_many` batch (full inspection
history); phase 2 is reserved for enrichment queries that depend on phase-1
output (e.g. keyed by BBL).

## Setup

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # optional; defaults work out of the box
```

Defaults to local **SQLite** (zero setup). For JSONB columns, point
`SCOUTEATS_DATABASE_URL` at Postgres (psycopg3):
`postgresql+psycopg://user:pass@localhost:5432/scouteats`.

## CLI

```bash
python -m scripts.ingest_closed ingest --limit 500     # bulk closed ingest
python -m scripts.ingest_closed search "NANCY'S RESTAURANT"
python -m scripts.ingest_closed rehydrate 1            # parallel full-history refresh
```

## API

```bash
uvicorn scouteats_intel.api:app --reload --port 8099
```

| Method & path | Purpose |
|---|---|
| `GET /establishments/search?q=&limit=&closed_only=` | DB first; inline-hydrates from Socrata on a miss, then re-queries |
| `GET /establishments/{id}` | establishment detail |
| `GET /establishments/{id}/violations` | normalized violations |
| `GET /establishments/{id}/compliance` | closure / re-open events |
| `POST /establishments/{id}/rehydrate` | parallel full-history refresh |
| `GET /ingestion/sources` · `GET /ingestion/runs` | registry & run log |
| `POST /ingestion/run/dohmh_inspections?limit=` | bulk closed ingest |

Data source: NYC DOHMH via NYC OpenData (`43nn-pn8j`).
