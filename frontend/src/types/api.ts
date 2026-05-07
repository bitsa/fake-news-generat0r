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

export type SourceFilter = "all" | SourceId;
export type SortMode = "recent" | "source";

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: number;
  role: ChatRole;
  content: string;
  is_error: boolean;
  request_id: string | null;
  created_at: string;
}

export interface ChatHistoryResponse {
  article_id: number;
  messages: ChatMessage[];
}
