import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { JSX } from "react";

import { listClusters, listEvents, listWorkOrders } from "../api/catalog";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
import { SignalLight } from "../components/SignalLight";
import { handlingSignal, reviewSignal } from "../components/signalState";
import type { ClusterSummaryResponse } from "../types/api";

const PANEL_STYLE = {
  background: "var(--color-surface)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-lg)",
  boxShadow: "var(--shadow-card)",
  padding: 20,
};

function StatCard({
  label,
  value,
  description,
  loading,
}: {
  label: string;
  value: number | string | null;
  description: string;
  loading: boolean;
}): JSX.Element {
  return (
    <article className="stat-card" style={{ minHeight: 128 }}>
      <div className="stat-card__body">
        <div className="stat-card__label">{label}</div>
        <div className="stat-card__value">
          {loading ? "—" : value ?? "—"}
        </div>
        <div className="stat-card__hint">{description}</div>
      </div>
    </article>
  );
}

function ClusterRow({ cluster }: { cluster: ClusterSummaryResponse }): JSX.Element {
  const handling = handlingSignal(cluster.handling_status);
  const review = reviewSignal(cluster.review_status);
  const tone = cluster.is_high_frequency ? "red" : handling.tone;
  const signalLabel = cluster.is_high_frequency ? "高频关注" : handling.label;
  return (
    <Link
      className={`dashboard-cluster-card dashboard-cluster-card--${tone}`}
      to={`/events/${cluster.cluster_id}`}
      style={{ textDecoration: "none" }}
    >
      <div className="dashboard-cluster-card__header">
        <div className="dashboard-cluster-card__title-wrap">
          <span className={`traffic-light traffic-light--${tone}`} aria-label={signalLabel} />
          <h3 className="dashboard-cluster-card__title">{cluster.name}</h3>
        </div>
        <div className="dashboard-cluster-card__badges">
          <StatusBadge status={cluster.handling_status} variant="handling" />
          <StatusBadge status={cluster.review_status} variant="neutral" />
        </div>
      </div>
      <div className="dashboard-cluster-card__meta">
        <span>关联工单：{cluster.work_order_count}</span>
        <span>AI 事件：{cluster.event_count}</span>
        <span>置信度：{Math.round(cluster.confidence * 100)}%</span>
      </div>
      <div className="dashboard-cluster-card__footer">
        <span className={`signal-label signal-label--${tone}`}>
          {signalLabel}
        </span>
        <span className="dashboard-cluster-card__review">审核：{review.label}</span>
        <span>查看详情 →</span>
      </div>
    </Link>
  );
}

function DashboardSignalPanel({ clusters }: { clusters: ClusterSummaryResponse[] }): JSX.Element {
  const statusCounts = clusters.reduce<Record<string, number>>((counts, cluster) => {
    const key = cluster.handling_status?.toLowerCase() || "unknown";
    counts[key] = (counts[key] ?? 0) + 1;
    return counts;
  }, {});
  const highCount = clusters.filter((cluster) => cluster.is_high_frequency).length;
  const rows = [
    { key: "unhandled", label: "未处理", tone: "red" as const, count: statusCounts.unhandled ?? 0 },
    { key: "investigating", label: "处理中", tone: "amber" as const, count: statusCounts.investigating ?? 0 },
    { key: "resolved", label: "已办结", tone: "green" as const, count: statusCounts.resolved ?? 0 },
  ];

  return (
    <aside className="dashboard-signal-panel">
      <div className="dashboard-signal-panel__header">
        <div>
          <p className="eyebrow">实时状态</p>
          <h2 className="dashboard-signal-panel__title">事件状态灯</h2>
        </div>
        <span className="dashboard-signal-panel__scope">当前已加载 {clusters.length} 条</span>
      </div>
      <div className="dashboard-signal-panel__stack">
        {rows.map((row) => (
          <SignalLight key={row.key} tone={row.tone} label={row.label} value={row.count} detail="当前多频列表" />
        ))}
        <SignalLight
          tone={highCount > 0 ? "red" : "muted"}
          label="高频关注"
          value={highCount}
          detail="三天内 ≥ 3 条工单"
        />
      </div>
      <p className="dashboard-signal-panel__note">
        状态灯只统计后端当前返回的真实 cluster；未加载的数据不在此处估算。
      </p>
    </aside>
  );
}

function BackendOnlyNotice(): JSX.Element {
  return (
    <div className="evidence-box" style={{ marginBottom: 20 }}>
      <span className="evidence-box__label">数据口径</span>
      <p className="text-muted" style={{ margin: "8px 0 0", lineHeight: 1.6 }}>
        首页只展示后端 API 已返回并能通过真实 ID 关联的数据。后端未提供的趋势、
        高频等级、准确率或活动记录不再用模拟数字填充。
      </p>
    </div>
  );
}

export function DashboardPage(): JSX.Element {
  const workOrdersQuery = useQuery({
    queryKey: ["dashboard", "work-orders"],
    queryFn: ({ signal }) => listWorkOrders({ offset: 0, limit: 1, signal }),
    retry: 1,
  });
  const eventsQuery = useQuery({
    queryKey: ["dashboard", "events"],
    queryFn: ({ signal }) => listEvents({ offset: 0, limit: 1, signal }),
    retry: 1,
  });
  const clustersQuery = useQuery({
    queryKey: ["dashboard", "clusters"],
    queryFn: ({ signal }) => listClusters({ offset: 0, limit: 20, signal }),
    retry: 1,
  });

  if (workOrdersQuery.isError || eventsQuery.isError || clustersQuery.isError) {
    const error =
      workOrdersQuery.error ?? eventsQuery.error ?? clustersQuery.error;
    return (
      <ErrorState
        error={error}
        onRetry={() => {
          void Promise.all([
            workOrdersQuery.refetch(),
            eventsQuery.refetch(),
            clustersQuery.refetch(),
          ]);
        }}
      />
    );
  }

  const loading =
    workOrdersQuery.isPending || eventsQuery.isPending || clustersQuery.isPending;
  if (loading) return <Skeleton variant="detail" />;

  const clusters = (clustersQuery.data?.items ?? []).filter(
    (cluster) => cluster.is_multi_frequency,
  );

  return (
    <section>
      <header className="detail-header" style={{ marginBottom: 20 }}>
        <p className="eyebrow">数据总览</p>
        <h1 className="detail-header__title">研判总览</h1>
        <p className="text-muted" style={{ margin: "8px 0 0" }}>
          只呈现当前 PostgreSQL 和后端目录 API 中存在的真实数据。
        </p>
      </header>

      <BackendOnlyNotice />

      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <StatCard
          label="工单总数"
          value={workOrdersQuery.data?.total ?? null}
          description="来自工单目录"
          loading={workOrdersQuery.isPending}
        />
        <StatCard
          label="AI 事件总数"
          value={eventsQuery.data?.total ?? null}
          description="来自事件目录，仅展示真实数据"
          loading={eventsQuery.isPending}
        />
        <StatCard
          label="多频事件"
          value={clustersQuery.data?.total ?? null}
          description="后端 is_multi_frequency=true"
          loading={clustersQuery.isPending}
        />
        <StatCard
          label="质量指标"
          value="—"
          description="暂无 Gold Set，不虚构准确率"
          loading={false}
        />
      </div>

      <div className="dashboard-overview-grid">
        <div style={PANEL_STYLE}>
          <div className="detail-section__title" style={{ marginBottom: 14 }}>
            当前多频事件
            <span className="detail-section__count">（{clusters.length} 条）</span>
          </div>
          {clusters.length === 0 ? (
            <EmptyState
              title="后端暂无多频事件"
          description="没有匹配的事件时，前端不显示预置或模拟内容。"
            />
          ) : (
            <div className="dashboard-cluster-grid">
              {clusters.map((cluster) => (
                <ClusterRow key={cluster.cluster_id} cluster={cluster} />
              ))}
            </div>
          )}
        </div>
        <DashboardSignalPanel clusters={clusters} />
      </div>

      <div style={PANEL_STYLE}>
        <div className="detail-section__title" style={{ marginBottom: 10 }}>
          高频判定说明
        </div>
        <p className="text-muted" style={{ margin: 0, lineHeight: 1.7 }}>
          高频仅展示后端合同结果：active cluster 在滚动三天日历窗口内至少有 3 条不同真实
          WorkOrder 且日期可解析。前端不会自行按相似度或日期重算；没有后端高频字段的记录
          不显示高频标签。
        </p>
      </div>
    </section>
  );
}
