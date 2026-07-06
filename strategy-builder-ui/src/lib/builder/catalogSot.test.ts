/**
 * Bidirectional catalog single-source-of-truth guardrail.
 *
 * The Python side (tests/unit/strategy_builder/test_catalog_registry_sot.py)
 * asserts: every YAML `runtime_supported` id is computable by the engine.
 *
 * This test closes the other direction the Python test cannot see: every
 * indicator the FRONTEND offers as addable (`implemented !== false`) must exist
 * in the backend builder catalog (config/strategy_builder/indicators.yaml).
 * Otherwise a user could build a condition on an indicator the runtime silently
 * skips, and the signal would never fire.
 *
 * Reads the committed YAML directly (not a fixture) so it fails the moment the
 * frontend catalog and backend catalog drift apart. See
 * docs/plans/2026-07-06-talib-builder-alignment.md (Phase E).
 */

import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { load } from "js-yaml";
import { ALL_INDICATORS } from "@/lib/builder/constants";

interface YamlCatalog {
  strategy_builder?: { indicators?: Array<{ id?: string }> };
}

function backendCatalogIds(): Set<string> {
  const yamlPath = resolve(
    __dirname,
    "../../../../config/strategy_builder/indicators.yaml",
  );
  const parsed = load(readFileSync(yamlPath, "utf8")) as YamlCatalog;
  const indicators = parsed.strategy_builder?.indicators ?? [];
  return new Set(
    indicators
      .map((entry) => entry?.id)
      .filter((id): id is string => typeof id === "string"),
  );
}

describe("frontend catalog ⊆ backend builder catalog", () => {
  it("every addable frontend indicator exists in the backend YAML catalog", () => {
    const backendIds = backendCatalogIds();
    const addable = ALL_INDICATORS.filter((def) => def.implemented !== false);
    const orphaned = addable
      .map((def) => def.id)
      .filter((id) => !backendIds.has(id));

    expect(
      orphaned,
      `frontend offers these ids as addable but the backend catalog cannot ` +
        `compute them (mark implemented:false in constants.ts, or wire them ` +
        `into the engine + indicators.yaml): ${orphaned.join(", ")}`,
    ).toEqual([]);
  });

  it("backend catalog is non-empty (guards against a path/parse regression)", () => {
    expect(backendCatalogIds().size).toBeGreaterThan(20);
  });
});
