import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Hero } from "@/components/leaseup/Hero";
import { About } from "@/components/leaseup/About";
import { FiltersBar } from "@/components/leaseup/FiltersBar";
import { StatsBar } from "@/components/leaseup/StatsBar";
import { SearchResults } from "@/components/leaseup/SearchResults";
import { Footer } from "@/components/leaseup/Footer";
import { useListings } from "@/hooks/useListings";
import { defaultFilters, filterListings } from "@/hooks/useFilteredListings";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "ScoutEats — NYC restaurant health inspections, made searchable" },
      {
        name: "description",
        content:
          "Search and filter NYC DOHMH restaurant inspection violations across all five boroughs by risk, category, and borough.",
      },
      { property: "og:title", content: "ScoutEats — NYC restaurant health inspections" },
      {
        property: "og:description",
        content: "Every flagged NYC restaurant, its critical violations, and how recently it was inspected.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const { data, isLoading, isError } = useListings();
  const [filters, setFilters] = useState(defaultFilters);

  const listings = data ?? [];
  const filtered = useMemo(
    () => filterListings(listings, filters),
    [listings, filters],
  );

  return (
    <main className="min-h-screen">
      <Hero total={listings.length || 27193} />
      <About />
      <FiltersBar
        filters={filters}
        setFilters={setFilters}
        resultCount={filtered.length}
        totalCount={listings.length}
      />

      {isLoading ? (
        <DataState>Loading inspection data…</DataState>
      ) : isError ? (
        <DataState>
          Couldn't load inspection data. Make sure{" "}
          <code className="text-coral">/data/inspections.json</code> is built.
        </DataState>
      ) : (
        <>
          <StatsBar listings={filtered} />
          <SearchResults listings={filtered} />
        </>
      )}

      <Footer />
    </main>
  );
}

function DataState({ children }: { children: React.ReactNode }) {
  return (
    <section className="mx-auto max-w-6xl px-6 py-24 text-center">
      <p className="font-mono text-xs uppercase tracking-[0.2em] text-mint">
        // status
      </p>
      <p className="mt-3 text-base text-muted-foreground">{children}</p>
    </section>
  );
}
