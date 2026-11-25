import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import BarsPanel from './BarsPanel';
import type { BarsRead } from './queries';
import type { BarsState, TosBarsDocument } from '@/lib/dashboard/tosBars';
import {
  NO_APPROVAL_DETAIL,
  futuresBarsDocument,
  stockBarsDocument,
} from '@/test/tosBarsFixture';

function read(overrides: Partial<BarsRead> = {}): BarsRead {
  const document = futuresBarsDocument();
  return {
    state: 'ready' as BarsState,
    document,
    response: { available: true, reason: null, age_seconds: 12, session: 'long-20261125', document },
    authError: false,
    isFetching: false,
    ...overrides,
  };
}

function mount(overrides: Partial<BarsRead> = {}, requested = 'long-20261125') {
  return render(<BarsPanel requested={requested} read={read(overrides)} />);
}

function panel(): HTMLElement {
  return screen.getByRole('region', { name: '판단 근거' });
}

/** The timeline row whose text carries `time`. */
async function pick(time: string) {
  await userEvent.click(screen.getByRole('radio', { name: new RegExp(time) }));
}

describe('판단 근거 패널', () => {
  it('opens on the last bar the engine JUDGED, not the last bar in the file', () => {
    mount();
    // 15:45 is the final counted bar; a withheld tail would otherwise greet
    // the operator with a bar that has no conditions to show.
    const slider = screen.getByLabelText('봉 선택');
    expect(slider).toHaveValue('5');
    expect(slider).toHaveAttribute('aria-valuetext', '15:45 · 청산');
  });

  it('states the verdict for a quiet bar instead of leaving it blank', async () => {
    mount();
    await pick('08:46');
    expect(screen.getByText(/진입 조건 중 .* 이\(가\) 서지 않아 아무 것도 하지 않았습니다/))
      .toBeInTheDocument();
  });

  it('never reports an unevaluated bar as 신호 없음', async () => {
    mount();
    await pick('08:45');
    expect(screen.getByText(/조건이 거짓이었던 것이 아니라, 판단 자체를 하지 않았습니다/))
      .toBeInTheDocument();
  });

  it('shows the formula with every term marked by its truth on the bar', async () => {
    mount();
    await pick('08:46');
    const formula = screen.getByText('매수 진입 =').closest('p') as HTMLElement;
    // One blocking condition is meant to be visible without reading the table.
    expect(formula).toHaveTextContent('— 진입 시간대');
    expect(formula).toHaveTextContent('— VWAP 이탈 z ≤ -1.8');
    await pick('09:14');
    const met = screen.getByText('매수 진입 =').closest('p') as HTMLElement;
    expect(met).toHaveTextContent('✓ 진입 시간대');
    expect(met).toHaveTextContent('✓ VWAP 이탈 z ≤ -1.8');
  });

  it('prints each condition in human units with its distance to passing', async () => {
    mount();
    await pick('08:46');
    const row = screen.getByText('z_x1000 LE config.z_entry_max_x1000').closest('tr') as HTMLElement;
    expect(within(row).getByText('-0.45')).toBeInTheDocument();
    expect(within(row).getByText('≤ -1.8')).toBeInTheDocument();
    expect(within(row).getByText('미충족')).toBeInTheDocument();
    expect(within(row).getByText('1.35 더 내려가야 충족')).toBeInTheDocument();
  });

  it('keeps the kernel gates in their own block, apart from the conditions', async () => {
    mount();
    const gates = screen.getByText('커널 게이트').closest('div') as HTMLElement;
    expect(gates).toHaveTextContent('전략 조건과는 별개입니다');

    await pick('08:46');
    expect(screen.getByText('이 봉을 막은 게이트 없음')).toBeInTheDocument();

    await pick('09:14');
    // The signal stood and a stage refused it — never the same shape as 「신호 없음」.
    expect(screen.getByText(/규칙은 섰지만 커널 게이트에서 막혀/)).toBeInTheDocument();
    expect(screen.getAllByText('독립 승인 — 단계 결과 모름').length).toBeGreaterThan(0);
    expect(screen.getByText(NO_APPROVAL_DETAIL)).toBeInTheDocument();
  });

  it('ranks the conditions that blocked entry over the judged bars', () => {
    mount();
    const section = screen.getByText('오늘 진입을 막은 조건').closest('div') as HTMLElement;
    // Four of the five conditions were false on three of the four judged bars.
    expect(within(section).getAllByText(/75.0% · 3\/4봉 거짓/)).toHaveLength(4);
    const names = within(section)
      .getAllByRole('listitem')
      .map((item) => item.textContent?.slice(0, 6));
    expect(names[0]).toContain('진입 시간대');
    expect(names[names.length - 1]).toContain('변동성');
  });

  it('collapses the session into the moments the verdict changed', () => {
    mount();
    const timeline = screen.getByRole('radiogroup', { name: '판단이 바뀐 지점' });
    expect(within(timeline).getAllByRole('radio')).toHaveLength(6);
    expect(within(timeline).getByText(/신호 없음 — 미충족: 진입 시간대/)).toBeInTheDocument();
    // Both exits decided and were then stopped — R2 at 08:48, R3 at 15:45.
    expect(within(timeline).getAllByText(/청산 신호 — 게이트에서 차단/)).toHaveLength(2);
  });

  it('moves the checklist when the slider moves — the keyboard path to a bar', () => {
    mount();
    fireEvent.change(screen.getByLabelText('봉 선택'), { target: { value: '1' } });
    expect(screen.getByLabelText('봉 선택')).toHaveAttribute('aria-valuetext', '08:46 · 신호 없음');
    // And the checklist followed: 08:46 is the quiet bar, z at -0.45.
    const row = screen.getByText('z_x1000 LE config.z_entry_max_x1000').closest('tr') as HTMLElement;
    expect(within(row).getByText('-0.45')).toBeInTheDocument();
  });

  it('calls the M2 probe a probe rather than an entry signal', async () => {
    const document = stockBarsDocument();
    mount({
      document,
      response: {
        available: true,
        reason: null,
        age_seconds: 5,
        session: 'stock-r1-20261125',
        document,
      },
    });
    await pick('09:15');
    expect(screen.getAllByText('시험 진입').length).toBeGreaterThan(0);
    expect(screen.queryByText('진입 — 매수 진입')).not.toBeInTheDocument();
  });

  it('summarises the probe session in one line above the timeline', async () => {
    // A probe tenant alternates 시험 진입 and 게이트 차단 for hundreds of bars;
    // the line answers it before any row is read, and separates firings from
    // the orders that actually left.
    const document = stockBarsDocument();
    mount({
      document,
      response: {
        available: true,
        reason: null,
        age_seconds: 5,
        session: 'stock-r1-20261125',
        document,
      },
    });
    const summary = screen.getByText(/봉 중 게이트 통과/).closest('p') as HTMLElement;
    expect(summary).toHaveTextContent('2봉 중 게이트 통과 1');
    expect(summary).toHaveTextContent('독립 승인 — 단계 결과 모름 1');
  });

  it('names the window the document covers', () => {
    mount();
    expect(screen.getByText('구간: 08:45 – 15:45')).toBeInTheDocument();
  });

  it('distinguishes a tenant that binds nothing from a document with no bindings', () => {
    mount();
    expect(screen.getByText(/바인딩: z_entry_max_x1000=-1800/)).toBeInTheDocument();

    const none = { ...futuresBarsDocument(), bindings: { values: {} } };
    mount({ document: none });
    expect(screen.getByText('바인딩: 없음')).toBeInTheDocument();

    const unknown = { ...futuresBarsDocument(), bindings: null };
    mount({ document: unknown });
    expect(screen.getByText('바인딩: 알 수 없음')).toBeInTheDocument();
  });

  it('says the record is written once, at session end', () => {
    mount();
    expect(screen.getByText(/장중에는 직전 세션을 보고 있을 수 있습니다/)).toBeInTheDocument();
  });

  it.each([
    ['missing' as BarsState, '이 세션의 바 기록이 아직 없습니다', /sts tos export-bars/],
    ['unreadable' as BarsState, '바 기록 파일을 열지 못했습니다', /접근 권한/],
    ['bad-request' as BarsState, '세션 이름을 확인해 주세요', /예: stock-r1-20261110/],
  ])('reports %s as a normal state and renders no chart', (state, label, hint) => {
    mount({ state, document: null, response: { available: false, reason: null, age_seconds: null, session: null, document: null } });
    const banner = screen.getByRole('alert');
    expect(banner).toHaveTextContent(label);
    expect(banner).toHaveTextContent(hint);
    expect(screen.queryByRole('group', { name: '가격과 VWAP' })).not.toBeInTheDocument();
  });

  it('reports an auth failure as auth, not as missing data', () => {
    mount({ state: 'error', document: null, authError: true });
    expect(screen.getByRole('alert')).toHaveTextContent('조회 인증을 확인해 주세요');
  });

  it('never renders a document the acceptance predicate refused', () => {
    // Banner and body must agree: `document` is null exactly when the shared
    // predicate rejected the body, whatever the response carried.
    mount({ state: 'invalid', document: null });
    expect(screen.queryByLabelText('봉 선택')).not.toBeInTheDocument();
  });

  it('offers no command surface — it is a read model', () => {
    mount();
    // Selection controls only: a slider and the timeline radios. Nothing here
    // can start, stop or re-export anything.
    expect(within(panel()).queryAllByRole('button')).toEqual([]);
  });

  it('names the session that was resolved when it differs from the one asked for', () => {
    mount({}, 'latest');
    expect(screen.getByText(/요청한 세션: latest · 조회된 세션: long-20261125/)).toBeInTheDocument();
  });
});

describe('문서 없는 상태', () => {
  it('renders nothing below the banner when there is no document', () => {
    const empty: TosBarsDocument | null = null;
    mount({ state: 'missing', document: empty });
    expect(screen.queryByRole('radiogroup', { name: '판단이 바뀐 지점' })).not.toBeInTheDocument();
  });
});
