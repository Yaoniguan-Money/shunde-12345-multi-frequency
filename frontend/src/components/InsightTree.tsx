import { useRef, useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";

import type { AgentTreeGroup } from "../types/api";

gsap.registerPlugin(useGSAP);

export type TreeMode = "topic" | "location" | "status";

export function InsightTree({ groups: suppliedGroups, mode, total, onSelect }: {
  groups: AgentTreeGroup[];
  mode: TreeMode;
  total: number;
  onSelect: (dimension: "topic" | "location" | "status", value: string) => void;
}): JSX.Element {
  const groups = suppliedGroups ?? [];
  const root = useRef<HTMLElement>(null);
  const [open, setOpen] = useState<string | null>(groups[0]?.label ?? null);
  const [showAllGroups, setShowAllGroups] = useState(false);
  const primaryDimension = mode === "topic" ? "topic" : mode === "location" ? "location" : "status";
  const childDimension = mode === "topic" ? "location" : "topic";
  const visibleGroups = showAllGroups ? groups : groups.slice(0, 6);

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
      <div className="insight-tree__groups">{visibleGroups.map((group) => {
        const expanded = open === group.label;
        return <div className={`insight-tree__group ${expanded ? "is-open" : ""}`} key={group.label}>
          <button className="insight-tree__node" onClick={() => { setOpen(expanded ? null : group.label); onSelect(primaryDimension, group.label); }}><span>{group.label}</span><b>{group.count}</b><small>{group.urgent_count ? `急 ${group.urgent_count}` : "无急单"} · {group.multi_frequency_count ? `多频 ${group.multi_frequency_count}` : "暂未多频"}</small></button>
          {expanded ? <div className="insight-tree__children">{group.children.map((child) => <div className="insight-tree__branch" key={child.label}><button onClick={() => onSelect(childDimension, child.label)}><span>{child.label}</span><b>{child.count}</b></button><div>{child.work_orders.map((item) => <Link className="insight-tree__leaf" key={item.work_order_id} to={`/work-orders/${item.work_order_id}`}>{item.external_work_order_number ?? "工单"} · {item.title ?? "未提供标题"}</Link>)}<button className="insight-tree__all" onClick={() => onSelect(childDimension, child.label)}>查看全部 {child.count} 条 →</button></div></div>)}</div> : null}
        </div>;
      })}{groups.length > 6 ? <button className="insight-tree__all insight-tree__all--groups" onClick={() => setShowAllGroups((value) => !value)}>{showAllGroups ? "收起分类" : `展开全部（显示 6 / 共 ${groups.length} 类）`}</button> : null}</div>
    </div>}
  </section>;
}
