"use client";

import { AxisBottom, AxisLeft } from "@visx/axis";
import { Group } from "@visx/group";
import { ParentSize } from "@visx/responsive";
import { scaleLinear, scaleOrdinal, scaleTime } from "@visx/scale";
import { AreaStack } from "@visx/shape";
import ChartCard from "@/components/dashboard/ChartCard";
import type { ExposureHistory, ExposurePoint } from "@/lib/dashboard/analytics";

const PALETTE = [
  "#245bee",
  "#ef4444",
  "#0891b2",
  "#9333ea",
  "#f59e0b",
  "#16a34a",
  "#e11d48",
  "#64748b",
];
const AXIS_TICK = { fontSize: 11, fill: "#94a3b8" } as const;
const EMPTY_LABEL = "포지션 스냅샷 없음 — 포지션 보유 시 표시됩니다";

function shortDate(value: string): string {
  return value.slice(5);
}

function fmtKrwTick(v: number): string {
  if (Math.abs(v) >= 1e8) return `${(v / 1e8).toFixed(1)}억`;
  if (Math.abs(v) >= 1e4) return `${Math.round(v / 1e4).toLocaleString("ko-KR")}만`;
  return Math.round(v).toLocaleString("ko-KR");
}

/** Fixed-size stacked-area renderer — named export for tests. */
export function ExposureStackSvg({
  width,
  height,
  points,
  symbols,
}: {
  width: number;
  height: number;
  points: ExposurePoint[];
  symbols: string[];
}) {
  const margin = { top: 8, right: 8, bottom: 24, left: 52 };
  const innerW = Math.max(0, width - margin.left - margin.right);
  const innerH = Math.max(0, height - margin.top - margin.bottom);

  const xScale = scaleTime({
    domain: [
      new Date(points[0].trade_date),
      new Date(points[points.length - 1].trade_date),
    ],
    range: [0, innerW],
  });
  const maxTotal = Math.max(
    1,
    ...points.map((p) =>
      symbols.reduce((sum, s) => sum + (Number(p[s]) || 0), 0),
    ),
  );
  const yScale = scaleLinear({
    domain: [0, maxTotal],
    range: [innerH, 0],
    nice: true,
  });
  const color = scaleOrdinal({ domain: symbols, range: PALETTE });

  return (
    <svg width={width} height={height}>
      <Group left={margin.left} top={margin.top}>
        <AreaStack
          keys={symbols}
          data={points}
          x={(d) => xScale(new Date(d.data.trade_date)) ?? 0}
          y0={(d) => yScale(d[0]) ?? 0}
          y1={(d) => yScale(d[1]) ?? 0}
          value={(d, key) => Number(d[key]) || 0}
        >
          {({ stacks, path }) =>
            stacks.map((stack) => (
              <path
                key={`stack-${stack.key}`}
                d={path(stack) || ""}
                fill={color(stack.key)}
                fillOpacity={0.75}
                stroke="#fff"
                strokeWidth={0.3}
              />
            ))
          }
        </AreaStack>
        <AxisLeft
          scale={yScale}
          numTicks={4}
          tickFormat={(v) => fmtKrwTick(Number(v))}
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

/** Gross exposure by symbol over time — surfaces concentration build-up. */
export default function ExposureHistoryChart({
  data,
}: {
  data: ExposureHistory | undefined;
}) {
  const ready =
    data?.status === "ok" && data.points.length > 0 && data.symbols.length > 0;
  return (
    <ChartCard
      title="심볼별 노출 추이"
      subtitle="일별 총노출(|수량|×현재가) 누적 · 집중위험 관찰"
      isEmpty={!ready}
      emptyLabel={EMPTY_LABEL}
    >
      <ParentSize>
        {({ width, height }) =>
          ready && width > 0 && height > 0 ? (
            <ExposureStackSvg
              width={width}
              height={height}
              points={data.points}
              symbols={data.symbols}
            />
          ) : null
        }
      </ParentSize>
    </ChartCard>
  );
}
