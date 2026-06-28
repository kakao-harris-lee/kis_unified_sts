"use client";

import type { ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  Loader2,
  RefreshCw,
  X,
} from "lucide-react";

import SideBadge from "@/components/dashboard/SideBadge";
import { formatKstDateTime } from "@/lib/dashboard/format";
import type {
  DecisionTraceEvidenceGap,
  DecisionTraceResponse,
} from "@/lib/dashboard/decisionTrace";
import type { TradeLifecycleStep } from "@/lib/dashboard/trades";

interface DecisionTracePanelProps {
  trace?: DecisionTraceResponse;
  isLoading?: boolean;
  error?: string | null;
  onClose: () => void;
  onRefresh: () => void;
}

function displayValue(value: unknown, fallback = "not available"): string {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString() : fallback;
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function displayPercent(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "unknown";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function displaySigned(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "unknown";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

const formatKst = (value?: string | null): string => formatKstDateTime(value);

function scoreResult(correct?: boolean | null): string {
  if (correct === null || correct === undefined) {
    return "unscorable";
  }
  return correct ? "correct" : "missed";
}

function stepTone(step: TradeLifecycleStep): string {
  if (step.source === "not_available") {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  if (["rejected", "blocked", "error", "failed"].includes(step.status)) {
    return "border-red-200 bg-red-50 text-red-700";
  }
  if (["missing", "not_available", "partial", "unknown"].includes(step.status)) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function StepIcon({ step }: { step: TradeLifecycleStep }) {
  const className = "h-4 w-4 shrink-0";
  if (
    step.source === "not_available" ||
    ["missing", "not_available", "partial", "unknown"].includes(step.status)
  ) {
    return <CircleHelp className={className} aria-hidden="true" />;
  }
  if (["rejected", "blocked", "error", "failed"].includes(step.status)) {
    return <AlertTriangle className={className} aria-hidden="true" />;
  }
  return <CheckCircle2 className={className} aria-hidden="true" />;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3">
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Field({
  label,
  value,
  fallback = "not available",
}: {
  label: string;
  value: unknown;
  fallback?: string;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[11px] font-medium uppercase text-slate-500">
        {label}
      </div>
      <div className="mt-1 break-words text-sm font-semibold text-slate-900">
        {displayValue(value, fallback)}
      </div>
    </div>
  );
}

function GapAlert({ gap }: { gap: DecisionTraceEvidenceGap }) {
  const tone =
    gap.severity === "error"
      ? "border-red-200 bg-red-50 text-red-700"
      : gap.severity === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-700"
        : "border-slate-200 bg-slate-50 text-slate-700";

  return (
    <div role="alert" className={`rounded border px-3 py-2 text-xs ${tone}`}>
      <div className="break-words font-semibold">{gap.code}</div>
      <div className="mt-1 break-words">{gap.message}</div>
    </div>
  );
}

function LifecycleStep({ step }: { step: TradeLifecycleStep }) {
  return (
    <div className={`rounded border px-3 py-2 text-sm ${stepTone(step)}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <StepIcon step={step} />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="break-words font-semibold">{step.label}</span>
              <span className="rounded bg-white/70 px-2 py-0.5 text-[11px] font-medium uppercase">
                {step.status}
              </span>
            </div>
            <div className="mt-0.5 break-words text-xs">
              {displayValue(step.summary || step.id, "not available")}
            </div>
          </div>
        </div>
        <div className="shrink-0 text-right text-xs">
          <div className="font-medium">{formatKst(step.timestamp)}</div>
          <div className="text-slate-500">{step.source}</div>
        </div>
      </div>
    </div>
  );
}

export default function DecisionTracePanel({
  trace,
  isLoading = false,
  error = null,
  onClose,
  onRefresh,
}: DecisionTracePanelProps) {
  const headerText = trace?.signal.symbol || trace?.signal.id || "No signal selected";

  return (
    <section
      role="region"
      aria-label="Decision Trace"
      className="rounded-lg border border-slate-200 bg-slate-50 p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <Clock3 className="h-4 w-4 text-slate-500" aria-hidden="true" />
            <span>Decision Trace</span>
          </div>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-2">
            <span className="break-words text-lg font-bold text-slate-950">
              {headerText}
            </span>
            {trace?.signal.id && trace.signal.id !== trace.signal.symbol ? (
              <span className="break-words rounded bg-white px-2 py-0.5 text-xs font-medium text-slate-500">
                {trace.signal.id}
              </span>
            ) : null}
            {trace ? <SideBadge side={trace.signal.side} /> : null}
            {trace ? (
              <span className="break-words rounded bg-white px-2 py-0.5 text-xs font-medium text-slate-600">
                {trace.summary.state}
              </span>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onRefresh}
            aria-label="Refresh decision trace"
            title="Refresh decision trace"
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close decision trace"
            title="Close decision trace"
            className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 bg-white text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      {isLoading ? (
        <div
          role="status"
          className="mt-4 flex items-center gap-2 text-sm text-slate-500"
        >
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading decision trace
        </div>
      ) : error ? (
        <div
          role="alert"
          className="mt-4 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
        >
          <span className="break-words">{error}</span>
        </div>
      ) : trace ? (
        <div className="mt-4 space-y-3">
          <Section title="Summary">
            <div className="space-y-3">
              <div className="break-words text-sm text-slate-700">
                {trace.summary.text}
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="State" value={trace.summary.state} fallback="unknown" />
                <Field label="Status" value={trace.signal.status} fallback="unknown" />
                <Field label="Signal Time KST" value={formatKst(trace.signal.timestamp)} />
                <Field label="Strategy" value={trace.signal.strategy} />
                <Field label="Type" value={trace.signal.signal_type} fallback="unknown" />
                <Field label="Confidence" value={displayPercent(trace.signal.confidence)} />
                <Field label="Price" value={trace.signal.price} />
              </div>
              {trace.summary.warnings.length > 0 ? (
                <div className="break-words rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  {trace.summary.warnings.join(", ")}
                </div>
              ) : null}
            </div>
          </Section>

          <Section title="LLM Context">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Status" value={trace.llm_context.status} fallback="unknown" />
              <Field label="Overall Signal" value={trace.llm_context.overall_signal} fallback="unknown" />
              <Field label="Confidence" value={displayPercent(trace.llm_context.confidence)} />
              <Field label="Risk Mode" value={trace.llm_context.risk_mode} fallback="unknown" />
              <Field label="Regime" value={trace.llm_context.regime} fallback="unknown" />
              <Field label="Risk Score" value={trace.llm_context.risk_score} />
              <Field label="Captured KST" value={formatKst(trace.llm_context.captured_at)} />
              <Field label="Source" value={trace.llm_context.source} />
            </div>
          </Section>

          <Section title="Strategy Inputs">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Setup" value={trace.strategy_inputs.setup_type} />
              <Field label="Reason" value={trace.strategy_inputs.raw_reason} />
              <Field label="Indicators" value={trace.strategy_inputs.indicators} />
              <Field label="Thresholds" value={trace.strategy_inputs.thresholds} />
              <Field label="Event Evidence" value={trace.strategy_inputs.event_evidence} />
            </div>
          </Section>

          <Section title="Risk And Orderability">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Orderability" value={trace.risk_orderability.orderability_state} fallback="unknown" />
              <Field label="Risk State" value={trace.risk_orderability.risk_state} fallback="unknown" />
              <Field label="Reject Stage" value={trace.risk_orderability.reject_stage} fallback="unknown" />
              <Field label="Reject Reason" value={trace.risk_orderability.reject_reason} />
              <Field label="Order Details" value={trace.risk_orderability.orderability_details} />
              <Field label="Risk Details" value={trace.risk_orderability.risk_details} />
            </div>
          </Section>

          <Section title="Lifecycle">
            <div className="space-y-3">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Field label="Status" value={trace.lifecycle.status} fallback="unknown" />
                <Field label="Signal ID" value={trace.lineage.signal_id} />
                <Field label="Order ID" value={trace.lineage.order_id} />
                <Field label="Fill ID" value={trace.lineage.fill_id} />
                <Field label="Position ID" value={trace.lineage.position_id} />
                <Field label="Trade ID" value={trace.lineage.trade_id} />
              </div>
              {trace.lifecycle.steps.length > 0 ? (
                <div className="space-y-2">
                  {trace.lifecycle.steps.map((step) => (
                    <LifecycleStep key={`${step.stage}:${step.id ?? step.status}`} step={step} />
                  ))}
                </div>
              ) : (
                <div className="break-words rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  {trace.lifecycle.status}
                </div>
              )}
              {trace.lifecycle.warnings.length > 0 ? (
                <div className="break-words rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                  {trace.lifecycle.warnings.join(", ")}
                </div>
              ) : null}
            </div>
          </Section>

          <Section title="Scorecard Evidence">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Status" value={trace.scorecard.status} fallback="unknown" />
              <Field label="Facet" value={trace.scorecard.facet} fallback="unknown" />
              <Field label="Date KST" value={trace.scorecard.date_kst} />
              <Field label="Captured KST" value={formatKst(trace.scorecard.captured_at)} />
              <Field label="Confidence" value={displayPercent(trace.scorecard.confidence)} />
              <Field label="Result" value={scoreResult(trace.scorecard.correct)} />
              <Field label="Value" value={trace.scorecard.value} />
              <Field label="Economic Proxy" value={trace.scorecard.economic_proxy} />
              <Field label="Baseline" value={trace.scorecard.baseline_value} />
              <Field label="Edge" value={displaySigned(trace.scorecard.edge)} />
              <Field label="Scored KST" value={formatKst(trace.scorecard.scored_at)} />
              <Field label="Detail" value={trace.scorecard.detail} />
            </div>
          </Section>

          <Section title="Evidence Gaps">
            {trace.evidence_gaps.length > 0 ? (
              <div className="space-y-2">
                {trace.evidence_gaps.map((gap) => (
                  <GapAlert key={`${gap.severity}:${gap.code}`} gap={gap} />
                ))}
              </div>
            ) : (
              <div className="text-sm font-medium text-slate-600">none</div>
            )}
          </Section>
        </div>
      ) : (
        <div className="mt-4 text-sm text-slate-500">
          Select a signal to inspect decision evidence.
        </div>
      )}
    </section>
  );
}
