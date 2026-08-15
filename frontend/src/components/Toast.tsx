import {
  useCallback,
  useMemo,
  useRef,
  useState,
  type JSX,
  type ReactNode,
} from "react";

import { ToastContext, type ToastMessage } from "./toastContext";

export function ToastProvider({ children }: { children: ReactNode }): JSX.Element {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const counter = useRef(0);

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (text: string, kind: ToastMessage["kind"] = "info") => {
      const id = ++counter.current;
      setToasts((prev) => [...prev, { id, kind, text }]);
      window.setTimeout(() => dismiss(id), 4000);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ toasts, push, dismiss }), [toasts, push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-container" role="region" aria-label="通知">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`toast toast--${t.kind}`}
            role={t.kind === "error" ? "alert" : "status"}
          >
            <span className="toast__text">{t.text}</span>
            <button
              type="button"
              className="toast__close"
              onClick={() => dismiss(t.id)}
              aria-label="关闭"
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
