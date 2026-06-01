import { useQuery } from "@tanstack/react-query";
import type { Listing } from "@/data/listings";

// The full inspection dataset (~27k restaurants) is served as a static JSON
// asset and fetched once on the client, then cached by react-query.
async function fetchListings(): Promise<Listing[]> {
  const res = await fetch("/data/inspections.json");
  if (!res.ok) throw new Error(`Failed to load inspections (${res.status})`);
  return res.json();
}

export function useListings() {
  return useQuery({
    queryKey: ["inspections"],
    queryFn: fetchListings,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
