import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

afterEach(() => {
  vi.restoreAllMocks();
});

function renderDashboard(): void {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

test("dashboard does not display simulated records when backend has no matching data", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
      new Response(
      JSON.stringify({
        items: [],
        offset: 0,
        limit: 100,
        total: 0,
        occurrence_dated_total: 0,
        occurrence_unknown_total: 0,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
      ),
  );

  renderDashboard();

  expect(await screen.findByText("工单总数")).toBeInTheDocument();
  expect(screen.queryByText("噪音扰民")).not.toBeInTheDocument();
  expect(screen.queryByText("占道经营")).not.toBeInTheDocument();
  expect(screen.queryByText("新高频事件预警")).not.toBeInTheDocument();
  expect(screen.queryByText("模拟数据")).not.toBeInTheDocument();
  expect(screen.queryByText("1243")).not.toBeInTheDocument();
});

test("dashboard renders only cluster records returned by the backend", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const path = new URL(String(input)).pathname;
    if (path === "/multi-frequency-events") {
      return new Response(
        JSON.stringify({
          items: [
            {
              cluster_id: "cluster-real",
              name: "真实后端事件",
              status: "active",
              confidence: 0.9,
              handling_status: "unhandled",
              member_count: 2,
              work_order_count: 2,
              event_count: 2,
              evidence: {},
              trace: null,
              review_status: "pending_review",
              is_multi_frequency: true,
              is_high_frequency: false,
              frequency_window_days: 3,
              frequency_work_order_count: 0,
            },
          ],
          offset: 0,
          limit: 20,
          total: 1,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(
      JSON.stringify({
        items: [],
        offset: 0,
        limit: 1,
        total: 0,
        occurrence_dated_total: 0,
        occurrence_unknown_total: 0,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  });

  renderDashboard();

  expect(await screen.findByText("真实后端事件")).toBeInTheDocument();
  expect(screen.queryByText("新高频事件预警")).not.toBeInTheDocument();
  expect(screen.queryByText("高频事件确认")).not.toBeInTheDocument();
});
