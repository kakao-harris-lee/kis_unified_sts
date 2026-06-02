"use client";

import { Check, AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import type { StageStatus } from "@/lib/builder/stageStatus";

interface FunnelStageProps {
  id: string;
  stepNum: number;
  title: string;
  status: StageStatus;
  showConnector?: boolean;
  children: ReactNode;
}

export function FunnelStage({
  id,
  stepNum,
  title,
  status,
  showConnector = true,
  children,
}: FunnelStageProps) {
  return (
    <section id={`stage-${id}`} aria-label={title} className="scroll-mt-24">
      <div className="card">
        <div className="flex items-center gap-2 mb-4 pb-3 border-b border-slate-100 dark:border-slate-700">
          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-primary/10 text-primary text-xs font-semibold flex-shrink-0">
            {stepNum}
          </span>
          <h2 className="text-subheading text-slate-900 dark:text-white flex-1">{title}</h2>
          <StatusChip status={status} />
        </div>
        {children}
      </div>
      {showConnector && (
        <div className="flex justify-center py-1" aria-hidden="true">
          <div className="w-px h-4 bg-gradient-to-b from-slate-300 to-transparent dark:from-slate-600" />
        </div>
      )}
    </section>
  );
}

function StatusChip({ status }: { status: StageStatus }) {
  if (status === "complete") {
    return (
      <span
        data-testid="stage-status-complete"
        className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400"
      >
        <Check className="w-3.5 h-3.5" aria-hidden="true" /> 완료
      </span>
    );
  }
  if (status === "warning") {
    return (
      <span
        data-testid="stage-status-warning"
        className="inline-flex items-center gap-1 text-xs font-medium text-amber-600 dark:text-amber-400"
      >
        <AlertTriangle className="w-3.5 h-3.5" aria-hidden="true" /> 조건 없음
      </span>
    );
  }
  return (
    <span
      data-testid="stage-status-empty"
      className="inline-flex items-center gap-1 text-xs font-medium text-slate-400 dark:text-slate-500"
    >
      비어있음
    </span>
  );
}
