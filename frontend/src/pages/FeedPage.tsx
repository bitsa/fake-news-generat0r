import { useEffect, useMemo, useState } from "react";

import { ArticleCard } from "../components/ArticleCard";
import { FeedEmpty } from "../components/FeedEmpty";
import { FeedError } from "../components/FeedError";
import { FeedHeader } from "../components/FeedHeader";
import { FeedHero } from "../components/FeedHero";
import { FeedMeta } from "../components/FeedMeta";
import { FeedSkeleton } from "../components/FeedSkeleton";
import { FilterRail, type FilterCounts } from "../components/FilterRail";
import { useArticles } from "../hooks/useArticles";
import { SOURCES } from "../lib/sources";
import type {
  FeedItem,
  SortMode,
  SourceFilter,
  SourceId,
} from "../types/api";

const SOURCE_IDS = Object.keys(SOURCES) as SourceId[];

function publishedTime(item: FeedItem): number {
  const ts = item.article.published_at;
  return ts ? new Date(ts).getTime() : Number.NEGATIVE_INFINITY;
}

export function FeedPage() {
  const [fakeMode, setFakeMode] = useState<boolean>(true);
  const [errorDismissed, setErrorDismissed] = useState<boolean>(false);
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");
  const [sort, setSort] = useState<SortMode>("recent");

  const { data, isLoading, isError, error } = useArticles();
  const articles = data?.articles ?? [];

  useEffect(() => {
    if (!isError) setErrorDismissed(false);
  }, [isError]);

  const counts = useMemo<FilterCounts>(() => {
    const c: FilterCounts = { all: articles.length, NYT: 0, NPR: 0, Guardian: 0 };
    for (const item of articles) c[item.article.source] += 1;
    return c;
  }, [articles]);

  const visible = useMemo<FeedItem[]>(() => {
    const filtered =
      sourceFilter === "all"
        ? articles
        : articles.filter((a) => a.article.source === sourceFilter);
    const sorted = [...filtered];
    if (sort === "recent") {
      sorted.sort((a, b) => publishedTime(b) - publishedTime(a));
    } else {
      sorted.sort((a, b) => {
        const byName = SOURCES[a.article.source].name.localeCompare(
          SOURCES[b.article.source].name,
        );
        return byName !== 0 ? byName : publishedTime(b) - publishedTime(a);
      });
    }
    return sorted;
  }, [articles, sourceFilter, sort]);

  const lastUpdatedAt = useMemo<string | null>(() => {
    if (articles.length === 0) return null;
    let max = articles[0].article.created_at;
    for (let i = 1; i < articles.length; i++) {
      const t = articles[i].article.created_at;
      if (new Date(t).getTime() > new Date(max).getTime()) max = t;
    }
    return max;
  }, [articles]);

  const hasArticles = articles.length > 0;

  return (
    <div>
      <FeedHeader fakeMode={fakeMode} setFakeMode={setFakeMode} />
      <main className="mx-auto max-w-[1240px] px-7 pb-20 pt-8">
        <FeedHero
          right={
            hasArticles ? (
              <FeedMeta
                total={data?.total ?? articles.length}
                sourceCount={SOURCE_IDS.length}
                lastUpdatedAt={lastUpdatedAt}
              />
            ) : undefined
          }
        />

        {isError && !errorDismissed && (
          <FeedError
            title="Couldn't load the feed"
            detail={error?.message ?? "Unknown error"}
            onDismiss={() => setErrorDismissed(true)}
          />
        )}

        {isLoading && <FeedSkeleton />}

        {!isLoading && (!isError || errorDismissed) && !hasArticles && (
          <FeedEmpty />
        )}

        {!isLoading && hasArticles && (
          <>
            <FilterRail
              counts={counts}
              sourceFilter={sourceFilter}
              setSourceFilter={setSourceFilter}
              sort={sort}
              setSort={setSort}
            />

            {visible.length === 0 ? (
              <p className="font-mono text-[12px] text-text-3">
                No articles match this filter.
              </p>
            ) : (
              <div className="grid gap-4">
                <ArticleCard item={visible[0]} fakeMode={fakeMode} featured />
                {visible.length > 1 && (
                  <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(360px,1fr))]">
                    {visible.slice(1).map((a) => (
                      <ArticleCard key={a.id} item={a} fakeMode={fakeMode} />
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
