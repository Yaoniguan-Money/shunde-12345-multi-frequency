import { useRef } from "react";
import type { JSX } from "react";
import { useGSAP } from "@gsap/react";
import { gsap } from "gsap";

import type { AgentTopicGroup } from "../types/api";

gsap.registerPlugin(useGSAP);

export type MetricTone = "blue" | "orange" | "red" | "green" | "slate";

export function MetricCard({ label, value, tone, detail }: {
  label: string; value: number; tone: MetricTone; detail: string;
}): JSX.Element {
  const root = useRef<HTMLElement>(null);
  useGSAP(() => {
    const number = root.current?.querySelector<HTMLElement>("[data-count]");
    if (!number) return undefined;
    const state = { value: 0 };
    const media = gsap.matchMedia();
    media.add({ all: "(min-width: 0px)", reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
      gsap.to(state, {
        value,
        duration: context.conditions?.reduceMotion ? 0 : 0.65,
        ease: "power2.out",
        onUpdate: () => { number.textContent = String(Math.round(state.value)); },
      });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [value], revertOnUpdate: true });

  return <article ref={root} className={`insight-metric insight-metric--${tone}`}>
    <span>{label}</span><strong data-count>0</strong><small>{detail}</small>
  </article>;
}

export function AnimatedBarChart({ title, items, onSelect, activeLabel, emptyMessage }: {
  title: string;
  items: AgentTopicGroup[];
  onSelect: (label: string) => void;
  activeLabel?: string | null;
  emptyMessage: string;
}): JSX.Element {
  const root = useRef<HTMLElement>(null);
  const max = Math.max(...items.map((item) => item.count), 1);
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ all: "(min-width: 0px)", reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
      gsap.fromTo(".animated-bar-chart__fill", { scaleX: 0 }, {
        scaleX: 1,
        duration: context.conditions?.reduceMotion ? 0 : 0.65,
        ease: "power2.out",
        stagger: 0.07,
        transformOrigin: "left center",
      });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [items.map((item) => `${item.label}:${item.count}`).join("|")], revertOnUpdate: true });

  return <section ref={root} className="insight-chart" aria-label={title}>
    <div className="insight-chart__head"><h3>{title}</h3><span>点击下钻</span></div>
    {items.length === 0 ? <p className="insight-chart__empty">{emptyMessage}</p> : <div className="animated-bar-chart">
      {items.slice(0, 8).map((item) => <button key={item.label} className={`animated-bar-chart__row ${activeLabel === item.label ? "is-active" : ""}`} onClick={() => onSelect(item.label)} title={`${item.label}：${item.count} 条`}>
        <span className="animated-bar-chart__label">{item.label}</span><span className="animated-bar-chart__track"><i className="animated-bar-chart__fill" style={{ width: `${(item.count / max) * 100}%` }} /></span><b>{item.count}</b>
      </button>)}
    </div>}
  </section>;
}

const STATUS_COLORS: Record<string, string> = { unhandled: "#dd7b19", investigating: "#2467c8", resolved: "#20845a" };

export function AnimatedDonutChart({ items, activeLabel, onSelect }: {
  items: AgentTopicGroup[]; activeLabel?: string | null; onSelect: (label: string) => void;
}): JSX.Element {
  const root = useRef<HTMLElement>(null);
  const total = items.reduce((sum, item) => sum + item.count, 0);
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  let progress = 0;
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ all: "(min-width: 0px)", reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
      gsap.fromTo(".animated-donut__segment", { strokeDashoffset: circumference }, {
        strokeDashoffset: 0,
        duration: context.conditions?.reduceMotion ? 0 : 0.7,
        ease: "power2.out",
        stagger: 0.09,
      });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [items.map((item) => `${item.label}:${item.count}`).join("|")], revertOnUpdate: true });

  return <section ref={root} className="insight-chart insight-chart--donut" aria-label="办理状态分布">
    <div className="insight-chart__head"><h3>办理状态</h3><span>点击下钻</span></div>
    {total === 0 ? <p className="insight-chart__empty">当前范围内暂无可统计的办理状态。</p> : <div className="animated-donut">
      <svg viewBox="0 0 120 120" role="img" aria-label={`${total} 条当前工单`}>
        <circle cx="60" cy="60" r={radius} className="animated-donut__base" />
        {items.map((item) => {
          const length = (item.count / total) * circumference;
          const offset = -progress * circumference;
          progress += item.count / total;
          return <circle key={item.label} className={`animated-donut__segment ${activeLabel === item.label ? "is-active" : ""}`} cx="60" cy="60" r={radius} stroke={STATUS_COLORS[item.label] ?? "#6d7d90"} strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={offset} onClick={() => onSelect(item.label)} />;
        })}
      </svg>
      <div className="animated-donut__center"><strong>{total}</strong><span>当前工单</span></div>
      <div className="animated-donut__legend">{items.map((item) => <button key={item.label} onClick={() => onSelect(item.label)}><i style={{ backgroundColor: STATUS_COLORS[item.label] ?? "#6d7d90" }} />{item.label === "unhandled" ? "未处理" : item.label === "investigating" ? "正在跟进" : item.label === "resolved" ? "已解决" : item.label}<b>{item.count}</b></button>)}</div>
    </div>}
  </section>;
}

export function StackedStatusBar({ items }: { items: AgentTopicGroup[] }): JSX.Element {
  const root = useRef<HTMLDivElement>(null);
  const total = items.reduce((sum, item) => sum + item.count, 0);
  useGSAP(() => {
    const media = gsap.matchMedia();
    media.add({ all: "(min-width: 0px)", reduceMotion: "(prefers-reduced-motion: reduce)" }, (context) => {
      gsap.fromTo(".stacked-status-bar__segment", { scaleX: 0 }, { scaleX: 1, transformOrigin: "left center", duration: context.conditions?.reduceMotion ? 0 : 0.55, ease: "power2.out", stagger: 0.08 });
    });
    return () => media.revert();
  }, { scope: root, dependencies: [items.map((item) => `${item.label}:${item.count}`).join("|")], revertOnUpdate: true });
  return <div ref={root} className="stacked-status-wrap">
    <div className="stacked-status-bar" aria-label="工作集办理状态分布">{items.map((item) => <span key={item.label} className={`stacked-status-bar__segment stacked-status-bar__segment--${item.label}`} style={{ width: `${total ? (item.count / total) * 100 : 0}%` }} title={`${item.label} ${item.count}`} />)}</div>
    <div className="stacked-status-bar__legend">{items.map((item) => <span key={item.label}><i className={`stacked-status-bar__dot stacked-status-bar__dot--${item.label}`} />{item.label === "unhandled" ? "未处理" : item.label === "investigating" ? "正在跟进" : "已解决"} <b>{item.count}</b></span>)}</div>
  </div>;
}
