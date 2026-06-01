// Domain types for NYC DOHMH restaurant inspection data.
// Records are produced by build_listings.py at the repo root and served from
// /data/inspections.json (one object per restaurant / CAMIS).

export type RiskLevel = "low" | "medium" | "high";

export type ViolationCategory =
  | "pests"
  | "temperature"
  | "hygiene"
  | "food-protection"
  | "equipment"
  | "administrative";

export interface Listing {
  id: string;
  name: string;
  address: string;
  borough: string;
  zip: string;
  lat: number | null;
  lng: number | null;
  violations: number;
  critical: number;
  categories: ViolationCategory[];
  risk: RiskLevel;
  lastInspection: string | null;
  // Present when served by the backend merge of multiple datasets.
  cuisine?: string | null;
  grade?: string | null;
  is_closed?: boolean;
  sources?: string[];
}

export const BOROUGHS = [
  "Manhattan",
  "Brooklyn",
  "Queens",
  "Bronx",
  "Staten Island",
] as const;

export const CATEGORY_LABELS: Record<ViolationCategory, string> = {
  pests: "Pests & vermin",
  temperature: "Temperature control",
  hygiene: "Personal hygiene",
  "food-protection": "Food protection",
  equipment: "Equipment & plumbing",
  administrative: "Administrative",
};

export const CATEGORY_OPTIONS: ViolationCategory[] = [
  "pests",
  "temperature",
  "hygiene",
  "food-protection",
  "equipment",
  "administrative",
];

export const RISK_LABELS: Record<RiskLevel, string> = {
  low: "Low risk",
  medium: "Watch",
  high: "High risk",
};
