"use client";

import { Check, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { StageId, StageStatus } from "@/lib/builder/stageStatus";

export interface StageRailItem {
  id: StageId;
  stepNum: number;
  shortLabel: string;
  status: StageStatus;
}

interface StageRailProps {
  stages: StageRailItem[];
  activeId: StageId | null;
  onJump: (id: StageId) => void;
}

export function StageRail({ stages, activeId, onJump }: StageRailProps) {
  return (
    <nav
      aria-label="전략 빌더 단계"
      className="hidden lg:flex flex-col gap-1 sticky top-20 self-start"
    >
      {stages.map((s) => {
        const isActive = s.id === activeId;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onJump(s.id)}
            aria-current={isActive ? "step" : undefined}
            className={cn(
              "flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors text-left focus-ring whitespace-nowrap",
              isActive && "bg-primary/10 text-primary",
              !isActive &&
                s.status === "complete" &&
                "text-emerald-600 dark:text-emerald-400 hover:bg-slate-50 dark:hover:bg-slate-800",
              !isActive &&
                s.status === "warning" &&
                "text-amber-600 dark:text-amber-400 hover:bg-slate-50 dark:hover:bg-slate-800",
              !isActive &&
                s.status === "empty" &&
                "text-slate-400 dark:text-slate-500 hover:bg-slate-50 dark:hover:bg-slate-800",
            )}
          >
            {s.status === "complete" ? (
              <Check className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
            ) : s.status === "warning" ? (
              <AlertTriangle className="w-3 h-3 flex-shrink-0" aria-hidden="true" />
            ) : (
              <span className="w-3 text-center flex-shrink-0">{s.stepNum}</span>
            )}
            <span>{s.shortLabel}</span>
          </button>
        );
      })}
    </nav>
  );
}
