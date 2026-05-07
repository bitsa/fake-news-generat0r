import type { ReactNode } from "react";

export interface ChipProps {
  active: boolean;
  onClick: () => void;
  count: number;
  dotClass?: string;
  children: ReactNode;
}

export function Chip({ active, onClick, count, dotClass, children }: ChipProps) {
  const base =
    "inline-flex items-center gap-2 rounded-full border px-3 py-[6px] font-sans text-[12px] font-medium transition-colors duration-150 cursor-pointer";
  const state = active
    ? "bg-bg-4 border-line-2 text-text"
    : "bg-transparent border-line text-text-2 hover:border-line-2";
  return (
    <button type="button" onClick={onClick} className={`${base} ${state}`}>
      {dotClass && (
        <span className={`inline-block h-[7px] w-[7px] rounded-full ${dotClass}`} />
      )}
      <span>{children}</span>
      <span className="font-mono text-[10px] text-text-3">{count}</span>
    </button>
  );
}
