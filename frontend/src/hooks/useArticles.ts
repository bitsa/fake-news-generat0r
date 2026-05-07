import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getArticles } from "../api/articles";
import type { ArticlesResponse } from "../types/api";

export function useArticles(): UseQueryResult<ArticlesResponse, Error> {
  return useQuery<ArticlesResponse, Error>({
    queryKey: ["articles"],
    queryFn: getArticles,
  });
}
