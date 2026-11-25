import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import EventLog, { eventRuns } from './EventLog';
import type { TosBarsBar } from '@/lib/dashboard/tosBars';
import {
  INADMISSIBLE_DETAIL,
  NO_APPROVAL_DETAIL,
  ZERO_POSITION_DETAIL,
  futuresBarsDocument,
  stockBarsDocument,
} from '@/test/tosBarsFixture';

const futures = futuresBarsDocument();
const stock = stockBarsDocument();

function mount(document = futures) {
  render(<EventLog bars={(document.bars ?? []) as TosBarsBar[]} summary={document.summary} />);
}

function log(): HTMLElement {
  return screen.getByRole('region', { name: '사건 기록' });
}

describe('사건 기록', () => {
  it('pairs every raw code with a plain-Korean name, never one without the other', () => {
    mount();
    const first = within(log()).getAllByRole('listitem')[0];
    expect(first).toHaveTextContent('시간 미인정');
    expect(first).toHaveTextContent('TIME_NOT_ADMITTED');
  });

  it('names the stage a denial fired at, beside the denial itself', () => {
    mount();
    const rows = within(log()).getAllByRole('listitem');
    const denial = rows.find((row) => row.textContent?.includes('주문서 작성')) as HTMLElement;
    expect(denial).toHaveTextContent('단계에서 거절');
    expect(denial).toHaveTextContent('STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION');
  });

  it('shows the evidence’s own sentence rather than paraphrasing it', () => {
    mount();
    // Two runs carry the zero-position denial — the VWAP exit and the EOD one.
    expect(within(log()).getAllByText(ZERO_POSITION_DETAIL)).toHaveLength(2);
    expect(within(log()).getByText(NO_APPROVAL_DETAIL)).toBeInTheDocument();
    mount(stock);
    expect(screen.getAllByText(INADMISSIBLE_DETAIL).length).toBeGreaterThan(0);
  });

  it('counts the bars of each stop, and the withheld and substituted ones', () => {
    mount();
    const counts = within(log()).getByText('기록된 사건 4봉').closest('p') as HTMLElement;
    expect(counts).toHaveTextContent('보류 1봉');
    expect(counts).toHaveTextContent('기록으로 대체 1봉');
  });

  it('collapses a run of the same code into one row with its time span', () => {
    const bar = (futures.bars as TosBarsBar[])[2];
    const runs = eventRuns([
      bar,
      { ...bar, time_kst: '08:49' },
      { ...bar, time_kst: '08:50' },
    ]);
    expect(runs).toHaveLength(1);
    expect(runs[0]).toMatchObject({ count: 3, firstTime: '08:48', lastTime: '08:50' });
  });

  it('never logs a quiet bar as an event', () => {
    // NO_ACTION_OUTCOME is the record that there was nothing to send; logging
    // it would make every ordinary bar of the day an incident.
    const quiet = (futures.bars as TosBarsBar[])[1];
    expect(eventRuns([quiet])).toEqual([]);
  });

  it('says so plainly when nothing stopped', () => {
    const quiet = (futures.bars as TosBarsBar[])[1];
    render(<EventLog bars={[quiet]} summary={{ withheld_bars: 0, substituted_bars: 0 }} />);
    expect(screen.getByText('판단을 멈추거나 주문을 막은 기록이 없습니다.')).toBeInTheDocument();
  });

  it('says 알 수 없음 rather than zero when a count is absent', () => {
    render(<EventLog bars={[]} summary={{}} />);
    expect(screen.getAllByText(/알 수 없음/).length).toBeGreaterThan(0);
  });
});
