import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getChatHistory } from "../api/chat";
import type { ChatHistoryResponse } from "../types/api";

export function chatHistoryKey(articleId: number): readonly unknown[] {
  return ["chat", articleId] as const;
}

export function useChatHistory(
  articleId: number,
): UseQueryResult<ChatHistoryResponse, Error> {
  return useQuery<ChatHistoryResponse, Error>({
    queryKey: chatHistoryKey(articleId),
    queryFn: () => getChatHistory(articleId),
    staleTime: 0,
  });
}
