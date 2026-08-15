import type { JSX } from "react";

import { ApiError } from "../api/client";

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
}

function describeError(error: unknown): {
  status?: number;
  detail?: string;
} {
  if (error instanceof ApiError) {
    let detailText: string | undefined;
    if (typeof error.detail === "string") {
      detailText = error.detail;
    } else if (error.detail && typeof error.detail === "object") {
      const maybe = error.detail as { detail?: unknown; message?: unknown };
      if (typeof maybe.detail === "string") detailText = maybe.detail;
      else if (typeof maybe.message === "string") detailText = maybe.message;
    }
    return { status: error.status, detail: detailText ?? error.message };
  }
  if (error instanceof Error) return { detail: error.message };
  return { detail: "未知错误" };
}

export function ErrorState({ error, onRetry }: ErrorStateProps): JSX.Element {
  const { status, detail } = describeError(error);
  const title = status ? `请求失败（HTTP ${status}）` : "请求失败";
  return (
    <div className="error-state" role="alert">
      <div className="error-state__icon" aria-hidden>
        !
      </div>
      <h3 className="error-state__title">{title}</h3>
      {detail ? <p className="error-state__detail">{detail}</p> : null}
      {onRetry ? (
        <button type="button" className="btn btn--primary" onClick={onRetry}>
          重试
        </button>
      ) : null}
    </div>
  );
}
