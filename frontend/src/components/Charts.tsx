import type { JSX } from "react";

interface MiniLineChartProps {
  data: number[];
  width?: number;
  height?: number;
  color?: "blue" | "orange" | "green" | "red";
  showArea?: boolean;
  showDots?: boolean;
}

export function MiniLineChart({
  data,
  width = 160,
  height = 56,
  color = "blue",
  showArea = true,
  showDots = false,
}: MiniLineChartProps): JSX.Element | null {
  if (!data.length) return null;
  const padding = showDots ? 4 : 0;
  const w = width - padding * 2;
  const h = height - padding * 2;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const stepX = data.length > 1 ? w / (data.length - 1) : 0;

  const points = data.map((v, i) => {
    const x = padding + i * stepX;
    const y = padding + h - ((v - min) / range) * h;
    return [x, y] as const;
  });

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
  const areaPath = showArea
    ? `${linePath} L${padding + w},${padding + h} L${padding},${padding + h} Z`
    : "";

  const colorClass =
    color === "orange" ? "mini-chart__line--orange" :
    color === "green" ? "mini-chart__line--green" :
    color === "red" ? "mini-chart__line--red" :
    "mini-chart__line--blue";

  const strokeColor =
    color === "orange" ? "#f97316" :
    color === "green" ? "#16a34a" :
    color === "red" ? "#ef4444" :
    "#2563eb";

  const gradId = `miniGrad-${color}-${Math.random().toString(36).slice(2, 8)}`;

  return (
    <svg width={width} height={height} className="mini-chart" viewBox={`0 0 ${width} ${height}`}>
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.3" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {showArea && (
        <path d={areaPath} fill={`url(#${gradId})`} />
      )}
      <path d={linePath} className={`mini-chart__line ${colorClass}`} />
      {showDots && points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={2} fill={strokeColor} />
      ))}
    </svg>
  );
}

interface DonutChartProps {
  segments: { value: number; color: string; label: string }[];
  size?: number;
  thickness?: number;
  centerValue?: string | number;
  centerLabel?: string;
}

export function DonutChart({
  segments,
  size = 160,
  thickness = 24,
  centerValue,
  centerLabel,
}: DonutChartProps): JSX.Element {
  const total = segments.reduce((s, seg) => s + seg.value, 0);
  const cx = size / 2;
  const cy = size / 2;
  const r = (size - thickness) / 2;
  const circumference = 2 * Math.PI * r;

  let offset = 0;
  const arcs = segments.map((seg) => {
    const pct = total > 0 ? seg.value / total : 0;
    const length = pct * circumference;
    const arc = {
      ...seg,
      dasharray: `${length} ${circumference - length}`,
      dashoffset: -offset,
    };
    offset += length;
    return arc;
  });

  return (
    <div className="donut-chart" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={cx} cy={cy} r={r}
          fill="none"
          stroke="#eef1f6"
          strokeWidth={thickness}
        />
        {arcs.map((arc, i) => (
          <circle
            key={i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={arc.color}
            strokeWidth={thickness}
            strokeDasharray={arc.dasharray}
            strokeDashoffset={arc.dashoffset}
            transform={`rotate(-90 ${cx} ${cy})`}
            strokeLinecap="butt"
          />
        ))}
      </svg>
      {(centerValue !== undefined || centerLabel) && (
        <div className="donut-chart__center">
          {centerValue !== undefined && (
            <div className="donut-chart__value">{centerValue}</div>
          )}
          {centerLabel && <div className="donut-chart__label">{centerLabel}</div>}
        </div>
      )}
    </div>
  );
}

interface TrendMiniChartProps {
  data: number[];
  labels: string[];
  width?: number;
  height?: number;
  color?: string;
}

export function TrendMiniChart({
  data,
  labels,
  width = 220,
  height = 100,
  color = "#2563eb",
}: TrendMiniChartProps): JSX.Element {
  const padL = 32;
  const padR = 8;
  const padT = 10;
  const padB = 24;
  const w = width - padL - padR;
  const h = height - padT - padB;
  const min = Math.min(...data, 0);
  const max = Math.max(...data, 1);
  const range = max - min || 1;
  const stepX = data.length > 1 ? w / (data.length - 1) : 0;

  const points = data.map((v, i) => {
    const x = padL + i * stepX;
    const y = padT + h - ((v - min) / range) * h;
    return [x, y] as const;
  });

  const linePath = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x},${y}`).join(" ");
  const areaPath = `${linePath} L${padL + w},${padT + h} L${padL},${padT + h} Z`;
  const gradId = `trendGrad-${Math.random().toString(36).slice(2, 8)}`;

  const yTicks = 4;
  const tickVals = Array.from({ length: yTicks + 1 }, (_, i) => min + (range * i) / yTicks);

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="mini-chart">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.25" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {tickVals.map((tv, i) => {
        const y = padT + h - ((tv - min) / range) * h;
        return (
          <g key={i}>
            <line x1={padL} y1={y} x2={padL + w} y2={y} stroke="#eef1f6" strokeWidth="1" />
            <text x={padL - 4} y={y + 3} textAnchor="end" fontSize="10" fill="#b4bdd0">
              {Math.round(tv)}
            </text>
          </g>
        );
      })}
      <path d={areaPath} fill={`url(#${gradId})`} />
      <path d={linePath} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {labels.map((lbl, i) => {
        const x = padL + i * stepX;
        return (
          <text key={i} x={x} y={height - 6} textAnchor="middle" fontSize="10" fill="#b4bdd0">
            {lbl}
          </text>
        );
      })}
    </svg>
  );
}
