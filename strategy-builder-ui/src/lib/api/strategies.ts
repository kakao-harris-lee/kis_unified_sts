/**
 * Strategies API
 */

import { apiGet, apiPost, apiDelete, type ApiResponse, type LogEntry } from "./client";
import type { Signal, ExecuteRequest, ExecuteResponse, StrategyInfo } from "@/types/signal";
import type { BuilderState } from "@/types/builder";

export interface StrategiesListResponse {
  strategies: StrategyInfo[];
}

export async function listStrategies(): Promise<StrategiesListResponse> {
  return apiGet<StrategiesListResponse>("/api/strategies");
}

/**
 * KIS Strategy Builder presets (with full BuilderState per item).
 *
 * Two strategy listings live under different namespaces:
 *
 *   /api/strategies                 → STS registry YAMLs (Cockpit/Signals filters)
 *   /api/kis-builder/strategies     → upstream KIS visual-builder presets
 *
 * The Strategy Builder UI consumes the latter — each entry carries a
 * `builder_state` that the visual editor loads directly. They are not
 * interchangeable; the former lacks `params` / `builder_state`, so the
 * Builder rendered 0 presets when it called /api/strategies after the
 * Caddy cutover (#351). Hit the explicit endpoint instead.
 */
export async function listKisBuilderPresets(): Promise<StrategiesListResponse> {
  return apiGet<StrategiesListResponse>("/api/kis-builder/strategies");
}

export async function listCustomStrategies(): Promise<StrategiesListResponse> {
  return apiGet<StrategiesListResponse>("/api/strategies/custom");
}

export async function executeStrategy(
  strategyId: string,
  stocks: string[],
  params: Record<string, number> = {},
  builderState?: BuilderState
): Promise<ExecuteResponse> {
  const request: ExecuteRequest = {
    strategy_id: strategyId,
    stocks,
    params,
    builder_state: builderState,
  };
  return apiPost<ExecuteResponse>("/api/strategies/execute", request);
}

export interface IndicatorsResponse {
  indicators: Array<{
    name: string;
    label: string;
    params: string[];
    example: string;
  }>;
  variables: string[];
  operators: {
    comparison: string[];
    crossover: string[];
    logical: string[];
  };
}

export async function listIndicators(): Promise<IndicatorsResponse> {
  return apiGet<IndicatorsResponse>("/api/strategies/indicators");
}

export interface BuildRequest {
  name: string;
  buy_condition: string;
  sell_condition?: string;
}

export interface BuildResponse {
  status: "success" | "error";
  message: string;
  file_path?: string;
  strategy_name?: string;
}

export async function buildStrategy(request: BuildRequest): Promise<BuildResponse> {
  return apiPost<BuildResponse>("/api/strategies/build", request);
}

export interface PreviewResponse {
  status: "success" | "error";
  code?: string;
  required_days?: number;
  message?: string;
}

export async function previewStrategy(request: BuildRequest): Promise<PreviewResponse> {
  return apiPost<PreviewResponse>("/api/strategies/preview", request);
}

export interface PreviewCodeResponse {
  status: "success" | "error";
  code?: string;
  buy_dsl?: string;
  sell_dsl?: string;
  message?: string;
}

export async function previewCodeFromState(builderState: BuilderState): Promise<PreviewCodeResponse> {
  return apiPost<PreviewCodeResponse>("/api/strategies/preview-code", {
    builder_state: builderState,
  });
}

/**
 * Builder→paper trading registration (Phase 3 client; backend in PR #357).
 *
 * The Strategy Builder shells out to the dashboard FastAPI under
 * /api/kis-builder/* to materialize a BuilderState as a YAML file under
 * config/strategies/built/. The orchestrator picks them up via the loader
 * change in #358 once the operator flips enabled to true.
 */

export interface RegisteredStrategy {
  id: string;
  name: string;
  description?: string | null;
  asset_class: string;
  enabled: boolean;
  registered_at?: string | null;
  path: string;
}

export interface RegisteredListResponse {
  strategies: RegisteredStrategy[];
  total: number;
}

export interface RegisterPaperRequest {
  builder_state: BuilderState;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  order_amount?: number;
  contracts?: number;
  cooldown_seconds?: number;
  min_confidence?: number;
}

export async function registerPaperStrategy(
  body: RegisterPaperRequest,
): Promise<RegisteredStrategy> {
  return apiPost<RegisteredStrategy>("/api/kis-builder/register-paper", body);
}

export async function listRegisteredStrategies(): Promise<RegisteredListResponse> {
  return apiGet<RegisteredListResponse>("/api/kis-builder/registered");
}

export async function setRegisteredEnabled(
  strategyId: string,
  enabled: boolean,
): Promise<RegisteredStrategy> {
  return apiPost<RegisteredStrategy>(
    `/api/kis-builder/registered/${encodeURIComponent(strategyId)}/enable`,
    { enabled },
  );
}

export async function unregisterStrategy(
  strategyId: string,
): Promise<{ id: string; deleted: boolean }> {
  return apiDelete<{ id: string; deleted: boolean }>(
    `/api/kis-builder/registered/${encodeURIComponent(strategyId)}`,
  );
}
