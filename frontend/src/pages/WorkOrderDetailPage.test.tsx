import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { WorkOrderDetailPage } from "./WorkOrderDetailPage";

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

function event(eventId: string, summary: string, ordinal: number) {
  return {
    event_id: eventId,
    work_order_id: "wo-1",
    ordinal,
    event_type: "commercial_noise",
    behavior: "要求处理",
    normalized_summary: summary,
    entities: [
      {
        entity_id: "entity-1",
        standard_name: "新桂北路29号116号铺",
        entity_type: "location",
      },
    ],
    location_signals: ["新桂北路29号116号铺"],
    time_signals: ["2026-08-15 19:00"],
    evidence: [{ quote: "噪声扰民严重", segment: "商业噪声" }],
    trace,
  };
}

test("renders work order detail with multiple AI events", async () => {
  const payload = {
    summary: {
      work_order_id: "wo-1",
      external_work_order_number: "WO-2026-0001",
      source_row_number: 1,
      raw_title: "商业噪声投诉",
      created_at: "2026-08-15T01:23:45Z",
      event_count: 2,
      cluster_count: 1,
    },
    import_batch_id: "batch-1",
    raw_content: "市民反映新桂北路29号116号铺夜间营业噪声扰民严重。",
    raw_fields: {
      source: "12345热线",
      channel: "电话",
      contact: "匿名",
    },
    events: [
      event("event-1", "商业噪声投诉要求关停音响", 0),
      event("event-2", "要求再次核实处理", 1),
    ],
  };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/work-orders/wo-1"]}>
        <Routes>
          <Route
            path="/work-orders/:workOrderId"
            element={<WorkOrderDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(
    (await screen.findAllByText("商业噪声投诉")).length,
  ).toBeGreaterThan(0);
  // 两个 AI 事件都渲染
  expect(screen.getByText("商业噪声投诉要求关停音响")).toBeInTheDocument();
  expect(screen.getByText("要求再次核实处理")).toBeInTheDocument();
  // 原始工单区字段
  expect(screen.getAllByText("WO-2026-0001").length).toBeGreaterThan(0);
  expect(
    screen.getByText("市民反映新桂北路29号116号铺夜间营业噪声扰民严重。"),
  ).toBeInTheDocument();
  // 原始 raw_fields 三个 key 都渲染
  expect(screen.getByText("source")).toBeInTheDocument();
  expect(screen.getByText("channel")).toBeInTheDocument();
  expect(screen.getByText("contact")).toBeInTheDocument();
  // 实体 chip
  expect(screen.getAllByText("新桂北路29号116号铺").length).toBeGreaterThan(0);
  // 入库时间标签（不能误称“投诉发生时间”）
  expect(screen.getAllByText(/入库时间/).length).toBeGreaterThan(0);
  // 已关联多频事件数：仅展示数字，不生成链接
  expect(screen.getByText(/已关联多频事件数/)).toBeInTheDocument();
});

test("shows 404 empty state when work order not found", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ detail: "not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/work-orders/missing-id"]}>
        <Routes>
          <Route
            path="/work-orders/:workOrderId"
            element={<WorkOrderDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(await screen.findByText("工单不存在")).toBeInTheDocument();
  expect(screen.getByText("返回工单列表")).toBeInTheDocument();
});

test("shows empty state when events are empty (unidentified)", async () => {
  const payload = {
    summary: {
      work_order_id: "wo-2",
      external_work_order_number: "WO-2026-0002",
      source_row_number: 2,
      raw_title: "占道经营",
      created_at: "2026-08-15T02:00:00Z",
      event_count: 0,
      cluster_count: 0,
    },
    import_batch_id: "batch-1",
    raw_content: "占道经营原始正文",
    raw_fields: {},
    events: [],
  };
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/work-orders/wo-2"]}>
        <Routes>
          <Route
            path="/work-orders/:workOrderId"
            element={<WorkOrderDetailPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );

  expect(
    (await screen.findAllByText("占道经营")).length,
  ).toBeGreaterThan(0);
  expect(screen.getByText("未识别 / 暂无 AI 事件")).toBeInTheDocument();
});
