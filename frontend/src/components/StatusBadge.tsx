import type { JSX } from "react";

type BadgeTone =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "handling"
  | "neutral";

const TONE_LABEL: Record<BadgeTone, string> = {
  queued: "排队中",
  running: "处理中",
  completed: "已完成",
  failed: "失败",
  handling: "处理状态",
  neutral: "未知",
};

interface StatusBadgeProps {
  /** 状态原始值（后端返回的字符串）。 */
  status?: string | null;
  /** 区分是研判状态、处理状态还是通用 badge。 */
  variant?: "analysis" | "handling" | "neutral";
}

function resolveTone(
  status: string | null | undefined,
  variant: StatusBadgeProps["variant"],
): BadgeTone {
  if (!status) return "neutral";
  const value = status.toLowerCase();
  if (variant === "handling") return "handling";
  if (variant === "neutral") return "neutral";
  // analysis variant：按已知枚举匹配，未知值回落 neutral
  if (value === "queued") return "queued";
  if (value === "running") return "running";
  if (value === "completed" || value === "complete" || value === "done")
    return "completed";
  if (value === "failed" || value === "error") return "failed";
  return "neutral";
}

export function StatusBadge({
  status,
  variant = "analysis",
}: StatusBadgeProps): JSX.Element {
  const tone = resolveTone(status, variant);
  const label = status ?? TONE_LABEL[tone];
  return (
    <span
      className={`badge badge--${tone}`}
      data-testid="status-badge"
      title={variant === "handling" ? "处理状态" : "研判状态"}
    >
      {label}
    </span>
  );
}
