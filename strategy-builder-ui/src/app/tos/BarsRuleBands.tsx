"use client";

import {
  BAR_FLAGS,
  hasFlag,
  type TosBarsBar,
  type TosBarsSummaryRule,
} from '@/lib/dashboard/tosBars';

interface BarsRuleBandsProps {
  bars: TosBarsBar[];
  rules: TosBarsSummaryRule[];
}

const WIDTH = 1000;
const ROW_HEIGHT = 18;
const GAP = 4;

const FLAG_LABELS: Record<string, string> = {
  V: 'V · 엔진 값이 journal 과 다름',
  D: 'D · 결정이 엔진 결과와 다름',
  W: 'W · 보류(평가 안 함)',
  U: 'U · journal 로 대체(분모 밖)',
};

/**
 * One strip per rule showing where its guard held, plus one per flag.
 *
 * A bar the engine never judged is NOT drawn as "did not fire": it gets its own
 * amber cell, because "the guard was false" and "nothing was evaluated" are
 * different facts and the summary's denominators already exclude the second.
 * Only the cells that carry something are emitted, so the background shows
 * through for the ordinary "did not fire" case.
 */
export default function BarsRuleBands({ bars, rules }: BarsRuleBandsProps) {
  const count = bars.length;
  const cell = count ? WIDTH / count : WIDTH;
  const rows = [...rules.map((rule) => ({ kind: 'rule' as const, rule })),
    ...BAR_FLAGS.map((flag) => ({ kind: 'flag' as const, flag }))];
  const height = rows.length * (ROW_HEIGHT + GAP);

  return (
    <div className="min-w-0 space-y-2">
      <div className="flex min-w-0 gap-3">
        <ul
          aria-label="띠 이름"
          className="w-52 shrink-0 space-y-0 text-xs text-slate-600 dark:text-slate-300"
        >
          {rows.map((row, index) => (
            <li
              key={index}
              style={{ height: `${ROW_HEIGHT + GAP}px` }}
              className="flex items-center truncate"
            >
              {row.kind === 'rule'
                ? `${row.rule.label ?? '?'} · ${row.rule.rule_id ?? '알 수 없음'}`
                : FLAG_LABELS[row.flag]}
            </li>
          ))}
        </ul>
        <svg
          viewBox={`0 0 ${WIDTH} ${height}`}
          className="min-w-0 flex-1"
          style={{ height: `${height}px` }}
          preserveAspectRatio="none"
          role="group"
          aria-label="규칙별 통과 띠"
        >
          {rows.map((row, rowIndex) => {
            const y = rowIndex * (ROW_HEIGHT + GAP);
            return (
              <g key={rowIndex}>
                <rect
                  x={0}
                  y={y}
                  width={WIDTH}
                  height={ROW_HEIGHT}
                  className="fill-slate-100 dark:fill-slate-800"
                />
                {bars.map((bar, barIndex) => {
                  const marked =
                    row.kind === 'rule'
                      ? bar.rules?.[rowIndex]?.fired === true
                      : hasFlag(bar, row.flag);
                  const unevaluated =
                    row.kind === 'rule' && !(bar.rules && bar.rules.length);
                  if (!marked && !unevaluated) return null;
                  return (
                    <rect
                      key={barIndex}
                      x={barIndex * cell}
                      y={y}
                      width={Math.max(cell, 1)}
                      height={ROW_HEIGHT}
                      className={
                        marked
                          ? 'fill-emerald-500'
                          : 'fill-amber-300 dark:fill-amber-500'
                      }
                    />
                  );
                })}
              </g>
            );
          })}
        </svg>
      </div>
      <p className="text-xs text-slate-500 dark:text-slate-400">
        초록 = 그 봉에서 발화/해당 · 노랑 = 평가하지 않음 · 회색 = 발화하지 않음
      </p>
    </div>
  );
}
