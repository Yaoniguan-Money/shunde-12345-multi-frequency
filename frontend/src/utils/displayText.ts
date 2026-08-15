/** Customer-facing display labels. Backend enum values remain unchanged. */
const EVENT_TYPE_LABELS: Record<string, string> = {
  wage_arrears: "拖欠工资",
  construction_noise: "施工噪音",
  social_noise: "社会噪音",
  commercial_noise: "商业噪音",
  road_waterlogging: "道路积水",
  waterlogging: "积水问题",
  traffic: "交通问题",
  environmental_pollution: "环境污染",
  other: "其他问题",
};

const STATUS_LABELS: Record<string, string> = {
  queued: "排队中",
  running: "研判中",
  completed: "已完成",
  complete: "已完成",
  done: "已完成",
  failed: "失败",
  error: "失败",
  active: "有效",
  inactive: "已停用",
  unhandled: "未处理",
  investigating: "处理中",
  resolved: "已办结",
  closed: "已关闭",
  rejected: "已驳回",
  pending: "待处理",
  pending_review: "待审核",
  confirmed: "已确认",
};

const STAGE_LABELS: Record<string, string> = {
  queued: "排队中",
  understanding: "语义理解",
  embedding: "向量生成",
  retrieval: "候选召回",
  matching: "同事件判断",
  clustering: "多频事件整理",
  completed: "研判完成",
};

export function displayEventType(value: string | null | undefined): string {
  if (!value) return "未分类问题";
  const normalized = value.trim().toLowerCase();
  if (EVENT_TYPE_LABELS[normalized]) return EVENT_TYPE_LABELS[normalized];
  if (/[㐀-鿿]/.test(value)) return value;
  return "其他问题";
}

export function displayStatus(value: string | null | undefined): string {
  if (!value) return "未提供";
  const normalized = value.trim().toLowerCase();
  return STATUS_LABELS[normalized] ?? "状态待同步";
}

export function displayStage(value: string | null | undefined): string {
  if (!value) return "等待开始";
  return STAGE_LABELS[value.trim().toLowerCase()] ?? "处理中";
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "未提供";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return "已记录";
}
