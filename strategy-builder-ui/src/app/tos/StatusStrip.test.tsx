import { render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import StatusStrip from './StatusStrip';
import type { SymbolsRead } from './queries';
import type { ProjectionState, TosProjection } from '@/lib/dashboard/tos';
import type { TosSymbolsDocument } from '@/lib/dashboard/tosSymbols';
import { symbolsDocument } from '@/test/tosBarsFixture';
import { tosFixture } from '@/test/tosFixture';

const projection = tosFixture();

function symbols(document: TosSymbolsDocument | null = symbolsDocument()): SymbolsRead {
  return {
    state: document ? 'ready' : 'missing',
    document,
    response: { available: true, reason: null, age_seconds: 42, document },
    authError: false,
  };
}

function mount(
  state: ProjectionState = 'recent',
  overrides: Partial<TosProjection> | null = {},
  symbolsRead: SymbolsRead = symbols(),
) {
  render(
    <StatusStrip
      projectionState={state}
      projection={overrides === null ? null : { ...projection, ...overrides }}
      projectionAgeSeconds={3}
      symbols={symbolsRead}
      stateLabel="아직 상태 파일이 없습니다"
    />,
  );
}

function strip(): HTMLElement {
  return screen.getByRole('region', { name: '지금 상태' });
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  vi.setSystemTime(new Date('2026-11-25T06:00:00Z')); // 15:00 KST
});

afterEach(() => vi.useRealTimers());

describe('상태 띠', () => {
  it('labels the runtime fact as the paper cell, never as «the system»', () => {
    mount();
    // The projection describes ONE resident paper cell and says nothing about
    // the tenant sessions below it. The old page showed it unlabelled.
    const fact = within(strip()).getByText('최근 상태 도착').closest('li') as HTMLElement;
    expect(fact).toHaveTextContent('paper 셀최근 상태 도착');
  });

  it('raises a latched halt above a merely stale read', () => {
    mount('recent', { driver: { wired: true, halt_latched: true, halt_reason: 'DRIVER_FAULT' } });
    expect(within(strip()).getByText('실행 중단 · DRIVER_FAULT')).toBeInTheDocument();
  });

  it('says the symbols document is stale when its date is not today', () => {
    const old = symbolsDocument();
    old.date = '2026-11-18';
    mount('recent', {}, symbols(old));
    expect(within(strip()).getByText('2026-11-18 · 오늘 아님')).toBeInTheDocument();
  });

  it('counts the tenant sessions by phase', () => {
    mount();
    expect(within(strip()).getByText('종목 tenant 1개')).toBeInTheDocument();
    expect(within(strip()).getByText('종료 1')).toBeInTheDocument();
  });

  it('counts gated decisions without colouring an ordinary day as an incident', () => {
    // Every tenant records STAGE_DENIED on exits it has no position to close.
    mount();
    const gates = within(strip()).getByText('게이트가 막은 판단').closest('li') as HTMLElement;
    expect(gates).toHaveTextContent('334건');
    expect(gates.querySelector('span')?.className).toContain('slate');
  });

  it('says 알 수 없음 rather than zero when the counts are absent', () => {
    const blank = symbolsDocument();
    blank.symbols![0].halt!.flow_counts = null;
    mount('recent', {}, symbols(blank));
    const gates = within(strip()).getByText('게이트가 막은 판단').closest('li') as HTMLElement;
    expect(gates).toHaveTextContent('알 수 없음');
  });

  it('drops the tenant facts entirely when there is no symbols document', () => {
    mount('recent', {}, symbols(null));
    expect(within(strip()).queryByText(/종목 tenant/)).not.toBeInTheDocument();
    expect(within(strip()).getByText('알 수 없음')).toBeInTheDocument();
  });

  it('states that it only summarises what the documents say', () => {
    mount();
    expect(within(strip()).getByText(/주문을 내리거나 멈출 수 있는 화면이 아닙니다/))
      .toBeInTheDocument();
  });
});
