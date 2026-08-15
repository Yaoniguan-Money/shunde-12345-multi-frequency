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
  return (
    <span
      className="trace-tag trace-tag--full"
      title="AI 派生数据追踪信息"
    >
      <span className="trace-tag__label">追踪</span>
      <span className="trace-tag__field">
        provider={trace.provider ?? "?"}
      </span>
      <span className="trace-tag__field">
        model={trace.model_id ?? "?"}
      </span>
      <span className="trace-tag__field">
        schema={trace.schema_version}
      </span>
      <span className="trace-tag__field">
        pipeline={trace.pipeline_version || "?"}
      </span>
      {trace.knowledge_snapshot_id ? (
        <span className="trace-tag__field">
          snapshot={trace.knowledge_snapshot_id.slice(0, 8)}…
        </span>
      ) : null}
    </span>
  );
}
