import { useQuery } from "@tanstack/react-query";
import type { Listing } from "@/data/listings";
import { enrichListing } from "@/lib/api/enrich";

/**
 * Fetch the enriched analysis card + takeover plan for a single listing.
 * Only runs while the modal is open (`enabled`). Cached effectively forever
 * since the enrichment for a given CAMIS is stable within a session.
 */
export function useEnrichCard(listing: Listing, enabled: boolean) {
  const query = useQuery({
    queryKey: ["enrich", listing.id],
    queryFn: () => enrichListing(listing),
    enabled,
    staleTime: Infinity,
    gcTime: Infinity,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
  };
}
