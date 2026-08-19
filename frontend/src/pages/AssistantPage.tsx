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

const EXAMPLES = ["容桂有什么事情", "容桂有几条急单", "大良有没有拖欠工资的情况"];
const statusLabel: Record<string, string> = { unhandled: "未处理", investigating: "正在跟进", resolved: "已解决" };

type ConversationMessage = { id: string; query: string; response: AgentQueryResponse; expanded: boolean };

function groupList(items: { label: string; count: number }[]): JSX.Element {
  return <div className="assistant-stat-list">{items.slice(0, 5).map((item) => <div key={item.label} className="assistant-stat-row"><span>{statusLabel[item.label] ?? item.label}</span><strong>{item.count}</strong></div>)}</div>;
}

function WorkOrderAttachment({ item, selected, selectable, toggle }: {
  item: AgentQueryResponse["work_orders"][number]; selected: UUID[]; selectable: boolean; toggle: (id: UUID) => void;
}): JSX.Element {
  return <article className="assistant-attachment-card">
    {selectable ? <label className="assistant-attachment-card__select"><input type="checkbox" checked={selected.includes(item.work_order_id)} onChange={() => toggle(item.work_order_id)} /><span>选择</span></label> : null}
    <div className="assistant-attachment-card__body"><div><span className="assistant-card__number">{item.external_work_order_number ?? "未提供工单号"}</span>{item.is_urgent ? <span className="tag tag--danger">急</span> : null}</div><strong>{item.title ?? "未提供标题"}</strong><p>{item.normalized_summary ?? "当前 V2 未生成事件摘要。"}</p><small>{item.location ?? "地点未解析"} · {item.event_type ?? "事件类型未归类"} · {statusLabel[item.handling_status] ?? item.handling_status}</small></div>
    <div className="assistant-attachment-card__links"><Link to={`/work-orders/${item.work_order_id}`}>查看工单 →</Link>{item.cluster_ids[0] ? <Link to={`/events/${item.cluster_ids[0]}`}>查看多频事件 →</Link> : null}</div>
  </article>;
}

export function AssistantPage(): JSX.Element {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [selected, setSelected] = useState<UUID[]>([]);
  const [workset, setWorkset] = useState<WorksetResponse | null>(null);
  const [dashboard, setDashboard] = useState<DynamicDashboardResponse | null>(null);
  const [preview, setPreview] = useState<BatchActionPreviewResponse | null>(null);
  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = messages.at(-1)?.response ?? null;

  const ask = async (question = input) => {
    const normalized = question.trim();
    if (!normalized || busy) return;
    setBusy(true); setError(null); setPreview(null);
    try {
      const previous = messages.at(-1);
      const response = await queryAgent({ query: normalized, previous_query: previous?.query, previous_query_snapshot: previous?.response.compiled_query, previous_work_order_ids: previous?.response.work_orders.map((item) => item.work_order_id) });
      setMessages((old) => [...old, { id: `${Date.now()}-${old.length}`, query: normalized, response, expanded: false }]);
      setInput(""); setSelected([]); setDashboard(null);
    } catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };
  const toggle = (id: UUID) => setSelected((old) => old.includes(id) ? old.filter((item) => item !== id) : [...old, id]);
  const selectedRows = latest?.work_orders.filter((item) => selected.includes(item.work_order_id)) ?? [];
  const addToWorkset = async () => {
    if (!latest || selected.length === 0) return;
    setBusy(true); setError(null);
    try {
      setWorkset(await createWorkset({ name: `${latest.original_query.slice(0, 22)}工作集`, original_query: latest.original_query, query_snapshot: latest.compiled_query, work_order_ids: selected, cluster_ids: [...new Set(selectedRows.flatMap((item) => item.cluster_ids))] }));
      setWorkspaceOpen(true);
    } catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };
  const makeDashboard = async () => {
    const ids = workset?.work_order_ids ?? selected;
    if (ids.length === 0) return;
    setBusy(true); setError(null);
    try { setDashboard(await generateAgentDashboard({ title: "当前查询临时看板", work_order_ids: ids, cluster_ids: workset?.cluster_ids ?? [] })); setWorkspaceOpen(true); }
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
    <header className="assistant-hero assistant-hero--chat"><div><p className="eyebrow">智能研判助手</p><h1>问问 12345</h1><p>在同一段对话里继续追问；回答只依据附带的可核查工单证据。</p></div><button className="btn btn--secondary" onClick={() => setWorkspaceOpen(true)}>工作集{workset ? ` · ${workset.result_count}` : ""}</button></header>
    <main className="assistant-chat-shell"><div className="assistant-conversation" aria-live="polite">
      {messages.map((message, index) => {
        const isLatest = index === messages.length - 1;
        const hasAttachments = message.response.total > 0;
        const showCards = hasAttachments && (message.response.total <= 3 || message.expanded);
        return <article className="assistant-message-pair" key={message.id}>
          <div className="assistant-user-message"><span>你</span><p>{message.query}</p></div>
          <div className="assistant-answer"><div className="assistant-answer__identity"><span>12345</span><strong>问问12345</strong></div><p>{message.response.answer}</p>
            {hasAttachments ? <div className="assistant-message-attachments">{showCards ? <div className="assistant-attachment-list">{message.response.work_orders.map((item) => <WorkOrderAttachment key={item.work_order_id} item={item} selected={isLatest ? selected : []} selectable={isLatest} toggle={toggle} />)}</div> : <button className="assistant-attachment-button" onClick={() => setMessages((old) => old.map((item) => item.id === message.id ? { ...item, expanded: true } : item))}>📄 查看 {message.response.total} 条工单</button>}{message.response.cluster_ids.length > 0 ? <Link className="assistant-attachment-link" to={`/events/${message.response.cluster_ids[0]}`}>🔗 多频事件 · {message.response.cluster_ids.length} 个</Link> : null}{message.expanded && message.response.total > 3 ? <button className="btn btn--secondary" onClick={() => setMessages((old) => old.map((item) => item.id === message.id ? { ...item, expanded: false } : item))}>收起工单</button> : null}</div> : null}
            {isLatest && selected.length > 0 ? <div className="assistant-message-actions"><span>已选择 {selected.length} 条</span><button className="btn btn--secondary" onClick={() => void addToWorkset()} disabled={busy}>加入工作集</button><button className="btn btn--primary" onClick={() => void makeDashboard()} disabled={busy}>生成看板</button></div> : null}<small>{message.response.disclaimer}</small></div>
        </article>;
      })}
      {messages.length === 0 ? <div className="assistant-empty"><h2>开始对话</h2><p>例如：容桂有什么事情？接着可以问“有几条急单”。</p><div>{EXAMPLES.map((example) => <button key={example} onClick={() => void ask(example)} disabled={busy}>{example}</button>)}</div></div> : null}
    </div>{error ? <div className="assistant-alert assistant-alert--error">{error}</div> : null}<div className={`assistant-query-box assistant-query-box--chat ${messages.length === 0 ? "assistant-query-box--initial" : ""}`}><textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void ask(); } }} placeholder="继续问问12345……" aria-label="自然语言工单查询" /><div className="assistant-query-box__footer"><span>Enter 发送 · Shift + Enter 换行</span><button className="btn btn--primary" onClick={() => void ask()} disabled={busy}>{busy ? "正在查询…" : messages.length === 0 ? "开始对话" : "发送"}</button></div></div></main>
    {workspaceOpen ? <div className="assistant-drawer-backdrop" role="presentation" onMouseDown={() => setWorkspaceOpen(false)}><aside className="assistant-workspace-drawer" aria-label="工作集" onMouseDown={(event) => event.stopPropagation()}><div className="assistant-drawer-head"><div><p className="eyebrow">工作集</p><h2>{workset?.name ?? "尚未创建工作集"}</h2></div><button className="btn btn--secondary" onClick={() => setWorkspaceOpen(false)}>关闭</button></div>{workset ? <><p>已持久化 {workset.result_count} 条人工选择的工单。</p><button className="btn btn--primary btn--block" onClick={() => void requestPreview()} disabled={busy}>批量设为正在跟进</button></> : <p>展开最新消息的工单附件并勾选后，可加入工作集。</p>}{preview ? <div className="assistant-drawer-section"><h3>执行前确认</h3><p>{preview.message}</p><button className="btn btn--secondary" onClick={() => setPreview(null)}>取消</button><button className="btn btn--primary" onClick={() => void confirmAction()} disabled={busy}>确认执行</button></div> : null}{dashboard ? <div className="assistant-drawer-section"><p className="eyebrow">动态临时看板</p><h3>{dashboard.title}</h3><p>{dashboard.work_order_count} 条工单 · {dashboard.multi_frequency_event_count} 个多频事件</p><h4>主要问题</h4>{groupList(dashboard.topic_groups)}<h4>主要地点</h4>{groupList(dashboard.location_groups)}<small>{dashboard.disclaimer}</small></div> : null}</aside></div> : null}
  </section>;
}
