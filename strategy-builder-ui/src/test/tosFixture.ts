import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { TosProjection } from '@/lib/dashboard/tos';

// Test-only I/O: do not bundle fixtures into the UI or require repository-level
// fixture files during the standalone Docker TypeScript build.
export function tosFixture(unknown = false): TosProjection {
  const name = unknown ? 'operator-projection-v1-unknown.json' : 'operator-projection-v1.json';
  return JSON.parse(readFileSync(resolve(process.cwd(), '../tests/fixtures/tos', name), 'utf8')) as TosProjection;
}

export interface ReasonPrefix {
  prefix: string;
  ui_state: string;
}

/**
 * The reason prefixes the API may emit, with the UI state each maps to.
 *
 * Shared with `tests/unit/dashboard/test_tos_projection.py`: the Python side
 * proves every `_unavailable(...)` call starts with one of these, and the TS
 * side proves `projectionState` maps each one.
 *
 * Both sides assert the file; only the Python side is CI-gated. There is no
 * node job in `.github/workflows/`, so a prefix added here without a matching
 * `projectionState` branch is green in CI and reaches the UI as `unknown`. A
 * UI-suite CI job is tracked as a follow-up, not done here.
 */
export function reasonPrefixes(): ReasonPrefix[] {
  const path = resolve(process.cwd(), '../tests/fixtures/tos/projection-reasons.json');
  return (JSON.parse(readFileSync(path, 'utf8')) as { reasons: ReasonPrefix[] }).reasons;
}
