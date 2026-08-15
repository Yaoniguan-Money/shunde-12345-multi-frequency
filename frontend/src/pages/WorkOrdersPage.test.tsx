import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { WorkOrdersPage } from "./WorkOrdersPage";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

function renderPage(initialPath = "/work-orders") {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/work-orders" element={<WorkOrdersPage />} />
          <Route
            path="/work-orders/:workOrderId"
            element={<div>DETAIL_STUB</div>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("renders work order list with search triggering new query", async () => {
  const payload = {
    items: [
      {
        work_order_id: "wo-1",
        external_work_order_number: "WO-2026-0001",
        source_row_number: 1,
        raw_title: "商业噪声投诉",
        created_at: "2026-08-15T01:23:45Z",
        event_count: 2,
        cluster_count: 1,
      },
      {
        work_order_id: "wo-2",
        external_work_order_number: "WO-2026-0002",
        source_row_number: 2,
        raw_title: "占道经营",
        created_at: "2026-08-15T02:00:00Z",
        event_count: 1,
        cluster_count: 0,
      },
    ],
    offset: 0,
    limit: 20,
    total: 35,
  };

  let callCount = 0;
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input: RequestInfo | URL) => {
      callCount += 1;
      const url = new URL(String(input));
      const query = url.searchParams.get("query");
      if (callCount === 1) {
        expect(query).toBeNull();
        return new Response(JSON.stringify(payload), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      // 第二次为搜索后的请求
      expect(query).toBe("占道");
      expect(url.searchParams.get("offset")).toBe("0");
      return new Response(
        JSON.stringify({
          items: [payload.items[1]],
          offset: 0,
          limit: 20,
          total: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });

  renderPage();

  expect(await screen.findByText("商业噪声投诉")).toBeInTheDocument();
  expect(screen.getByText("占道经营")).toBeInTheDocument();
  expect(screen.getByText(/共 35 条/)).toBeInTheDocument();

  // 搜索 debounce 350ms
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fireEvent.change(screen.getByPlaceholderText(/全局搜索/), {
    target: { value: "占道" },
  });
  vi.advanceTimersByTime(400);
  vi.useRealTimers();

  await waitFor(() => {
    expect(screen.getByText(/共 1 条/)).toBeInTheDocument();
  });
  expect(screen.queryByText("商业噪声投诉")).not.toBeInTheDocument();
  expect(screen.getByText("占道经营")).toBeInTheDocument();
  expect(fetchSpy).toHaveBeenCalledTimes(2);
});

test("pagination click triggers new offset", async () => {
  let callCount = 0;
  const fetchSpy = vi
    .spyOn(globalThis, "fetch")
    .mockImplementation(async (input: RequestInfo | URL) => {
      callCount += 1;
      const url = new URL(String(input));
      const offset = url.searchParams.get("offset");
      if (callCount === 1) {
        expect(offset).toBe("0");
        return new Response(
          JSON.stringify({
            items: [
              {
                work_order_id: "wo-1",
                external_work_order_number: "WO-1",
                source_row_number: 1,
                raw_title: "首页工单",
                created_at: "2026-08-15T00:00:00Z",
                event_count: 1,
                cluster_count: 0,
              },
            ],
            offset: 0,
            limit: 20,
            total: 30,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      expect(offset).toBe("20");
      return new Response(
        JSON.stringify({
          items: [
            {
              work_order_id: "wo-2",
              external_work_order_number: "WO-2",
              source_row_number: 21,
              raw_title: "第二页工单",
              created_at: "2026-08-15T01:00:00Z",
              event_count: 1,
              cluster_count: 0,
            },
          ],
          offset: 20,
          limit: 20,
          total: 30,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    });

  renderPage();

  expect(await screen.findByText("首页工单")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));
  expect(await screen.findByText("第二页工单")).toBeInTheDocument();
  expect(fetchSpy).toHaveBeenCalledTimes(2);
});

test("shows empty state when total is 0", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ items: [], offset: 0, limit: 20, total: 0 }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  renderPage();
  expect(await screen.findByText("暂无工单")).toBeInTheDocument();
});

test("shows error state on failure", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "boom" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    }),
  );
  renderPage();
  expect(await screen.findByText(/请求失败/)).toBeInTheDocument();
  expect(screen.getByText("重试")).toBeInTheDocument();
});
