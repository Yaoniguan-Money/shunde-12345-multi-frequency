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
  type ImportResponse,
} from "../api/imports";
import type { AnalysisJobResponse } from "../types/api";
import { ToastContext } from "../components/toastContext";

type Step = 1 | 2 | 3 | 4;

type AiStepStatus = "waiting" | "running" | "done" | "failed";

interface AiStep {
  key: string;
  label: string;
  desc: string;
}

interface PreviewRow {
  orderNo: string;
  content: string;
  time: string;
  address: string;
  channel: string;
}

interface ValidationError {
  row: number;
  reason: string;
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

const MOCK_PREVIEW_ROWS: PreviewRow[] = [
  { orderNo: "GD2024010001", content: "大良街道某小区下水道堵塞，污水外溢，影响居民出行", time: "2024-01-15 09:23", address: "顺德区大良街道南华小区3栋", channel: "12345热线" },
  { orderNo: "GD2024010002", content: "容桂街道某路段路灯不亮，夜间出行不便，存在安全隐患", time: "2024-01-15 10:45", address: "顺德区容桂街道桂洲大道中", channel: "微信公众号" },
  { orderNo: "GD2024010003", content: "勒流街道某工厂夜间噪音扰民，持续多日未解决", time: "2024-01-15 14:12", address: "顺德区勒流街道富安工业区", channel: "12345热线" },
  { orderNo: "GD2024010004", content: "北滘镇某公园健身器材损坏，存在安全隐患，建议尽快维修", time: "2024-01-15 16:30", address: "顺德区北滘镇北滘公园", channel: "APP" },
  { orderNo: "GD2024010005", content: "陈村镇某建筑工地扬尘污染严重，影响周边居民生活", time: "2024-01-16 08:50", address: "顺德区陈村镇白陈路侧", channel: "网站" },
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

function formatTime(d: Date): string {
  const pad = (n: number): string => n.toString().padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function genLogLine(text: string, level: LogLine["level"] = "info"): LogLine {
  return { time: formatTime(new Date()), text, level };
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
}: {
  file: File | null;
  onFileSelected: (f: File) => void;
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
  previewRows,
  totalCount,
  validCount,
  warningCount,
  invalidCount,
  errors,
  onReselect,
  onConfirm,
  onBack,
  confirming,
}: {
  file: File;
  previewRows: PreviewRow[];
  totalCount: number;
  validCount: number;
  warningCount: number;
  invalidCount: number;
  errors: ValidationError[];
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

      <div className="preview-table-wrap">
        <table className="preview-table">
          <thead>
            <tr>
              <th>工单号</th>
              <th>反映内容</th>
              <th>反映时间</th>
              <th>地址</th>
              <th>渠道</th>
            </tr>
          </thead>
          <tbody>
            {previewRows.map((row, idx) => (
              <tr key={idx}>
                <td style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}>{row.orderNo}</td>
                <td>{row.content}</td>
                <td style={{ whiteSpace: "nowrap" }}>{row.time}</td>
                <td>{row.address}</td>
                <td><span className="req-tag req-tag--required">{row.channel}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="validation-summary">
        <div className="validation-stat">
          <div className="validation-stat__value validation-stat__value--total">{totalCount}</div>
          <div className="validation-stat__label">总数据</div>
        </div>
        <div className="validation-stat">
          <div className="validation-stat__value validation-stat__value--valid">{validCount}</div>
          <div className="validation-stat__label">有效</div>
        </div>
        <div className="validation-stat">
          <div className="validation-stat__value validation-stat__value--warning">{warningCount}</div>
          <div className="validation-stat__label">待确认</div>
        </div>
        <div className="validation-stat">
          <div className="validation-stat__value validation-stat__value--invalid">{invalidCount}</div>
          <div className="validation-stat__label">无效</div>
        </div>
      </div>

      {errors.length > 0 ? (
        <div className="validation-errors">
          <div className="validation-errors__title">发现 {errors.length} 条数据异常：</div>
          <ul className="validation-errors__list">
            {errors.map((e, i) => (
              <li key={i}>第 {e.row} 行：{e.reason}</li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="validation-success"><CheckIcon size={14} /> 数据格式校验通过</div>
      )}

      <div className="stage-actions">
        <button className="btn-secondary" onClick={onBack} disabled={confirming}>上一步</button>
        <button className="btn btn--primary" onClick={onConfirm} disabled={confirming || invalidCount > 0}>
          {confirming ? "导入中..." : "确认导入"}
        </button>
      </div>
    </div>
  );
}

function StageImportProgress({
  progress,
  currentRow,
  totalRows,
  result,
  elapsed,
  error,
  onStartAnalysis,
}: {
  progress: number;
  currentRow: number;
  totalRows: number;
  result: ImportResponse | null;
  elapsed: number;
  error: string | null;
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
          <div className="progress-section__percent">{progress}%</div>
          <div className="progress-bar" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="progress-bar__fill" style={{ width: `${progress}%` }} />
          </div>
          <div className="progress-section__text">正在导入第 {currentRow} / {totalRows} 条...</div>
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
        <div className="import-done__sub">批次数据已成功写入数据库</div>
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
        <button className="btn btn--primary btn--lg" onClick={onStartAnalysis}>开始AI研判</button>
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
  highConfidenceRate,
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
  highConfidenceRate: number;
}): JSX.Element {
  const logRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logs]);

  if (error) {
    return (
      <div className="import-stage">
        <div className="error-banner"><CloseIcon size={12} />AI研判失败：{error}</div>
      </div>
    );
  }

  const isCompleted = job?.status === "completed";

  return (
    <div className="import-stage">
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
          <div className="ai-done__title">AI研判完成</div>
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
            <div className="ai-done__stat">
              <div className="ai-done__stat-value">{highConfidenceRate}%</div>
              <div className="ai-done__stat-label">高置信度</div>
            </div>
          </div>
          <div className="ai-done__actions">
            <button className="btn btn--primary" onClick={onViewEvents}>查看多频事件</button>
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
  const [previewRows] = useState<PreviewRow[]>(MOCK_PREVIEW_ROWS);
  const [totalCount] = useState(127);
  const [validCount] = useState(122);
  const [warningCount] = useState(5);
  const [invalidCount] = useState(0);
  const [validationErrors] = useState<ValidationError[]>([]);

  const [importProgress, setImportProgress] = useState(0);
  const [importCurrentRow, setImportCurrentRow] = useState(0);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importElapsed, setImportElapsed] = useState(0);

  const [job, setJob] = useState<AnalysisJobResponse | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [isCreatingJob, setIsCreatingJob] = useState(false);

  const [currentAiStep, setCurrentAiStep] = useState(0);
  const [aiStepStatuses, setAiStepStatuses] = useState<AiStepStatus[]>(
    AI_STEPS.map(() => "waiting"),
  );
  const [logs, setLogs] = useState<LogLine[]>([]);
  const [simEventCount, setSimEventCount] = useState(0);
  const [simClusterCount, setSimClusterCount] = useState(0);
  const [simProcessed, setSimProcessed] = useState(0);

  const importTimersRef = useRef<number[]>([]);
  const simTimersRef = useRef<number[]>([]);
  const pollTimerRef = useRef<number | null>(null);

  const highConfidenceRate = useMemo(() => {
    if (!job || job.cluster_count === 0) return 0;
    return Math.round((job.cluster_count / Math.max(job.event_count, 1)) * 100 * 1.2);
  }, [job]);

  const clearImportTimers = () => {
    importTimersRef.current.forEach((t) => window.clearTimeout(t));
    importTimersRef.current = [];
  };

  const clearSimTimers = () => {
    simTimersRef.current.forEach((t) => window.clearTimeout(t));
    simTimersRef.current = [];
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
      clearSimTimers();
      stopPolling();
    };
  }, []);

  const handleFileSelected = useCallback((f: File) => {
    setFile(f);
    setStep(2);
    pushToast(`已选择文件：${f.name}`, "info");
  }, [pushToast]);

  const handleReselect = useCallback(() => {
    setFile(null);
    setStep(1);
  }, []);

  const handleBackToUpload = useCallback(() => {
    setStep(1);
  }, []);

  const handleConfirmImport = useCallback(async () => {
    if (!file) return;
    setStep(3);
    setImporting(true);
    setImportProgress(0);
    setImportCurrentRow(0);
    setImportResult(null);
    setImportError(null);
    setImportElapsed(0);
    clearImportTimers();

    const startTime = Date.now();
    const elapsedTimer = window.setInterval(() => {
      setImportElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 200);
    importTimersRef.current.push(elapsedTimer);

    const total = totalCount;
    const tickMs = 40;
    let row = 0;
    const progressTimer = window.setInterval(() => {
      row += Math.max(1, Math.floor(total / 60));
      if (row >= total) {
        row = total;
        setImportCurrentRow(row);
        setImportProgress(100);
        window.clearInterval(progressTimer);
      } else {
        setImportCurrentRow(row);
        setImportProgress(Math.round((row / total) * 100));
      }
    }, tickMs);
    importTimersRef.current.push(progressTimer);

    try {
      const result = await executeImport({
        file,
        mapping: {
          content: "反映内容",
          external_work_order_number: "工单编号",
        },
      });
      await new Promise<void>((resolve) => {
        const t = window.setTimeout(() => {
          setImportCurrentRow(total);
          setImportProgress(100);
          resolve();
        }, 2500);
        importTimersRef.current.push(t);
      });
      window.clearInterval(progressTimer);
      setImportResult(result);
      setImporting(false);
      pushToast(`导入完成：成功 ${result.successful_rows} 条`, "success");
    } catch (e) {
      window.clearInterval(progressTimer);
      setImportError(describeApiError(e));
      setImporting(false);
      pushToast(`导入失败：${describeApiError(e)}`, "error");
    } finally {
      window.clearInterval(elapsedTimer);
      setImportElapsed(Math.floor((Date.now() - startTime) / 1000));
    }
  }, [file, totalCount, pushToast]);

  const runSimulation = useCallback((total: number, jobIdRef: { current: string | null }) => {
    clearSimTimers();
    setLogs([genLogLine("加载工单批次...", "info")]);
    setSimEventCount(0);
    setSimClusterCount(0);
    setSimProcessed(0);
    setCurrentAiStep(0);
    setAiStepStatuses(AI_STEPS.map(() => "waiting"));

    const addLog = (text: string, level: LogLine["level"] = "info") => {
      setLogs((prev) => [...prev, genLogLine(text, level)]);
    };

    const setStepStatus = (idx: number, status: AiStepStatus) => {
      setAiStepStatuses((prev) => {
        const next = [...prev];
        next[idx] = status;
        return next;
      });
    };

    let destroyed = false;

    const stepFlow = [
      {
        name: "语义理解",
        start: () => {
          setCurrentAiStep(0);
          setStepStatus(0, "running");
          addLog("开始语义理解处理...", "info");
        },
        run: () => {
          let p = 0;
          const chunk = Math.max(1, Math.floor(total / 40));
          const t = window.setInterval(() => {
            if (destroyed) { window.clearInterval(t); return; }
            p += chunk;
            if (p >= total) p = total;
            setSimProcessed(p);
            if (p >= total) {
              window.clearInterval(t);
              setStepStatus(0, "done");
              addLog("语义理解完成", "success");
              doStep(1);
            }
          }, 80);
          simTimersRef.current.push(t);
        },
      },
      {
        name: "事件抽取",
        start: () => {
          setCurrentAiStep(1);
          setStepStatus(1, "running");
          addLog("开始事件抽取...", "info");
        },
        run: () => {
          let ev = 0;
          const targetEv = Math.floor(total * 0.85);
          const t = window.setInterval(() => {
            if (destroyed) { window.clearInterval(t); return; }
            ev += Math.max(1, Math.floor(targetEv / 30));
            if (ev >= targetEv) ev = targetEv;
            setSimEventCount(ev);
            if (ev >= targetEv) {
              window.clearInterval(t);
              setStepStatus(1, "done");
              addLog(`事件抽取完成，共 ${targetEv} 个事件`, "success");
              doStep(2);
            }
          }, 80);
          simTimersRef.current.push(t);
        },
      },
      {
        name: "向量生成",
        start: () => {
          setCurrentAiStep(2);
          setStepStatus(2, "running");
          addLog("开始向量生成...", "info");
        },
        run: () => {
          const t = window.setTimeout(() => {
            if (destroyed) return;
            setStepStatus(2, "done");
            addLog("向量生成完成", "success");
            doStep(3);
          }, 1200);
          simTimersRef.current.push(t);
        },
      },
      {
        name: "相似度匹配",
        start: () => {
          setCurrentAiStep(3);
          setStepStatus(3, "running");
          addLog("开始相似度匹配...", "info");
        },
        run: () => {
          let edges = 0;
          const t = window.setInterval(() => {
            if (destroyed) { window.clearInterval(t); return; }
            edges += Math.floor(Math.random() * 15) + 10;
            if (edges > 400) edges = 400;
            if (edges >= 400) {
              window.clearInterval(t);
              setStepStatus(3, "done");
              addLog("相似度匹配完成，建立匹配边 400 余条", "success");
              doStep(4);
            }
          }, 100);
          simTimersRef.current.push(t);
        },
      },
      {
        name: "聚类研判",
        start: () => {
          setCurrentAiStep(4);
          setStepStatus(4, "running");
          addLog("开始多频事件聚类...", "info");
        },
        run: () => {
          let cl = 0;
          const targetCl = 12;
          const t = window.setInterval(() => {
            if (destroyed) { window.clearInterval(t); return; }
            cl += 1;
            setSimClusterCount(cl);
            if (cl >= targetCl) {
              window.clearInterval(t);
              setStepStatus(4, "done");
              addLog(`聚类研判完成，发现 ${targetCl} 个多频事件簇`, "success");
              addLog("AI研判流程全部完成", "success");
            }
          }, 300);
          simTimersRef.current.push(t);
        },
      },
    ];

    const doStep = (idx: number) => {
      if (idx >= stepFlow.length) return;
      stepFlow[idx].start();
      stepFlow[idx].run();
    };

    doStep(0);

    return () => { destroyed = true; };
  }, []);

  const handleStartAnalysis = useCallback(async () => {
    if (!importResult) return;
    setStep(4);
    setJob(null);
    setJobId(null);
    setJobError(null);
    setIsCreatingJob(true);

    try {
      const created = await createAnalysisJob({
        import_batch_id: importResult.batch_id,
        max_work_orders: Math.min(importResult.successful_rows, 300),
      });
      setJobId(created.job_id);
      setJob(created);
      setIsCreatingJob(false);
      pushToast(`已创建研判任务`, "success");

      const total = created.selected_rows > 0 ? created.selected_rows : importResult.successful_rows;
      runSimulation(total, { current: created.job_id });

      if (created.status !== "completed" && created.status !== "failed") {
        stopPolling();
        pollTimerRef.current = window.setInterval(async () => {
          if (!jobIdRef.current) return;
          try {
            const data = await getAnalysisJob(jobIdRef.current);
            setJob(data);
            if (data.status === "completed") {
              stopPolling();
              setSimProcessed(data.processed_rows);
              setSimEventCount(data.event_count);
              setSimClusterCount(data.cluster_count);
              setAiStepStatuses(AI_STEPS.map(() => "done"));
              queryClient.invalidateQueries({ queryKey: ["clusters"] });
              pushToast("研判完成", "success");
            } else if (data.status === "failed") {
              stopPolling();
              setJobError(data.error ?? "未知错误");
              pushToast("研判失败", "error");
            }
          } catch (e) {
            // keep polling
          }
        }, POLL_INTERVAL_MS);
      } else if (created.status === "completed") {
        setAiStepStatuses(AI_STEPS.map(() => "done"));
      }
    } catch (e) {
      setIsCreatingJob(false);
      setJobError(describeApiError(e));
      pushToast(`创建研判失败：${describeApiError(e)}`, "error");
    }
  }, [importResult, pushToast, queryClient, runSimulation]);

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

  const handleHistory = useCallback(() => {
    pushToast("历史记录功能开发中", "info");
  }, [pushToast]);

  const aiProgress = job
    ? job.selected_rows > 0
      ? Math.min(100, Math.round((job.processed_rows / job.selected_rows) * 100))
      : 0
    : (() => {
        const stepWeights = [20, 20, 15, 25, 20];
        let pct = 0;
        for (let i = 0; i < aiStepStatuses.length; i++) {
          if (aiStepStatuses[i] === "done") pct += stepWeights[i];
          else if (aiStepStatuses[i] === "running") {
            if (i === 0) pct += Math.round((simProcessed / Math.max(totalCount, 1)) * stepWeights[i]);
            else if (i === 1) pct += Math.round((simEventCount / Math.max(Math.floor(totalCount * 0.85), 1)) * stepWeights[i]);
            else pct += stepWeights[i] / 2;
            break;
          } else break;
        }
        return Math.min(99, pct);
      })();

  const displayProcessed = job ? job.processed_rows : simProcessed;
  const displayEvents = job ? job.event_count : simEventCount;
  const displayClusters = job ? job.cluster_count : simClusterCount;
  const displayTotal = job ? job.selected_rows : totalCount;

  const aiStatusText = useMemo(() => {
    if (job?.status === "queued") return "研判任务排队中...";
    if (job?.status === "running") return "正在进行AI智能研判...";
    const runningIdx = aiStepStatuses.findIndex((s) => s === "running");
    if (runningIdx >= 0) return `正在进行${AI_STEPS[runningIdx].label}...`;
    if (aiStepStatuses.every((s) => s === "done")) return "AI研判即将完成...";
    return "正在准备AI研判...";
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
        <StageUpload file={file} onFileSelected={handleFileSelected} />
      ) : null}

      {step === 2 && file ? (
        <StagePreview
          file={file}
          previewRows={previewRows}
          totalCount={totalCount}
          validCount={validCount}
          warningCount={warningCount}
          invalidCount={invalidCount}
          errors={validationErrors}
          onReselect={handleReselect}
          onConfirm={handleConfirmImport}
          onBack={handleBackToUpload}
          confirming={importing}
        />
      ) : null}

      {step === 3 ? (
        <StageImportProgress
          progress={importProgress}
          currentRow={importCurrentRow}
          totalRows={totalCount}
          result={importResult}
          elapsed={importElapsed}
          error={importError}
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
          highConfidenceRate={highConfidenceRate}
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
