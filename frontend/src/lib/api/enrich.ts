// Client for the backend POST /analysis/enrich endpoint.
//
// The wire contract is the `EnrichResponse` envelope: a strictly
// schema-conformant `card` (https://scouteats/analysis-card.schema.json) plus
// sibling envelope fields (risk_assessment, takeover, enrichment) that hold all
// AI/derived data. Nothing AI/derived ever lives inside `card`.
//
// This module also ships a CLIENT-SIDE fallback (`localFallbackEnrich`) that
// synthesizes the same envelope deterministically from a Listing so the modal
// still works in static-snapshot mode (VITE_API_URL === "") or when the backend
// is unreachable.

import type { Listing, RiskLevel, ViolationCategory } from "@/data/listings";
import { CATEGORY_LABELS } from "@/data/listings";

// Same base-URL pattern as useListings.ts.
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8099";

// ----- AnalysisCardPayload (per the JSON Schema, additionalProperties:false) ---

export type SourceTag = "socrata_live" | "dohmh_csv" | "manhattan_closed";

export interface RestaurantIdentity {
  camis?: string | null;
  name?: string | null;
  address?: string | null;
  borough?: string | null;
  zip?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  cuisine?: string | null;
}

export interface CategoryBreakdown {
  category: string;
  count: number;
}

export interface CardSummary {
  total_violations: number;
  critical_violations: number;
  risk: RiskLevel;
  is_closed: boolean;
  categories?: string[];
  category_breakdown?: CategoryBreakdown[];
  latest_grade?: string | null;
  latest_score?: number | null;
  last_inspection_date?: string | null;
  last_closure_date?: string | null;
}

export interface ViolationDetail {
  code: string;
  category: string;
  severity?: string | null;
  status?: string | null;
  description?: string | null;
  inspection_type?: string | null;
  issue_date?: string | null;
}

export interface ComplianceEventDetail {
  event_type: string;
  event_date?: string | null;
  action_text?: string | null;
}

export interface AnalysisCardPayload {
  $schema?: string;
  restaurant: RestaurantIdentity;
  summary: CardSummary;
  violations?: ViolationDetail[];
  compliance_events?: ComplianceEventDetail[];
  sources?: SourceTag[];
}

// ----- EnrichResponse envelope -------------------------------------------------

export type EnrichSource = "codify.cafe" | "local_fallback";

export interface RiskAssessment {
  source: EnrichSource;
  available: boolean;
  risk: RiskLevel | null;
  score: number | null;
  rationale: string | null;
  degraded_reason: string | null;
  raw: Record<string, unknown> | null;
}

export type TakeoverStepCategory =
  | "remediation"
  | "permit"
  | "inspection"
  | "legal"
  | "financial"
  | "general";

export interface TakeoverStep {
  order: number;
  title: string;
  detail: string;
  category: TakeoverStepCategory | null;
  related_violation_categories: string[];
}

export interface Takeover {
  headline: string;
  summary: string;
  steps: TakeoverStep[];
  codify_url: string;
  source: EnrichSource;
}

export interface EnrichmentMeta {
  matched: boolean;
  hydrated: boolean;
  db_violations: number;
  db_compliance_events: number;
  degraded: boolean;
  notes: string[];
}

export interface EnrichResponse {
  card: AnalysisCardPayload;
  risk_assessment: RiskAssessment;
  takeover: Takeover;
  enrichment: EnrichmentMeta;
}

const SCHEMA_ID = "https://scouteats/analysis-card.schema.json";
const VALID_SOURCES: SourceTag[] = [
  "socrata_live",
  "dohmh_csv",
  "manhattan_closed",
];

function isSourceTag(s: string): s is SourceTag {
  return (VALID_SOURCES as string[]).includes(s);
}

/**
 * Map a frontend Listing onto the request AnalysisCardPayload. Summary-only
 * (no violations/compliance_events) is valid per the schema.
 */
export function listingToPayload(listing: Listing): AnalysisCardPayload {
  const sources = (listing.sources ?? []).filter(isSourceTag);

  return {
    $schema: SCHEMA_ID,
    restaurant: {
      camis: listing.id,
      name: listing.name,
      address: listing.address || null,
      borough: listing.borough || null,
      zip: listing.zip || null,
      latitude: listing.lat,
      longitude: listing.lng,
      cuisine: listing.cuisine ?? null,
    },
    summary: {
      total_violations: listing.violations,
      critical_violations: listing.critical,
      risk: listing.risk,
      is_closed: Boolean(listing.is_closed),
      categories: listing.categories,
      // The Listing carries no per-category counts, so leave the breakdown
      // empty — the backend recomputes it from hydrated data.
      category_breakdown: [],
      latest_grade: listing.grade ?? null,
      last_inspection_date: listing.lastInspection,
    },
    sources: sources.length > 0 ? sources : undefined,
  };
}

/**
 * POST the payload to the backend and return the EnrichResponse envelope.
 * Falls back to a deterministic client-side envelope when there is no API URL
 * (static-snapshot mode) or the request fails for any reason.
 */
export async function enrichListing(listing: Listing): Promise<EnrichResponse> {
  if (!API_URL) return localFallbackEnrich(listing);

  try {
    const res = await fetch(`${API_URL}/analysis/enrich`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(listingToPayload(listing)),
    });
    if (!res.ok) throw new Error(`enrich failed (${res.status})`);
    return (await res.json()) as EnrichResponse;
  } catch {
    return localFallbackEnrich(listing);
  }
}

// ----- Deterministic client-side fallback -------------------------------------

function categoryLabel(c: string): string {
  return CATEGORY_LABELS[c as ViolationCategory] ?? c;
}

function codifyUrl(camis: string): string {
  return `https://codify.cafe/restaurants/${encodeURIComponent(camis)}`;
}

/**
 * Build the same EnrichResponse envelope entirely on the client, with no
 * network. Steps are derived deterministically from the listing's closure
 * status, top violation categories, and risk level. `steps` is always
 * non-empty.
 */
export function localFallbackEnrich(listing: Listing): EnrichResponse {
  const card = listingToPayload(listing);
  const isClosed = Boolean(listing.is_closed);
  const categories = listing.categories ?? [];

  const steps: TakeoverStep[] = [];
  let order = 1;
  const push = (s: Omit<TakeoverStep, "order">) =>
    steps.push({ order: order++, ...s });

  if (isClosed) {
    push({
      title: "Confirm the DOHMH closure status",
      detail:
        "This establishment was closed by DOHMH. Pull the full inspection " +
        "history and confirm the closure has not already been resolved or " +
        "re-opened before pursuing a takeover.",
      category: "inspection",
      related_violation_categories: [],
    });
    push({
      title: "Remediate the closure-triggering violations",
      detail:
        "Address every condition cited at the closing inspection. A re-" +
        "inspection must pass before the location can legally operate again.",
      category: "remediation",
      related_violation_categories: categories,
    });
  }

  // One remediation step per top violation category (cap at 3 to keep focused).
  for (const c of categories.slice(0, 3)) {
    push({
      title: `Remediate ${categoryLabel(c)} violations`,
      detail: `Resolve outstanding "${categoryLabel(
        c,
      )}" findings and document the corrective action for the next inspection.`,
      category: "remediation",
      related_violation_categories: [c],
    });
  }

  push({
    title: "Negotiate the lease assignment or new lease",
    detail:
      "Work with the landlord to assign the existing lease or sign a new one. " +
      "Confirm there are no outstanding liens or back rent tied to the space.",
    category: "legal",
    related_violation_categories: [],
  });
  push({
    title: "Transfer or obtain DOHMH permits",
    detail:
      "Apply for or transfer the Food Service Establishment permit and any " +
      "supporting permits (e.g. tobacco, sidewalk cafe) under the new operator.",
    category: "permit",
    related_violation_categories: [],
  });
  push({
    title: "Budget for remediation and re-inspection",
    detail:
      "Estimate the capital needed to clear violations, pass re-inspection, " +
      "and cover permit and legal fees before reopening.",
    category: "financial",
    related_violation_categories: [],
  });
  push({
    title: "Schedule a DOHMH re-inspection",
    detail:
      "Once corrections are complete, request a re-inspection to restore an " +
      "operating grade.",
    category: "inspection",
    related_violation_categories: [],
  });

  const riskWord: Record<RiskLevel, string> = {
    high: "high-risk",
    medium: "watch-list",
    low: "low-risk",
  };
  const summary =
    `${listing.name} is a ${riskWord[listing.risk]} location with ` +
    `${listing.violations} recorded violation${
      listing.violations === 1 ? "" : "s"
    } (${listing.critical} critical)` +
    (isClosed ? ", currently closed by DOHMH." : ".") +
    (categories.length > 0
      ? ` Top issues: ${categories.map(categoryLabel).join(", ")}.`
      : "");

  return {
    card,
    risk_assessment: {
      source: "local_fallback",
      available: true,
      risk: listing.risk,
      score: null,
      rationale: `Risk derived locally from ${listing.critical} critical violation${
        listing.critical === 1 ? "" : "s"
      } across ${listing.violations} total.`,
      degraded_reason: API_URL
        ? "codify.cafe assessment unavailable — using local risk."
        : "Static-snapshot mode — no backend configured.",
      raw: null,
    },
    takeover: {
      headline: `Steps to take over ${listing.name}`,
      summary,
      steps,
      codify_url: codifyUrl(listing.id),
      source: "local_fallback",
    },
    enrichment: {
      matched: false,
      hydrated: false,
      db_violations: 0,
      db_compliance_events: 0,
      degraded: true,
      notes: [
        API_URL
          ? "Backend unreachable — enriched locally on the client."
          : "Static-snapshot mode — enriched locally on the client.",
      ],
    },
  };
}
