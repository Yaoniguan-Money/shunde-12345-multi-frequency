import {
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type FormEvent,
  type JSX,
} from "react";
import { useNavigate } from "react-router-dom";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";

import { createAnalysisJob, getAnalysisJob } from "../api/analysis";
import { describeApiError } from "../api/client";
import {
  executeImport,
  previewImport,
  type ImportMapping,
  type ImportPreviewResponse,
  type ImportResponse,
} from "../api/imports";
import type { AnalysisJobResponse } from "../types/api";
import { ErrorState } from "../components/ErrorState";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
import { TraceTag } from "../components/TraceTag";
import { ToastContext } from "../components/toastContext";

gsap.registerPlugin(useGSAP);

type Phase = "select" | "preview" | "importing" | "analysis";

interface TargetFieldDef {
  key: keyof ImportMapping;
  label: string;
  required: boolean;
  hint: string;
}

const TARGET_FIELDS: TargetFieldDef[] = [
  {
    key: "source_row_number",
    label: "源行号",
    required: false,
    hint: "Excel 行号列（可选，便于溯源）",
  },
  {
    key: "external_work_order_number",
    label: "外部工单号",
    required: false,
    hint: "12345 工单编号列（可选）",
  },
  {
    key: "title",
    label: "标题",
    required: false,
    hint: "工单标题列（可选）",
  },
  {
    key: "content",
    label: "内容",
    required: true,
    hint: "工单正文列（必填，AI 研判的核心输入）",
  },
];

const UNMAPPED_VALUE = "";
const UNMAPPED_LABEL = "未映射";
const ACCEPTED_EXT = [".xlsx", ".xls", ".csv"];
const POLL_INTERVAL_MS = 2000;
const MAX_WORK_ORDERS_DEFAULT = 50;
const MAX_WORK_ORDERS_MIN = 1;
const MAX_WORK_ORDERS_MAX = 300;

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function detectFormat(file: File): string {
  const name = file.name.toLowerCase();
  if (name.endsWith(".csv")) return "CSV";
  if (name.endsWith(".xlsx")) return "Excel (xlsx)";
  if (name.endsWith(".xls")) return "Excel (xls)";
  return file.type || "未知";
}

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXT.some((ext) => name.endsWith(ext));
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

function buildInitialMapping(suggested: Record<string, string>): ImportMapping {
  const mapping: ImportMapping = {};
  for (const field of TARGET_FIELDS) {
    const value = suggested[field.key];
    mapping[field.key] = value && value.length > 0 ? value : null;
  }
  return mapping;
}

function Stepper({ current }: { current: Phase }): JSX.Element {
  const steps: Array<{ phase: Phase; label: string }> = [
    { phase: "select", label: "选择文件" },
    { phase: "preview", label: "预览与映射" },
    { phase: "importing", label: "正式导入" },
    { phase: "analysis", label: "AI 研判" },
  ];
  const currentIndex = steps.findIndex((s) => s.phase === current);
  return (
    <ol className="stepper" aria-label="导入流程步骤">
      {steps.map((step, i) => {
        const state =
          i < currentIndex ? "done" : i === currentIndex ? "current" : "todo";
        return (
          <li
            key={step.phase}
            className={`stepper__item stepper__item--${state}`}
            aria-current={i === currentIndex ? "step" : undefined}
          >
            <span className="stepper__index" aria-hidden>
              {i + 1}
            </span>
            <span className="stepper__label">{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}

function SelectFileStage({
  file,
  previewLoading,
  previewError,
  onPickFile,
  onClearFile,
  onPreview,
}: {
  file: File | null;
  previewLoading: boolean;
  previewError: unknown;
  onPickFile: (file: File) => void;
  onClearFile: () => void;
  onPreview: () => void;
}): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [rejectReason, setRejectReason] = useState<string | null>(null);

  function handleFiles(files: FileList | null): void {
    setRejectReason(null);
    if (!files || files.length === 0) return;
    const f = files[0];
    if (!isAcceptedFile(f)) {
      setRejectReason(
        `不支持的文件格式：${f.name}。仅接受 .xlsx / .xls / .csv`,
      );
      return;
    }
    onPickFile(f);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  }

  return (
    <div className="imports-stage">
      <div
        className={`dropzone${dragOver ? " dropzone--over" : ""}`}
        onDrop={handleDrop}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        data-testid="dropzone"
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          className="dropzone__input"
          onChange={(e: ChangeEvent<HTMLInputElement>) =>
            handleFiles(e.target.files)
          }
          data-testid="file-input"
        />
        <div className="dropzone__prompt">
          <span className="dropzone__icon" aria-hidden>
            ⬆
          </span>
          <p className="dropzone__title">拖拽文件到此处，或点击选择</p>
          <p className="dropzone__hint">
            支持 .xlsx / .xls / .csv，仅本地读取，不上传到云端
          </p>
        </div>
      </div>

      {rejectReason ? (
        <p className="imports-error-line" role="alert">
          {rejectReason}
        </p>
      ) : null}

      {file ? (
        <div className="file-card">
          <div className="file-card__row">
            <span className="file-card__key">文件名</span>
            <span className="file-card__value">{file.name}</span>
          </div>
          <div className="file-card__row">
            <span className="file-card__key">格式</span>
            <span className="file-card__value">{detectFormat(file)}</span>
          </div>
          <div className="file-card__row">
            <span className="file-card__key">大小</span>
            <span className="file-card__value">
              {formatFileSize(file.size)}
            </span>
          </div>
          <div className="file-card__actions">
            <button
              type="button"
              className="btn btn--ghost btn--small"
              onClick={onClearFile}
              disabled={previewLoading}
            >
              重新选择
            </button>
            <button
              type="button"
              className="btn btn--primary"
              onClick={onPreview}
              disabled={previewLoading}
              data-testid="start-preview-btn"
            >
              {previewLoading ? "预览中…" : "开始预览"}
            </button>
          </div>
        </div>
      ) : null}

      {previewError ? (
        <div style={{ marginTop: 12 }}>
          <ErrorState error={previewError} />
        </div>
      ) : null}
    </div>
  );
}

function PreviewStage({
  preview,
  mapping,
  importLoading,
  onMappingChange,
  onExecute,
  onBackToSelect,
}: {
  preview: ImportPreviewResponse;
  mapping: ImportMapping;
  importLoading: boolean;
  onMappingChange: (next: ImportMapping) => void;
  onExecute: () => void;
  onBackToSelect: () => void;
}): JSX.Element {
  const contentUnmapped =
    !mapping.content || mapping.content.length === 0;
  const columnOptions = [UNMAPPED_LABEL, ...preview.columns];

  function handleChange(field: keyof ImportMapping, value: string): void {
    onMappingChange({
      ...mapping,
      [field]: value === UNMAPPED_VALUE ? null : value,
    });
  }

  return (
    <div className="imports-stage">
      <div className="detail-section">
        <h2 className="detail-section__title">
          后端预览结果
          <span className="detail-section__count">
            （共 {preview.total_rows} 行）
          </span>
        </h2>
        <div className="preview-summary">
          <span>
            <strong>{preview.total_rows}</strong> 行数据
          </span>
          <span>
            <strong>{preview.columns.length}</strong> 个源字段
          </span>
        </div>
        <div className="preview-columns">
          <span className="preview-columns__label">源字段列表：</span>
          <span className="preview-columns__list">
            {preview.columns.map((c) => (
              <span className="chip" key={c}>
                {c}
              </span>
            ))}
          </span>
        </div>
        <p className="text-muted" style={{ fontSize: 12, marginTop: 8 }}>
          预览数据由后端 /imports/preview 返回，前端不自行解析 Excel。
        </p>
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">字段映射</h2>
        <p className="text-muted" style={{ fontSize: 12, margin: "0 0 12px" }}>
          已根据后端 suggested_mapping 自动预填。请确认每个目标字段对应的源列；
          <strong>内容</strong>字段必填，其余可保持“未映射”。
        </p>
        <div className="mapping-form">
          {TARGET_FIELDS.map((field) => {
            const value = (mapping[field.key] ?? UNMAPPED_VALUE) as string;
            return (
              <div className="mapping-form__field" key={field.key}>
                <label
                  className="mapping-form__label"
                  htmlFor={`mapping-${field.key}`}
                >
                  {field.label}
                  {field.required ? <span className="req">*</span> : null}
                </label>
                <select
                  id={`mapping-${field.key}`}
                  className="mapping-form__select"
                  value={value}
                  onChange={(e) => handleChange(field.key, e.target.value)}
                  data-testid={`mapping-${field.key}`}
                  disabled={importLoading}
                >
                  {columnOptions.map((opt) => (
                    <option
                      key={opt}
                      value={opt === UNMAPPED_LABEL ? UNMAPPED_VALUE : opt}
                    >
                      {opt}
                    </option>
                  ))}
                </select>
                <span className="mapping-form__hint">{field.hint}</span>
              </div>
            );
          })}
        </div>
        {contentUnmapped ? (
          <p className="imports-error-line" role="alert">
            “内容”字段必须映射到一个源列才能正式导入。
          </p>
        ) : null}
      </div>

      <div className="action-toolbar">
        <button
          type="button"
          className="btn btn--ghost"
          onClick={onBackToSelect}
          disabled={importLoading}
        >
          ← 重新选择文件
        </button>
        <button
          type="button"
          className="btn btn--primary"
          onClick={onExecute}
          disabled={contentUnmapped || importLoading}
          data-testid="execute-import-btn"
        >
          {importLoading ? "导入中…" : "正式导入"}
        </button>
        <span className="action-toolbar__hint">
          导入为幂等操作；若该文件已导入过，将命中检查点并跳过重复行。
        </span>
      </div>
    </div>
  );
}

function ImportingStage(): JSX.Element {
  return (
    <div className="imports-stage">
      <Skeleton variant="detail" />
      <p className="text-muted" style={{ marginTop: 12 }}>
        正在向后端提交导入请求，请稍候…
      </p>
    </div>
  );
}

function AnalysisStage({
  importResult,
  jobId,
  job,
  jobError,
  createError,
  isCreating,
  maxWorkOrders,
  onMaxWorkOrdersChange,
  onCreateJob,
  onRetry,
  onNavigateEvents,
  onResetAll,
}: {
  importResult: ImportResponse;
  jobId: string | null;
  job: AnalysisJobResponse | null;
  jobError: unknown;
  createError: unknown;
  isCreating: boolean;
  maxWorkOrders: number;
  onMaxWorkOrdersChange: (n: number) => void;
  onCreateJob: () => void;
  onRetry: () => void;
  onNavigateEvents: () => void;
  onResetAll: () => void;
}): JSX.Element {
  const maxValid =
    Number.isInteger(maxWorkOrders) &&
    maxWorkOrders >= MAX_WORK_ORDERS_MIN &&
    maxWorkOrders <= MAX_WORK_ORDERS_MAX;
  const status = job?.status;
  const progressPct =
    job && job.selected_rows > 0
      ? Math.min(
          100,
          Math.round((job.processed_rows / job.selected_rows) * 100),
        )
      : 0;

  return (
    <div className="imports-stage">
      <div className="detail-section">
        <h2 className="detail-section__title">导入结果</h2>
        <div className="import-result">
          <div className="import-result__row">
            <span className="import-result__key">批次 ID</span>
            <span className="import-result__value uuid-mono" data-testid="batch-id">
              {importResult.batch_id}
            </span>
          </div>
          <div className="import-result__row">
            <span className="import-result__key">状态</span>
            <span className="import-result__value">{importResult.status}</span>
          </div>
          <div className="import-result__row">
            <span className="import-result__key">总行数</span>
            <span className="import-result__value">
              {importResult.total_rows}
            </span>
          </div>
          <div className="import-result__row">
            <span className="import-result__key">成功</span>
            <span className="import-result__value">
              {importResult.successful_rows}
            </span>
          </div>
          <div className="import-result__row">
            <span className="import-result__key">失败</span>
            <span className="import-result__value">
              {importResult.failed_rows}
            </span>
          </div>
          <div className="import-result__row">
            <span className="import-result__key">重复跳过</span>
            <span className="import-result__value">
              {importResult.duplicate_rows}
            </span>
          </div>
          <div className="import-result__row">
            <span className="import-result__key">检查点行</span>
            <span className="import-result__value">
              {importResult.checkpoint_row}
            </span>
          </div>
          {importResult.idempotent ? (
            <p className="import-result__idempotent" role="status">
              该文件已导入过，幂等命中（未重复写入）。
            </p>
          ) : null}
        </div>
        <div className="action-toolbar" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={onResetAll}
          >
            再导入一个文件
          </button>
        </div>
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">AI 研判</h2>
        {jobId === null ? (
          <form
            className="analysis-form"
            onSubmit={(e: FormEvent) => {
              e.preventDefault();
              if (maxValid && !isCreating) onCreateJob();
            }}
          >
            <div className="analysis-form__field">
              <label
                className="analysis-form__label"
                htmlFor="max-work-orders"
              >
                本次研判工单数（{MAX_WORK_ORDERS_MIN} - {MAX_WORK_ORDERS_MAX}）
                <span className="req">*</span>
              </label>
              <input
                id="max-work-orders"
                type="number"
                min={MAX_WORK_ORDERS_MIN}
                max={MAX_WORK_ORDERS_MAX}
                step={1}
                value={maxWorkOrders}
                onChange={(e) =>
                  onMaxWorkOrdersChange(Number(e.target.value))
                }
                className="analysis-form__input"
                data-testid="max-work-orders"
                disabled={isCreating}
              />
              <span className="analysis-form__hint">
                本次只研判{" "}
                <strong>{maxValid ? maxWorkOrders : "?"}</strong>{" "}
                条工单，不会自动处理全部数据。
              </span>
              {!maxValid ? (
                <span className="imports-error-line" role="alert">
                  请输入 {MAX_WORK_ORDERS_MIN} - {MAX_WORK_ORDERS_MAX}{" "}
                  之间的整数。
                </span>
              ) : null}
            </div>
            <div className="analysis-form__actions">
              <button
                type="submit"
                className="btn btn--primary"
                disabled={!maxValid || isCreating}
                data-testid="create-job-btn"
              >
                {isCreating ? "创建中…" : "发起研判"}
              </button>
            </div>
            {createError ? (
              <div className="analysis-form__error">
                <ErrorState error={createError} />
              </div>
            ) : null}
          </form>
        ) : null}

        {jobId !== null && job ? (
          <div className="analysis-job" data-testid="analysis-job">
            <div className="analysis-job__header">
              <StatusBadge status={job.status} variant="analysis" />
              <span className="uuid-mono">job_id: {job.job_id}</span>
            </div>
            <div className="analysis-job__progress">
              <div
                className="progress-bar"
                role="progressbar"
                aria-valuenow={progressPct}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  className="progress-bar__fill"
                  style={{ width: `${progressPct}%` }}
                />
              </div>
              <span className="progress-bar__label">
                {job.processed_rows} / {job.selected_rows}
                （选中 {job.selected_rows} / 总 {job.total_rows}）
              </span>
            </div>
            <div className="analysis-job__stats">
              <span>
                <span className="analysis-job__stat-key">AI 事件</span>
                <strong>{job.event_count}</strong>
              </span>
              <span>
                <span className="analysis-job__stat-key">匹配边</span>
                <strong>{job.match_edge_count}</strong>
              </span>
              <span>
                <span className="analysis-job__stat-key">多频事件簇</span>
                <strong>{job.cluster_count}</strong>
              </span>
              <span>
                <span className="analysis-job__stat-key">开始</span>
                <strong>{formatTime(job.started_at)}</strong>
              </span>
              <span>
                <span className="analysis-job__stat-key">结束</span>
                <strong>{formatTime(job.finished_at)}</strong>
              </span>
            </div>
            <div className="analysis-job__trace">
              <TraceTag trace={job.trace} />
            </div>
            {status === "queued" || status === "running" ? (
              <p className="text-muted" style={{ fontSize: 12 }}>
                正在研判中，每 {POLL_INTERVAL_MS / 1000} 秒刷新一次…
              </p>
            ) : null}
            {status === "completed" ? (
              <div className="action-toolbar" style={{ marginTop: 12 }}>
                <button
                  type="button"
                  className="btn btn--primary"
                  onClick={onNavigateEvents}
                  data-testid="goto-events-btn"
                >
                  查看多频事件 →
                </button>
              </div>
            ) : null}
            {status === "failed" ? (
              <div className="analysis-job__failed">
                <p className="imports-error-line" role="alert">
                  研判失败：{job.error ?? "后端未返回错误详情"}
                </p>
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={onRetry}
                  data-testid="retry-job-btn"
                >
                  重新发起
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
        {jobId !== null && jobError ? (
          <div style={{ marginTop: 12 }}>
            <ErrorState error={jobError} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function ImportsPage(): JSX.Element {
  const navigate = useNavigate();
  const toastCtx = useContext(ToastContext);
  const push = toastCtx?.push;
  const pushToast = useCallback(
    (text: string, kind: "info" | "success" | "error" = "info") => {
      push?.(text, kind);
    },
    [push],
  );
  const containerRef = useRef<HTMLElement>(null);

  const [phase, setPhase] = useState<Phase>("select");
  const [file, setFile] = useState<File | null>(null);

  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [mapping, setMapping] = useState<ImportMapping>({});

  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);

  const [maxWorkOrders, setMaxWorkOrders] = useState<number>(
    MAX_WORK_ORDERS_DEFAULT,
  );
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<unknown>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [job, setJob] = useState<AnalysisJobResponse | null>(null);
  const [jobError, setJobError] = useState<unknown>(null);

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".imports-stage", {
          opacity: 0,
          y: 8,
          duration: 0.25,
          ease: "power1.out",
        });
      });
    },
    { scope: containerRef, dependencies: [phase] },
  );

  const handlePickFile = useCallback(
    (f: File) => {
      setFile(f);
      setPreview(null);
      setPreviewError(null);
      setMapping({});
    },
    [],
  );

  const handleClearFile = useCallback(() => {
    setFile(null);
    setPreview(null);
    setPreviewError(null);
    setMapping({});
  }, []);

  const handlePreview = useCallback(async () => {
    if (!file) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const data = await previewImport({ file });
      setPreview(data);
      setMapping(buildInitialMapping(data.suggested_mapping ?? {}));
      setPhase("preview");
      pushToast(`预览完成：${data.total_rows} 行`, "success");
    } catch (e) {
      setPreviewError(e);
      pushToast(`预览失败：${describeApiError(e)}`, "error");
    } finally {
      setPreviewLoading(false);
    }
  }, [file, pushToast]);

  const handleBackToSelect = useCallback(() => {
    setPhase("select");
  }, []);

  const handleExecute = useCallback(async () => {
    if (!file) return;
    setPhase("importing");
    setImportLoading(true);
    try {
      const result = await executeImport({ file, mapping });
      setImportResult(result);
      if (result.idempotent) {
        pushToast("该文件已导入过，幂等命中", "info");
      } else {
        pushToast(`导入完成：成功 ${result.successful_rows} 条`, "success");
      }
      setPhase("analysis");
    } catch (e) {
      pushToast(`导入失败：${describeApiError(e)}`, "error");
      setPhase("preview");
    } finally {
      setImportLoading(false);
    }
  }, [file, mapping, pushToast]);

  const handleCreateJob = useCallback(async () => {
    if (!importResult) return;
    setIsCreating(true);
    setCreateError(null);
    try {
      const data = await createAnalysisJob({
        import_batch_id: importResult.batch_id,
        max_work_orders: maxWorkOrders,
      });
      setJobId(data.job_id);
      setJob(data);
      setJobError(null);
      pushToast(`已创建研判任务 ${data.job_id.slice(0, 8)}…`, "success");
    } catch (e) {
      setCreateError(e);
      pushToast(`创建研判失败：${describeApiError(e)}`, "error");
    } finally {
      setIsCreating(false);
    }
  }, [importResult, maxWorkOrders, pushToast]);

  const handleRetry = useCallback(() => {
    setJobId(null);
    setJob(null);
    setJobError(null);
    setCreateError(null);
  }, []);

  const handleNavigateEvents = useCallback(() => {
    navigate("/events");
  }, [navigate]);

  const handleResetAll = useCallback(() => {
    setPhase("select");
    setFile(null);
    setPreview(null);
    setPreviewError(null);
    setMapping({});
    setImportResult(null);
    setImportLoading(false);
    setJobId(null);
    setJob(null);
    setJobError(null);
    setCreateError(null);
    setMaxWorkOrders(MAX_WORK_ORDERS_DEFAULT);
  }, []);

  // 轮询：queued/running 时每 POLL_INTERVAL_MS 拉取一次，终态停止。
  useEffect(() => {
    if (!jobId || !job) return;
    if (job.status === "completed" || job.status === "failed") return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const data = await getAnalysisJob(jobId, controller.signal);
        if (controller.signal.aborted) return;
        setJob(data);
        if (data.status === "completed") {
          pushToast("研判完成", "success");
        } else if (data.status === "failed") {
          pushToast("研判失败", "error");
        }
      } catch (e) {
        if (controller.signal.aborted) return;
        setJobError(e);
      }
    }, POLL_INTERVAL_MS);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [jobId, job, pushToast]);

  return (
    <section ref={containerRef}>
      <header className="page-header">
        <div>
          <p className="eyebrow">IMPORTS &amp; AI ANALYSIS</p>
          <h1 className="page-header__title">数据导入与 AI 研判</h1>
          <p className="page-header__subtitle">
            选择 Excel/CSV → 后端预览 → 字段映射 → 正式导入 → 触发 AI 多频事件研判。
            全程仅调用真实后端 API。
          </p>
        </div>
      </header>

      <Stepper current={phase} />

      {phase === "select" ? (
        <SelectFileStage
          file={file}
          previewLoading={previewLoading}
          previewError={previewError}
          onPickFile={handlePickFile}
          onClearFile={handleClearFile}
          onPreview={handlePreview}
        />
      ) : null}

      {phase === "preview" && preview ? (
        <PreviewStage
          preview={preview}
          mapping={mapping}
          importLoading={importLoading}
          onMappingChange={setMapping}
          onExecute={handleExecute}
          onBackToSelect={handleBackToSelect}
        />
      ) : null}

      {phase === "importing" ? <ImportingStage /> : null}

      {phase === "analysis" && importResult ? (
        <AnalysisStage
          importResult={importResult}
          jobId={jobId}
          job={job}
          jobError={jobError}
          createError={createError}
          isCreating={isCreating}
          maxWorkOrders={maxWorkOrders}
          onMaxWorkOrdersChange={setMaxWorkOrders}
          onCreateJob={handleCreateJob}
          onRetry={handleRetry}
          onNavigateEvents={handleNavigateEvents}
          onResetAll={handleResetAll}
        />
      ) : null}
    </section>
  );
}
