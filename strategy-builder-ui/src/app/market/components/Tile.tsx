"use client";

// 공용 수치 타일 — /market 카드들(헤지 어드바이저, Tier 3 워치)이 공유하는
// label/value/sub 스탯 타일. 값 텍스트는 텍스트 토큰을 기본으로 하고, 상태
// 강조가 필요할 때만 tone으로 덮어쓴다 (색상 단독 의미 전달 금지 — 라벨 병기).
export default function Tile({
  label,
  value,
  sub,
  tone,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
      <div className="text-xs font-medium text-slate-500 dark:text-slate-400">
        {label}
      </div>
      <div
        className={`mt-1 truncate text-lg font-bold tabular-nums ${
          tone ?? "text-slate-900 dark:text-slate-100"
        }`}
      >
        {value}
      </div>
      {sub && <div className="text-[11px] text-slate-400">{sub}</div>}
    </div>
  );
}
