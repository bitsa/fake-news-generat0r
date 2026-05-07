import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ArticleBody } from "../components/ArticleBody";
import { ChatPanel } from "../components/ChatPanel";
import { ArrowLeftIcon, DiffIcon } from "../components/Icons";
import { InlineDiff } from "../components/InlineDiff";
import { Logo } from "../components/Logo";
import { Tag } from "../components/Tag";
import { ToggleSwitch, type ArticleViewMode } from "../components/ToggleSwitch";
import { useArticles } from "../hooks/useArticles";
import type { FeedItem } from "../types/api";

type DetailView = "fake" | "orig" | "diff";

export function ArticleDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const articleId = Number(id);

  const { data, isLoading, isError, error } = useArticles();

  const item = useMemo<FeedItem | null>(() => {
    if (!data) return null;
    return data.articles.find((a) => a.id === articleId) ?? null;
  }, [data, articleId]);

  const [view, setView] = useState<DetailView>("fake");

  if (Number.isNaN(articleId)) {
    return <DetailShell><InlineNotice text="Invalid article id." /></DetailShell>;
  }

  if (isLoading) {
    return <DetailShell><InlineNotice text="Loading article…" /></DetailShell>;
  }

  if (isError) {
    if (error) console.error("Failed to load article", error);
    return (
      <DetailShell>
        <InlineNotice
          text="Couldn't load article right now. Please try again."
          tone="error"
        />
      </DetailShell>
    );
  }

  if (!item) {
    return (
      <DetailShell>
        <InlineNotice text="Article not found." />
      </DetailShell>
    );
  }

  const articlePane = (
    <div className="relative overflow-hidden rounded-lg border border-line bg-bg-2 px-10 py-9">
      <div className="mb-7 flex flex-wrap items-center justify-between gap-4">
        <button
          type="button"
          onClick={() => navigate("/")}
          className="inline-flex h-7 items-center gap-2 rounded-full border-0 bg-transparent px-3 font-sans text-[12px] text-text-2 hover:text-text"
        >
          <ArrowLeftIcon size={14} /> Back to feed
        </button>
        <div className="inline-flex items-center gap-[10px]">
          <ToggleSwitch
            value={view === "diff" ? "fake" : (view as ArticleViewMode)}
            onChange={(v) => setView(v)}
          />
          <button
            type="button"
            onClick={() => setView("diff")}
            className={[
              "inline-flex items-center gap-[7px] rounded-full border border-line px-[14px] py-[7px] font-sans text-[12px]",
              view === "diff" ? "bg-bg-4 text-text" : "bg-transparent text-text-2",
            ].join(" ")}
          >
            <DiffIcon size={13} /> Diff
          </button>
        </div>
      </div>

      {view === "diff" ? (
        <div className="fl-fadein">
          <Tag>What changed</Tag>
          <h2 className="m-0 mb-6 mt-2 font-serif text-[28px] font-semibold text-text">
            Original → Satirical
          </h2>
          <div className="grid gap-7">
            <div>
              <Tag>Title</Tag>
              <div className="mt-2">
                <InlineDiff
                  original={item.article.title}
                  fake={item.fake.title ?? ""}
                />
              </div>
            </div>
            <div>
              <Tag>Description</Tag>
              <div className="mt-2">
                <InlineDiff
                  original={item.article.description ?? ""}
                  fake={item.fake.description ?? ""}
                />
              </div>
            </div>
            <div className="flex gap-[18px] font-mono text-[11px] text-text-3">
              <span>
                <span className="text-bad">━</span> removed from original
              </span>
              <span>
                <span className="text-accent">━</span> added by model
              </span>
            </div>
          </div>
        </div>
      ) : (
        <div className="fl-fadein" key={view}>
          <ArticleBody item={item} view={view as ArticleViewMode} />
        </div>
      )}
    </div>
  );

  return (
    <DetailShell>
      <div className="grid gap-5 [grid-template-columns:minmax(0,1fr)] lg:[grid-template-columns:minmax(0,1fr)_420px]">
        {articlePane}
        <aside className="h-[560px] self-start lg:sticky lg:top-20 lg:h-[calc(100vh-100px)]">
          <ChatPanel item={item} />
        </aside>
      </div>
    </DetailShell>
  );
}

function DetailShell({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1320px] items-center gap-6 px-7 py-[14px]">
          <Link to="/" className="no-underline">
            <Logo />
          </Link>
          <div className="flex items-baseline gap-[6px] font-mono text-[11px] uppercase tracking-[0.12em] text-text-3">
            <span className="inline-block h-[1px] w-[18px] bg-line-2" />
            <span>Satirical news, generated</span>
          </div>
          <div className="flex-1" />
        </div>
      </header>
      <main className="mx-auto max-w-[1320px] px-7 pb-16 pt-6">
        {children}
      </main>
    </div>
  );
}

function InlineNotice({
  text,
  tone = "info",
}: {
  text: string;
  tone?: "info" | "error";
}) {
  return (
    <div
      className={[
        "rounded-lg border px-6 py-5 text-[13px]",
        tone === "error"
          ? "border-bad/40 bg-bad/10 text-bad"
          : "border-line bg-bg-2 text-text-2",
      ].join(" ")}
    >
      {text}
    </div>
  );
}
