export interface FeedErrorProps {
  title: string;
  detail: string;
  onDismiss: () => void;
}

export function FeedError({ title, detail, onDismiss }: FeedErrorProps) {
  return (
    <div className="mb-4 flex items-start gap-[14px] rounded-[12px] border border-bad/30 bg-bad/[0.08] px-[18px] py-[14px]">
      <WarnIcon />
      <div className="flex-1">
        <div className="mb-[2px] text-[13px] font-semibold text-text">{title}</div>
        <div className="text-[12px] text-text-2">{detail}</div>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="bg-transparent text-text-3 hover:text-text-2"
      >
        <CloseIcon />
      </button>
    </div>
  );
}

function WarnIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={18}
      height={18}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="shrink-0 text-bad"
    >
      <path d="M12 3 2 21h20Z" />
      <path d="M12 10v5M12 18.5v.01" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      width={14}
      height={14}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}
