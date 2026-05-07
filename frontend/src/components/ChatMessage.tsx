import type { ChatRole } from "../types/api";

import { BotIcon, UserIcon, WarnIcon } from "./Icons";

export interface ChatMessageViewProps {
  role: ChatRole;
  content: string;
  createdAt?: string | null;
  streaming?: boolean;
  isError?: boolean;
}

function fmtClock(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ChatMessageView({
  role,
  content,
  createdAt,
  streaming = false,
  isError = false,
}: ChatMessageViewProps) {
  const isUser = role === "user";
  return (
    <div
      className={[
        "fl-fadein flex gap-[10px] py-[14px]",
        isUser ? "flex-row-reverse" : "flex-row",
      ].join(" ")}
    >
      <div
        className={[
          "inline-flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-bg-4 text-text-2"
            : isError
              ? "bg-bad text-accent-ink"
              : "bg-accent text-accent-ink",
        ].join(" ")}
      >
        {isUser ? (
          <UserIcon size={13} />
        ) : isError ? (
          <WarnIcon size={13} />
        ) : (
          <BotIcon size={14} />
        )}
      </div>
      <div className="min-w-0 max-w-[85%] flex-1">
        <div
          className={[
            "text-[14px] leading-[1.55]",
            isUser
              ? "rounded-[12px] border border-line bg-bg-3 px-[14px] py-[10px] text-text"
              : "px-0 py-1",
            isError ? "text-bad" : "text-text",
          ].join(" ")}
        >
          {streaming ? (
            <span>
              {content}
              <span className="fl-blink ml-[1px] text-accent">▍</span>
            </span>
          ) : (
            <span className="whitespace-pre-wrap">{content}</span>
          )}
        </div>
        {createdAt && (
          <div
            className={[
              "mt-[4px] font-mono text-[10px] text-text-4",
              isUser ? "text-right" : "text-left",
            ].join(" ")}
          >
            {fmtClock(createdAt)}
          </div>
        )}
      </div>
    </div>
  );
}
