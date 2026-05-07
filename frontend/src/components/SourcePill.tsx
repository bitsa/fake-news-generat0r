import type { Source } from "../lib/sources";
import type { SourceId } from "../types/api";

export interface SourcePillProps {
  source: Source;
}

const DOT_BG: Record<SourceId, string> = {
  NYT: "bg-nyt",
  NPR: "bg-npr",
  Guardian: "bg-grd",
};

export function SourcePill({ source }: SourcePillProps) {
  return (
    <span className="inline-flex items-center gap-[7px] font-mono text-[10px] uppercase tracking-[0.12em] text-text-2">
      <span
        className={`inline-block h-[7px] w-[7px] rounded-full ${DOT_BG[source.id]}`}
      />
      {source.name}
    </span>
  );
}
