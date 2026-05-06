import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { apiFetch } from "../api/client";
import type { HealthResponse } from "../types/api";

export function useHealth(): UseQueryResult<HealthResponse, Error> {
  return useQuery<HealthResponse, Error>({
    queryKey: ["health"],
    queryFn: () => apiFetch<HealthResponse>("/health"),
    refetchOnWindowFocus: true,
  });
}
