import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { ToastProvider } from "../components/Toast";
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

function event(
  eventId: string,
  workOrderId: string,
  summary: string,
  ordinal: number,
) {
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

function detailPayload(overrides: Partial<{
  workOrders: ReturnType<typeof workOrder>[];
  eventsByWorkOrder: Record<string, ReturnType<typeof event>[]>;
  handlingHistory: unknown[];
  humanCorrections: unknown[];
  removedMembers: unknown[];
  workOrderCount: number;
  eventCount: number;
}> = {}) {
  const workOrderA = overrides.workOrders?.[0] ?? workOrder("work-order-a", 1, 2);
  const workOrderB =
    overrides.workOrders?.[1] ?? workOrder("work-order-b", 2, 1);
  const eventsByWorkOrder = overrides.eventsByWorkOrder ?? {
    [workOrderA.work_order_id]: [
      event("event-a1", workOrderA.work_order_id, "商业噪声投诉", 0),
      event("event-a2", workOrderA.work_order_id, "要求再次关停音响", 1),
    ],
    [workOrderB.work_order_id]: [
      event("event-b1", workOrderB.work_order_id, "再次反映商业噪声", 0),
    ],
  };
  return {
    summary: {
      cluster_id: "cluster-1",
      name: "同一地点商业噪声",
      status: "active",
      confidence: 0.95,
      handling_status: "unhandled",
      member_count: 2,
      work_order_count: overrides.workOrderCount ?? 2,
      event_count: overrides.eventCount ?? 3,
      evidence: {},
      trace,
    },
    members: [],
    work_orders: [workOrderA, workOrderB].map((wo) => ({
      summary: wo,
      import_batch_id: "batch-1",
      raw_content: `原始正文-${wo.work_order_id}`,
      raw_fields: {},
      events: eventsByWorkOrder[wo.work_order_id] ?? [],
    })),
    edges: [],
    handling_history: overrides.handlingHistory ?? [],
    human_corrections: overrides.humanCorrections ?? [],
    removed_members: overrides.removedMembers ?? [],
  };
}

function jsonOk(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function jsonError(status: number, detail: unknown): Response {
  return new Response(JSON.stringify({ detail }), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubMatchMedia(): void {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

interface RenderOptions {
  initialPath?: string;
  routes?: { path: string; element: React.ReactNode }[];
}

function renderPage(
  fetchImpl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
  options: RenderOptions = {},
) {
  vi.spyOn(globalThis, "fetch").mockImplementation(
    fetchImpl as unknown as typeof globalThis.fetch,
  );
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const initialPath = options.initialPath ?? "/events/cluster-1";
  const routes = options.routes ?? [
    { path: "/events/:clusterId", element: <ClusterDetailPage /> },
    { path: "/events", element: <div>EVENTS_LIST_STUB</div> },
  ];
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            {routes.map((r) => (
              <Route key={r.path} path={r.path} element={r.element} />
            ))}
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

test("groups multiple AI events under one distinct work order card", async () => {
  stubMatchMedia();
  renderPage(async () => jsonOk(detailPayload()));

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  // 每个原始工单只渲染一次
  expect(screen.getAllByText("原始正文-work-order-a")).toHaveLength(1);
  expect(screen.getAllByText("原始正文-work-order-b")).toHaveLength(1);
  expect(screen.getByText("商业噪声投诉")).toBeInTheDocument();
  expect(screen.getByText("要求再次关停音响")).toBeInTheDocument();
  expect(screen.getByText("再次反映商业噪声")).toBeInTheDocument();
  // 移除按钮数量应等于 event 总数（3）
  expect(screen.getAllByText("移出该多频事件")).toHaveLength(3);
});

test("work_order_count and event_count are shown in distinct positions", async () => {
  stubMatchMedia();
  renderPage(async () => jsonOk(detailPayload({ workOrderCount: 5, eventCount: 7 })));

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  // 顶部概览里分别展示关联工单数和研判事项数
  const meta = screen.getByLabelText("事件概况");
  expect(meta.textContent).toContain("关联工单");
  expect(meta.textContent).toContain("5");
  expect(meta.textContent).toContain("研判事项");
  expect(meta.textContent).toContain("7");
  // 关联工单 section title 含 work_orders.length（不是 work_order_count）
  // 这里 work_orders 数组长度 2，event_count 7
  // 用 getByRole 精确拿到 heading，避免误匹配 header meta
  const workOrdersSectionHeader = screen.getByRole("heading", {
    level: 2,
    name: /关联工单/,
  });
  expect(workOrdersSectionHeader.textContent).toContain("2 条工单");
  expect(workOrdersSectionHeader.textContent).toContain("7 项研判结果");
});

test("handling record submission invalidates detail and refetches", async () => {
  stubMatchMedia();
  let getCallCount = 0;
  const handlingResponse = {
    record_id: "rec-1",
    cluster_id: "cluster-1",
    previous_status: "unhandled",
    new_status: "investigating",
    actor_id: "demo-operator",
    description: "已派员核实",
    result: null,
    attachment_references: [],
    created_at: "2026-08-15T01:00:00Z",
  };
  renderPage(async (input, init) => {
    const url = new URL(String(input));
    const method = (init?.method ?? "GET").toUpperCase();
    if (
      url.pathname.endsWith("/handling-records") &&
      method === "POST"
    ) {
      getCallCount += 0;
      return jsonOk(handlingResponse, 201);
    }
    // GET cluster detail
    getCallCount += 1;
    if (getCallCount === 1) {
      return jsonOk(detailPayload({ handlingHistory: [] }));
    }
    // 第二次 GET 应携带新增的处理记录
    return jsonOk(
      detailPayload({ handlingHistory: [handlingResponse] }),
    );
  });

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  // 初始时间线为空，description "已派员核实" 不应出现
  expect(screen.queryByText("已派员核实")).not.toBeInTheDocument();

  fireEvent.click(screen.getByText("新增办理记录"));
  const statusInput = await screen.findByLabelText(/新状态/);
  fireEvent.change(statusInput, { target: { value: "investigating" } });
  fireEvent.click(screen.getByText("提交处理记录"));

  // 第二次 GET 后，时间线里应包含 description
  await waitFor(() => {
    expect(screen.getByText("已派员核实")).toBeInTheDocument();
  });
  // 时间线只向业务人员展示中文状态，不暴露后端枚举值
  expect(screen.getAllByText("未处理").length).toBeGreaterThan(0);
  expect(screen.getAllByText("处理中").length).toBeGreaterThan(0);
  expect(screen.queryByText("investigating")).not.toBeInTheDocument();
});

test("remove_member triggers confirm dialog and calls addCorrection", async () => {
  stubMatchMedia();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  let postedCorrectionBody: unknown = null;
  renderPage(async (input, init) => {
    const url = new URL(String(input));
    const method = (init?.method ?? "GET").toUpperCase();
    if (url.pathname.endsWith("/corrections") && method === "POST") {
      const text = init?.body;
      postedCorrectionBody = text ? JSON.parse(String(text)) : null;
      return jsonOk(
        {
          correction_id: "corr-1",
          cluster_id: "cluster-1",
          work_order_id: "work-order-a",
          correction_type: "remove_member",
          actor_id: "demo-operator",
          reason: null,
          payload: { event_instance_id: "event-a1" },
          supersedes_correction_id: null,
          created_at: "2026-08-15T02:00:00Z",
        },
        201,
      );
    }
    return jsonOk(detailPayload());
  });

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  // 点击第一个"移出该多频事件"按钮
  const removeButtons = await screen.findAllByText("移出该多频事件");
  fireEvent.click(removeButtons[0]);

  await waitFor(() => {
    expect(confirmSpy).toHaveBeenCalledTimes(1);
  });
  expect(confirmSpy.mock.calls[0][0]).toContain("移除");
  await waitFor(() => {
    expect(postedCorrectionBody).toEqual({
      correction_type: "remove_member",
      event_instance_id: expect.any(String),
      actor_id: "演示操作员",
    });
  });
  const body = postedCorrectionBody as { event_instance_id: string };
  expect(body.event_instance_id).toMatch(/^event-/);
});

test("remove_member followed by 404 on refetch shows toast and navigates to /events", async () => {
  stubMatchMedia();
  vi.spyOn(window, "confirm").mockReturnValue(true);
  let getCallCount = 0;
  renderPage(async (input, init) => {
    const url = new URL(String(input));
    const method = (init?.method ?? "GET").toUpperCase();
    if (url.pathname.endsWith("/corrections") && method === "POST") {
      return jsonOk(
        {
          correction_id: "corr-1",
          cluster_id: "cluster-1",
          work_order_id: "work-order-a",
          correction_type: "remove_member",
          actor_id: "demo-operator",
          reason: null,
          payload: { event_instance_id: "event-a1" },
          supersedes_correction_id: null,
          created_at: "2026-08-15T02:00:00Z",
        },
        201,
      );
    }
    getCallCount += 1;
    if (getCallCount === 1) {
      return jsonOk(detailPayload());
    }
    // 第二次 GET：模拟 cluster 已不再满足多频条件，被删除
    return jsonError(404, "cluster not found");
  });

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  fireEvent.click((await screen.findAllByText("移出该多频事件"))[0]);

  await waitFor(() => {
    expect(screen.getByText("EVENTS_LIST_STUB")).toBeInTheDocument();
  });
  expect(
    screen.getByText(/已不再满足多频条件/),
  ).toBeInTheDocument();
});

test("CSV export calls triggerBlobDownload with returned blob", async () => {
  stubMatchMedia();
  // 创建一个 spy 来观察 document.createElement('a') 的 click
  const createdLinks: HTMLAnchorElement[] = [];
  const realCreateElement = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
    const el = realCreateElement(tag);
    if (tag.toLowerCase() === "a") {
      const clickSpy = vi.fn();
      el.click = clickSpy;
      (el as unknown as { __clickSpy?: unknown }).__clickSpy = clickSpy;
      createdLinks.push(el as unknown as HTMLAnchorElement);
    }
    return el;
  });
  const csvContent = "cluster_id,work_order_id\nc1,wo1\n";
  const csvBlob = new Blob([csvContent], { type: "text/csv" });

  renderPage(async (input) => {
    const url = new URL(String(input));
    if (url.pathname.endsWith("/export.csv")) {
      return new Response(csvBlob, {
        status: 200,
        headers: {
          "Content-Type": "text/csv",
          "Content-Disposition": 'attachment; filename="cluster-1.csv"',
        },
      });
    }
    return jsonOk(detailPayload());
  });

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  fireEvent.click(screen.getByText("导出事件表格"));

  await waitFor(() => {
    expect(createdLinks.length).toBeGreaterThan(0);
  });
  const link = createdLinks[0];
  expect(link.download).toBe("cluster-1.csv");
  expect(
    (link as unknown as { __clickSpy?: { mock: { calls: unknown[] } } }).__clickSpy
      ?.mock.calls.length,
  ).toBe(1);
});

test("empty handling history and corrections show empty states", async () => {
  stubMatchMedia();
  renderPage(async () => jsonOk(detailPayload()));

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  expect(await screen.findAllByText("暂无处理记录")).toHaveLength(1);
  expect(await screen.findAllByText("暂无纠错记录")).toHaveLength(1);
});

test("existing handling history renders in timeline", async () => {
  stubMatchMedia();
  const history = [
    {
      record_id: "rec-1",
      cluster_id: "cluster-1",
      previous_status: "unhandled",
      new_status: "investigating",
      actor_id: "op-1",
      description: "派员核实",
      result: "已现场处理",
      attachment_references: ["att-1"],
      created_at: "2026-08-15T01:00:00Z",
    },
  ];
  renderPage(async () => jsonOk(detailPayload({ handlingHistory: history })));

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  expect(await screen.findByText("派员核实")).toBeInTheDocument();
  expect(screen.getByText("已现场处理")).toBeInTheDocument();
  expect(screen.getByText("att-1")).toBeInTheDocument();
  // 状态流转只显示中文标签
  expect(screen.getAllByText("未处理").length).toBeGreaterThan(0);
  expect(screen.getAllByText("处理中").length).toBeGreaterThan(0);
  expect(screen.queryByText("unhandled")).not.toBeInTheDocument();
});

test("removed events render in a separate restore section", async () => {
  stubMatchMedia();
  const removedEvent = event("event-a1", "work-order-a", "商业噪声投诉", 0);
  const corrections = [
    {
      correction_id: "corr-1",
      cluster_id: "cluster-1",
      work_order_id: "work-order-a",
      correction_type: "remove_member",
      actor_id: "op-1",
      reason: "误判",
      payload: { event_instance_id: "event-a1" },
      supersedes_correction_id: null,
      created_at: "2026-08-15T01:00:00Z",
    },
  ];
  renderPage(async () =>
    jsonOk(
      detailPayload({
        humanCorrections: corrections,
        removedMembers: [
          {
            event: removedEvent,
            event_instance_id: "event-a1",
            work_order: workOrder("work-order-a", 1, 1),
            raw_title: "商业噪声",
            raw_content: "原始正文-work-order-a",
            correction_id: "corr-1",
            actor_id: "op-1",
            reason: "误判",
            removed_at: "2026-08-15T01:00:00Z",
            can_restore: true,
          },
        ],
        eventsByWorkOrder: {
          "work-order-a": [
            event("event-a2", "work-order-a", "要求再次关停音响", 1),
          ],
          "work-order-b": [
            event("event-b1", "work-order-b", "再次反映商业噪声", 0),
          ],
        },
        eventCount: 2,
      }),
    ),
  );

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  expect(screen.getByRole("heading", { level: 2, name: /已移出事件/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "恢复归属" })).toBeInTheDocument();
  expect(screen.getAllByText("移出该多频事件")).toHaveLength(2);
  // 纠错历史里 reason "误判" 出现在 "理由：误判" span 中
  expect(screen.getAllByText(/误判/).length).toBeGreaterThan(0);
});

test("restoring removed event sends explicit actor and reason", async () => {
  stubMatchMedia();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  let postedCorrectionBody: unknown = null;
  let getCallCount = 0;
  const removedEvent = event("event-a1", "work-order-a", "商业噪声投诉", 0);
  const removedMember = {
    event: removedEvent,
    event_instance_id: "event-a1",
    work_order: workOrder("work-order-a", 1, 1),
    raw_title: "商业噪声",
    raw_content: "原始正文-work-order-a",
    correction_id: "corr-1",
    actor_id: "op-1",
    reason: "误判",
    removed_at: "2026-08-15T01:00:00Z",
    can_restore: true,
  };
  renderPage(async (input, init) => {
    const url = new URL(String(input));
    const method = (init?.method ?? "GET").toUpperCase();
    if (url.pathname.endsWith("/corrections") && method === "POST") {
      postedCorrectionBody = JSON.parse(String(init?.body));
      return jsonOk({ correction_id: "corr-2" }, 201);
    }
    getCallCount += 1;
    if (getCallCount === 1) {
      return jsonOk(
        detailPayload({
          removedMembers: [removedMember],
          eventsByWorkOrder: {
            "work-order-a": [
              event("event-a2", "work-order-a", "要求再次关停音响", 1),
            ],
            "work-order-b": [
              event("event-b1", "work-order-b", "再次反映商业噪声", 0),
            ],
          },
          eventCount: 2,
        }),
      );
    }
    return jsonOk(
      detailPayload({
        eventsByWorkOrder: {
          "work-order-a": [
            event("event-a1", "work-order-a", "商业噪声投诉", 0),
            event("event-a2", "work-order-a", "要求再次关停音响", 1),
          ],
          "work-order-b": [
            event("event-b1", "work-order-b", "再次反映商业噪声", 0),
          ],
        },
      }),
    );
  });

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  const restoreActorInputs = screen.getAllByPlaceholderText("请输入操作员编号");
  fireEvent.change(restoreActorInputs[restoreActorInputs.length - 1], {
    target: { value: "reviewer-2" },
  });
  fireEvent.change(screen.getByPlaceholderText("例如：误判，恢复归属"), {
    target: { value: "确认属于同一现实事件" },
  });
  fireEvent.click(screen.getByRole("button", { name: "恢复归属" }));

  await waitFor(() => expect(confirmSpy).toHaveBeenCalledTimes(1));
  await waitFor(() => {
    expect(postedCorrectionBody).toEqual({
      correction_type: "confirm_member",
      event_instance_id: "event-a1",
      actor_id: "reviewer-2",
      reason: "确认属于同一现实事件",
    });
  });
  await waitFor(() => expect(screen.getAllByText("移出该多频事件")).toHaveLength(3));
});

// 防止 React act 警告：所有 fireEvent 都包裹在 act 中（testing-library 已默认）
// 上面的 test 全部使用 fireEvent / waitFor，已隐式 act。
test("actor id is required for remove_member submission", async () => {
  stubMatchMedia();
  const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
  renderPage(async () => jsonOk(detailPayload()));

  expect(await screen.findByText("同一地点商业噪声")).toBeInTheDocument();
  // 清空第一个 actor input
  const actorInputs = screen.getAllByPlaceholderText("请输入操作员编号");
  fireEvent.change(actorInputs[0], { target: { value: "" } });
  fireEvent.click(screen.getAllByText("移出该多频事件")[0]);
  // 由于按钮 disabled，click 不会触发 confirm
  expect(confirmSpy).not.toHaveBeenCalled();
});

test("technical evidence values are translated for business users", async () => {
  stubMatchMedia();
  const payload = detailPayload();
  payload.summary.evidence = {
    consistency: "complete_link_guard",
    locations: ["顺德区陈村镇"],
  };
  renderPage(async () => jsonOk(payload));

  expect(await screen.findByText("已通过关联完整性检查")).toBeInTheDocument();
  expect(screen.getByText("顺德区陈村镇")).toBeInTheDocument();
  expect(screen.queryByText("complete_link_guard")).not.toBeInTheDocument();
  expect(screen.getByText("智能判断摘要")).toBeInTheDocument();
});
