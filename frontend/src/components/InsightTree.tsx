import { useEffect, useRef, useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";

import type { AgentHandlingStatus, AgentTreeGroup } from "../types/api";

gsap.registerPlugin(useGSAP);

export type TreeMode = "topic" | "location" | "status";
export type TreeSelection = { topic?: string; location?: string; status?: AgentHandlingStatus };

type TreeDimension = "topic" | "location" | "status";
type VisibleTreeGroup = Omit<AgentTreeGroup, "children"> & {
  displayLabel: string;
  children: Array<AgentTreeGroup["children"][number] & { displayLabel: string }>;
};

export function InsightTree({ groups: suppliedGroups, mode, total, onSelect, displayLabel }: {
  groups: AgentTreeGroup[];
  mode: TreeMode;
  total: number;
  onSelect: (selection: TreeSelection) => void;
  displayLabel?: (dimension: TreeDimension, label: string) => string | null;
}): JSX.Element {
  const dimensions: readonly [TreeDimension, TreeDimension] = mode === "topic" ? ["topic", "location"] : mode === "location" ? ["location", "topic"] : ["status", "topic"];
  const groups: VisibleTreeGroup[] = (suppliedGroups ?? []).flatMap((group) => {
    const label = displayLabel ? displayLabel(dimensions[0], group.label) : group.label;
    if (!label) return [];
    const children = group.children.flatMap((child) => {
      const childLabel = displayLabel ? displayLabel(dimensions[1], child.label) : child.label;
      return childLabel ? [{ ...child, displayLabel: childLabel }] : [];
    });
    return children.length ? [{ ...group, displayLabel: label, children }] : [];
  });
  const root = useRef<HTMLElement>(null);
  const [open, setOpen] = useState<string | null>(groups[0]?.label ?? null);
  const selectionFor = (primary: string, child?: string): TreeSelection => {
    if (mode === "topic") return { topic: primary, ...(child ? { location: child } : {}) };
    if (mode === "location") return { location: primary, ...(child ? { topic: child } : {}) };
    return { status: primary as AgentHandlingStatus, ...(child ? { topic: child } : {}) };
  };

  useEffect(() => {
    setOpen((current) => current ?? groups[0]?.label ?? null);
  }, [groups]);

  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ all: "(min-width: 0px)", reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
      gsap.fromTo(".insight-tree__children", { autoAlpha: 0, y: -8 }, {
        autoAlpha: 1, y: 0, duration: context.conditions?.reduceMotion ? 0 : 0.3,
        ease: "power2.out", clearProps: "visibility",
      });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [mode, open], revertOnUpdate: true });

  return <section ref={root} className="insight-tree" aria-label="完整查询范围工单关系树">
    <div className="insight-tree__title"><div><span>完整范围关系</span><h2>工单关系树</h2></div><p>{mode === "topic" ? "问题 → 地点 → 工单" : mode === "location" ? "地点 → 问题 → 工单" : "状态 → 问题 → 工单"}</p></div>
    {groups.length === 0 ? <div className="insight-tree__empty"><strong>当前范围内暂无关系节点</strong><p>查询返回工单后，这里会基于真实问题、地点和状态建立可下钻结构。</p></div> : <div className="insight-tree__canvas">
      <div className="insight-tree__root">当前查询<span>{total}</span></div>
      <div className="insight-tree__groups">{groups.map((group) => {
        const expanded = open === group.label;
        return <div className={`insight-tree__group ${expanded ? "is-open" : ""}`} key={group.label}>
          <button className="insight-tree__node" onClick={() => { setOpen(expanded ? null : group.label); onSelect(selectionFor(group.label)); }}><span>{group.displayLabel}</span><b>{group.count}</b><small>{group.urgent_count ? `急 ${group.urgent_count}` : "无急单"} · {group.multi_frequency_count ? `多频 ${group.multi_frequency_count}` : "暂未多频"}</small></button>
          {expanded ? <div className="insight-tree__children">{group.children.map((child) => <div className="insight-tree__branch" key={child.label}><button onClick={() => onSelect(selectionFor(group.label, child.label))}><span>{child.displayLabel}</span><b>{child.count}</b></button><div>{child.work_orders.map((item) => <Link className="insight-tree__leaf" key={item.work_order_id} to={`/work-orders/${item.work_order_id}`} state={{ fromAssistant: true }}>{item.external_work_order_number ?? "工单"} · {item.title ?? "未提供标题"}</Link>)}<button className="insight-tree__all" onClick={() => onSelect(selectionFor(group.label, child.label))}>查看全部 {child.count} 条 →</button></div></div>)}</div> : null}
        </div>;
      })}</div>
    </div>}
  </section>;
}
