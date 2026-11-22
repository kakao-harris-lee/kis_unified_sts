import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SymbolsPanel from './SymbolsPanel';
import {
  tosSymbolsApi,
  type TosSymbolRow,
  type TosSymbolsDocument,
  type TosSymbolsResponse,
} from '@/lib/dashboard/tosSymbols';

vi.mock('@/lib/dashboard/tosSymbols', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tosSymbols')>(
    '@/lib/dashboard/tosSymbols',
  );
  return { ...actual, tosSymbolsApi: { getSymbolsToday: vi.fn() } };
});

const TODAY = '2026-11-20';

/** A traded row — the 2026-11-20 round trip the usage plan §1 records. */
function traded(): TosSymbolRow {
  return {
    symbol: '005930',
    tree_id: 'cp3-setup-d-stock-005930',
    session: {
      name: 'stock-r5-20261120',
      status: 'ENDED',
      boot_at: '14:34:32',
      end_at: '15:40:01',
      run_rc: 0,
    },
    buy: {
      fills: 1,
      quantity: '1',
      last: {
        quantity: '1',
        order_price_krw: '181900',
        execution_price_krw: '181700',
        price_basis: 'EXECUTION',
        broker_execution_id: '0000027053',
        time_kst: '14:36',
        time_basis: 'ORDER_BAR',
      },
    },
    sell: {
      fills: 1,
      quantity: '1',
      last: {
        quantity: '1',
        order_price_krw: '183100',
        execution_price_krw: '183100',
        price_basis: 'EXECUTION',
        broker_execution_id: '0000029505',
        time_kst: '15:16',
        time_basis: 'ORDER_BAR',
      },
    },
    holding: { quantity: '0', lots: 0, basis: 'TOS_LEDGER_FIFO_OPEN_LOTS' },
    halt: {
      error: null,
      last_flow: {
        reason: 'STAGE_DENIED',
        step: 'CANDIDATE_COMMAND_CONSTRUCTION',
        time_kst: '15:18',
      },
      last_withheld: { reason: 'TIME_NOT_ADMITTED', step: 'DECISION_WITHHELD', time_kst: '14:33' },
      flow_counts: { STAGE_DENIED: 3 },
    },
    ticks: 46,
    error: null,
  };
}

/** A tenant that did not run today. */
function idle(): TosSymbolRow {
  return {
    symbol: '000660',
    tree_id: 'cp3-setup-d-stock-000660',
    session: { name: null, status: null, boot_at: null, end_at: null, run_rc: null },
    buy: { fills: 0, quantity: '0', last: null },
    sell: { fills: 0, quantity: '0', last: null },
    holding: { quantity: '0', lots: 0, basis: 'TOS_LEDGER_FIFO_OPEN_LOTS' },
    halt: { error: null, last_flow: null, last_withheld: null, flow_counts: {} },
    ticks: 0,
    error: null,
  };
}

/** A tenant still running, holding one share TOS has not closed. */
function holding(): TosSymbolRow {
  return {
    symbol: '005380',
    tree_id: 'cp3-setup-d-stock-005380',
    session: {
      name: 'stock-005380-r5-20261120',
      status: 'RUNNING',
      boot_at: '14:33:29',
      end_at: null,
      run_rc: null,
    },
    buy: {
      fills: 1,
      quantity: '1',
      last: {
        quantity: '1',
        order_price_krw: '253500',
        execution_price_krw: null,
        price_basis: 'ORDER_PRICE',
        broker_execution_id: '0000026858',
        time_kst: null,
        time_basis: null,
      },
    },
    sell: { fills: 0, quantity: '0', last: null },
    holding: { quantity: '1', lots: 1, basis: 'TOS_LEDGER_FIFO_OPEN_LOTS' },
    halt: { error: null, last_flow: null, last_withheld: null, flow_counts: {} },
    ticks: 47,
    error: null,
  };
}

function fixture(overrides: Partial<TosSymbolsDocument> = {}): TosSymbolsDocument {
  return {
    schema_version: 1,
    date: TODAY,
    generated_kst: '2026-11-20T15:41:02+09:00',
    holding_basis: 'TOS_LEDGER_FIFO_OPEN_LOTS',
    symbols: [traded(), idle(), holding()],
    ...overrides,
  };
}

function response(overrides: Partial<TosSymbolsResponse> = {}): TosSymbolsResponse {
  return { available: true, reason: null, age_seconds: 12, document: fixture(), ...overrides };
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <SymbolsPanel />
    </QueryClientProvider>,
  );
}

/** The row whose header cell names `symbol`. */
function rowFor(symbol: string): HTMLElement {
  return screen.getByRole('rowheader', { name: symbol }).closest('tr') as HTMLElement;
}

const mocked = vi.mocked(tosSymbolsApi.getSymbolsToday);

beforeEach(() => {
  // The panel compares the document's date against today in KST. Pin the clock
  // so a run after midnight Seoul does not flip the "not today" banner on.
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date('2026-11-20T06:00:00Z')); // 15:00 KST
  mocked.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('SymbolsPanel', () => {
  it('shows one row per symbol — the plan §5 acceptance, on one screen', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    expect(screen.getByRole('rowheader', { name: '000660' })).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: '005380' })).toBeInTheDocument();
    // Header row plus three symbol rows, and nothing else.
    expect(screen.getAllByRole('row')).toHaveLength(4);
  });

  it('renders today’s buys and sells with their price basis and order bar', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    const row = within(rowFor('005930'));
    expect(row.getByText(/체결가 181,700/)).toBeInTheDocument();
    expect(row.getByText(/주문 봉 14:36/)).toBeInTheDocument();
    expect(row.getByText(/체결가 183,100/)).toBeInTheDocument();
    expect(row.getByText(/0000029505/)).toBeInTheDocument();
  });

  it('labels a limit-price fill as 지정가, never as an execution price', async () => {
    // The exporter falls back to the sealed order price when the evidence has
    // no broker average. Showing that as 체결가 would overstate what is known.
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005380' });
    const row = within(rowFor('005380'));
    expect(row.getByText(/지정가 253,500/)).toBeInTheDocument();
    expect(row.queryByText(/체결가/)).not.toBeInTheDocument();
  });

  it('says 시각 없음 rather than inventing one when the order bar is unknown', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005380' });
    expect(within(rowFor('005380')).getByText(/시각 없음/)).toBeInTheDocument();
  });

  it('shows the holding TOS still has open, and labels the basis as TOS 기준', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005380' });
    expect(within(rowFor('005380')).getByText('1주')).toBeInTheDocument();
    expect(within(rowFor('005380')).getByText('1 lot')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /보유 \(TOS 기준\)/ })).toBeInTheDocument();
    expect(screen.getByText(/브로커 잔고 조회가 아니라/)).toBeInTheDocument();
  });

  it('shows the last flow halt with its bar time, and the withholding separately', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    const row = within(rowFor('005930'));
    expect(row.getByText(/STAGE_DENIED · 15:18/)).toBeInTheDocument();
    expect(row.getByText(/보류 TIME_NOT_ADMITTED · 14:33/)).toBeInTheDocument();
  });

  it('marks a tenant that did not run today instead of dropping its row', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '000660' });
    const row = within(rowFor('000660'));
    expect(row.getByText('오늘 시작 안 함')).toBeInTheDocument();
    expect(row.getAllByText('없음').length).toBeGreaterThanOrEqual(2);
  });

  it('separates a running session from a settled one', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    expect(within(rowFor('005930')).getByText(/종료 · ENDED/)).toBeInTheDocument();
    expect(within(rowFor('005380')).getByText(/진행 중 · RUNNING/)).toBeInTheDocument();
  });

  it('warns when the document is not today’s, without hiding the rows', async () => {
    mocked.mockResolvedValue(response({ document: fixture({ date: '2026-11-18' }) }));
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    expect(screen.getByText(/오늘\(KST\)의 기록이 아닙니다/)).toBeInTheDocument();
    // The numbers stay on screen — they are true of 11-18, just not of today.
    expect(within(rowFor('005930')).getByText(/체결가 181,700/)).toBeInTheDocument();
  });

  it('does not warn when the document is today’s', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    expect(screen.queryByText(/오늘\(KST\)의 기록이 아닙니다/)).not.toBeInTheDocument();
  });

  it('keeps a row whose leaf could not be read, with the reason', async () => {
    const broken: TosSymbolRow = { ...idle(), error: 'OperationalError' };
    mocked.mockResolvedValue(response({ document: fixture({ symbols: [traded(), broken] }) }));
    renderPanel();
    await screen.findByRole('rowheader', { name: '000660' });
    expect(within(rowFor('000660')).getByText(/OperationalError/)).toBeInTheDocument();
  });

  it('tells the operator how to produce a document that is not there yet', async () => {
    mocked.mockResolvedValue(
      response({ available: false, reason: 'symbols document absent', document: null }),
    );
    renderPanel();
    const banner = await screen.findByRole('alert');
    expect(banner).toHaveTextContent('아직 종목 현황이 내보내지지 않았습니다');
    expect(banner).toHaveTextContent('sts tos export-symbols');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('points at permissions, not at the data, for an unreadable file', async () => {
    mocked.mockResolvedValue(
      response({ available: false, reason: 'cannot read symbols document: PermissionError', document: null }),
    );
    renderPanel();
    const banner = await screen.findByRole('alert');
    expect(banner).toHaveTextContent('종목 현황 파일을 열지 못했습니다');
    expect(banner).toHaveTextContent('접근 권한');
  });

  it('asks for the API key on a 401 instead of showing a format error', async () => {
    mocked.mockRejectedValue(
      new AxiosError('unauthorized', '401', undefined, undefined, {
        status: 401,
        data: {},
        statusText: 'Unauthorized',
        headers: {},
        config: { headers: {} as never },
      }),
    );
    renderPanel();
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('조회 인증을 확인해 주세요'),
    );
  });

  it('renders no table at all when the document version is unsupported', async () => {
    mocked.mockResolvedValue(
      response({ document: { schema_version: 2, symbols: [traded()] } as TosSymbolsDocument }),
    );
    renderPanel();
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument());
    // Banner and body must agree: a rejected document never renders rows.
    expect(screen.queryByRole('rowheader', { name: '005930' })).not.toBeInTheDocument();
  });

  it('says so when no tenant is declared at all', async () => {
    mocked.mockResolvedValue(response({ document: fixture({ symbols: [] }) }));
    renderPanel();
    expect(await screen.findByText('선언된 종목 tenant 가 없습니다.')).toBeInTheDocument();
  });
});
