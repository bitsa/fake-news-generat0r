import { SOURCES } from "../lib/sources";
import type { SourceId } from "../types/api";

const DOT_BG: Record<SourceId, string> = {
  NYT: "bg-nyt",
  NPR: "bg-npr",
  Guardian: "bg-grd",
};

export function FeedEmpty() {
  return (
    <div className="rounded-[18px] border border-dashed border-line-2 bg-bg-2 px-8 py-16 text-center">
      <div className="mb-[18px] inline-flex rounded-full bg-bg-3 p-[14px] text-accent">
        <SparkleIcon />
      </div>
      <h3 className="m-0 font-display text-[32px] tracking-[0.01em] text-text">
        NOTHING TO READ — YET
      </h3>
      <p className="mx-auto mb-[22px] mt-2 max-w-[460px] font-serif text-[15px] leading-[1.6] text-text-2">
        The scraper hasn't run. Hit the button to pull the latest from NYT,
        NPR, and The Guardian — then we'll have an LLM make them weirder.
      </p>
      <div className="mt-[22px] flex justify-center gap-[14px] font-mono text-[12px] text-text-3">
        {Object.values(SOURCES).map((s) => (
          <span key={s.id} className="inline-flex items-center gap-[6px]">
            <span
              className={`inline-block h-[6px] w-[6px] rounded-full ${DOT_BG[s.id]}`}
            />
            {s.name}
          </span>
        ))}
      </div>
    </div>
  );
}

function SparkleIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={22}
      height={22}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.5 5.5l2.8 2.8M15.7 15.7l2.8 2.8M5.5 18.5l2.8-2.8M15.7 8.3l2.8-2.8" />
    </svg>
  );
}
