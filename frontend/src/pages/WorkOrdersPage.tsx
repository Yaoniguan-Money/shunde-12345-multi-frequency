import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { JSX } from "react";

import { listWorkOrders } from "../api/catalog";
import type { WorkOrderAnalysisState, WorkOrderListItem } from "../types/api";
import { Pagination } from "../components/Pagination";
import { ErrorState } from "../components/ErrorState";
import { EmptyState } from "../components/EmptyState";

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 350;

function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "未提供" : date.toLocaleString("zh-CN");
}

function getStateBadge(state: WorkOrderAnalysisState | undefined): { label: string; cls: string } {
  switch (state) {
    case "analyzed":
      return { label: "已分析", cls: "badge badge--success" };
    case "analyzed_no_event":
      return { label: "无事件", cls: "badge badge--info" };
    case "failed":
      return { label: "失败", cls: "badge badge--danger" };
    default:
      return { label: "未处理", cls: "badge badge--neutral" };
  }
}

function getTagVariant(tag: string): string {
  if (tag.includes("噪音")) return "tag--info";
  if (tag.includes("占道")) return "tag--warning";
  if (tag.includes("违建") || tag.includes("搭建")) return "tag--danger";
  if (tag.includes("环境") || tag.includes("环卫")) return "tag--success";
  return "tag--neutral";
}

function normalizeItem(item: WorkOrderListItem): WorkOrderListItem {
  const raw = item as WorkOrderListItem & { title_tags?: string[]; analysis_state?: WorkOrderAnalysisState };
  return {
    ...item,
    title_tags: Array.isArray(raw.title_tags) ? raw.title_tags : [],
    analysis_state: raw.analysis_state ?? "unprocessed",
    is_urgent: raw.is_urgent === true,
  };
}

export function WorkOrdersPage(): JSX.Element {
  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [stateFilter, setStateFilter] = useState("all");
  const [urgentFilter, setUrgentFilter] = useState("all");

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(searchInput.trim());
      setOffset(0);
    }, DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const query = useQuery({
    queryKey: ["work-orders", { offset, limit: PAGE_SIZE, query: debouncedQuery, stateFilter }],
    queryFn: ({ signal }) => listWorkOrders({
      offset,
      limit: PAGE_SIZE,
      query: debouncedQuery || undefined,
      analysisState: stateFilter === "all" ? undefined : stateFilter === "no_event" ? "analyzed_no_event" : stateFilter,
      signal,
    }),
    placeholderData: (prev) => prev,
  });

  const items = (query.data?.items ?? []).map(normalizeItem).filter((item) => {
    if (urgentFilter === "urgent" && !item.is_urgent) return false;
    return true;
  });
  const total = query.data?.total ?? 0;

  return (
    <section>
      <header className="detail-header" style={{ marginBottom: 20 }}>
        <p className="eyebrow">BACKEND-CONNECTED WORK ORDERS</p>
        <h1 className="detail-header__title">工单中心</h1>
        <p className="text-muted" style={{ margin: "8px 0 0" }}>
          只展示后端返回的真实工单；未提供的字段不补造。
        </p>
      </header>

      <div className="evidence-box" style={{ marginBottom: 20 }}>
        <span className="evidence-box__label">数据口径</span>
        <p className="text-muted" style={{ margin: "8px 0 0", lineHeight: 1.6 }}>
          当前列表没有后端导入历史、趋势或类型分布合同，因此页面不显示模拟导入、随机趋势或估算统计。
        </p>
      </div>

      <div className="filter-bar">
        <div className="filter-bar__left">
          <div className="search-input">
            <input
              type="search"
              className="search-input__field"
              placeholder="全局搜索工单号、标题关键词..."
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>
          <select className="form-select" value={stateFilter} onChange={(event) => { setStateFilter(event.target.value); setOffset(0); }}>
            <option value="all">全部分析状态</option>
            <option value="unprocessed">未处理</option>
            <option value="analyzed">已分析</option>
            <option value="no_event">无事件</option>
            <option value="failed">失败</option>
          </select>
          <select className="form-select" value={urgentFilter} onChange={(event) => setUrgentFilter(event.target.value)}>
            <option value="all">全部紧急状态</option>
            <option value="urgent">仅紧急（当前页）</option>
          </select>
        </div>
        <span className="filter-bar__count">后端共 <strong>{total}</strong> 条</span>
      </div>

      {query.isPending ? (
        <div className="loading-state" role="status">正在读取后端工单...</div>
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : items.length === 0 ? (
        <EmptyState title="暂无工单" description="后端没有返回与当前条件匹配的工单。" />
      ) : (
        <div style={{ overflow: "hidden", borderRadius: "var(--radius-lg)" }}>
          <table className="data-table">
            <thead>
              <tr><th>工单号</th><th>工单标题</th><th>类型标签</th><th>分析状态</th><th>事件数</th><th>紧急</th><th>接收时间</th><th>操作</th></tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const number = item.external_work_order_number ?? `WO-${item.source_row_number}`;
                const title = item.raw_title?.trim() || "未提供标题";
                const badge = getStateBadge(item.analysis_state);
                return (
                  <tr key={item.work_order_id}>
                    <td><Link to={`/work-orders/${item.work_order_id}`} className="data-table__wo-link">{number}</Link></td>
                    <td><span className="data-table__title-text">{title.length > 40 ? `${title.slice(0, 40)}...` : title}</span></td>
                    <td><div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>{item.title_tags.length > 0 ? item.title_tags.slice(0, 2).map((tag) => <span key={tag} className={`tag ${getTagVariant(tag)}`}>{tag}</span>) : <span className="text-muted">未提供</span>}</div></td>
                    <td><span className={badge.cls}>{badge.label}</span></td>
                    <td>{item.event_count}</td>
                    <td>{item.is_urgent ? <span className="tag tag--danger">紧急</span> : <span className="text-muted">—</span>}</td>
                    <td className="text-muted">{formatTime(item.created_at)}</td>
                    <td><Link to={`/work-orders/${item.work_order_id}`} className="table-action-link">详情 →</Link></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!query.isPending && !query.isError && items.length > 0 ? <Pagination offset={offset} limit={PAGE_SIZE} total={total} onPageChange={setOffset} /> : null}
    </section>
  );
}
