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
  running: "研判中",
  completed: "已完成",
  failed: "失败",
  handling: "处理状态",
  neutral: "未知",
};

/**
 * 已知状态的中文映射。未知状态仍展示原始值，不擅自改意义。
 * analysis variant：研判任务/cluster 状态。
 * handling variant：事件业务处理状态。
 */
const STATUS_CN_MAP: Record<string, string> = {
  // analysis job / cluster status
  queued: "排队中",
  running: "研判中",
  completed: "已完成",
  complete: "已完成",
  done: "已完成",
  failed: "失败",
  error: "失败",
  active: "有效",
  inactive: "失效",
  // cluster handling_status
  unhandled: "未处理",
  investigating: "处理中",
  resolved: "已办结",
  closed: "已关闭",
  rejected: "已驳回",
  pending: "待处理",
  pending_review: "待审核",
  confirmed: "已确认",
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
  // 客户界面不暴露后端枚举原文；未知值明确标记为待同步。
  const label = status
    ? (STATUS_CN_MAP[status.toLowerCase()] ?? "状态待同步")
    : TONE_LABEL[tone];
  return (
    <span
      className={`badge badge--${tone}`}
      data-testid="status-badge"
      title={
        variant === "handling"
          ? "处理状态"
          : variant === "analysis"
            ? "研判状态"
            : "状态"
      }
    >
      {label}
    </span>
  );
}
