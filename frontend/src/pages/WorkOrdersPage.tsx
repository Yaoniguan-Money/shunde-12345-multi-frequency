import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import type { JSX } from "react";

import { listWorkOrders } from "../api/catalog";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Pagination } from "../components/Pagination";
import { SearchInput } from "../components/SearchInput";
import { Skeleton } from "../components/Skeleton";

gsap.registerPlugin(useGSAP);

const PAGE_SIZE = 20;
const DEBOUNCE_MS = 350;

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

export function WorkOrdersPage(): JSX.Element {
  const navigate = useNavigate();
  const containerRef = useRef<HTMLElement>(null);
  const [offset, setOffset] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  // 全局搜索 debounce：与 /events 的“当前页筛选”不同，此处会触发后端全量检索。
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

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".work-order-card", {
          opacity: 0,
          y: 12,
          duration: 0.3,
          stagger: 0.04,
          ease: "power1.out",
        });
      });
    },
    { scope: containerRef, dependencies: [query.data?.items] },
  );

  const total = query.data?.total ?? 0;
  const items = query.data?.items ?? [];
  const isFetching = query.isFetching;

  return (
    <section ref={containerRef}>
      <header className="page-header">
        <div>
          <p className="eyebrow">WORK ORDERS</p>
          <h1 className="page-header__title">工单中心</h1>
          <p className="page-header__subtitle">
            原始 12345 工单浏览与检索。点击工单查看 AI 派生事件理解。
          </p>
        </div>
      </header>

      <div className="toolbar">
        <div className="toolbar__group">
          <label className="toolbar__label" htmlFor="work-orders-search">
            全局搜索
          </label>
          <SearchInput
            value={searchInput}
            onChange={setSearchInput}
            placeholder="按工单编号/标题等全局搜索（后端全量检索，非当前页筛选）"
            maxLength={128}
          />
        </div>
        <span className="toolbar__hint">
          全局搜索（后端全量匹配），非当前页筛选
          {debouncedQuery ? ` · 当前关键词：“${debouncedQuery}”` : ""}
          {isFetching ? " · 加载中…" : ""}
        </span>
      </div>

      {query.isPending ? (
        <Skeleton variant="list" count={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : total === 0 ? (
        <EmptyState
          title={debouncedQuery ? "未匹配到工单" : "暂无工单"}
          description={
            debouncedQuery
              ? `后端按关键词 “${debouncedQuery}” 全量检索后未返回任何工单。可调整关键词后重试。`
              : "后端尚未导入任何工单。请通过“数据导入与 AI 研判”流程导入后再返回查看。"
          }
          action={
            debouncedQuery ? (
              <button
                type="button"
                className="btn btn--ghost"
                onClick={() => setSearchInput("")}
              >
                清空搜索
              </button>
            ) : undefined
          }
        />
      ) : (
        <div className="cluster-list">
          {items.map((item) => (
            <button
              key={item.work_order_id}
              type="button"
              className="cluster-card work-order-card"
              onClick={() => navigate(`/work-orders/${item.work_order_id}`)}
            >
              <div className="cluster-card__header">
                <h3 className="cluster-card__name">
                  {item.raw_title ??
                    item.external_work_order_number ??
                    `工单 #${item.source_row_number}`}
                </h3>
                <span className="uuid-mono">#{item.source_row_number}</span>
              </div>
              <div className="cluster-card__meta">
                <span className="cluster-card__meta-item">
                  <span className="cluster-card__meta-key">外部工单号</span>
                  <span className="cluster-card__meta-value">
                    {item.external_work_order_number ?? "—"}
                  </span>
                </span>
                <span className="cluster-card__meta-item">
                  <span className="cluster-card__meta-key">AI 事件</span>
                  <span className="cluster-card__meta-value">
                    {item.event_count}
                  </span>
                </span>
                <span className="cluster-card__meta-item">
                  <span className="cluster-card__meta-key">关联多频事件</span>
                  <span className="cluster-card__meta-value">
                    {item.cluster_count}
                  </span>
                </span>
                <span className="cluster-card__meta-item">
                  <span className="cluster-card__meta-key">入库时间</span>
                  <span className="cluster-card__meta-value">
                    {formatTime(item.created_at)}
                  </span>
                </span>
              </div>
              <div className="cluster-card__footer">
                <span className="cluster-card__footer-link">查看工单详情 →</span>
              </div>
            </button>
          ))}
        </div>
      )}

      <Pagination
        offset={offset}
        limit={PAGE_SIZE}
        total={total}
        onPageChange={setOffset}
      />
    </section>
  );
}
