import { useState } from "react";
import type { JSX } from "react";

interface LongTextProps {
  text: string | null | undefined;
  maxChars?: number;
  /** 展开后是否换行显示。 */
  preserveBreaks?: boolean;
}

export function LongText({
  text,
  maxChars = 200,
  preserveBreaks = true,
}: LongTextProps): JSX.Element {
  const [expanded, setExpanded] = useState(false);

  if (!text) {
    return <span className="long-text long-text--empty">（无）</span>;
  }

  const overflows = text.length > maxChars;
  const visible = expanded || !overflows ? text : text.slice(0, maxChars);

  return (
    <span className="long-text">
      <span className={preserveBreaks ? "long-text__content" : undefined}>
        {visible}
      </span>
      {overflows ? (
        <button
          type="button"
          className="long-text__toggle"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? "收起" : "展开全部"}
        </button>
      ) : null}
    </span>
  );
}
