import { MapPin, AlertTriangle, CalendarDays, ShieldAlert } from "lucide-react";
import type { Listing, RiskLevel } from "@/data/listings";
import { CATEGORY_LABELS, RISK_LABELS } from "@/data/listings";
import { daysSince } from "@/hooks/useFilteredListings";

const RISK_TONE: Record<RiskLevel, string> = {
  high: "bg-urgent/15 text-urgent ring-urgent/40",
  medium: "bg-warn/15 text-warn ring-warn/40",
  low: "bg-mint/10 text-mint ring-mint/30",
};

const RISK_BAR: Record<RiskLevel, string> = {
  high: "from-urgent/40 via-coral/20 to-transparent",
  medium: "from-warn/35 via-warn/10 to-transparent",
  low: "from-mint/30 via-mint/10 to-transparent",
};

function lastInspectionLabel(iso: string | null): string {
  const d = daysSince(iso);
  if (d === null) return "—";
  if (d <= 0) return "today";
  if (d < 45) return `${d}d ago`;
  if (d < 365) return `${Math.round(d / 30)}mo ago`;
  return `${(d / 365).toFixed(1)}y ago`;
}

export function ListingCard({ listing }: { listing: Listing }) {
  const tone = RISK_TONE[listing.risk];

  return (
    <article className="group relative overflow-hidden rounded-2xl hairline bg-surface/60 transition-all duration-300 hover:-translate-y-1 hover:bg-surface hover:glow-mint">
      {/* Risk-coded header (the inspection data has no photos). */}
      <div className="relative aspect-[5/2] overflow-hidden">
        <div className={`absolute inset-0 bg-gradient-to-br ${RISK_BAR[listing.risk]}`} />
        <div className="absolute inset-0 grid-bg opacity-40" />

        <div className="absolute left-3 top-3 inline-flex items-center gap-1.5 rounded-full bg-background/70 px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider text-foreground/90 backdrop-blur">
          <span className="text-mint">●</span> CAMIS {listing.id}
        </div>

        <div
          className={`absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium ring-1 backdrop-blur ${tone}`}
        >
          <ShieldAlert className="h-3 w-3" />
          {RISK_LABELS[listing.risk]}
        </div>

        <div className="absolute bottom-3 left-3 flex items-end gap-2">
          <span className="font-mono text-4xl font-bold leading-none text-foreground/90">
            {listing.violations}
          </span>
          <span className="mb-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            violations
          </span>
        </div>
      </div>

      <div className="p-5">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-foreground">
            {listing.name}
          </h3>
          <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" />
            <span className="truncate">
              {listing.address} · {listing.borough} {listing.zip}
            </span>
          </div>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2 border-t border-hairline pt-4 font-mono text-xs">
          <Stat icon={AlertTriangle} label="critical" value={String(listing.critical)} />
          <Stat icon={ShieldAlert} label="total" value={String(listing.violations)} />
          <Stat
            icon={CalendarDays}
            label="inspected"
            value={lastInspectionLabel(listing.lastInspection)}
            small
          />
        </div>

        {listing.categories.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {listing.categories.map((c) => (
              <span
                key={c}
                className="rounded-full bg-coral/10 px-2 py-0.5 text-[10px] font-medium text-coral ring-1 ring-coral/30"
              >
                {CATEGORY_LABELS[c]}
              </span>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  small = false,
}: {
  icon: typeof MapPin;
  label: string;
  value: string;
  small?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3" /> {label}
      </span>
      <span className={`text-foreground ${small ? "text-[11px]" : "text-sm"}`}>{value}</span>
    </div>
  );
}
