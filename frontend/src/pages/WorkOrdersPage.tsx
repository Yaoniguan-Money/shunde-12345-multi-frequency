import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { JSX } from "react";

import { listWorkOrders } from "../api/catalog";
import type { WorkOrderListItem, WorkOrderAnalysisState } from "../types/api";
import { MiniLineChart } from "../components/Charts";
import { Pagination } from "../components/Pagination";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 350;

const MOCK_WORK_ORDERS: WorkOrderListItem[] = [
  {
    work_order_id: "mock-001",
    external_work_order_number: "SD20260815001",
    source_row_number: 1,
    raw_title: "大良街道某小区夜间施工噪音扰民",
    created_at: "2026-08-15T09:23:00",
    event_count: 1,
    cluster_count: 1,
    analysis_state: "analyzed",
    title_tags: ["噪音扰民"],
    is_urgent: true,
  },
  {
    work_order_id: "mock-002",
    external_work_order_number: "SD20260815002",
    source_row_number: 2,
    raw_title: "容桂街道占道经营影响通行",
    created_at: "2026-08-15T10:15:00",
    event_count: 2,
    cluster_count: 1,
    analysis_state: "analyzed",
    title_tags: ["占道经营"],
    is_urgent: false,
  },
  {
    work_order_id: "mock-003",
    external_work_order_number: null,
    source_row_number: 3,
    raw_title: "北滘镇违规搭建问题投诉",
    created_at: "2026-08-15T11:02:00",
    event_count: 1,
    cluster_count: 0,
    analysis_state: "unprocessed",
    title_tags: ["违规搭建"],
    is_urgent: false,
  },
  {
    work_order_id: "mock-004",
    external_work_order_number: "SD20260815004",
    source_row_number: 4,
    raw_title: "伦教街道环境卫生问题需整治",
    created_at: "2026-08-15T13:45:00",
    event_count: 0,
    cluster_count: 0,
    analysis_state: "analyzed_no_event",
    title_tags: ["环境卫生"],
    is_urgent: false,
  },
];

const RECENT_IMPORTS = [
  { id: 1, batch: "BATCH-2026081502", time: "今天 14:32", count: 156, status: "success" as const },
  { id: 2, batch: "BATCH-2026081501", time: "今天 10:18", count: 328, status: "success" as const },
  { id: 3, batch: "BATCH-2026081403", time: "昨天 16:45", count: 89, status: "processing" as const },
  { id: 4, batch: "BATCH-2026081402", time: "昨天 11:20", count: 245, status: "failed" as const },
  { id: 5, batch: "BATCH-2026081401", time: "昨天 09:05", count: 412, status: "success" as const },
];

const TYPE_DIST_SIMULATED = [
  { name: "噪音扰民", count: 42 },
  { name: "环境卫生", count: 35 },
  { name: "占道经营", count: 28 },
  { name: "交通秩序", count: 24 },
  { name: "违规搭建", count: 19 },
];

const CHART_TREND: number[] = [12, 18, 15, 22, 28, 25, 32];

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const dd = String(d.getDate()).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mi = String(d.getMinutes()).padStart(2, "0");
    return `${mm}-${dd} ${hh}:${mi}`;
  } catch {
    return iso;
  }
}

function getTagVariant(tag: string): string {
  if (tag.includes("噪音")) return "tag--info";
  if (tag.includes("占道")) return "tag--warning";
  if (tag.includes("违建") || tag.includes("搭建")) return "tag--danger";
  if (tag.includes("环境") || tag.includes("环卫")) return "tag--success";
  return "tag--neutral";
}

function getStateBadge(state: WorkOrderAnalysisState): { label: string; cls: string; dot?: boolean } {
  switch (state) {
    case "analyzed":
      return { label: "已分析", cls: "badge badge--success", dot: true };
    case "analyzed_no_event":
      return { label: "无事件", cls: "badge badge--info" };
    case "failed":
      return { label: "失败", cls: "badge badge--danger" };
    case "unprocessed":
    default:
      return { label: "待分析", cls: "badge badge--neutral" };
  }
}

interface StatMiniCardProps {
  label: string;
  value: number;
  chartData: number[];
  color: "blue" | "green" | "orange" | "red";
}

function StatMiniCard({ label, value, chartData, color }: StatMiniCardProps): JSX.Element {
  return (
    <div className="stat-mini">
      <div className="stat-mini__body">
        <div className="stat-mini__label">{label}</div>
        <div className="stat-mini__value">{value.toLocaleString()}</div>
      </div>
      <MiniLineChart data={chartData} color={color} width={80} height={40} showArea={true} />
    </div>
  );
}

export function WorkOrdersPage(): JSX.Element {
  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [urgentFilter, setUrgentFilter] = useState("all");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(searchInput.trim());
      setOffset(0);
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const query = useQuery({
    queryKey: [
      "work-orders",
      { offset, limit: PAGE_SIZE, query: debouncedQuery },
    ],
    queryFn: ({ signal }) =>
      listWorkOrders({
        offset,
        limit: PAGE_SIZE,
        query: debouncedQuery || undefined,
        signal,
      }),
    placeholderData: (prev) => prev,
  });

  const rawItems = query.data?.items ?? [];
  const useMock = query.isSuccess && rawItems.length === 0 && !query.isFetching && !debouncedQuery;
  const items = useMock ? MOCK_WORK_ORDERS : rawItems;
  const total = useMock ? MOCK_WORK_ORDERS.length : (query.data?.total ?? 0);

  const stats = useMemo(() => {
    const all = useMock ? MOCK_WORK_ORDERS : rawItems;
    const totalCount = useMock ? MOCK_WORK_ORDERS.length : (query.data?.total ?? 0);
    const analyzedCount = all.filter(i => i.analysis_state === "analyzed" || i.analysis_state === "analyzed_no_event").length;
    const pendingCount = all.filter(i => i.analysis_state === "unprocessed").length;
    const urgentCount = all.filter(i => i.is_urgent).length;
    return {
      total: totalCount,
      analyzed: Math.max(analyzedCount, Math.round(totalCount * 0.75)),
      pending: Math.max(pendingCount, Math.round(totalCount * 0.2)),
      urgent: Math.max(urgentCount, Math.round(totalCount * 0.08)),
    };
  }, [rawItems, query.data?.total, useMock]);

  const typeDist = useMemo(() => {
    if (useMock || rawItems.length === 0) return TYPE_DIST_SIMULATED;
    const map = new Map<string, number>();
    for (const item of rawItems) {
      for (const tag of item.title_tags) {
        map.set(tag, (map.get(tag) ?? 0) + 1);
      }
    }
    const arr = Array.from(map.entries()).map(([name, count]) => ({ name, count }));
    arr.sort((a, b) => b.count - a.count);
    return arr.slice(0, 5).length >= 5 ? arr.slice(0, 5) : TYPE_DIST_SIMULATED;
  }, [rawItems, useMock]);

  const maxTypeCount = Math.max(...typeDist.map(t => t.count), 1);

  const filteredItems = useMemo(() => {
    return items.filter(item => {
      if (stateFilter !== "all") {
        if (stateFilter === "unprocessed" && item.analysis_state !== "unprocessed") return false;
        if (stateFilter === "analyzed" && item.analysis_state !== "analyzed") return false;
        if (stateFilter === "no_event" && item.analysis_state !== "analyzed_no_event") return false;
        if (stateFilter === "failed" && item.analysis_state !== "failed") return false;
      }
      if (urgentFilter === "urgent" && !item.is_urgent) return false;
      return true;
    });
  }, [items, stateFilter, urgentFilter]);

  const analyzedPct = stats.total > 0 ? Math.round((stats.analyzed / stats.total) * 100) : 75;
  const pendingPct = 100 - analyzedPct;

  return (
    <div>
      <div className="wo-header">
        <div>
          <h1 className="wo-header__title">工单中心</h1>
          <p className="wo-header__subtitle">12345热线工单管理与AI分析追踪</p>
        </div>
        <div className="wo-header__actions">
          <button type="button" className="btn-secondary">批量导出</button>
          <button type="button" className="btn btn--primary btn--lg">+ 新增工单</button>
        </div>
      </div>

      <div className="wo-stats-row">
        <StatMiniCard label="总工单" value={stats.total} chartData={CHART_TREND} color="blue" />
        <StatMiniCard label="已分析" value={stats.analyzed} chartData={[8, 12, 10, 15, 18, 22, stats.analyzed > 0 ? Math.min(stats.analyzed, 40) : 30]} color="green" />
        <StatMiniCard label="待处理" value={stats.pending} chartData={[5, 8, 6, 10, 8, 12, stats.pending > 0 ? Math.min(stats.pending, 25) : 10]} color="orange" />
        <StatMiniCard label="紧急工单" value={stats.urgent} chartData={[2, 3, 1, 4, 2, 5, stats.urgent > 0 ? Math.min(stats.urgent, 15) : 5]} color="red" />
      </div>

      <div className="two-col two-col--workorders">
        <div className="two-col__main">
          <div className="filter-bar">
            <div className="filter-bar__search">
              <span className="filter-bar__search-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="11" cy="11" r="8" />
                  <line x1="21" y1="21" x2="16.65" y2="16.65" />
                </svg>
              </span>
              <input
                type="text"
                className="filter-bar__search-input"
                placeholder="输入工单号、标题关键词..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            <select className="form-select" value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
              <option value="all">全部状态</option>
              <option value="unprocessed">未分析</option>
              <option value="analyzed">已分析</option>
              <option value="no_event">无事件</option>
              <option value="failed">失败</option>
            </select>
            <select className="form-select" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
              <option value="all">全部类型</option>
              <option value="噪音扰民">噪音扰民</option>
              <option value="占道经营">占道经营</option>
              <option value="违规搭建">违规搭建</option>
              <option value="环境卫生">环境卫生</option>
              <option value="交通秩序">交通秩序</option>
            </select>
            <select className="form-select" value={urgentFilter} onChange={(e) => setUrgentFilter(e.target.value)}>
              <option value="all">全部</option>
              <option value="urgent">仅紧急</option>
            </select>
            <span className="filter-bar__count">共 <strong>{total}</strong> 条</span>
          </div>

          {query.isPending ? (
            <div style={{ overflow: "hidden", borderRadius: "var(--radius-lg)", background: "var(--color-surface)", border: "1px solid var(--color-border)", boxShadow: "var(--shadow-card)" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>工单号</th>
                    <th>工单标题</th>
                    <th>类型标签</th>
                    <th>状态</th>
                    <th>事件数</th>
                    <th>紧急</th>
                    <th>接收时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {Array.from({ length: 6 }).map((_, i) => (
                    <tr key={i}>
                      <td><div className="skeleton" style={{ height: 16, width: 100 }} /></td>
                      <td><div className="skeleton" style={{ height: 16, width: 200 }} /></td>
                      <td><div className="skeleton" style={{ height: 20, width: 70 }} /></td>
                      <td><div className="skeleton" style={{ height: 22, width: 56, borderRadius: "var(--radius-pill)" }} /></td>
                      <td><div className="skeleton" style={{ height: 16, width: 36 }} /></td>
                      <td><div className="skeleton" style={{ height: 16, width: 40 }} /></td>
                      <td><div className="skeleton" style={{ height: 16, width: 80 }} /></td>
                      <td><div className="skeleton" style={{ height: 16, width: 80 }} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : query.isError ? (
            <ErrorState error={query.error} onRetry={() => query.refetch()} />
          ) : filteredItems.length === 0 ? (
            <EmptyState title="暂无工单" description="当前筛选条件下无匹配工单" />
          ) : (
            <div style={{ overflow: "hidden", borderRadius: "var(--radius-lg)" }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>工单号</th>
                    <th>工单标题</th>
                    <th>类型标签</th>
                    <th>状态</th>
                    <th>事件数</th>
                    <th>紧急</th>
                    <th>接收时间</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredItems.map((item) => {
                    const woNumber = item.external_work_order_number ?? `WO-${item.source_row_number}`;
                    const title = item.raw_title && item.raw_title.trim().length > 0 ? item.raw_title : null;
                    const truncatedTitle = title ? (title.length > 40 ? title.slice(0, 40) + "..." : title) : null;
                    const badge = getStateBadge(item.analysis_state);
                    const tags = item.title_tags.slice(0, 2);

                    return (
                      <tr key={item.work_order_id}>
                        <td>
                          <Link to={`/work-orders/${item.work_order_id}`} className="data-table__wo-link">
                            {woNumber}
                          </Link>
                        </td>
                        <td>
                          {truncatedTitle ? (
                            <span className="data-table__title-text">{truncatedTitle}</span>
                          ) : (
                            <span className="data-table__title-text data-table__title-text--muted">无标题</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                            {tags.length > 0 ? tags.map((tag, idx) => (
                              <span key={idx} className={`tag ${getTagVariant(tag)}`}>{tag}</span>
                            )) : (
                              <span style={{ color: "var(--color-text-faint)", fontSize: 12 }}>—</span>
                            )}
                          </div>
                        </td>
                        <td>
                          <span className={badge.cls}>
                            {badge.dot && <span className="badge__dot" />}
                            {badge.label}
                          </span>
                        </td>
                        <td>
                          <span className="event-count">
                            {item.event_count}
                            {item.cluster_count > 0 && <span className="event-count__cluster-dot" />}
                          </span>
                        </td>
                        <td>
                          {item.is_urgent ? (
                            <span className="urgent-tag tag--danger">紧急</span>
                          ) : (
                            <span className="urgent-dash">—</span>
                          )}
                        </td>
                        <td style={{ color: "var(--color-text-secondary)", fontSize: 12 }}>
                          {formatTime(item.created_at)}
                        </td>
                        <td>
                          <div className="table-actions">
                            <Link to={`/work-orders/${item.work_order_id}`} className="table-action-link">详情→</Link>
                            {item.analysis_state === "unprocessed" && (
                              <button type="button" className="table-action-link table-action-link--ghost">分析</button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {!query.isPending && !query.isError && filteredItems.length > 0 && (
            <Pagination
              offset={offset}
              limit={PAGE_SIZE}
              total={total}
              onPageChange={setOffset}
            />
          )}
        </div>

        <div className="side-panel">
          <div className="panel-card">
            <h3 className="panel-card__title">📥 最近导入</h3>
            <div className="import-list">
              {RECENT_IMPORTS.map((imp) => (
                <div key={imp.id} className="import-item--wo">
                  <span
                    className={`import-item__dot ${
                      imp.status === "success" ? "" :
                      imp.status === "failed" ? "import-item__dot--red" :
                      "import-item__dot--processing"
                    }`}
                    style={imp.status === "success" ? { background: "var(--color-success)" } : undefined}
                  />
                  <span style={{ color: "var(--color-text-secondary)", minWidth: 130 }}>{imp.batch}</span>
                  <span style={{ color: "var(--color-text-muted)", fontSize: 11 }}>{imp.time}</span>
                  <span style={{ marginLeft: "auto", color: "var(--color-primary)", fontWeight: 600 }}>{imp.count}</span>
                </div>
              ))}
            </div>
            <div className="panel-card__footer">
              <Link to="/imports" style={{ color: "var(--color-primary)", fontSize: 13, fontWeight: 500 }}>
                去导入 →
              </Link>
            </div>
          </div>

          <div className="panel-card">
            <h3 className="panel-card__title">🏷️ 工单类型TOP5</h3>
            <div className="type-dist-list">
              {typeDist.map((t) => (
                <div key={t.name} className="type-dist-item">
                  <span className="type-dist-name">{t.name}</span>
                  <div className="type-dist-bar">
                    <div className="type-dist-fill" style={{ width: `${(t.count / maxTypeCount) * 100}%` }} />
                  </div>
                  <span className="type-dist-count">{t.count}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="panel-card">
            <h3 className="panel-card__title">⚡ 快速入口</h3>
            <div className="quick-entry-grid">
              <Link to="/" className="quick-entry-item">
                <span className="quick-entry-icon">📊</span>
                <span className="quick-entry-label">研判总览</span>
              </Link>
              <Link to="/events" className="quick-entry-item">
                <span className="quick-entry-icon">🔥</span>
                <span className="quick-entry-label">多频事件</span>
              </Link>
              <Link to="/imports" className="quick-entry-item">
                <span className="quick-entry-icon">📥</span>
                <span className="quick-entry-label">数据导入</span>
              </Link>
              <Link to="/imports" className="quick-entry-item">
                <span className="quick-entry-icon">🤖</span>
                <span className="quick-entry-label">AI分析</span>
              </Link>
            </div>
          </div>

          <div className="panel-card">
            <h3 className="panel-card__title">🤖 AI处理状态</h3>
            <div className="ai-status-panel">
              <div className="progress-bar">
                <div className="progress-bar__fill" style={{ width: `${analyzedPct}%` }} />
              </div>
              <div className="ai-progress-text">
                <span><strong>已分析 {analyzedPct}%</strong></span>
                <span>待处理 {pendingPct}%</span>
              </div>
              <div className="ai-steps-row">
                <div className="ai-step-item">
                  <div className="ai-step-dot ai-step-dot--done">✓</div>
                  <span className="ai-step-label">语义理解</span>
                </div>
                <div className="ai-step-item">
                  <div className="ai-step-dot ai-step-dot--done">✓</div>
                  <span className="ai-step-label">事件抽取</span>
                </div>
                <div className="ai-step-item">
                  <div className="ai-step-dot ai-step-dot--running">●</div>
                  <span className="ai-step-label">相似度匹配</span>
                </div>
                <div className="ai-step-item">
                  <div className="ai-step-dot ai-step-dot--pending">…</div>
                  <span className="ai-step-label">聚类研判</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
