import { useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import type { JSX } from "react";

import { getCluster } from "../api/catalog";
import type { EventDetailResponse } from "../types/api";
import { EdgeCard } from "../components/EdgeCard";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LongText } from "../components/LongText";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
import { TraceTag } from "../components/TraceTag";
import { ApiError } from "../api/client";
import {
  describeEvidence,
  formatConfidence,
} from "../utils/evidence";

gsap.registerPlugin(useGSAP);

function formatEvidenceValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function ClusterEvidenceSummary({
  evidence,
}: {
  evidence: Record<string, unknown>;
}): JSX.Element {
  const items = describeEvidence(evidence);
  return (
    <div className="evidence-box">
      <span className="evidence-box__label">AI 判断依据摘要</span>
      {items.length === 0 ? (
        <p className="text-muted" style={{ margin: 0 }}>
          后端未返回结构化 evidence。
        </p>
      ) : (
        <div className="edge-card__evidence-list" style={{ marginTop: 0 }}>
          {items.map((item) => (
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
                {formatEvidenceValue(item.value)}
              </span>
            </div>
          ))}
        </div>
      )}
      {evidence && Object.keys(evidence).length > 0 ? (
        <details style={{ marginTop: 8 }}>
          <summary
            style={{
              cursor: "pointer",
              fontSize: 11,
              color: "var(--color-text-muted)",
            }}
          >
            原始 evidence JSON（{Object.keys(evidence).length} 项）
          </summary>
          <pre style={{ margin: "8px 0 0" }}>
{JSON.stringify(evidence, null, 2)}
          </pre>
        </details>
      ) : null}
    </div>
  );
}

function MemberCard({ member }: { member: EventDetailResponse }): JSX.Element {
  const { event, work_order: workOrder, raw_title: rawTitle, raw_content: rawContent } = member;
  return (
    <article className="member-card">
      <header className="member-card__header">
        <h4 className="member-card__title">
          {rawTitle ?? `工单 ${workOrder.external_work_order_number ?? workOrder.work_order_id}`}
        </h4>
        <span className="uuid-mono">#{workOrder.source_row_number}</span>
      </header>
      <div className="member-card__body">
        <div className="member-card__region member-card__region--raw">
          <div className="member-card__region-label member-card__region-label--raw">
            原始工单
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">外部工单号</span>
            <span className="member-card__field-value">
              {workOrder.external_work_order_number ?? "—"}
            </span>
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">原始标题</span>
            <span className="member-card__field-value">
              {rawTitle ?? "—"}
            </span>
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">原始内容</span>
            <span className="member-card__field-value">
              <LongText text={rawContent} maxChars={400} />
            </span>
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">创建时间</span>
            <span className="member-card__field-value">
              {new Date(workOrder.created_at).toLocaleString("zh-CN")}
            </span>
          </div>
        </div>
        <div className="member-card__region member-card__region--ai">
          <div className="member-card__region-label member-card__region-label--ai">
            AI 理解
          </div>
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
                {event.entities.map((e) => (
                  <span
                    className="chip chip--entity"
                    key={e.entity_id}
                    title={e.entity_type ?? undefined}
                  >
                    {e.standard_name ?? e.entity_id.slice(0, 8)}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {event.location_signals.length > 0 ? (
            <div className="member-card__field">
              <span className="member-card__field-key">地点信号</span>
              <div className="member-card__chips">
                {event.location_signals.map((loc, idx) => (
                  <span className="chip chip--location" key={`${loc}-${idx}`}>
                    {loc}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          {event.time_signals.length > 0 ? (
            <div className="member-card__field">
              <span className="member-card__field-key">时间信号</span>
              <div className="member-card__chips">
                {event.time_signals.map((t, idx) => (
                  <span className="chip chip--time" key={`${t}-${idx}`}>
                    {t}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
          <div className="member-card__field">
            <TraceTag trace={event.trace} compact />
          </div>
        </div>
      </div>
    </article>
  );
}

export function ClusterDetailPage(): JSX.Element {
  const { clusterId } = useParams<{ clusterId: string }>();
  const navigate = useNavigate();
  const containerRef = useRef<HTMLElement>(null);

  const query = useQuery({
    queryKey: ["cluster", clusterId],
    queryFn: ({ signal }) => getCluster(clusterId ?? "", signal),
    enabled: Boolean(clusterId),
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
    { scope: containerRef, dependencies: [query.data?.summary.cluster_id] },
  );

  if (!clusterId) {
    return (
      <ErrorState error={new Error("缺少 clusterId 路径参数")} />
    );
  }

  if (query.isPending) {
    return <Skeleton variant="detail" />;
  }

  if (query.isError) {
    const err = query.error;
    if (err instanceof ApiError && err.status === 404) {
      return (
        <EmptyState
          title="事件不存在"
          description={`未找到 cluster_id = ${clusterId} 的多频事件。可能已被删除或 ID 不正确。`}
          action={
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => navigate("/events")}
            >
              返回多频事件列表
            </button>
          }
        />
      );
    }
    return <ErrorState error={err} onRetry={() => query.refetch()} />;
  }

  const data = query.data;
  if (!data) {
    return <EmptyState title="未加载到事件数据" />;
  }
  const { summary, members, edges } = data;

  return (
    <section ref={containerRef}>
      <div className="detail-header">
        <div className="detail-header__back">
          <button
            type="button"
            className="btn btn--ghost btn--back"
            onClick={() => navigate("/events")}
          >
            ← 返回多频事件
          </button>
        </div>
        <p className="eyebrow">CLUSTER · {summary.cluster_id}</p>
        <h1 className="detail-header__title">{summary.name}</h1>
        <div className="detail-header__badges">
          <StatusBadge status={summary.status} variant="analysis" />
          <StatusBadge
            status={summary.handling_status}
            variant="handling"
          />
        </div>
        <div className="detail-header__meta">
          <span>
            成员工单：<strong>{summary.member_count}</strong>
          </span>
          <span>
            置信度：
            <strong>{formatConfidence(summary.confidence)}</strong>
            <span className="text-muted" style={{ marginLeft: 6 }}>
              （需配合下方 evidence 解读，不单独作为结论）
            </span>
          </span>
        </div>
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          事件概要与 AI 判断依据
        </h2>
        <ClusterEvidenceSummary evidence={summary.evidence} />
        <div style={{ marginTop: 12 }}>
          <TraceTag trace={summary.trace} />
        </div>
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          关联工单
          <span className="detail-section__count">
            （{members.length} 条 · 原始工单 vs AI 派生）
          </span>
        </h2>
        {members.length === 0 ? (
          <EmptyState title="暂无关联工单" description="该事件簇当前没有任何成员工单。" />
        ) : (
          members.map((m) => <MemberCard key={m.event.event_id} member={m} />)
        )}
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          AI 判断依据
          <span className="detail-section__count">
            （{edges.length} 条匹配边）
          </span>
        </h2>
        {edges.length === 0 ? (
          <EmptyState
            title="暂无 AI 判断依据"
            description="后端未对该事件簇返回任何 MatchEdge。可能是单工单事件簇或尚未完成同事件比对。"
          />
        ) : (
          edges.map((edge, idx) => <EdgeCard key={idx} edge={edge} />)
        )}
      </div>

      <div className="detail-section">
        <div className="placeholder-block">
          <h3 className="placeholder-block__title">
            人工纠错 / 业务处理 / 审计历史 即将上线
          </h3>
          <p className="placeholder-block__desc">
            后续阶段将在此呈现人工纠错记录、业务处理状态变更与审计日志，
            并支持 CSV 导出。当前阶段仅做事件结构与 AI 判断依据的展示。
          </p>
        </div>
      </div>
    </section>
  );
}
