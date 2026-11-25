import { apiClient } from './client';
import config from '@/config/tos-control-plane.json';

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
  /**
   * True when the READER had to strip a path or an account-shaped value on the
   * way out — which means the exporter regressed. The body is safe either way,
   * so this is not an error state; the page says a sentence was altered rather
   * than presenting a scrubbed broken export as normal.
   */
  redacted?: boolean;
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
export type BoardVerdict = 'blocked' | 'check' | 'clear' | 'stopped' | 'stale' | 'unknown';

/**
 * The KST wall clock, as the export window is written.
 *
 * `weekday` is 0=Sunday … 6=Saturday, matching `Date.getDay()` so the config's
 * `weekdays: [1,2,3,4,5]` reads the way an operator would write it. Both parts
 * come from one `Intl` pass in Asia/Seoul, because the viewer's own timezone
 * must not decide whether the exporter was supposed to be running.
 */
export function kstClock(now: Date = new Date()): { hour: number; weekday: number } {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Asia/Seoul',
    hour12: false,
    hour: '2-digit',
    weekday: 'short',
  }).formatToParts(now);
  const hourPart = parts.find((part) => part.type === 'hour')?.value ?? '0';
  const weekdayPart = parts.find((part) => part.type === 'weekday')?.value ?? '';
  const names = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  // `hour12: false` renders midnight as 24 in some ICU builds.
  const hour = Number(hourPart) % 24;
  return { hour: Number.isFinite(hour) ? hour : 0, weekday: Math.max(0, names.indexOf(weekdayPart)) };
}

/**
 * Whether the exporter is supposed to be rewriting the board right now.
 *
 * The window is config (`tos-control-plane.json::statusExportWindowKst`), not a
 * literal here, because it mirrors the export cron on the host — a schedule
 * change must not need a UI release to stop the page lying in one direction or
 * the other.
 */
export function insideExportWindow(now: Date = new Date()): boolean {
  const { hour, weekday } = kstClock(now);
  const window = config.statusExportWindowKst;
  if (!window.weekdays.includes(weekday)) return false;
  return hour >= window.fromHour && hour < window.untilHour;
}

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
 * The board's verdict: the counts the exporter took, and whether it is still
 * taking them.
 *
 * Two freshness rules, in this order, because each catches a different way the
 * page could pass a dead exporter off as a healthy day.
 *
 * * **`stale` beats every other answer.** A board from another day says nothing
 *   about now: on the morning after a clean close the document still reads
 *   "0 blocks", and rendering that as "clear" is precisely how a stopped
 *   exporter passes for a healthy day.
 * * **`stopped` catches the same failure WITHIN a day.** The export cron runs
 *   every five minutes through the session, so a board whose date is today but
 *   whose age is three intervals old was written before the cron died — and it
 *   still reads «0 blocks» at 15:00 because nothing has updated it since 10:00.
 *   The date rule cannot see that; only the age can. It applies **only inside
 *   the export window**, so the board sitting untouched overnight — which is
 *   correct and expected — is not flagged until the next session.
 *
 * `stopped` wins over `clear` and over the counts, because the counts it would
 * report are not about now. It does not hide them: the caller still has
 * `document.blocked`/`checks` and labels them «마지막 기록 기준».
 *
 * `unknown` when the document names no date or no counts — absence stays
 * absence rather than defaulting to good news.
 *
 * @param ageSeconds the response's `age_seconds`. `undefined` means the caller
 *   did not measure it (the pre-P2 call shape) and the age rule is skipped;
 *   `null` means the reader could not tell, which inside the window is itself
 *   a reason not to say «이상 없음».
 */
export function boardVerdict(
  document: TosStatusDocument | null | undefined,
  now: Date = new Date(),
  ageSeconds?: number | null,
): BoardVerdict {
  if (!document?.date) return 'unknown';
  if (document.date !== kstToday(now)) return 'stale';
  if (ageSeconds !== undefined && insideExportWindow(now)) {
    if (ageSeconds == null || ageSeconds > config.statusStaleAfterSeconds) return 'stopped';
  }
  const blocked = document.blocked;
  const checks = document.checks;
  if (typeof blocked !== 'number' || typeof checks !== 'number') return 'unknown';
  if (blocked > 0) return 'blocked';
  if (checks > 0) return 'check';
  return 'clear';
}

/**
 * The issues, blocks first — the board's own level words, not a literal here.
 *
 * The order is the one an operator reads in: what is stopped comes before what
 * wants a look. Inside a level the exporter's order is preserved, because it is
 * already the order `sts tos status` prints (tenant by tenant, then paper), and
 * re-sorting would make the page and the CLI disagree about the same day.
 *
 * A level the document did not name sorts last rather than being dropped: an
 * unrecognised level is still an issue somebody raised.
 */
export function orderedIssues(
  document: TosStatusDocument | null | undefined,
): TosStatusIssue[] {
  const issues = document?.issues ?? [];
  const blocked = document?.levels?.blocked ?? null;
  const check = document?.levels?.check ?? null;
  const rank = (issue: TosStatusIssue): number => {
    if (blocked != null && issue.level === blocked) return 0;
    if (check != null && issue.level === check) return 1;
    return 2;
  };
  return [...issues].sort((left, right) => rank(left) - rank(right));
}

/** Whether the resident paper cell was running when the board was taken. */
export type PaperLiveness = 'alive' | 'partial' | 'stopped' | 'not-checked' | 'unknown';

/**
 * The resident paper cell's liveness, from the board alone.
 *
 * `not-checked` is its own answer and not a synonym for «stopped»: the
 * exporter reads /proc only for today, so on a past date both flags are false
 * and say nothing at all. Rendering that as «꺼짐» would report an outage for
 * every board older than this morning.
 */
export function paperLiveness(paper: TosStatusPaper | null | undefined): PaperLiveness {
  if (!paper) return 'unknown';
  if (paper.live_check !== true) return 'not-checked';
  const runtime = paper.runtime_alive;
  const driver = paper.driver_alive;
  if (runtime == null || driver == null) return 'unknown';
  if (runtime && driver) return 'alive';
  if (runtime || driver) return 'partial';
  return 'stopped';
}

export const tosStatusApi = {
  getStatus: async () => {
    const { data } = await apiClient.get<TosStatusResponse>('/api/tos/status');
    return data;
  },
};
