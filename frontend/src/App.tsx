import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import type { JSX } from "react";

import { fetchLiveness } from "./api/health";
import "./styles.css";

interface NavItem {
  to: string;
  label: string;
  tag?: string;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/events", label: "多频事件", end: false },
  { to: "/work-orders", label: "工单中心", tag: "即将上线" },
  { to: "/imports", label: "数据导入与AI研判", tag: "即将上线" },
];

function HealthIndicator(): JSX.Element {
  const health = useQuery({
    queryKey: ["backend-liveness"],
    queryFn: ({ signal }) => fetchLiveness(signal),
    retry: false,
    refetchInterval: 30_000,
  });

  const dotClass = health.isPending
    ? "is-loading"
    : health.isSuccess
      ? "is-alive"
      : "is-down";
  const label = health.isPending
    ? "后端连接中…"
    : health.isSuccess
      ? "后端在线"
      : "后端未连接";

  return (
    <div className="app-topbar__health" title="后端 /health/live 实时状态">
      <span className={`health-dot ${dotClass}`} aria-hidden />
      <span>{label}</span>
    </div>
  );
}

export function App(): JSX.Element {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-sidebar__brand">
          <h2 className="app-sidebar__brand-title">顺德 12345</h2>
          <div className="app-sidebar__brand-sub">多频工单智能研判</div>
        </div>
        <nav className="app-sidebar__nav" aria-label="主导航">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `app-sidebar__nav-item${isActive ? " is-active" : ""}`
              }
            >
              <span>{item.label}</span>
              {item.tag ? <span className="nav-tag">{item.tag}</span> : null}
            </NavLink>
          ))}
        </nav>
        <div className="app-sidebar__footer">
          前端 phase · 核心展示链路
          <br />
          仅调用真实后端 API
        </div>
      </aside>

      <header className="app-topbar">
        <div className="app-topbar__title">多频工单智能研判工作台</div>
        <HealthIndicator />
      </header>

      <main className="app-main">
        <div className="app-main__inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
