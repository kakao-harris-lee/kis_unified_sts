import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TenantCards from './TenantCards';
import type { SessionsRead, SymbolsRead } from './queries';
import { tosBarsApi, type TosSessionEntry } from '@/lib/dashboard/tosBars';
import type { TosSymbolsDocument } from '@/lib/dashboard/tosSymbols';
import {
  futuresBarsDocument,
  quietBar,
  stockBarsDocument,
  symbolsDocument,
} from '@/test/tosBarsFixture';

vi.mock('@/lib/dashboard/tosBars', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tosBars')>(
    '@/lib/dashboard/tosBars',
  );
  return { ...actual, tosBarsApi: { getBars: vi.fn(), listSessions: vi.fn() } };
});

function entry(overrides: Partial<TosSessionEntry> & { session: string }): TosSessionEntry {
  return {
    date: '2026-11-25',
    kind: 'other',
    direction: null,
    instrument: null,
    run: null,
    age_seconds: 600,
    ...overrides,
  };
}

function sessions(overrides: Partial<SessionsRead> = {}): SessionsRead {
  return {
    response: undefined,
    sessions: [
      entry({ session: 'long-20261125', kind: 'futures', direction: 'LONG' }),
      entry({ session: 'stock-r1-20261125', kind: 'stock', run: 1 }),
      // An older day, which must NOT get a card.
      entry({ session: 'stock-r1-20261110', date: '2026-11-10', kind: 'stock', run: 1 }),
    ],
    truncated: false,
    failed: false,
    ...overrides,
  };
}

function symbols(document: TosSymbolsDocument | null = symbolsDocument()): SymbolsRead {
  return {
    state: document ? 'ready' : 'missing',
    document,
    response: { available: true, reason: null, age_seconds: 30, document },
    authError: false,
  };
}

let client: QueryClient;

function mount(
  overrides: Partial<SessionsRead> = {},
  symbolsRead: SymbolsRead = symbols(),
  selected = 'long-20261125',
) {
  const onSelect = vi.fn();
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(
    <QueryClientProvider client={client}>
      <TenantCards
        sessions={sessions(overrides)}
        symbols={symbolsRead}
        selected={selected}
        onSelect={onSelect}
      />
    </QueryClientProvider>,
  );
  return onSelect;
}

/** The card whose text names `label`. */
function card(label: string): HTMLElement {
  return screen.getByText(label).closest('li') as HTMLElement;
}

beforeEach(() => {
  vi.mocked(tosBarsApi.getBars).mockImplementation(async (session: string) => {
    const document = session.startsWith('long') ? futuresBarsDocument() : stockBarsDocument();
    return { available: true, reason: null, age_seconds: 10, session, document };
  });
});

afterEach(() => client?.clear());

describe('tenant 카드', () => {
  it('shows one card per session of the NEWEST exported day, and no older one', async () => {
    mount();
    await screen.findByText('선물 LONG');
    expect(screen.getByText('주식 005930')).toBeInTheDocument();
    expect(screen.getAllByRole('radio')).toHaveLength(2);
  });

  it('answers «얼마나 가까웠나» with the best in-window bar, not the EOD one', async () => {
    mount();
    await screen.findByText('선물 LONG');
    const futures = within(card('선물 LONG'));
    // 09:14 met everything; 15:45 is an EOD bar whose window is shut. Reading
    // the last bar would make every card say 1/5 every evening.
    expect(await futures.findByText('가장 근접')).toBeInTheDocument();
    expect(futures.getByText('5/5 충족')).toBeInTheDocument();
    expect(futures.getByText('09:14 봉')).toBeInTheDocument();
    expect(futures.queryByText(/15:45/)).not.toBeInTheDocument();
  });

  it('names the conditions missing at the closest bar', async () => {
    // A day whose window opened but whose other four conditions never stood.
    const quiet = futuresBarsDocument();
    quiet.bars = [quietBar('09:30', { entry_window: true }), quietBar('10:00', { entry_window: true })];
    vi.mocked(tosBarsApi.getBars).mockImplementation(async (session: string) => ({
      available: true,
      reason: null,
      age_seconds: 10,
      session,
      document: quiet,
    }));
    mount();
    await screen.findByText('선물 LONG');
    expect(
      await within(card('선물 LONG')).findByText(/가장 근접했을 때 못 채운 조건: 변동성 충분/),
    ).toBeInTheDocument();
  });

  it('marks a futures tenant as decision-only and shows it no fills at all', async () => {
    mount();
    await screen.findByText('선물 LONG');
    const futures = within(card('선물 LONG'));
    expect(futures.getByText('판단 전용')).toBeInTheDocument();
    expect(futures.getByText(/주문을 내지 않는 tenant/)).toBeInTheDocument();
    expect(futures.queryByText('매수')).not.toBeInTheDocument();
  });

  it('shows a stock tenant its fills and the holding TOS still has open', async () => {
    mount();
    const stock = within(card('주식 005930'));
    expect(await stock.findByText('모의 계좌')).toBeInTheDocument();
    expect(stock.getByText('매수').closest('div')).toHaveTextContent('1건');
    expect(stock.getByText('보유').closest('div')).toHaveTextContent('0주');
  });

  it('badges the probe as a probe, with how often it fired', async () => {
    mount();
    // The strategy YAML says R4 is NOT a Setup D signal; a card that showed it
    // as an entry would overstate what the day's strategy did.
    await screen.findByText('주식 005930');
    const badge = await within(card('주식 005930')).findByTitle('R4-M2-PROBE-ENTRY-LONG');
    // Firings and orders are different numbers and both are shown: the stock
    // fixture fires twice and exactly one gets past the gates.
    expect(badge).toHaveTextContent('시험 진입(프로브) 발화 2봉 · 게이트 통과 1');
    expect(within(card('선물 LONG')).queryByTitle('R4-M2-PROBE-ENTRY-LONG')).not.toBeInTheDocument();
  });

  /** The document's row for one tenant, by the session the card names. */
  function rowFor(document: TosSymbolsDocument, session: string) {
    return document.symbols!.find((row) => row.session?.name === session)!;
  }

  it('separates 진행 중 from 대기·차단 and from 종료·시작 안 함', async () => {
    const running = symbolsDocument();
    rowFor(running, 'stock-r1-20261125').session!.status = 'RUNNING';
    mount({}, symbols(running));
    expect(await within(card('주식 005930')).findByText('진행 중 · RUNNING')).toBeInTheDocument();

    const failed = symbolsDocument();
    rowFor(failed, 'stock-r1-20261125').session!.status = 'FAILED';
    client.clear();
    mount({}, symbols(failed));
    expect(screen.getAllByText('대기 · 차단 · FAILED').length).toBeGreaterThan(0);
  });

  it('gives a futures tenant its real session status, now that the document has one', async () => {
    // Until P2 the per-symbol export carried the stock tenants only and every
    // futures card read 「상태 기록 없음」. It now carries the futures rows, so
    // the card states what actually happened — and its boot and end times.
    mount();
    await screen.findByText('선물 LONG');
    expect(within(card('선물 LONG')).getByText('종료')).toBeInTheDocument();
    expect(within(card('선물 LONG')).getByText(/부팅 08:46 · 종료 15:50/)).toBeInTheDocument();
  });

  it('says 상태 기록 없음 for a tenant this document does not cover', async () => {
    // A session the export has no row for at all. 「종료」 would be a claim
    // about a session the page cannot see.
    const partial = symbolsDocument();
    partial.symbols = partial.symbols!.filter((row) => row.session?.name !== 'long-20261125');
    mount({}, symbols(partial));
    await screen.findByText('선물 LONG');
    expect(within(card('선물 LONG')).getByText('상태 기록 없음')).toBeInTheDocument();
  });

  it('shows a stock tenant today’s realized PnL and the running total', async () => {
    mount();
    const stock = within(card('주식 005930'));
    expect(await stock.findByText('-4,050원')).toBeInTheDocument();
    // The hue is never alone: the sign is printed and the word follows.
    expect(stock.getAllByText('손실').length).toBeGreaterThan(0);
    expect(stock.getByText('-3,150원')).toBeInTheDocument();
    // The counts sit beside a tooltip term, so the words are split across
    // elements — assert on the card's text rather than on one node.
    expect(card('주식 005930')).toHaveTextContent('왕복 4회 · 승 2');
  });

  it('badges the orders the PnL could not account for', async () => {
    mount();
    await screen.findByText('주식 005930');
    expect(card('주식 005930')).toHaveTextContent('미해결 주문 1건');
  });

  it('says 손익 기록 없음 rather than 0원 when the row carries no PnL', async () => {
    const blank = symbolsDocument();
    rowFor(blank, 'stock-r1-20261125').pnl = null;
    mount({}, symbols(blank));
    await screen.findByText('주식 005930');
    expect(within(card('주식 005930')).getByText(/기록 없음/)).toBeInTheDocument();
    expect(within(card('주식 005930')).queryByText('0원')).not.toBeInTheDocument();
  });

  it('shows a futures tenant its hypothetical figure, labelled and outlined', async () => {
    mount();
    await screen.findByText('선물 LONG');
    const futures = within(card('선물 LONG'));
    expect(await futures.findByText(/가상 손익\(체결 가정\)/)).toBeInTheDocument();
    expect(futures.getByText('+2.94 pt')).toBeInTheDocument();
    expect(futures.getByText('+147,000원')).toBeInTheDocument();
    expect(futures.getByText(/가상 손익은 실현 손익과\s*합산하지 않습니다/)).toBeInTheDocument();
  });

  it('says 진입 없음 — never 0원 — for a session that decided nothing', async () => {
    vi.mocked(tosBarsApi.getBars).mockImplementation(async (session: string) => {
      const document = futuresBarsDocument();
      document.hypothetical_pnl = {
        ...document.hypothetical_pnl,
        trades: [],
        totals: { trades: 0, wins: 0, points: null, hypothetical_pnl_krw: null, forced_closes: 0 },
      };
      return { available: true, reason: null, age_seconds: 1, session, document };
    });
    mount();
    await screen.findByText('선물 LONG');
    const futures = within(card('선물 LONG'));
    expect(await futures.findByText('진입 없음')).toBeInTheDocument();
    expect(futures.queryByText('0원')).not.toBeInTheDocument();
  });

  it('reports the selection without acting on anything', async () => {
    const onSelect = mount();
    await screen.findByText('주식 005930');
    const radios = screen.getAllByRole('radio');
    await userEvent.click(radios[1]);
    expect(onSelect).toHaveBeenCalledWith('stock-r1-20261125');
    // Radios, not buttons: picking a tenant changes what is shown and nothing else.
    expect(screen.queryAllByRole('button')).toEqual([]);
  });

  it('carries an as-of line on every card', async () => {
    mount();
    await screen.findByText('선물 LONG');
    expect(within(card('선물 LONG')).getByText(/2026-11-25 · 10분 전 내보냄/)).toBeInTheDocument();
  });

  it('says so when the listing could not be had, instead of an empty grid', () => {
    mount({ sessions: [], failed: true });
    expect(screen.getByText(/세션 목록을 가져오지 못했습니다/)).toBeInTheDocument();
  });

  it('distinguishes «nothing exported yet» from «listing failed»', () => {
    mount({ sessions: [], failed: false });
    expect(screen.getByText('내보낸 세션이 아직 없습니다.')).toBeInTheDocument();
  });
});
