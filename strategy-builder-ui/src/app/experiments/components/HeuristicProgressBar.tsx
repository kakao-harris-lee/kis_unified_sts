"use client";

import { useEffect, useState } from "react";

// The backend job manager exposes only a binary status (running/done), no true
// step progress. This bar is an ELAPSED-TIME HEURISTIC — it approaches (but
// never reaches) 100% asymptotically so it reads as "working" without
// implying a real completion percentage. Labeled 예상 to stay honest.
const EXPECTED_SECONDS = 180; // rough backtest duration; only sets the curve slope

export default function HeuristicProgressBar({
  startedAt,
}: {
  startedAt: string | null | undefined;
}) {
  const [pct, setPct] = useState(5);

  useEffect(() => {
    if (!startedAt) return;
    const start = new Date(startedAt).getTime();
    if (Number.isNaN(start)) return;

    const tick = () => {
      const elapsed = (Date.now() - start) / 1000;
      // Asymptotic: 1 - e^(-t/EXPECTED) caps below 100%, clamped to [5, 95].
      const raw = (1 - Math.exp(-elapsed / EXPECTED_SECONDS)) * 100;
      setPct(Math.min(95, Math.max(5, raw)));
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [startedAt]);

  return (
    <div
      className="flex items-center gap-2"
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label="백테스트 진행(예상)"
    >
      <div className="h-1.5 w-32 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-700">
        <div
          className="h-full rounded-full bg-primary transition-[width] duration-1000 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-slate-400">예상 {Math.round(pct)}%</span>
    </div>
  );
}
