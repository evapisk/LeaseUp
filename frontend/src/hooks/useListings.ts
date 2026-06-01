import { useQuery } from "@tanstack/react-query";
import type { Listing } from "@/data/listings";

// Backend API base. Override with VITE_API_URL; defaults to the local
// ScoutEats Intel backend. Set VITE_API_URL="" to fall back to the static
// /data/inspections.json snapshot.
const API_URL =
  import.meta.env.VITE_API_URL ?? "http://localhost:8099";

async function fetchListings(): Promise<Listing[]> {
  const endpoint = API_URL
    ? `${API_URL}/listings?limit=40000`
    : "/data/inspections.json";
  const res = await fetch(endpoint);
  if (!res.ok) throw new Error(`Failed to load inspections (${res.status})`);
  return res.json();
}

export function useListings() {
  return useQuery({
    queryKey: ["inspections", API_URL],
    queryFn: fetchListings,
    staleTime: Infinity,
    gcTime: Infinity,
  });
}
