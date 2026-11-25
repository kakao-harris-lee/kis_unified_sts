import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import VerdictTimeline from './VerdictTimeline';
import config from '@/config/tos-control-plane.json';
import type { TosBarsBar } from '@/lib/dashboard/tosBars';
import { futuresBarsDocument, quietThenTradeDocument } from '@/test/tosBarsFixture';

function mount(bars: TosBarsBar[], selectedIndex = 0) {
  const onSelect = vi.fn();
  render(<VerdictTimeline bars={bars} selectedIndex={selectedIndex} onSelect={onSelect} />);
  return onSelect;
}

/** Every row currently in the DOM, open disclosure included. */
function allRows(): string[] {
  return screen.getAllByRole('listitem').map((row) => row.textContent ?? '');
}

const longDay = quietThenTradeDocument().bars as TosBarsBar[];

describe('판단 타임라인', () => {
  it('renders a trade that falls far past any row cap', async () => {
    // The regression: 42 quiet changes, then the day's only entry and exit.
    // A flat 40-row cap dropped both — 거래 현황 showed the fill and this panel
    // refused to show the decision behind it, even under «더 보기».
    mount(longDay);
    await userEvent.click(screen.getByText(/줄 더 보기/));
    const rows = allRows();
    expect(rows.some((row) => row.includes('11:18') && row.includes('진입'))).toBe(true);
    expect(rows.some((row) => row.includes('11:26') && row.includes('청산'))).toBe(true);
  });

  it('counts the whole session on one line, for every tenant', () => {
    mount(longDay);
    const summary = screen.getByText(/진입 신호/).closest('p') as HTMLElement;
    expect(summary).toHaveTextContent('진입 신호 1봉 (게이트 통과 1)');
    expect(summary).toHaveTextContent('청산 신호 1봉 (게이트 통과 1)');
    expect(summary).toHaveTextContent('신호 없음 42구간');
  });

  it('lists every entry and exit with no cap at all when filtered', async () => {
    mount(longDay);
    await userEvent.click(screen.getByRole('checkbox', { name: /진입 · 청산만 보기/ }));
    const rows = allRows();
    expect(rows).toHaveLength(2);
    expect(rows[0]).toContain('11:18');
    expect(rows[1]).toContain('11:26');
    // And no «더 보기» hiding anything, because nothing is hidden.
    expect(screen.queryByText(/줄 더 보기/)).not.toBeInTheDocument();
  });

  it('trims only the quiet background, and says how much of which kind', async () => {
    // One more quiet change than the cap allows.
    const bars = quietThenTradeDocument(config.timelineQuietMaxRows + 3).bars as TosBarsBar[];
    mount(bars);
    expect(screen.getByText(/신호 없음 3구간은 접었습니다/)).toBeInTheDocument();
    expect(screen.getByText(/진입 · 청산 · 시험 진입은 모두 위에 있습니다/)).toBeInTheDocument();
    await userEvent.click(screen.getByText(/줄 더 보기/));
    const rows = allRows();
    // The trades survived the trim; only quiet rows went.
    expect(rows.some((row) => row.includes('11:18'))).toBe(true);
    expect(rows.some((row) => row.includes('11:26'))).toBe(true);
  });

  it('says nothing about trimming when nothing was trimmed', () => {
    mount(futuresBarsDocument().bars as TosBarsBar[]);
    expect(screen.queryByText(/접었습니다/)).not.toBeInTheDocument();
  });

  it('moves the selection without offering a command', async () => {
    const onSelect = mount(longDay);
    await userEvent.click(screen.getByRole('checkbox', { name: /진입 · 청산만 보기/ }));
    await userEvent.click(within(screen.getAllByRole('listitem')[0]).getByRole('radio'));
    expect(onSelect).toHaveBeenCalledWith(42);
    expect(screen.queryAllByRole('button')).toEqual([]);
  });

  it('says so plainly when the session produced no changes at all', () => {
    mount([]);
    expect(screen.getByText('판단 기록이 없습니다.')).toBeInTheDocument();
  });
});
