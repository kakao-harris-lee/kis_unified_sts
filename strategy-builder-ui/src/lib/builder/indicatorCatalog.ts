/**
 * Indicator Catalog — merges backend capabilities (source of truth) with the
 * static `constants.ts` seed (UI meta + offline fallback).
 *
 * Direction 1 (동적 fetch): the backend `getCapabilities()` response drives
 * which indicators are genuinely supported. `constants.ts` is demoted to a
 * fallback seed that supplies UI-only metadata (한글 설명, 선물 적용성) and keeps
 * the picker populated when the backend is unreachable.
 *
 * This module is pure (no React) so the mapping/merge logic is unit-testable
 * without a render tree.
 */

import type {
  IndicatorCategory,
  IndicatorDefinition,
  IndicatorOutput,
  IndicatorParam,
} from "@/types/builder";
import type { CapabilityIndicator } from "@/lib/dashboard/strategyBuilder";
import { ALL_INDICATORS } from "@/lib/builder/constants";

/** live = backend capabilities loaded; loading = first fetch in flight;
 * fallback = fetch failed/empty, using constants seed. */
export type CatalogStatus = "live" | "loading" | "fallback";

export interface IndicatorCatalog {
  all: IndicatorDefinition[];
  status: CatalogStatus;
  getById: (id: string) => IndicatorDefinition | undefined;
  byCategory: (category: IndicatorCategory) => IndicatorDefinition[];
  search: (query: string) => IndicatorDefinition[];
}

function firstBool(...values: Array<boolean | undefined>): boolean | undefined {
  for (const value of values) {
    if (typeof value === "boolean") return value;
  }
  return undefined;
}

/**
 * Map one raw backend capability item to the frontend `IndicatorDefinition`.
 * Reads snake_case first, camelCase alias second (defensive), and translates
 * support flags into the UI's badge flags:
 *   backend `backtest_supported === false` → `leanUnsupported`
 *   backend `runtime_supported === false`  → `runtimeUnsupported`
 *   backend `implemented === false`        → `implemented: false` (blocks add)
 */
export function mapCapabilityIndicator(raw: CapabilityIndicator): IndicatorDefinition {
  const nameKo = raw.name_ko ?? raw.nameKo ?? raw.name;
  const defaultOutput = raw.default_output ?? raw.defaultOutput ?? "value";
  const backtestSupported = firstBool(raw.backtest_supported, raw.backtestSupported);
  const runtimeSupported = firstBool(raw.runtime_supported, raw.runtimeSupported);

  return {
    id: raw.id,
    name: raw.name,
    nameKo,
    category: raw.category,
    description: raw.description ?? "",
    params: (raw.params ?? []) as IndicatorParam[],
    outputs: (raw.outputs ?? []) as IndicatorOutput[],
    defaultOutput,
    implemented: raw.implemented ?? true,
    leanUnsupported: backtestSupported === false,
    runtimeUnsupported: runtimeSupported === false,
    backendUnsupported: false,
  };
}

/**
 * Merge capabilities with the constants seed.
 *  - `raw` empty/null  → return the constants seed as-is (graceful fallback;
 *    no synthetic badges because backend support is unknown).
 *  - `raw` present      → capabilities is the source of truth. constants supplies
 *    UI-only meta (선물 적용성 + 한글/설명 fallback). constants-only ids are marked
 *    `backendUnsupported` (선택 가능하되 경고 — 캔들패턴 63종이 대표적). capability-only
 *    ids (backend has, constants doesn't — e.g. `volume_ma`) are appended.
 */
export function mergeIndicatorCatalog(
  raw: CapabilityIndicator[] | null | undefined,
): IndicatorDefinition[] {
  if (!raw || raw.length === 0) {
    return ALL_INDICATORS.map((def) => ({ ...def }));
  }

  const capById = new Map<string, CapabilityIndicator>();
  for (const cap of raw) capById.set(cap.id, cap);

  const merged: IndicatorDefinition[] = [];
  const usedCapIds = new Set<string>();

  // 1) constants ordering preserved; capabilities wins on structure/flags.
  for (const meta of ALL_INDICATORS) {
    const cap = capById.get(meta.id);
    if (cap) {
      const mapped = mapCapabilityIndicator(cap);
      merged.push({
        ...mapped,
        // constants supplies UI-only meta the backend does not carry.
        nameKo: (cap.name_ko ?? cap.nameKo) || meta.nameKo,
        description: cap.description || meta.description,
        futuresApplicability: meta.futuresApplicability,
      });
      usedCapIds.add(meta.id);
    } else {
      merged.push({ ...meta, backendUnsupported: true });
    }
  }

  // 2) capability-only ids (present in backend, absent from constants).
  for (const cap of raw) {
    if (!usedCapIds.has(cap.id)) {
      merged.push(mapCapabilityIndicator(cap));
    }
  }

  return merged;
}

/** Build a catalog view (merged list + lookup helpers) for a given status. */
export function buildCatalog(
  raw: CapabilityIndicator[] | null | undefined,
  status: CatalogStatus,
): IndicatorCatalog {
  const all = mergeIndicatorCatalog(raw);
  const byId = new Map(all.map((def) => [def.id, def]));

  return {
    all,
    status,
    getById: (id) => byId.get(id),
    byCategory: (category) => all.filter((def) => def.category === category),
    search: (query) => {
      const trimmed = query.trim();
      if (!trimmed) return [];
      const lower = trimmed.toLowerCase();
      return all.filter(
        (def) =>
          def.id.toLowerCase().includes(lower) ||
          def.name.toLowerCase().includes(lower) ||
          def.nameKo.includes(trimmed),
      );
    },
  };
}
