import type { ArticlesResponse } from "../types/api";

import { apiFetch } from "./client";

export function getArticles(): Promise<ArticlesResponse> {
  return apiFetch<ArticlesResponse>("/api/articles");
}
