import type { JSX } from "react";

import type { TraceResponse } from "../types/api";

interface TraceTagProps {
  trace: TraceResponse | null;
  /** 紧凑模式只显示 pipeline_version，适合放在卡片角落。 */
  compact?: boolean;
}

export function TraceTag({ trace, compact = false }: TraceTagProps): JSX.Element {
  if (!trace) {
    return (
      <span className="trace-tag trace-tag--empty" title="未附带追踪信息">
        无追踪信息
      </span>
    );
  }
  if (compact) {
    return (
      <span
        className="trace-tag trace-tag--compact"
        title={`provider=${trace.provider ?? "?"} model=${trace.model_id ?? "?"} schema=${trace.schema_version}`}
      >
        v{trace.pipeline_version || "?"}
      </span>
    );
  }
  // full 模式收纳到"技术追踪"可折叠区域，不抢主业务信息中心
  return (
    <details className="trace-tag trace-tag--foldable" title="AI 派生数据技术追踪信息">
      <summary className="trace-tag__summary">技术追踪</summary>
      <div className="trace-tag__body">
        <span className="trace-tag__field">
          <span className="trace-tag__field-key">provider</span>
          <span className="trace-tag__field-val">{trace.provider ?? "?"}</span>
        </span>
        <span className="trace-tag__field">
          <span className="trace-tag__field-key">model</span>
          <span className="trace-tag__field-val">{trace.model_id ?? "?"}</span>
        </span>
        <span className="trace-tag__field">
          <span className="trace-tag__field-key">schema</span>
          <span className="trace-tag__field-val">{trace.schema_version}</span>
        </span>
        <span className="trace-tag__field">
          <span className="trace-tag__field-key">pipeline</span>
          <span className="trace-tag__field-val">{trace.pipeline_version || "?"}</span>
        </span>
        {trace.knowledge_snapshot_id ? (
          <span className="trace-tag__field">
            <span className="trace-tag__field-key">snapshot</span>
            <span className="trace-tag__field-val">
              {trace.knowledge_snapshot_id.slice(0, 8)}…
            </span>
          </span>
        ) : null}
      </div>
    </details>
  );
}
