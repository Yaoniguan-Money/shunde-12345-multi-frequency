import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { App } from "./App";

afterEach(() => vi.restoreAllMocks());

function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/events"]}>
        <Routes>
          <Route path="/" element={<App />}>
            <Route path="events" element={<div>EVENTS_PAGE_STUB</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders the workbench shell with sidebar nav and health indicator", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ status: "alive" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );

  renderApp();

  // 侧边导航三项
  expect(screen.getByText("多频事件")).toBeInTheDocument();
  expect(screen.getByText("工单中心")).toBeInTheDocument();
  expect(screen.getByText("数据导入与AI研判")).toBeInTheDocument();
  // 嵌套路由 outlet 渲染
  expect(screen.getByText("EVENTS_PAGE_STUB")).toBeInTheDocument();
  // 健康指示器在后端 alive 时显示“后端在线”
  await waitFor(() => {
    expect(screen.getByText("后端在线")).toBeInTheDocument();
  });
});

test("shows backend disconnected when health check fails", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

  renderApp();

  await waitFor(() => {
    expect(screen.getByText("后端未连接")).toBeInTheDocument();
  });
});
