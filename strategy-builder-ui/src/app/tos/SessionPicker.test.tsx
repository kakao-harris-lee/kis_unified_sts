import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import SessionPicker from './SessionPicker';
import type { SessionsRead } from './queries';
import type { TosSessionEntry } from '@/lib/dashboard/tosBars';

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

function read(overrides: Partial<SessionsRead> = {}): SessionsRead {
  return {
    response: undefined,
    sessions: sessionList(),
    truncated: false,
    failed: false,
    ...overrides,
  };
}

function mount(overrides: Partial<SessionsRead> = {}, value = 'latest') {
  const onChange = vi.fn();
  render(<SessionPicker sessions={read(overrides)} value={value} onChange={onChange} />);
  return onChange;
}

/** The listing unavailable — the picker must still reach a session. */
const NO_LISTING: Partial<SessionsRead> = { sessions: [], failed: true };

describe('세션 선택', () => {
  it('offers the exported sessions grouped by day, newest first', () => {
    mount();
    const picker = screen.getByLabelText('세션');
    expect(picker.tagName).toBe('SELECT');
    // The sentinel stays the first option: the page opens on it, and it is
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

  it('keeps the raw session id on the option the label stands for', () => {
    mount();
    expect(screen.getByRole('option', { name: '11-25 · 주식 000660' })).toHaveAttribute(
      'title',
      'stock-000660-r1-20261125',
    );
  });

  it('reports the session the operator picked', async () => {
    const onChange = mount();
    await userEvent.selectOptions(screen.getByLabelText('세션'), 'long-20261125');
    expect(onChange).toHaveBeenCalledWith('long-20261125');
  });

  it('says when the listing is only the newest part of the directory', () => {
    mount({ truncated: true });
    expect(screen.getByText(/최근 5개 세션만 목록에 있습니다/)).toBeInTheDocument();
  });

  it('keeps a session past the cap reachable by name', async () => {
    // The cap keeps the NEWEST sessions, so an older one is still in the
    // directory and still readable — the dropdown alone would make it
    // unreachable from the UI, which is the one thing the cap must not do.
    const onChange = mount({ truncated: true });
    expect(screen.getByLabelText('세션').tagName).toBe('SELECT');
    const box = screen.getByLabelText('직접 입력');
    expect(box.tagName).toBe('INPUT');
    await userEvent.type(box, 'stock-r1-20260901');
    await userEvent.click(screen.getByRole('button', { name: '조회' }));
    expect(onChange).toHaveBeenCalledWith('stock-r1-20260901');
  });

  it('offers no second box while the whole directory fits in the picker', () => {
    mount();
    expect(screen.queryByLabelText('직접 입력')).not.toBeInTheDocument();
  });

  it('keeps a session the listing does not carry selectable', () => {
    // The operator typed it while the listing was down, and the listing then
    // arrived without it. A blank select over a rendered session is worse than
    // an option that names the id.
    mount({}, 'long-20261001');
    const picker = screen.getByLabelText('세션');
    expect(picker).toHaveValue('long-20261001');
    expect(within(picker).getByRole('option', { name: 'long-20261001' })).toBeInTheDocument();
  });

  it('falls back to the text box when the listing is unavailable', async () => {
    const onChange = mount(NO_LISTING);
    const box = screen.getByLabelText('세션');
    expect(box.tagName).toBe('INPUT');
    await userEvent.type(box, 'long-20261110');
    await userEvent.click(screen.getByRole('button', { name: '조회' }));
    expect(onChange).toHaveBeenCalledWith('long-20261110');
  });

  it('falls back to latest when the operator submits an empty box', async () => {
    const onChange = mount(NO_LISTING);
    await userEvent.click(screen.getByRole('button', { name: '조회' }));
    expect(onChange).toHaveBeenCalledWith('latest');
  });

  it('offers no button at all while the dropdown covers the directory', () => {
    // Picking applies on change, so the picker needs none; the 조회 button
    // exists only to submit the fallback box.
    mount();
    expect(screen.queryAllByRole('button')).toEqual([]);
  });
});
