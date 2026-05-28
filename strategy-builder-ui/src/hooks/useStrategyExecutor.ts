"use client";

import { useState, useCallback, useEffect } from "react";
import { executeStrategy } from "@/lib/api";
import { loadAllStrategies } from "@/lib/builder/storage";
import type { StrategyInfo, SignalResult, LogEntry } from "@/types/signal";
import type { StoredStrategy } from "@/types/builder";

interface UseStrategyExecutorResult {
  strategies: StrategyInfo[];
  selectedStrategy: StrategyInfo | null;
  params: Record<string, number>;
  signals: SignalResult[];
  logs: LogEntry[];
  isLoading: boolean;
  isExecuting: boolean;
  error: string | null;
  loadStrategies: () => Promise<void>;
  selectStrategy: (strategy: StrategyInfo | null) => void;
  setParam: (name: string, value: number) => void;
  execute: (stocks: string[]) => Promise<SignalResult[]>;
  clearSignals: () => void;
}

export function useStrategyExecutor(): UseStrategyExecutorResult {
  const [strategies, setStrategies] = useState<StrategyInfo[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyInfo | null>(null);
  const [params, setParams] = useState<Record<string, number>>({});
  const [signals, setSignals] = useState<SignalResult[]>([]);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStrategies = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      // /execute is the Strategy Builder's execution surface: it runs
      // strategies that the user has *built* in /builder (kept in local
      // storage with full BuilderState). The STS /api/strategies endpoint
      // exposes registry-loaded YAML strategies that have a completely
      // different shape (no `params` array, no builder_state). Mixing the
      // two used to populate the strategy dropdown with entries that
      // crashed on select. Strategy Execute now only lists locally built
      // strategies; YAML registry strategies remain visible elsewhere
      // (Cockpit / Signals filters) where their shape is appropriate.
      const localStrategies: StoredStrategy[] = loadAllStrategies();
      const convertedLocalStrategies: StrategyInfo[] = localStrategies.map((s) => ({
        id: `local_${s.id}`,
        name: `📁 ${s.state.metadata.name}`,
        description: s.state.metadata.description || "내 전략",
        category: s.state.metadata.category || "custom",
        params: [], // 로컬 전략은 params를 builder_state에서 처리
        builder_state: s.state,
        isLocal: true,
      }));

      setStrategies(convertedLocalStrategies);
    } catch (err) {
      const message = err instanceof Error ? err.message : "전략 목록 조회 오류";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const selectStrategy = useCallback((strategy: StrategyInfo | null) => {
    setSelectedStrategy(strategy);
    setSignals([]);
    setLogs([]);

    // Initialize params with defaults. The KIS STS `/api/strategies` endpoint
    // does not currently emit a `params` array per strategy (the registry
    // YAMLs hold the parameter definitions, not the response). Guard against
    // missing/null so selecting a strategy on /execute doesn't crash with
    // "Cannot read properties of undefined (reading 'forEach')". When the
    // backend gains structured params this branch will populate naturally.
    if (strategy) {
      const defaultParams: Record<string, number> = {};
      const strategyParams = strategy.params ?? [];
      for (const param of strategyParams) {
        defaultParams[param.name] = param.default;
      }
      setParams(defaultParams);
    } else {
      setParams({});
    }
  }, []);

  const setParam = useCallback((name: string, value: number) => {
    setParams(prev => ({
      ...prev,
      [name]: value,
    }));
  }, []);

  const execute = useCallback(async (stocks: string[]): Promise<SignalResult[]> => {
    if (!selectedStrategy) {
      setError("전략을 선택해주세요");
      return [];
    }

    if (stocks.length === 0) {
      setError("종목을 입력해주세요");
      return [];
    }

    setIsExecuting(true);
    setError(null);
    setSignals([]);
    setLogs([]);

    try {
      // Pass builder_state for local strategies
      const response = await executeStrategy(
        selectedStrategy.id,
        stocks,
        params,
        selectedStrategy.isLocal ? selectedStrategy.builder_state : undefined
      );

      if (response.status === "success") {
        setSignals(response.results);
        setLogs(response.logs);
        return response.results;
      } else {
        setError(response.message || "전략 실행 실패");
        setLogs(response.logs);
        return [];
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "전략 실행 오류";
      setError(message);
      return [];
    } finally {
      setIsExecuting(false);
    }
  }, [selectedStrategy, params]);

  const clearSignals = useCallback(() => {
    setSignals([]);
    setLogs([]);
  }, []);

  // Load strategies on mount
  useEffect(() => {
    loadStrategies();
  }, [loadStrategies]);

  return {
    strategies,
    selectedStrategy,
    params,
    signals,
    logs,
    isLoading,
    isExecuting,
    error,
    loadStrategies,
    selectStrategy,
    setParam,
    execute,
    clearSignals,
  };
}

export default useStrategyExecutor;
