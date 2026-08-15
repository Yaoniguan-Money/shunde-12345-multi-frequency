import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { JSX } from "react";

import { listClusters, listEvents, listWorkOrders } from "../api/catalog";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
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
  return (
    <Link
      className="dashboard-cluster-card"
      to={`/events/${cluster.cluster_id}`}
      style={{ textDecoration: "none" }}
    >
      <div className="dashboard-cluster-card__header">
        <h3 className="dashboard-cluster-card__title">{cluster.name}</h3>
        <StatusBadge status={cluster.handling_status} variant="handling" />
      </div>
      <div className="dashboard-cluster-card__meta">
        <span>关联工单：{cluster.work_order_count}</span>
        <span>AI 事件：{cluster.event_count}</span>
        <span>置信度：{Math.round(cluster.confidence * 100)}%</span>
      </div>
      <div className="dashboard-cluster-card__footer">
        <span>后端判定：{cluster.is_multi_frequency ? "多频事件" : "非多频"}</span>
        <span>查看详情 →</span>
      </div>
    </Link>
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
        <p className="eyebrow">BACKEND-CONNECTED OVERVIEW</p>
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
          description="来自 GET /work-orders"
          loading={workOrdersQuery.isPending}
        />
        <StatCard
          label="AI 事件总数"
          value={eventsQuery.data?.total ?? null}
          description="来自 GET /events，不做样本外估算"
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

      <div style={{ ...PANEL_STYLE, marginBottom: 20 }}>
        <div className="detail-section__title" style={{ marginBottom: 14 }}>
          当前多频事件
          <span className="detail-section__count">（{clusters.length} 条）</span>
        </div>
        {clusters.length === 0 ? (
          <EmptyState
            title="后端暂无多频事件"
            description="没有匹配的 cluster 时，前端不显示预置或模拟事件。"
          />
        ) : (
          <div className="dashboard-cluster-grid">
            {clusters.map((cluster) => (
              <ClusterRow key={cluster.cluster_id} cluster={cluster} />
            ))}
          </div>
        )}
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
