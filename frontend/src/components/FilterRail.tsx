import { SOURCES } from "../lib/sources";
import type { SortMode, SourceFilter, SourceId } from "../types/api";

import { Chip } from "./Chip";
import { Tag } from "./Tag";

export type FilterCounts = Record<SourceFilter, number>;

export interface FilterRailProps {
  counts: FilterCounts;
  sourceFilter: SourceFilter;
  setSourceFilter: (f: SourceFilter) => void;
  sort: SortMode;
  setSort: (s: SortMode) => void;
}

const DOT_BG: Record<SourceId, string> = {
  NYT: "bg-nyt",
  NPR: "bg-npr",
  Guardian: "bg-grd",
};

const SORT_OPTIONS: ReadonlyArray<{ id: SortMode; label: string }> = [
  { id: "recent", label: "Most recent" },
  { id: "source", label: "By source" },
];

export function FilterRail({
  counts,
  sourceFilter,
  setSourceFilter,
  sort,
  setSort,
}: FilterRailProps) {
  const sourceIds = Object.keys(SOURCES) as SourceId[];
  return (
    <div className="flex flex-wrap items-center gap-[10px] py-5">
      <Tag>filter</Tag>
      <Chip
        active={sourceFilter === "all"}
        onClick={() => setSourceFilter("all")}
        count={counts.all}
      >
        All sources
      </Chip>
      {sourceIds.map((id) => (
        <Chip
          key={id}
          active={sourceFilter === id}
          onClick={() => setSourceFilter(id)}
          count={counts[id]}
          dotClass={DOT_BG[id]}
        >
          {SOURCES[id].name}
        </Chip>
      ))}
      <div className="flex-1" />
      <Tag>sort</Tag>
      {SORT_OPTIONS.map((opt) => {
        const active = sort === opt.id;
        return (
          <button
            key={opt.id}
            type="button"
            onClick={() => setSort(opt.id)}
            className={[
              "cursor-pointer border-0 bg-transparent px-2 py-1 font-sans text-[12px]",
              "border-b",
              active ? "text-text border-accent" : "text-text-3 border-transparent",
            ].join(" ")}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
