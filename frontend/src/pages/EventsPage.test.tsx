import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { EventsPage } from "./EventsPage";

afterEach(() => {
  vi.restoreAllMocks();
});

test("renders the backend high-frequency decision without recomputing it", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(
      JSON.stringify({
        items: [
          {
            cluster_id: "cluster-high",
            name: "三天内重复反映",
            status: "active",
            confidence: 0.9,
            handling_status: "unhandled",
            member_count: 3,
            work_order_count: 3,
            event_count: 3,
            evidence: { summary: "真实摘要" },
            trace: null,
            review_status: "pending_review",
            is_multi_frequency: true,
            is_high_frequency: true,
            frequency_window_days: 3,
            frequency_work_order_count: 3,
          },
        ],
        offset: 0,
        limit: 10,
        total: 1,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    ),
  );

  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <EventsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("三天内重复反映")).toBeInTheDocument();
  expect(screen.getByText("高频 · 3天内3条工单")).toBeInTheDocument();
  expect(screen.getByText(/滚动三天日历窗口判定/)).toBeInTheDocument();
});
