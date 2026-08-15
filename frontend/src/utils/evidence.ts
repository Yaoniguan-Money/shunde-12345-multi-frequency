// 把后端 evidence（Record<string, unknown>）转成可读摘要与结构化条目。
// 严格遵循：未知字段原样呈现，不臆造、不抹平。

import type { TraceResponse } from "../types/api";

export interface EvidenceItem {
  key: string;
  label: string;
  value: unknown;
  /** positive=支持同事件，conflict=冲突证据，neutral=中性。 */
  tone: "positive" | "conflict" | "neutral";
}

const POSITIVE_KEYS = new Set([
  "same_subject",
  "same_entity",
  "subject_match",
  "entity_match",
  "same_location",
  "location_match",
  "same_event_type",
  "event_type_match",
  "same_behavior",
  "behavior_match",
  "time_overlap",
  "time_match",
  "temporal_match",
  "content_match",
  "summary_match",
]);

const CONFLICT_KEYS = new Set([
  "different_subject",
  "different_entity",
  "different_location",
  "different_event_type",
  "different_behavior",
  "time_conflict",
  "temporal_conflict",
  "location_conflict",
  "content_conflict",
  "conflict",
]);

const LABEL_OVERRIDES: Record<string, string> = {
  same_subject: "主体一致",
  same_entity: "实体一致",
  subject_match: "主体匹配",
  entity_match: "实体匹配",
  same_location: "地点一致",
  location_match: "地点匹配",
  same_event_type: "事件类型一致",
  event_type_match: "事件类型匹配",
  same_behavior: "行为一致",
  behavior_match: "行为匹配",
  time_overlap: "时间重叠",
  time_match: "时间匹配",
  temporal_match: "时间匹配",
  content_match: "事件内容一致",
  summary_match: "摘要匹配",
  different_subject: "主体冲突",
  different_entity: "实体冲突",
  different_location: "地点冲突",
  different_event_type: "事件类型冲突",
  different_behavior: "行为冲突",
  time_conflict: "时间冲突",
  temporal_conflict: "时间冲突",
  location_conflict: "地点冲突",
  content_conflict: "事件内容冲突",
  conflict: "冲突证据",
  confidence: "置信度",
  similarity: "相似度",
  score: "分数",
  reason: "理由",
  summary: "摘要",
  note: "备注",
};

function resolveTone(key: string): EvidenceItem["tone"] {
  if (POSITIVE_KEYS.has(key)) return "positive";
  if (CONFLICT_KEYS.has(key)) return "conflict";
  return "neutral";
}

function resolveLabel(key: string): string {
  return LABEL_OVERRIDES[key] ?? key;
}

export function describeEvidence(
  evidence: Record<string, unknown> | null | undefined,
): EvidenceItem[] {
  if (!evidence || typeof evidence !== "object") return [];
  const items: EvidenceItem[] = [];
  for (const [key, value] of Object.entries(evidence)) {
    if (value === null || value === undefined) continue;
    items.push({
      key,
      label: resolveLabel(key),
      value,
      tone: resolveTone(key),
    });
  }
  return items;
}

/** 生成 evidence 文本摘要，用于卡片角落。 */
export function summarizeEvidence(
  evidence: Record<string, unknown> | null | undefined,
  maxLen = 120,
): string {
  const items = describeEvidence(evidence);
  if (items.length === 0) return "无可用判断依据";
  const positives = items.filter((i) => i.tone === "positive");
  const conflicts = items.filter((i) => i.tone === "conflict");
  const parts: string[] = [];
  if (positives.length > 0) {
    parts.push(`一致项 ${positives.length}：${positives.map((p) => p.label).join("、")}`);
  }
  if (conflicts.length > 0) {
    parts.push(`冲突项 ${conflicts.length}：${conflicts.map((p) => p.label).join("、")}`);
  }
  const neutral = items.filter((i) => i.tone === "neutral");
  if (neutral.length > 0 && parts.length === 0) {
    parts.push(`其他依据 ${neutral.length}：${neutral.map((p) => p.label).join("、")}`);
  }
  let text = parts.join("；");
  if (text.length > maxLen) text = text.slice(0, maxLen) + "…";
  return text || "无可用判断依据";
}

export function formatConfidence(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined || Number.isNaN(confidence)) {
    return "—";
  }
  return `${(confidence * 100).toFixed(1)}%`;
}

export function shortId(id: string | null | undefined, prefix = 8): string {
  if (!id) return "—";
  if (id.length <= prefix) return id;
  return `${id.slice(0, prefix)}…`;
}

export function traceKey(trace: TraceResponse | null): string {
  if (!trace) return "no-trace";
  return `${trace.pipeline_version || "?"}|${trace.schema_version}|${trace.model_id ?? "?"}`;
}
