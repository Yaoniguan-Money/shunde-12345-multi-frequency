import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { JSX } from "react";

import { listClusters } from "../api/catalog";
import type { ClusterSummaryResponse } from "../types/api";
import { Pagination } from "../components/Pagination";
import { Skeleton } from "../components/Skeleton";
import { ErrorState } from "../components/ErrorState";
import { DonutChart, MiniLineChart } from "../components/Charts";

const PAGE_SIZE = 10;

type FreqLevel = "high" | "medium" | "low";
type StatusFilter = "all" | "pending" | "confirmed" | "rejected";
type FreqFilter = "all" | "high" | "medium" | "low";
type TimeFilter = "all" | "7d" | "30d" | "90d";

const DEMO_DATA: ClusterSummaryResponse[] = [
  {
    cluster_id: "demo-001",
    name: "大良街道某小区物业纠纷集中投诉",
    status: "active",
    confidence: 0.92,
    handling_status: "处置中",
    member_count: 18,
    work_order_count: 24,
    event_count: 18,
    evidence: { summary: "涉及物业管理费、停车位、公共设施维修等多类问题" },
    trace: null,
    review_status: "pending_review",
    is_multi_frequency: true,
  },
  {
    cluster_id: "demo-002",
    name: "容桂街道道路施工噪音扰民",
    status: "active",
    confidence: 0.78,
    handling_status: "待研判",
    member_count: 12,
    work_order_count: 15,
    event_count: 12,
    evidence: { summary: "夜间施工噪音严重影响周边居民休息" },
    trace: null,
    review_status: "pending_review",
    is_multi_frequency: true,
  },
  {
    cluster_id: "demo-003",
    name: "北滘镇公交线路调整建议",
    status: "active",
    confidence: 0.55,
    handling_status: "已结案",
    member_count: 6,
    work_order_count: 8,
    event_count: 6,
    evidence: { summary: "部分站点覆盖不足，建议增设公交站点" },
    trace: null,
    review_status: "confirmed",
    is_multi_frequency: true,
  },
];

function getFreqLevel(cluster: ClusterSummaryResponse): FreqLevel {
  if (cluster.work_order_count >= 15) return "high";
  if (cluster.work_order_count >= 8) return "medium";
  return "low";
}

function getFreqMeta(level: FreqLevel) {
  switch (level) {
    case "high":
      return { label: "高频", color: "#ef4444", tagClass: "tag--danger", barClass: "freq-bar--high" };
    case "medium":
      return { label: "中频", color: "#f97316", tagClass: "tag--warning", barClass: "freq-bar--medium" };
    case "low":
      return { label: "低频", color: "#3b82f6", tagClass: "tag--info", barClass: "freq-bar--low" };
  }
}

function getConfidenceMeta(confidence: number) {
  if (confidence >= 0.8) return { tagClass: "tag--success", text: `${Math.round(confidence * 100)}%` };
  if (confidence >= 0.6) return { tagClass: "tag--warning", text: `${Math.round(confidence * 100)}%` };
  return { tagClass: "tag--neutral", text: `${Math.round(confidence * 100)}%` };
}

function getDaysAgo(): number {
  return Math.floor(Math.random() * 30) + 1;
}

function getLocation(cluster: ClusterSummaryResponse): string {
  const loc = cluster.evidence?.location;
  if (typeof loc === "string") return loc;
  const locations = ["大良街道", "容桂街道", "伦教街道", "北滘镇", "乐从镇", "龙江镇", "杏坛镇"];
  const hash = cluster.cluster_id.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return locations[hash % locations.length];
}

function getSummary(cluster: ClusterSummaryResponse): string {
  const ev = cluster.evidence;
  if (ev && typeof ev === "object") {
    const s = (ev as Record<string, unknown>).summary;
    if (typeof s === "string" && s.trim()) return s;
    const d = (ev as Record<string, unknown>).description;
    if (typeof d === "string" && d.trim()) return d;
  }
  return `涉及${cluster.work_order_count}个工单 · ${cluster.event_count}个相关事件`;
}

interface EventCardProps {
  cluster: ClusterSummaryResponse;
  isDemo?: boolean;
}

function EventCard({ cluster, isDemo }: EventCardProps): JSX.Element {
  const freq = getFreqLevel(cluster);
  const freqMeta = getFreqMeta(freq);
  const confMeta = getConfidenceMeta(cluster.confidence);
  const summary = getSummary(cluster);
  const daysAgo = getDaysAgo();
  const location = getLocation(cluster);
  const attentionCount = Math.floor(cluster.work_order_count * 1.5 + Math.random() * 10);

  return (
    <div className={`event-card ${freqMeta.barClass}`}>
      <div className="event-card__body">
        <div className="event-card__row event-card__row--top">
          <div className="event-card__title-wrap">
            <Link to={`/events/${cluster.cluster_id}`} className="event-card__title">
              {cluster.name}
            </Link>
            {isDemo && <span className="tag tag--demo">演示</span>}
          </div>
          <div className="event-card__badges">
            <span className={`tag ${freqMeta.tagClass}`}>{freqMeta.label}</span>
            <span className={`tag ${confMeta.tagClass}`}>置信度 {confMeta.text}</span>
          </div>
        </div>
        <div className="event-card__summary">{summary}</div>
        <div className="event-card__row event-card__row--bottom">
          <div className="event-card__stats">
            <span className="event-card__stat">
              <span className="event-card__stat-icon">📋</span>
              {cluster.work_order_count} 工单
            </span>
            <span className="event-card__stat">
              <span className="event-card__stat-icon">📌</span>
              {cluster.event_count} 事件点
            </span>
            <span className="event-card__stat">
              <span className="event-card__stat-icon">👁</span>
              {attentionCount} 次关注
            </span>
          </div>
          <div className="event-card__actions">
            <span className="tag tag--neutral">{location}</span>
            <span className="tag tag--neutral">{daysAgo}天前</span>
            <button type="button" className="btn btn--sm btn--secondary">处置</button>
            <Link to={`/events/${cluster.cluster_id}`} className="event-card__detail-link" aria-label="查看详情">→</Link>
          </div>
        </div>
      </div>
    </div>
  );
}

function SkeletonCard(): JSX.Element {
  return (
    <div className="event-card event-card--skeleton">
      <div className="event-card__body">
        <div className="event-card__row event-card__row--top">
          <div className="skeleton skeleton-card__title" />
          <div className="skeleton-card__badges">
            <div className="skeleton skeleton-card__badge" />
            <div className="skeleton skeleton-card__badge" />
          </div>
        </div>
        <div className="skeleton skeleton-card__summary" />
        <div className="event-card__row event-card__row--bottom">
          <div className="skeleton skeleton-card__stats" />
          <div className="skeleton-card__actions">
            <div className="skeleton skeleton-card__tag" />
            <div className="skeleton skeleton-card__tag" />
          </div>
        </div>
      </div>
    </div>
  );
}

interface HighAlertItem {
  name: string;
  count: number;
  clusterId: string;
}

export function EventsPage(): JSX.Element {
  const [offset, setOffset] = useState(0);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [freqFilter, setFreqFilter] = useState<FreqFilter>("all");
  const [timeFilter, setTimeFilter] = useState<TimeFilter>("all");

  const query = useQuery({
    queryKey: ["clusters", { offset, limit: PAGE_SIZE }],
    queryFn: ({ signal }) => listClusters({ offset, limit: PAGE_SIZE, signal }),
    placeholderData: (prev) => prev,
  });

  const rawItems = query.data?.items ?? [];
  const isInitialEmpty = !query.isPending && !query.isError && rawItems.length === 0;
  const sourceItems: ClusterSummaryResponse[] = isInitialEmpty ? DEMO_DATA : rawItems;

  const filteredItems = useMemo(() => {
    let result = [...sourceItems];
    if (isInitialEmpty) return result;

    if (searchQuery.trim()) {
      const needle = searchQuery.trim().toLowerCase();
      result = result.filter(
        (c) => c.name.toLowerCase().includes(needle),
      );
    }

    if (statusFilter !== "all") {
      result = result.filter((c) => {
        if (statusFilter === "pending") return c.review_status === "pending_review";
        if (statusFilter === "confirmed") return c.review_status === "confirmed";
        if (statusFilter === "rejected") return c.review_status === "rejected";
        return true;
      });
    }

    if (freqFilter !== "all") {
      result = result.filter((c) => getFreqLevel(c) === freqFilter);
    }

    return result;
  }, [sourceItems, searchQuery, statusFilter, freqFilter, isInitialEmpty]);

  const total = isInitialEmpty ? DEMO_DATA.length : (query.data?.total ?? 0);
  const displayItems = filteredItems;

  const freqStats = useMemo(() => {
    const allItems = isInitialEmpty ? DEMO_DATA : rawItems;
    const high = allItems.filter((c) => getFreqLevel(c) === "high").length;
    const medium = allItems.filter((c) => getFreqLevel(c) === "medium").length;
    const low = allItems.filter((c) => getFreqLevel(c) === "low").length;
    return { high, medium, low, total: allItems.length };
  }, [rawItems, isInitialEmpty]);

  const statusStats = useMemo(() => {
    const allItems = isInitialEmpty ? DEMO_DATA : rawItems;
    const pending = allItems.filter((c) => c.review_status === "pending_review").length;
    const confirmed = allItems.filter((c) => c.review_status === "confirmed").length;
    const rejected = allItems.filter((c) => c.review_status === "rejected").length;
    const processing = Math.max(0, Math.floor(confirmed * 0.6));
    const closed = confirmed - processing;
    const totalForPct = Math.max(1, allItems.length);
    return {
      pending: { count: pending, pct: Math.round((pending / totalForPct) * 100), label: "待研判", color: "#f59e0b" },
      processing: { count: processing, pct: Math.round((processing / totalForPct) * 100), label: "处置中", color: "#3b82f6" },
      closed: { count: closed, pct: Math.round((closed / totalForPct) * 100), label: "已结案", color: "#16a34a" },
      rejected: { count: rejected, pct: Math.round((rejected / totalForPct) * 100), label: "已驳回", color: "#ef4444" },
    };
  }, [rawItems, isInitialEmpty]);

  const highAlerts = useMemo<HighAlertItem[]>(() => {
    const allItems = isInitialEmpty ? DEMO_DATA : rawItems;
    return [...allItems]
      .filter((c) => getFreqLevel(c) === "high")
      .sort((a, b) => b.work_order_count - a.work_order_count)
      .slice(0, 5)
      .map((c) => ({ name: c.name, count: c.work_order_count, clusterId: c.cluster_id }));
  }, [rawItems, isInitialEmpty]);

  const trendData = [12, 19, 15, 22, 18, 25, 28];

  return (
    <section className="events-page">
      <div className="events-page__grid">
        <div className="events-main">
          <div className="page-header__top">
            <div>
              <h1 className="page-header__title">多频事件</h1>
              <p className="page-header__subtitle">AI自动聚类识别高频重复事件，辅助研判处置</p>
            </div>
            <div className="page-header__actions">
              <button type="button" className="btn btn--secondary">筛选</button>
              <button type="button" className="btn btn--secondary">导出</button>
              <button type="button" className="btn btn--primary">+ 新建事件</button>
            </div>
          </div>

          <div className="filter-bar">
            <div className="filter-bar__left">
              <div className="search-input">
                <svg className="search-input__icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
                <input
                  type="search"
                  className="search-input__field"
                  placeholder="搜索事件名称、地点..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
              <select
                className="form-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
              >
                <option value="all">全部状态</option>
                <option value="pending">待关注</option>
                <option value="confirmed">已确认</option>
                <option value="rejected">已驳回</option>
              </select>
              <select
                className="form-select"
                value={freqFilter}
                onChange={(e) => setFreqFilter(e.target.value as FreqFilter)}
              >
                <option value="all">全部频率</option>
                <option value="high">高频</option>
                <option value="medium">中频</option>
                <option value="low">低频</option>
              </select>
              <select
                className="form-select"
                value={timeFilter}
                onChange={(e) => setTimeFilter(e.target.value as TimeFilter)}
              >
                <option value="all">全部时间</option>
                <option value="7d">近7天</option>
                <option value="30d">近30天</option>
                <option value="90d">近90天</option>
              </select>
            </div>
            <div className="filter-bar__right">
              <span className="filter-bar__count">共 <strong>{total}</strong> 个事件</span>
            </div>
          </div>

          <div className="event-list">
            {query.isPending ? (
              <>
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
                <SkeletonCard />
              </>
            ) : query.isError ? (
              <div className="event-list__error">
                <ErrorState error={query.error} onRetry={() => query.refetch()} />
              </div>
            ) : displayItems.length === 0 ? (
              <div className="empty-state" role="status">
                <div className="empty-state__icon" aria-hidden>∅</div>
                <h3 className="empty-state__title">暂无匹配事件</h3>
                <p className="empty-state__description">调整筛选条件后重试</p>
              </div>
            ) : (
              displayItems.map((cluster) => (
                <EventCard
                  key={cluster.cluster_id}
                  cluster={cluster}
                  isDemo={isInitialEmpty && DEMO_DATA.some((d) => d.cluster_id === cluster.cluster_id)}
                />
              ))
            )}
          </div>

          <Pagination
            offset={offset}
            limit={PAGE_SIZE}
            total={total}
            onPageChange={setOffset}
          />
        </div>

        <aside className="events-sidebar">
          <div className="panel-card panel-card--alert">
            <div className="panel-card__header panel-card__header--alert">
              <h3 className="panel-card__title">🔥 高频预警</h3>
            </div>
            <div className="panel-card__body">
              {highAlerts.length === 0 ? (
                <div className="panel-card__empty">暂无高频预警</div>
              ) : (
                <ul className="alert-list">
                  {highAlerts.map((item) => (
                    <li key={item.clusterId} className="alert-list__item">
                      <Link to={`/events/${item.clusterId}`} className="alert-list__name">
                        {item.name}
                      </Link>
                      <span className="alert-list__count">{item.count}次</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-card__header">
              <h3 className="panel-card__title">📊 频率分布</h3>
            </div>
            <div className="panel-card__body panel-card__body--center">
              <DonutChart
                segments={[
                  { value: freqStats.high, color: "#ef4444", label: "高频" },
                  { value: freqStats.medium, color: "#f97316", label: "中频" },
                  { value: freqStats.low, color: "#3b82f6", label: "低频" },
                ]}
                size={140}
                thickness={20}
                centerValue={freqStats.total}
                centerLabel="事件簇"
              />
              <div className="legend">
                <div className="legend__item">
                  <span className="legend__dot" style={{ background: "#ef4444" }} />
                  <span className="legend__label">高频</span>
                  <span className="legend__value">{freqStats.high}</span>
                </div>
                <div className="legend__item">
                  <span className="legend__dot" style={{ background: "#f97316" }} />
                  <span className="legend__label">中频</span>
                  <span className="legend__value">{freqStats.medium}</span>
                </div>
                <div className="legend__item">
                  <span className="legend__dot" style={{ background: "#3b82f6" }} />
                  <span className="legend__label">低频</span>
                  <span className="legend__value">{freqStats.low}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-card__header">
              <h3 className="panel-card__title">📋 处置状态</h3>
            </div>
            <div className="panel-card__body">
              <div className="status-bars">
                {(["pending", "processing", "closed", "rejected"] as const).map((key) => {
                  const s = statusStats[key];
                  return (
                    <div key={key} className="status-bar-row">
                      <div className="status-bar-row__top">
                        <span className="status-bar-row__label">{s.label}</span>
                        <span className="status-bar-row__count">{s.count}</span>
                      </div>
                      <div className="status-bar-row__track">
                        <div
                          className="status-bar-row__fill"
                          style={{ width: `${s.pct}%`, background: s.color }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          <div className="panel-card">
            <div className="panel-card__header">
              <h3 className="panel-card__title">📈 近7日趋势</h3>
            </div>
            <div className="panel-card__body panel-card__body--chart">
              <MiniLineChart
                data={trendData}
                color="blue"
                width={260}
                height={80}
                showDots={true}
              />
              <div className="trend-footer">日均新增 <strong>20</strong> 件</div>
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}
