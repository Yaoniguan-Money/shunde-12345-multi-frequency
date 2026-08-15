import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import type { JSX } from "react";

import { listClusters } from "../api/catalog";
import type { ClusterSummaryResponse } from "../types/api";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { Pagination } from "../components/Pagination";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
import {
  formatConfidence,
  summarizeEvidence,
} from "../utils/evidence";

gsap.registerPlugin(useGSAP);

type SortKey = "work_order_count" | "confidence" | "handling_status" | "default";

const PAGE_SIZE = 20;

export function EventsListPage(): JSX.Element {
  const navigate = useNavigate();
  const [offset, setOffset] = useState(0);
  const [sortKey, setSortKey] = useState<SortKey>("default");
  const [localFilter, setLocalFilter] = useState("");

  const query = useQuery({
    queryKey: ["clusters", { offset, limit: PAGE_SIZE }],
    queryFn: ({ signal }) =>
      listClusters({ offset, limit: PAGE_SIZE, signal }),
    placeholderData: (prev) => prev,
  });

  const containerRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".cluster-card", {
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

  const processedItems = useMemo<ClusterSummaryResponse[]>(() => {
    const items = query.data?.items ?? [];
    let result = [...items];

    if (localFilter.trim()) {
      const needle = localFilter.trim().toLowerCase();
      result = result.filter(
        (c) =>
          c.name.toLowerCase().includes(needle) ||
          (c.status ?? "").toLowerCase().includes(needle) ||
          (c.handling_status ?? "").toLowerCase().includes(needle),
      );
    }

    switch (sortKey) {
      case "work_order_count":
        result.sort((a, b) => b.work_order_count - a.work_order_count);
        break;
      case "confidence":
        result.sort((a, b) => (b.confidence ?? 0) - (a.confidence ?? 0));
        break;
      case "handling_status":
        result.sort((a, b) =>
          String(a.handling_status ?? "").localeCompare(
            String(b.handling_status ?? ""),
          ),
        );
        break;
      default:
        break;
    }
    return result;
  }, [query.data?.items, localFilter, sortKey]);

  const total = query.data?.total ?? 0;

  return (
    <section ref={containerRef}>
      <header className="page-header">
        <div>
          <p className="eyebrow">多频事件</p>
          <h1 className="page-header__title">多频事件</h1>
          <p className="page-header__subtitle">
            智能研判聚合后的民生事件。点击卡片查看事件详情与判断依据。
          </p>
        </div>
      </header>

      <div className="toolbar">
        <div className="toolbar__group">
          <label className="toolbar__label" htmlFor="sort-select">
            排序
          </label>
          <select
            id="sort-select"
            className="toolbar__select"
            value={sortKey}
            onChange={(e) => setSortKey(e.target.value as SortKey)}
          >
            <option value="default">默认（按接口顺序）</option>
            <option value="work_order_count">关联工单数 降序</option>
            <option value="confidence">置信度 降序</option>
            <option value="handling_status">处理状态 字典序</option>
          </select>
        </div>
        <div className="toolbar__group">
          <label className="toolbar__label" htmlFor="filter-input">
            当前页筛选
          </label>
          <input
            id="filter-input"
            className="search-input__field"
            type="search"
            value={localFilter}
            maxLength={128}
            placeholder="按名称/状态筛选本页"
            onChange={(e) => setLocalFilter(e.target.value)}
          />
        </div>
        <span className="toolbar__hint">仅作用于当前页，非全局搜索</span>
      </div>

      {query.isPending ? (
        <Skeleton variant="list" count={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => query.refetch()} />
      ) : total === 0 ? (
        <EmptyState
          title="暂无多频事件"
          description="后端尚未产生任何多频事件。请通过“数据导入与 AI 研判”流程触发研判后再返回查看。"
        />
      ) : processedItems.length === 0 ? (
        <EmptyState
          title="当前页筛选无匹配结果"
          description="调整筛选条件或清空筛选后重试。注意：此筛选仅作用于当前页。"
          action={
            <button
              type="button"
              className="btn btn--ghost"
              onClick={() => setLocalFilter("")}
            >
              清空筛选
            </button>
          }
        />
      ) : (
        <div className="cluster-list">
          {processedItems.map((cluster) => (
            <button
              key={cluster.cluster_id}
              type="button"
              className="cluster-card"
              onClick={() => navigate(`/events/${cluster.cluster_id}`)}
            >
              <div className="cluster-card__header">
                <h3 className="cluster-card__name">{cluster.name}</h3>
                <div className="cluster-card__badges">
                  <StatusBadge status={cluster.status} variant="analysis" />
                  <StatusBadge
                    status={cluster.handling_status}
                    variant="handling"
                  />
                </div>
              </div>
              <div className="cluster-card__meta">
                <span className="cluster-card__meta-item">
                  <span className="cluster-card__meta-key">关联工单</span>
                  <span className="cluster-card__meta-value">
                    {cluster.work_order_count}
                  </span>
                </span>
                <span className="cluster-card__meta-item">
                  <span className="cluster-card__meta-key">AI 事件</span>
                  <span className="cluster-card__meta-value">{cluster.event_count}</span>
                </span>
                <span className="cluster-card__meta-item">
                  <span className="cluster-card__meta-key">置信度</span>
                  <span className="confidence-bar">
                    <span className="cluster-card__meta-value">
                      {formatConfidence(cluster.confidence)}
                    </span>
                    <span className="confidence-bar__track">
                      <span
                        className="confidence-bar__fill"
                        style={{
                          width: `${Math.min(100, Math.max(0, (cluster.confidence ?? 0) * 100))}%`,
                        }}
                      />
                    </span>
                  </span>
                </span>
              </div>
              <div className="cluster-card__evidence">
                <span className="eyebrow" style={{ display: "block", marginBottom: 4 }}>
                  AI 判断依据摘要
                </span>
                {summarizeEvidence(cluster.evidence)}
              </div>
              <div className="cluster-card__footer">
                <span className="cluster-card__footer-link">查看详情 →</span>
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
