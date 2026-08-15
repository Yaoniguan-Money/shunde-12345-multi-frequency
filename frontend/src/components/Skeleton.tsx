import type { JSX } from "react";

interface SkeletonProps {
  variant: "list" | "detail";
  /** list variant 下渲染的卡片骨架数量。 */
  count?: number;
}

export function Skeleton({ variant, count = 5 }: SkeletonProps): JSX.Element {
  if (variant === "list") {
    return (
      <div className="skeleton-list" role="status" aria-live="polite">
        {Array.from({ length: count }).map((_, idx) => (
          <div className="skeleton-card" key={idx}>
            <div className="skeleton-line skeleton-line--title" />
            <div className="skeleton-line skeleton-line--short" />
            <div className="skeleton-line skeleton-line--full" />
            <div className="skeleton-line skeleton-line--full" />
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="skeleton-detail" role="status" aria-live="polite">
      <div className="skeleton-line skeleton-line--title" />
      <div className="skeleton-line skeleton-line--short" />
      <div className="skeleton-line skeleton-line--full" />
      <div className="skeleton-line skeleton-line--full" />
      <div className="skeleton-line skeleton-line--full" />
      <div className="skeleton-line skeleton-line--short" />
    </div>
  );
}
