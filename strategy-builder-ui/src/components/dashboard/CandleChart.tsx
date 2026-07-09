"use client";

import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear } from "@visx/scale";
import type { OhlcvBar } from "@/lib/dashboard/marketData";

// KR convention: up = red (profit), down = blue (loss). Matches --color-profit/loss.
const COLOR_UP = "#ef4444";
const COLOR_DOWN = "#3b82f6";
const COLOR_BUY_MARKER = "#16a34a";
const COLOR_SELL_MARKER = "#ea580c";
const AXIS_TICK = { fontSize: 11, fill: "#94a3b8" } as const;

export interface PriceMarker {
  t: string; // ISO timestamp
  price: number;
  side: "BUY" | "SELL";
  label?: string;
}

interface Candle {
  t: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** Drop bars with any null OHLC so the chart only renders complete candles. */
export function toCandles(bars: OhlcvBar[]): Candle[] {
  const out: Candle[] = [];
  for (const b of bars) {
    if (
      b.open === null ||
      b.high === null ||
      b.low === null ||
      b.close === null
    )
      continue;
    out.push({ t: b.t, open: b.open, high: b.high, low: b.low, close: b.close });
  }
  return out;
}

function fmtPrice(v: number): string {
  return v.toLocaleString("ko-KR");
}

function hhmm(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getHours()).padStart(2, "0")}:${String(
    d.getMinutes(),
  ).padStart(2, "0")}`;
}

/** Fixed-size SVG — named export for deterministic render tests. */
export function CandleSvg({
  width,
  height,
  candles,
  markers,
}: {
  width: number;
  height: number;
  candles: Candle[];
  markers: PriceMarker[];
}) {
  const margin = { top: 8, right: 8, bottom: 22, left: 52 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  // Index-based x so candles are evenly spaced (gaps/sessions don't distort).
  const n = candles.length;
  const step = n > 0 ? innerW / n : innerW;
  const bodyW = Math.max(1, step * 0.6);

  const lows = candles.map((c) => c.low);
  const highs = candles.map((c) => c.high);
  const yScale = scaleLinear({
    domain: [Math.min(...lows), Math.max(...highs)],
    range: [innerH, 0],
    nice: true,
  });

  const indexByT = new Map<string, number>();
  candles.forEach((c, i) => indexByT.set(c.t, i));

  const xCenter = (i: number) => i * step + step / 2;

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        {candles.map((c, i) => {
          const up = c.close >= c.open;
          const color = up ? COLOR_UP : COLOR_DOWN;
          const cx = xCenter(i);
          const yHigh = yScale(c.high) ?? 0;
          const yLow = yScale(c.low) ?? 0;
          const yOpen = yScale(c.open) ?? 0;
          const yClose = yScale(c.close) ?? 0;
          const bodyTop = Math.min(yOpen, yClose);
          const bodyH = Math.max(1, Math.abs(yClose - yOpen));
          return (
            <g key={c.t}>
              <line
                x1={cx}
                x2={cx}
                y1={yHigh}
                y2={yLow}
                stroke={color}
                strokeWidth={1}
              />
              <rect
                x={cx - bodyW / 2}
                y={bodyTop}
                width={bodyW}
                height={bodyH}
                fill={color}
              />
            </g>
          );
        })}
        {markers.map((m, i) => {
          const idx = indexByT.get(m.t);
          if (idx === undefined) return null;
          const cx = xCenter(idx);
          const cy = yScale(m.price) ?? 0;
          const color = m.side === "BUY" ? COLOR_BUY_MARKER : COLOR_SELL_MARKER;
          // Triangle marker: up-pointing for BUY (below price), down for SELL.
          const dir = m.side === "BUY" ? 1 : -1;
          const points = `${cx},${cy} ${cx - 4},${cy + dir * 8} ${cx + 4},${cy + dir * 8}`;
          return (
            <polygon
              key={`${m.t}-${i}`}
              points={points}
              fill={color}
              stroke="#fff"
              strokeWidth={0.5}
            >
              <title>{`${m.side} ${fmtPrice(m.price)}${m.label ? ` · ${m.label}` : ""}`}</title>
            </polygon>
          );
        })}
        <AxisLeft
          scale={yScale}
          numTicks={4}
          tickFormat={(v) => fmtPrice(Number(v))}
          tickLabelProps={() => AXIS_TICK}
          stroke="#cbd5e1"
          tickStroke="#cbd5e1"
        />
        <AxisBottom
          top={innerH}
          scale={scaleLinear({ domain: [0, Math.max(1, n)], range: [0, innerW] })}
          numTicks={Math.min(6, n)}
          tickFormat={(v) => {
            const i = Math.round(Number(v));
            return candles[i] ? hhmm(candles[i].t) : "";
          }}
          tickLabelProps={() => AXIS_TICK}
          stroke="#cbd5e1"
          tickStroke="#cbd5e1"
        />
      </Group>
    </svg>
  );
}

/**
 * Candlestick price chart with BUY/SELL markers overlaid at fill/signal
 * price+time. For post-hoc diagnosis ("why did it enter here"), not live
 * trading — a bounded window, so no realtime-streaming engine needed.
 */
export default function CandleChart({
  bars,
  markers = [],
  title,
  subtitle,
}: {
  bars: OhlcvBar[];
  markers?: PriceMarker[];
  title: string;
  subtitle?: string;
}) {
  const candles = toCandles(bars);
  return (
    <section
      aria-label={title}
      className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900"
    >
      <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
        {title}
      </h3>
      {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      {candles.length === 0 ? (
        <div className="flex h-64 items-center justify-center text-sm text-slate-400">
          가격 데이터 없음 — 심볼·기간을 확인하세요
        </div>
      ) : (
        <div className="mt-2 h-64">
          <ParentSize>
            {({ width, height }) =>
              width > 0 && height > 0 ? (
                <CandleSvg
                  width={width}
                  height={height}
                  candles={candles}
                  markers={markers}
                />
              ) : null
            }
          </ParentSize>
        </div>
      )}
    </section>
  );
}
