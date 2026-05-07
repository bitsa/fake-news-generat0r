import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { streamChat } from "../api/chat";
import type { ChatHistoryResponse, ChatMessage } from "../types/api";

import { chatHistoryKey } from "./useChatHistory";

export interface PendingMessage {
  text: string;
  isError: boolean;
}

export interface UseChatStreamResult {
  pendingUser: string | null;
  pendingAssistant: PendingMessage | null;
  isStreaming: boolean;
  send: (message: string) => void;
  cancel: () => void;
}

// Synthetic IDs for client-appended messages. Negative so they can't collide
// with real DB ids; the next genuine history fetch replaces them.
let nextLocalId = -1;
function localId(): number {
  return nextLocalId--;
}

function appendMessages(
  qc: ReturnType<typeof useQueryClient>,
  articleId: number,
  msgs: ChatMessage[],
): void {
  qc.setQueryData<ChatHistoryResponse | undefined>(
    chatHistoryKey(articleId),
    (prev) =>
      prev
        ? { ...prev, messages: [...prev.messages, ...msgs] }
        : { article_id: articleId, messages: msgs },
  );
}

export function useChatStream(articleId: number): UseChatStreamResult {
  const qc = useQueryClient();
  const abortRef = useRef<AbortController | null>(null);

  const [pendingUser, setPendingUser] = useState<string | null>(null);
  const [pendingAssistant, setPendingAssistant] =
    useState<PendingMessage | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  useEffect(
    () => () => {
      abortRef.current?.abort();
    },
    [],
  );

  const send = useCallback(
    (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || isStreaming) return;

      const controller = new AbortController();
      abortRef.current = controller;

      setPendingUser(trimmed);
      setPendingAssistant({ text: "", isError: false });
      setIsStreaming(true);

      let accumulated = "";

      streamChat(articleId, trimmed, {
        signal: controller.signal,
        onToken: (token) => {
          accumulated += token;
          setPendingAssistant({ text: accumulated, isError: false });
        },
        onError: () => {
          // Backend persists an error placeholder on stream failure; let the
          // next history refetch surface the canonical row.
          void qc.invalidateQueries({ queryKey: chatHistoryKey(articleId) });
        },
        onDone: () => {
          /* server sends [DONE] when stream completes successfully */
        },
      })
        .then(() => {
          if (controller.signal.aborted) {
            setPendingUser(null);
            setPendingAssistant(null);
            setIsStreaming(false);
            abortRef.current = null;
            return;
          }
          // Both rows are now persisted server-side; mirror them into the cache
          // with synthetic IDs to skip the redundant GET refetch.
          const now = new Date().toISOString();
          appendMessages(qc, articleId, [
            {
              id: localId(),
              role: "user",
              content: trimmed,
              is_error: false,
              request_id: null,
              created_at: now,
            },
            {
              id: localId(),
              role: "assistant",
              content: accumulated,
              is_error: false,
              request_id: null,
              created_at: now,
            },
          ]);
          setPendingUser(null);
          setPendingAssistant(null);
          setIsStreaming(false);
          abortRef.current = null;
        })
        .catch(() => {
          if (controller.signal.aborted) {
            setPendingUser(null);
            setPendingAssistant(null);
            setIsStreaming(false);
            abortRef.current = null;
            return;
          }
          setIsStreaming(false);
          abortRef.current = null;
          // Refetch so both the user row and the persisted error placeholder
          // appear with their real IDs; clear local pending state.
          setPendingUser(null);
          setPendingAssistant(null);
          void qc.invalidateQueries({ queryKey: chatHistoryKey(articleId) });
        });
    },
    [articleId, isStreaming, qc],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setPendingUser(null);
    setPendingAssistant(null);
    setIsStreaming(false);
  }, []);

  return { pendingUser, pendingAssistant, isStreaming, send, cancel };
}
