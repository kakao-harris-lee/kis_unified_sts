import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TenantCards from './TenantCards';
import type { SessionsRead, SymbolsRead } from './queries';
import { tosBarsApi, type TosSessionEntry } from '@/lib/dashboard/tosBars';
import type { TosSymbolsDocument } from '@/lib/dashboard/tosSymbols';
import { futuresBarsDocument, stockBarsDocument, symbolsDocument } from '@/test/tosBarsFixture';

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

  it('says how close the last judged bar came to entering, and what was missing', async () => {
    mount();
    // The futures fixture's last counted bar is 15:45: entry window shut,
    // volatility fine, stall and reversal false, z short of the threshold.
    expect(await within(card('선물 LONG')).findByText('진입 조건 1/5 충족')).toBeInTheDocument();
    expect(within(card('선물 LONG')).getByText(/못 채운 조건: 진입 시간대/)).toBeInTheDocument();
    expect(within(card('선물 LONG')).getByText('15:45 봉 기준')).toBeInTheDocument();
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
    expect(badge).toHaveTextContent('시험 진입(프로브) 2회');
    expect(within(card('선물 LONG')).queryByTitle('R4-M2-PROBE-ENTRY-LONG')).not.toBeInTheDocument();
  });

  it('separates 진행 중 from 대기·차단 and from 종료·시작 안 함', async () => {
    const running = symbolsDocument();
    running.symbols![0].session!.status = 'RUNNING';
    mount({}, symbols(running));
    expect(await within(card('주식 005930')).findByText('진행 중 · RUNNING')).toBeInTheDocument();

    const failed = symbolsDocument();
    failed.symbols![0].session!.status = 'FAILED';
    client.clear();
    mount({}, symbols(failed));
    expect(screen.getAllByText('대기 · 차단 · FAILED').length).toBeGreaterThan(0);
  });

  it('says 상태 기록 없음 for a tenant this document does not cover', async () => {
    // The per-symbol export carries stock tenants only. 「종료」 would be a
    // claim about a futures session the page cannot see.
    mount();
    await screen.findByText('선물 LONG');
    expect(within(card('선물 LONG')).getByText('상태 기록 없음')).toBeInTheDocument();
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
