import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import Term from './Term';
import { GLOSSARY } from '@/lib/dashboard/tosGlossary';

describe('용어 풀이', () => {
  it('shows the plain-Korean name in place of the raw code', () => {
    render(<Term name="STAGE_DENIED" />);
    expect(screen.getByText('단계에서 거절')).toBeInTheDocument();
  });

  it('carries its explanation even while closed, so nothing is ever unexplained', () => {
    render(<Term name="hi_vol" />);
    expect(screen.getByText('변동성 충분')).toHaveAttribute('title', GLOSSARY.hi_vol.meaning);
  });

  it('is focusable and describes itself once focused', async () => {
    render(<Term name="hi_vol" />);
    const term = screen.getByText('변동성 충분');
    expect(term).toHaveAttribute('tabindex', '0');
    await userEvent.tab();
    expect(term).toHaveFocus();
    // aria-describedby takes precedence over title, and points at the popup.
    const described = term.getAttribute('aria-describedby');
    expect(described).toBeTruthy();
    expect(screen.getByRole('tooltip')).toHaveAttribute('id', described as string);
  });

  it('opens and closes on tap, for a device with no hover', () => {
    render(<Term name="hi_vol" />);
    const term = screen.getByText('변동성 충분');
    // A tap fires pointerenter first. If that opened the popup, the click
    // behind it would immediately close it again and touch would never work.
    // jsdom implements no PointerEvent, so `pointerType` has to be set on the
    // event object by hand — fireEvent's init would otherwise be dropped and
    // the enter would read as a mouse.
    const tap = () => {
      const enter = new Event('pointerenter', { bubbles: false });
      Object.defineProperty(enter, 'pointerType', { value: 'touch' });
      fireEvent(term, enter);
      fireEvent.click(term);
    };
    tap();
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    tap();
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('opens on hover for a pointer that can leave again', async () => {
    render(<Term name="hi_vol" />);
    const term = screen.getByText('변동성 충분');
    await userEvent.hover(term);
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    await userEvent.unhover(term);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('closes on Escape while keeping focus on the term', async () => {
    render(<Term name="hi_vol" />);
    await userEvent.tab();
    expect(screen.getByRole('tooltip')).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
    expect(screen.getByText('변동성 충분')).toHaveFocus();
  });

  it('keeps its sentence out of the surrounding text while closed', () => {
    // An always-rendered description would put a paragraph inside every table
    // cell on the page — and inside every text assertion over one.
    render(
      <p data-testid="row">
        마지막 차단 사유: <Term name="STAGE_DENIED" /> · 15:18
      </p>,
    );
    expect(screen.getByTestId('row')).toHaveTextContent('마지막 차단 사유: 단계에서 거절 · 15:18');
  });

  it('is not a button — this page commands nothing', () => {
    render(<Term name="STAGE_DENIED" />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders a term it has never seen as plain text, rather than hiding it', () => {
    render(<Term name="SOME_FUTURE_CODE" />);
    const shown = screen.getByText('SOME_FUTURE_CODE');
    expect(shown).not.toHaveAttribute('tabindex');
    expect(shown).not.toHaveAttribute('title');
  });

  it('lets a caller keep its own wording over the glossary label', () => {
    render(<Term name="TOS_LEDGER_FIFO_OPEN_LOTS">보유 (TOS 기준)</Term>);
    expect(screen.getByText('보유 (TOS 기준)')).toBeInTheDocument();
  });
});
