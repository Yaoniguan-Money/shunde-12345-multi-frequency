import type { JSX } from "react";

interface PlaceholderPageProps {
  title: string;
  description: string;
}

export function PlaceholderPage({
  title,
  description,
}: PlaceholderPageProps): JSX.Element {
  return (
    <div className="placeholder-page">
      <h1 className="placeholder-page__title">{title}</h1>
      <p className="placeholder-page__desc">{description}</p>
      <span className="eyebrow">即将上线 · 后续阶段</span>
    </div>
  );
}
