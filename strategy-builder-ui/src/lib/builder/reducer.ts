import type {
  BuilderAction,
  BuilderIndicator,
  BuilderState,
} from "@/types/builder";
import { generateAutoConditions } from "@/lib/builder/autoConditions";

export const INITIAL_STATE: BuilderState = {
  metadata: {
    id: "",
    name: "",
    description: "",
    category: "custom",
    tags: [],
    author: "user",
  },
  assetClass: "stock",
  indicators: [],
  entry: {
    logic: "AND",
    conditions: [],
  },
  exit: {
    logic: "AND",
    conditions: [],
  },
  risk: {
    stopLoss: { enabled: false, percent: 5 },
    takeProfit: { enabled: false, percent: 10 },
    trailingStop: { enabled: false, percent: 3 },
  },
};

export function builderReducer(state: BuilderState, action: BuilderAction): BuilderState {
  switch (action.type) {
    case "SET_METADATA":
      return {
        ...state,
        metadata: { ...state.metadata, ...action.payload },
      };

    case "SET_ASSET_CLASS":
      return { ...state, assetClass: action.payload };

    case "ADD_INDICATOR":
      return {
        ...state,
        indicators: [...state.indicators, action.payload],
      };

    case "ADD_INDICATOR_WITH_AUTO": {
      const newIndicators = [...state.indicators, action.payload];
      const allAuto = (state.entry.conditions.length === 0 && state.exit.conditions.length === 0) ||
        (state.entry.conditions.every(c => c.id.startsWith("auto_")) &&
         state.exit.conditions.every(c => c.id.startsWith("auto_")));

      if (allAuto) {
        // 전체 auto 상태 → 모든 지표로 재생성
        const auto = generateAutoConditions(newIndicators);
        return {
          ...state,
          indicators: newIndicators,
          entry: { ...state.entry, conditions: auto.entry },
          exit: { ...state.exit, conditions: auto.exit },
        };
      }

      // 수동 조건이 섞여 있음 → 새 지표에 대한 조건만 추가
      const added = generateAutoConditions([action.payload]);
      return {
        ...state,
        indicators: newIndicators,
        entry: { ...state.entry, conditions: [...state.entry.conditions, ...added.entry] },
        exit: { ...state.exit, conditions: [...state.exit.conditions, ...added.exit] },
      };
    }

    case "UPDATE_INDICATOR": {
      // alias는 내부 key — 변경 불가. displayName 등 다른 필드만 업데이트.
      const updates = { ...action.payload.updates };
      delete (updates as Partial<BuilderIndicator>).alias; // alias 변경 무시

      const updatedIndicators = state.indicators.map((ind) =>
        ind.id === action.payload.id ? { ...ind, ...updates } : ind
      );
      return { ...state, indicators: updatedIndicators };
    }

    case "REMOVE_INDICATOR": {
      const removedAlias = state.indicators.find((i) => i.id === action.payload)?.alias;
      const remainingIndicators = state.indicators.filter((ind) => ind.id !== action.payload);

      // 조건이 모두 auto-generated이면 재생성, 아니면 해당 지표 참조 조건만 제거
      const entryAllAutoR = state.entry.conditions.every(c => c.id.startsWith("auto_"));
      const exitAllAutoR = state.exit.conditions.every(c => c.id.startsWith("auto_"));

      if (entryAllAutoR && exitAllAutoR) {
        const auto = generateAutoConditions(remainingIndicators);
        return {
          ...state,
          indicators: remainingIndicators,
          entry: { ...state.entry, conditions: auto.entry },
          exit: { ...state.exit, conditions: auto.exit },
        };
      }

      return {
        ...state,
        indicators: remainingIndicators,
        entry: {
          ...state.entry,
          conditions: state.entry.conditions.filter(
            (c) =>
              c.left.indicatorAlias !== removedAlias &&
              c.right.indicatorAlias !== removedAlias &&
              c.candlestickAlias !== removedAlias
          ),
        },
        exit: {
          ...state.exit,
          conditions: state.exit.conditions.filter(
            (c) =>
              c.left.indicatorAlias !== removedAlias &&
              c.right.indicatorAlias !== removedAlias &&
              c.candlestickAlias !== removedAlias
          ),
        },
      };
    }

    case "ADD_ENTRY_CONDITION":
      return {
        ...state,
        entry: {
          ...state.entry,
          conditions: [...state.entry.conditions, action.payload],
        },
      };

    case "UPDATE_ENTRY_CONDITION":
      return {
        ...state,
        entry: {
          ...state.entry,
          conditions: state.entry.conditions.map((c) =>
            c.id === action.payload.id ? { ...c, ...action.payload.updates } : c
          ),
        },
      };

    case "REMOVE_ENTRY_CONDITION":
      return {
        ...state,
        entry: {
          ...state.entry,
          conditions: state.entry.conditions.filter((c) => c.id !== action.payload),
        },
      };

    case "REORDER_ENTRY_CONDITIONS":
      return {
        ...state,
        entry: {
          ...state.entry,
          conditions: action.payload,
        },
      };

    case "SET_ENTRY_LOGIC":
      return {
        ...state,
        entry: { ...state.entry, logic: action.payload },
      };

    case "ADD_EXIT_CONDITION":
      return {
        ...state,
        exit: {
          ...state.exit,
          conditions: [...state.exit.conditions, action.payload],
        },
      };

    case "UPDATE_EXIT_CONDITION":
      return {
        ...state,
        exit: {
          ...state.exit,
          conditions: state.exit.conditions.map((c) =>
            c.id === action.payload.id ? { ...c, ...action.payload.updates } : c
          ),
        },
      };

    case "REMOVE_EXIT_CONDITION":
      return {
        ...state,
        exit: {
          ...state.exit,
          conditions: state.exit.conditions.filter((c) => c.id !== action.payload),
        },
      };

    case "REORDER_EXIT_CONDITIONS":
      return {
        ...state,
        exit: {
          ...state.exit,
          conditions: action.payload,
        },
      };

    case "SET_EXIT_LOGIC":
      return {
        ...state,
        exit: { ...state.exit, logic: action.payload },
      };

    case "SET_RISK":
      return {
        ...state,
        risk: { ...state.risk, ...action.payload },
      };

    case "AUTO_GENERATE_CONDITIONS":
      return {
        ...state,
        entry: {
          ...state.entry,
          conditions: action.payload.entry,
        },
        exit: {
          ...state.exit,
          conditions: action.payload.exit,
        },
      };

    case "LOAD_STATE": {
      const loaded = action.payload;
      const seenIds = new Set<string>();
      const fixedIndicators = loaded.indicators.map((ind) => {
        if (seenIds.has(ind.id)) {
          return { ...ind, id: `${ind.indicatorId}_${Date.now()}_${Math.random().toString(36).substr(2, 5)}` };
        }
        seenIds.add(ind.id);
        return ind;
      });

      return { ...loaded, assetClass: loaded.assetClass ?? "stock", indicators: fixedIndicators };
    }

    case "RESET":
      return INITIAL_STATE;

    default:
      return state;
  }
}
