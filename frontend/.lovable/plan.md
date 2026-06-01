# LeaseUp — Plan

A frontend-only single-page app for discovering commercial/cafe spaces with expiring leases or violations. No backend; mock data in React state. Cyber-terminal structure balanced 50/50 with warm community feel.

## Design system (set in `src/styles.css`)

- Background: near-black charcoal `#0D0F12` with faint grid + scanline overlay and ambient teal glow.
- Accents: electric mint `#3DF5C5` (cyber), warm coral `#FF8A5B` (community).
- Typography: Geist (sans) for headings/body, Geist Mono for all data (dates, sqft, prices, codes, counts). Loaded via Google Fonts in `__root.tsx` head.
- Cards: ~16px radius, hairline borders (1px, low-opacity mint), soft shadows, hover lift + mint glow.
- Tokens added: `--background`, `--foreground`, `--accent-mint`, `--accent-coral`, `--surface`, `--hairline`, `--urgency-red/amber/mint`, mono font family. All components use semantic tokens — no raw hex in JSX.
- Motion: smooth scroll, fade/slide-in on viewport enter (IntersectionObserver-based small hook), animated grid/particle hero background (CSS + light canvas or pure CSS scanlines + drifting dots).

## Page structure (single scrolling route at `/`)

Replace placeholder in `src/routes/index.tsx`. Compose from components under `src/components/leaseup/`:

1. `Hero.tsx` — bold headline, one-line subhead, animated grid/scanline background, primary "Start scanning" CTA that smooth-scrolls to `#search`. Mono trust line: "1,240 spaces tracked across 38 neighborhoods."
2. `About.tsx` — 2–3 sentence description + 3 value props in a row (icons + short labels).
3. `FiltersBar.tsx` — sticky on scroll (`position: sticky; top: 0`). Contains:
   - Lease end chips: `<30d`, `<90d`, `<6mo`, `<1y`, custom range (date pickers).
   - Violation type multi-select chips.
   - Neighborhood searchable dropdown (Command/Popover from shadcn).
   - Size sqft range slider.
   - Price range slider.
   - Live results count in mono.
4. `SearchResults.tsx` — search input (address/neighborhood/keyword) + responsive card grid (`ListingCard.tsx`). Card: photo, address, lease-status label, type, sqft (mono), price (mono), urgency countdown badge (red/amber/mint by days remaining). Hover: lift + mint glow. No contact button.
5. `Footer.tsx` — community-tone tagline + app name.

## Data + filtering

- `src/data/listings.ts`: 12 mock listings with `id, address, neighborhood, type (cafe|retail|office|flex), sqft, monthlyPrice, leaseEndDate, violationTypes[], status, imageUrl`.
- Photos: Unsplash source URLs (no asset generation needed).
- `src/hooks/useFilteredListings.ts`: takes listings + filter state, returns filtered list and count. Pure function — runs on every state change.
- Filter state lifted into `index.tsx` (or a small context if cleaner) so FiltersBar + SearchResults share it.
- Urgency badge derived from `daysUntil(leaseEndDate)`: <30 red, <90 amber, else mint.

## Animations

- `useInView` small hook (IntersectionObserver) → adds `animate-fade-in` / slide-in class on enter.
- Hero background: CSS grid pattern + animated scanline + a few drifting particles (CSS keyframes, no heavy lib).
- `scroll-behavior: smooth` on `html`.

## Tech notes

- TanStack Start route `/` only. Update head meta (title "LeaseUp — Find your next space first", description, og tags).
- Tailwind v4 via existing `src/styles.css`; extend `@theme inline` with new tokens.
- Mobile responsive: filters collapse into a Sheet/drawer on small screens; card grid 1 → 2 → 3 cols.
- No backend, no auth, no Lovable Cloud.

## File changes

- Edit: `src/styles.css`, `src/routes/index.tsx`, `src/routes/__root.tsx` (fonts + smooth scroll).
- Create: `src/data/listings.ts`, `src/hooks/useInView.ts`, `src/hooks/useFilteredListings.ts`, `src/components/leaseup/{Hero,About,FiltersBar,SearchResults,ListingCard,Footer}.tsx`.

Ready to build on approval.