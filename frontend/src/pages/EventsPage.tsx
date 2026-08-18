import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { JSX } from "react";

import { listClusters } from "../api/catalog";
import type { ClusterSummaryResponse } from "../types/api";
import { Pagination } from "../components/Pagination";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { handlingSignal } from "../components/signalState";

const PAGE_SIZE = 10;
type StatusFilter = "all" | "pending" | "confirmed" | "rejected";

function getSummary(cluster: ClusterSummaryResponse): string {
  const summary = cluster.evidence?.summary;
  return typeof summary === "string" && summary.trim() ? summary : "";
}

function EventCard({ cluster }: { cluster: ClusterSummaryResponse }): JSX.Element {
  const handling = handlingSignal(cluster.handling_status);
  const signalTone = cluster.is_high_frequency ? "red" : handling.tone;
  const signalLabel = cluster.is_high_frequency ? "高频关注" : handling.label;
  return (
    <article className={`event-card event-card--${signalTone}`}>
      <div className="event-card__body">
        <div className="event-card__row event-card__row--top">
          <div className="event-card__title-wrap">
            <span className={`traffic-light traffic-light--${signalTone}`} aria-label={signalLabel} />
            <Link to={`/events/${cluster.cluster_id}`} className="event-card__title">
              {cluster.name}
            </Link>
            <span className="tag tag--info">多频</span>
            {cluster.is_high_frequency === true ? (
              <span className="tag tag--danger">
                高频 · {cluster.frequency_window_days ?? 3}天内
                {cluster.frequency_work_order_count ?? 0}条工单
              </span>
            ) : null}
          </div>
          <div className="event-card__badges">
            <StatusBadge status={cluster.review_status} variant="neutral" />
            <StatusBadge status={cluster.handling_status} variant="handling" />
          </div>
        </div>
        <div className="event-card__summary">{getSummary(cluster)}</div>
        <div className="event-card__row event-card__row--bottom">
          <div className="event-card__stats">
            <span className="event-card__stat">📋 {cluster.work_order_count} 个关联工单</span>
            <span className="event-card__stat">📌 {cluster.event_count} 项研判结果</span>
            <span className="event-card__stat">置信度 {Math.round(cluster.confidence * 100)}%</span>
            <span className={`event-card__signal event-card__signal--${signalTone}`}>
              {signalLabel}
            </span>
          </div>
          <div className="event-card__actions">
            <Link to={`/events/${cluster.cluster_id}`} className="event-card__detail-link">
              查看详情 →
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}

function SkeletonCard(): JSX.Element {
  return (
    <div className="event-card event-card--skeleton">
      <div className="event-card__body">
        <div className="skeleton skeleton-card__title" />
        <div className="skeleton skeleton-card__summary" />
        <div className="skeleton skeleton-card__stats" />
      </div>
    </div>
  );
}

export function EventsPage(): JSX.Element {
  const [offset, setOffset] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const query = useQuery({
    queryKey: ["clusters", { offset, limit: PAGE_SIZE }],
    queryFn: ({ signal }) => listClusters({ offset, limit: PAGE_SIZE, signal }),
    placeholderData: (prev) => prev,
  });

  const filteredItems = useMemo(() => {
    const needle = searchQuery.trim().toLowerCase();
    return (query.data?.items ?? []).filter((cluster) => {
      if (needle && !cluster.name.toLowerCase().includes(needle)) return false;
      if (statusFilter === "pending" && cluster.review_status !== "pending_review") return false;
      if (statusFilter === "confirmed" && cluster.review_status !== "confirmed") return false;
      if (statusFilter === "rejected" && cluster.review_status !== "rejected") return false;
      return cluster.is_multi_frequency;
    });
  }, [query.data?.items, searchQuery, statusFilter]);

  const total = query.data?.total ?? 0;

  return (
    <section className="events-page">
      <div className="page-header__top">
        <div>
          <h1 className="page-header__title">多频事件</h1>
          <p className="text-muted">高频状态由后端按 reported_at 的滚动三天日历窗口判定。</p>
        </div>
      </div>

      <div className="filter-bar">
        <div className="filter-bar__left">
          <div className="search-input">
            <input
              type="search"
              className="search-input__field"
              placeholder="搜索事件名称..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>
          <select
            className="form-select"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
          >
            <option value="all">全部审核状态</option>
            <option value="pending">待审核</option>
            <option value="confirmed">已确认</option>
            <option value="rejected">已驳回</option>
          </select>
        </div>
        <div className="filter-bar__right">
          <span className="filter-bar__count">后端共 <strong>{total}</strong> 个多频事件</span>
        </div>
      </div>

      <div className="event-list">
        {query.isPending ? (
          Array.from({ length: 4 }, (_, index) => <SkeletonCard key={index} />)
        ) : query.isError ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} />
        ) : filteredItems.length === 0 ? (
          <EmptyState title="暂无匹配多频事件" description="后端没有可展示的真实事件。" />
        ) : (
          filteredItems.map((cluster) => <EventCard key={cluster.cluster_id} cluster={cluster} />)
        )}
      </div>

      {!query.isPending && !query.isError && filteredItems.length > 0 ? (
        <Pagination offset={offset} limit={PAGE_SIZE} total={total} onPageChange={setOffset} />
      ) : null}
    </section>
  );
}
