import { RefreshIcon } from "./Icons";
import type { RefreshStatus } from "../hooks/useRefreshFeed";

export interface RefreshFeedButtonProps {
  onClick: () => void;
  status: RefreshStatus;
  isWorking: boolean;
  error: string | null;
}

const LABEL: Record<RefreshStatus, string> = {
  idle: "Refresh feed",
  scraping: "Fetching…",
  polling: "Generating…",
  done: "Refresh feed",
  error: "Refresh feed",
  timeout: "Refresh feed",
};

export function RefreshFeedButton({
  onClick,
  status,
  isWorking,
  error,
}: RefreshFeedButtonProps) {
  const showError = (status === "error" || status === "timeout") && error;
  const iconAnim =
    status === "scraping"
      ? "animate-refresh-pulse"
      : status === "polling"
        ? "animate-refresh-spin"
        : undefined;

  return (
    <div className="flex flex-col items-end">
      <button
        type="button"
        onClick={onClick}
        disabled={isWorking}
        title={isWorking ? LABEL[status] : "Fetch fresh articles"}
        className="inline-flex items-center gap-2 rounded-full border border-line bg-transparent px-3 py-[6px] font-sans text-[12px] text-text-2 transition-colors hover:text-text disabled:cursor-default disabled:opacity-80"
      >
        <RefreshIcon size={14} className={iconAnim} />
        <span>{LABEL[status]}</span>
      </button>
      {showError && (
        <span
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          className="mt-1 font-mono text-[10px] uppercase tracking-[0.08em] text-bad"
        >
          {error}
        </span>
      )}
    </div>
  );
}
