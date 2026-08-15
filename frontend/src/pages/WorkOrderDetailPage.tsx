import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import type { JSX } from "react";

import { getWorkOrder } from "../api/catalog";
import type { EventResponse } from "../types/api";
import { ApiError } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LongText } from "../components/LongText";
import { Skeleton } from "../components/Skeleton";
import { TraceTag } from "../components/TraceTag";

gsap.registerPlugin(useGSAP);

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

function formatRawValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function EventEvidence({
  evidence,
  ordinal,
}: {
  evidence: Record<string, unknown>[];
  ordinal: number;
}): JSX.Element {
  if (evidence.length === 0) {
    return (
      <p className="text-muted" style={{ margin: "4px 0 0" }}>
        后端未返回 evidence。
      </p>
    );
  }
  return (
    <details className="edge-evidence-raw" style={{ marginTop: 8 }}>
      <summary
        style={{
          cursor: "pointer",
          fontSize: 11,
          color: "var(--color-text-muted)",
        }}
      >
        原始 evidence JSON（事件 #{ordinal + 1} · {evidence.length} 项）
      </summary>
      <pre style={{ margin: "8px 0 0" }}>
{JSON.stringify(evidence, null, 2)}
      </pre>
    </details>
  );
}

function EventCard({ event }: { event: EventResponse }): JSX.Element {
  return (
    <article className="member-card__event">
      <div className="member-card__field">
        <span className="member-card__field-key">事件摘要</span>
        <span className="member-card__field-value">
          {event.normalized_summary}
        </span>
      </div>
      <div className="member-card__field">
        <span className="member-card__field-key">事件类型</span>
        <span className="member-card__field-value">
          {event.event_type ?? "—"}
        </span>
      </div>
      <div className="member-card__field">
        <span className="member-card__field-key">行为</span>
        <span className="member-card__field-value">
          {event.behavior ?? "—"}
        </span>
      </div>
      {event.entities.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">实体</span>
          <div className="member-card__chips">
            {event.entities.map((entity) => (
              <span
                className="chip chip--entity"
                key={entity.entity_id}
                title={entity.entity_type ?? undefined}
              >
                {entity.standard_name ?? entity.entity_id.slice(0, 8)}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {event.location_signals.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">地点信号</span>
          <div className="member-card__chips">
            {event.location_signals.map((location, index) => (
              <span
                className="chip chip--location"
                key={`${location}-${index}`}
              >
                {location}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {event.time_signals.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">时间信号</span>
          <div className="member-card__chips">
            {event.time_signals.map((time, index) => (
              <span className="chip chip--time" key={`${time}-${index}`}>
                {time}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <div className="member-card__field">
        <span className="member-card__field-key">AI 判断依据</span>
        <EventEvidence
          evidence={event.evidence}
          ordinal={event.ordinal}
        />
      </div>
      <div className="member-card__field">
        <TraceTag trace={event.trace} compact />
      </div>
    </article>
  );
}

export function WorkOrderDetailPage(): JSX.Element {
  const { workOrderId } = useParams<{ workOrderId: string }>();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLElement>(null);

  const query = useQuery({
    queryKey: ["work-order", workOrderId],
    queryFn: ({ signal }) => getWorkOrder(workOrderId ?? "", signal),
    enabled: Boolean(workOrderId),
  });

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".detail-section", {
          opacity: 0,
          y: 10,
          duration: 0.3,
          stagger: 0.06,
          ease: "power1.out",
        });
      });
    },
    { scope: containerRef, dependencies: [query.data?.summary.work_order_id] },
  );

  if (!workOrderId) {
    return <ErrorState error={new Error("缺少 workOrderId 路径参数")} />;
  }

  if (query.isPending) {
    return <Skeleton variant="detail" />;
  }

  if (query.isError) {
    const err = query.error;
    if (err instanceof ApiError && err.status === 404) {
      return (
        <EmptyState
          title="工单不存在"
          description={`未找到 work_order_id = ${workOrderId} 的工单。可能已被删除或 ID 不正确。`}
          action={
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => navigate("/work-orders")}
            >
              返回工单列表
            </button>
          }
        />
      );
    }
    return <ErrorState error={err} onRetry={() => query.refetch()} />;
  }

  const data = query.data;
  if (!data) {
    return <EmptyState title="未加载到工单数据" />;
  }

  const { summary, raw_content: rawContent, raw_fields: rawFields, events } = data;
  const rawFieldEntries = Object.entries(rawFields ?? {});

  return (
    <section ref={containerRef}>
      <div className="detail-header">
        <div className="detail-header__back">
          <button
            type="button"
            className="btn btn--ghost btn--back"
            onClick={() => navigate("/work-orders")}
          >
            ← 返回工单列表
          </button>
        </div>
        <p className="eyebrow">WORK ORDER · {summary.work_order_id}</p>
        <h1 className="detail-header__title">
          {summary.raw_title ??
            summary.external_work_order_number ??
            `工单 #${summary.source_row_number}`}
        </h1>
        <div className="detail-header__meta">
          <span>
            外部工单号：<strong>{summary.external_work_order_number ?? "—"}</strong>
          </span>
          <span>
            源行号：<strong>#{summary.source_row_number}</strong>
          </span>
          <span>
            入库时间：
            <strong>{formatTime(summary.created_at)}</strong>
          </span>
          <span>
            AI 事件：<strong>{summary.event_count}</strong>
          </span>
          <span>
            已关联多频事件数：<strong>{summary.cluster_count}</strong>
            <span className="text-muted" style={{ marginLeft: 6 }}>
              （无 cluster_id 字段，仅展示数量，不生成链接）
            </span>
          </span>
        </div>
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">原始工单（不可编辑）</h2>
        <article className="member-card">
          <div className="member-card__body">
            <div className="member-card__region member-card__region--raw">
              <div className="member-card__region-label member-card__region-label--raw">
                RAW WORK ORDER
              </div>
              <div className="member-card__field">
                <span className="member-card__field-key">外部工单编号</span>
                <span className="member-card__field-value">
                  {summary.external_work_order_number ?? "—"}
                </span>
              </div>
              <div className="member-card__field">
                <span className="member-card__field-key">原始标题</span>
                <span className="member-card__field-value">
                  {summary.raw_title ?? "—"}
                </span>
              </div>
              <div className="member-card__field">
                <span className="member-card__field-key">原始正文</span>
                <span className="member-card__field-value">
                  <LongText text={rawContent} maxChars={400} />
                </span>
              </div>
              <div className="member-card__field">
                <span className="member-card__field-key">源行号</span>
                <span className="member-card__field-value">
                  #{summary.source_row_number}
                </span>
              </div>
              <div className="member-card__field">
                <span className="member-card__field-key">入库时间</span>
                <span className="member-card__field-value">
                  {formatTime(summary.created_at)}
                </span>
              </div>
              {rawFieldEntries.length > 0 ? (
                <div className="member-card__field">
                  <span className="member-card__field-key">原始字段</span>
                  <div className="edge-card__evidence-list" style={{ marginTop: 4 }}>
                    {rawFieldEntries.map(([key, value]) => (
                      <div className="edge-evidence-row" key={key}>
                        <span className="edge-evidence-row__key">{key}</span>
                        <span className="edge-evidence-row__value">
                          {formatRawValue(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="member-card__field">
                  <span className="member-card__field-key">原始字段</span>
                  <span className="member-card__field-value text-muted">
                    后端未返回 raw_fields。
                  </span>
                </div>
              )}
            </div>
          </div>
        </article>
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          AI 派生理解
          <span className="detail-section__count">
            （{events.length} 个 AI 事件）
          </span>
        </h2>
        {events.length === 0 ? (
          <EmptyState
            title="未识别 / 暂无 AI 事件"
            description="后端尚未对该工单产出 AI 事件理解。可能尚未触发研判流程，或研判后未识别出可结构化事件。"
          />
        ) : (
          <article className="member-card">
            <div className="member-card__body">
              <div className="member-card__region member-card__region--ai">
                <div className="member-card__region-label member-card__region-label--ai">
                  AI UNDERSTANDING · {events.length} EVENTS
                </div>
                {events.map((event) => (
                  <EventCard key={event.event_id} event={event} />
                ))}
              </div>
            </div>
          </article>
        )}
      </div>
    </section>
  );
}
