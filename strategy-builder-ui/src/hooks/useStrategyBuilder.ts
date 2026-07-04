/**
 * Strategy Builder State Management Hook
 */

import { useReducer, useCallback, useMemo } from "react";
import type {
  BuilderState,
  BuilderIndicator,
  BuilderCondition,
  BuilderMetadata,
  RiskManagement,
} from "@/types/builder";
import { getIndicatorById } from "@/lib/builder/constants";
import { useIndicatorCatalog } from "@/lib/builder/useIndicatorCatalog";
import { builderReducer, INITIAL_STATE } from "@/lib/builder/reducer";
import { toYamlStrategy, toYamlString as serializeYamlStrategy } from "@/lib/builder/yamlSerializer";

export { INITIAL_STATE } from "@/lib/builder/reducer";

// ============================================================
// Hook
// ============================================================

export function useStrategyBuilder(initialState?: BuilderState) {
  const [state, dispatch] = useReducer(builderReducer, initialState || INITIAL_STATE);

  // Backend capabilities drive the indicator catalog (동적 fetch). React Query
  // dedupes this with the IndicatorSelector's subscription. The catalog already
  // falls back to the constants seed while loading / on error, so createIndicator
  // always resolves a definition.
  const catalog = useIndicatorCatalog();

  // ============================================================
  // Metadata Actions
  // ============================================================

  const setMetadata = useCallback((updates: Partial<BuilderMetadata>) => {
    dispatch({ type: "SET_METADATA", payload: updates });
  }, []);

  const setAssetClass = useCallback(
    (assetClass: "stock" | "futures") =>
      dispatch({ type: "SET_ASSET_CLASS", payload: assetClass }),
    [],
  );

  // ============================================================
  // Indicator Actions
  // ============================================================

  const addIndicator = useCallback((indicator: BuilderIndicator) => {
    dispatch({ type: "ADD_INDICATOR", payload: indicator });
  }, []);

  /** 지표 추가 + 진입/청산 조건 자동 재생성 (조건이 비어있거나 모두 auto인 경우) */
  const addIndicatorWithAutoConditions = useCallback((indicator: BuilderIndicator) => {
    dispatch({ type: "ADD_INDICATOR_WITH_AUTO", payload: indicator });
  }, []);

  const updateIndicator = useCallback(
    (id: string, updates: Partial<BuilderIndicator>) => {
      dispatch({ type: "UPDATE_INDICATOR", payload: { id, updates } });
    },
    []
  );

  const removeIndicator = useCallback((id: string) => {
    dispatch({ type: "REMOVE_INDICATOR", payload: id });
  }, []);

  // ============================================================
  // Entry Condition Actions
  // ============================================================

  const addEntryCondition = useCallback((condition: BuilderCondition) => {
    dispatch({ type: "ADD_ENTRY_CONDITION", payload: condition });
  }, []);

  const updateEntryCondition = useCallback(
    (id: string, updates: Partial<BuilderCondition>) => {
      dispatch({ type: "UPDATE_ENTRY_CONDITION", payload: { id, updates } });
    },
    []
  );

  const removeEntryCondition = useCallback((id: string) => {
    dispatch({ type: "REMOVE_ENTRY_CONDITION", payload: id });
  }, []);

  const setEntryLogic = useCallback((logic: "AND" | "OR") => {
    dispatch({ type: "SET_ENTRY_LOGIC", payload: logic });
  }, []);

  const reorderEntryConditions = useCallback((conditions: BuilderCondition[]) => {
    dispatch({ type: "REORDER_ENTRY_CONDITIONS", payload: conditions });
  }, []);

  // ============================================================
  // Exit Condition Actions
  // ============================================================

  const addExitCondition = useCallback((condition: BuilderCondition) => {
    dispatch({ type: "ADD_EXIT_CONDITION", payload: condition });
  }, []);

  const updateExitCondition = useCallback(
    (id: string, updates: Partial<BuilderCondition>) => {
      dispatch({ type: "UPDATE_EXIT_CONDITION", payload: { id, updates } });
    },
    []
  );

  const removeExitCondition = useCallback((id: string) => {
    dispatch({ type: "REMOVE_EXIT_CONDITION", payload: id });
  }, []);

  const setExitLogic = useCallback((logic: "AND" | "OR") => {
    dispatch({ type: "SET_EXIT_LOGIC", payload: logic });
  }, []);

  const reorderExitConditions = useCallback((conditions: BuilderCondition[]) => {
    dispatch({ type: "REORDER_EXIT_CONDITIONS", payload: conditions });
  }, []);

  // ============================================================
  // Risk Management Actions
  // ============================================================

  const setRisk = useCallback((updates: Partial<RiskManagement>) => {
    dispatch({ type: "SET_RISK", payload: updates });
  }, []);

  // ============================================================
  // State Actions
  // ============================================================

  const loadState = useCallback((newState: BuilderState) => {
    dispatch({ type: "LOAD_STATE", payload: newState });
  }, []);

  const reset = useCallback(() => {
    dispatch({ type: "RESET" });
  }, []);

  // ============================================================
  // YAML Conversion
  // ============================================================

  const toYaml = useMemo(() => toYamlStrategy(state), [state]);

  const toYamlString = useMemo(() => serializeYamlStrategy(toYaml), [toYaml]);

  // ============================================================
  // Validation
  // ============================================================

  const isValid = useMemo((): boolean => {
    if (!state.metadata.name.trim()) return false;
    if (state.indicators.length === 0) return false;
    if (state.entry.conditions.length === 0) return false;
    if (state.exit.conditions.length === 0) return false;
    return true;
  }, [state]);

  const validationErrors = useMemo((): string[] => {
    const errors: string[] = [];
    if (!state.metadata.name.trim()) {
      errors.push("전략 이름을 입력하세요");
    }
    if (state.indicators.length === 0) {
      errors.push("최소 1개의 지표를 추가하세요");
    }
    if (state.entry.conditions.length === 0) {
      errors.push("진입 조건을 추가하세요");
    }
    if (state.exit.conditions.length === 0) {
      errors.push("청산 조건을 추가하세요");
    }
    return errors;
  }, [state]);

  // ============================================================
  // Helper: Create Indicator with Defaults
  // ============================================================

  const createIndicator = useCallback(
    (indicatorId: string, customAlias?: string): BuilderIndicator | null => {
      // Prefer the capability-driven catalog; fall back to the constants seed
      // (offline / first render) so the builder still functions.
      const def = catalog.getById(indicatorId) ?? getIndicatorById(indicatorId);
      if (!def) return null;

      const defaultParams: Record<string, number | string> = {};
      def.params.forEach((p) => {
        defaultParams[p.name] = p.default;
      });

      const existingCount = state.indicators.filter((i) => i.indicatorId === indicatorId).length;
      const existingAliases = new Set(state.indicators.map((i) => i.alias));

      // alias는 항상 깔끔한 Python 식별자로 자동 생성 (사용자 입력 무관)
      const baseAlias = `${indicatorId}_${existingCount + 1}`;
      const resolveAlias = (base: string): string => {
        if (!existingAliases.has(base)) return base;
        let n = 2;
        while (existingAliases.has(`${base}_${n}`)) n++;
        return `${base}_${n}`;
      };
      const alias = resolveAlias(baseAlias);
      // customAlias는 displayName으로 사용 (표시용)
      const displayName = customAlias !== alias ? customAlias : undefined;

      // 고유 ID 생성: timestamp + random string (중복 방지)
      const uniqueId = `${indicatorId}_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;

      return {
        id: uniqueId,
        indicatorId,
        alias,
        ...(displayName ? { displayName } : {}),
        params: defaultParams,
        output: def.defaultOutput,
      };
    },
    [state.indicators, catalog]
  );

  // ============================================================
  // Return
  // ============================================================

  return {
    state,
    // Metadata
    setMetadata,
    setAssetClass,
    // Indicators
    addIndicator,
    addIndicatorWithAutoConditions,
    updateIndicator,
    removeIndicator,
    createIndicator,
    // Entry Conditions
    addEntryCondition,
    updateEntryCondition,
    removeEntryCondition,
    reorderEntryConditions,
    setEntryLogic,
    // Exit Conditions
    addExitCondition,
    updateExitCondition,
    removeExitCondition,
    reorderExitConditions,
    setExitLogic,
    // Risk
    setRisk,
    // State
    loadState,
    reset,
    // YAML
    toYaml,
    toYamlString,
    // Validation
    isValid,
    validationErrors,
  };
}

export type UseStrategyBuilderReturn = ReturnType<typeof useStrategyBuilder>;
