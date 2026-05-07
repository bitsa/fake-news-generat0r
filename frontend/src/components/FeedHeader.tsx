import { Logo } from "./Logo";

export interface FeedHeaderProps {
  fakeMode: boolean;
  setFakeMode: (next: boolean) => void;
}

export function FeedHeader({ fakeMode, setFakeMode }: FeedHeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-bg/85 backdrop-blur-md">
      <div className="mx-auto flex max-w-[1240px] items-center gap-6 px-7 py-[14px]">
        <Logo />
        <div className="flex items-baseline gap-[6px] font-mono text-[11px] uppercase tracking-[0.12em] text-text-3">
          <span className="inline-block h-[1px] w-[18px] bg-line-2" />
          <span>Satirical news, generated</span>
        </div>
        <div className="flex-1" />
        <button
          type="button"
          onClick={() => setFakeMode(!fakeMode)}
          title="Toggle global fake/original"
          className="inline-flex items-center gap-2 rounded-full border border-line bg-transparent px-3 py-[6px] font-sans text-[12px] text-text-2"
        >
          <span
            className={[
              "relative h-4 w-7 rounded-full border transition-colors duration-200",
              fakeMode ? "bg-accent border-accent" : "bg-bg-4 border-line-2",
            ].join(" ")}
          >
            <span
              className="absolute top-[1px] h-3 w-3 rounded-full bg-white transition-[left] duration-200"
              style={{ left: fakeMode ? 13 : 1 }}
            />
          </span>
          <span>{fakeMode ? "Showing satirical" : "Showing originals"}</span>
        </button>
      </div>
    </header>
  );
}
