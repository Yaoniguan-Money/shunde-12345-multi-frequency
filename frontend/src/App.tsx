import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { useEffect, useState } from "react";
import type { JSX } from "react";

import { fetchDependencies, fetchLiveness } from "./api/health";
import "./styles.css";

interface NavItem {
  to: string;
  label: string;
  icon: JSX.Element;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  {
    to: "/",
    label: "研判总览",
    end: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    to: "/events",
    label: "多频事件",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 3" />
      </svg>
    ),
  },
  {
    to: "/work-orders",
    label: "工单中心",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </svg>
    ),
  },
  {
    to: "/imports",
    label: "数据导入与智能研判",
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="7 10 12 15 17 10" />
        <line x1="12" y1="15" x2="12" y2="3" />
      </svg>
    ),
  },
];

function SidebarStatus(): JSX.Element {
  const health = useQuery({
    queryKey: ["backend-liveness-sidebar"],
    queryFn: ({ signal }) => fetchLiveness(signal),
    retry: false,
    refetchInterval: 30_000,
  });
  const dependencies = useQuery({
    queryKey: ["backend-dependencies-sidebar"],
    queryFn: ({ signal }) => fetchDependencies(signal),
    retry: false,
    refetchInterval: 30_000,
  });

  const aiOk = health.isSuccess;
  const dependencyState = (key: "database" | "gazetteer") => {
    if (dependencies.isPending) return "loading";
    return dependencies.data?.[key]?.state === "up" ? "ok" : "down";
  };

  return (
    <div className="app-sidebar__status">
      <div className="app-sidebar__status-title">系统状态</div>
      <div className="app-sidebar__status-item">
        <span className={`status-dot ${aiOk ? "status-dot--ok" : health.isPending ? "status-dot--loading" : "status-dot--down"}`} />
        <span>{aiOk ? "后端在线" : health.isPending ? "后端连接中…" : "后端未连接"}</span>
      </div>
      <div className="app-sidebar__status-item">
        <span className={`status-dot status-dot--${dependencyState("database")}`} />
        <span>数据库 {dependencyState("database") === "ok" ? "正常" : dependencyState("database") === "loading" ? "检测中…" : "异常"}</span>
      </div>
      <div className="app-sidebar__status-item">
        <span className={`status-dot status-dot--${dependencyState("gazetteer")}`} />
        <span>地名服务 {dependencyState("gazetteer") === "ok" ? "正常" : dependencyState("gazetteer") === "loading" ? "检测中…" : "异常"}</span>
      </div>
    </div>
  );
}

function TopBar(): JSX.Element {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(timer);
  }, []);

  const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;

  const handleRefresh = () => {
    window.location.reload();
  };

  return (
    <header className="app-topbar">
      <div className="app-topbar__spacer" />
      <div className="app-topbar__actions">
        <span className="app-topbar__date">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ verticalAlign: "-2px", marginRight: 4 }}>
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
          {dateStr}
        </span>
        <button className="app-topbar__btn" onClick={handleRefresh} title="刷新">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
        <button className="app-topbar__btn" title="通知" style={{ position: "relative" }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
        </button>
        <div style={{ width: 34, height: 34, borderRadius: "50%", background: "linear-gradient(135deg,#3b82f6,#8b5cf6)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 13, fontWeight: 600, cursor: "pointer" }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
      </div>
    </header>
  );
}

export function App(): JSX.Element {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-sidebar__brand">
          <div className="app-sidebar__logo">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l4 2" />
            </svg>
          </div>
          <div className="app-sidebar__brand-text">
            <div className="app-sidebar__brand-title">顺德12345</div>
            <div className="app-sidebar__brand-sub">多频工单智能研判</div>
          </div>
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
              <span className="app-sidebar__nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <SidebarStatus />
        <div className="app-sidebar__user">
          <div className="app-sidebar__avatar">管</div>
          <div className="app-sidebar__user-info">
            <div className="app-sidebar__user-name">管理员</div>
            <div className="app-sidebar__user-role">系统管理员</div>
          </div>
        </div>
      </aside>

      <TopBar />

      <main className="app-main">
        <div className="app-main__inner">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
