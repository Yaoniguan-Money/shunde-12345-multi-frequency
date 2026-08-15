import type { JSX } from "react";

import type { MatchEdgeResponse } from "../types/api";
import {
  describeEvidence,
  formatConfidence,
  shortId,
} from "../utils/evidence";

interface EdgeCardProps {
  edge: MatchEdgeResponse;
}

function formatValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return "已记录";
}

export function EdgeCard({ edge }: EdgeCardProps): JSX.Element {
  const items = describeEvidence(edge.evidence).filter(
    (item) => !["member_event_ids", "member_work_order_ids", "rejected_edges"].includes(item.key),
  );

  return (
    <article className="edge-card">
      <div className="edge-card__header">
        <div className="edge-card__pair">
          <span title={edge.left_event_id}>{shortId(edge.left_event_id)}</span>
          <span className="edge-card__pair-arrow" aria-hidden>
            ⇄
          </span>
          <span title={edge.right_event_id}>
            {shortId(edge.right_event_id)}
          </span>
        </div>
        <div className="edge-card__judgment">
          <span
            className={
              edge.same_event ? "badge badge--completed" : "badge badge--failed"
            }
          >
            {edge.same_event ? "判定为同一事件" : "判定为非同一事件"}
          </span>
          <span className="confidence-bar">
            <span className="cluster-card__meta-value">
              {formatConfidence(edge.confidence)}
            </span>
            <span className="confidence-bar__track">
              <span
                className="confidence-bar__fill"
                style={{
                  width: `${Math.min(100, Math.max(0, edge.confidence * 100))}%`,
                }}
              />
            </span>
          </span>
        </div>
      </div>

      <div className="edge-card__evidence-list">
        <div className="edge-evidence-row">
          <span className="edge-evidence-row__key">判定结论</span>
          <span
            className={
              edge.same_event
                ? "edge-evidence-row__value edge-evidence-row__value--positive"
                : "edge-evidence-row__value edge-evidence-row__value--conflict"
            }
          >
            {edge.same_event ? "同一事件" : "非同一事件"} · 置信度{" "}
            {formatConfidence(edge.confidence)}
          </span>
        </div>
        {items.length === 0 ? (
          <div className="edge-evidence-row">
            <span className="edge-evidence-row__key">判断依据</span>
            <span className="edge-evidence-row__value text-muted">
              后端未返回结构化 evidence 字段
            </span>
          </div>
        ) : (
          items.map((item) => (
            <div className="edge-evidence-row" key={item.key}>
              <span className="edge-evidence-row__key">{item.label}</span>
              <span
                className={
                  item.tone === "positive"
                    ? "edge-evidence-row__value edge-evidence-row__value--positive"
                    : item.tone === "conflict"
                      ? "edge-evidence-row__value edge-evidence-row__value--conflict"
                      : "edge-evidence-row__value"
                }
              >
                {formatValue(item.value)}
              </span>
            </div>
          ))
        )}
      </div>

      {items.length > 0 ? (
        <p className="text-muted edge-card__footer-note">
          以上为结构化判断依据，需结合原始工单和人工复核使用。
        </p>
      ) : null}
    </article>
  );
}
