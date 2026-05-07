import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { getArticles, postScrape } from "../api/articles";
import type { ArticlesResponse } from "../types/api";

const POLL_INTERVAL_MS = 1500;
const MAX_TRIES = 20;

export type RefreshStatus =
  | "idle"
  | "scraping"
  | "polling"
  | "done"
  | "error"
  | "timeout";

export interface UseRefreshFeed {
  refresh: () => void;
  status: RefreshStatus;
  isWorking: boolean;
  error: string | null;
}

export function useRefreshFeed(): UseRefreshFeed {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<RefreshStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;
    return () => {
      cancelledRef.current = true;
    };
  }, []);

  const isWorking = status === "scraping" || status === "polling";
  const runningRef = useRef(false);

  const refresh = useCallback(() => {
    if (cancelledRef.current || runningRef.current) return;
    runningRef.current = true;
    setError(null);
    setStatus("scraping");

    void (async () => {
      try {
        await postScrape();
        if (cancelledRef.current) return;
        setStatus("polling");

        for (let i = 0; i < MAX_TRIES; i++) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
          if (cancelledRef.current) return;
          try {
            const data = await getArticles();
            queryClient.setQueryData<ArticlesResponse>(["articles"], data);
            if (data.pending === 0) {
              setStatus("done");
              return;
            }
          } catch {
            // transient: keep polling
          }
        }
        if (cancelledRef.current) return;
        setError("Still processing — try again in a moment");
        setStatus("timeout");
      } catch (e) {
        if (cancelledRef.current) return;
        setStatus("error");
        setError(e instanceof Error ? e.message : "Failed to refresh feed");
      } finally {
        runningRef.current = false;
      }
    })();
  }, [queryClient]);

  return { refresh, status, isWorking, error };
}
