import { Tag } from "./Tag";

export function FeedHero() {
  const date = new Date().toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
  return (
    <div className="mb-1">
      <Tag accent>The Front Page · {date}</Tag>
      <h1 className="m-0 mt-2 font-display text-[64px] leading-[0.95] tracking-[0.005em] text-text">
        TODAY'S HEADLINES, <span className="text-accent">SLIGHTLY OFF</span>
      </h1>
      <p className="m-0 mt-[14px] max-w-[620px] font-serif text-[16px] leading-[1.55] text-text-2">
        We pull real articles from 3 feeds, run them through a language model,
        and serve them back with the absurdity dial turned up. Every story
        links to the original.
      </p>
    </div>
  );
}
