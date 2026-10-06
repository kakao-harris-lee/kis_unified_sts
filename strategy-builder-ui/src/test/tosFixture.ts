import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { TosProjection } from '@/lib/dashboard/tos';

// Test-only I/O: do not bundle fixtures into the UI or require repository-level
// fixture files during the standalone Docker TypeScript build.
//
// The projection document fixtures are owned by the distribution that produces
// them (`tos_runtime.operator.projection`) and live in its own tree. The planned
// repo split keeps `tos/` and removes the legacy runtime, so every reader points
// into `tos/`; nothing under `tos/` reads out of it (review note e of #861).
//
// Paired with the `.github/workflows/ui.yml` path filters (PR #867) — this
// loader reads TWO trees, so change both together or the UI job stops
// watching the half that moved.
const TOS_FIXTURE_DIR = '../tos/runtime/tests/fixtures';

export function tosFixture(unknown = false): TosProjection {
  const name = unknown ? 'operator-projection-v1-unknown.json' : 'operator-projection-v1.json';
  return JSON.parse(readFileSync(resolve(process.cwd(), TOS_FIXTURE_DIR, name), 'utf8')) as TosProjection;
}

export interface ReasonPrefix {
  prefix: string;
  ui_state: string;
}

/**
 * The reason prefixes the API may emit, with the UI state each maps to.
 *
 * Unlike the projection document above, this vocabulary is emitted by the
 * dashboard API (the Control Plane API / BFF), not by `tos_runtime` — nothing
 * under `tos/` reads it — so it stays in the legacy test tree it belongs to.
 *
 * Shared with `tests/unit/dashboard/test_tos_projection.py`: the Python side
 * proves every `_unavailable(...)` call starts with one of these, and the TS
 * side proves `projectionState` maps each one.
 *
 * Both sides assert the file. The TS side runs in CI as the `ui` job
 * (`.github/workflows/ui.yml`), path-gated on `strategy-builder-ui/**` and
 * `tests/fixtures/**` — so a prefix added to the JSON without a matching
 * `projectionState` branch fails that job instead of reaching the UI as
 * `unknown`. `ui` is not a required check, so a red `ui` does not by itself
 * block the merge button.
 */
export function reasonPrefixes(): ReasonPrefix[] {
  // Paired with the `.github/workflows/ui.yml` path filters (PR #867) —
  // the other half of the pair above; see that comment.
  const path = resolve(process.cwd(), '../tests/fixtures/tos/projection-reasons.json');
  return (JSON.parse(readFileSync(path, 'utf8')) as { reasons: ReasonPrefix[] }).reasons;
}
