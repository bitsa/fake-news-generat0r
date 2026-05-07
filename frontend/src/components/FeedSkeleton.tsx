export function FeedSkeleton() {
  return (
    <div className="grid gap-4">
      <SkeletonCard featured />
      <div className="grid gap-4 [grid-template-columns:repeat(auto-fill,minmax(360px,1fr))]">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </div>
  );
}

interface SkeletonCardProps {
  featured?: boolean;
}

function SkeletonCard({ featured = false }: SkeletonCardProps) {
  return (
    <div
      className={[
        "rounded-[12px] border border-line bg-bg-2",
        featured ? "p-[28px]" : "p-[22px]",
      ].join(" ")}
    >
      <div className="mb-[14px] flex items-center gap-3">
        <SkeletonBar w="120px" h="10px" />
        <div className="flex-1" />
        <SkeletonBar w="56px" h="14px" />
        <SkeletonBar w="48px" h="10px" />
      </div>
      <SkeletonBar
        w="85%"
        h={featured ? "32px" : "22px"}
        className="mb-[10px]"
      />
      <SkeletonBar
        w="100%"
        h={featured ? "16px" : "14px"}
        className="mb-[6px]"
      />
      <SkeletonBar
        w="92%"
        h={featured ? "16px" : "14px"}
        className="mb-[6px]"
      />
      <SkeletonBar w="60%" h={featured ? "16px" : "14px"} />
      <div className="mt-4 flex items-center gap-[14px]">
        <SkeletonBar w="140px" h="12px" />
        <SkeletonBar w="120px" h="12px" />
      </div>
    </div>
  );
}

interface SkeletonBarProps {
  w: string;
  h: string;
  className?: string;
}

function SkeletonBar({ w, h, className = "" }: SkeletonBarProps) {
  return (
    <div
      className={`fl-pulse rounded bg-bg-3 ${className}`}
      style={{ width: w, height: h }}
    />
  );
}
