export type ArticleViewMode = "fake" | "orig";

export interface ToggleSwitchProps {
  value: ArticleViewMode;
  onChange: (next: ArticleViewMode) => void;
}

interface Option {
  k: ArticleViewMode;
  label: string;
}

const OPTIONS: ReadonlyArray<Option> = [
  { k: "fake", label: "Satirical" },
  { k: "orig", label: "Original" },
];

export function ToggleSwitch({ value, onChange }: ToggleSwitchProps) {
  return (
    <div className="inline-flex items-stretch rounded-full border border-line bg-bg-3 p-[3px]">
      {OPTIONS.map((opt) => {
        const active = value === opt.k;
        const activeClasses =
          opt.k === "fake"
            ? "bg-accent text-accent-ink"
            : "bg-bg-4 text-text";
        const inactiveClasses = "bg-transparent text-text-2";
        return (
          <button
            key={opt.k}
            type="button"
            onClick={() => onChange(opt.k)}
            className={[
              "inline-flex items-center rounded-full border-0 px-4 py-[7px] font-sans text-[12px] font-semibold transition-colors duration-150",
              active ? activeClasses : inactiveClasses,
            ].join(" ")}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
