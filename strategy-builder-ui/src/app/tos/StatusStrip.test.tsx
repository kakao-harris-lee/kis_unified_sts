import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StatusStrip from './StatusStrip';
import type { StatusRead, SymbolsRead } from './queries';
import type { ProjectionState, TosProjection } from '@/lib/dashboard/tos';
import type { TosStatusDocument } from '@/lib/dashboard/tosStatus';
import type { TosSymbolsDocument } from '@/lib/dashboard/tosSymbols';
import { statusDocument, symbolsDocument } from '@/test/tosBarsFixture';
import { tosFixture } from '@/test/tosFixture';

const projection = tosFixture();

function symbols(document: TosSymbolsDocument | null = symbolsDocument()): SymbolsRead {
  return {
    state: document ? 'ready' : 'missing',
    document,
    response: { available: true, reason: null, age_seconds: 42, document },
    authError: false,
  };
}

function status(
  document: TosStatusDocument | null = statusDocument(),
  overrides: Partial<StatusRead> = {},
): StatusRead {
  return {
    state: document ? 'ready' : 'missing',
    document,
    response: { available: document != null, reason: null, age_seconds: 55, document },
    authError: false,
    ...overrides,
  };
}

function mount(
  state: ProjectionState = 'recent',
  overrides: Partial<TosProjection> | null = {},
  reads: { status?: StatusRead; symbols?: SymbolsRead } = {},
) {
  render(
    <StatusStrip
      projectionState={state}
      projection={overrides === null ? null : { ...projection, ...overrides }}
      projectionAgeSeconds={3}
      status={reads.status ?? status()}
      symbols={reads.symbols ?? symbols()}
      stateLabel="아직 상태 파일이 없습니다"
    />,
  );
}

function strip(): HTMLElement {
  return screen.getByRole('region', { name: '지금 상태' });
}

/**
 * The chip whose label is `label`, as a whole list item.
 *
 * `getAllByText` because the same words also appear in the as-of line below
 * the chips («paper 셀 상태: …»), and the chip is the one inside a list item.
 */
function chip(label: string): HTMLElement {
  const found = within(strip())
    .getAllByText(label)
    .map((node) => node.closest('li'))
    .find((item): item is HTMLLIElement => item !== null);
  if (!found) throw new Error(`chip not found: ${label}`);
  return found;
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date('2026-11-25T06:00:00Z')); // 15:00 KST
});

afterEach(() => vi.useRealTimers());

describe('상태 띠', () => {
  it('reports the board’s own counts rather than recounting the issues', () => {
    mount();
    // The exporter took these from the same list it shipped; recounting here
    // is how the page and `sts tos status` would come to disagree.
    expect(chip('상태판')).toHaveTextContent('막힘 0 · 확인 2');
  });

  it('says «오늘 문서 아님» for a board from another day, before any count', () => {
    // A board from yesterday still reads «0 blocks». Showing that as «이상
    // 없음» is exactly how a stopped exporter passes for a healthy morning.
    const old = statusDocument();
    old.date = '2026-11-18';
    mount('recent', {}, { status: status(old) });
    expect(chip('상태판')).toHaveTextContent('오늘 문서 아님');
    expect(chip('상태판')).toHaveTextContent('기준일 2026-11-18');
  });

  it('says 갱신 멈춤 for a board nothing has rewritten since 10:00', () => {
    // 2026-11-25 06:00Z is 15:00 KST, inside the export window; the board is
    // today's and clean, and only its age says the cron died five hours ago.
    const clean = statusDocument();
    clean.checks = 0;
    clean.issues = [];
    mount('recent', {}, {
      status: {
        state: 'ready',
        document: clean,
        response: { available: true, reason: null, age_seconds: 18000, document: clean },
        authError: false,
      },
    });
    expect(chip('상태판')).toHaveTextContent('갱신 멈춤');
    expect(chip('상태판')).toHaveTextContent('5시간 0분 전 기록');
    expect(chip('상태판')).not.toHaveTextContent('이상 없음');
    // The counts are relabelled, not hidden.
    expect(chip('상태판')).toHaveTextContent('마지막 기록 기준 막힘 0 · 확인 0');
    expect(chip('상태판').querySelector('span')?.className).toContain('amber');
  });

  it('says 이상 없음 only when today’s board counted nothing at all', () => {
    const clean = statusDocument();
    clean.checks = 0;
    clean.issues = [];
    mount('recent', {}, { status: status(clean) });
    expect(chip('상태판')).toHaveTextContent('이상 없음');
  });

  it('keeps 이상 없음 outside the export window, where nothing should rewrite it', () => {
    vi.setSystemTime(new Date('2026-11-25T11:00:00Z')); // 20:00 KST
    const clean = statusDocument();
    clean.checks = 0;
    clean.issues = [];
    mount('recent', {}, {
      status: {
        state: 'ready',
        document: clean,
        response: { available: true, reason: null, age_seconds: 18000, document: clean },
        authError: false,
      },
    });
    expect(chip('상태판')).toHaveTextContent('이상 없음');
  });

  it('keeps «확인» neutral', () => {
    // Every ordinary session records a check-level line; amber every day is
    // amber nobody reads.
    mount();
    expect(chip('상태판').querySelector('span')?.className).toContain('slate');
  });

  it('raises «막힘» to amber, with the warning icon', () => {
    const blocked = statusDocument();
    blocked.blocked = 1;
    blocked.issues = [{ level: '막힘', where: 'stock-r1-20261125', text: '세션이 멈췄습니다' }];
    mount('recent', {}, { status: status(blocked) });
    expect(chip('상태판').querySelector('span')?.className).toContain('amber');
  });

  it('shows the clean-day streak against its target, with its meaning', () => {
    mount();
    const streak = chip('깨끗한 날 · long');
    expect(streak).toHaveTextContent('5/5일 달성');
    expect(within(streak).getByText(/깨끗한 날/)).toHaveAttribute(
      'title',
      expect.stringContaining('막힘 없이 끝난 거래일'),
    );
  });

  it('says a streak that could not be counted is unknown, never zero', () => {
    const broken = statusDocument();
    broken.clean_streak = [{ label: 'long', days: null, target_days: 5, error: '달력을 읽지 못했다' }];
    mount('recent', {}, { status: status(broken) });
    expect(chip('깨끗한 날 · long')).toHaveTextContent('알 수 없음');
    expect(chip('깨끗한 날 · long')).toHaveTextContent('달력을 읽지 못했다');
  });

  it('does not read a board that skipped the liveness check as «상주 아님»', () => {
    // `live_check: false` means /proc was never read — on any past date. Both
    // flags are then false and say nothing.
    mount();
    expect(chip('paper 셀')).toHaveTextContent('상주 확인 안 함');
    expect(chip('paper 셀')).not.toHaveTextContent('상주 아님');
  });

  it('says 상주 중 when the board actually checked and both were up', () => {
    const live = statusDocument();
    live.paper = { ...live.paper, live_check: true, runtime_alive: true, driver_alive: true };
    mount('recent', {}, { status: status(live) });
    expect(chip('paper 셀')).toHaveTextContent('상주 중');
  });

  it('raises a latched halt above a merely stale read', () => {
    mount('recent', { driver: { wired: true, halt_latched: true, halt_reason: 'DRIVER_FAULT' } });
    expect(within(strip()).getByText('실행 중단 · DRIVER_FAULT')).toBeInTheDocument();
  });

  it('counts the tenant sessions from the board, which covers all five trees', () => {
    mount();
    expect(chip('tenant 2개')).toHaveTextContent('종료 2');
    expect(chip('tenant 2개').querySelector('span')?.className).toContain('emerald');
  });

  it('does not draw a tenant that never booted as 이상 없음', () => {
    // An absence is not a clean run: the board lists the tenant and it has no
    // session at all.
    const idle = statusDocument();
    idle.tenants = idle.tenants!.map((tenant) => ({ ...tenant, status: null }));
    mount('recent', {}, { status: status(idle) });
    expect(chip('tenant 2개')).toHaveTextContent('시작 안 함 2');
    expect(chip('tenant 2개').querySelector('span')?.className).toContain('amber');
  });

  it('drops P1’s day-wide gate count, which the board now answers for', () => {
    // It read in the hundreds on every ordinary day — every tenant records
    // STAGE_DENIED on exits it has no position to close — so it cost the first
    // screen a chip row to say nothing an operator could act on. The counts
    // stay where they have context: ③ per bar, ⑤ per stretch, ④ per tenant.
    mount();
    expect(within(strip()).queryByText('게이트가 막은 판단')).not.toBeInTheDocument();
  });

  it('warns about the symbols document’s day only when it is not today’s', () => {
    const old = symbolsDocument();
    old.date = '2026-11-18';
    mount('recent', {}, { symbols: symbols(old) });
    expect(chip('종목 기록 기준일')).toHaveTextContent('2026-11-18 · 오늘 아님');
  });

  it('keeps the strip short on a normal day by dropping that chip', () => {
    const today = symbolsDocument();
    today.date = '2026-11-25';
    mount('recent', {}, { symbols: symbols(today) });
    expect(within(strip()).queryByText('종목 기록 기준일')).not.toBeInTheDocument();
  });

  it('lists the issues under one disclosure, blocks first', () => {
    const mixed = statusDocument();
    mixed.blocked = 1;
    mixed.issues = [
      { level: '확인', where: 'long-20261125', text: '확인할 것이 있다' },
      { level: '막힘', where: 'stock-r1-20261125', text: '세션이 멈췄습니다' },
    ];
    mount('recent', {}, { status: status(mixed) });
    const details = within(strip()).getByText(/이슈 2건/).closest('details') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    const items = within(details).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('세션이 멈췄습니다');
    expect(items[1]).toHaveTextContent('확인할 것이 있다');
  });

  it('says when the reader had to mask part of a sentence', () => {
    mount('recent', {}, { status: status(statusDocument(), { response: { available: true, reason: null, age_seconds: 1, redacted: true, document: statusDocument() } }) });
    expect(within(strip()).getByText(/경로·계좌로 보이는 값이 가려진/)).toBeInTheDocument();
  });

  it('names the kind of absence when the board itself is missing', () => {
    mount('recent', {}, { status: status(null) });
    expect(chip('상태판')).toHaveTextContent('아직 상태판이 없습니다');
    expect(within(strip()).queryByText(/이슈 /)).not.toBeInTheDocument();
  });

  it('states that it only repeats what the host judged', () => {
    mount();
    expect(within(strip()).getByText(/주문을 내리거나 멈출 수 있는 화면이 아닙니다/))
      .toBeInTheDocument();
  });
});
