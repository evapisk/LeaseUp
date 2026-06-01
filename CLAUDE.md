# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**ScoutEats** — a NYC restaurant health-inspection explorer. It combines the NYC
DOHMH Restaurant Inspection Results dataset (Socrata `43nn-pn8j`) with a React
frontend (reskinned from the `space-scout` property app) into a searchable,
filterable visualization of restaurant violations, with a focus on restaurants
**Closed by DOHMH**.

> This `poc_hack/` repo is a standalone proof-of-concept. It is *not* part of the
> P2X/Codify ecosystem described in the parent `~/Desktop/CLAUDE.md` — that file's
> tenancy/deploy/module conventions do **not** apply here.

Two independent halves:

| Half | Stack | Dir | Dev port |
|------|-------|-----|----------|
| **Backend** (`scouteats_intel`) | FastAPI + SQLAlchemy 2.0 + async httpx | `backend/` | 8099 |
| **Frontend** | TanStack Start + Vite 7 + React 19 + shadcn/ui + Tailwind v4 | `frontend/` | 8080 |

The frontend talks to the backend's `GET /listings` (via `VITE_API_URL`, default
`http://localhost:8099`); with `VITE_API_URL=""` it falls back to the static
`frontend/public/data/inspections.json` snapshot built by `build_listings.py`.

## Commands

```bash
# Backend (from backend/)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn scouteats_intel.api:app --reload --port 8099   # API
python -m scripts.ingest_closed ingest --limit 500     # bulk closed ingest (CLI)
python -m scripts.ingest_closed search "NANCY'S RESTAURANT"
python -m scripts.ingest_closed rehydrate 1            # parallel full-history refresh

# Frontend (from frontend/)
npm install
npm run dev        # http://localhost:8080
npm run build
npm run lint       # eslint
npm run format     # prettier

# Data (from repo root) — regenerate the static snapshot from the CSV
python3 build_listings.py     # writes frontend/public/data/inspections.json
```

There is **no test suite** in this repo (neither pytest nor a frontend test runner is configured).

## Backend architecture (`backend/scouteats_intel/`)

A "scraper + identity-resolution + enrichment" pipeline adapted from a property-intel
design (buildings → restaurants). Data flows: **Socrata → adapter normalize → identity
resolve → persist (establishment + violations + compliance events)**.

- **`socrata.py`** — async httpx client with linear-backoff retry. Three fetch modes:
  `fetch_where` (one page, `$select` projection), `fetch_all` (paginated bulk),
  `fetch_many` (parallel batch over one shared client via `asyncio.gather(...,
  return_exceptions=True)`). Always use it as `async with SocrataClient() as client:`
  so the connection pool is shared.
- **`adapters/`** — `BaseSourceAdapter` maps one Socrata dataset to the models. The only
  concrete one is `DohmhInspectionsAdapter`. **One Socrata row = one cited violation**;
  rows whose `action` marks a closure also emit a compliance event. The natural key is
  `(camis, inspection_date, violation_code)`. `ADAPTERS` / `ADAPTERS_BY_KEY` in
  `adapters/__init__.py` are the registry the pipeline iterates.
- **`persistence.py`** — `persist_record` writes each row inside a `begin_nested()`
  SAVEPOINT so one bad row can't fail the batch. `resolve_establishment` matches by
  identifier (CAMIS → BIN → BBL) then by `(name, address)`; **on a hit it only hydrates
  null fields and never overwrites existing values**. Raw payloads are upserted with a
  checksum for change detection.
- **`hydration.py`** — three entry points: `hydrate_query` (inline on a search miss),
  `ingest_closed` (bulk), `force_rehydrate` (two-phase parallel refresh of one CAMIS's
  full history). Every run is logged to `scouteats_ingestion_run` for observability.
- **`api.py`** — FastAPI app. Key behavior: `GET /establishments/search` queries the DB
  first and **inline-hydrates from Socrata on a miss**, then re-queries. `GET /listings`
  is the frontend's feed: it merges live Socrata establishments with the two local
  datasets and dedupes (see below).
- **`local_sources.py`** — merges three pools into the frontend "listing" shape, deduped
  by CAMIS: `socrata_live` (DB), `dohmh_csv` (`inspections.json`), `manhattan_closed`
  (`MANHATTAN_CLOSED.json`). Merge rules: `is_closed` OR'd, violation/critical counts
  `max`'d, categories/sources unioned, scalars first-non-null, risk recomputed.
- **`models.py` / `db.py`** — SQLAlchemy 2.0 (`Mapped[...]`). `JSONColumn` is JSONB on
  Postgres, plain JSON on SQLite. **Defaults to local SQLite** (`scouteats.db`,
  zero-setup); point `SCOUTEATS_DATABASE_URL` at Postgres for JSONB. Tables are created
  via `init_db()` on startup — no Alembic migrations.

Config is env-driven via pydantic-settings with the **`SCOUTEATS_` prefix** (`config.py`).

### Violation taxonomy — duplicated, keep in sync

NYC violation codes are bucketed by their leading two digits into categories
(`pests`, `temperature`, `hygiene`, `food-protection`, `equipment`,
`administrative`) and a risk level (`low`/`medium`/`high` from the critical count).
This mapping exists in **two places** that must stay identical:
`backend/scouteats_intel/normalize.py` (`_PREFIX_CATEGORY`, `category_for_code`,
`risk_for`) and `build_listings.py` (`PREFIX_CATEGORY`, `category_for`, `risk_for`).
Closure detection lives only in `normalize.closure_status` (matches
`closed by dohmh` / `re-closed` / `re-opened`).

## Frontend architecture (`frontend/`)

- **TanStack Start** (file-based routing in `src/routes/`, SSR via `src/server.ts`). Built
  with **Vite 7** through `@lovable.dev/vite-tanstack-config` — that wrapper already
  registers tanstackStart, React, Tailwind v4, tsconfig-paths, nitro, and VITE_ env
  injection. **Do not re-add those plugins** in `vite.config.ts` or the build breaks.
- **Server logic** uses `createServerFn` (see `src/lib/api/example.functions.ts`), not edge
  functions. Server-only values go in `*.server.ts` files (e.g. `config.server.ts`); read
  `process.env` *inside* handlers, never at module scope. Anything client-readable must use
  the `VITE_` prefix via `import.meta.env`.
- **Data loading**: `src/hooks/useListings.ts` fetches the unified feed (TanStack Query,
  cached forever). `useFilteredListings.ts` applies the search/risk/category/borough/min-
  violations filters. The listing shape is defined in `src/data/listings.ts`.
- UI: shadcn/ui primitives in `src/components/ui/`, app components in
  `src/components/leaseup/` (Hero, FiltersBar, SearchResults, ListingCard, StatsBar — the
  `leaseup` name is a holdover from the space-scout origin).

## Data files (repo root)

- `DOHMH_..._useful.csv` (~41 MB, one row per violation) — source for `build_listings.py`.
- `MANHATTAN_CLOSED.json`, `CITY_CLOSED.csv` — closed-restaurant lists.
- `frontend/public/data/inspections.json` — **generated** per-restaurant aggregate
  (~27k records) consumed by the frontend fallback and merged into `/listings`.
- `filter_dohmh_by_year.py`, `dohmh_closed_restaurant_rows.py` — one-off CSV slimming
  scripts.

## Analysis-card enrichment + lease-takeover feature

`POST /analysis/enrich` accepts an **`AnalysisCardPayload`** (one restaurant card, schema
id `https://scouteats/analysis-card.schema.json`; `restaurant` + `summary` required,
violations/compliance optional), enriches it, and returns an **`EnrichResponse` envelope**:

```
{ card, risk_assessment, takeover, enrichment }
```

The `card` is the **same schema, re-validated** — because the schema is
`additionalProperties: false`, no AI/derived data may live inside it. The takeover steps,
AI risk, and run metadata live in the sibling envelope fields. The frontend renders
`takeover.steps` in a modal when a card is clicked.

**Backend pipeline** (`enrichment.enrich_card`, all reusing existing code):
resolve establishment by CAMIS → name+address → **hydrate from Socrata when thin**
(`force_rehydrate`/`hydrate_query`) → rebuild the authoritative summary from the DB
(DB overrides submitted values; submitted survives only where DB is empty) → assemble
`ViolationDetail[]`/`ComplianceEventDetail[]` → **call codify.cafe for AI risk + steps** →
fall back to a deterministic local plan → stamp `generated_at`/`sources`/`dataset_id`.

| File | Role |
|------|------|
| `schemas.py` | Pydantic models for the card (matches the JSON Schema exactly; `extra="ignore"` → lenient input, strict output) + envelope models. |
| `enrichment.py` | The pipeline. **Does not import `api.py`** (avoids a cycle) — maps ORM models → schema models directly. |
| `codify_client.py` | Async httpx client for **codify.cafe = the P2X Laravel `api/`** (`POST /api/pipes/invoke`, `pipe_name=restaurant_lease_takeover`; subproject resolved via `/api/internal/resolve-subproject`). Mirrors `socrata.py` (shared client, retry/backoff). Raises `CodifyUnavailable`. |
| `takeover.py` | `build_fallback_plan(card)` — deterministic, **always non-empty** steps derived from closure status + violation categories + permit/re-inspection/lease/financial. `codify_url(camis)` deep link. |
| `normalize.py` | `category_breakdown`, `canonical_borough` (added; taxonomy stays single-sourced). |

**Graceful degradation is load-bearing** — the endpoint never 5xx's on a codify/Socrata
failure (422 only for a malformed body). codify down → `local_fallback`; backend down or
`VITE_API_URL=""` → the frontend's `localFallbackEnrich` synthesizes the same envelope
client-side. codify is **off unless `SCOUTEATS_CODIFY_TOKEN` is set** (see `.env.example`
for the `SCOUTEATS_CODIFY_*` vars); without it you always get the local plan.

**Frontend** (`src/`): `lib/api/enrich.ts` (types, `listingToPayload`, `enrichListing`,
`localFallbackEnrich`), `hooks/useEnrichCard.ts` (TanStack Query, enabled when modal open),
`components/leaseup/TakeoverModal.tsx` (shadcn Dialog: risk badge, steps, codify.cafe
button), and a clickable `ListingCard.tsx`. The TS types in `enrich.ts` mirror the
envelope — **keep them in sync** with `schemas.py` if the contract changes.
