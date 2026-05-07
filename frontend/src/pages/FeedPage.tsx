import { useState } from "react";

import { ArticleCard } from "../components/ArticleCard";
import { FeedEmpty } from "../components/FeedEmpty";
import { FeedError } from "../components/FeedError";
import { FeedHeader } from "../components/FeedHeader";
import { FeedHero } from "../components/FeedHero";
import { FeedSkeleton } from "../components/FeedSkeleton";
import { useArticles } from "../hooks/useArticles";

export function FeedPage() {
  const [fakeMode, setFakeMode] = useState<boolean>(true);
  const [errorDismissed, setErrorDismissed] = useState<boolean>(false);

  const { data, isLoading, isError, error } = useArticles();
  const articles = data?.articles ?? [];

  return (
    <div>
      <FeedHeader fakeMode={fakeMode} setFakeMode={setFakeMode} />
      <main className="mx-auto max-w-[1240px] px-7 pb-20 pt-8">
        <FeedHero />

        {isError && !errorDismissed && (
          <FeedError
            title="Couldn't load the feed"
            detail={error?.message ?? "Unknown error"}
            onDismiss={() => setErrorDismissed(true)}
          />
        )}

        {isLoading && <FeedSkeleton />}

        {!isLoading && !isError && articles.length === 0 && <FeedEmpty />}

        {!isLoading && articles.length > 0 && (
          <div className="grid gap-4">
            <ArticleCard item={articles[0]} fakeMode={fakeMode} featured />
            {articles.length > 1 && (
              <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(360px,1fr))]">
                {articles.slice(1).map((a) => (
                  <ArticleCard key={a.id} item={a} fakeMode={fakeMode} />
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
