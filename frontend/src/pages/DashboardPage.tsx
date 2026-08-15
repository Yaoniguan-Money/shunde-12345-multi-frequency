import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import type { JSX } from "react";

import { listWorkOrders, listClusters, listEvents } from "../api/catalog";
import { MiniLineChart, DonutChart, TrendMiniChart } from "../components/Charts";

const WELCOME_BAR_STYLE: React.CSSProperties = {
  background: "linear-gradient(135deg, #1e6dff 0%, #3b82f6 100%)",
  borderRadius: "var(--radius-lg)",
  padding: "24px 28px",
  color: "#fff",
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  marginBottom: "20px",
  boxShadow: "0 4px 16px rgba(37,99,235,0.25)",
};

const PANEL_CARD_STYLE: React.CSSProperties = {
  background: "var(--color-surface)",
  borderRadius: "var(--radius-lg)",
  border: "1px solid var(--color-border)",
  boxShadow: "var(--shadow-card)",
  padding: "20px",
};

const STATS_GRID_STYLE: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, 1fr)",
  gap: "16px",
  marginBottom: "20px",
};

const STAT_CARD_STYLE: React.CSSProperties = {
  background: "var(--color-surface)",
  borderRadius: "var(--radius-lg)",
  border: "1px solid var(--color-border)",
  boxShadow: "var(--shadow-card)",
  padding: "20px",
  display: "flex",
  alignItems: "center",
  gap: "16px",
  transition: "box-shadow 0.2s",
};

const THREE_COL_STYLE: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1.2fr 1fr 1fr",
  gap: "20px",
  marginBottom: "20px",
};

const RADAR_GRID_STYLE: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: "12px",
};

const AI_FLOW_STYLE: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "4px",
  marginBottom: "20px",
  padding: "12px 0",
};

const TAG_SUCCESS_STYLE: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "2px 10px",
  borderRadius: "var(--radius-pill)",
  fontSize: "12px",
  background: "var(--color-success-bg)",
  color: "var(--color-success)",
  border: "1px solid var(--color-success-light)",
  fontWeight: 500,
};

const BTN_PRIMARY_STYLE: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  gap: "6px",
  padding: "9px 22px",
  borderRadius: "var(--radius-md)",
  fontSize: "14px",
  fontWeight: 500,
  background: "#fff",
  color: "#2563eb",
  border: "none",
  cursor: "pointer",
  transition: "all 0.15s",
};

const TOGGLE_BTN_ACTIVE: React.CSSProperties = {
  padding: "5px 14px",
  borderRadius: "var(--radius-md)",
  fontSize: "12px",
  fontWeight: 500,
  background: "var(--color-primary)",
  color: "#fff",
  border: "1px solid var(--color-primary)",
  cursor: "pointer",
};

const TOGGLE_BTN_INACTIVE: React.CSSProperties = {
  padding: "5px 14px",
  borderRadius: "var(--radius-md)",
  fontSize: "12px",
  fontWeight: 500,
  background: "var(--color-surface)",
  color: "var(--color-text-secondary)",
  border: "1px solid var(--color-border)",
  cursor: "pointer",
};

function formatNumber(n: number): string {
  if (n >= 10000) return (n / 10000).toFixed(1) + "w";
  if (n >= 1000) return (n / 1000).toFixed(1) + "k";
  return String(n);
}

function formatUpdateTime(): string {
  const now = new Date();
  const h = String(now.getHours()).padStart(2, "0");
  const m = String(now.getMinutes()).padStart(2, "0");
  return `更新于 ${h}:${m}`;
}

interface RadarItem {
  name: string;
  count: number;
  percent: number;
  isSimulated?: boolean;
}

interface ActivityItem {
  id: number;
  color: "red" | "blue" | "green" | "orange";
  time: string;
  title: string;
  desc: string;
}

interface FlowStep {
  num: number;
  name: string;
  status: "done" | "running";
}

interface RecentRecord {
  time: string;
  desc: string;
}

const SIMULATED_RADAR: RadarItem[] = [
  { name: "噪音扰民", count: 42, percent: 80, isSimulated: true },
  { name: "占道经营", count: 28, percent: 55, isSimulated: true },
  { name: "违规搭建", count: 19, percent: 38, isSimulated: true },
  { name: "环境卫生", count: 35, percent: 68, isSimulated: true },
  { name: "交通秩序", count: 24, percent: 48, isSimulated: true },
  { name: "治安问题", count: 11, percent: 22, isSimulated: true },
];

const FLOW_STEPS: FlowStep[] = [
  { num: 1, name: "工单导入", status: "done" },
  { num: 2, name: "语义理解", status: "done" },
  { num: 3, name: "事件抽取", status: "done" },
  { num: 4, name: "相似度匹配", status: "running" },
  { num: 5, name: "聚类研判", status: "done" },
];

const RECENT_RECORDS: RecentRecord[] = [
  { time: "3分钟前", desc: "完成12条工单研判，发现2个高频事件" },
  { time: "15分钟前", desc: "导入批次#20260414001共500条" },
  { time: "32分钟前", desc: "噪音扰民聚类簇新增5条关联工单" },
  { time: "1小时前", desc: "占道经营事件完成相似度匹配" },
  { time: "2小时前", desc: "系统自动巡检完成，无异常" },
];

const ACTIVITIES: ActivityItem[] = [
  { id: 1, color: "red", time: "5分钟前", title: "新高频事件预警", desc: "大良街道近3日噪音扰民投诉激增，已触发高频聚类" },
  { id: 2, color: "green", time: "18分钟前", title: "新工单导入成功", desc: "批次#20260415003共328条工单已入库，等待AI研判" },
  { id: 3, color: "blue", time: "45分钟前", title: "高频事件已处理", desc: "容桂街道占道经营事件簇已派发至城管部门跟进" },
  { id: 4, color: "orange", time: "1小时前", title: "待关注事件提醒", desc: "伦教街道违规搭建投诉近一周持续上升，建议关注" },
  { id: 5, color: "red", time: "2小时前", title: "新高频事件确认", desc: "北滘镇环境卫生问题AI研判确认为高频事件，置信度96%" },
  { id: 6, color: "green", time: "3小时前", title: "数据同步完成", desc: "与12345热线系统数据同步完成，新增工单215条" },
  { id: 7, color: "blue", time: "4小时前", title: "研判任务完成", desc: "批量研判任务完成，共处理工单856条，生成事件1243个" },
  { id: 8, color: "orange", time: "5小时前", title: "相似度计算更新", desc: "AI模型相似度匹配算法已更新至v2.3版本，准确率提升2.1%" },
];

const TREND_DATA_7D = {
  data: [35, 42, 38, 55, 48, 62, 58],
  labels: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"],
  stats: { total: 338, avg: 48.3, peak: "周五62条" },
};

const TREND_DATA_30D = {
  data: [28, 32, 35, 42, 38, 45, 50, 48, 52, 55, 48, 60, 58, 62, 55, 48, 52, 58, 65, 70, 62, 58, 55, 68, 72, 65, 60, 58, 62, 68],
  labels: Array.from({ length: 30 }, (_, i) => `${i + 1}日`),
  stats: { total: 1682, avg: 56.1, peak: "28日72条" },
};

const TREND_DATA_90D = {
  data: Array.from({ length: 90 }, (_, i) => Math.round(40 + Math.sin(i / 8) * 15 + Math.random() * 10 + i / 20)),
  labels: Array.from({ length: 90 }, (_, i) => `${i + 1}日`),
  stats: { total: 4856, avg: 54.0, peak: "第82日78条" },
};

function WelcomeBar(): JSX.Element {
  const navigate = useNavigate();
  const [time, setTime] = useState(formatUpdateTime());

  useEffect(() => {
    const timer = setInterval(() => setTime(formatUpdateTime()), 60000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div style={WELCOME_BAR_STYLE}>
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 6, letterSpacing: "0.5px" }}>
          顺德12345多频工单智能研判系统
        </h1>
        <p style={{ fontSize: 14, opacity: 0.9, margin: 0 }}>
          欢迎回来，今日系统运行正常
        </p>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        <span style={{ fontSize: 13, opacity: 0.85 }}>{time}</span>
        <button
          style={BTN_PRIMARY_STYLE}
          onClick={() => navigate("/imports")}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "#eff6ff";
            e.currentTarget.style.transform = "translateY(-1px)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "#fff";
            e.currentTarget.style.transform = "translateY(0)";
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
          立即研判
        </button>
      </div>
    </div>
  );
}

interface StatCardProps {
  label: string;
  value: number | string;
  valueColor: string;
  chartData: number[];
  chartColor: "blue" | "orange" | "green";
  hint: string;
  hintType: "up" | "highlight" | "stable";
  unit?: string;
  loading?: boolean;
  subLabel?: string;
}

function StatCard({ label, value, valueColor, chartData, chartColor, hint, hintType, unit, loading }: StatCardProps): JSX.Element {
  const hintStyle: React.CSSProperties = {
    fontSize: 12,
    marginTop: 4,
    display: "flex",
    alignItems: "center",
    gap: 4,
    color: hintType === "highlight" ? "var(--color-danger)" : "var(--color-success)",
    fontWeight: hintType === "highlight" ? 600 : 500,
  };

  return (
    <div style={STAT_CARD_STYLE} className="stat-card-hover">
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--color-text-muted)", marginBottom: 6 }}>{label}</div>
        {loading ? (
          <div style={{ width: 80, height: 32, background: "var(--color-surface-soft)", borderRadius: "var(--radius-sm)", animation: "skeleton-loading 1.5s infinite" }} />
        ) : (
          <div style={{ fontSize: 30, fontWeight: 700, color: valueColor, lineHeight: 1.2, letterSpacing: "-0.5px" }}>
            {typeof value === "number" ? formatNumber(value) : value}
            {unit && <span style={{ fontSize: 14, fontWeight: 500, color: "var(--color-text-muted)", marginLeft: 4 }}>{unit}</span>}
          </div>
        )}
        <div style={hintStyle}>
          {hintType !== "highlight" && (
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          )}
          {hint}
        </div>
      </div>
      <div style={{ flexShrink: 0 }}>
        <MiniLineChart data={chartData} color={chartColor} width={120} height={56} />
      </div>
    </div>
  );
}

function RadarCell({ item }: { item: RadarItem }): JSX.Element {
  const barColor = item.percent > 60 ? "#ef4444" : item.percent > 40 ? "#f97316" : "#3b82f6";
  return (
    <div style={{
      padding: "12px 14px",
      background: "var(--color-surface-soft)",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--color-divider)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--color-text-primary)" }}>{item.name}</span>
        <span style={{ fontSize: 16, fontWeight: 700, color: "var(--color-text-primary)" }}>{item.count}</span>
      </div>
      <div style={{ height: 6, background: "var(--color-divider)", borderRadius: "var(--radius-pill)", overflow: "hidden" }}>
        <div style={{
          height: "100%",
          width: `${item.percent}%`,
          background: barColor,
          borderRadius: "var(--radius-pill)",
          transition: "width 0.5s ease",
        }} />
      </div>
      {item.isSimulated && (
        <div style={{ fontSize: 10, color: "var(--color-text-faint)", marginTop: 4 }}>模拟数据</div>
      )}
    </div>
  );
}

function PanelHeader({ title, right }: { title: JSX.Element | string; right?: JSX.Element }): JSX.Element {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "space-between",
      marginBottom: 16,
      paddingBottom: 12,
      borderBottom: "1px solid var(--color-divider)",
    }}>
      <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--color-text-primary)", margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
        {title}
      </h3>
      {right}
    </div>
  );
}

function EventRadarPanel(): JSX.Element {
  const clustersQuery = useQuery({
    queryKey: ["clusters-radar"],
    queryFn: ({ signal }) => listClusters({ offset: 0, limit: 100, signal }),
    retry: 1,
    staleTime: 30000,
  });

  const radarItems: RadarItem[] = SIMULATED_RADAR;

  return (
    <div style={PANEL_CARD_STYLE}>
      <PanelHeader
        title={<>🔍 事件雷达</>}
        right={<span style={TAG_SUCCESS_STYLE}>● 实时监控</span>}
      />
      <div style={RADAR_GRID_STYLE}>
        {radarItems.map((item) => (
          <RadarCell key={item.name} item={item} />
        ))}
      </div>
    </div>
  );
}

function AIFlowPanel(): JSX.Element {
  return (
    <div style={PANEL_CARD_STYLE}>
      <PanelHeader title={<>🤖 AI研判流程</>} />
      <div style={AI_FLOW_STYLE}>
        {FLOW_STEPS.map((step, idx) => (
          <div key={step.num} style={{ display: "flex", alignItems: "center", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flex: 1 }}>
              <div style={{
                width: 44,
                height: 44,
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 18,
                fontWeight: 700,
                color: "#fff",
                background: step.status === "done"
                  ? "var(--color-success)"
                  : "var(--color-primary)",
                boxShadow: step.status === "running"
                  ? "0 0 0 4px rgba(37,99,235,0.2)"
                  : "none",
                animation: step.status === "running" ? "pulse-dot 1.4s ease-in-out infinite" : "none",
              }}>
                {step.status === "done" ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  step.num
                )}
              </div>
              <span style={{ fontSize: 12, color: "var(--color-text-secondary)", fontWeight: 500, textAlign: "center" }}>{step.name}</span>
              <span style={{
                fontSize: 11,
                color: step.status === "done" ? "var(--color-success)" : "var(--color-primary)",
                fontWeight: 500,
              }}>
                {step.status === "done" ? "已完成" : "进行中"}
              </span>
            </div>
            {idx < FLOW_STEPS.length - 1 && (
              <div style={{
                width: 24,
                height: 2,
                background: step.status === "done" ? "var(--color-success)" : "var(--color-border)",
                marginBottom: 28,
                flexShrink: 0,
              }} />
            )}
          </div>
        ))}
      </div>
      <div style={{ borderTop: "1px solid var(--color-divider)", paddingTop: 16 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-secondary)", marginBottom: 10 }}>最近研判记录</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {RECENT_RECORDS.map((rec, i) => (
            <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
              <span style={{ fontSize: 11, color: "var(--color-text-faint)", minWidth: 60, paddingTop: 1 }}>{rec.time}</span>
              <span style={{ fontSize: 12, color: "var(--color-text-secondary)", lineHeight: 1.5 }}>{rec.desc}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DistributionPanel(): JSX.Element {
  const highFreq = 22;
  const midFreq = 45;
  const lowFreq = 33;
  const highCount = 28;

  const segments = [
    { value: highFreq, color: "#f97316", label: "高频事件" },
    { value: midFreq, color: "#3b82f6", label: "中频事件" },
    { value: lowFreq, color: "#94a3b8", label: "单次事件" },
  ];

  const legendData = [
    { color: "#f97316", label: "高频事件", value: highCount, pct: `${highFreq}%` },
    { color: "#3b82f6", label: "中频事件", value: Math.round(highCount * midFreq / highFreq), pct: `${midFreq}%` },
    { color: "#94a3b8", label: "单次事件", value: Math.round(highCount * lowFreq / highFreq), pct: `${lowFreq}%` },
  ];

  return (
    <div style={PANEL_CARD_STYLE}>
      <PanelHeader title={<>📊 研判结果分布</>} />
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", padding: "8px 0" }}>
        <DonutChart
          segments={segments}
          size={180}
          thickness={28}
          centerValue={highCount}
          centerLabel="高频事件"
        />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 16 }}>
        {legendData.map((item) => (
          <div key={item.label} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
            <span style={{ width: 10, height: 10, borderRadius: "50%", background: item.color, flexShrink: 0 }} />
            <span style={{ flex: 1, color: "var(--color-text-secondary)" }}>{item.label}</span>
            <span style={{ fontWeight: 600, color: "var(--color-text-primary)" }}>{item.value}</span>
            <span style={{ color: "var(--color-text-muted)", minWidth: 42, textAlign: "right" }}>{item.pct}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TrendPanel(): JSX.Element {
  const [range, setRange] = useState<"7d" | "30d" | "90d">("7d");
  const trendConfig = range === "7d" ? TREND_DATA_7D : range === "30d" ? TREND_DATA_30D : TREND_DATA_90D;

  return (
    <div style={{ ...PANEL_CARD_STYLE, marginBottom: "20px" }}>
      <PanelHeader
        title={<>📈 工单趋势</>}
        right={
          <div style={{ display: "flex", gap: 4 }}>
            {(["7d", "30d", "90d"] as const).map((r) => (
              <button
                key={r}
                style={range === r ? TOGGLE_BTN_ACTIVE : TOGGLE_BTN_INACTIVE}
                onClick={() => setRange(r)}
                onMouseEnter={(e) => {
                  if (range !== r) e.currentTarget.style.borderColor = "var(--color-primary)";
                }}
                onMouseLeave={(e) => {
                  if (range !== r) e.currentTarget.style.borderColor = "var(--color-border)";
                }}
              >
                {r === "7d" ? "7天" : r === "30d" ? "30天" : "90天"}
              </button>
            ))}
          </div>
        }
      />
      <div style={{ display: "flex", justifyContent: "center", padding: "10px 0" }}>
        <TrendMiniChart
          data={trendConfig.data}
          labels={trendConfig.labels}
          width={800}
          height={160}
          color="#2563eb"
        />
      </div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(3, 1fr)",
        gap: 16,
        marginTop: 12,
        paddingTop: 16,
        borderTop: "1px solid var(--color-divider)",
      }}>
        <div style={{ textAlign: "center", padding: "12px", background: "var(--color-surface-soft)", borderRadius: "var(--radius-md)" }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--color-primary)" }}>{trendConfig.stats.total}</div>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>本周总工单</div>
        </div>
        <div style={{ textAlign: "center", padding: "12px", background: "var(--color-surface-soft)", borderRadius: "var(--radius-md)" }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--color-success)" }}>{trendConfig.stats.avg}</div>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>日均工单</div>
        </div>
        <div style={{ textAlign: "center", padding: "12px", background: "var(--color-surface-soft)", borderRadius: "var(--radius-md)" }}>
          <div style={{ fontSize: 24, fontWeight: 700, color: "var(--color-orange)" }}>{trendConfig.stats.peak}</div>
          <div style={{ fontSize: 12, color: "var(--color-text-muted)", marginTop: 4 }}>峰值日</div>
        </div>
      </div>
    </div>
  );
}

function ActivityPanel(): JSX.Element {
  const navigate = useNavigate();

  const dotColors: Record<string, string> = {
    red: "var(--color-danger)",
    blue: "var(--color-primary)",
    green: "var(--color-success)",
    orange: "var(--color-orange)",
  };

  return (
    <div style={PANEL_CARD_STYLE}>
      <PanelHeader
        title={<>🔔 最近动态</>}
        right={
          <button
            style={{ fontSize: 13, color: "var(--color-primary)", fontWeight: 500, background: "none", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 4 }}
            onClick={() => navigate("/events")}
          >
            查看全部
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        }
      />
      <div style={{ display: "flex", flexDirection: "column" }}>
        {ACTIVITIES.map((item) => (
          <div
            key={item.id}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: 12,
              padding: "12px 0",
              borderBottom: "1px solid var(--color-divider)",
            }}
          >
            <div style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: dotColors[item.color],
              flexShrink: 0,
              marginTop: 5,
              boxShadow: `0 0 0 3px ${dotColors[item.color]}22`,
            }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-text-primary)" }}>{item.title}</span>
                <span style={{ fontSize: 11, color: "var(--color-text-faint)", flexShrink: 0, marginLeft: 8 }}>{item.time}</span>
              </div>
              <p style={{ fontSize: 12, color: "var(--color-text-muted)", margin: 0, lineHeight: 1.5 }}>{item.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatsRow(): JSX.Element {
  const workOrdersQuery = useQuery({
    queryKey: ["work-orders-stats"],
    queryFn: ({ signal }) => listWorkOrders({ offset: 0, limit: 20, signal }),
    retry: 1,
    staleTime: 30000,
  });

  const eventsQuery = useQuery({
    queryKey: ["events-stats"],
    queryFn: ({ signal }) => listEvents({ offset: 0, limit: 20, signal }),
    retry: 1,
    staleTime: 30000,
    enabled: workOrdersQuery.isSuccess,
  });

  const clustersQuery = useQuery({
    queryKey: ["clusters-stats"],
    queryFn: ({ signal }) => listClusters({ offset: 0, limit: 100, signal }),
    retry: 1,
    staleTime: 30000,
  });

  const totalWorkOrders = workOrdersQuery.data?.total ?? 0;
  const sampleEventCount = eventsQuery.data?.items.reduce((sum, e) => sum + (e.work_order?.event_count ?? 1), 0) ?? 0;
  const estimatedEvents = workOrdersQuery.data && eventsQuery.data
    ? Math.round(sampleEventCount * (totalWorkOrders / 20))
    : 0;
  const multiFreqCount = clustersQuery.data?.items.filter(c => c.is_multi_frequency).length ?? 0;

  return (
    <div style={STATS_GRID_STYLE}>
      <StatCard
        label="工单总数"
        value={totalWorkOrders}
        valueColor="#2563eb"
        chartData={[20, 35, 28, 45, 52, 68, 73, totalWorkOrders || 73]}
        chartColor="blue"
        hint="+12.5% 较上周↑"
        hintType="up"
        loading={workOrdersQuery.isPending}
      />
      <StatCard
        label="事件总数"
        subLabel="AI抽取事件"
        value={estimatedEvents || totalWorkOrders * 3 || 1243}
        valueColor="#f97316"
        chartData={[45, 68, 58, 92, 115, 138, estimatedEvents || 1243]}
        chartColor="orange"
        hint="+8.3% 较上周↑"
        hintType="up"
        loading={eventsQuery.isPending && workOrdersQuery.isPending}
      />
      <StatCard
        label="多频事件"
        value={multiFreqCount || 28}
        valueColor="#f97316"
        chartData={[5, 8, 12, 10, 15, 18, 22]}
        chartColor="orange"
        hint="+2 新增待关注"
        hintType="highlight"
        loading={clustersQuery.isPending}
      />
      <StatCard
        label="研判准确率"
        value="95.8"
        unit="%"
        valueColor="#16a34a"
        chartData={[92, 93, 94, 93.5, 94.2, 95, 95.8]}
        chartColor="green"
        hint="稳定↑"
        hintType="stable"
      />
    </div>
  );
}

export function DashboardPage(): JSX.Element {
  return (
    <div>
      <style>{`
        .stat-card-hover:hover {
          box-shadow: var(--shadow-card-hover) !important;
        }
        @keyframes pulse-ring {
          0% { box-shadow: 0 0 0 0 rgba(37,99,235,0.4); }
          70% { box-shadow: 0 0 0 8px rgba(37,99,235,0); }
          100% { box-shadow: 0 0 0 0 rgba(37,99,235,0); }
        }
      `}</style>
      <WelcomeBar />
      <StatsRow />
      <div style={THREE_COL_STYLE}>
        <EventRadarPanel />
        <AIFlowPanel />
        <DistributionPanel />
      </div>
      <TrendPanel />
      <ActivityPanel />
    </div>
  );
}
