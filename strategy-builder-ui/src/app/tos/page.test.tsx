import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TosPage from './page';
import {
  isAcceptedProjection,
  tosApi,
  type TosProjection,
  type TosProjectionResponse,
} from '@/lib/dashboard/tos';
import { tosBarsApi, type TosSessionEntry } from '@/lib/dashboard/tosBars';
import { tosSymbolsApi } from '@/lib/dashboard/tosSymbols';
import { tosFixture } from '@/test/tosFixture';
import { futuresBarsDocument, stockBarsDocument, symbolsDocument } from '@/test/tosBarsFixture';
const fixture = tosFixture();
const unknown = tosFixture(true);
import config from '@/config/tos-control-plane.json';

// `accept` lets a test replace the shared acceptance predicate. The page must
// read THAT export rather than re-deriving the condition locally (지적 11).
const shared = vi.hoisted(() => ({ accept: null as null | ((p: unknown) => boolean) }));
vi.mock('@/lib/dashboard/tos', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tos')>('@/lib/dashboard/tos');
  return {
    ...actual,
    tosApi: { getProjection: vi.fn() },
    isAcceptedProjection: (p: unknown) => (shared.accept ?? actual.isAcceptedProjection)(p as TosProjection),
  };
});
vi.mock('@/lib/dashboard/tosBars', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tosBars')>(
    '@/lib/dashboard/tosBars',
  );
  return { ...actual, tosBarsApi: { getBars: vi.fn(), listSessions: vi.fn() } };
});
vi.mock('@/lib/dashboard/tosSymbols', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tosSymbols')>(
    '@/lib/dashboard/tosSymbols',
  );
  return { ...actual, tosSymbolsApi: { getSymbolsToday: vi.fn() } };
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

let client: QueryClient;

function mount(response?: Partial<TosProjectionResponse>) {
  // Only when a response is asked for: a test that set its own rejection on
  // `getProjection` must keep it.
  if (response) {
    vi.mocked(tosApi.getProjection).mockImplementation(async () => ({
      requestedAt: performance.now(),
      response: {
        available: true,
        reason: null,
        age_seconds: 0,
        projection: fixture,
        ...response,
      },
    }));
  }
  vi.mocked(tosBarsApi.listSessions).mockResolvedValue({
    available: true,
    reason: null,
    truncated: false,
    sessions: [
      entry({ session: 'long-20261125', kind: 'futures', direction: 'LONG' }),
      entry({ session: 'stock-r1-20261125', kind: 'stock', run: 1 }),
    ],
  });
  vi.mocked(tosBarsApi.getBars).mockImplementation(async (session: string) => {
    const resolved = session === 'latest' ? 'long-20261125' : session;
    const document = resolved.startsWith('long') ? futuresBarsDocument() : stockBarsDocument();
    return { available: true, reason: null, age_seconds: 12, session: resolved, document };
  });
  vi.mocked(tosSymbolsApi.getSymbolsToday).mockResolvedValue({
    available: true,
    reason: null,
    age_seconds: 30,
    document: symbolsDocument(),
  });
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(
    <QueryClientProvider client={client}>
      <TosPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date('2026-11-25T06:00:00Z')); // 15:00 KST
});
afterEach(() => {
  client?.clear();
  vi.useRealTimers();
  shared.accept = null;
});

describe('TOS 운영 페이지', () => {
  it('asks its four questions in order, each with a plain-Korean subtitle', async () => {
    mount({});
    await screen.findByText('최근 상태 도착');
    const sections = screen
      .getAllByRole('region')
      .map((region) => region.getAttribute('aria-label'));
    expect(sections.slice(0, 5)).toEqual([
      '지금 상태',
      'tenant 현황',
      '판단 근거',
      '거래 현황',
      '사건 기록',
    ]);
    expect(screen.getByText(/왜 진입했나 \/ 안 했나/)).toBeInTheDocument();
    expect(screen.getByText(/무엇을 사고팔았나/)).toBeInTheDocument();
    expect(screen.getByText(/무슨 일이 있었나/)).toBeInTheDocument();
  });

  it('puts the machinery last and collapsed, labelled as the paper cell', async () => {
    mount({});
    await screen.findByText('최근 상태 도착');
    const details = document.querySelector('details') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details).toHaveTextContent('paper 셀 상태와 기록 검증');
    // The five fact cards are still there, whole — just no longer the page.
    expect(within(details).getByText('릴리스 상태')).toBeInTheDocument();
  });

  it('opens on the newest session and lets a tenant card change it', async () => {
    mount({});
    await screen.findByText('최근 상태 도착');
    await waitFor(() => expect(tosBarsApi.getBars).toHaveBeenCalledWith('latest'));
    // The resolved id is what marks a card, so `latest` does not leave every
    // card unselected while the panel below renders one of them.
    await waitFor(() => expect(screen.getByText('선물 LONG')).toBeInTheDocument());
    await userEvent.click(screen.getAllByRole('radio', { name: /주식 005930/ })[0]);
    await waitFor(() => expect(tosBarsApi.getBars).toHaveBeenCalledWith('stock-r1-20261125'));
  });

  it('offers exactly one command-shaped control, and it only re-reads', async () => {
    mount({});
    await screen.findByText('최근 상태 도착');
    // 조회 belongs to the session fallback box and is absent while the listing
    // fills the dropdown. Everything else selects rather than acts.
    expect(screen.getAllByRole('button').map((b) => b.textContent?.trim())).toEqual(['새로고침']);
  });

  it('renders producer fixture values, preserving false and zero', async () => {
    mount({});
    await screen.findByText('최근 상태 도착');
    const internals = document.querySelector('details') as HTMLElement;
    expect(within(internals).getByRole('region', { name: '위험 원장과 증거' })).toHaveTextContent('0');
    expect(within(internals).getByRole('region', { name: '릴리스 상태' })).toHaveTextContent('거부');
  });

  it('renders whole null groups as unknown, including alert counts', async () => {
    mount({ projection: unknown });
    await screen.findByText('최근 상태 도착');
    const internals = document.querySelector('details') as HTMLElement;
    expect(within(internals).getAllByText('알 수 없음').length).toBeGreaterThan(10);
    expect(
      within(within(internals).getByRole('region', { name: '백업과 알림' })).queryByText('없음'),
    ).not.toBeInTheDocument();
  });

  it.each([
    ['projection file absent', '아직 상태 파일이 없습니다'],
    ['invalid json: /private/secret-path', '상태 데이터 형식 오류'],
    ['cannot read projection: PermissionError', '상태 파일을 열지 못했습니다'],
    ['unsupported schema_version 2', '지원하지 않는 상태 버전'],
  ])('shows %s without leaking the backend reason/path', async (reason, label) => {
    mount({ available: false, reason, projection: null });
    expect(await screen.findByText(label)).toBeInTheDocument();
    expect(screen.queryByText(/private/)).not.toBeInTheDocument();
    expect(screen.queryByRole('region', { name: '릴리스 상태' })).not.toBeInTheDocument();
  });

  it('does not raise a full-width alert over a merely stale paper cell', async () => {
    // The paper cell stops writing when it stops at 15:45, so an amber banner
    // above everything would dominate the page every evening while the tenant
    // sections below it are current. The fact belongs to the paper cell, and
    // the status strip is where the page says it.
    mount({ age_seconds: config.staleAfterSeconds + 120 });
    await screen.findByText(`${config.staleAfterSeconds}초 넘게 새 상태 없음`);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('still raises one for a request that did not land', async () => {
    const error = new AxiosError('Unauthorized');
    error.response = { status: 401 } as AxiosError['response'];
    vi.mocked(tosApi.getProjection).mockRejectedValue(error);
    mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('조회 인증을 확인해 주세요');
  });

  it('reports authentication failure without treating it as missing data', async () => {
    const error = new AxiosError('Unauthorized');
    error.response = { status: 401 } as AxiosError['response'];
    vi.mocked(tosApi.getProjection).mockRejectedValue(error);
    mount();
    expect(await screen.findByText('조회 인증을 확인해 주세요')).toBeInTheDocument();
  });

  it('marks retained data as a connection error after a failed refetch', async () => {
    mount({});
    await screen.findByText('최근 상태 도착');
    vi.mocked(tosApi.getProjection).mockRejectedValue(new Error('offline'));
    await act(() => client.refetchQueries({ queryKey: ['tos-operator-projection'] }));
    // A request that did not land IS worth the full-width alert, unlike a
    // stale document; the strip repeats it against the paper cell it belongs to.
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('상태 조회 연결 오류'));
  });

  it('shows an absent reason list as unknown, never as none', async () => {
    mount({ projection: { ...fixture, recovery: { readiness_verdict: 'READY', reasons: null } } });
    await screen.findByText('최근 상태 도착');
    const card = within(await screen.findByRole('region', { name: '복구와 실행 상태' }));
    expect(card.getByText('알 수 없음')).toBeInTheDocument();
    expect(card.queryByText('없음')).not.toBeInTheDocument();
  });

  it('still shows an empty reason list as none', async () => {
    mount({ projection: { ...fixture, recovery: { readiness_verdict: 'READY', reasons: [] } } });
    await screen.findByText('최근 상태 도착');
    const card = within(await screen.findByRole('region', { name: '복구와 실행 상태' }));
    expect(card.getByText('없음')).toBeInTheDocument();
  });

  it.each([
    ['accepted document', (p: TosProjection) => p],
    ['future schema version', (p: TosProjection) => ({ ...p, schema_version: 2 })],
    ['authorizing document', (p: TosProjection) => ({ ...p, non_authorizing: false })],
  ])('renders fact cards exactly when the shared predicate accepts: %s', async (_name, mutate) => {
    const projection = mutate(fixture);
    mount({ projection });
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: '릴리스 상태' }) !== null).toBe(
        isAcceptedProjection(projection),
      ),
    );
  });

  it.each([
    ['refuses the document', false, false],
    ['accepts the document', true, true],
  ])('defers to the shared acceptance predicate when it %s', async (_name, accept, rendered) => {
    // Divergence proof: the fixture is a valid v1 document either way, so only a
    // page that actually calls the shared export follows this override.
    shared.accept = () => accept;
    mount({});
    await screen.findByText('최근 상태 도착');
    expect(screen.queryByRole('region', { name: '릴리스 상태' }) !== null).toBe(rendered);
  });

  it('ages into stale while the next request is still pending', async () => {
    mount({ age_seconds: config.staleAfterSeconds - 1 });
    await screen.findByText('최근 상태 도착');
    // A real timer tick, with monotonic elapsed controlled independently of network polling.
    const started = performance.now();
    vi.spyOn(performance, 'now').mockReturnValue(started + 2000);
    vi.mocked(tosApi.getProjection).mockImplementation(() => new Promise(() => {}));
    await waitFor(
      () => expect(screen.getByText(`${config.staleAfterSeconds}초 넘게 새 상태 없음`)).toBeInTheDocument(),
      { timeout: config.clockTickMs * 3 },
    );
    vi.restoreAllMocks();
  });
});
