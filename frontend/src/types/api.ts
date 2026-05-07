export interface HealthResponse {
  status: "ok" | "error";
}

export type SourceId = "NYT" | "NPR" | "Guardian";

export interface Article {
  id: number;
  source: SourceId;
  title: string;
  description: string | null;
  url: string;
  published_at: string | null;
  created_at: string;
}

export interface ArticleFake {
  id: number;
  title: string;
  description: string;
  model: string | null;
  temperature: number | null;
  created_at: string;
}

export interface FeedItem {
  id: number;
  article: Article;
  fake: ArticleFake;
}

export interface ArticlesResponse {
  total: number;
  pending: number;
  articles: FeedItem[];
}
