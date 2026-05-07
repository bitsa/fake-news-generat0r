import { SOURCES } from "../lib/sources";
import { relTime } from "../lib/time";
import type { FeedItem } from "../types/api";

import { ClockIcon, ExternalIcon, SparkleIcon } from "./Icons";
import { SatireBadge } from "./SatireBadge";
import { SourcePill } from "./SourcePill";

export interface ArticleBodyProps {
  item: FeedItem;
  view: "fake" | "orig";
}

function formatPublished(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ArticleBody({ item, view }: ArticleBodyProps) {
  const isFake = view === "fake";
  const source = SOURCES[item.article.source];
  const display = isFake
    ? { title: item.fake.title ?? "", description: item.fake.description ?? "" }
    : {
        title: item.article.title,
        description: item.article.description ?? "",
      };

  return (
    <div className="relative">
      <div className="mb-[18px] flex items-center gap-3">
        <SourcePill source={source} />
        <span className="inline-block h-[3px] w-[3px] rounded-full bg-text-4" />
        <span className="font-mono text-[11px] text-text-3">
          {formatPublished(item.article.published_at)}
        </span>
        {isFake && (
          <>
            <span className="inline-block h-[3px] w-[3px] rounded-full bg-text-4" />
            <SatireBadge />
          </>
        )}
      </div>
      <h1 className="m-0 font-serif text-[48px] font-semibold leading-[1.08] tracking-[-0.015em] text-text">
        {display.title}
      </h1>
      <p
        className={[
          "mb-0 mt-5 font-serif text-[19px] leading-[1.55] text-text-2",
          "border-l-2 pl-[18px]",
          isFake ? "border-accent" : "border-line-2",
        ].join(" ")}
      >
        {display.description}
      </p>
      <div className="mt-7 flex flex-wrap items-center gap-4 text-[12px] text-text-3">
        <a
          href={item.article.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-[6px] border-b border-line-2 pb-[2px] text-text-2 no-underline hover:border-text-3"
        >
          <ExternalIcon size={13} /> View original on {source.name}
        </a>
        <span className="inline-flex items-center gap-[6px]">
          <ClockIcon size={13} /> Scraped {relTime(item.article.created_at)}
        </span>
        <span className="inline-flex items-center gap-[6px]">
          <SparkleIcon size={13} className="text-accent" /> Transformed{" "}
          {relTime(item.fake.created_at)}
        </span>
      </div>
    </div>
  );
}
