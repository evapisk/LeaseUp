import type { Listing, RiskLevel, ViolationCategory } from "@/data/listings";

export type RiskPreset = "all" | RiskLevel;

export interface FilterState {
  query: string;
  borough: string | null;
  categories: ViolationCategory[];
  risk: RiskPreset;
  criticalOnly: boolean;
  minViolations: number;
}

export const VIOLATION_BOUNDS: [number, number] = [1, 90];

export const defaultFilters: FilterState = {
  query: "",
  borough: null,
  categories: [],
  risk: "all",
  criticalOnly: false,
  minViolations: VIOLATION_BOUNDS[0],
};

export function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  return Math.round((Date.now() - then) / (1000 * 60 * 60 * 24));
}

export function filterListings(listings: Listing[], f: FilterState): Listing[] {
  const q = f.query.trim().toLowerCase();

  return listings.filter((l) => {
    if (q) {
      const hay = `${l.name} ${l.address} ${l.borough} ${l.zip}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (f.borough && l.borough !== f.borough) return false;
    if (f.risk !== "all" && l.risk !== f.risk) return false;
    if (f.criticalOnly && l.critical === 0) return false;
    if (l.violations < f.minViolations) return false;
    if (
      f.categories.length &&
      !f.categories.some((c) => l.categories.includes(c))
    ) {
      return false;
    }
    return true;
  });
}
