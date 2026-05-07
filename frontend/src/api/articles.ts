import type { ArticlesResponse } from "../types/api";

import { apiFetch } from "./client";

export interface ScrapeResponse {
  inserted: number;
  fetched: number;
  skipped_url_duplicates: number;
  skipped_near_duplicates: number;
  embedding_calls: number;
}

export function getArticles(): Promise<ArticlesResponse> {
  return apiFetch<ArticlesResponse>("/api/articles");
}

export function postScrape(): Promise<ScrapeResponse> {
  return apiFetch<ScrapeResponse>("/api/scrape", { method: "POST" });
}
