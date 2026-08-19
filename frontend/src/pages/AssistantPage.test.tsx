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
  topic_groups: [{ label: "欠薪", count: 1 }],
  handling_groups: [{ label: "unhandled", count: 1 }],
  work_orders: [{
    work_order_id: "11111111-1111-1111-1111-111111111111",
    external_work_order_number: "WO-1",
    title: "拖欠工资",
    reported_at: "2026-08-01T00:00:00Z",
    time_label: "业务受理时间",
    normalized_summary: "司机工资未结清",
    location: "大良",
    event_type: "欠薪",
    handling_status: "unhandled",
    cluster_ids: [],
    is_multi_frequency: false,
    retrieval_evidence: ["地点命中：大良"],
  }],
  cluster_ids: [],
  retrieval_trace: [],
};

afterEach(() => vi.restoreAllMocks());

test("keeps a conversation history and does not auto-select retrieved work orders", async () => {
  let calls = 0;
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => {
    calls += 1;
    const response = calls === 1
      ? FIRST_RESPONSE
      : { ...FIRST_RESPONSE, original_query: "那最近一个月呢？", answer: "最近一个月没有记录。", total: 0, work_orders: [] };
    return new Response(JSON.stringify(response), { status: 200, headers: { "Content-Type": "application/json" } });
  });

  render(<MemoryRouter><AssistantPage /></MemoryRouter>);
  const input = screen.getByLabelText("自然语言工单查询");
  fireEvent.change(input, { target: { value: "大良有没有拖欠工资" } });
  fireEvent.click(screen.getByRole("button", { name: "开始对话" }));

  expect(await screen.findByText("有。当前检索范围内找到 1 条直接相关工单。")).toBeInTheDocument();
  expect((screen.getByRole("checkbox") as HTMLInputElement).checked).toBe(false);
  expect(screen.getByText("已选择 0 条")).toBeInTheDocument();

  fireEvent.change(input, { target: { value: "那最近一个月呢？" } });
  fireEvent.click(screen.getByRole("button", { name: "开始对话" }));
  expect(await screen.findByText("最近一个月没有记录。")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByText("大良有没有拖欠工资")).toBeInTheDocument());
  expect(calls).toBe(2);
});
