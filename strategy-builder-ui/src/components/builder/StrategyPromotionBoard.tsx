"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Circle,
  Columns3,
  Loader2,
  Lock,
  XCircle,
  type LucideIcon,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { BuilderState, StoredStrategy } from "@/types/builder";
import {
  getStrategyPromotionSources,
  type PromotionActivity,
  type PromotionExperimentSummary,
  type PromotionPaperComparison,
  type PromotionPaperComparisonRow,
  type PromotionRegisteredStrategy,
  type StrategyPromotionSources,
} from "@/lib/dashboard/strategyBuilder";

export interface PromotionPresetStrategy {
  id: string;
  name: string;
  description?: string;
  category?: string;
  state: BuilderState;
}

interface StrategyPromotionBoardProps {
  localStrategies: StoredStrategy[];
  presetStrategies: PromotionPresetStrategy[];
  refreshSignal?: number;
}

type PromotionColumnId =
  | "draft"
  | "validated"
  | "backtested"
  | "swept"
  | "paper_enabled"
  | "paper_observed"
  | "live_gated";

type EvidenceStatus = "present" | "missing" | "not_available";

interface EvidenceItem {
  key: string;
  label: string;
  status: EvidenceStatus;
  detail: string;
}

interface PromotionSeed {
  id: string;
  name: string;
  description?: string | null;
  assetClass?: string;
  state?: BuilderState;
  registered?: PromotionRegisteredStrategy;
  activity?: PromotionActivity;
  summary?: PromotionExperimentSummary;
  comparison?: PromotionPaperComparisonRow;
  origins: Set<string>;
}

interface PromotionCard {
  id: string;
  name: string;
  description?: string | null;
  assetClass: string;
  column: PromotionColumnId;
  origins: string[];
  evidence: EvidenceItem[];
  metrics: string[];
  artifactLinks: Array<{ href: string; label: string }>;
}

const EMPTY_SOURCES: StrategyPromotionSources = {
  registered: [],
  activity: [],
  latestReport: null,
  paperComparison: null,
  sourceErrors: [],
};

const COLUMNS: Array<{
  id: PromotionColumnId;
  title: string;
  empty: string;
}> = [
  {
    id: "draft",
    title: "Draft",
    empty: "No incomplete local drafts.",
  },
  {
    id: "validated",
    title: "Validated",
    empty: "No validation-only strategies.",
  },
  {
    id: "backtested",
    title: "Backtested",
    empty: "No strategies with backtest-only evidence.",
  },
  {
    id: "swept",
    title: "Swept",
    empty: "No explicit sweep/operator-hold strategies.",
  },
  {
    id: "paper_enabled",
    title: "Paper Enabled",
    empty: "No enabled paper strategies waiting for observation.",
  },
  {
    id: "paper_observed",
    title: "Paper Observed",
    empty: "No paper trade evidence yet.",
  },
  {
    id: "live_gated",
    title: "Live Gated",
    empty: "Display-only. No live approval evidence source is available.",
  },
];

const STATUS_STYLES: Record<EvidenceStatus, { className: string; Icon: LucideIcon }> = {
  present: {
    Icon: CheckCircle2,
    className:
      "border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/60 dark:bg-emerald-900/25 dark:text-emerald-300",
  },
  missing: {
    Icon: XCircle,
    className:
      "border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-900/60 dark:bg-amber-900/25 dark:text-amber-300",
  },
  not_available: {
    Icon: Circle,
    className:
      "border-slate-200 bg-slate-50 text-slate-500 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400",
  },
};

function linkKey(state: BuilderState | undefined, fallback: string): string {
  return (state?.metadata.id || "").trim() || fallback;
}

function upsertSeed(
  seeds: Map<string, PromotionSeed>,
  id: string,
  patch: Partial<Omit<PromotionSeed, "id" | "origins">> & { origin: string },
): PromotionSeed {
  const seed = seeds.get(id) ?? {
    id,
    name: id,
    assetClass: "unknown",
    origins: new Set<string>(),
  };
  seed.origins.add(patch.origin);
  seed.name = patch.name ?? seed.name;
  seed.description = patch.description ?? seed.description;
  seed.assetClass = patch.assetClass ?? seed.assetClass;
  seed.state = patch.state ?? seed.state;
  seed.registered = patch.registered ?? seed.registered;
  seed.activity = patch.activity ?? seed.activity;
  seed.summary = patch.summary ?? seed.summary;
  seed.comparison = patch.comparison ?? seed.comparison;
  seeds.set(id, seed);
  return seed;
}

function hasConditions(state: BuilderState): boolean {
  return state.entry.conditions.length > 0 && state.exit.conditions.length > 0;
}

function validationEvidence(state: BuilderState | undefined): EvidenceItem {
  if (!state) {
    return {
      key: "validation",
      label: "validation",
      status: "not_available",
      detail: "builder state not available",
    };
  }

  const valid = Boolean(state.metadata.name.trim()) && hasConditions(state);
  return {
    key: "validation",
    label: "validation",
    status: valid ? "present" : "missing",
    detail: valid ? "builder conditions complete" : "metadata or entry/exit conditions missing",
  };
}

function backtestEvidence(seed: PromotionSeed): EvidenceItem {
  const closedTrades =
    seed.comparison?.backtest.closed_trades ?? seed.summary?.closed_trades ?? null;
  if (typeof closedTrades === "number" && closedTrades > 0) {
    return {
      key: "backtest",
      label: "backtest",
      status: "present",
      detail: `${closedTrades} closed backtest trades`,
    };
  }
  if (seed.assetClass === "futures") {
    return {
      key: "backtest",
      label: "backtest",
      status: "not_available",
      detail: "latest experiment source is stock-only",
    };
  }
  return {
    key: "backtest",
    label: "backtest",
    status: "missing",
    detail: "latest experiment has no closed-trade evidence",
  };
}

type RiskControl = { enabled?: boolean; percent?: number };
type MaybeSnakeRisk = BuilderState["risk"] & {
  stop_loss?: RiskControl;
  take_profit?: RiskControl;
  trailing_stop?: RiskControl;
};

function riskEvidence(state: BuilderState | undefined): EvidenceItem {
  if (!state) {
    return {
      key: "risk",
      label: "risk",
      status: "not_available",
      detail: "risk config not exposed by this source",
    };
  }

  const risk = state.risk as MaybeSnakeRisk;
  const stopLoss = risk.stopLoss ?? risk.stop_loss;
  const takeProfit = risk.takeProfit ?? risk.take_profit;
  const trailingStop = risk.trailingStop ?? risk.trailing_stop;
  const controls = [
    stopLoss?.enabled && stopLoss.percent ? `SL ${stopLoss.percent}%` : null,
    takeProfit?.enabled && takeProfit.percent ? `TP ${takeProfit.percent}%` : null,
    trailingStop?.enabled && trailingStop.percent ? `trail ${trailingStop.percent}%` : null,
  ].filter((item): item is string => Boolean(item));

  return {
    key: "risk",
    label: "risk",
    status: controls.length > 0 ? "present" : "missing",
    detail: controls.length > 0 ? controls.join(", ") : "no explicit risk control enabled",
  };
}

function paperEvidence(
  seed: PromotionSeed,
  paperComparison: PromotionPaperComparison | null,
): EvidenceItem {
  const minPaperTrades = paperComparison?.source.min_paper_trades ?? 1;
  const comparisonTrades = seed.comparison?.paper.trade_count ?? 0;
  const activityTrades = seed.activity?.trades ?? 0;
  const activitySignals = seed.activity?.signals ?? 0;
  const paperTrades = Math.max(comparisonTrades, activityTrades);

  if (paperTrades > 0) {
    const thresholdDetail =
      comparisonTrades > 0 ? `comparison min ${minPaperTrades}` : "activity count";
    return {
      key: "paper",
      label: "paper",
      status: "present",
      detail: `${paperTrades} paper trades (${thresholdDetail})`,
    };
  }

  if (
    seed.comparison?.missing_evidence.includes("runtime_ledger") ||
    paperComparison?.missing_evidence.includes("runtime_ledger")
  ) {
    return {
      key: "paper",
      label: "paper",
      status: "not_available",
      detail: "runtime ledger evidence unavailable",
    };
  }

  return {
    key: "paper",
    label: "paper",
    status: "missing",
    detail:
      activitySignals > 0
        ? `${activitySignals} paper signals, no paper trades`
        : "no paper trade evidence",
  };
}

function operatorEvidence(seed: PromotionSeed): EvidenceItem {
  if (!seed.registered) {
    return {
      key: "operator",
      label: "operator gate",
      status: "missing",
      detail: "no paper registration",
    };
  }

  return {
    key: "operator",
    label: "operator gate",
    status: seed.registered.enabled ? "present" : "missing",
    detail: seed.registered.enabled
      ? "paper registration enabled"
      : "paper registration present, disabled",
  };
}

function sweepEvidence(): EvidenceItem {
  return {
    key: "sweep",
    label: "sweep",
    status: "not_available",
    detail: "no sweep artifact source",
  };
}

function chooseColumn(
  seed: PromotionSeed,
  evidenceByKey: Record<string, EvidenceItem>,
): PromotionColumnId {
  if (evidenceByKey.paper.status === "present") return "paper_observed";
  if (seed.registered?.enabled) return "paper_enabled";
  if (seed.registered) return "swept";
  if (evidenceByKey.backtest.status === "present") return "backtested";
  if (evidenceByKey.validation.status === "present") return "validated";
  return "draft";
}

function formatPct(value: number | null | undefined): string | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function buildMetrics(seed: PromotionSeed): string[] {
  const metrics: string[] = [];
  const totalReturn = formatPct(
    seed.comparison?.backtest.total_return_pct ?? seed.summary?.total_return_pct,
  );
  if (totalReturn) metrics.push(`BT ${totalReturn}`);
  const winRate = formatPct(seed.comparison?.paper.win_rate_pct);
  if (winRate) metrics.push(`Paper WR ${winRate}`);
  if (seed.activity) {
    metrics.push(`signals ${seed.activity.signals}`);
    metrics.push(`trades ${seed.activity.trades}`);
  }
  return metrics;
}

function buildCards(
  localStrategies: StoredStrategy[],
  presetStrategies: PromotionPresetStrategy[],
  sources: StrategyPromotionSources,
): PromotionCard[] {
  const seeds = new Map<string, PromotionSeed>();
  const activityById = new Map(sources.activity.map((item) => [item.id, item]));

  for (const strategy of localStrategies) {
    const id = linkKey(strategy.state, strategy.id);
    upsertSeed(seeds, id, {
      origin: "local draft",
      name: strategy.name,
      description: strategy.state.metadata.description,
      assetClass: strategy.state.assetClass,
      state: strategy.state,
    });
  }

  for (const preset of presetStrategies) {
    const id = linkKey(preset.state, preset.id);
    upsertSeed(seeds, id, {
      origin: "preset",
      name: preset.name,
      description: preset.description,
      assetClass: preset.state.assetClass,
      state: preset.state,
    });
  }

  for (const registered of sources.registered) {
    upsertSeed(seeds, registered.id, {
      origin: "paper registration",
      name: registered.name,
      description: registered.description,
      assetClass: registered.asset_class,
      registered,
      activity: activityById.get(registered.id),
    });
  }

  for (const summary of sources.latestReport?.summaries ?? []) {
    const id = summary.strategy_id || summary.strategy_name || "";
    if (!id) continue;
    upsertSeed(seeds, id, {
      origin: "experiment",
      name: summary.strategy_name ?? id,
      assetClass: "stock",
      summary,
    });
  }

  for (const comparison of sources.paperComparison?.comparisons ?? []) {
    if (!comparison.strategy_id) continue;
    upsertSeed(seeds, comparison.strategy_id, {
      origin: "paper comparison",
      name: comparison.strategy_name ?? comparison.strategy_id,
      assetClass: "stock",
      comparison,
    });
  }

  return [...seeds.values()]
    .map((seed) => {
      const evidence = [
        validationEvidence(seed.state),
        backtestEvidence(seed),
        sweepEvidence(),
        paperEvidence(seed, sources.paperComparison),
        riskEvidence(seed.state),
        operatorEvidence(seed),
      ];
      const evidenceByKey = Object.fromEntries(
        evidence.map((item) => [item.key, item]),
      ) as Record<string, EvidenceItem>;
      const artifactLinks: Array<{ href: string; label: string }> = [];
      if (seed.summary || seed.comparison) {
        artifactLinks.push({ href: "/experiments", label: "experiment evidence" });
      }
      return {
        id: seed.id,
        name: seed.name,
        description: seed.description,
        assetClass: seed.assetClass ?? "unknown",
        column: chooseColumn(seed, evidenceByKey),
        origins: [...seed.origins].sort(),
        evidence,
        metrics: buildMetrics(seed),
        artifactLinks,
      };
    })
    .sort((a, b) => a.name.localeCompare(b.name));
}

function EvidencePill({ item }: { item: EvidenceItem }) {
  const { Icon, className } = STATUS_STYLES[item.status];
  return (
    <span
      className={cn(
        "inline-flex max-w-full items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium",
        className,
      )}
      title={item.detail}
      aria-label={`${item.label}: ${item.status}. ${item.detail}`}
    >
      <Icon className="h-3 w-3 flex-shrink-0" aria-hidden="true" />
      <span className="truncate">
        {item.label} {item.status}
      </span>
    </span>
  );
}

function StrategyCard({ card }: { card: PromotionCard }) {
  return (
    <article className="rounded-md border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">
            {card.name}
          </h4>
          <div className="mt-1 flex flex-wrap gap-1">
            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              {card.assetClass}
            </span>
            {card.origins.map((origin) => (
              <span
                key={origin}
                className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] font-medium text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
              >
                {origin}
              </span>
            ))}
          </div>
        </div>
      </div>

      {card.description ? (
        <p className="mt-2 line-clamp-2 text-xs text-slate-500 dark:text-slate-400">
          {card.description}
        </p>
      ) : null}

      <div className="mt-3 flex flex-wrap gap-1">
        {card.evidence.map((item) => (
          <EvidencePill key={item.key} item={item} />
        ))}
      </div>

      {card.metrics.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1 text-[10px] text-slate-500 dark:text-slate-400">
          {card.metrics.map((metric) => (
            <span key={metric} className="rounded bg-slate-50 px-1.5 py-0.5 dark:bg-slate-800">
              {metric}
            </span>
          ))}
        </div>
      ) : null}

      {card.artifactLinks.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
          {card.artifactLinks.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="font-medium text-blue-600 hover:text-blue-700 dark:text-blue-300 dark:hover:text-blue-200"
            >
              {link.label}
            </a>
          ))}
        </div>
      ) : null}
    </article>
  );
}

export function StrategyPromotionBoard({
  localStrategies,
  presetStrategies,
  refreshSignal = 0,
}: StrategyPromotionBoardProps) {
  const [sources, setSources] = useState<StrategyPromotionSources>(EMPTY_SOURCES);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    getStrategyPromotionSources()
      .then((nextSources) => {
        if (alive) setSources(nextSources);
      })
      .catch((error: unknown) => {
        if (!alive) return;
        setSources({
          ...EMPTY_SOURCES,
          sourceErrors: [error instanceof Error ? error.message : String(error)],
        });
      })
      .finally(() => {
        if (alive) setIsLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [refreshSignal]);

  const cards = useMemo(
    () => buildCards(localStrategies, presetStrategies, sources),
    [localStrategies, presetStrategies, sources],
  );

  const cardsByColumn = useMemo(() => {
    const grouped = new Map<PromotionColumnId, PromotionCard[]>();
    for (const column of COLUMNS) grouped.set(column.id, []);
    for (const card of cards) grouped.get(card.column)?.push(card);
    return grouped;
  }, [cards]);

  return (
    <section className="mt-8">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
            <Columns3 className="h-5 w-5 text-primary" aria-hidden="true" />
            Strategy Promotion Kanban
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
            <span>read-only</span>
            <span>paper-safe</span>
            <span className="inline-flex items-center gap-1">
              <Lock className="h-3 w-3" aria-hidden="true" />
              live readiness not inferred
            </span>
          </div>
        </div>
        <div className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs text-slate-500 dark:border-slate-700 dark:text-slate-400">
          {isLoading ? (
            <span
              role="status"
              aria-label="Loading promotion evidence"
              className="inline-flex items-center gap-1"
            >
              <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
              loading evidence
            </span>
          ) : (
            <span>{cards.length} strategies</span>
          )}
        </div>
      </div>

      {sources.sourceErrors.length > 0 ? (
        <div
          role="alert"
          className="mb-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-900/60 dark:bg-amber-900/25 dark:text-amber-200"
        >
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden="true" />
          <span className="min-w-0 break-words">Evidence source unavailable: {sources.sourceErrors.join("; ")}</span>
        </div>
      ) : null}

      <div className="overflow-x-auto pb-2">
        <div className="grid gap-3 sm:grid-cols-2 lg:min-w-[1260px] lg:grid-cols-7">
          {COLUMNS.map((column) => {
            const columnCards = cardsByColumn.get(column.id) ?? [];
            return (
              <div key={column.id} className="rounded-lg border border-slate-200 bg-slate-50/70 p-2 dark:border-slate-700 dark:bg-slate-950/50">
                <div className="mb-2 flex items-center justify-between gap-2 px-1">
                  <h3 className="text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">
                    {column.title}
                  </h3>
                  <span className="rounded bg-white px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-slate-900 dark:text-slate-400">
                    {columnCards.length}
                  </span>
                </div>
                <div className="space-y-2">
                  {columnCards.length > 0 ? (
                    columnCards.map((card) => <StrategyCard key={card.id} card={card} />)
                  ) : (
                    <div className="rounded-md border border-dashed border-slate-200 px-2 py-4 text-center text-xs text-slate-400 dark:border-slate-700 dark:text-slate-500">
                      {column.empty}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
