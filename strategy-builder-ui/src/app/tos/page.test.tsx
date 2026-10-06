import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TosPage from './page';
import { isAcceptedProjection, tosApi, type TosProjection, type TosProjectionResponse } from '@/lib/dashboard/tos';
import { tosFixture } from '@/test/tosFixture';
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
let client: QueryClient;
function mount(response?: Partial<TosProjectionResponse>) {
  if (response) vi.mocked(tosApi.getProjection).mockImplementation(async () => ({
    requestedAt: performance.now(), response: { available: true, reason: null, age_seconds: 0, projection: fixture, ...response },
  }));
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  render(<QueryClientProvider client={client}><TosPage /></QueryClientProvider>);
}
beforeEach(() => vi.resetAllMocks());
afterEach(() => { client?.clear(); vi.useRealTimers(); shared.accept = null; });

describe('TOS read-only page', () => {
  it('renders producer fixture, preserves false/zero, and has no command buttons', async () => {
    mount({});
    await screen.findByText('최근 상태를 조회했습니다');
    expect(within(screen.getByRole('region', { name: '위험 원장과 증거' })).getByText('0')).toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: '릴리스와 보호 상태' })).getByText('거부')).toBeInTheDocument();
    expect(screen.getAllByRole('button').map(b => b.textContent)).toEqual(['새로고침']);
  });
  it('renders whole null groups as unknown, including alert counts', async () => {
    mount({ projection: unknown });
    await screen.findByText('최근 상태를 조회했습니다');
    expect(screen.getAllByText('알 수 없음').length).toBeGreaterThan(10);
    expect(within(screen.getByRole('region', { name: '백업과 알림' })).queryByText('없음')).not.toBeInTheDocument();
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
    expect(screen.queryByRole('region', { name: '릴리스와 보호 상태' })).not.toBeInTheDocument();
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
    await screen.findByText('최근 상태를 조회했습니다');
    vi.mocked(tosApi.getProjection).mockRejectedValue(new Error('offline'));
    await act(() => client.refetchQueries({ queryKey: ['tos-operator-projection'] }));
    expect(await screen.findByText('상태 조회 연결 오류')).toBeInTheDocument();
    expect(screen.getByText(/마지막 조회 기록/)).toBeInTheDocument();
  });
  it('renders the protective verdict object as facts, never [object Object]', async () => {
    mount({});
    const card = within(await screen.findByRole('region', { name: '릴리스와 보호 상태' }));
    // Fixture verdict: derestriction false, capacity null, classification null,
    // reasons ['derestriction_admissible'], unevaluated ['capacity_exhausted'].
    expect(card.getByText('불허')).toBeInTheDocument();
    expect(card.getByText('derestriction_admissible')).toBeInTheDocument();
    expect(card.getByText('capacity_exhausted')).toBeInTheDocument();
    expect(card.queryByText(/\[object Object\]/)).not.toBeInTheDocument();
  });
  it.each([
    [null, '해소 · 알 수 없음'],
    [[], '해소 · 없음'],
    [['stale snapshot'], '해소 · stale snapshot'],
  ] as const)('renders a safety-mesh reason list of %s distinctly', async (reasons, expected) => {
    // 지적 4: the old `reasons?.length ? … : ''` rendered null and [] the same.
    // '없음' is a substring of '알 수 없음', so compare the whole cell text.
    mount({ projection: { ...fixture, safety_mesh: {
      snapshot_generation: null, services: { spg: { clear: true, reasons } },
    } } });
    const card = within(await screen.findByRole('region', { name: '안전 서비스' }));
    const cell = card.getByText(/해소/);
    expect(cell.textContent?.replace(/\s+/g, ' ').trim()).toBe(expected);
  });
  it('shows an absent reason list as unknown, never as none', async () => {
    mount({ projection: { ...fixture, recovery: { readiness_verdict: 'READY', reasons: null } } });
    const card = within(await screen.findByRole('region', { name: '복구와 실행 상태' }));
    expect(card.getByText('알 수 없음')).toBeInTheDocument();
    expect(card.queryByText('없음')).not.toBeInTheDocument();
  });
  it('still shows an empty reason list as none', async () => {
    mount({ projection: { ...fixture, recovery: { readiness_verdict: 'READY', reasons: [] } } });
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
    await screen.findByRole('status').catch(() => screen.findByRole('alert'));
    await waitFor(() =>
      expect(screen.queryByRole('region', { name: '릴리스와 보호 상태' }) !== null)
        .toBe(isAcceptedProjection(projection)));
  });
  it.each([
    ['refuses the document', false, false],
    ['accepts the document', true, true],
  ])('defers to the shared acceptance predicate when it %s', async (_name, accept, rendered) => {
    // Divergence proof: the fixture is a valid v1 document either way, so only a
    // page that actually calls the shared export follows this override.
    shared.accept = () => accept;
    mount({});
    await screen.findByText('최근 상태를 조회했습니다');
    expect(screen.queryByRole('region', { name: '릴리스와 보호 상태' }) !== null).toBe(rendered);
  });
  it('ages into stale while the next request is still pending', async () => {
    mount({ age_seconds: config.staleAfterSeconds - 1 });
    await screen.findByText('최근 상태를 조회했습니다');
    // A real timer tick, with monotonic elapsed controlled independently of network polling.
    const started = performance.now();
    vi.spyOn(performance, 'now').mockReturnValue(started + 2000);
    vi.mocked(tosApi.getProjection).mockImplementation(() => new Promise(() => {}));
    await waitFor(() => expect(screen.getByText('오래된 상태')).toBeInTheDocument(), { timeout: config.clockTickMs * 3 });
    vi.restoreAllMocks();
  });
});
