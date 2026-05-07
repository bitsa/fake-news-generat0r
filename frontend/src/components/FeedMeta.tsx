import { relTime } from "../lib/time";

export interface FeedMetaProps {
  total: number;
  sourceCount: number;
  lastUpdatedAt: string | null;
}

export function FeedMeta({ total, sourceCount, lastUpdatedAt }: FeedMetaProps) {
  return (
    <div className="text-right font-mono text-[11px] uppercase tracking-[0.08em] text-text-3">
      <div>{total} ARTICLES IN FEED</div>
      <div className="mt-1">{sourceCount} SOURCES</div>
      {lastUpdatedAt && (
        <div className="mt-1">UPDATED {relTime(lastUpdatedAt).toUpperCase()}</div>
      )}
    </div>
  );
}
