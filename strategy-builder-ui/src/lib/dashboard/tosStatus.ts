import { apiClient } from './client';

// Wire contract: services/dashboard/routes/tos_status.py. Legibility plan
// docs/plans/2026-11-25-tos-operator-page-legibility-plan.md §4 ① «상태 띠».
//
// Every leaf is optional and nullable because the board's own sources report
// "no source == null" and this reader must not turn absence into a fact. The
// document deliberately carries NO filesystem path, release digest or repo
// commit: the exporter strips them, because /tos is open to the internet behind
// Cloudflare Access and has no auth of its own.
//
// Nothing here is judged on this side. The levels, the issue sentences and the
// counts are the ones `sts tos status` already produced on the host — deriving
// any of them again in the browser would let the page and the CLI disagree
// about the same day.

/** The document version this reader understands (export_status.STATUS_SCHEMA_VERSION). */
export const SUPPORTED_STATUS_SCHEMA_VERSION = 1;

export interface TosStatusIssue {
  /** The board's own level word; `document.levels` names both of them. */
  level?: string | null;
  /** Which session (or `paper`, or `streak/<label>`) raised it. */
  where?: string | null;
  text?: string | null;
}

/** An issue raised by one tenant session — no `where`, the row is the where. */
export interface TosStatusTenantIssue {
  level?: string | null;
  text?: string | null;
}

export interface TosStatusTenant {
  name?: string | null;
  label?: string | null;
  tree_id?: string | null;
  market?: string | null;
  direction?: string | null;
  instrument?: string | null;
  status?: string | null;
  /**
   * Only meaningful for today: the exporter does not read /proc for a past
   * date, and both flags are then false rather than "unknown".
   */
  run_alive?: boolean | null;
  producer_alive?: boolean | null;
  boot_at?: string | null;
  end_at?: string | null;
  run_rc?: number | null;
  producer_rc?: number | null;
  ticks?: number | null;
  issues?: TosStatusTenantIssue[] | null;
}

export interface TosStatusStreak {
  label?: string | null;
  days?: number | null;
  target_days?: number | null;
  window_days?: number | null;
  met?: boolean | null;
  start?: string | null;
  window_start?: string | null;
  /** Why today cannot be judged yet (a running session) — not a failure. */
  pending?: string | null;
  broke_on?: string | null;
  broke_reason?: string | null;
  calendar_version?: string | null;
  /** Set when the count could not be taken at all: show "unknown", not zero. */
  error?: string | null;
}

export interface TosStatusPaperReport {
  verdict?: string | null;
  exit_code?: number | null;
  stop_reason?: string | null;
  started_kst?: string | null;
  ended_kst?: string | null;
  events_consumed?: number | null;
  stale_withheld?: number | null;
  stale_ratio?: number | null;
}

export interface TosStatusPaper {
  session?: string | null;
  /** False for a past date: the two *_alive flags then say nothing. */
  live_check?: boolean | null;
  runtime_alive?: boolean | null;
  driver_alive?: boolean | null;
  /**
   * The boot proof's verdict alone — the line itself carries a commit revision
   * and is not exported. `null` is "no boot-proof line", which is not the same
   * as `false` ("there was one and it was not OK").
   */
  boot_ok?: boolean | null;
  report?: TosStatusPaperReport | null;
  issues?: TosStatusTenantIssue[] | null;
}

/** The two level words the board uses, so the page needs no literal of its own. */
export interface TosStatusLevels {
  blocked?: string | null;
  check?: string | null;
}

export interface TosStatusDocument {
  schema_version: number;
  /** The KST day this board judges. Compared against the viewer's own today. */
  date?: string | null;
  generated_kst?: string | null;
  tenants?: TosStatusTenant[] | null;
  clean_streak?: TosStatusStreak[] | null;
  paper?: TosStatusPaper | null;
  issues?: TosStatusIssue[] | null;
  /** Counted by the exporter from the same list the page renders. */
  blocked?: number | null;
  checks?: number | null;
  levels?: TosStatusLevels | null;
}

export interface TosStatusResponse {
  available: boolean;
  reason: string | null;
  age_seconds: number | null;
  document: TosStatusDocument | null;
}

export type StatusState =
  | 'loading' | 'error' | 'missing' | 'unreadable' | 'invalid' | 'unsupported' | 'unknown' | 'ready';

/**
 * The one acceptance predicate for a status document.
 *
 * The strip and the issue list must never disagree about what counts as a
 * usable document — two copies of the same condition means raising the
 * supported version in one place silently blanks or silently renders the other.
 */
export function isAcceptedStatusDocument(
  document: TosStatusDocument | null | undefined,
): document is TosStatusDocument {
  if (!document) return false;
  if (document.schema_version !== SUPPORTED_STATUS_SCHEMA_VERSION) return false;
  return Array.isArray(document.tenants);
}

/**
 * Map one response onto a banner state.
 *
 * Prefix matching, because the shared fixture
 * (tests/fixtures/tos/status-reasons.json) declares these as prefixes and the
 * Python side only guarantees each reason *starts with* one. A prefix added
 * there without a branch here fails the UI job rather than landing as 'unknown'.
 */
export function statusState(
  response: TosStatusResponse | undefined,
  connectionFailed: boolean,
): StatusState {
  if (connectionFailed) return 'error';
  if (!response) return 'loading';
  if (!response.available) {
    if (response.reason?.startsWith('status document absent')) return 'missing';
    // Not a data-format problem: the file could not be opened at all
    // (permissions, uid mismatch, a directory in its place). Sending the
    // operator to look at the exporter's output would be the wrong instruction.
    if (response.reason?.startsWith('cannot read status document')) return 'unreadable';
    if (response.reason?.startsWith('unsupported schema_version')) return 'unsupported';
    if (response.reason?.startsWith('invalid json') || response.reason?.startsWith('schema mismatch')) return 'invalid';
    return 'unknown';
  }
  return isAcceptedStatusDocument(response.document) ? 'ready' : 'invalid';
}

/** How the strip should read overall. Never derived from a level literal here. */
export type BoardVerdict = 'blocked' | 'check' | 'clear' | 'stale' | 'unknown';

/**
 * Today in KST, as `YYYY-MM-DD`.
 *
 * The viewer's own clock and timezone are irrelevant: trading days here are KST
 * (CLAUDE.md, "Timezone"), so a laptop in another zone must not make yesterday's
 * board look current.
 */
export function kstToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul' }).format(now);
}

/**
 * The board's one-word verdict, from the counts the exporter already took.
 *
 * **`stale` beats every other answer.** A board from another day says nothing
 * about now: on the morning after a clean close the document still reads
 * "0 blocks", and rendering that as "clear" is precisely how a stopped
 * exporter passes for a healthy day. The counts are only meaningful once the
 * document is today's.
 *
 * `unknown` when the document names no date or no counts — absence stays
 * absence rather than defaulting to good news.
 */
export function boardVerdict(
  document: TosStatusDocument | null | undefined,
  now: Date = new Date(),
): BoardVerdict {
  if (!document?.date) return 'unknown';
  if (document.date !== kstToday(now)) return 'stale';
  const blocked = document.blocked;
  const checks = document.checks;
  if (typeof blocked !== 'number' || typeof checks !== 'number') return 'unknown';
  if (blocked > 0) return 'blocked';
  if (checks > 0) return 'check';
  return 'clear';
}

export const tosStatusApi = {
  getStatus: async () => {
    const { data } = await apiClient.get<TosStatusResponse>('/api/tos/status');
    return data;
  },
};
