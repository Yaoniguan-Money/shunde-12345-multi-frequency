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
  "最近一周有哪些正在升温的问题？",
  "最近一个月有哪些工程款投诉？",
  "查一下金域滨江近期投诉",
  "哪些未处理工单值得优先关注？",
];

const statusLabel: Record<string, string> = {
  unhandled: "未处理",
  investigating: "正在跟进",
  resolved: "已解决",
};

function groupList(items: { label: string; count: number }[]): JSX.Element {
  return (
    <div className="assistant-stat-list">
      {items.slice(0, 5).map((item) => (
        <div key={item.label} className="assistant-stat-row">
          <span>{statusLabel[item.label] ?? item.label}</span><strong>{item.count}</strong>
        </div>
      ))}
    </div>
  );
}

export function AssistantPage(): JSX.Element {
  const [input, setInput] = useState("");
  const [result, setResult] = useState<AgentQueryResponse | null>(null);
  const [selected, setSelected] = useState<UUID[]>([]);
  const [workset, setWorkset] = useState<WorksetResponse | null>(null);
  const [dashboard, setDashboard] = useState<DynamicDashboardResponse | null>(null);
  const [preview, setPreview] = useState<BatchActionPreviewResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = async (question = input) => {
    const normalized = question.trim();
    if (!normalized || busy) return;
    setBusy(true); setError(null); setPreview(null);
    try {
      const response = await queryAgent({
        query: normalized,
        previous_query_snapshot: result?.compiled_query,
        previous_work_order_ids: result?.work_orders.map((item) => item.work_order_id),
      });
      setInput(normalized);
      setResult(response);
      setSelected(response.work_orders.map((item) => item.work_order_id));
      setDashboard(null);
    } catch (cause) {
      setError(describeApiError(cause));
    } finally { setBusy(false); }
  };

  const toggle = (id: UUID) => setSelected((old) => old.includes(id) ? old.filter((item) => item !== id) : [...old, id]);
  const allSelected = result !== null && selected.length === result.work_orders.length;

  const addToWorkset = async () => {
    if (!result || selected.length === 0) return;
    setBusy(true); setError(null);
    try {
      const selectedRows = result.work_orders.filter((item) => selected.includes(item.work_order_id));
      const created = await createWorkset({
        name: `${result.original_query.slice(0, 22)}工作集`,
        original_query: result.original_query,
        query_snapshot: result.compiled_query,
        work_order_ids: selected,
        cluster_ids: [...new Set(selectedRows.flatMap((item) => item.cluster_ids))],
      });
      setWorkset(created);
    } catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };

  const makeDashboard = async () => {
    const ids = workset?.work_order_ids ?? selected;
    const clusters = workset?.cluster_ids ?? result?.cluster_ids ?? [];
    if (ids.length === 0) return;
    setBusy(true); setError(null);
    try { setDashboard(await generateAgentDashboard({ title: "当前查询临时看板", work_order_ids: ids, cluster_ids: clusters })); }
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
    try {
      await executeWorksetAction(workset.id, { preview_id: preview.preview_id });
      setPreview(null);
      await ask("只看正在跟进的");
    } catch (cause) { setError(describeApiError(cause)); }
    finally { setBusy(false); }
  };

  return (
    <section className="assistant-page">
      <header className="assistant-hero">
        <p className="eyebrow">智能研判助手</p>
        <h1>问问 12345 工单</h1>
        <p>用一句自然语言查询真实工单，形成可核查证据、工作集与后续批量业务操作。</p>
        <div className="assistant-query-box">
          <textarea value={input} onChange={(event) => setInput(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void ask(); } }} placeholder="例如：最近有哪些工程款拖欠相关工单？" aria-label="自然语言工单查询" />
          <div className="assistant-query-box__footer"><span>Ctrl / ⌘ + Enter 提交</span><button className="btn btn--primary" onClick={() => void ask()} disabled={busy}>{busy ? "正在研判…" : "开始研判"}</button></div>
        </div>
        <div className="assistant-examples">{EXAMPLES.map((example) => <button key={example} onClick={() => void ask(example)} disabled={busy}>{example}</button>)}</div>
      </header>

      {error ? <div className="assistant-alert assistant-alert--error">{error}</div> : null}
      {result ? <div className="assistant-layout">
        <div className="assistant-results">
          <div className="assistant-answer">
            <span className="assistant-answer__mark">研判结论</span>
            <p>{result.answer}</p><small>{result.disclaimer}</small>
          </div>
          <div className="assistant-metrics">
            <div><span>相关工单</span><strong>{result.total}</strong></div>
            <div><span>多频事件</span><strong>{result.cluster_ids.length}</strong></div>
            <div><span>查询方式</span><strong>{result.planner_mode === "llm" ? "AI 规划" : "受控规则"}</strong></div>
          </div>
          <div className="assistant-group-grid"><div className="assistant-group"><h2>主要问题</h2>{groupList(result.topic_groups)}</div><div className="assistant-group"><h2>处理状态</h2>{groupList(result.handling_groups)}</div></div>
          <div className="assistant-results-head"><div><h2>真实工单</h2><p>已选择 {selected.length} / {result.work_orders.length} 条</p></div><div className="assistant-results-head__actions"><button className="btn btn--secondary" onClick={() => setSelected(allSelected ? [] : result.work_orders.map((item) => item.work_order_id))}>{allSelected ? "取消全选" : "全选"}</button><button className="btn btn--primary" onClick={() => void addToWorkset()} disabled={busy || selected.length === 0}>加入工作集</button><button className="btn btn--secondary" onClick={() => void makeDashboard()} disabled={busy || selected.length === 0}>生成看板</button></div></div>
          <div className="assistant-cards">{result.work_orders.map((item) => <article className="assistant-card" key={item.work_order_id}><label className="assistant-card__select"><input type="checkbox" checked={selected.includes(item.work_order_id)} onChange={() => toggle(item.work_order_id)} /><span>选择</span></label><div className="assistant-card__body"><div className="assistant-card__top"><span className="assistant-card__number">{item.external_work_order_number ?? "未提供工单号"}</span><span className={`assistant-status assistant-status--${item.handling_status}`}>{statusLabel[item.handling_status] ?? item.handling_status}</span></div><h3>{item.title ?? "未提供标题"}</h3><p>{item.normalized_summary ?? "当前 V2 未生成事件摘要。"}</p><div className="assistant-card__meta"><span>{item.location ?? "地点未解析"}</span><span>{item.event_type ?? "事件类型未归类"}</span>{item.is_multi_frequency ? <span>关联多频事件</span> : null}</div><div className="assistant-card__evidence">{item.retrieval_evidence.map((evidence) => <span key={evidence}>{evidence}</span>)}</div></div><div className="assistant-card__links"><Link to={`/work-orders/${item.work_order_id}`}>查看工单 →</Link>{item.cluster_ids[0] ? <Link to={`/events/${item.cluster_ids[0]}`}>查看多频事件 →</Link> : null}</div></article>)}</div>
        </div>
        <aside className="assistant-side">
          <div className="assistant-side-card"><p className="eyebrow">当前工作集</p>{workset ? <><h2>{workset.name}</h2><p>已持久化 {workset.result_count} 条工单，可在后续流程继续使用。</p><button className="btn btn--primary btn--block" onClick={() => void requestPreview()} disabled={busy}>批量设为正在跟进</button></> : <><h2>尚未创建工作集</h2><p>选择查询结果后加入工作集，才能进行批量业务操作。</p></>}</div>
          {preview ? <div className="assistant-side-card assistant-confirm"><p className="eyebrow">执行前确认</p><h2>准备处理 {preview.affected_work_order_count} 条</h2><p>{preview.message}</p><div className="assistant-confirm__actions"><button className="btn btn--secondary" onClick={() => setPreview(null)}>取消</button><button className="btn btn--primary" onClick={() => void confirmAction()} disabled={busy}>确认执行</button></div></div> : null}
          {dashboard ? <div className="assistant-side-card assistant-dashboard"><p className="eyebrow">动态临时看板</p><h2>{dashboard.title}</h2><div className="assistant-dashboard__numbers"><span><strong>{dashboard.work_order_count}</strong>相关工单</span><span><strong>{dashboard.multi_frequency_event_count}</strong>多频事件</span></div><h3>主要问题</h3>{groupList(dashboard.topic_groups)}<h3>主要地点</h3>{groupList(dashboard.location_groups)}<p className="text-muted">{dashboard.disclaimer}</p></div> : null}
        </aside>
      </div> : null}
    </section>
  );
}
