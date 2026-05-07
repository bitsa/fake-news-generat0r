import type { ArticlesResponse } from "../types/api";

import { apiFetch } from "./client";

export interface ScrapeResponse {
  inserted: number;
  fetched: number;
}

export function getArticles(): Promise<ArticlesResponse> {
  return apiFetch<ArticlesResponse>("/api/articles");
}

export function postScrape(): Promise<ScrapeResponse> {
  return apiFetch<ScrapeResponse>("/api/scrape", { method: "POST" });
}
