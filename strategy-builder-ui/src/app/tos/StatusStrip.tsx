"use client";

import type { ReactNode } from 'react';
import config from '@/config/tos-control-plane.json';
import type { ProjectionState, TosProjection } from '@/lib/dashboard/tos';
import {
  boardVerdict,
  orderedIssues,
  paperLiveness,
  type BoardVerdict,
  type PaperLiveness,
  type StatusState,
  type TosStatusIssue,
  type TosStatusStreak,
} from '@/lib/dashboard/tosStatus';
import { isTodaysDocument, sessionPhase } from '@/lib/dashboard/tosSymbols';
import { issueExplanation, type IssueExplanation } from '@/lib/dashboard/tosGlossary';
import { AlertTriangle } from 'lucide-react';
import { AsOf, Badge, ageLabel, type Tone } from './marks';
import Term from './Term';
import type { StatusRead, SymbolsRead } from './queries';

interface StatusStripProps {
  projectionState: ProjectionState;
  projection: TosProjection | null;
  projectionAgeSeconds: number | null;
  status: StatusRead;
  symbols: SymbolsRead;
  /**
   * The page's own wording for a projection state that is not «recent».
   *
   * It used to head a full-width banner; now that a stale paper cell no longer
   * earns one, the specific sentence («아직 상태 파일이 없습니다», …) lands here
   * so the operator still sees WHICH kind of absence it is.
   */
  stateLabel: string;
}

interface Fact {
  key: string;
  label: ReactNode;
  value: string;
  /** Secondary text inside the same chip — a second fact about the same thing. */
  detail?: string | null;
  tone: Tone;
  /** Carries the warning icon, so the one real alarm is not a hue alone. */
  alert?: boolean;
}

/** What the strip says when the board itself could not be read. */
const BOARD_STATES: Record<StatusState, string> = {
  loading: '불러오는 중',
  error: '조회 연결 오류',
  missing: '아직 상태판이 없습니다',
  unreadable: '상태판 파일을 열지 못했습니다',
  invalid: '상태판 형식 오류',
  unsupported: '지원하지 않는 상태판 버전',
  unknown: '상태판 확인 불가',
  ready: '',
};

/**
 * The board's verdict as a tone.
 *
 * «확인» is NEUTRAL on purpose. Every ordinary session records a handful of
 * check-level lines (a feed pass over its window, a digest the release file
 * does not pin), so painting them amber would make the strip shout on a day
 * when nothing is wrong — and an operator who sees amber daily stops reading
 * it. Amber is kept for «막힘», for a board that is not today's, and for a
 * board that could not be read at all.
 */
const VERDICT_TONES: Record<BoardVerdict, Tone> = {
  blocked: 'warn',
  check: 'neutral',
  clear: 'good',
  stopped: 'warn',
  stale: 'warn',
  unknown: 'warn',
};

interface IssueGroup {
  key: string;
  level: string | null | undefined;
  /** The sentence and action, when this page knows the code. */
  explanation: IssueExplanation | null;
  /** Every tenant that raised it, in the board's order, without repeats. */
  where: string[];
  rows: TosStatusIssue[];
}

/**
 * The issue list as one row per KIND, not per tenant.
 *
 * Five tenants overrunning their feed window is one fact and five rows, and
 * the eleven-row list it produces is why the disclosure was unreadable. Rows
 * are grouped by level and by the code this page can name; a row whose code is
 * unknown groups on its own text, so two different unknown problems never
 * merge into one line.
 */
export function groupIssues(issues: TosStatusIssue[]): IssueGroup[] {
  const groups = new Map<string, IssueGroup>();
  for (const issue of issues) {
    const explanation = issueExplanation(issue.text);
    const key = `${issue.level ?? ''}|${explanation?.code ?? issue.text ?? ''}`;
    const group = groups.get(key);
    if (group) {
      group.rows.push(issue);
      if (issue.where && !group.where.includes(issue.where)) group.where.push(issue.where);
      continue;
    }
    groups.set(key, {
      key,
      level: issue.level,
      explanation,
      where: issue.where ? [issue.where] : [],
      rows: [issue],
    });
  }
  return [...groups.values()];
}

/** «12분 전 기록», or that the reader could not tell when it was written. */
function lastWrittenPhrase(ageSeconds: number | null | undefined): string {
  if (ageSeconds == null) return '갱신 시각 모름';
  const minutes = Math.floor(ageSeconds / 60);
  if (minutes < 1) return '방금 기록';
  if (minutes < 60) return `${minutes}분 전 기록`;
  return `${Math.floor(minutes / 60)}시간 ${minutes % 60}분 전 기록`;
}

const LIVENESS_WORDS: Record<PaperLiveness, string | null> = {
  alive: '상주 중',
  partial: '일부만 떠 있음',
  stopped: '상주 아님',
  // Not a synonym for «꺼짐»: the board reads /proc only for today.
  'not-checked': '상주 확인 안 함',
  unknown: null,
};

/** «5/5일 달성», «3/5일», or what stopped the count from being taken. */
function streakValue(streak: TosStatusStreak): string {
  if (streak.error != null) return '알 수 없음';
  if (streak.days == null) return '알 수 없음';
  const target = streak.target_days == null ? '?' : String(streak.target_days);
  return `${streak.days}/${target}일${streak.met === true ? ' 달성' : ''}`;
}

function streakDetail(streak: TosStatusStreak): string | null {
  if (streak.error != null) return streak.error;
  if (streak.pending) return `오늘 판정 보류 · ${streak.pending}`;
  if (streak.broke_on) return `${streak.broke_on} 에 끊김`;
  return null;
}

/**
 * «지금 괜찮은가» — the one line above everything else.
 *
 * Its verdict is the status board's, not this page's: `sts tos status` already
 * judged the day on the host, and the counts, the level words and the issue
 * sentences are carried through verbatim. Deriving any of them again in the
 * browser is how the page and the CLI would come to disagree about the same
 * day, and the operator has no way to tell which one is right.
 *
 * Three things the strip refuses to do:
 *
 * * **it never reads an absent board as a quiet one.** A board from yesterday
 *   still says «0 blocks», so `boardVerdict` answers `stale` before it answers
 *   anything else, and the strip says «오늘 문서 아님»;
 * * **it keeps «paper 셀» labelled.** `/api/tos/projection` describes the ONE
 *   resident paper cell and says nothing about the CP-3 tenant sessions whose
 *   cards sit below. The page used to show those cards unlabelled, which read
 *   as «the system» — the single misreading this strip exists to stop;
 * * **it leaves «확인» neutral.** See `VERDICT_TONES`.
 */
export default function StatusStrip({
  projectionState,
  projection,
  projectionAgeSeconds,
  status,
  symbols,
  stateLabel,
}: StatusStripProps) {
  const board = status.document;
  const boardAge = status.response?.age_seconds;
  // The age is part of the verdict, not a footnote: a board whose export cron
  // died at 10:00 still reads «0 blocks» at 15:00, and only its age says so.
  const verdict = boardVerdict(board, new Date(), status.state === 'ready' ? (boardAge ?? null) : undefined);
  const issues = orderedIssues(board);
  const groups = groupIssues(issues);
  const blockedLevel = board?.levels?.blocked ?? '막힘';
  const checkLevel = board?.levels?.check ?? '확인';
  const facts: Fact[] = [];

  // 1. The board's verdict — the whole point of the strip.
  const counts =
    board?.blocked != null && board?.checks != null
      ? `${blockedLevel} ${board.blocked} · ${checkLevel} ${board.checks}`
      : '알 수 없음';
  facts.push({
    key: 'board',
    // A stopped export with a block already recorded is still a block: the
    // icon follows the counts even while the headline is about the silence.
    alert: verdict === 'blocked' || (verdict === 'stopped' && (board?.blocked ?? 0) > 0),
    label: '상태판',
    value:
      status.state !== 'ready'
        ? BOARD_STATES[status.state]
        : verdict === 'clear'
          ? '이상 없음'
          : verdict === 'stale'
            ? '오늘 문서 아님'
            : verdict === 'stopped'
              ? `갱신 멈춤 · ${lastWrittenPhrase(boardAge)}`
              : verdict === 'unknown'
                ? '알 수 없음'
                : counts,
    detail:
      verdict === 'stale'
        ? `기준일 ${board?.date ?? '알 수 없음'}`
        : // The counts are not hidden — they are relabelled, because they
          // describe the last write rather than now.
          verdict === 'stopped'
          ? `마지막 기록 기준 ${counts}`
          : null,
    tone: status.state === 'loading' ? 'neutral' : status.state !== 'ready' ? 'warn' : VERDICT_TONES[verdict],
  });

  // 2. The tenant sessions, by phase — the board covers all five trees, which
  //    the per-symbol document did not until it learned the futures rows.
  const tenants = board?.tenants ?? [];
  if (tenants.length) {
    // Same mapping the symbols rows use, so a status word cannot mean one
    // thing in the strip and another on the card below it.
    const phases = tenants.map((tenant) => sessionPhase({ status: tenant.status }));
    const parts = (
      [
        ['진행 중', phases.filter((phase) => phase === 'running').length],
        ['종료', phases.filter((phase) => phase === 'settled').length],
        ['시작 안 함', phases.filter((phase) => phase === 'none').length],
        ['확인 필요', phases.filter((phase) => phase === 'unknown').length],
      ] as const
    )
      .filter(([, n]) => n > 0)
      .map(([word, n]) => `${word} ${n}`);
    facts.push({
      key: 'tenants',
      label: `tenant ${tenants.length}개`,
      value: parts.join(' · ') || '알 수 없음',
      // «시작 안 함» is amber beside «확인 필요», as it was in P1: a tenant the
      // board lists and that never booted is an absence, and the one thing
      // this page must never do is draw an absence as «이상 없음».
      tone: phases.some((phase) => phase === 'unknown' || phase === 'none') ? 'warn' : 'good',
    });
  }

  // 3. The clean-day streaks — the paper-promotion count, one chip per label.
  for (const streak of board?.clean_streak ?? []) {
    facts.push({
      key: `streak-${streak.label ?? 'default'}`,
      label: (
        <Term name="clean_streak">
          깨끗한 날{streak.label ? ` · ${streak.label}` : ''}
        </Term>
      ),
      value: streakValue(streak),
      detail: streakDetail(streak),
      tone: streak.error != null ? 'warn' : streak.met === true ? 'good' : 'neutral',
    });
  }

  // 4. The resident paper cell: the polled projection says whether a new state
  //    arrived and whether a halt is latched; the board says whether the two
  //    processes were up when it was taken. Neither answers the other's
  //    question, so both ride in one chip rather than contradicting each other
  //    from two.
  const halted = projection?.driver?.halt_latched;
  const liveness = paperLiveness(board?.paper);
  const reportVerdict = board?.paper?.report?.verdict;
  facts.push({
    key: 'paper',
    label: <Term name="paper_cell">paper 셀</Term>,
    alert: halted === true,
    value:
      halted === true
        ? `실행 중단${projection?.driver?.halt_reason ? ` · ${projection.driver.halt_reason}` : ''}`
        : projectionState === 'recent'
          ? '최근 상태 도착'
          : projectionState === 'stale'
            ? `${config.staleAfterSeconds}초 넘게 새 상태 없음`
            : projectionState === 'loading'
              ? '불러오는 중'
              : stateLabel,
    detail: [LIVENESS_WORDS[liveness], reportVerdict ? `마감 ${reportVerdict}` : null]
      .filter((part): part is string => part !== null)
      .join(' · '),
    tone:
      halted === true
        ? 'warn'
        : liveness === 'stopped' || liveness === 'partial'
          ? 'neutral'
          : projectionState === 'recent'
            ? 'good'
            : projectionState === 'loading'
              ? 'neutral'
              : 'warn',
  });

  // P1 also carried a day-wide «게이트가 막은 판단 n건» chip here. It is gone:
  // the board is now the thing that says whether the day is in trouble, and a
  // count that reads in the hundreds on every ordinary day (every tenant
  // records STAGE_DENIED on exits it has no position to close) said nothing an
  // operator could act on while costing the first screen a chip row at phone
  // width. The same counts are still on screen where they have context — per
  // bar in ③ 커널 게이트, per stretch in ⑤ 사건 기록, per tenant in ④.

  // 5. The symbols document's own day — shown only when it is NOT today's,
  //    because sections ② and ④ read it and an operator must not take a
  //    yesterday's row for this morning's trading. On a normal day the chip is
  //    absent rather than repeating what the board already said.
  const symbolsToday = isTodaysDocument(symbols.document);
  if (symbolsToday !== true) {
    facts.push({
      key: 'day',
      label: '종목 기록 기준일',
      value: symbols.document?.date == null ? '알 수 없음' : `${symbols.document.date} · 오늘 아님`,
      tone: 'warn',
    });
  }

  const redacted = status.response?.redacted === true || symbols.response?.redacted === true;

  return (
    <section
      aria-label="지금 상태"
      className="min-w-0 rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h2 className="font-semibold">지금 괜찮은가</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          호스트의 상태판이 내린 판정을 그대로 옮깁니다. 주문을 내리거나 멈출 수 있는 화면이 아닙니다.
        </p>
      </div>
      {/* The issue list rides IN the chip row rather than under it: the first
          screen is ① + ②, and a disclosure on its own line costs it a row on
          every single load for something that is collapsed by default. */}
      <ul className="mt-3 flex flex-wrap items-center gap-2">
        {facts.map((fact) => (
          <li key={fact.key}>
            <Badge tone={fact.tone}>
              {fact.alert && <AlertTriangle aria-hidden="true" className="h-3.5 w-3.5" />}
              <span className="text-slate-500 dark:text-slate-400">{fact.label}</span>
              <span className="font-medium">{fact.value}</span>
              {fact.detail ? (
                <span className="text-slate-500 dark:text-slate-400">· {fact.detail}</span>
              ) : null}
            </Badge>
          </li>
        ))}
        {issues.length > 0 && (
          <li className="min-w-0">
            <details className="text-sm">
              <summary className="cursor-pointer text-xs text-slate-600 dark:text-slate-300">
                이슈 {issues.length}건 — {blockedLevel} 먼저
                {groups.length < issues.length ? ` · ${groups.length}가지` : ''}
              </summary>
              <ul className="mt-2 space-y-2">
                {groups.map((group) => (
                  <li key={group.key} className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-x-2">
                      <Badge tone={group.level === blockedLevel ? 'warn' : 'neutral'}>
                        <Term name={group.level === blockedLevel ? 'level_blocked' : 'level_check'}>
                          {group.level ?? '알 수 없음'}
                        </Term>
                      </Badge>
                      {/* The plain sentence leads when this page knows the
                          code. An unknown code keeps the board's own line as
                          the headline rather than wearing a guessed caption. */}
                      <span className="min-w-0 break-words">
                        {group.explanation?.sentence ?? group.rows[0]?.text ?? '내용 없음'}
                      </span>
                      {group.explanation && (
                        <Badge tone={group.explanation.action === '조치 불필요' ? 'neutral' : 'warn'}>
                          {group.explanation.action}
                        </Badge>
                      )}
                      <span className="text-xs text-slate-500 dark:text-slate-400">
                        {group.rows.length}건 · {group.where.join(', ')}
                      </span>
                    </div>
                    {/* The exporter's own text, kept verbatim underneath: it is
                        the record, and the numbers in it (how many rows, how
                        long the worst pass) are what an operator checks. */}
                    {group.explanation && (
                      <ul className="ml-2 mt-0.5 space-y-0.5">
                        {group.rows.map((row, index) => (
                          <li
                            key={`${row.where ?? ''}-${index}`}
                            className="text-xs text-slate-500 dark:text-slate-400"
                          >
                            {row.where ? `${row.where} · ` : ''}
                            {row.text ?? '내용 없음'}
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
              </ul>
            </details>
          </li>
        )}
      </ul>

      {redacted && (
        <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
          문서의 일부 문장에서 경로·계좌로 보이는 값이 가려진 채 전달됐습니다. 사유는 그대로 남아
          있습니다.
        </p>
      )}

      <AsOf>
        <span className="mr-3">
          상태판: {board?.generated_kst ?? '내보낸 시각 알 수 없음'}
          {status.response?.age_seconds != null ? ` · ${ageLabel(status.response.age_seconds)}` : ''}
        </span>
        <span className="mr-3">
          <Term name="paper_cell" /> 상태: {ageLabel(projectionAgeSeconds)} ·{' '}
          {config.pollIntervalMs / 1000}초마다 조회
        </span>
        <span>
          종목 기록: {symbols.document?.generated_kst ?? '내보낸 시각 알 수 없음'}
          {symbols.response?.age_seconds != null ? ` · ${ageLabel(symbols.response.age_seconds)}` : ''}
        </span>
      </AsOf>
    </section>
  );
}
