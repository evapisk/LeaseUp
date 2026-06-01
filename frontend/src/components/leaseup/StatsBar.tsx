import { useMemo } from "react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";
import type { Listing } from "@/data/listings";
import { CATEGORY_LABELS, CATEGORY_OPTIONS } from "@/data/listings";

// Aggregate visualizations over the currently filtered set: violations by
// borough and restaurants by violation category.
export function StatsBar({ listings }: { listings: Listing[] }) {
  const { byBorough, byCategory, totalViolations, totalCritical } = useMemo(() => {
    const boro = new Map<string, number>();
    const cat = new Map<string, number>();
    let v = 0;
    let c = 0;
    for (const l of listings) {
      boro.set(l.borough, (boro.get(l.borough) ?? 0) + l.violations);
      v += l.violations;
      c += l.critical;
      for (const k of l.categories) cat.set(k, (cat.get(k) ?? 0) + 1);
    }
    return {
      byBorough: [...boro.entries()]
        .map(([name, value]) => ({ name, value }))
        .sort((a, b) => b.value - a.value),
      byCategory: CATEGORY_OPTIONS.map((k) => ({
        name: CATEGORY_LABELS[k].split(" ")[0],
        value: cat.get(k) ?? 0,
      })),
      totalViolations: v,
      totalCritical: c,
    };
  }, [listings]);

  if (listings.length === 0) return null;

  return (
    <section className="relative border-t border-hairline">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          <Metric label="restaurants" value={listings.length.toLocaleString()} />
          <Metric label="total violations" value={totalViolations.toLocaleString()} />
          <Metric
            label="critical violations"
            value={totalCritical.toLocaleString()}
            accent
          />
          <Metric
            label="avg per restaurant"
            value={(totalViolations / listings.length).toFixed(1)}
          />
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-2">
          <ChartCard title="Violations by borough">
            <Chart data={byBorough} color="var(--mint)" />
          </ChartCard>
          <ChartCard title="Restaurants by violation type">
            <Chart data={byCategory} color="var(--coral)" />
          </ChartCard>
        </div>
      </div>
    </section>
  );
}

function Metric({
  label,
  value,
  accent = false,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-2xl hairline bg-surface/60 p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      <div
        className={`mt-2 font-mono text-3xl font-bold ${
          accent ? "text-coral" : "text-foreground"
        }`}
      >
        {value}
      </div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl hairline bg-surface/60 p-5">
      <div className="mb-3 font-mono text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
        {title}
      </div>
      <div className="h-48">{children}</div>
    </div>
  );
}

function Chart({
  data,
  color,
}: {
  data: { name: string; value: number }[];
  color: string;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: 4 }}>
        <XAxis
          dataKey="name"
          tick={{ fontSize: 10, fill: "var(--muted-foreground)" }}
          axisLine={false}
          tickLine={false}
          interval={0}
        />
        <Tooltip
          cursor={{ fill: "var(--surface-elevated)" }}
          contentStyle={{
            background: "var(--background)",
            border: "1px solid var(--hairline)",
            borderRadius: 12,
            fontSize: 12,
          }}
          formatter={(v: number) => [v.toLocaleString(), "count"]}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={color} fillOpacity={0.55 + (i % 2) * 0.25} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
