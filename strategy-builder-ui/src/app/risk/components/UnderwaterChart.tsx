"use client";

import { AxisBottom, AxisLeft } from "@visx/axis";
import { curveMonotoneX } from "@visx/curve";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear, scaleTime } from "@visx/scale";
import { AreaClosed } from "@visx/shape";
import ChartCard from "@/components/dashboard/ChartCard";
import type { PortfolioEquityHistoryPoint } from "@/lib/dashboard/portfolio";

// Underwater(수중) 낙폭 색상 — SVG stroke/fill은 var()를 받지 못해 리터럴 hex 사용.
const COLOR_DRAWDOWN = "#3b82f6"; // --color-loss (파랑 = 하락/손실, KR 관례)

const EMPTY_LABEL = "배치 미가동 — equity 배치 가동 후 표시됩니다";

const AXIS_TICK = { fontSize: 11, fill: "#94a3b8" } as const;

export interface DrawdownPoint {
  trade_date: string;
  /** 누적 최고점 대비 낙폭 % (≤ 0). */
  drawdown_pct: number;
}

/**
 * Underwater(수중) 낙폭 — total_equity의 누적 최고점(running max) 대비 낙폭 %.
 *
 * total_equity가 null인 포인트는 건너뛴다(0으로 채우지 않음). 결측일을 0%로
 * 채우면 "최고점 회복"으로 오독되므로, 유효 포인트만 사용한다(sibling 차트의
 * hasData 관례와 동일). running max는 조회 윈도우(기본 90일) 내 첫 유효 포인트에서
 * 시작한다 — 그 이전 데이터는 클라이언트에 없다(허용된 경계 조건).
 */
export function computeDrawdown(
  points: PortfolioEquityHistoryPoint[],
): DrawdownPoint[] {
  const result: DrawdownPoint[] = [];
  let runningMax: number | null = null;
  for (const p of points) {
    if (p.trade_date === null || p.total_equity === null) continue;
    runningMax =
      runningMax === null ? p.total_equity : Math.max(runningMax, p.total_equity);
    const drawdown_pct =
      runningMax > 0 ? ((p.total_equity - runningMax) / runningMax) * 100 : 0;
    result.push({ trade_date: p.trade_date, drawdown_pct });
  }
  return result;
}

function fmtPct(v: number): string {
  return `${v.toFixed(1)}%`;
}

function shortDate(value: string): string {
  return value.slice(5);
}

/**
 * 고정 width/height를 받는 순수 SVG 렌더러 — named export로 노출해 테스트에서
 * ParentSize/ResizeObserver 타이밍 없이 직접 렌더할 수 있게 한다.
 */
export function DrawdownSvg({
  width,
  height,
  data,
}: {
  width: number;
  height: number;
  data: DrawdownPoint[];
}) {
  const margin = { top: 8, right: 8, bottom: 24, left: 44 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const xScale = scaleTime({
    domain: [
      new Date(data[0].trade_date),
      new Date(data[data.length - 1].trade_date),
    ],
    range: [0, innerW],
  });
  const minDd = Math.min(0, ...data.map((d) => d.drawdown_pct));
  const yScale = scaleLinear({
    domain: [minDd, 0],
    range: [innerH, 0],
    nice: true,
  });

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        <AreaClosed
          data={data}
          x={(d) => xScale(new Date(d.trade_date)) ?? 0}
          y={(d) => yScale(d.drawdown_pct) ?? 0}
          yScale={yScale}
          curve={curveMonotoneX}
          fill={COLOR_DRAWDOWN}
          fillOpacity={0.25}
          stroke={COLOR_DRAWDOWN}
          strokeWidth={1.5}
        />
        <AxisLeft
          scale={yScale}
          numTicks={4}
          tickFormat={(v) => fmtPct(Number(v))}
          tickLabelProps={() => AXIS_TICK}
          stroke="#cbd5e1"
          tickStroke="#cbd5e1"
        />
        <AxisBottom
          top={innerH}
          scale={xScale}
          numTicks={5}
          tickFormat={(d) => shortDate((d as Date).toISOString().slice(0, 10))}
          tickLabelProps={() => AXIS_TICK}
          stroke="#cbd5e1"
          tickStroke="#cbd5e1"
        />
      </Group>
    </svg>
  );
}

/** Underwater(수중) 낙폭 차트 — 누적 최고점 대비 낙폭 %(≤0)를 면적으로 표시. */
export default function UnderwaterChart({
  points,
}: {
  points: PortfolioEquityHistoryPoint[];
}) {
  const hasData = points.some((p) => p.total_equity !== null);
  const data = computeDrawdown(points);
  return (
    <ChartCard
      title="Underwater (누적 최고점 대비 낙폭)"
      subtitle="전체 자산 누적 최고점 대비 낙폭 % · 항상 ≤ 0"
      isEmpty={!hasData || data.length === 0}
      emptyLabel={EMPTY_LABEL}
    >
      <ParentSize>
        {({ width, height }) =>
          width > 0 && height > 0 ? (
            <DrawdownSvg width={width} height={height} data={data} />
          ) : null
        }
      </ParentSize>
    </ChartCard>
  );
}
