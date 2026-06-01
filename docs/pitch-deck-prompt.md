# Pitch-deck prompt — ScoutEats

Paste everything below the line into a new Claude conversation (Cowork / Projects)
to generate the pitch deck. Edit the bracketed `[...]` fields first.

---

You are an expert startup pitch-deck writer and product storyteller. Help me
create a compelling investor/hackathon pitch deck for **ScoutEats**. Work
slide-by-slide: for each slide give a punchy headline, 2–4 tight bullets (or a
one-line narrative), and a short "visual / speaker note." Keep it concrete and
data-driven — no filler buzzwords. Ask me clarifying questions only if something
material is missing.

## One-liner
ScoutEats turns NYC's public restaurant health-inspection record into one calm,
searchable feed — surfacing every restaurant the city has **Closed by DOHMH**,
plus the violations behind it, before you decide where to eat (or where to lease).

## The problem
- NYC publishes ~265k restaurant inspection violation records, but the raw data
  (NYC OpenData dataset `43nn-pn8j`) is a sprawling CSV/SoQL API that ordinary
  people can't navigate.
- The single most important signal — *was this place shut down by the health
  department?* — is buried in a free-text `action` column, not a clean flag.
- Diners, prospective restaurateurs, and journalists have no friendly way to ask
  "which restaurants near me got closed, and why?"

## The solution / product
A web app + backend that:
- Ingests the live DOHMH inspection dataset, normalizes it, and **deduplicates
  ~265k violation rows into one record per restaurant** (keyed by CAMIS).
- Detects closures from the messy `action` text ("Establishment Closed by
  DOHMH…" and "re-closed"), tags each restaurant `is_closed`, and derives a
  **risk level** (low/medium/high) from its critical-violation count.
- Groups violations into human categories (pests, temperature, hygiene, food
  protection, equipment, administrative).
- Presents it as a searchable, filterable feed: search, risk level, **closed by
  DOHMH** toggle, critical-only, violation category, borough, and minimum
  violations — plus charts (violations by borough, restaurants by category) and
  a card grid with closed badges and cuisine.

## How it works (architecture — for the "how" / technical slide)
- **Frontend:** React (TanStack Start + Vite + shadcn/ui + Recharts), client-side
  filtering and pagination over the full dataset.
- **Backend ("ScoutEats Intel"):** async Python scraper of NYC's Socrata API
  (`httpx`, retry/backoff, parallel batch fetch), an adapter pattern per dataset,
  identity resolution/dedup, per-record fault isolation, SQLAlchemy 2.0 +
  PostgreSQL (JSONB) / SQLite, and a FastAPI service.
- **Unified data layer:** a `/listings` endpoint **merges three sources, deduped
  by CAMIS** — the live Socrata feed, a full CSV-derived snapshot (~27k
  restaurants, all actions), and a curated closed-restaurant list — tagging each
  record with provenance (`sources`).

## Traction / proof points (from a working build — label as a dev snapshot)
- Source: 265,703 violation rows; 27,223 unique restaurants across all 5 boroughs.
- Live closed-ingest pulled **11,931 closure rows → 1,251 unique closed
  restaurants** (10,650 "Closed by DOHMH" + 1,281 "re-closed").
- Unified feed: **27,219 restaurants, 1,252 flagged closed**, sorted closed-first.
- Closed-restaurant risk mix: ~1,120 high / 121 medium / 10 low.
- Closed by borough: Brooklyn 431, Manhattan 369, Queens 311, Bronx 109,
  Staten Island 29.
- End-to-end working: live API → backend → frontend, fully built and verified.

## Who it's for (market / use cases)
- **Diners** — "know before you go."
- **Aspiring restaurateurs / real estate** — closed restaurants are soon-to-be
  **available commercial spaces** (the original "scout a space before it lists"
  angle).
- **Journalists & civic-tech** — fast lens on food-safety enforcement.
- **Adjacent expansion:** any city with open inspection data; other DOHMH/DOB/HPD
  datasets via the same adapter pattern (BIN/BBL enrichment is already scaffolded).

## Differentiation
- Built directly on **authoritative, free public data** — no scraping reviews or
  guesswork.
- Turns an unusable free-text field into a **clean, filterable closure signal**.
- A real **data pipeline + API**, not a static dashboard — refreshable and
  extensible to new datasets/cities.

## Business / roadmap angles (offer options, don't overstate)
- Possible models: B2C freemium alerts ("notify me if a place near me is
  closed"), B2B data/API for real-estate & food-service tooling, civic/press
  licensing.
- Roadmap: geo/map view, "available space" lead-gen for brokers, multi-city,
  enrichment via building datasets, historical closure trends.

## My specifics to weave in
- Audience: [investors / hackathon judges / accelerator — pick one]
- Deck length: [10–12 slides]
- Tone: [confident & technical / consumer-friendly / civic-minded]
- Team / who's presenting: [names + roles]
- The ask: [funding amount / prize / next milestone — or "none, demo only"]
- Brand vibe: dark, "live signal / radar" aesthetic, mint-green accent, mono
  type. Name: **ScoutEats** — tagline "know before you go."

## Deliverable
Produce the full deck slide-by-slide (suggested flow: Title → Problem → Solution
→ Product/Demo → How it works → Data & traction → Market → Differentiation →
Business model → Roadmap → Team → Ask). After the outline, give me a tight
30-second verbal pitch and 3 likely tough questions with crisp answers.
