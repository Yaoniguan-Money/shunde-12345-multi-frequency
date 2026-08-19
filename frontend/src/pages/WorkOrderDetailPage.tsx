import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useNavigate, useParams } from "react-router-dom";
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
import { displayEventType, displayEvidenceValue } from "../utils/displayText";
import { describeEvidence } from "../utils/evidence";

gsap.registerPlugin(useGSAP);

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
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
        暂无可展示的结构化判断依据。
      </p>
    );
  }
  return (
    <div className="edge-card__evidence-list" style={{ marginTop: 4 }}>
      {evidence.flatMap((item, evidenceIndex) =>
        describeEvidence(item).filter((entry) => !["member_event_ids", "member_work_order_ids", "rejected_edges"].includes(entry.key)).map((entry) => (
          <div className="edge-evidence-row" key={`${ordinal}-${evidenceIndex}-${entry.key}`}>
            <span className="edge-evidence-row__key">{entry.label}</span>
            <span className="edge-evidence-row__value">{displayEvidenceValue(entry.value)}</span>
          </div>
        )),
      )}
    </div>
  );
}

function EventCard({ event }: { event: EventResponse }): JSX.Element {
  return (
    <article className="member-card__event">
      <div className="member-card__field">
        <span className="member-card__field-key">事项摘要</span>
        <span className="member-card__field-value">
          {event.normalized_summary}
        </span>
      </div>
      <div className="member-card__field">
        <span className="member-card__field-key">问题类型</span>
        <span className="member-card__field-value">
          {displayEventType(event.event_type)}
        </span>
      </div>
      <div className="member-card__field">
        <span className="member-card__field-key">诉求内容</span>
        <span className="member-card__field-value">
          {event.behavior ?? "—"}
        </span>
      </div>
      {event.entities.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">涉及对象</span>
          <div className="member-card__chips">
            {event.entities.map((entity) => (
              <span
                className="chip chip--entity"
                key={entity.entity_id}
              >
                {entity.standard_name ?? entity.entity_id.slice(0, 8)}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {event.location_signals.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">涉及地点</span>
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
          <span className="member-card__field-key">反映时间</span>
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
        <span className="member-card__field-key">智能判断依据</span>
        <EventEvidence
          evidence={event.evidence}
          ordinal={event.ordinal}
        />
      </div>
    </article>
  );
}

export function WorkOrderDetailPage(): JSX.Element {
  const { workOrderId } = useParams<{ workOrderId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const fromAssistant = Boolean(
    (location.state as { fromAssistant?: boolean } | null)?.fromAssistant,
  );
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
    return <ErrorState error={new Error("缺少工单标识")} />;
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
          description="未找到该工单，可能已被删除或链接已失效。"
          action={
            <div className="detail-return-actions">
              {fromAssistant ? <button type="button" className="btn btn--primary" onClick={() => navigate("/assistant")}>← 返回智能研判</button> : null}
              <button type="button" className="btn btn--secondary" onClick={() => navigate("/")}>返回研判总览</button>
              <button type="button" className="btn btn--secondary" onClick={() => navigate("/work-orders")}>返回工单列表</button>
            </div>
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

  const { summary, raw_content: rawContent, events } = data;

  return (
    <section ref={containerRef} className="cluster-detail-page work-order-detail-page">
      <div className="detail-header">
        <div className="detail-header__back detail-return-actions">
          {fromAssistant ? <button type="button" className="btn btn--ghost btn--back" onClick={() => navigate("/assistant")}>← 返回智能研判</button> : null}
          <button type="button" className="btn btn--ghost btn--back" onClick={() => navigate("/")}>返回研判总览</button>
          {!fromAssistant ? <button type="button" className="btn btn--ghost btn--back" onClick={() => navigate("/work-orders")}>返回工单列表</button> : null}
        </div>
        <p className="eyebrow">工单详情</p>
        <h1 className="detail-header__title">
          {summary.raw_title ??
            summary.external_work_order_number ??
            `工单 #${summary.source_row_number}`}
        </h1>
        <div className="detail-header__meta">
          <span>
            工单编号：<strong>{summary.external_work_order_number ?? "—"}</strong>
          </span>
          <span>
            入库时间：
            <strong>{formatTime(summary.created_at)}</strong>
          </span>
          <span>
            研判事项：<strong>{summary.event_count}</strong>
          </span>
          <span>
            已关联多频事件数：<strong>{summary.cluster_count}</strong>
            <span className="text-muted" style={{ marginLeft: 6 }}>
              （仅展示已关联数量）
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
                原始工单内容
              </div>
              <div className="member-card__field">
                <span className="member-card__field-key">工单编号</span>
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
                <span className="member-card__field-key">入库时间</span>
                <span className="member-card__field-value">
                  {formatTime(summary.created_at)}
                </span>
              </div>
            </div>
          </div>
        </article>
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          智能研判结果
          <span className="detail-section__count">
            （{events.length} 项）
          </span>
        </h2>
        {events.length === 0 ? (
          <EmptyState
            title="暂未识别到事项"
            description="该工单暂未产出可展示的结构化事件，可能尚未完成研判或未识别到明确诉求。"
          />
        ) : (
          <article className="member-card">
            <div className="member-card__body">
              <div className="member-card__region member-card__region--ai">
                <div className="member-card__region-label member-card__region-label--ai">
                  智能研判 · {events.length} 项研判事项
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
