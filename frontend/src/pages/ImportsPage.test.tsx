import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, test, vi } from "vitest";

import { ImportsPage } from "./ImportsPage";

const PREVIEW_URL = /\/imports\/preview$/;
const IMPORT_URL = /\/imports$/;
const ANALYSIS_CREATE_URL = /\/analysis-jobs$/;
const PROVIDER_PROFILES_URL = /\/ai\/provider-profiles$/;
const PROVIDER_PROFILES = {
  items: [{
    profile_id: "cloud-qwen",
    deployment_kind: "cloud",
    display_name: "云端模型（千问，已适配）",
    configured: true,
    validation_status: "validated",
    last_validated_at: "2026-08-18T00:00:00Z",
    model_display_name: "qwen-plus",
    service_description: "synthetic test provider",
    configuration_version: "test",
  }],
};
function analysisGetUrl(jobId: string): RegExp {
  return new RegExp(`/analysis-jobs/${jobId}$`);
}

const SAMPLE_COLUMNS = ["序号", "工单编号", "标题", "内容"];
const SAMPLE_SUGGESTED: Record<string, string> = {
  source_row_number: "序号",
  external_work_order_number: "工单编号",
  title: "标题",
  content: "内容",
};

const IMPORT_RESULT = {
  batch_id: "batch-uuid-1234",
  status: "completed",
  total_rows: 100,
  successful_rows: 98,
  failed_rows: 2,
  duplicate_rows: 0,
  checkpoint_row: 100,
  idempotent: false,
};

const TRACE = {
  provider: "local-llm",
  model_id: "qwen-7b-q4",
  model_config_hash: "abc123",
  schema_version: "1.0.0",
  knowledge_snapshot_id: null,
  pipeline_version: "0.1.0",
};

const JOB_QUEUED = {
  job_id: "job-uuid-queued",
  status: "queued",
  current_stage: "queued",
  total_rows: 100,
  selected_rows: 50,
  processed_rows: 0,
  event_count: 0,
  match_edge_count: 0,
  cluster_count: 0,
  started_at: null,
  finished_at: null,
  error: null,
  trace: TRACE,
};

const JOB_RUNNING = {
  ...JOB_QUEUED,
  status: "running",
  current_stage: "matching",
  processed_rows: 25,
  started_at: "2026-08-15T01:00:00Z",
};

const JOB_COMPLETED = {
  ...JOB_QUEUED,
  status: "completed",
  current_stage: "completed",
  processed_rows: 50,
  event_count: 48,
  match_edge_count: 12,
  cluster_count: 3,
  started_at: "2026-08-15T01:00:00Z",
  finished_at: "2026-08-15T01:05:00Z",
};

const JOB_FAILED = {
  ...JOB_QUEUED,
  status: "failed",
  error: "local model timed out",
  started_at: "2026-08-15T01:00:00Z",
  finished_at: "2026-08-15T01:01:00Z",
};

// WorkOrdersPage.test.tsx 风格：直接 mock global fetch
function makeFile(
  name = "sample.xlsx",
  content = "fake",
  type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
): File {
  return new File([content], name, { type });
}

interface RenderOptions {
  initialPath?: string;
}

function renderPage({ initialPath = "/imports" }: RenderOptions = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/imports" element={<ImportsPage />} />
          <Route path="/events" element={<div>EVENTS_PAGE_STUB</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const urlMatches = (input: RequestInfo | URL, regex: RegExp): boolean => {
  const u = new URL(String(input));
  return regex.test(u.pathname);
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("ImportsPage - preview stage", () => {
  test("uses backend suggested_mapping to prefill mapping selects", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input: RequestInfo | URL) => {
        if (urlMatches(input, PREVIEW_URL)) {
          return new Response(
            JSON.stringify({
              columns: SAMPLE_COLUMNS,
              total_rows: 100,
              suggested_mapping: SAMPLE_SUGGESTED,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
        throw new Error(`unexpected fetch: ${String(input)}`);
      });

    renderPage();

    // 选择文件
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });
    expect(screen.getByText("sample.xlsx")).toBeInTheDocument();

    // 触发预览
    fireEvent.click(screen.getByTestId("start-preview-btn"));

    // 等待预览结果与映射表单出现
    await screen.findByTestId("mapping-content");

    // 断言每个目标字段的 select 默认值与 suggested_mapping 一致
    expect(
      (screen.getByTestId("mapping-content") as HTMLSelectElement).value,
    ).toBe("内容");
    expect(
      (screen.getByTestId("mapping-title") as HTMLSelectElement).value,
    ).toBe("标题");
    expect(
      (
        screen.getByTestId(
          "mapping-external_work_order_number",
        ) as HTMLSelectElement
      ).value,
    ).toBe("工单编号");
    expect(
      (screen.getByTestId("mapping-source_row_number") as HTMLSelectElement)
        .value,
    ).toBe("序号");

    // 断言显示了后端返回的行数与源字段
    expect(screen.getByText(/共 100 行/)).toBeInTheDocument();
    expect(fetchSpy).toHaveBeenCalled();
  });

  test("disables execute import button when content is unmapped", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (urlMatches(input, PREVIEW_URL)) {
        return new Response(
          JSON.stringify({
            columns: SAMPLE_COLUMNS,
            total_rows: 100,
            // suggested_mapping 不含 content，强制 content 未映射
            suggested_mapping: {
              source_row_number: "序号",
              external_work_order_number: "工单编号",
              title: "标题",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
      throw new Error(`unexpected fetch: ${String(input)}`);
    });

    renderPage();
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [makeFile()] },
    });
    fireEvent.click(screen.getByTestId("start-preview-btn"));
    await screen.findByTestId("mapping-content");

    const executeBtn = screen.getByTestId(
      "execute-import-btn",
    ) as HTMLButtonElement;
    expect(executeBtn.disabled).toBe(true);
    expect(
      screen.getByText(/“内容”字段必须映射到一个源列才能正式导入。/),
    ).toBeInTheDocument();
  });
});

describe("ImportsPage - import stage", () => {
  test("shows real batch_id after successful import", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        if (urlMatches(input, PREVIEW_URL)) {
          return new Response(
            JSON.stringify({
              columns: SAMPLE_COLUMNS,
              total_rows: 100,
              suggested_mapping: SAMPLE_SUGGESTED,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (urlMatches(input, IMPORT_URL)) {
          return new Response(JSON.stringify(IMPORT_RESULT), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
        throw new Error(`unexpected fetch: ${String(input)}`);
      });

    renderPage();
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [makeFile()] },
    });
    fireEvent.click(screen.getByTestId("start-preview-btn"));
    await screen.findByTestId("mapping-content");
    fireEvent.click(screen.getByTestId("execute-import-btn"));

    // 进入阶段4并显示 batch_id
    expect(await screen.findByTestId("batch-id")).toHaveTextContent(
      "batch-uuid-1234",
    );
    expect(fetchSpy).toHaveBeenCalled();
  });

  test("shows idempotent hint when backend reports idempotent hit", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (urlMatches(input, PREVIEW_URL)) {
        return new Response(
          JSON.stringify({
            columns: SAMPLE_COLUMNS,
            total_rows: 100,
            suggested_mapping: SAMPLE_SUGGESTED,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (urlMatches(input, IMPORT_URL)) {
        return new Response(
          JSON.stringify({ ...IMPORT_RESULT, idempotent: true }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
      throw new Error(`unexpected fetch: ${String(input)}`);
    });

    renderPage();
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [makeFile()] },
    });
    fireEvent.click(screen.getByTestId("start-preview-btn"));
    await screen.findByTestId("mapping-content");
    fireEvent.click(screen.getByTestId("execute-import-btn"));

    expect(await screen.findByTestId("batch-id")).toBeInTheDocument();
    expect(
      screen.getByText(/该文件已导入过，幂等命中/),
    ).toBeInTheDocument();
  });
});

describe("ImportsPage - analysis stage", () => {
  test("uses the validated provider and always targets the full successful batch", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (urlMatches(input, PREVIEW_URL)) {
        return new Response(
          JSON.stringify({
            columns: SAMPLE_COLUMNS,
            total_rows: 100,
            suggested_mapping: SAMPLE_SUGGESTED,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (urlMatches(input, IMPORT_URL)) {
        return new Response(JSON.stringify(IMPORT_RESULT), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
      throw new Error(`unexpected fetch: ${String(input)}`);
    });

    renderPage();
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [makeFile()] },
    });
    fireEvent.click(screen.getByTestId("start-preview-btn"));
    await screen.findByTestId("mapping-content");
    fireEvent.click(screen.getByTestId("execute-import-btn"));
    await screen.findByTestId("batch-id");

    const createBtn = screen.getByTestId(
      "create-job-btn",
    ) as HTMLButtonElement;
    await waitFor(() => expect(createBtn).not.toBeDisabled());
    expect(screen.queryByTestId("max-work-orders")).not.toBeInTheDocument();
    expect(screen.getByText(/本次将研判全部/)).toBeInTheDocument();
  });

  test("queued -> running -> completed UI with CTA to view events", async () => {
    // 用计数器模拟轮询序列：第1次GET返回running，第2次GET返回completed。
    let getCount = 0;
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        if (urlMatches(input, PREVIEW_URL)) {
          return new Response(
            JSON.stringify({
              columns: SAMPLE_COLUMNS,
              total_rows: 100,
              suggested_mapping: SAMPLE_SUGGESTED,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (urlMatches(input, IMPORT_URL)) {
          return new Response(JSON.stringify(IMPORT_RESULT), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (urlMatches(input, ANALYSIS_CREATE_URL)) {
          return new Response(JSON.stringify(JOB_QUEUED), {
            status: 202,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (urlMatches(input, analysisGetUrl(JOB_QUEUED.job_id))) {
          getCount += 1;
          const body = getCount === 1 ? JOB_RUNNING : JOB_COMPLETED;
          return new Response(JSON.stringify(body), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
        throw new Error(`unexpected fetch: ${String(input)}`);
      });

    renderPage();
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [makeFile()] },
    });
    fireEvent.click(screen.getByTestId("start-preview-btn"));
    await screen.findByTestId("mapping-content");
    fireEvent.click(screen.getByTestId("execute-import-btn"));
    await screen.findByTestId("batch-id");
    await waitFor(() => expect(screen.getByTestId("create-job-btn")).not.toBeDisabled());
    fireEvent.click(screen.getByTestId("create-job-btn"));

    // 创建后应显示 queued 状态徽章（StatusBadge data-testid=status-badge，中文映射"排队中"）
    const jobRoot = await screen.findByTestId("analysis-job");
    expect(
      within(jobRoot).getByTestId("status-badge"),
    ).toHaveTextContent("排队中");

    // 等待第一次轮询（2000ms）→ running，第二次轮询（4000ms）→ completed
    await waitFor(
      () => {
        expect(
          within(screen.getByTestId("analysis-job")).getByTestId(
            "status-badge",
          ),
        ).toHaveTextContent("已完成");
      },
      { timeout: 8000 },
    );

    expect(getCount).toBeGreaterThanOrEqual(2);
    expect(
      within(screen.getByTestId("analysis-job")).getByText("完整研判完成"),
    ).toBeInTheDocument();

    // 完成后展示 CTA
    expect(
      screen.getByTestId("goto-events-btn"),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("goto-events-btn"));
    await waitFor(() => {
      expect(screen.getByText("EVENTS_PAGE_STUB")).toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalled();
  });

  test("failed UI shows error text and retry returns to job creation form", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        if (urlMatches(input, PREVIEW_URL)) {
          return new Response(
            JSON.stringify({
              columns: SAMPLE_COLUMNS,
              total_rows: 100,
              suggested_mapping: SAMPLE_SUGGESTED,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (urlMatches(input, IMPORT_URL)) {
          return new Response(JSON.stringify(IMPORT_RESULT), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (urlMatches(input, ANALYSIS_CREATE_URL)) {
          return new Response(JSON.stringify(JOB_FAILED), {
            status: 202,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
        throw new Error(`unexpected fetch: ${String(input)}`);
      });

    renderPage();
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [makeFile()] },
    });
    fireEvent.click(screen.getByTestId("start-preview-btn"));
    await screen.findByTestId("mapping-content");
    fireEvent.click(screen.getByTestId("execute-import-btn"));
    await screen.findByTestId("batch-id");
    await waitFor(() => expect(screen.getByTestId("create-job-btn")).not.toBeDisabled());
    fireEvent.click(screen.getByTestId("create-job-btn"));

    // 失败状态展示错误原文
    await screen.findByTestId("analysis-job");
    expect(
      await screen.findByText(/local model timed out/),
    ).toBeInTheDocument();

    // 重新发起回到填表阶段
    fireEvent.click(screen.getByTestId("retry-job-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("create-job-btn")).toBeInTheDocument();
      expect(screen.queryByTestId("analysis-job")).not.toBeInTheDocument();
    });

    expect(fetchSpy).toHaveBeenCalled();
  });

  test("does not show a full-corpus analysis button", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      if (urlMatches(input, PREVIEW_URL)) {
        return new Response(
          JSON.stringify({
            columns: SAMPLE_COLUMNS,
            total_rows: 128278,
            suggested_mapping: SAMPLE_SUGGESTED,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (urlMatches(input, IMPORT_URL)) {
        return new Response(
          JSON.stringify({ ...IMPORT_RESULT, total_rows: 128278 }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (urlMatches(input, PROVIDER_PROFILES_URL)) return new Response(JSON.stringify(PROVIDER_PROFILES), { status: 200 });
      throw new Error(`unexpected fetch: ${String(input)}`);
    });

    renderPage();
    fireEvent.change(screen.getByTestId("file-input"), {
      target: { files: [makeFile()] },
    });
    fireEvent.click(screen.getByTestId("start-preview-btn"));
    await screen.findByTestId("mapping-content");
    fireEvent.click(screen.getByTestId("execute-import-btn"));
    await screen.findByTestId("batch-id");

    // 研判目标固定为导入批次全部成功工单，不提供 max_work_orders 输入。
    expect(screen.getByText(/本次将研判全部/)).toBeInTheDocument();
    expect(screen.queryByTestId("max-work-orders")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /全量|全部研判|分析全部/ }),
    ).not.toBeInTheDocument();
  });
});

describe("ImportsPage - select stage", () => {
  test("rejects unsupported file formats", async () => {
    renderPage();
    const input = screen.getByTestId("file-input") as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["x"], "notes.txt", { type: "text/plain" })] },
    });
    expect(
      await screen.findByText(/不支持的文件格式/),
    ).toBeInTheDocument();
  });
});
