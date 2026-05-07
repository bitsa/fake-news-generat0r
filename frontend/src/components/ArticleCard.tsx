import { SOURCES } from "../lib/sources";
import { relTime } from "../lib/time";
import type { FeedItem } from "../types/api";

import { SatireBadge } from "./SatireBadge";
import { SourcePill } from "./SourcePill";

export interface ArticleCardProps {
  item: FeedItem;
  fakeMode: boolean;
  featured?: boolean;
}

export function ArticleCard({ item, fakeMode, featured = false }: ArticleCardProps) {
  const source = SOURCES[item.article.source];
  const display = fakeMode
    ? { title: item.fake.title, description: item.fake.description }
    : { title: item.article.title, description: item.article.description ?? "" };

  const tinted = fakeMode;

  return (
    <article
      onClick={(e) => e.preventDefault()}
      className={[
        "relative overflow-hidden rounded-[12px] border cursor-pointer",
        "transition-[border-color,background-color] duration-150",
        featured ? "p-[28px]" : "p-[22px]",
        tinted
          ? "bg-accent/[0.04] border-accent/[0.18] hover:border-line-2"
          : "bg-bg-2 border-line hover:border-line-2",
      ].join(" ")}
    >
      <div className="mb-[14px] flex items-center gap-3">
        <SourcePill source={source} />
        {/* topic slot: kept for layout parity with design; no data in API yet */}
        {/* <span className="inline-block h-[3px] w-[3px] rounded-full bg-text-4" />
            <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-text-3">{topic}</span> */}
        <div className="flex-1" />
        {fakeMode && <SatireBadge />}
        <span className="font-mono text-[11px] text-text-3">
          {relTime(item.article.published_at)}
        </span>
      </div>
      <h2
        className={[
          "m-0 mb-[10px] font-serif font-semibold leading-[1.15] tracking-[-0.01em] text-text",
          featured ? "text-[32px]" : "text-[22px]",
        ].join(" ")}
      >
        {display.title}
      </h2>
      <p
        className={[
          "m-0 line-clamp-3 font-serif leading-[1.55] text-text-2",
          featured ? "text-[16px]" : "text-[14px]",
        ].join(" ")}
      >
        {display.description}
      </p>
      <div className="mt-4 flex items-center gap-[14px] text-[12px] text-text-3">
        <span className="inline-flex items-center gap-[6px]">
          <ChatIcon /> Ask about this article
        </span>
        <span className="inline-flex items-center gap-[6px]">
          <DiffIcon /> Compare to original
        </span>
      </div>
    </article>
  );
}

function ChatIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={13}
      height={13}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 12a8 8 0 0 1-11.7 7L4 20l1-4.6A8 8 0 1 1 21 12Z" />
    </svg>
  );
}

function DiffIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={13}
      height={13}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M8 3v18M16 3v18M3 8h10M11 16h10" />
    </svg>
  );
}
