"use client";

// 트랙 A 상시 라벨 (roadmap §5.3) — Phase 2 shadow/Phase 4 advisory 라벨
// 관행(amber dashed)과 동일 톤. 트랙 A는 수동 트랙: Tier 3 워치·코어 홀딩스
// 카드는 어떤 매매 컨트롤도 제공하지 않는다.
export default function ManualTrackLabel() {
  return (
    <span className="inline-flex items-center rounded border border-dashed border-amber-400 bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
      수동 트랙 — 자동 매매 없음
    </span>
  );
}
