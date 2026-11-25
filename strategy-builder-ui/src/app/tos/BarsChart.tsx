"use client";

import type { PointerEvent } from 'react';
import {
  barValue,
  hasFlag,
  type TosBarsBar,
  type TosHypotheticalTrade,
} from '@/lib/dashboard/tosBars';
import { barVerdict, isProbeRule, type ProbePredicate } from '@/lib/dashboard/tosDecision';
import { glossaryLabel } from '@/lib/dashboard/tosGlossary';

interface BarsChartProps {
  bars: TosBarsBar[];
  /** The bar the checklist below is explaining. */
  selectedIndex: number;
  onSelect: (index: number) => void;
  /** The document's probe test, when it carries one. */
  isProbe?: ProbePredicate;
  /**
   * The would-have-been trades, drawn hollow beside the real marks.
   *
   * They are NOT fills: this tenant never ordered. Hollow and dashed is the
   * whole point — a solid mark on the same row as a real entry would put an
   * assumed fill and an actual one in the same visual language.
   */
  hypothetical?: TosHypotheticalTrade[];
}

const WIDTH = 1000;
const PLOT_TOP = 16;
const PLOT_BOTTOM = 150;
const MARK_ROW = 170;
const HEIGHT = 212;
/** How many time labels the axis carries, at most. */
const AXIS_TICKS = 6;

/** `close_x100` / `vwap_x100` are hundredths; the axis labels divide them back. */
function price(value: number | null): string {
  return value == null ? '알 수 없음' : (value / 100).toLocaleString('ko-KR');
}

function x(index: number, count: number): number {
  return count < 2 ? WIDTH / 2 : (index / (count - 1)) * WIDTH;
}

/** Where the hypothetical marks sit — one row under the decision marks. */
const HYPO_ROW = 192;

/** The sentence a marker shows on hover — what happened, in plain Korean. */
function markerTitle(bar: TosBarsBar, isProbe: ProbePredicate = isProbeRule): string {
  const verdict = barVerdict(bar, isProbe);
  const rule = verdict.ruleId ? `${glossaryLabel(verdict.ruleId)} (${verdict.ruleId})` : null;
  const gate = verdict.gate ? ` · 게이트 ${verdict.gate.label}` : '';
  return `${bar.time_kst ?? '시각 알 수 없음'} · ${verdict.headline}${rule ? ` · ${rule}` : ''}${gate}`;
}

/**
 * Price against VWAP for the session, with one mark per decision and per halt.
 *
 * Reads what the engine evaluated (`barValue` prefers the engine's value view
 * over the producer's journal line), so a bar where the two disagree is drawn
 * at the value the decision was actually made on.
 *
 * **Accessibility, and why the drawing is not the accessible surface.** Every
 * fact drawn here is also stated in text below: the selected bar's checklist,
 * the verdict timeline, and the event log. The slider is the keyboard path to
 * the same selection a pointer makes on the plot, so the chart is marked
 * `img` with a summary label and the marks carry `<title>` for sighted hover,
 * rather than pretending a 380-point polyline can be read element by element.
 */
export default function BarsChart({
  bars,
  selectedIndex,
  onSelect,
  isProbe = isProbeRule,
  hypothetical = [],
}: BarsChartProps) {
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
  const y = (value: number) => PLOT_TOP + (1 - (value - low) / span) * (PLOT_BOTTOM - PLOT_TOP);

  const points = (series: (number | null)[]) =>
    series
      .map((value, index) => (value == null ? null : `${x(index, bars.length)},${y(value)}`))
      .filter((point): point is string => point !== null)
      .join(' ');

  const indexed = bars.map((bar, index) => ({ bar, index }));
  const entries = indexed.filter(({ bar }) => barVerdict(bar, isProbe).kind === 'entry');
  const probes = indexed.filter(({ bar }) => barVerdict(bar, isProbe).kind === 'probe');
  const exits = indexed.filter(({ bar }) => barVerdict(bar, isProbe).kind === 'exit');
  const halted = indexed.filter(
    ({ bar }) => barVerdict(bar, isProbe).gate != null && bar.evaluation !== 'withheld',
  );
  const withheld = indexed.filter(({ bar }) => hasFlag(bar, 'W'));

  // The hypothetical legs, placed by the bar time each one names. A time the
  // document does not carry is dropped rather than drawn at index 0.
  const indexByTime = new Map(
    bars.map((bar, index) => [bar.time_kst ?? '', index] as const).filter(([time]) => time !== ''),
  );
  const hypoLegs = hypothetical.flatMap((trade, order) => {
    const legs: { key: string; index: number; leg: 'entry' | 'exit'; title: string }[] = [];
    const entryIndex = indexByTime.get(trade.entry_time_kst ?? '');
    const exitIndex = indexByTime.get(trade.exit_time_kst ?? '');
    if (entryIndex != null) {
      legs.push({
        key: `hi-${order}`,
        index: entryIndex,
        leg: 'entry',
        title: `${trade.entry_time_kst} · 가상 진입(체결 가정) · ${glossaryLabel(trade.entry_rule_id)}`,
      });
    }
    if (exitIndex != null) {
      legs.push({
        key: `hx-${order}`,
        index: exitIndex,
        leg: 'exit',
        title: `${trade.exit_time_kst} · 가상 청산(체결 가정) · ${
          trade.exit_rule_id ? glossaryLabel(trade.exit_rule_id) : '강제 청산'
        }`,
      });
    }
    return legs;
  });

  const ticks = Array.from({ length: Math.min(AXIS_TICKS, bars.length) }, (_, slot) => {
    const index =
      bars.length < 2 ? 0 : Math.round((slot / (Math.min(AXIS_TICKS, bars.length) - 1 || 1)) * (bars.length - 1));
    return { index, label: bars[index]?.time_kst ?? '' };
  });

  /** Pointer x within the plot → the nearest bar. */
  const selectFromPointer = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    if (box.width === 0 || bars.length < 2) return;
    const ratio = (event.clientX - box.left) / box.width;
    const index = Math.round(ratio * (bars.length - 1));
    onSelect(Math.min(bars.length - 1, Math.max(0, index)));
  };

  const selected = bars[selectedIndex];

  return (
    <figure role="group" aria-label="가격과 VWAP" className="min-w-0 space-y-2">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="h-56 w-full touch-none"
        preserveAspectRatio="none"
        role="img"
        aria-label={`${bars.length}개 봉의 종가와 VWAP. 진입 ${entries.length}회, 청산 ${exits.length}회, 시험 진입 ${probes.length}회, 게이트 차단 ${halted.length}회${
          hypoLegs.length ? `, 가상 진입·청산 ${hypoLegs.length}회` : ''
        }.`}
        onPointerDown={selectFromPointer}
        onPointerMove={(event) => {
          if (event.buttons === 1) selectFromPointer(event);
        }}
      >
        {withheld.map(({ index }) => (
          <rect
            key={`w-${index}`}
            x={x(index, bars.length) - 1}
            y={PLOT_TOP - 4}
            width={2}
            height={PLOT_BOTTOM - PLOT_TOP + 8}
            className="fill-amber-300/60"
          >
            <title>{markerTitle(bars[index], isProbe)}</title>
          </rect>
        ))}
        {/* The cursor: where the checklist below is reading. */}
        <line
          x1={x(selectedIndex, bars.length)}
          x2={x(selectedIndex, bars.length)}
          y1={PLOT_TOP - 6}
          y2={MARK_ROW + 8}
          className="stroke-slate-900 dark:stroke-slate-100"
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <polyline
          points={points(vwaps)}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          strokeDasharray="6 4"
          className="text-slate-400 dark:text-slate-500"
        />
        <polyline
          points={points(closes)}
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="text-slate-700 dark:text-slate-200"
        />
        {exits.map(({ index }) => (
          <rect
            key={`x-${index}`}
            x={x(index, bars.length) - 3}
            y={MARK_ROW - 3}
            width={6}
            height={6}
            className="fill-slate-500"
          >
            <title>{markerTitle(bars[index], isProbe)}</title>
          </rect>
        ))}
        {/* Thin and translucent on purpose: a probe tenant fires on every bar
            of the window, and a solid 325-wide slab would read as one long
            fault rather than as "this ran all day". */}
        {probes.map(({ index }) => (
          <rect
            key={`p-${index}`}
            x={x(index, bars.length) - 1}
            y={MARK_ROW - 5}
            width={2}
            height={10}
            className="fill-amber-500/60"
          >
            <title>{markerTitle(bars[index], isProbe)}</title>
          </rect>
        ))}
        {entries.map(({ index }) => (
          <circle
            key={`e-${index}`}
            cx={x(index, bars.length)}
            cy={MARK_ROW}
            r={5}
            className="fill-emerald-500"
          >
            <title>{markerTitle(bars[index], isProbe)}</title>
          </circle>
        ))}
        {halted.map(({ index }) => (
          <path
            key={`h-${index}`}
            d={`M ${x(index, bars.length)} ${MARK_ROW + 10} l 4 7 l -8 0 z`}
            className="fill-amber-600"
          >
            <title>{markerTitle(bars[index], isProbe)}</title>
          </path>
        ))}
        {/* Hollow, dashed, and on their own row: an assumed fill must not
            share a visual language with a real one. */}
        {hypoLegs.map(({ key, index, leg, title }) =>
          leg === 'entry' ? (
            <circle
              key={key}
              cx={x(index, bars.length)}
              cy={HYPO_ROW}
              r={5}
              fill="none"
              strokeWidth={1.5}
              strokeDasharray="3 2"
              className="stroke-slate-600 dark:stroke-slate-300"
            >
              <title>{title}</title>
            </circle>
          ) : (
            <rect
              key={key}
              x={x(index, bars.length) - 4}
              y={HYPO_ROW - 4}
              width={8}
              height={8}
              fill="none"
              strokeWidth={1.5}
              strokeDasharray="3 2"
              className="stroke-slate-600 dark:stroke-slate-300"
            >
              <title>{title}</title>
            </rect>
          ),
        )}
        {ticks.map(({ index, label }) => (
          <text
            key={`t-${index}`}
            x={Math.min(WIDTH - 24, Math.max(24, x(index, bars.length)))}
            y={HEIGHT - 4}
            textAnchor="middle"
            className="fill-slate-500 text-[11px]"
          >
            {label}
          </text>
        ))}
      </svg>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        {/* `htmlFor`, not a wrapping label: the time beside the slider is part
            of the control's row but not part of its name. */}
        <label htmlFor="bars-bar-index" className="text-slate-500 dark:text-slate-400">
          봉 선택
        </label>
        <input
          id="bars-bar-index"
          type="range"
          min={0}
          max={Math.max(0, bars.length - 1)}
          step={1}
          value={selectedIndex}
          onChange={(event) => onSelect(Number(event.target.value))}
          aria-valuetext={`${selected?.time_kst ?? '시각 알 수 없음'} · ${
            selected ? barVerdict(selected, isProbe).headline : '알 수 없음'
          }`}
          className="min-w-0 flex-1"
        />
        <span className="tabular-nums font-medium">{selected?.time_kst ?? '알 수 없음'}</span>
      </div>

      <figcaption className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500 dark:text-slate-400">
        <span>
          종가 {price(low)} – {price(high)}
        </span>
        <span>— 종가</span>
        <span className="text-slate-500 dark:text-slate-400">- - VWAP</span>
        <span className="text-emerald-600 dark:text-emerald-400">● 진입</span>
        <span className="text-slate-600 dark:text-slate-300">■ 청산</span>
        <span className="text-amber-600 dark:text-amber-400">▌시험 진입 · 평가 보류</span>
        <span className="text-amber-700 dark:text-amber-400">▲ 게이트 차단</span>
        {hypoLegs.length > 0 && (
          <span className="text-slate-600 dark:text-slate-300">
            ○ □ 가상 진입 · 청산(체결 가정 — 실제 체결 아님)
          </span>
        )}
        <span>{bars.length}개 봉 · 엔진이 평가한 값 기준</span>
      </figcaption>
    </figure>
  );
}
