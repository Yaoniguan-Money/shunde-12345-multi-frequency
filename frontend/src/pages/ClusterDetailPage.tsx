import { useMemo, useRef, useState } from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import type { JSX } from "react";

import { getCluster } from "../api/catalog";
import { ApiError, describeApiError, triggerBlobDownload } from "../api/client";
import {
  addCorrection,
  addHandlingRecord,
  exportClusterCsv,
  type HandlingRecordCreate,
  type HumanCorrectionCreate,
} from "../api/review";
import type {
  EventResponse,
  HandlingRecordResponse,
  HumanCorrectionResponse,
  RemovedMemberResponse,
  WorkOrderDetailResponse,
} from "../types/api";
import { EdgeCard } from "../components/EdgeCard";
import { EmptyState } from "../components/EmptyState";
import { ErrorState } from "../components/ErrorState";
import { LongText } from "../components/LongText";
import { Skeleton } from "../components/Skeleton";
import { StatusBadge } from "../components/StatusBadge";
import { useToast } from "../components/useToast";
import {
  describeEvidence,
  formatConfidence,
} from "../utils/evidence";
import {
  displayActor,
  displayEventType,
  displayEvidenceValue,
  displayStatus,
} from "../utils/displayText";

gsap.registerPlugin(useGSAP);

const DEFAULT_ACTOR_ID = "演示操作员";
const STATUS_SUGGESTIONS = [
  { value: "unhandled", label: "未处理" },
  { value: "investigating", label: "处理中" },
  { value: "resolved", label: "已办结" },
];

function ClusterEvidenceSummary({
  evidence,
}: {
  evidence: Record<string, unknown>;
}): JSX.Element {
  const items = describeEvidence(evidence).filter(
    (item) => !["member_event_ids", "member_work_order_ids", "rejected_edges"].includes(item.key),
  );
  return (
    <div className="evidence-box">
      <span className="evidence-box__label">智能判断摘要</span>
      {items.length === 0 ? (
        <p className="text-muted" style={{ margin: 0 }}>
          暂无可展示的结构化判断依据。
        </p>
      ) : (
        <div className="edge-card__evidence-list" style={{ marginTop: 0 }}>
          {items.map((item) => (
            <div className="edge-evidence-row" key={item.key}>
              <span className="edge-evidence-row__key">{item.label}</span>
              <span
                className={
                  item.tone === "positive"
                    ? "edge-evidence-row__value edge-evidence-row__value--positive"
                    : item.tone === "conflict"
                      ? "edge-evidence-row__value edge-evidence-row__value--conflict"
                      : "edge-evidence-row__value"
                }
              >
                {displayEvidenceValue(item.value)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EventUnderstanding({
  event,
  onRemove,
  onConfirm,
  actorId,
  onActorIdChange,
  isRemoving,
  isConfirming,
  isRemoved,
}: {
  event: EventResponse;
  onRemove: () => void;
  onConfirm: () => void;
  actorId: string;
  onActorIdChange: (value: string) => void;
  isRemoving: boolean;
  isConfirming: boolean;
  isRemoved: boolean;
}): JSX.Element {
  return (
    <section className="member-card__event">
      <div className="member-card__field">
        <span className="member-card__field-key">事件摘要</span>
        <span className="member-card__field-value">{event.normalized_summary}</span>
      </div>
      <div className="member-card__field">
        <span className="member-card__field-key">问题类型</span>
        <span className="member-card__field-value">{displayEventType(event.event_type)}</span>
      </div>
      <div className="member-card__field">
        <span className="member-card__field-key">诉求内容</span>
        <span className="member-card__field-value">{event.behavior ?? "—"}</span>
      </div>
      {event.entities.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">涉及对象</span>
          <div className="member-card__chips">
            {event.entities.map((entity) => (
              <span
                className="chip chip--entity"
                key={entity.entity_id}
              >
                {entity.standard_name ?? entity.entity_id.slice(0, 8)}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {event.location_signals.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">涉及地点</span>
          <div className="member-card__chips">
            {event.location_signals.map((location, index) => (
              <span className="chip chip--location" key={`${location}-${index}`}>
                {location}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      {event.time_signals.length > 0 ? (
        <div className="member-card__field">
          <span className="member-card__field-key">反映时间</span>
          <div className="member-card__chips">
            {event.time_signals.map((time, index) => (
              <span className="chip chip--time" key={`${time}-${index}`}>
                {time}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <details className="member-card__event-actions">
        <summary>调整事件归属</summary>
        <div className="event-action-row">
          <div className="event-action-row__actor">
            <label
              className="event-action-row__actor-label"
              htmlFor={`actor-${event.event_id}`}
            >
              操作员编号
            </label>
            <input
              id={`actor-${event.event_id}`}
              type="text"
              className="event-action-row__actor-input"
              value={actorId}
              onChange={(e) => onActorIdChange(e.target.value)}
              disabled={isRemoved}
              placeholder="请输入操作员编号"
            />
          </div>
          {isRemoved ? (
            <button
              type="button"
              className="btn btn--secondary btn--small"
              onClick={onConfirm}
              disabled={isConfirming || !actorId.trim()}
            >
              {isConfirming ? "提交中…" : "恢复归属"}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn--danger btn--small"
              onClick={onRemove}
              disabled={isRemoving || !actorId.trim()}
            >
              {isRemoving ? "提交中…" : "移出该多频事件"}
            </button>
          )}
        </div>
      </details>
    </section>
  );
}

function RemovedMemberCard({
  item,
  actorId,
  reason,
  onActorChange,
  onReasonChange,
  onRestore,
  isRestoring,
}: {
  item: RemovedMemberResponse;
  actorId: string;
  reason: string;
  onActorChange: (value: string) => void;
  onReasonChange: (value: string) => void;
  onRestore: () => void;
  isRestoring: boolean;
}): JSX.Element {
  const event = item.event;
  const workOrder = item.work_order;
  return (
    <article className="member-card member-card--removed">
      <header className="member-card__header">
        <h4 className="member-card__title">
          {item.raw_title ?? workOrder?.raw_title ?? "已移出事件"}
        </h4>
        <span className="uuid-mono">
          {workOrder?.external_work_order_number ?? "编号未提供"}
        </span>
      </header>
      <div className="member-card__body">
        <div className="member-card__region member-card__region--raw">
          <div className="member-card__region-label member-card__region-label--raw">
            已移出事件
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">事件摘要</span>
            <span className="member-card__field-value">
              {event?.normalized_summary ?? "原事件不可解析"}
            </span>
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">涉及地点</span>
            <span className="member-card__field-value">
              {event?.location_signals?.join("、") || "—"}
            </span>
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">移出记录</span>
            <span className="member-card__field-value">
              {displayActor(item.actor_id)} · {new Date(item.removed_at).toLocaleString("zh-CN")}
              {item.reason ? ` · ${item.reason}` : ""}
            </span>
          </div>
          {item.raw_content ? (
            <div className="member-card__field">
              <span className="member-card__field-key">原始内容</span>
              <span className="member-card__field-value">
                <LongText text={item.raw_content} maxChars={320} />
              </span>
            </div>
          ) : null}
        </div>
        <div className="member-card__region member-card__region--ai">
          <div className="member-card__region-label member-card__region-label--ai">
            恢复归属
          </div>
          {!item.can_restore || !event ? (
            <p className="text-muted" style={{ margin: 0 }}>
              原事件不可解析，保留纠错记录但无法恢复归属。
            </p>
          ) : (
            <div className="action-form">
              <div className="action-form__field">
                <label className="action-form__label" htmlFor={`restore-actor-${event.event_id}`}>
                  操作员编号
                </label>
                <input
                  id={`restore-actor-${event.event_id}`}
                  type="text"
                  className="action-form__input"
                  value={actorId}
                  onChange={(e) => onActorChange(e.target.value)}
                  disabled={isRestoring}
                  placeholder="请输入操作员编号"
                />
              </div>
              <div className="action-form__field">
                <label className="action-form__label" htmlFor={`restore-reason-${event.event_id}`}>
                  恢复理由
                </label>
                <input
                  id={`restore-reason-${event.event_id}`}
                  type="text"
                  className="action-form__input"
                  value={reason}
                  onChange={(e) => onReasonChange(e.target.value)}
                  disabled={isRestoring}
                  placeholder="例如：误判，恢复归属"
                />
              </div>
              <div className="action-form__actions">
                <button
                  type="button"
                  className="btn btn--secondary btn--small"
                  onClick={onRestore}
                  disabled={isRestoring || !actorId.trim() || !reason.trim()}
                >
                  {isRestoring ? "提交中…" : "恢复归属"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </article>
  );
}

function WorkOrderCard({
  detail,
  fromAssistant,
  onRemoveEvent,
  onConfirmEvent,
  actorByEvent,
  onActorChange,
  removingEventId,
  confirmingEventId,
  removedEventIds,
}: {
  detail: WorkOrderDetailResponse;
  fromAssistant: boolean;
  onRemoveEvent: (eventInstanceId: string) => void;
  onConfirmEvent: (eventInstanceId: string) => void;
  actorByEvent: Record<string, string>;
  onActorChange: (eventInstanceId: string, value: string) => void;
  removingEventId: string | null;
  confirmingEventId: string | null;
  removedEventIds: Set<string>;
}): JSX.Element {
  const { summary: workOrder, raw_content: rawContent, events } = detail;
  return (
    <article className="member-card">
      <header className="member-card__header">
        <h4 className="member-card__title">
          <Link to={`/work-orders/${workOrder.work_order_id}`} state={{ fromAssistant }}>
          {workOrder.raw_title ??
            `工单 ${workOrder.external_work_order_number ?? "未命名"}`}
          </Link>
        </h4>
        <Link className="uuid-mono" to={`/work-orders/${workOrder.work_order_id}`} state={{ fromAssistant }}>
          {workOrder.external_work_order_number ?? "工单编号未提供"}
        </Link>
      </header>
      <div className="member-card__body">
        <div className="member-card__region member-card__region--raw">
          <div className="member-card__region-label member-card__region-label--raw">
            市民诉求原文
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">工单编号</span>
            <span className="member-card__field-value">
              {workOrder.external_work_order_number ?? "—"}
            </span>
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">原始内容</span>
            <span className="member-card__field-value">
              <LongText text={rawContent} maxChars={400} />
            </span>
          </div>
          <div className="member-card__field">
            <span className="member-card__field-key">入库时间</span>
            <span className="member-card__field-value">
              {new Date(workOrder.created_at).toLocaleString("zh-CN")}
            </span>
          </div>
        </div>
        <div className="member-card__region member-card__region--ai">
          <div className="member-card__region-label member-card__region-label--ai">
            智能研判结果 · {events.length} 项
          </div>
          {events.map((event) => (
            <EventUnderstanding
              key={event.event_id}
              event={event}
              actorId={actorByEvent[event.event_id] ?? DEFAULT_ACTOR_ID}
              onActorIdChange={(value) => onActorChange(event.event_id, value)}
              onRemove={() => onRemoveEvent(event.event_id)}
              onConfirm={() => onConfirmEvent(event.event_id)}
              isRemoving={removingEventId === event.event_id}
              isConfirming={confirmingEventId === event.event_id}
              isRemoved={removedEventIds.has(event.event_id)}
            />
          ))}
        </div>
      </div>
    </article>
  );
}

function HandlingTimeline({
  records,
}: {
  records: HandlingRecordResponse[];
}): JSX.Element {
  if (records.length === 0) {
    return <EmptyState title="暂无处理记录" />;
  }
  return (
    <div className="timeline" role="list">
      {records.map((record) => (
        <div className="timeline__item" key={record.record_id} role="listitem">
          <div className="timeline__dot" aria-hidden />
          <div className="timeline__body">
            <div className="timeline__head">
              <span className="timeline__status">
                {displayStatus(record.previous_status)}
              </span>
              <span className="timeline__arrow" aria-hidden>
                →
              </span>
              <span className="timeline__status">
                {displayStatus(record.new_status)}
              </span>
              <span className="timeline__actor">{displayActor(record.actor_id)}</span>
              <span className="timeline__time">
                {new Date(record.created_at).toLocaleString("zh-CN")}
              </span>
            </div>
            {record.description ? (
              <p className="timeline__desc" style={{ margin: 0 }}>
                {record.description}
              </p>
            ) : null}
            {record.result ? (
              <p className="timeline__desc" style={{ margin: 0 }}>
                <span className="text-muted">结果：</span>
                {record.result}
              </p>
            ) : null}
            {record.attachment_references.length > 0 ? (
              <div className="timeline__attachments">
                {record.attachment_references.map((ref, idx) => (
                  <span className="chip" key={`${ref}-${idx}`}>
                    {ref}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function CorrectionHistory({
  corrections,
}: {
  corrections: HumanCorrectionResponse[];
}): JSX.Element {
  if (corrections.length === 0) {
    return <EmptyState title="暂无纠错记录" />;
  }
  return (
    <div className="correction-list">
      {corrections.map((correction) => {
        const isRemove = correction.correction_type === "remove_member";
        const isConfirm = correction.correction_type === "confirm_member";
        const payload = correction.payload ?? {};
        const eventInstanceId =
          (payload.event_instance_id as string | undefined) ??
          (correction.work_order_id ?? "—");
        return (
          <div
            className={
              isConfirm
                ? "correction-item correction-item--confirm"
                : "correction-item"
            }
            key={correction.correction_id}
          >
            <span
              className={
                isRemove
                  ? "correction-item__type correction-item__type--remove"
                  : isConfirm
                    ? "correction-item__type correction-item__type--confirm"
                    : "correction-item__type"
              }
            >
              {isRemove ? "移除" : isConfirm ? "确认归属" : "其他纠错"}
            </span>
            <span className="correction-item__field">
              关联工单：<strong>{correction.work_order_id ? "已记录" : "未提供"}</strong>
            </span>
            <span className="correction-item__field">
              关联事件：<strong>{eventInstanceId === "—" ? "未提供" : "已记录"}</strong>
            </span>
            <span className="correction-item__field">
              操作员：<strong>{displayActor(correction.actor_id)}</strong>
            </span>
            <span className="correction-item__field">
              {new Date(correction.created_at).toLocaleString("zh-CN")}
            </span>
            {correction.reason ? (
              <span className="correction-item__field">
                理由：{correction.reason}
              </span>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function HandlingRecordForm({
  clusterId,
  currentHandlingStatus,
}: {
  clusterId: string;
  currentHandlingStatus: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const { push: pushToast } = useToast();
  const [newStatus, setNewStatus] = useState("");
  const [actorId, setActorId] = useState(DEFAULT_ACTOR_ID);
  const [description, setDescription] = useState("");
  const [result, setResult] = useState("");
  const [attachments, setAttachments] = useState("");

  const mutation = useMutation({
    mutationFn: (body: HandlingRecordCreate) =>
      addHandlingRecord(clusterId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["cluster", clusterId] });
      void queryClient.invalidateQueries({ queryKey: ["clusters"] });
      pushToast("处理记录已提交", "success");
      setNewStatus("");
      setDescription("");
      setResult("");
      setAttachments("");
    },
    onError: (error: unknown) => {
      pushToast(`提交失败：${describeApiError(error)}`, "error");
    },
  });

  function handleSubmit(event: React.FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const trimmedStatus = newStatus.trim();
    const trimmedActor = actorId.trim();
    if (!trimmedStatus) {
      pushToast("请填写新的处理状态", "error");
      return;
    }
    if (!trimmedActor) {
      pushToast("请填写操作员编号", "error");
      return;
    }
    const body: HandlingRecordCreate = {
      new_status: trimmedStatus,
      actor_id: trimmedActor,
    };
    const trimmedDesc = description.trim();
    if (trimmedDesc) body.description = trimmedDesc;
    const trimmedResult = result.trim();
    if (trimmedResult) body.result = trimmedResult;
    const attachmentsList = attachments
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s.length > 0);
    if (attachmentsList.length > 0) {
      body.attachment_references = attachmentsList;
    }
    mutation.mutate(body);
  }

  return (
    <form className="action-form" onSubmit={handleSubmit}>
      <div className="action-form__field">
        <label
          className="action-form__label"
          htmlFor="handling-new-status"
        >
          新状态<span className="req">*</span>
        </label>
        <select
          id="handling-new-status"
          className="action-form__input"
          value={newStatus}
          onChange={(e) => setNewStatus(e.target.value)}
          disabled={mutation.isPending}
        >
          <option value="">请选择处理状态</option>
          {STATUS_SUGGESTIONS.map((status) => (
            <option key={status.value} value={status.value}>{status.label}</option>
          ))}
        </select>
        <span className="action-form__hint">
          当前状态：
          <strong>{displayStatus(currentHandlingStatus)}</strong>
        </span>
      </div>
      <div className="action-form__field">
        <label className="action-form__label" htmlFor="handling-actor">
          操作员编号<span className="req">*</span>
        </label>
        <input
          id="handling-actor"
          type="text"
          className="action-form__input"
          value={actorId}
          onChange={(e) => setActorId(e.target.value)}
          maxLength={255}
          required
          disabled={mutation.isPending}
        />
      </div>
      <div className="action-form__field action-form__field--full">
        <label className="action-form__label" htmlFor="handling-description">
          描述（可选）
        </label>
        <textarea
          id="handling-description"
          className="action-form__textarea"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={10000}
          disabled={mutation.isPending}
        />
      </div>
      <div className="action-form__field">
        <label className="action-form__label" htmlFor="handling-result">
          处理结果（可选）
        </label>
        <input
          id="handling-result"
          type="text"
          className="action-form__input"
          value={result}
          onChange={(e) => setResult(e.target.value)}
          maxLength={10000}
          disabled={mutation.isPending}
        />
      </div>
      <div className="action-form__field">
        <label
          className="action-form__label"
          htmlFor="handling-attachments"
        >
          附件编号（可选，多个请用逗号分隔）
        </label>
        <input
          id="handling-attachments"
          type="text"
          className="action-form__input"
          value={attachments}
          onChange={(e) => setAttachments(e.target.value)}
          placeholder="例如：附件1，附件2"
          disabled={mutation.isPending}
        />
      </div>
      <div className="action-form__actions">
        <button
          type="submit"
          className="btn btn--primary"
          disabled={mutation.isPending}
        >
          {mutation.isPending ? "提交中…" : "提交处理记录"}
        </button>
      </div>
    </form>
  );
}

export function ClusterDetailPage(): JSX.Element {
  const { clusterId } = useParams<{ clusterId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const fromAssistant = Boolean(
    (location.state as { fromAssistant?: boolean } | null)?.fromAssistant,
  );
  const queryClient = useQueryClient();
  const { push: pushToast } = useToast();
  const containerRef = useRef<HTMLElement>(null);
  const [actorByEvent, setActorByEvent] = useState<Record<string, string>>({});
  const [reasonByEvent, setReasonByEvent] = useState<Record<string, string>>({});
  const [removingEventId, setRemovingEventId] = useState<string | null>(null);
  const [confirmingEventId, setConfirmingEventId] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["cluster", clusterId],
    queryFn: ({ signal }) => getCluster(clusterId ?? "", signal),
    enabled: Boolean(clusterId),
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.status === 404) {
        return false;
      }
      return failureCount < 1;
    },
  });

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".detail-section", {
          opacity: 0,
          y: 10,
          duration: 0.3,
          stagger: 0.06,
          ease: "power1.out",
        });
      });
    },
    { scope: containerRef, dependencies: [query.data?.summary.cluster_id] },
  );

  // 纠错 mutation：成功后失效缓存；如果 detail 重新拉取后 404，则跳转回列表。
  const correctionMutation = useMutation({
    mutationFn: (vars: { body: HumanCorrectionCreate }) =>
      addCorrection(clusterId ?? "", vars.body),
    onMutate: (vars) => {
      if (vars.body.correction_type === "remove_member") {
        setRemovingEventId(vars.body.event_instance_id);
      } else {
        setConfirmingEventId(vars.body.event_instance_id);
      }
    },
    onSuccess: async (_data, vars) => {
      if (vars.body.correction_type === "remove_member") {
        pushToast("已提交移除，事件归属已更新", "success");
      } else {
        pushToast("已恢复归属", "success");
      }
      // 主动 refetch detail，捕获 404。失效 clusters 列表。
      try {
        await queryClient.refetchQueries({
          queryKey: ["cluster", clusterId],
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          pushToast("纠错后该事件已不再满足多频条件，已返回列表", "info");
          navigate("/events", { replace: true });
          return;
        }
        // 其他错误让 react-query 内部状态处理，不吞掉
        throw error;
      }
      // refetchQueries 不会抛出（错误落在 query.error），
      // 所以需要额外检查 query 当前状态：
      const state = queryClient.getQueryState(["cluster", clusterId]);
      if (
        state?.status === "error" &&
        state.error instanceof ApiError &&
        state.error.status === 404
      ) {
        pushToast("纠错后该事件已不再满足多频条件，已返回列表", "info");
        navigate("/events", { replace: true });
        return;
      }
      void queryClient.invalidateQueries({ queryKey: ["clusters"] });
    },
    onError: (error: unknown) => {
      pushToast(`纠错失败：${describeApiError(error)}`, "error");
    },
    onSettled: () => {
      setRemovingEventId(null);
      setConfirmingEventId(null);
    },
  });

  const exportCsvMutation = useMutation({
    mutationFn: () => exportClusterCsv(clusterId ?? ""),
    onSuccess: (data) => {
      const filename = data.filename || `cluster-${clusterId ?? "unknown"}.csv`;
      triggerBlobDownload(data.blob, filename);
      pushToast("事件表格已导出", "success");
    },
    onError: (error: unknown) => {
      pushToast(`导出失败：${describeApiError(error)}`, "error");
    },
  });

  const removedEventIds = useMemo(() => {
    const set = new Set<string>();
    if (!query.data) return set;
    for (const correction of query.data.human_corrections) {
      if (correction.correction_type !== "remove_member") continue;
      const payload = correction.payload ?? {};
      const id = payload.event_instance_id;
      if (typeof id === "string") {
        // 若同一 event 没有后续 confirm_member，则视为已移除
        const hasConfirm = query.data.human_corrections.some(
          (c) =>
            c.correction_type === "confirm_member" &&
            (c.payload?.event_instance_id === id ||
              c.work_order_id === correction.work_order_id),
        );
        if (!hasConfirm) set.add(id);
      }
    }
    return set;
  }, [query.data]);

  if (!clusterId) {
    return <ErrorState error={new Error("缺少多频事件标识")} />;
  }

  if (query.isPending) {
    return <Skeleton variant="detail" />;
  }

  if (query.isError) {
    const err = query.error;
    if (err instanceof ApiError && err.status === 404 && !query.isFetchedAfterMount) {
      return (
        <EmptyState
          title="事件不存在"
          description="未找到该多频事件，可能已被删除或链接已失效。"
          action={
            <div className="detail-return-actions">
              {fromAssistant ? <button type="button" className="btn btn--primary" onClick={() => navigate("/assistant")}>← 返回智能研判</button> : null}
              <button type="button" className="btn btn--secondary" onClick={() => navigate("/")}>返回研判总览</button>
            </div>
          }
        />
      );
    }
    return <ErrorState error={err} onRetry={() => query.refetch()} />;
  }

  const data = query.data;
  if (!data) {
    return <EmptyState title="未加载到事件数据" />;
  }
  const {
    summary,
    work_orders: workOrders,
    edges,
    handling_history: handlingHistory,
    human_corrections: humanCorrections,
    removed_members: removedMembers = [],
  } = data;

  function handleRemoveEvent(eventInstanceId: string): void {
    const actor = (actorByEvent[eventInstanceId] ?? DEFAULT_ACTOR_ID).trim();
    if (!actor) {
      pushToast("请填写操作员编号", "error");
      return;
    }
    const confirmed = window.confirm(
      "确认移除该事件？移出后仍可在‘已移出事件’中恢复。",
    );
    if (!confirmed) return;
    correctionMutation.mutate({
      body: {
        correction_type: "remove_member",
        event_instance_id: eventInstanceId,
        actor_id: actor,
      },
    });
  }

  function handleConfirmEvent(eventInstanceId: string): void {
    const actor = (actorByEvent[eventInstanceId] ?? DEFAULT_ACTOR_ID).trim();
    if (!actor) {
      pushToast("请填写操作员编号", "error");
      return;
    }
    const confirmed = window.confirm(
      "确认恢复该事件的归属？",
    );
    if (!confirmed) return;
    correctionMutation.mutate({
      body: {
        correction_type: "confirm_member",
        event_instance_id: eventInstanceId,
        actor_id: actor,
      },
    });
  }

  function handleActorChange(eventInstanceId: string, value: string): void {
    setActorByEvent((prev) => ({ ...prev, [eventInstanceId]: value }));
  }

  function handleReasonChange(eventInstanceId: string, value: string): void {
    setReasonByEvent((prev) => ({ ...prev, [eventInstanceId]: value }));
  }

  function handleRestoreRemovedMember(item: RemovedMemberResponse): void {
    const eventInstanceId = item.event?.event_id;
    if (!eventInstanceId || !item.can_restore) {
      pushToast("原事件不可解析，无法恢复归属", "error");
      return;
    }
    const actor = (actorByEvent[eventInstanceId] ?? DEFAULT_ACTOR_ID).trim();
    const reason = (reasonByEvent[eventInstanceId] ?? "").trim();
    if (!actor) {
      pushToast("请填写操作员编号", "error");
      return;
    }
    if (!reason) {
      pushToast("请填写恢复理由", "error");
      return;
    }
    const confirmed = window.confirm(
      "确认恢复该事件的归属？",
    );
    if (!confirmed) return;
    correctionMutation.mutate({
      body: {
        correction_type: "confirm_member",
        event_instance_id: eventInstanceId,
        actor_id: actor,
        reason,
      },
    });
  }

  return (
    <section ref={containerRef} className="cluster-detail-page">
      <div className="detail-header">
        <div className="detail-header__back detail-return-actions">
          {fromAssistant ? <button type="button" className="btn btn--ghost btn--back" onClick={() => navigate("/assistant")}>← 返回智能研判</button> : null}
          <button type="button" className="btn btn--ghost btn--back" onClick={() => navigate("/")}>返回研判总览</button>
          {!fromAssistant ? <button type="button" className="btn btn--ghost btn--back" onClick={() => navigate("/events")}>返回多频事件</button> : null}
        </div>
        <p className="eyebrow">多频事件详情</p>
        <h1 className="detail-header__title">{summary.name}</h1>
        <div className="detail-header__badges">
          <StatusBadge status={summary.status} variant="analysis" />
          <StatusBadge status={summary.handling_status} variant="handling" />
        </div>
        <div className="detail-header__meta" aria-label="事件概况">
          <span><small>关联工单</small><strong>{summary.work_order_count}</strong></span>
          <span><small>研判事项</small><strong>{summary.event_count}</strong></span>
          <span><small>研判可信度</small><strong>{formatConfidence(summary.confidence)}</strong></span>
        </div>
        <div className="action-toolbar">
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => exportCsvMutation.mutate()}
            disabled={exportCsvMutation.isPending}
          >
            {exportCsvMutation.isPending ? "导出中…" : "导出事件表格"}
          </button>
          <span className="action-toolbar__hint">
            包含关联工单、研判结果、判断依据和办理记录。
          </span>
        </div>
      </div>

      <div className="detail-section detail-section--overview">
        <h2 className="detail-section__title">
          事件概览
        </h2>
        <ClusterEvidenceSummary evidence={summary.evidence} />
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          关联工单
          <span className="detail-section__count">
            （{workOrders.length} 条工单 · {summary.event_count} 项研判结果）
          </span>
        </h2>
        {workOrders.length === 0 ? (
          <EmptyState title="暂无关联工单" description="该多频事件当前没有关联工单。" />
        ) : (
          workOrders.map((workOrder) => (
            <WorkOrderCard
              key={workOrder.summary.work_order_id}
              detail={workOrder}
              fromAssistant={fromAssistant}
              onRemoveEvent={handleRemoveEvent}
              onConfirmEvent={handleConfirmEvent}
              actorByEvent={actorByEvent}
              onActorChange={handleActorChange}
              removingEventId={removingEventId}
              confirmingEventId={confirmingEventId}
              removedEventIds={removedEventIds}
            />
          ))
        )}
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          关联判断依据
          <span className="detail-section__count">
            （{edges.length} 条）
          </span>
        </h2>
        {edges.length === 0 ? (
          <EmptyState
            title="暂无关联判断依据"
            description="当前没有可展示的关联判断依据，可能是单工单事件或尚未完成比对。"
          />
        ) : (
          edges.map((edge, idx) => <EdgeCard key={idx} edge={edge} />)
        )}
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          已移出事件
          <span className="detail-section__count">（{removedMembers.length} 条）</span>
        </h2>
        {removedMembers.length === 0 ? (
          <EmptyState title="暂无已移出事件" description="移出成员会保留在这里，可在确认后恢复归属。" />
        ) : (
          removedMembers.map((item) => {
            const eventId = item.event?.event_id ?? "";
            return (
              <RemovedMemberCard
                key={item.correction_id}
                item={item}
                actorId={item.event ? actorByEvent[item.event.event_id] ?? DEFAULT_ACTOR_ID : DEFAULT_ACTOR_ID}
                reason={item.event ? reasonByEvent[item.event.event_id] ?? "" : ""}
                onActorChange={(value) => {
                  if (item.event) handleActorChange(item.event.event_id, value);
                }}
                onReasonChange={(value) => {
                  if (item.event) handleReasonChange(item.event.event_id, value);
                }}
                onRestore={() => handleRestoreRemovedMember(item)}
                isRestoring={confirmingEventId === eventId}
              />
            );
          })
        )}
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          处理记录
          <span className="detail-section__count">
            （{handlingHistory.length} 条历史）
          </span>
        </h2>
        <details className="workflow-panel">
          <summary>新增办理记录</summary>
          <HandlingRecordForm
            clusterId={clusterId}
            currentHandlingStatus={summary.handling_status}
          />
        </details>
        <HandlingTimeline records={handlingHistory} />
      </div>

      <div className="detail-section">
        <h2 className="detail-section__title">
          人工纠错
          <span className="detail-section__count">
            （{humanCorrections.length} 条历史）
          </span>
        </h2>
        <p className="detail-section__help">
          如发现事件归属不准确，可在对应研判结果中选择“调整事件归属”。所有调整都会保留操作记录。
        </p>
        <CorrectionHistory corrections={humanCorrections} />
      </div>
    </section>
  );
}
