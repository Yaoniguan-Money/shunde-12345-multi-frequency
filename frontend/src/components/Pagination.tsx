import type { JSX } from "react";

interface PaginationProps {
  offset: number;
  limit: number;
  total: number;
  onPageChange: (offset: number) => void;
}

export function Pagination({
  offset,
  limit,
  total,
  onPageChange,
}: PaginationProps): JSX.Element | null {
  if (total <= 0) return null;
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  const goTo = (page: number) => {
    const nextOffset = Math.max(0, Math.min((page - 1) * limit, (totalPages - 1) * limit));
    if (nextOffset !== offset) onPageChange(nextOffset);
  };

  return (
    <nav className="pagination" aria-label="分页">
      <button
        type="button"
        className="btn btn--ghost"
        disabled={!hasPrev}
        onClick={() => goTo(currentPage - 1)}
      >
        上一页
      </button>
      <span className="pagination__info">
        第 <strong>{currentPage}</strong> / {totalPages} 页 · 共 {total} 条
      </span>
      <button
        type="button"
        className="btn btn--ghost"
        disabled={!hasNext}
        onClick={() => goTo(currentPage + 1)}
      >
        下一页
      </button>
    </nav>
  );
}
