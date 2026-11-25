import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SymbolsPanel from './SymbolsPanel';
import { useSymbolsDocument } from './queries';
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
    pnl: {
      today: { pnl_krw: '-4050', pnl_basis: 'EXECUTION', closed_round_trips: 1, wins: 0 },
      cumulative: { pnl_krw: '-3150', pnl_basis: 'EXECUTION', closed_round_trips: 4, wins: 2 },
      unresolved: {
        count: 1,
        attempts: [
          {
            status: 'NO_FILL',
            status_label: '비체결 종료',
            side: 'BUY',
            quantity: '1',
            order_price_krw: '175800',
            broker_execution_id: null,
            trading_date: '20261123',
            reason: '미접수(마지막 결과 UNKNOWN → 재조회로 확인)',
            observation: '전송되지 않음(체결 없음)',
          },
        ],
      },
    },
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
    pnl: {
      today: { pnl_krw: '1000', pnl_basis: 'ORDER_PRICE', closed_round_trips: 1, wins: 1 },
      cumulative: { pnl_krw: '1000', pnl_basis: 'ORDER_PRICE', closed_round_trips: 1, wins: 1 },
      unresolved: { count: 0, attempts: [] },
    },
    halt: { error: null, last_flow: null, last_withheld: null, flow_counts: {} },
    ticks: 47,
    error: null,
  };
}

/**
 * A decision-only tenant, as the export has carried one since P2.
 *
 * Every trading cell is null — not zero — because this tree stops at an
 * independent approval step and never orders.
 */
function decisionOnly(): TosSymbolRow {
  return {
    symbol: 'A05612',
    tree_id: 'cp3-setup-d-long',
    kind: 'futures',
    direction: 'LONG',
    decision_only: true,
    session: {
      name: 'long-20261120',
      status: 'ENDED',
      boot_at: '08:46:08',
      end_at: '15:50:01',
      run_rc: 0,
    },
    buy: { fills: null, quantity: null, last: null },
    sell: { fills: null, quantity: null, last: null },
    holding: { quantity: null, lots: null, basis: 'TOS_LEDGER_FIFO_OPEN_LOTS' },
    pnl: null,
    halt: {
      error: null,
      last_flow: { reason: 'STAGE_DENIED', step: 'CANDIDATE_COMMAND_CONSTRUCTION', time_kst: '15:33' },
      last_withheld: null,
      flow_counts: { STAGE_DENIED: 36 },
    },
    ticks: 409,
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

/**
 * The panel is presentational — the page owns the query so the status strip and
 * the tenant cards read the same document. This harness calls the real hook, so
 * the suite still exercises the acceptance and banner paths end to end.
 */
function Harness() {
  return <SymbolsPanel read={useSymbolsDocument()} />;
}

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <Harness />
    </QueryClientProvider>,
  );
}

/**
 * The row whose header cell names `symbol`.
 *
 * A matcher rather than an exact string: the header cell carries the tenant's
 * fixed direction under the symbol, so its accessible name is «005930 LONG».
 */
function rowFor(symbol: string | RegExp): HTMLElement {
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
    await screen.findByRole('rowheader', { name: /005930/ });
    expect(screen.getByRole('rowheader', { name: /000660/ })).toBeInTheDocument();
    expect(screen.getByRole('rowheader', { name: /005380/ })).toBeInTheDocument();
    // Header row, three symbol rows and the totals row, and nothing else.
    expect(screen.getAllByRole('row')).toHaveLength(5);
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

  it('does not call a time 주문 봉 when the document names another basis', async () => {
    // 「주문 봉」 is a claim about where the time came from. A future exporter
    // basis must print its own name, not inherit this label.
    const row = traded();
    row.buy!.last!.time_basis = 'BROKER_CLOCK';
    mocked.mockResolvedValue(response({ document: fixture({ symbols: [row] }) }));
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    const cell = within(rowFor('005930'));
    expect(cell.getByText(/BROKER_CLOCK 14:36/)).toBeInTheDocument();
    expect(cell.queryByText(/주문 봉 14:36/)).not.toBeInTheDocument();
  });

  it('does not call the holding TOS 기준 when the document names another basis', async () => {
    mocked.mockResolvedValue(
      response({ document: fixture({ holding_basis: 'BROKER_BALANCE' }) }),
    );
    renderPanel();
    await screen.findByRole('rowheader', { name: '005930' });
    expect(screen.getByRole('columnheader', { name: /보유 \(BROKER_BALANCE\)/ })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: /TOS 기준/ })).not.toBeInTheDocument();
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
    const row = rowFor('005930');
    // The codes are replaced by their plain-Korean names; the codes themselves
    // stay reachable through each term's own description.
    expect(row).toHaveTextContent('단계에서 거절 · 15:18 · 주문서 작성');
    expect(row).toHaveTextContent('보류 시간 미인정 · 14:33');
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
    expect(banner).toHaveTextContent('아직 거래 현황이 내보내지지 않았습니다');
    expect(banner).toHaveTextContent('sts tos export-symbols');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('points at permissions, not at the data, for an unreadable file', async () => {
    mocked.mockResolvedValue(
      response({ available: false, reason: 'cannot read symbols document: PermissionError', document: null }),
    );
    renderPanel();
    const banner = await screen.findByRole('alert');
    expect(banner).toHaveTextContent('거래 현황 파일을 열지 못했습니다');
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

  it('gives a decision-only tenant no trading cells at all, rather than zeros', async () => {
    mocked.mockResolvedValue(
      response({ document: fixture({ symbols: [traded(), decisionOnly()] }) }),
    );
    renderPanel();
    await screen.findByRole('rowheader', { name: /A05612/ });
    const row = within(rowFor(/A05612/));
    expect(row.getByText('판단 전용')).toBeInTheDocument();
    expect(row.getByText(/주문·체결·손익 해당 없음/)).toBeInTheDocument();
    // Not a single zero anywhere in that row — the claim would be that it
    // traded and came out even.
    expect(row.queryByText('0원')).not.toBeInTheDocument();
    // The halt column survives: a tenant that cannot order still records what
    // the kernel refused.
    expect(row.getByText(/주문서 작성/)).toBeInTheDocument();
  });

  it('shows today’s realized PnL with its sign, its word and its basis', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: /005930/ });
    const row = within(rowFor(/005930/));
    expect(row.getByText('-4,050원')).toBeInTheDocument();
    // Colour is never the only carrier.
    expect(row.getAllByText('손실').length).toBeGreaterThan(0);
    expect(row.getByText('-3,150원')).toBeInTheDocument();
    // A figure built on a sealed limit price says so; an execution-priced one
    // does not need to.
    expect(row.queryByText('지정가 기준')).not.toBeInTheDocument();
    expect(within(rowFor(/005380/)).getAllByText('지정가 기준').length).toBeGreaterThan(0);
  });

  it('says 알 수 없음, not 0, for a row the exporter sent no PnL for', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: /000660/ });
    const row = within(rowFor(/000660/));
    expect(row.getAllByText('알 수 없음').length).toBeGreaterThan(0);
    expect(row.queryByText('0원')).not.toBeInTheDocument();
  });

  it('sums the stock tenants only, and only when every figure is known', async () => {
    // One row without a figure makes the total unknown rather than a sum that
    // silently counts that row as zero.
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: /005930/ });
    const totals = within(screen.getByRole('rowheader', { name: /합계/ }).closest('tr')!);
    expect(totals.getAllByText('알 수 없음').length).toBeGreaterThan(0);
    expect(totals.queryByText(/원$/)).not.toBeInTheDocument();
    expect(totals.getByText(/판단 전용 tenant 와 가상 손익은 합계에 들어가지 않습니다/))
      .toBeInTheDocument();
  });

  it('adds the day up once every stock tenant has a figure', async () => {
    const quiet = idle();
    quiet.pnl = {
      today: { pnl_krw: '0', pnl_basis: null, closed_round_trips: 0, wins: 0 },
      cumulative: { pnl_krw: '0', pnl_basis: null, closed_round_trips: 0, wins: 0 },
      unresolved: { count: 0, attempts: [] },
    };
    mocked.mockResolvedValue(
      response({ document: fixture({ symbols: [traded(), quiet, holding(), decisionOnly()] }) }),
    );
    renderPanel();
    await screen.findByRole('rowheader', { name: /005930/ });
    const totals = within(screen.getByRole('rowheader', { name: /합계/ }).closest('tr')!);
    // -4,050 + 0 + 1,000 — the decision-only row is not in it.
    expect(totals.getByText('-3,050원')).toBeInTheDocument();
    expect(totals.getByText(/주식 tenant 3개/)).toBeInTheDocument();
  });

  it('says so when the summed rows do not share one price basis', async () => {
    // 005930 is priced on the broker's fills and 005380 on a sealed limit:
    // a total that inherited the first row's basis would overstate what is
    // known about the other.
    const quiet = idle();
    quiet.pnl = {
      today: { pnl_krw: '0', pnl_basis: 'EXECUTION', closed_round_trips: 0, wins: 0 },
      cumulative: { pnl_krw: '0', pnl_basis: 'EXECUTION', closed_round_trips: 0, wins: 0 },
      unresolved: { count: 0, attempts: [] },
    };
    mocked.mockResolvedValue(
      response({ document: fixture({ symbols: [traded(), quiet, holding()] }) }),
    );
    renderPanel();
    await screen.findByRole('rowheader', { name: /005930/ });
    const totals = within(screen.getByRole('rowheader', { name: /합계/ }).closest('tr')!);
    expect(totals.getByText(/기준 섞임/)).toBeInTheDocument();
    expect(totals.getByText(/체결가 기준 · 지정가 기준/)).toBeInTheDocument();
  });

  it('says nothing about the basis when every summed row shares one', async () => {
    const quiet = idle();
    quiet.pnl = {
      today: { pnl_krw: '0', pnl_basis: 'EXECUTION', closed_round_trips: 0, wins: 0 },
      cumulative: { pnl_krw: '0', pnl_basis: 'EXECUTION', closed_round_trips: 0, wins: 0 },
      unresolved: { count: 0, attempts: [] },
    };
    mocked.mockResolvedValue(response({ document: fixture({ symbols: [traded(), quiet] }) }));
    renderPanel();
    await screen.findByRole('rowheader', { name: /005930/ });
    const totals = within(screen.getByRole('rowheader', { name: /합계/ }).closest('tr')!);
    expect(totals.queryByText(/기준 섞임/)).not.toBeInTheDocument();
  });

  it('lists the orders the PnL could not account for, outside it', async () => {
    mocked.mockResolvedValue(response());
    renderPanel();
    await screen.findByRole('rowheader', { name: /005930/ });
    expect(screen.getByText(/손익 집계 밖입니다/)).toBeInTheDocument();
    expect(screen.getByText(/매수 · 1주 · 지정가 175,800원 · 비체결 종료/)).toBeInTheDocument();
    expect(screen.getByText(/미접수\(마지막 결과 UNKNOWN/)).toBeInTheDocument();
    expect(screen.getByText(/전송되지 않음\(체결 없음\)/)).toBeInTheDocument();
    expect(screen.getByText(/거래일 20261123/)).toBeInTheDocument();
  });

  it('says so when no tenant is declared at all', async () => {
    mocked.mockResolvedValue(response({ document: fixture({ symbols: [] }) }));
    renderPanel();
    expect(await screen.findByText('선언된 종목 tenant 가 없습니다.')).toBeInTheDocument();
  });
});
