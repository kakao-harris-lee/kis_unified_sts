import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BarsPanel from './BarsPanel';
import { tosBarsApi, type TosBarsDocument, type TosBarsResponse } from '@/lib/dashboard/tosBars';

vi.mock('@/lib/dashboard/tosBars', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tosBars')>(
    '@/lib/dashboard/tosBars',
  );
  return { ...actual, tosBarsApi: { getBars: vi.fn() } };
});

/** Two bars: one withheld (not evaluated), one counted whose view ≠ journal. */
function fixture(): TosBarsDocument {
  return {
    schema_version: 1,
    session: 'stock-r1-20261110',
    instrument: '005930',
    strategy: { sha256: 'df164ee2461aa133ac6506889cd53c3618134a42403e2c302128cb3c54fd3b00' },
    bindings: { values: { z_entry_max_x1000: -1800 } },
    window: { from: null, to: null },
    default: { rule_id: 'R0-DEFAULT-NO-ACTION', decision_kind: 'NO_ACTION' },
    bars: [
      {
        time_kst: '09:00',
        fields: { close_x100: 19940000, vwap_x100: 19963333 },
        env_values: {},
        evaluation: 'withheld',
        counted: false,
        flags: '--W-',
        rules: [],
        decision_rule_id: null,
        decision_kind: null,
        evidence: { joined: true, withheld_reason: 'TIME_NOT_ADMITTED' },
      },
      {
        time_kst: '09:01',
        fields: { close_x100: 19910000, vwap_x100: 19957162, hi_vol: false },
        env_values: { close_x100: 19910000, vwap_x100: 19957162, hi_vol: true },
        evaluation: 'engine_view',
        counted: true,
        flags: 'V---',
        view_diff: { hi_vol: { value_view: 'true', journal: 'false' } },
        decision_rule_id: 'R2-EXIT-VWAP-REVERTED',
        decision_kind: 'FLAT',
        rules: [
          { label: 'R1', rule_id: 'R1-ENTRY-LONG', fired: false, compares: [] },
          { label: 'R2', rule_id: 'R2-EXIT-VWAP-REVERTED', fired: true, compares: [] },
        ],
        evidence: {
          joined: true,
          outcome_type: 'Proposal',
          halt_step: 'CANDIDATE_COMMAND_CONSTRUCTION',
          halt_reason: 'STAGE_DENIED',
        },
      },
    ],
    summary: {
      bars: 2,
      counted_bars: 1,
      withheld_bars: 1,
      substituted_bars: 0,
      view_diff_bars: 1,
      view_diff_fields: { hi_vol: 1 },
      disagreement_bars: 0,
      not_comparable_bars: 0,
      rules: [
        {
          label: 'R1',
          rule_id: 'R1-ENTRY-LONG',
          fired_bars: 0,
          bars: 1,
          fired_pct: 0,
          compares: [
            { index: 1, expression: 'entry_window EQ true', failed_bars: 1, bars: 1, failed_pct: 100 },
          ],
        },
        {
          label: 'R2',
          rule_id: 'R2-EXIT-VWAP-REVERTED',
          fired_bars: 1,
          bars: 1,
          fired_pct: 100,
          compares: [
            { index: 1, expression: 'vwap_reverted EQ true', failed_bars: 0, bars: 1, failed_pct: 0 },
          ],
        },
      ],
      decisions: { 'R2-EXIT-VWAP-REVERTED': 1 },
      evidence_outcomes: { Proposal: 1, TIME_NOT_ADMITTED: 1 },
      evidence_halts: { 'STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION': 1 },
      unjoined: {},
      value_view_refused: {},
    },
  };
}

let client: QueryClient;

function mount(response?: Partial<TosBarsResponse>) {
  vi.mocked(tosBarsApi.getBars).mockImplementation(async () => ({
    available: true,
    reason: null,
    age_seconds: 12,
    session: 'stock-r1-20261110',
    document: fixture(),
    ...response,
  }));
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(
    <QueryClientProvider client={client}>
      <BarsPanel />
    </QueryClientProvider>,
  );
}

beforeEach(() => vi.resetAllMocks());
afterEach(() => client?.clear());

describe('TOS bars panel', () => {
  it('opens on the latest session without the operator naming one', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    expect(tosBarsApi.getBars).toHaveBeenCalledWith('latest');
  });

  it('renders the summary denominators and the per-comparison shares', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    const panel = screen.getByRole('region', { name: '바별 결정 점검' });
    // The denominator is the COUNTED bars, not all rendered bars.
    expect(within(panel).getByText(/분모 1봉/)).toBeInTheDocument();
    expect(within(panel).getByText(/보류 1봉/)).toBeInTheDocument();
    const row = within(panel).getByText('1 entry_window EQ true').closest('tr');
    expect(row).not.toBeNull();
    expect(within(row as HTMLElement).getByText('100.0%')).toBeInTheDocument();
    expect(within(row as HTMLElement).getByText('1 거짓')).toBeInTheDocument();
  });

  it('reports a view/journal difference with the field name', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    const panel = screen.getByRole('region', { name: '바별 결정 점검' });
    expect(within(panel).getByText(/1봉 · hi_vol 1/)).toBeInTheDocument();
  });

  it('draws the price/VWAP chart and the per-rule bands', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    expect(screen.getByRole('group', { name: '가격과 VWAP' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: '규칙별 통과 띠' })).toBeInTheDocument();
    // One labelled row per rule plus one per flag. Scoped to the band's own
    // label list: the summary table repeats the rule ids, and a page-wide query
    // would pass on either of them.
    const names = screen.getByRole('list', { name: '띠 이름' });
    expect(within(names).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'R1 · R1-ENTRY-LONG',
      'R2 · R2-EXIT-VWAP-REVERTED',
      'V · 엔진 값이 journal 과 다름',
      'D · 결정이 엔진 결과와 다름',
      'W · 보류(평가 안 함)',
      'U · journal 로 대체(분모 밖)',
    ]);
  });

  it('asks for the session the operator typed', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    await userEvent.clear(screen.getByLabelText('세션'));
    await userEvent.type(screen.getByLabelText('세션'), 'long-20261110');
    await userEvent.click(screen.getByRole('button', { name: '조회' }));
    await waitFor(() => expect(tosBarsApi.getBars).toHaveBeenCalledWith('long-20261110'));
  });

  it('falls back to latest when the operator submits an empty box', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    await userEvent.click(screen.getByRole('button', { name: '조회' }));
    await waitFor(() => expect(tosBarsApi.getBars).toHaveBeenLastCalledWith('latest'));
  });

  it('shows a missing document as a normal state with the export command', async () => {
    mount({ available: false, reason: 'bars document absent', document: null });
    await screen.findByText('이 세션의 바 기록이 아직 없습니다');
    expect(screen.getByText(/sts tos export-bars/)).toBeInTheDocument();
    expect(screen.queryByRole('group', { name: '가격과 VWAP' })).not.toBeInTheDocument();
  });

  it('sends an unreadable document to permissions, not to the data', async () => {
    mount({
      available: false,
      reason: 'cannot read bars document: PermissionError',
      document: null,
    });
    await screen.findByText('바 기록 파일을 열지 못했습니다');
    expect(screen.getByText(/접근 권한/)).toBeInTheDocument();
  });

  it('refuses to render a document of an unsupported version', async () => {
    mount({ available: true, document: { ...fixture(), schema_version: 99 } });
    await screen.findByText('바 기록 형식 오류');
    expect(screen.queryByRole('group', { name: '가격과 VWAP' })).not.toBeInTheDocument();
  });

  it('names a rejected session id as a client-side mistake', async () => {
    mount({
      available: false,
      reason: 'invalid session id (expected ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$, got 9 chars)',
      document: null,
    });
    await screen.findByText('세션 이름을 확인해 주세요');
    // The hint names a valid example; the API's own reason (which carries the
    // regex, not the rejected id) is never rendered.
    const banner = screen.getByRole('alert');
    expect(within(banner).getByText(/예: stock-r1-20261110/)).toBeInTheDocument();
    expect(within(banner).queryByText(/A-Za-z0-9/)).not.toBeInTheDocument();
  });

  it('reports an auth failure as auth, not as missing data', async () => {
    vi.mocked(tosBarsApi.getBars).mockRejectedValue(
      new AxiosError('denied', '401', undefined, undefined, {
        status: 401,
        data: {},
        statusText: 'Unauthorized',
        headers: {},
        config: { headers: {} as never },
      }),
    );
    client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
    render(
      <QueryClientProvider client={client}>
        <BarsPanel />
      </QueryClientProvider>,
    );
    await screen.findByText('조회 인증을 확인해 주세요');
  });

  it('offers no command surface — it is a read model', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    const panel = screen.getByRole('region', { name: '바별 결정 점검' });
    expect(within(panel).getAllByRole('button').map((b) => b.textContent)).toEqual(['조회']);
  });
});
