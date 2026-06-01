import { Search, SlidersHorizontal, X } from "lucide-react";
import {
  CATEGORY_LABELS,
  CATEGORY_OPTIONS,
  RISK_LABELS,
  BOROUGHS,
} from "@/data/listings";
import type { ViolationCategory } from "@/data/listings";
import {
  type FilterState,
  type RiskPreset,
  VIOLATION_BOUNDS,
  defaultFilters,
} from "@/hooks/useFilteredListings";

const RISK_CHIPS: { value: RiskPreset; label: string }[] = [
  { value: "all", label: "Any" },
  { value: "high", label: RISK_LABELS.high },
  { value: "medium", label: RISK_LABELS.medium },
  { value: "low", label: RISK_LABELS.low },
];

interface Props {
  filters: FilterState;
  setFilters: (f: FilterState) => void;
  resultCount: number;
  totalCount: number;
}

export function FiltersBar({ filters, setFilters, resultCount, totalCount }: Props) {
  const toggleCategory = (c: ViolationCategory) => {
    const has = filters.categories.includes(c);
    setFilters({
      ...filters,
      categories: has
        ? filters.categories.filter((x) => x !== c)
        : [...filters.categories, c],
    });
  };

  const reset = () => setFilters({ ...defaultFilters, query: filters.query });

  return (
    <div className="sticky top-0 z-30 border-y border-hairline bg-background/85 backdrop-blur-xl">
      <div className="mx-auto max-w-6xl px-6 py-4">
        {/* search */}
        <div className="relative">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={filters.query}
            onChange={(e) => setFilters({ ...filters, query: e.target.value })}
            placeholder="Search restaurant, address, or ZIP…"
            className="w-full rounded-full hairline bg-surface/70 py-3 pl-11 pr-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-mint/40"
          />
        </div>

        {/* risk chips */}
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            risk&nbsp;level
          </span>
          {RISK_CHIPS.map((c) => {
            const active = filters.risk === c.value;
            return (
              <button
                key={c.value}
                onClick={() => setFilters({ ...filters, risk: c.value })}
                className={`rounded-full px-3 py-1.5 font-mono text-xs transition-all ${
                  active
                    ? "bg-mint text-mint-foreground"
                    : "hairline bg-surface/50 text-foreground/80 hover:bg-surface"
                }`}
              >
                {c.label}
              </button>
            );
          })}
          <button
            onClick={() =>
              setFilters({ ...filters, criticalOnly: !filters.criticalOnly })
            }
            className={`ml-1 rounded-full px-3 py-1.5 font-mono text-xs transition-all ${
              filters.criticalOnly
                ? "bg-coral text-coral-foreground"
                : "hairline bg-surface/50 text-foreground/80 hover:bg-surface"
            }`}
          >
            critical only
          </button>
        </div>

        {/* violation categories */}
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
            violations
          </span>
          {CATEGORY_OPTIONS.map((c) => {
            const active = filters.categories.includes(c);
            return (
              <button
                key={c}
                onClick={() => toggleCategory(c)}
                className={`rounded-full px-3 py-1.5 text-xs transition-all ${
                  active
                    ? "bg-coral text-coral-foreground"
                    : "hairline bg-surface/50 text-foreground/80 hover:bg-surface"
                }`}
              >
                {CATEGORY_LABELS[c]}
              </button>
            );
          })}
        </div>

        {/* borough + min violations */}
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
              borough
            </label>
            <select
              value={filters.borough ?? ""}
              onChange={(e) =>
                setFilters({ ...filters, borough: e.target.value || null })
              }
              className="mt-1 w-full rounded-lg hairline bg-surface/70 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-mint/40"
            >
              <option value="">All boroughs</option>
              {BOROUGHS.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between">
              <label className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                min&nbsp;violations
              </label>
              <span className="font-mono text-[11px] text-foreground/90">
                {filters.minViolations}+
              </span>
            </div>
            <input
              type="range"
              min={VIOLATION_BOUNDS[0]}
              max={VIOLATION_BOUNDS[1]}
              step={1}
              value={filters.minViolations}
              onChange={(e) =>
                setFilters({ ...filters, minViolations: Number(e.target.value) })
              }
              className="mt-3 w-full accent-mint"
            />
          </div>
        </div>

        {/* result count + reset */}
        <div className="mt-4 flex items-center justify-between border-t border-hairline pt-3">
          <div className="flex items-center gap-2 font-mono text-xs text-muted-foreground">
            <SlidersHorizontal className="h-3.5 w-3.5 text-mint" />
            <span>
              <span className="text-mint">{resultCount.toLocaleString()}</span>
              <span className="mx-1">/</span>
              <span>{totalCount.toLocaleString()}</span> restaurants
            </span>
          </div>
          <button
            onClick={reset}
            className="inline-flex items-center gap-1.5 rounded-full hairline px-3 py-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
            Reset filters
          </button>
        </div>
      </div>
    </div>
  );
}
