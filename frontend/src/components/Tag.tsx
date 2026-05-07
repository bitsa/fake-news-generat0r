import type { ReactNode } from "react";

export interface TagProps {
  children: ReactNode;
  accent?: boolean;
}

export function Tag({ children, accent = false }: TagProps) {
  const color = accent ? "text-accent" : "text-text-3";
  return (
    <span
      className={`font-mono text-[10px] uppercase tracking-[0.12em] ${color}`}
    >
      {children}
    </span>
  );
}
