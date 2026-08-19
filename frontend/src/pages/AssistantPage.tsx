import { useState } from "react";
import { Link } from "react-router-dom";
import type { JSX } from "react";

import {
  createWorkset,
  executeWorksetAction,
  generateAgentDashboard,
  previewWorksetAction,
  queryAgent,
} from "../api/agent";
import { describeApiError } from "../api/client";
import type {
  AgentQueryResponse,
  BatchActionPreviewResponse,
  DynamicDashboardResponse,
  UUID,
  WorksetResponse,
} from "../types/api";

const EXAMPLES = [
  "大良有没有拖欠工资的情况",
  "大良最近有什么投诉",
  "最近一个月有哪些工程款投诉？",
  "金域滨江有什么问题",
];
const CARD_LIMIT = 5;

const statusLabel: Record<string, string> = {
  unhandled: "未处理",
  investigating: "正在跟进",
  resolved: "已解决",
};

type ConversationMessage = {
  id: string;
  query: string;
  response: AgentQueryResponse;
  expanded: boolean;
};

function groupList(items: { label: string; count: number }[]): JSX.Element {
  return <div className="assistant-stat-list">{items.slice(0, 5).map((item) => <div key={item.label} className="assistant-stat-row"><span>{statusLabel[item.label] ?? item.label}</span><strong>{item.count}</strong></div>)}</div>;
}

function workOrderCard(
  item: AgentQueryResponse["work_orders"][number],
  selected: UUID[],
  toggle: (id: UUID) => void,
  selectable: boolean,
): JSX.Element {
  return <article className="assistant-card" key={item.work_order_id}>
    <label className="assistant-card__select"><input type="checkbox" checked={selected.includes(item.work_order_id)} onChange={() => toggle(item.work_order_id)} disabled={!selectable} /><span>选择</span></label>
    <div className="assistant-card__body">
      <div className="assistant-card__top"><span className="assistant-card__number">{item.external_work_order_number ?? "未提供工单号"}</span><span className={`assistant-status assistant-status--${item.handling_status}`}>{statusLabel[item.handling_status] ?? item.handling_status}</span></div>
      <h3>{item.title ?? "未提供标题"}</h3><p>{item.normalized_summary ?? "当前 V2 未生成事件摘要。"}</p>
      <div className="assistant-card__meta"><span>{item.location ?? "地点未解析"}</span><span>{item.event_type ?? "事件类型未归类"}</span><span>{item.reported_at ? `${item.time_label}：${new Date(item.reported_at).toLocaleDateString()}` : item.time_label}</span></div>
    </div>
    <div className="assistant-card__links"><Link to={`/work-orders/${item.work_order_id}`}>查看工单 →</Link>{item.cluster_ids[0] ? <Link to={`/events/${item.cluster_ids[0]}`}>查看多频事件 →</Link> : null}</div>
  </article>;
}

export function AssistantPage(): JSX.Element {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [selected, setSelected] = useState<UUID[]>([]);
  const [workset, setWorkset] = useState<WorksetResponse | null>(null);
  const [dashboard, setDashboard] = useState<DynamicDashboardResponse | null>(null);
  const [preview, setPreview] = useState<BatchActionPreviewResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = messages.at(-1)?.response ?? null;

  const ask = async (question = input) => {
    const normalized = question.trim();
    if (!normalized || busy) return;
    setBusy(true); setError(null); setPreview(null);
    try {
      const response = await queryAgent({
        query: normalized,
        previous_query_snapshot: latest?.compiled_query,
        previous_work_order_ids: latest?.work_orders.map((item) => item.work_order_id),
      });
      setMessages((old) => [...old, { id: `${Date.now()}-${old.length}`, query: normalized, response, expanded: false }]);
      setInput("");
      // Retrieval never becomes a workset selection without an operator action.
      setSelected([]);
      setDashboard(null);
    } catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };

  const toggle = (id: UUID) => setSelected((old) => old.includes(id) ? old.filter((item) => item !== id) : [...old, id]);
  const addToWorkset = async () => {
    if (!latest || selected.length === 0) return;
    setBusy(true); setError(null);
    try {
      const selectedRows = latest.work_orders.filter((item) => selected.includes(item.work_order_id));
      setWorkset(await createWorkset({ name: `${latest.original_query.slice(0, 22)}工作集`, original_query: latest.original_query, query_snapshot: latest.compiled_query, work_order_ids: selected, cluster_ids: [...new Set(selectedRows.flatMap((item) => item.cluster_ids))] }));
    } catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };
  const makeDashboard = async () => {
    const ids = workset?.work_order_ids ?? selected;
    if (ids.length === 0) return;
    setBusy(true); setError(null);
    try { setDashboard(await generateAgentDashboard({ title: "当前查询临时看板", work_order_ids: ids, cluster_ids: workset?.cluster_ids ?? [] })); }
    catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };
  const requestPreview = async () => {
    if (!workset) return;
    setBusy(true); setError(null);
    try { setPreview(await previewWorksetAction(workset.id, { action_type: "set_handling_status", new_status: "investigating" })); }
    catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };
  const confirmAction = async () => {
    if (!workset || !preview) return;
    setBusy(true); setError(null);
    try { await executeWorksetAction(workset.id, { preview_id: preview.preview_id }); setPreview(null); }
    catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };

  return <section className="assistant-page">
    <header className="assistant-hero"><p className="eyebrow">智能研判助手</p><h1>问问 12345</h1><p>自然语言查询真实工单。每一轮回答只依据其下方展示的工单证据。</p></header>
    <div className="assistant-layout"><main className="assistant-results">
      <div className="assistant-conversation" aria-live="polite">
        {messages.map((message, index) => {
          const visible = message.expanded ? message.response.work_orders : message.response.work_orders.slice(0, CARD_LIMIT);
          const isLatest = index === messages.length - 1;
          return <div className="assistant-turn" key={message.id}>
            <div className="assistant-user-message">{message.query}</div>
            <div className="assistant-answer"><span className="assistant-answer__mark">回答</span><p>{message.response.answer}</p><small>{message.response.disclaimer}</small></div>
            <div className="assistant-results-head"><div><h2>相关工单（{message.response.total}）</h2><p>{isLatest ? `已选择 ${selected.length} 条` : "该轮检索证据"}</p></div>{isLatest && message.response.work_orders.length > 0 ? <div className="assistant-results-head__actions"><button className="btn btn--primary" onClick={() => void addToWorkset()} disabled={busy || selected.length === 0}>加入工作集</button><button className="btn btn--secondary" onClick={() => void makeDashboard()} disabled={busy || selected.length === 0}>生成看板</button></div> : null}</div>
            <div className="assistant-cards">{visible.map((item) => workOrderCard(item, isLatest ? selected : [], isLatest ? toggle : () => undefined, isLatest))}</div>
            {message.response.work_orders.length > CARD_LIMIT ? <button className="btn btn--secondary" onClick={() => setMessages((old) => old.map((item) => item.id === message.id ? { ...item, expanded: !item.expanded } : item))}>{message.expanded ? "收起工单" : `查看全部 ${message.response.total} 条`}</button> : null}
          </div>;
        })}
        {messages.length === 0 ? <div className="assistant-empty"><h2>开始对话</h2><p>例如：大良有没有拖欠工资的情况？</p></div> : null}
      </div>
      {error ? <div className="assistant-alert assistant-alert--error">{error}</div> : null}
      <div className="assistant-query-box"><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void ask(); } }} placeholder="继续问，或输入一个新的工单问题…" aria-label="自然语言工单查询" /><div className="assistant-query-box__footer"><span>Ctrl / ⌘ + Enter 发送</span><button className="btn btn--primary" onClick={() => void ask()} disabled={busy}>{busy ? "正在查询…" : "开始对话"}</button></div></div>
      <div className="assistant-examples">{EXAMPLES.map((example) => <button key={example} onClick={() => void ask(example)} disabled={busy}>{example}</button>)}</div>
    </main>
    <aside className="assistant-side"><div className="assistant-side-card"><p className="eyebrow">当前工作集</p>{workset ? <><h2>{workset.name}</h2><p>已持久化 {workset.result_count} 条人工选择的工单。</p><button className="btn btn--primary btn--block" onClick={() => void requestPreview()} disabled={busy}>批量设为正在跟进</button></> : <><h2>尚未创建工作集</h2><p>勾选最新一轮中的工单后，才可加入工作集。</p></>}</div>{preview ? <div className="assistant-side-card assistant-confirm"><p className="eyebrow">执行前确认</p><h2>准备处理 {preview.affected_work_order_count} 条</h2><p>{preview.message}</p><div className="assistant-confirm__actions"><button className="btn btn--secondary" onClick={() => setPreview(null)}>取消</button><button className="btn btn--primary" onClick={() => void confirmAction()} disabled={busy}>确认执行</button></div></div> : null}{dashboard ? <div className="assistant-side-card assistant-dashboard"><p className="eyebrow">动态临时看板</p><h2>{dashboard.title}</h2><div className="assistant-dashboard__numbers"><span><strong>{dashboard.work_order_count}</strong>相关工单</span><span><strong>{dashboard.multi_frequency_event_count}</strong>多频事件</span></div><h3>主要问题</h3>{groupList(dashboard.topic_groups)}<h3>主要地点</h3>{groupList(dashboard.location_groups)}<p className="text-muted">{dashboard.disclaimer}</p></div> : null}</aside>
    </div>
  </section>;
}
