import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { TosProjection } from '@/lib/dashboard/tos';

// Test-only I/O: do not bundle fixtures into the UI or require repository-level
// fixture files during the standalone Docker TypeScript build.
export function tosFixture(unknown = false): TosProjection {
  const name = unknown ? 'operator-projection-v1-unknown.json' : 'operator-projection-v1.json';
  return JSON.parse(readFileSync(resolve(process.cwd(), '../tests/fixtures/tos', name), 'utf8')) as TosProjection;
}
