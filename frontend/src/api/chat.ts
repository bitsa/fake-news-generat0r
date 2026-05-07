import { fetchEventSource } from "@microsoft/fetch-event-source";

import type { ChatHistoryResponse } from "../types/api";

import { apiFetch } from "./client";

export function getChatHistory(articleId: number): Promise<ChatHistoryResponse> {
  return apiFetch<ChatHistoryResponse>(`/api/articles/${articleId}/chat`);
}

export interface StreamChatHandlers {
  signal: AbortSignal;
  onToken: (token: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
}

export async function streamChat(
  articleId: number,
  message: string,
  { signal, onToken, onDone, onError }: StreamChatHandlers,
): Promise<void> {
  await fetchEventSource(`/api/articles/${articleId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
    openWhenHidden: true,
    onopen: async (res) => {
      if (!res.ok) {
        let detail = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          if (body && typeof body === "object" && "detail" in body) {
            detail = String((body as { detail: unknown }).detail);
          }
        } catch {
          /* ignore body parse errors */
        }
        throw new Error(detail);
      }
    },
    onmessage: (ev) => {
      if (ev.data === "[DONE]") {
        onDone();
        return;
      }
      try {
        const parsed = JSON.parse(ev.data) as
          | { token?: string; error?: string };
        if (parsed.error) {
          onError(parsed.error);
          return;
        }
        if (typeof parsed.token === "string") {
          onToken(parsed.token);
        }
      } catch {
        /* ignore non-JSON keepalives */
      }
    },
    onerror: (err) => {
      const msg = err instanceof Error ? err.message : "Stream error";
      onError(msg);
      throw err;
    },
  });
}
