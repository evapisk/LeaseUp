# LeaseUp — NYC restaurant inspections, visualized

Combines the **NYC DOHMH restaurant inspection dataset** (this repo) with the
**space-scout** React frontend (pulled from
https://github.com/evapisk/space-scout.git, reskinned as *ScoutEats*) into one
searchable, filterable visualization of restaurant health violations.

## Layout

```
poc_hack/
├── DOHMH_..._useful.csv          # source: one row per violation (265k rows, 5 boroughs)
├── MANHATTAN_CLOSED.json         # source: closed Manhattan restaurants
├── filter_dohmh_by_year.py       # original CSV slimming script
├── build_listings.py             # ← combine step: CSV → frontend JSON
└── frontend/                     # the React app (TanStack Start + Vite + shadcn/ui)
    └── public/data/inspections.json   # generated, consumed by the app
```

## The combine step

`build_listings.py` rolls up the per-violation CSV into **one record per
restaurant** (27,193 total), enriching each with:

- total violation count + critical-violation count
- violation **categories** (pests, temperature, hygiene, food protection,
  equipment, administrative) derived from NYC violation codes
- a **risk level** (low / medium / high) from the critical count
- most recent inspection date and location (borough, ZIP, lat/lng)

Regenerate the dataset:

```bash
python3 build_listings.py
# writes frontend/public/data/inspections.json
```

## Run the frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:8080
npm run build      # production build
```

The app fetches `/data/inspections.json` on load and renders:

- a **hero + about** intro,
- a **filters bar** (search, risk level, critical-only, violation category,
  borough, minimum violations),
- aggregate **charts** (violations by borough, restaurants by violation type),
- a paginated **card grid** of flagged restaurants.

Data source: NYC DOHMH via NYC OpenData.
