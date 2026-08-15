import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { ClusterDetailPage } from "./ClusterDetailPage";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

const trace = {
  provider: "remote-openai-compatible",
  model_id: "qwen-plus",
  model_config_hash: "hash",
  schema_version: "understanding.v2",
  knowledge_snapshot_id: null,
  pipeline_version: "understanding.v2",
};

function event(eventId: string, workOrderId: string, summary: string, ordinal: number) {
  return {
    event_id: eventId,
    work_order_id: workOrderId,
    ordinal,
    event_type: "commercial_noise",
    behavior: "要求处理",
    normalized_summary: summary,
    entities: [],
    location_signals: ["新桂北路29号116号铺"],
    time_signals: [],
    evidence: [],
    trace,
  };
}

function workOrder(workOrderId: string, sourceRow: number, eventCount: number) {
  return {
    work_order_id: workOrderId,
    external_work_order_number: `WO-${sourceRow}`,
    source_row_number: sourceRow,
    raw_title: "商业噪声",
    created_at: "2026-08-15T00:00:00Z",
    event_count: eventCount,
    cluster_count: 1,
  };
}

test("groups multiple AI events under one distinct work order card", async () => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
  const workOrderA = workOrder("work-order-a", 1, 2);
  const workOrderB = workOrder("work-order-b", 2, 1);
  const eventA1 = event("event-a1", workOrderA.work_order_id, "商业噪声投诉", 0);
  const eventA2 = event("event-a2", workOrderA.work_order_id, "要求再次关停音响", 1);
  const eventB1 = event("event-b1", workOrderB.work_order_id, "再次反映商业噪声", 0);
  const payload = {
    summary: {
      cluster_id: "cluster-1",
      name: "同一地点商业噪声",
      status: "active",
      confidence: 0.95,
      handling_status: "unhandled",
      member_count: 2,
      work_order_count: 2,
      event_count: 3,
      evidence: {},
      trace,
    },
    members: [
      { event: eventA1, work_order: workOrderA, raw_title: "商业噪声", raw_content: "同一原始正文" },
      { event: eventA2, work_order: workOrderA, raw_title: "商业噪声", raw_content: "同一原始正文" },
      { event: eventB1, work_order: workOrderB, raw_title: "商业噪声", raw_content: "另一张原始工单" },
    ],
    work_orders: [
      {
        summary: workOrderA,
        import_batch_id: "batch-1",
        raw_content: "同一原始正文",
        raw_fields: {},
        events: [eventA1, eventA2],
      },
      {
        summary: workOrderB,
        import_batch_id: "batch-1",
        raw_content: "另一张原始工单",
        raw_fields: {},
        events: [eventB1],
      },
    ],
    edges: [],
    handling_history: [],
    human_corrections: [],
  };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/events/cluster-1"]}>
        <Routes>
          <Route path="/events/:clusterId" element={<ClusterDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  expect(screen.getAllByText("同一原始正文")).toHaveLength(1);
  expect(screen.getByText("商业噪声投诉")).toBeInTheDocument();
  expect(screen.getByText("要求再次关停音响")).toBeInTheDocument();
  expect(screen.getByText("再次反映商业噪声")).toBeInTheDocument();
});
