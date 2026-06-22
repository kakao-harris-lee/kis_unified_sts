"use client";

import { useId } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Loader2,
  X,
} from "lucide-react";
import type {
  TradeLifecycleResponse,
  TradeLifecycleStep,
} from "@/lib/dashboard/trades";

interface LifecycleTimelineProps {
  data?: TradeLifecycleResponse;
  isLoading?: boolean;
  error?: string | null;
  title?: string;
  onRetry?: () => void;
  onClose?: () => void;
}

function formatTime(value?: string | null): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatValue(value: string | number | boolean | null): string {
  if (value === null) return "-";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return Number.isFinite(value) ? value.toLocaleString() : "-";
  return value || "-";
}

function stepTone(step: TradeLifecycleStep): string {
  if (step.source === "not_available") {
    return step.status === "unknown"
      ? "border-amber-300 bg-amber-50 text-amber-700"
      : "border-slate-200 bg-slate-50 text-slate-500";
  }
  if (["rejected", "blocked", "error", "failed"].includes(step.status)) {
    return "border-red-300 bg-red-50 text-red-700";
  }
  if (["unknown", "not_available"].includes(step.status)) {
    return "border-amber-300 bg-amber-50 text-amber-700";
  }
  return "border-emerald-300 bg-emerald-50 text-emerald-700";
}

function StepIcon({ step }: { step: TradeLifecycleStep }) {
  const className = "h-4 w-4";
  if (step.source === "not_available" || ["unknown", "not_available"].includes(step.status)) {
    return <CircleHelp className={className} aria-hidden="true" />;
  }
  if (["rejected", "blocked", "error", "failed"].includes(step.status)) {
    return <AlertTriangle className={className} aria-hidden="true" />;
  }
  return <CheckCircle2 className={className} aria-hidden="true" />;
}

function DetailList({ step }: { step: TradeLifecycleStep }) {
  const entries = Object.entries(step.details)
    .filter(([, value]) => value !== null && value !== "")
    .slice(0, 6);

  if (entries.length === 0) {
    return null;
  }

  return (
    <div className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-slate-500 sm:grid-cols-3">
      {entries.map(([key, value]) => (
        <div key={key} className="min-w-0">
          <span className="mr-1 text-slate-400">{key}</span>
          <span className="font-medium text-slate-700">{formatValue(value)}</span>
        </div>
      ))}
    </div>
  );
}

export default function LifecycleTimeline({
  data,
  isLoading,
  error,
  title = "Lifecycle",
  onRetry,
  onClose,
}: LifecycleTimelineProps) {
  const titleId = useId();

  return (
    <section
      role="region"
      aria-labelledby={titleId}
      aria-live="polite"
      className="rounded-lg border border-slate-200 bg-white p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-slate-500" aria-hidden="true" />
            <h3 id={titleId} className="text-base font-semibold text-slate-900">{title}</h3>
          </div>
          {data ? (
            <div className="mt-1 text-xs text-slate-500">
              as of {formatTime(data.as_of)} - {data.asset_class}
            </div>
          ) : null}
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="Close lifecycle panel"
            title="Close lifecycle panel"
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-slate-500 hover:bg-slate-50 hover:text-slate-900"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        ) : null}
      </div>

      {isLoading ? (
        <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading lifecycle
        </div>
      ) : error ? (
        <div
          role="alert"
          className="mt-4 flex items-center justify-between gap-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          <span className="min-w-0 flex-1 break-words">{error}</span>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="rounded border border-red-200 bg-white px-2 py-1 text-xs font-medium hover:bg-red-100"
            >
              Retry
            </button>
          ) : null}
        </div>
      ) : data ? (
        <div className="mt-4 space-y-3">
          {data.steps.map((step) => (
            <div
              key={step.stage}
              className={`rounded border px-3 py-2 ${stepTone(step)}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <StepIcon step={step} />
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold">{step.label}</span>
                      <span className="rounded bg-white/70 px-2 py-0.5 text-[11px] font-medium uppercase">
                        {step.status}
                      </span>
                    </div>
                    <div className="mt-0.5 break-words text-xs">
                      {step.summary || step.id || "-"}
                    </div>
                  </div>
                </div>
                <div className="text-right text-xs">
                  <div className="font-medium">{formatTime(step.timestamp)}</div>
                  <div className="text-slate-400">{step.source}</div>
                </div>
              </div>
              <DetailList step={step} />
            </div>
          ))}
          {data.warnings.length > 0 ? (
            <div
              role="alert"
              className="break-words rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700"
            >
              {data.warnings.join(", ")}
            </div>
          ) : null}
        </div>
      ) : (
        <div className="mt-4 text-sm text-slate-500">Select a row to inspect lifecycle.</div>
      )}
    </section>
  );
}
