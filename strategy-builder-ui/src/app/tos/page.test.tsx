import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor, within } from '@testing-library/react';
import { AxiosError } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import TosPage from './page';
import { tosApi, type TosProjectionResponse } from '@/lib/dashboard/tos';
import { tosFixture } from '@/test/tosFixture';
const fixture = tosFixture();
const unknown = tosFixture(true);
import config from '@/config/tos-control-plane.json';

vi.mock('@/lib/dashboard/tos', async () => {
  const actual = await vi.importActual<typeof import('@/lib/dashboard/tos')>('@/lib/dashboard/tos');
  return { ...actual, tosApi: { getProjection: vi.fn() } };
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
afterEach(() => { client?.clear(); vi.useRealTimers(); });

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
