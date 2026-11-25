import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import BarsPanel from './BarsPanel';
import {
  tosBarsApi,
  type TosBarsDocument,
  type TosBarsResponse,
  type TosSessionEntry,
  type TosSessionsResponse,
} from '@/lib/dashboard/tosBars';

vi.mock('@/lib/dashboard/tosBars', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tosBars')>(
    '@/lib/dashboard/tosBars',
  );
  return { ...actual, tosBarsApi: { getBars: vi.fn(), listSessions: vi.fn() } };
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

/** One entry of the listing the picker reads (GET /api/tos/sessions). */
function entry(overrides: Partial<TosSessionEntry> & { session: string }): TosSessionEntry {
  return {
    date: null,
    kind: 'other',
    direction: null,
    instrument: null,
    run: null,
    age_seconds: 60,
    ...overrides,
  };
}

/** Two trading days: today's futures pair and three stock tenants. */
function sessionList(): TosSessionEntry[] {
  return [
    entry({ session: 'long-20261125', date: '2026-11-25', kind: 'futures', direction: 'LONG' }),
    entry({ session: 'short-20261125', date: '2026-11-25', kind: 'futures', direction: 'SHORT' }),
    entry({
      session: 'stock-000660-r1-20261125',
      date: '2026-11-25',
      kind: 'stock',
      instrument: '000660',
      run: 1,
    }),
    // The tenant whose name predates the per-symbol convention: no instrument
    // in the name, so the label has to come from the UI's own config.
    entry({ session: 'stock-r1-20261125', date: '2026-11-25', kind: 'stock', run: 1 }),
    entry({ session: 'stock-r1-20261110', date: '2026-11-10', kind: 'stock', run: 1 }),
  ];
}

let client: QueryClient;

function mount(
  response?: Partial<TosBarsResponse>,
  sessions?: Partial<TosSessionsResponse> | Error,
) {
  vi.mocked(tosBarsApi.getBars).mockImplementation(async () => ({
    available: true,
    reason: null,
    age_seconds: 12,
    session: 'stock-r1-20261110',
    document: fixture(),
    ...response,
  }));
  if (sessions instanceof Error) {
    vi.mocked(tosBarsApi.listSessions).mockRejectedValue(sessions);
  } else {
    vi.mocked(tosBarsApi.listSessions).mockImplementation(async () => ({
      available: true,
      reason: null,
      sessions: sessionList(),
      truncated: false,
      ...sessions,
    }));
  }
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(
    <QueryClientProvider client={client}>
      <BarsPanel />
    </QueryClientProvider>,
  );
}

/** The listing unavailable — the panel must still reach a session. */
const NO_LISTING: Partial<TosSessionsResponse> = {
  available: false,
  reason: 'bars directory absent',
  sessions: [],
};

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

  it('offers the exported sessions grouped by day, newest first', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    const picker = screen.getByLabelText('세션');
    expect(picker.tagName).toBe('SELECT');
    // The sentinel stays the first option: the panel opens on it, and it is
    // the one choice that works when the listing does not.
    const options = within(picker).getAllByRole('option');
    expect(options[0]).toHaveValue('latest');
    expect(options.map((option) => option.textContent)).toEqual([
      '최신 세션 (latest)',
      '11-25 · 선물 LONG',
      '11-25 · 선물 SHORT',
      '11-25 · 주식 000660',
      // The legacy tenant's symbol is not in its name; the label comes from
      // src/config/tos-control-plane.json, not from a literal in a branch.
      '11-25 · 주식 005930',
      '11-10 · 주식 005930',
    ]);
    expect(
      within(picker)
        .getAllByRole('group')
        .map((group) => group.getAttribute('label')),
    ).toEqual(['2026-11-25', '2026-11-10']);
  });

  it('keeps the raw session id on the option the label stands for', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    expect(screen.getByRole('option', { name: '11-25 · 주식 000660' })).toHaveAttribute(
      'title',
      'stock-000660-r1-20261125',
    );
  });

  it('asks for the session the operator picked', async () => {
    mount();
    await screen.findByText('바 기록을 조회했습니다');
    await userEvent.selectOptions(screen.getByLabelText('세션'), 'long-20261125');
    await waitFor(() => expect(tosBarsApi.getBars).toHaveBeenCalledWith('long-20261125'));
    expect(screen.getByText(/요청한 세션: long-20261125/)).toBeInTheDocument();
  });

  it('says when the listing is only the newest part of the directory', async () => {
    mount({}, { truncated: true });
    await screen.findByText('바 기록을 조회했습니다');
    expect(screen.getByText('최근 5개 세션만 표시합니다.')).toBeInTheDocument();
  });

  it('keeps a session the listing does not carry selectable', async () => {
    // The operator typed it while the listing was down, and the listing then
    // arrived without it. A blank select over a rendered session is worse than
    // an option that names the id.
    mount({}, NO_LISTING);
    await screen.findByText('바 기록을 조회했습니다');
    await userEvent.type(screen.getByLabelText('세션'), 'long-20261001');
    await userEvent.click(screen.getByRole('button', { name: '조회' }));
    await waitFor(() => expect(tosBarsApi.getBars).toHaveBeenCalledWith('long-20261001'));

    vi.mocked(tosBarsApi.listSessions).mockResolvedValue({
      available: true,
      reason: null,
      sessions: sessionList(),
      truncated: false,
    });
    await client.refetchQueries({ queryKey: ['tos-sessions'] });
    await waitFor(() => expect(screen.getByLabelText('세션').tagName).toBe('SELECT'));
    const picker = screen.getByLabelText('세션');
    expect(picker).toHaveValue('long-20261001');
    expect(within(picker).getByRole('option', { name: 'long-20261001' })).toBeInTheDocument();
  });

  it('falls back to the text box when the listing is unavailable', async () => {
    mount({}, NO_LISTING);
    await screen.findByText('바 기록을 조회했습니다');
    const box = screen.getByLabelText('세션');
    expect(box.tagName).toBe('INPUT');
    // latest still works, and a session is still reachable by name — the whole
    // point of keeping the box rather than rendering an empty dropdown.
    expect(tosBarsApi.getBars).toHaveBeenCalledWith('latest');
    await userEvent.type(box, 'long-20261110');
    await userEvent.click(screen.getByRole('button', { name: '조회' }));
    await waitFor(() => expect(tosBarsApi.getBars).toHaveBeenCalledWith('long-20261110'));
  });

  it('falls back to the text box when the listing call itself fails', async () => {
    // The picker is the only thing the operator loses: the bars query never
    // waited on the listing, so the panel still opened on `latest`.
    mount({}, new Error('offline'));
    await screen.findByText('바 기록을 조회했습니다');
    expect(screen.getByLabelText('세션').tagName).toBe('INPUT');
    expect(tosBarsApi.getBars).toHaveBeenCalledWith('latest');
  });

  it('falls back to the text box when nothing has been exported yet', async () => {
    mount({}, { available: true, sessions: [] });
    await screen.findByText('바 기록을 조회했습니다');
    expect(screen.getByLabelText('세션').tagName).toBe('INPUT');
  });

  it('falls back to the text box on a body that lost its sessions key', async () => {
    // A proxy error page, or a future route revision. Grouping an undefined
    // list would throw and take the whole panel — including the bars — down.
    mount({}, { available: true, sessions: undefined as unknown as [] });
    await screen.findByText('바 기록을 조회했습니다');
    expect(screen.getByLabelText('세션').tagName).toBe('INPUT');
  });

  it('falls back to latest when the operator submits an empty box', async () => {
    mount({}, NO_LISTING);
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
    // Picking a session applies on change, so the picker needs no button at
    // all; the fallback box keeps its 조회 and nothing else.
    expect(within(panel).queryAllByRole('button')).toEqual([]);
  });

  it('offers no command surface in the fallback either', async () => {
    mount({}, NO_LISTING);
    await screen.findByText('바 기록을 조회했습니다');
    const panel = screen.getByRole('region', { name: '바별 결정 점검' });
    expect(within(panel).getAllByRole('button').map((b) => b.textContent)).toEqual(['조회']);
  });
});
