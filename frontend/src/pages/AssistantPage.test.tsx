import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";

import { AssistantPage } from "./AssistantPage";

const FIRST_RESPONSE = {
  original_query: "大良有没有拖欠工资",
  compiled_query: {
    intent: "search_work_orders",
    time_range: null,
    keywords: ["拖欠", "工资"],
    topic: "工资",
    title_tag: null,
    aggregation: "none",
    context_mode: "new_scope",
    issue_required: true,
    entity: null,
    location: "大良",
    event_type: null,
    handling_status: null,
    cluster_status: null,
    sort: "relevance",
    limit: 20,
    work_order_ids: [],
  },
  planner_mode: "rules",
  answer: "有。当前检索范围内找到 1 条直接相关工单。",
  disclaimer: "测试免责声明",
  total: 1,
  matched_total: 1,
  page: 1,
  page_size: 20,
  topic_groups: [{ label: "欠薪", count: 1 }],
  handling_groups: [{ label: "unhandled", count: 1 }],
  work_orders: [{
    work_order_id: "11111111-1111-1111-1111-111111111111",
    external_work_order_number: "WO-1",
    title: "拖欠工资",
    title_tags: [],
    is_urgent: false,
    reported_at: "2026-08-01T00:00:00Z",
    time_label: "业务受理时间",
    normalized_summary: "司机工资未结清",
    location: "大良",
    event_type: "欠薪",
    handling_status: "unhandled",
    cluster_ids: [],
    is_multi_frequency: false,
    is_high_frequency: false,
    retrieval_evidence: ["地点命中：大良"],
  }],
  cluster_ids: [],
  retrieval_trace: [],
};

const DASHBOARD_RESPONSE = {
  title: "当前查询洞察",
  work_order_count: 1,
  multi_frequency_event_count: 0,
  multi_frequency_work_order_count: 0,
  high_frequency_event_count: 0,
  urgent_count: 0,
  handling_groups: [{ label: "unhandled", count: 1 }],
  topic_groups: [{ label: "欠薪", count: 1 }],
  location_groups: [{ label: "大良", count: 1 }],
  topic_tree: [],
  location_tree: [],
  status_tree: [],
  focus_cluster_ids: [],
  disclaimer: "测试免责声明",
};

afterEach(() => vi.restoreAllMocks());

test("keeps query context in memory and does not auto-select retrieved work orders", async () => {
  let queryCalls = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    if (url.includes("/worksets")) {
      return new Response(JSON.stringify({ items: [], total: 0 }), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    if (url.includes("/agent/dashboard")) {
      return new Response(JSON.stringify(DASHBOARD_RESPONSE), { status: 200, headers: { "Content-Type": "application/json" } });
    }
    queryCalls += 1;
    const response = queryCalls === 1
      ? FIRST_RESPONSE
      : { ...FIRST_RESPONSE, original_query: "那最近一个月呢？", answer: "最近一个月没有记录。", total: 0, work_orders: [] };
    return new Response(JSON.stringify(response), { status: 200, headers: { "Content-Type": "application/json" } });
  });

  render(<MemoryRouter><AssistantPage /></MemoryRouter>);
  const input = screen.getByLabelText("自然语言工单查询");
  fireEvent.change(input, { target: { value: "大良有没有拖欠工资" } });
  fireEvent.click(screen.getByRole("button", { name: "开始研判" }));

  expect(await screen.findByText("有。当前检索范围内找到 1 条直接相关工单。")).toBeInTheDocument();
  expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(false);

  fireEvent.change(input, { target: { value: "那最近一个月呢？" } });
  fireEvent.click(screen.getByRole("button", { name: "开始研判" }));
  expect(await screen.findByText("最近一个月没有记录。")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("heading", { name: "那最近一个月呢？" })).toBeInTheDocument());
  expect(queryCalls).toBe(2);
});

test("pages the compiled scope without clearing a cross-page selection", async () => {
  const secondPageItem = { ...FIRST_RESPONSE.work_orders[0], work_order_id: "22222222-2222-2222-2222-222222222222", title: "第二页真实工单" };
  const requestPaths: string[] = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const url = String(input);
    requestPaths.push(url);
    if (url.includes("/worksets")) return new Response(JSON.stringify({ items: [], total: 0 }), { status: 200, headers: { "Content-Type": "application/json" } });
    if (url.includes("/agent/dashboard")) return new Response(JSON.stringify({ ...DASHBOARD_RESPONSE, work_order_count: 21 }), { status: 200, headers: { "Content-Type": "application/json" } });
    if (url.includes("/agent/query/results")) return new Response(JSON.stringify({ matched_total: 21, page: 2, page_size: 20, items: [secondPageItem] }), { status: 200, headers: { "Content-Type": "application/json" } });
    return new Response(JSON.stringify({ ...FIRST_RESPONSE, total: 21, matched_total: 21 }), { status: 200, headers: { "Content-Type": "application/json" } });
  });

  render(<MemoryRouter><AssistantPage /></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "容桂有什么事情" }));
  expect(await screen.findByRole("checkbox", { name: "选择" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("checkbox", { name: "选择" }));
  fireEvent.click(screen.getByRole("button", { name: "下一页" }));

  expect((await screen.findAllByText("第二页真实工单")).length).toBeGreaterThan(0);
  expect(screen.getByRole("button", { name: "建立工作集 · 1" })).toBeInTheDocument();
  expect(requestPaths.some((path) => path.includes("/agent/query/results"))).toBe(true);
});
