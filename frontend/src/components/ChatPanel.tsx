import { useEffect, useRef, useState, type FormEvent } from "react";

import { useChatHistory } from "../hooks/useChatHistory";
import { useChatStream } from "../hooks/useChatStream";
import type { FeedItem } from "../types/api";

import { ChatMessageView } from "./ChatMessage";
import {
  BotIcon,
  DiffIcon,
  ListIcon,
  SendIcon,
  SparkleIcon,
  TagIcon,
} from "./Icons";

export interface ChatPanelProps {
  item: FeedItem;
}

interface QuickPrompt {
  k: string;
  label: string;
  icon: React.ReactNode;
}

const QUICK_PROMPTS: ReadonlyArray<QuickPrompt> = [
  { k: "summarize", label: "Summarize this article", icon: <ListIcon size={13} /> },
  { k: "entities", label: "Key entities", icon: <TagIcon size={13} /> },
  { k: "changed", label: "How was it changed?", icon: <DiffIcon size={13} /> },
];

// Spinning sparkle = active/loading; static bot = idle. Reused in the header
// avatar and inline as the "thinking" indicator before the first token lands.
function StatusIcon({ active, size = 15 }: { active: boolean; size?: number }) {
  return active ? (
    <SparkleIcon
      size={size}
      className="animate-spin [animation-duration:1.6s]"
    />
  ) : (
    <BotIcon size={size + 1} />
  );
}

export function ChatPanel({ item }: ChatPanelProps) {
  const articleId = item.id;
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const { data, isLoading, isError } = useChatHistory(articleId);
  const { pendingUser, pendingAssistant, isStreaming, send } =
    useChatStream(articleId);

  const messages = data?.messages ?? [];
  const showEmpty =
    !isLoading &&
    !isError &&
    messages.length === 0 &&
    !pendingUser &&
    !pendingAssistant;

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, pendingAssistant?.text, pendingUser]);

  const onSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text || isStreaming) return;
    send(text);
    setDraft("");
  };

  const sendPrompt = (label: string) => {
    if (isStreaming) return;
    send(label);
  };

  const groundedTitle = item.article.title;

  const isBusy = isLoading || isStreaming;
  const showThinking =
    isStreaming && pendingAssistant?.text === "" && !pendingAssistant.isError;

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-lg border border-line bg-bg-2">
      <div className="flex items-center gap-[10px] border-b border-line px-[18px] py-4">
        <div className="inline-flex h-7 w-7 items-center justify-center rounded-md bg-accent text-accent-ink">
          <StatusIcon active={isBusy} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[13px] font-semibold text-text">
            Article assistant
          </div>
          <div
            className="truncate text-[11px] text-text-3"
            title={groundedTitle}
          >
            Grounded on: {groundedTitle}
          </div>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto px-[18px] py-1"
      >
        {isLoading && (
          <div className="px-0 py-6 text-[13px] text-text-3">
            Loading conversation…
          </div>
        )}
        {isError && (
          <div className="px-0 py-6 text-[13px] text-bad">
            Couldn&apos;t load chat history.
          </div>
        )}
        {showEmpty && (
          <div className="px-0 py-6 text-[13px] leading-[1.6] text-text-3">
            <div className="mb-[10px] text-text-2">
              Ask anything about this article.
            </div>
            History is persisted per-article — refresh and your thread is still
            here.
          </div>
        )}

        {messages.map((m) => (
          <ChatMessageView
            key={m.id}
            role={m.role}
            content={m.content}
            createdAt={m.created_at}
            isError={m.is_error}
          />
        ))}

        {pendingUser && (
          <ChatMessageView role="user" content={pendingUser} />
        )}
        {pendingAssistant && (
          <ChatMessageView
            role="assistant"
            content={pendingAssistant.text}
            streaming={!pendingAssistant.isError}
            isError={pendingAssistant.isError}
          />
        )}
        {showThinking && (
          <div className="flex items-center gap-2 py-2 pl-9 text-[12px] text-text-3">
            <span className="text-accent">
              <StatusIcon active size={14} />
            </span>
            Thinking…
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-[6px] border-t border-line px-[14px] pb-[6px] pt-[10px]">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p.k}
            type="button"
            onClick={() => sendPrompt(p.label)}
            disabled={isStreaming}
            className={[
              "inline-flex items-center gap-[6px] rounded-full border border-line bg-bg-3 px-[10px] py-[6px] text-[11px] text-text-2",
              isStreaming ? "cursor-not-allowed opacity-55" : "cursor-pointer",
            ].join(" ")}
          >
            {p.icon} {p.label}
          </button>
        ))}
      </div>

      <form onSubmit={onSubmit} className="flex gap-2 px-[14px] pb-[14px] pt-2">
        <label htmlFor="chat-input" className="sr-only">
          Ask about this article
        </label>
        <input
          id="chat-input"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Ask about this article…"
          className="flex-1 rounded-full border border-line bg-bg-3 px-4 py-[10px] font-sans text-[13px] text-text outline-none focus:border-line-2"
        />
        <button
          type="submit"
          aria-label="Send message"
          disabled={!draft.trim() || isStreaming}
          className={[
            "inline-flex h-[38px] w-[38px] items-center justify-center rounded-full border-0 bg-accent text-accent-ink",
            !draft.trim() || isStreaming
              ? "cursor-not-allowed opacity-50"
              : "cursor-pointer",
          ].join(" ")}
        >
          <SendIcon size={15} />
        </button>
      </form>
    </div>
  );
}
