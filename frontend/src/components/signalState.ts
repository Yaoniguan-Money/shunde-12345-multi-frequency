export type SignalTone = "red" | "amber" | "green" | "blue" | "muted";

export function handlingSignal(status: string | null | undefined): {
  tone: SignalTone;
  label: string;
} {
  const normalized = status?.toLowerCase();
  if (normalized === "resolved" || normalized === "closed") {
    return { tone: "green", label: normalized === "closed" ? "已关闭" : "已办结" };
  }
  if (normalized === "investigating" || normalized === "pending") {
    return { tone: "amber", label: normalized === "pending" ? "待处理" : "处理中" };
  }
  if (normalized === "unhandled") return { tone: "red", label: "未处理" };
  return { tone: "muted", label: status || "未提供" };
}

export function reviewSignal(status: string | null | undefined): {
  tone: SignalTone;
  label: string;
} {
  const normalized = status?.toLowerCase();
  if (normalized === "confirmed") return { tone: "green", label: "已确认" };
  if (normalized === "rejected") return { tone: "red", label: "已驳回" };
  if (normalized === "pending_review") return { tone: "amber", label: "待审核" };
  return { tone: "muted", label: status || "未提供" };
}
