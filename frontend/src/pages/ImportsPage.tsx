import {
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type JSX,
} from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { createAnalysisJob, getAnalysisJob } from "../api/analysis";
import { describeApiError } from "../api/client";
import {
  executeImport,
  previewImport,
  type ImportResponse,
} from "../api/imports";
import type { AnalysisJobResponse } from "../types/api";
import { ToastContext } from "../components/toastContext";
import { StatusBadge } from "../components/StatusBadge";

type Step = 1 | 2 | 3 | 4;

type AiStepStatus = "waiting" | "running" | "done" | "failed";

interface AiStep {
  key: string;
  label: string;
  desc: string;
}

interface LogLine {
  time: string;
  text: string;
  level: "info" | "success" | "warn" | "error";
}

const ACCEPTED_EXT = [".xlsx", ".xls", ".csv"];
const POLL_INTERVAL_MS = 2000;
const MAX_FILE_SIZE = 50 * 1024 * 1024;

const AI_STEPS: AiStep[] = [
  { key: "understand", label: "语义理解", desc: "解析工单内容，识别语义要素" },
  { key: "extract", label: "事件抽取", desc: "从工单中抽取结构化事件" },
  { key: "embed", label: "向量生成", desc: "生成事件语义向量表征" },
  { key: "match", label: "相似度匹配", desc: "跨工单事件相似度计算" },
  { key: "cluster", label: "聚类研判", desc: "多频事件聚类与置信度评估" },
];

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function isAcceptedFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXT.some((ext) => name.endsWith(ext));
}

function CloudUploadIcon(): JSX.Element {
  return (
    <svg className="upload-zone__cloud-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 16a5 5 0 1 0-1.5-9.77A6 6 0 0 0 4 12v1a4 4 0 0 0 4 4h9z" />
      <path d="M12 12v7" />
      <path d="m9 15 3-3 3 3" />
    </svg>
  );
}

function FileIcon(): JSX.Element {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="12" y1="18" x2="12" y2="12" />
      <polyline points="9 15 12 12 15 15" />
    </svg>
  );
}

function CheckIcon({ size = 16 }: { size?: number }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function CloseIcon({ size = 14 }: { size?: number }): JSX.Element {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function Stepper({ current }: { current: Step }): JSX.Element {
  const steps: Array<{ n: Step; label: string }> = [
    { n: 1, label: "上传文件" },
    { n: 2, label: "解析预览" },
    { n: 3, label: "确认导入" },
    { n: 4, label: "AI研判" },
  ];
  return (
    <div className="steps-horizontal">
      {steps.map((s, i) => {
        const isActive = s.n === current;
        const isDone = s.n < current;
        const circleCls = isDone
          ? "step__circle step__circle--done"
          : isActive
            ? "step__circle step__circle--active"
            : "step__circle step__circle--pending";
        const labelCls = isDone
          ? "step__label step__label--done"
          : isActive
            ? "step__label step__label--active"
            : "step__label step__label--pending";
        return (
          <div key={s.n} className="step">
            <div className={circleCls}>
              {isDone ? <CheckIcon size={16} /> : s.n}
            </div>
            <span className={labelCls}>{s.label}</span>
            {i < steps.length - 1 ? (
              <div className={`step__connector${isDone ? " step__connector--done" : ""}`} />
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function StageUpload({
  file,
  onFileSelected,
  onStartPreview,
  previewLoading,
}: {
  onFileSelected: (f: File) => void;
  file: File | null;
  onStartPreview: () => void;
  previewLoading: boolean;
}): JSX.Element {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [rejectMsg, setRejectMsg] = useState<string | null>(null);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      setRejectMsg(null);
      if (!files || files.length === 0) return;
      const f = files[0];
      if (!isAcceptedFile(f)) {
        setRejectMsg(`不支持的文件格式：${f.name}。仅接受 .xlsx / .xls / .csv`);
        return;
      }
      if (f.size > MAX_FILE_SIZE) {
        setRejectMsg(`文件大小超过50MB限制：${formatFileSize(f.size)}`);
        return;
      }
      onFileSelected(f);
    },
    [onFileSelected],
  );

  const triggerPicker = () => inputRef.current?.click();

  return (
    <div className="import-stage">
      <div
        className={`upload-zone--lg${dragOver ? " drag-over" : ""}`}
        onClick={triggerPicker}
        onDrop={(e: DragEvent<HTMLDivElement>) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            triggerPicker();
          }
        }}
      >
        <input
          ref={inputRef}
          data-testid="file-input"
          type="file"
          accept=".xlsx,.xls,.csv"
          style={{ display: "none" }}
          onChange={(e: ChangeEvent<HTMLInputElement>) => handleFiles(e.target.files)}
        />
        <CloudUploadIcon />
        <div className="upload-zone__title">点击或拖拽文件到此处上传</div>
        <div className="upload-zone__sub">支持 .xlsx / .xls / .csv 格式，单文件不超过50MB</div>
        <button
          type="button"
          className="btn btn--primary"
          onClick={(e) => {
            e.stopPropagation();
            triggerPicker();
          }}
        >
          选择文件
        </button>
      </div>

      {rejectMsg ? <div className="error-banner"><CloseIcon size={12} />{rejectMsg}</div> : null}
      {file ? (
        <div className="file-info-card" style={{ marginTop: 16 }}>
          <div className="file-info-card__body"><div className="file-info-card__name">{file.name}</div><div className="file-info-card__meta">{formatFileSize(file.size)}</div></div>
          <button type="button" className="btn btn--primary" data-testid="start-preview-btn" onClick={onStartPreview} disabled={previewLoading}>{previewLoading ? "解析中..." : "开始预览"}</button>
        </div>
      ) : null}

      <div className="requirements-card">
        <div className="requirements-card__title">文件格式要求</div>
        <div className="req-tags">
          <span className="req-tag req-tag--required">工单编号</span>
          <span className="req-tag req-tag--required">反映内容</span>
          <span className="req-tag req-tag--required">反映时间</span>
          <span className="req-tag req-tag--required">地址</span>
          <span className="req-tag req-tag--required">渠道</span>
          <span className="req-tag req-tag--optional">联系人</span>
          <span className="req-tag req-tag--optional">联系电话</span>
        </div>
        <ul className="req-list">
          <li>数据需去重，工单编号不可重复</li>
          <li>地址字段需完整，包含区/街道/详细位置</li>
          <li>时间格式统一为 YYYY-MM-DD 或 YYYY-MM-DD HH:mm</li>
        </ul>
      </div>
    </div>
  );
}

function StagePreview({
  file,
  totalCount,
  columns,
  suggestedMapping,
  onMappingChange,
  previewLoading,
  previewError,
  onReselect,
  onConfirm,
  onBack,
  confirming,
}: {
  file: File;
  totalCount: number;
  columns: string[];
  suggestedMapping: Record<string, string>;
  onMappingChange: (target: string, source: string) => void;
  previewLoading: boolean;
  previewError: string | null;
  onReselect: () => void;
  onConfirm: () => void;
  onBack: () => void;
  confirming: boolean;
}): JSX.Element {
  return (
    <div className="import-stage">
      <div className="file-info-card">
        <div className="file-info-card__icon"><FileIcon /></div>
        <div className="file-info-card__body">
          <div className="file-info-card__name">{file.name}</div>
          <div className="file-info-card__meta">
            {formatFileSize(file.size)} · 修改时间 {new Date(file.lastModified).toLocaleString("zh-CN")}
          </div>
        </div>
        <button className="file-info-card__action" onClick={onReselect} disabled={confirming}>重新选择</button>
      </div>

      {previewLoading ? <div className="loading-state" role="status">正在读取真实文件字段...</div> : null}
      {previewError ? <div className="error-banner"><CloseIcon size={12} />文件预览失败：{previewError}</div> : null}
      {!previewLoading && !previewError ? (
        <div className="preview-table-wrap">
          <table className="preview-table">
            <thead><tr><th>后端目标字段</th><th>导入源列</th></tr></thead>
            <tbody>
              {["source_row_number", "external_work_order_number", "title", "content"].map((target) => (
                <tr key={target}>
                  <td>{target}</td>
                  <td>
                    <select
                      data-testid={`mapping-${target}`}
                      value={suggestedMapping[target] ?? ""}
                      onChange={(event) => onMappingChange(target, event.target.value)}
                    >
                      <option value="">未映射</option>
                      {columns.map((column) => <option key={column} value={column}>{column}</option>)}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-muted" style={{ marginTop: 12 }}>共 {totalCount || "—"} 行 · 文件列：{columns.length > 0 ? columns.join("、") : "后端未返回"}</p>
          {!suggestedMapping.content ? <p className="text-danger" style={{ marginTop: 8 }}>“内容”字段必须映射到一个源列才能正式导入。</p> : null}
        </div>
      ) : null}

      <div className="validation-summary">
        <div className="validation-stat">
          <div className="validation-stat__value validation-stat__value--total">{totalCount || "—"}</div>
          <div className="validation-stat__label">后端预览行数</div>
        </div>
      </div>
      <div className="validation-success"><CheckIcon size={14} /> 字段预览来自后端；行级校验结果以导入响应为准</div>

      <div className="stage-actions">
        <button className="btn-secondary" onClick={onBack} disabled={confirming}>上一步</button>
        <button data-testid="execute-import-btn" className="btn btn--primary" onClick={onConfirm} disabled={confirming || previewLoading || Boolean(previewError) || !suggestedMapping.content}>
          {confirming ? "导入中..." : "确认导入"}
        </button>
      </div>
    </div>
  );
}

function StageImportProgress({
  result,
  elapsed,
  error,
  maxWorkOrders,
  onMaxWorkOrdersChange,
  maxWorkOrdersError,
  onStartAnalysis,
}: {
  result: ImportResponse | null;
  elapsed: number;
  error: string | null;
  maxWorkOrders: number;
  onMaxWorkOrdersChange: (value: number) => void;
  maxWorkOrdersError: string | null;
  onStartAnalysis: () => void;
}): JSX.Element {
  if (error) {
    return (
      <div className="import-stage">
        <div className="error-banner"><CloseIcon size={12} />导入失败：{error}</div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="import-stage">
        <div className="progress-section">
          <div className="progress-section__percent">处理中</div>
          <div className="progress-bar" role="progressbar" aria-label="等待后端导入结果">
            <div className="progress-bar__fill" style={{ width: "100%" }} />
          </div>
          <div className="progress-section__text">正在等待后端导入响应，不显示估算行进度</div>
        </div>
      </div>
    );
  }

  return (
    <div className="import-stage">
      <div className="progress-section">
        <div className="progress-section__percent">100%</div>
        <div className="progress-bar">
          <div className="progress-bar__fill" style={{ width: "100%" }} />
        </div>
      </div>
      <div className="import-done">
        <div className="import-done__icon"><CheckIcon size={36} /></div>
        <div className="import-done__title">导入成功</div>
        <div data-testid="batch-id" className="text-muted" style={{ marginTop: 8 }}>批次 ID：{result.batch_id}</div>
        <div className="import-done__sub">批次数据已成功写入数据库</div>
        {result.idempotent ? <div className="validation-success" style={{ marginTop: 12 }}>该文件已导入过，幂等命中，未重复写入原始工单。</div> : null}
      <div className="import-done__stats">
          <div className="import-done__stat">
            <div className="import-done__stat-value import-done__stat-value--success">{result.successful_rows}</div>
            <div className="import-done__stat-label">成功（条）</div>
          </div>
          <div className="import-done__stat">
            <div className="import-done__stat-value import-done__stat-value--fail">{result.failed_rows}</div>
            <div className="import-done__stat-label">失败（条）</div>
          </div>
          <div className="import-done__stat">
            <div className="import-done__stat-value import-done__stat-value--time">{elapsed}s</div>
            <div className="import-done__stat-label">耗时</div>
          </div>
      </div>
      <label style={{ display: "block", margin: "16px 0", maxWidth: 360 }}>
        <span className="text-muted">本次 AI 研判工单上限（1–300）</span>
        <input data-testid="max-work-orders" type="number" min={1} max={300} value={maxWorkOrders} onChange={(event) => onMaxWorkOrdersChange(Number(event.target.value))} style={{ display: "block", width: "100%", marginTop: 6 }} />
      </label>
      {maxWorkOrdersError ? <p className="text-danger">{maxWorkOrdersError}</p> : null}
      <p className="text-muted">本次只研判 <strong>{maxWorkOrders}</strong> 条工单，不会自动处理全部数据。</p>
        <button data-testid="create-job-btn" className="btn btn--primary btn--lg" disabled={Boolean(maxWorkOrdersError)} onClick={onStartAnalysis}>开始AI研判</button>
      </div>
    </div>
  );
}

function StageAnalysis({
  currentAiStep,
  aiStepStatuses,
  statusText,
  progress,
  processedRows,
  totalRows,
  eventCount,
  clusterCount,
  logs,
  job,
  error,
  onViewEvents,
  onViewWorkOrders,
  onRetry,
}: {
  currentAiStep: number;
  aiStepStatuses: AiStepStatus[];
  statusText: string;
  progress: number;
  processedRows: number;
  totalRows: number;
  eventCount: number;
  clusterCount: number;
  logs: LogLine[];
  job: AnalysisJobResponse | null;
  error: string | null;
  onViewEvents: () => void;
  onViewWorkOrders: () => void;
  onRetry: () => void;
}): JSX.Element {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  if (error) {
    return (
      <div className="import-stage" data-testid="analysis-job">
        <div className="error-banner"><CloseIcon size={12} />AI研判失败：{error}</div>
        <button data-testid="retry-job-btn" className="btn btn--secondary" onClick={onRetry}>重新设置研判上限</button>
      </div>
    );
  }

  const isCompleted = job?.status === "completed";

  return (
    <div className="import-stage" data-testid="analysis-job">
      <div style={{ marginBottom: 12 }}><StatusBadge status={job?.status ?? "queued"} variant="analysis" /></div>
      {!isCompleted ? (
        <>
          <div className="ai-steps">
            {AI_STEPS.map((s, idx) => {
              const st = aiStepStatuses[idx];
              const dotCls =
                st === "done"
                  ? "ai-step__dot ai-step__dot--done"
                  : st === "running"
                    ? "ai-step__dot ai-step__dot--running"
                    : st === "failed"
                      ? "ai-step__dot ai-step__dot--failed"
                      : "ai-step__dot ai-step__dot--waiting";
              const nameCls = st === "waiting" ? "ai-step__name ai-step__name--waiting" : "ai-step__name";
              const lineCls =
                idx < currentAiStep || (idx === currentAiStep && st === "done")
                  ? "ai-step__line ai-step__line--done"
                  : "ai-step__line";
              return (
                <div key={s.key} className="ai-step">
                  <div className="ai-step__indicator">
                    <div className={dotCls}>
                      {st === "done" ? <CheckIcon size={14} /> : st === "failed" ? <CloseIcon size={12} /> : idx + 1}
                    </div>
                    <div className={lineCls} />
                  </div>
                  <div className="ai-step__body">
                    <div className={nameCls}>{s.label}</div>
                    <div className="ai-step__desc">{s.desc}</div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="ai-progress-header">
            <div className="ai-progress-header__title">{statusText}</div>
            <div className="progress-bar">
              <div className="progress-bar__fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="ai-progress-header__sub">
              <span>已处理 <strong>{processedRows}</strong>/{totalRows} 条</span>
              <span>发现事件 <strong>{eventCount}</strong> 个</span>
              <span>聚类 <strong>{clusterCount}</strong> 簇</span>
            </div>
          </div>

          <div className="log-panel" ref={logRef}>
            {logs.map((l, i) => (
              <div key={i} className={`log-panel__line log-panel__line--${l.level}`}>
                [{l.time}] {l.text}
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="ai-done">
          <div className="ai-done__icon"><CheckIcon size={36} /></div>
          <div className="ai-done__title">完整研判完成</div>
          <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginTop: 4 }}>
            多频事件智能分析已完成，可查看研判结果
          </div>
          <div className="ai-done__stats">
            <div className="ai-done__stat">
              <div className="ai-done__stat-value">{job.total_rows}</div>
              <div className="ai-done__stat-label">总工单</div>
            </div>
            <div className="ai-done__stat">
              <div className="ai-done__stat-value">{job.event_count}</div>
              <div className="ai-done__stat-label">抽取事件</div>
            </div>
            <div className="ai-done__stat">
              <div className="ai-done__stat-value">{job.cluster_count}</div>
              <div className="ai-done__stat-label">多频事件</div>
            </div>
          </div>
          <div className="ai-done__actions">
            <button data-testid="goto-events-btn" className="btn btn--primary" onClick={onViewEvents}>查看多频事件</button>
            <button className="btn-secondary" onClick={onViewWorkOrders}>查看工单</button>
          </div>
        </div>
      )}
    </div>
  );
}

export function ImportsPage(): JSX.Element {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toastCtx = useContext(ToastContext);
  const push = toastCtx?.push;
  const pushToast = useCallback(
    (text: string, kind: "info" | "success" | "error" = "info") => {
      push?.(text, kind);
    },
    [push],
  );

  const [step, setStep] = useState<Step>(1);
  const [file, setFile] = useState<File | null>(null);
  const [previewColumns, setPreviewColumns] = useState<string[]>([]);
  const [suggestedMapping, setSuggestedMapping] = useState<Record<string, string>>({});
  const [previewTotal, setPreviewTotal] = useState(0);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);

  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importElapsed, setImportElapsed] = useState(0);
  const [maxWorkOrders, setMaxWorkOrders] = useState(50);

  const [job, setJob] = useState<AnalysisJobResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [isCreatingJob, setIsCreatingJob] = useState(false);

  const [currentAiStep] = useState(0);
  const [aiStepStatuses, setAiStepStatuses] = useState<AiStepStatus[]>(
    AI_STEPS.map(() => "waiting"),
  );
  const [logs] = useState<LogLine[]>([]);

  const importTimersRef = useRef<number[]>([]);
  const pollTimerRef = useRef<number | null>(null);

  const clearImportTimers = () => {
    importTimersRef.current.forEach((t) => window.clearTimeout(t));
    importTimersRef.current = [];
  };

  const stopPolling = () => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      clearImportTimers();
      stopPolling();
    };
  }, []);

  const handleFileSelected = useCallback((f: File) => {
    setFile(f);
    setPreviewError(null);
    setPreviewColumns([]);
    setSuggestedMapping({});
    setPreviewTotal(0);
    pushToast(`已选择文件：${f.name}`, "info");
  }, [pushToast]);

  const handleStartPreview = useCallback(async () => {
    if (!file) return;
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const preview = await previewImport({ file });
      setPreviewColumns(preview.columns);
      setSuggestedMapping(preview.suggested_mapping);
      setPreviewTotal(preview.total_rows);
      setStep(2);
    } catch (error) {
      setPreviewError(describeApiError(error));
    } finally {
      setPreviewLoading(false);
    }
  }, [file]);

  const handleReselect = useCallback(() => {
    setFile(null);
    setStep(1);
    setPreviewColumns([]);
    setSuggestedMapping({});
    setPreviewTotal(0);
    setPreviewError(null);
  }, []);

  const handleBackToUpload = useCallback(() => {
    setStep(1);
  }, []);

  const handleConfirmImport = useCallback(async () => {
    if (!file) return;
    setStep(3);
    setImporting(true);
    setImportResult(null);
    setImportError(null);
    setImportElapsed(0);
    clearImportTimers();

    const startTime = Date.now();

    try {
      const result = await executeImport({
        file,
        mapping: suggestedMapping,
      });
      setImportResult(result);
      setImporting(false);
      pushToast(`导入完成：成功 ${result.successful_rows} 条`, "success");
    } catch (e) {
      setImportError(describeApiError(e));
      setImporting(false);
      pushToast(`导入失败：${describeApiError(e)}`, "error");
    } finally {
      setImportElapsed(Math.floor((Date.now() - startTime) / 1000));
    }
  }, [file, suggestedMapping, pushToast]);

  const handleStartAnalysis = useCallback(async () => {
    if (!importResult) return;
    if (!Number.isInteger(maxWorkOrders) || maxWorkOrders < 1 || maxWorkOrders > 300) return;
    setStep(4);
    setJob(null);
    setJobId(null);
    setJobError(null);
    setIsCreatingJob(true);

    try {
      const created = await createAnalysisJob({
        import_batch_id: importResult.batch_id,
        max_work_orders: Math.min(maxWorkOrders, importResult.successful_rows),
      });
      setJobId(created.job_id);
      setJob(created);
      setIsCreatingJob(false);
      pushToast(`已创建研判任务`, "success");

      if (created.status !== "completed" && created.status !== "failed") {
        stopPolling();
        pollTimerRef.current = window.setInterval(async () => {
          if (!jobIdRef.current) return;
          try {
            const data = await getAnalysisJob(jobIdRef.current);
            setJob(data);
            if (data.status === "completed") {
              stopPolling();
              setAiStepStatuses(AI_STEPS.map(() => "done"));
              queryClient.invalidateQueries({ queryKey: ["clusters"] });
              pushToast("研判完成", "success");
            } else if (data.status === "failed") {
              stopPolling();
              setJobError(data.error ?? "未知错误");
              pushToast("研判失败", "error");
            }
          } catch {
            // keep polling
          }
        }, POLL_INTERVAL_MS);
      } else if (created.status === "completed") {
        setAiStepStatuses(AI_STEPS.map(() => "done"));
      } else if (created.status === "failed") {
        setJobError(created.error ?? "研判失败");
      }
    } catch (e) {
      setIsCreatingJob(false);
      setJobError(describeApiError(e));
      pushToast(`创建研判失败：${describeApiError(e)}`, "error");
    }
  }, [importResult, maxWorkOrders, pushToast, queryClient]);

  const maxWorkOrdersError = !Number.isInteger(maxWorkOrders) || maxWorkOrders < 1 || maxWorkOrders > 300
    ? "请输入 1 - 300 之间的整数"
    : null;

  const jobIdRef = useRef<string | null>(null);
  useEffect(() => {
    jobIdRef.current = jobId;
  }, [jobId]);

  const handleViewEvents = useCallback(() => {
    navigate("/events");
  }, [navigate]);

  const handleViewWorkOrders = useCallback(() => {
    navigate("/work-orders");
  }, [navigate]);

  const handleRetryJob = useCallback(() => {
    stopPolling();
    setJob(null);
    setJobId(null);
    setJobError(null);
    setIsCreatingJob(false);
    setStep(3);
  }, []);

  const handleHistory = useCallback(() => {
    pushToast("历史记录功能开发中", "info");
  }, [pushToast]);

  const aiProgress = job && job.selected_rows > 0
    ? Math.min(100, Math.round((job.processed_rows / job.selected_rows) * 100))
    : 0;

  const displayProcessed = job?.processed_rows ?? 0;
  const displayEvents = job?.event_count ?? 0;
  const displayClusters = job?.cluster_count ?? 0;
  const displayTotal = job?.selected_rows ?? importResult?.successful_rows ?? 0;

  const aiStatusText = useMemo(() => {
    if (job?.status === "queued") return "研判任务排队中...";
    if (job?.status === "running") return "正在进行AI智能研判...";
    const runningIdx = aiStepStatuses.findIndex((s) => s === "running");
    if (runningIdx >= 0) return `正在进行${AI_STEPS[runningIdx].label}...`;
    if (aiStepStatuses.every((s) => s === "done")) return "AI研判已完成";
    return "等待后端研判任务状态...";
  }, [job, aiStepStatuses]);

  return (
    <section>
      <div className="page-header--imports">
        <div>
          <h1 className="page-header--imports__title">数据导入与AI研判</h1>
          <p className="page-header--imports__subtitle">支持Excel/CSV批量导入，AI自动研判多频事件</p>
        </div>
        <button className="btn-secondary" onClick={handleHistory}>历史记录</button>
      </div>

      <Stepper current={step} />

      {step === 1 ? (
        <StageUpload file={file} onFileSelected={handleFileSelected} onStartPreview={handleStartPreview} previewLoading={previewLoading} />
      ) : null}

      {step === 2 && file ? (
        <StagePreview
          file={file}
          totalCount={previewTotal}
          columns={previewColumns}
          suggestedMapping={suggestedMapping}
          onMappingChange={(target, source) => setSuggestedMapping((current) => ({ ...current, [target]: source }))}
          previewLoading={previewLoading}
          previewError={previewError}
          onReselect={handleReselect}
          onConfirm={handleConfirmImport}
          onBack={handleBackToUpload}
          confirming={importing}
        />
      ) : null}

      {step === 3 ? (
        <StageImportProgress
          result={importResult}
          elapsed={importElapsed}
          error={importError}
          maxWorkOrders={maxWorkOrders}
          onMaxWorkOrdersChange={setMaxWorkOrders}
          maxWorkOrdersError={maxWorkOrdersError}
          onStartAnalysis={handleStartAnalysis}
        />
      ) : null}

      {step === 4 ? (
        <StageAnalysis
          currentAiStep={currentAiStep}
          aiStepStatuses={aiStepStatuses}
          statusText={isCreatingJob ? "正在创建研判任务..." : aiStatusText}
          progress={aiProgress}
          processedRows={displayProcessed}
          totalRows={displayTotal}
          eventCount={displayEvents}
          clusterCount={displayClusters}
          logs={logs}
          job={job}
          error={jobError}
          onViewEvents={handleViewEvents}
          onViewWorkOrders={handleViewWorkOrders}
          onRetry={handleRetryJob}
        />
      ) : null}

      <details className="help-collapse">
        <summary className="help-collapse__summary">📖 使用说明</summary>
        <div className="help-collapse__body">
          <ol>
            <li>准备好符合规范的Excel/CSV文件</li>
            <li>上传后自动校验，无效数据会提示修改</li>
            <li>导入完成后可启动AI研判</li>
            <li>研判结果可在多频事件页面查看</li>
            <li>支持人工复核和修正</li>
          </ol>
        </div>
      </details>
    </section>
  );
}
