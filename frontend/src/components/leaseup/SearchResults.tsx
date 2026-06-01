import { useEffect, useState } from "react";
import type { Listing } from "@/data/listings";
import { ListingCard } from "./ListingCard";

const PAGE = 24;

export function SearchResults({ listings }: { listings: Listing[] }) {
  const [visible, setVisible] = useState(PAGE);

  // Reset paging whenever the filtered set changes.
  useEffect(() => {
    setVisible(PAGE);
  }, [listings]);

  const shown = listings.slice(0, visible);

  return (
    <section id="search" className="relative">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="mb-8 flex items-end justify-between">
          <div>
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-mint">
              // live feed
            </span>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
              Flagged kitchens
            </h2>
          </div>
        </div>

        {listings.length === 0 ? (
          <div className="rounded-2xl hairline bg-surface/50 p-12 text-center">
            <p className="font-mono text-xs uppercase tracking-[0.2em] text-mint">
              no_matches.found
            </p>
            <p className="mt-3 text-base text-foreground">
              No restaurants match these filters — try widening the risk level or
              lowering the minimum violations.
            </p>
          </div>
        ) : (
          <>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {shown.map((l, i) => (
                <div
                  key={l.id}
                  className="animate-fade-up"
                  style={{ animationDelay: `${(i % 9) * 60}ms` }}
                >
                  <ListingCard listing={l} />
                </div>
              ))}
            </div>

            {visible < listings.length && (
              <div className="mt-10 flex flex-col items-center gap-3">
                <p className="font-mono text-xs text-muted-foreground">
                  showing {shown.length.toLocaleString()} of{" "}
                  {listings.length.toLocaleString()}
                </p>
                <button
                  onClick={() => setVisible((v) => v + PAGE)}
                  className="rounded-full bg-mint px-6 py-2.5 text-sm font-semibold text-mint-foreground transition-all hover:shadow-[0_0_40px_-5px_oklch(0.88_0.18_170/0.6)]"
                >
                  Load more
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </section>
  );
}
