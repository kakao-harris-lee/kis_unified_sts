"use client";

import { barValue, hasFlag, type TosBarsBar } from '@/lib/dashboard/tosBars';

interface BarsChartProps {
  bars: TosBarsBar[];
}

const WIDTH = 1000;
const HEIGHT = 180;
const MARK_ROW = HEIGHT - 10;

/** `close_x100` / `vwap_x100` are hundredths; the axis labels divide them back. */
function label(value: number | null): string {
  return value == null ? '알 수 없음' : (value / 100).toLocaleString('ko-KR');
}

function x(index: number, count: number): number {
  return count < 2 ? WIDTH / 2 : (index / (count - 1)) * WIDTH;
}

/**
 * Price and VWAP over the session, with a mark per decision and per halt.
 *
 * Reads what the engine evaluated (`barValue` prefers the engine's value view
 * over the producer's journal line), so a bar where the two disagree is drawn
 * at the value the decision was actually made on.
 */
export default function BarsChart({ bars }: BarsChartProps) {
  const closes = bars.map((bar) => barValue(bar, 'close_x100'));
  const vwaps = bars.map((bar) => barValue(bar, 'vwap_x100'));
  const known = [...closes, ...vwaps].filter((value): value is number => value != null);
  if (!known.length) {
    return (
      <p className="text-sm text-slate-500 dark:text-slate-400">
        가격·VWAP 값이 없어 그릴 수 없습니다.
      </p>
    );
  }
  const low = Math.min(...known);
  const high = Math.max(...known);
  const span = high - low || 1;
  const y = (value: number) => 20 + (1 - (value - low) / span) * (HEIGHT - 60);

  const points = (series: (number | null)[]) =>
    series
      .map((value, index) => (value == null ? null : `${x(index, bars.length)},${y(value)}`))
      .filter((point): point is string => point !== null)
      .join(' ');

  const decided = bars
    .map((bar, index) => ({ bar, index }))
    .filter(({ bar }) => bar.decision_kind && bar.decision_kind !== 'NO_ACTION');
  const halted = bars
    .map((bar, index) => ({ bar, index }))
    .filter(({ bar }) => bar.evidence?.halt_step || bar.evidence?.halt_reason);
  const withheld = bars
    .map((bar, index) => ({ bar, index }))
    .filter(({ bar }) => hasFlag(bar, 'W'));

  return (
    <figure
      role="group"
      aria-label="가격과 VWAP"
      className="min-w-0 overflow-x-auto"
    >
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-44 w-full"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <polyline
          points={points(vwaps)}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeDasharray="6 4"
          className="text-sky-500"
        />
        <polyline
          points={points(closes)}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="text-slate-700 dark:text-slate-200"
        />
        {withheld.map(({ index }) => (
          <rect
            key={`w-${index}`}
            x={x(index, bars.length) - 1}
            y={14}
            width={2}
            height={HEIGHT - 40}
            className="fill-amber-300/60"
          />
        ))}
        {decided.map(({ index }) => (
          <circle
            key={`d-${index}`}
            cx={x(index, bars.length)}
            cy={MARK_ROW}
            r={4}
            className="fill-emerald-500"
          />
        ))}
        {halted.map(({ index }) => (
          <rect
            key={`h-${index}`}
            x={x(index, bars.length) - 3}
            y={MARK_ROW - 3}
            width={6}
            height={6}
            className="fill-rose-500"
          />
        ))}
      </svg>
      <figcaption className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <span>종가 {label(low)} – {label(high)}</span>
        <span>— 종가</span>
        <span className="text-sky-600 dark:text-sky-400">- - VWAP</span>
        <span className="text-emerald-600 dark:text-emerald-400">● 결정</span>
        <span className="text-rose-600 dark:text-rose-400">■ 정지</span>
        <span className="text-amber-600 dark:text-amber-400">▌보류</span>
        <span>{bars.length}개 봉 · 평가한 값 기준</span>
      </figcaption>
    </figure>
  );
}
