import { useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";

import type { AgentWorkOrderResult } from "../types/api";

gsap.registerPlugin(useGSAP);

export type TreeMode = "topic" | "location" | "status";

const statusName: Record<string, string> = { unhandled: "未处理", investigating: "正在跟进", resolved: "已解决" };

function keyFor(item: AgentWorkOrderResult, mode: TreeMode): string {
  if (mode === "topic") return item.event_type ?? "未归类";
  if (mode === "location") return item.location ?? "未提供地点";
  return statusName[item.handling_status] ?? item.handling_status;
}

function childKeyFor(item: AgentWorkOrderResult, mode: TreeMode): string {
  if (mode === "topic") return item.location ?? "未提供地点";
  if (mode === "location") return item.event_type ?? "未归类";
  return item.event_type ?? "未归类";
}

export function InsightTree({ items, mode, onSelect }: {
  items: AgentWorkOrderResult[];
  mode: TreeMode;
  onSelect: (dimension: "topic" | "location" | "status", value: string) => void;
}): JSX.Element {
  const root = useRef<HTMLElement>(null);
  const groups = useMemo(() => {
    const grouped = new Map<string, Map<string, AgentWorkOrderResult[]>>();
    items.forEach((item) => {
      const key = keyFor(item, mode);
      const child = childKeyFor(item, mode);
      const inner = grouped.get(key) ?? new Map<string, AgentWorkOrderResult[]>();
      inner.set(child, [...(inner.get(child) ?? []), item]);
      grouped.set(key, inner);
    });
    return [...grouped.entries()].sort((a, b) => [...b[1].values()].flat().length - [...a[1].values()].flat().length).slice(0, 6);
  }, [items, mode]);
  const [open, setOpen] = useState<string | null>(groups[0]?.[0] ?? null);
  const primaryDimension = mode === "topic" ? "topic" : mode === "location" ? "location" : "status";
  const childDimension = mode === "topic" ? "location" : "topic";
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ all: "(min-width: 0px)", reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
      gsap.fromTo(".insight-tree__children", { autoAlpha: 0, y: -8 }, {
        autoAlpha: 1,
        y: 0,
        duration: context.conditions?.reduceMotion ? 0 : 0.3,
        ease: "power2.out",
        clearProps: "visibility",
      });
      gsap.fromTo(".insight-tree__connectors path", { strokeDashoffset: 38 }, {
        strokeDashoffset: 0,
        duration: context.conditions?.reduceMotion ? 0 : 0.42,
        stagger: 0.04,
        ease: "power1.out",
      });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [mode, open], revertOnUpdate: true });

  return <section ref={root} className="insight-tree" aria-label="工单关系树">
    <div className="insight-tree__title"><div><span>关系结构</span><h2>工单关系树</h2></div><p>{mode === "topic" ? "问题 → 地点 → 工单" : mode === "location" ? "地点 → 问题 → 工单" : "状态 → 问题 → 工单"}</p></div>
    {groups.length === 0 ? <div className="insight-tree__empty"><strong>当前范围内暂无关系节点</strong><p>查询返回工单后，这里会基于真实问题、地点和状态建立可下钻结构。</p></div> : <div className="insight-tree__canvas">
      <svg className="insight-tree__connectors" viewBox={`0 0 940 ${Math.max(260, groups.length * 132)}`} preserveAspectRatio="none" aria-hidden="true">
        {groups.map((_, index) => <path key={index} d={`M26 ${index * 132 + 34} C 65 ${index * 132 + 34}, 72 ${index * 132 + 48}, 112 ${index * 132 + 48} M290 ${index * 132 + 48} C 340 ${index * 132 + 48}, 350 ${index * 132 + 82}, 395 ${index * 132 + 82}`} />)}
      </svg>
      <div className="insight-tree__root">当前查询<span>{items.length}</span></div>
      <div className="insight-tree__groups">{groups.map(([label, children]) => {
        const total = [...children.values()].flat().length;
        const urgent = [...children.values()].flat().filter((item) => item.is_urgent).length;
        const multi = [...children.values()].flat().filter((item) => item.is_multi_frequency).length;
        const expanded = open === label;
        return <div className={`insight-tree__group ${expanded ? "is-open" : ""}`} key={label}>
          <button className="insight-tree__node" onClick={() => { setOpen(expanded ? null : label); onSelect(primaryDimension, label); }}><span>{label}</span><b>{total}</b><small>{urgent ? `急 ${urgent}` : "无急单"} · {multi ? `多频 ${multi}` : "暂未多频"}</small></button>
          {expanded ? <div className="insight-tree__children">{[...children.entries()].sort((a, b) => b[1].length - a[1].length).slice(0, 4).map(([child, workOrders]) => <div className="insight-tree__branch" key={child}><button onClick={() => onSelect(childDimension, child)}><span>{child}</span><b>{workOrders.length}</b></button><div>{workOrders.slice(0, 3).map((item) => <button className="insight-tree__leaf" key={item.work_order_id} onClick={() => onSelect("topic", item.event_type ?? "未归类")}>{item.external_work_order_number ?? "工单"} · {item.title ?? "未提供标题"}</button>)}</div></div>)}</div> : null}
        </div>;
      })}</div>
    </div>}
  </section>;
}
