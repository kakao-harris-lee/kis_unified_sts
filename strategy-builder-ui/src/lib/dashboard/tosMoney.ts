// Money and counts, worded once for the whole page.
//
// Two rules live here rather than in each component that prints a number.
//
// * **Absent is «알 수 없음», never 0.** A leaf the exporter could not read
//   sends null, and a tenant that cannot trade sends null. Both are facts about
//   knowledge, and a zero would turn either into the claim «it traded and came
//   out even» — the single way a PnL figure on this page could mislead.
// * **The sign and the word travel with the colour.** `--color-profit` is red
//   and `--color-loss` is blue (Korean convention), and that hue is never the
//   only carrier: every figure below renders its own `+`/`-` and the caller
//   prints the matching word. The page reads the same in greyscale.
//
// Nothing here rounds or re-derives: the exporter already decided the figure
// (`tools/tos_cp3/perf.py`), and this module only groups the digits.

/** Which way a figure went. `flat` is a real zero the document asserted. */
export type PnlDirection = 'profit' | 'loss' | 'flat';

/** The plain word that rides beside every figure, so the hue carries nothing alone. */
export const PNL_WORDS: Record<PnlDirection, string> = {
  profit: '이익',
  loss: '손실',
  flat: '변동 없음',
};

/** The token class for a direction — profit red, loss blue, flat inherits. */
export const PNL_CLASSES: Record<PnlDirection, string> = {
  profit: 'text-profit',
  loss: 'text-loss',
  flat: 'text-slate-600 dark:text-slate-300',
};

export interface PnlFigure {
  amount: number;
  direction: PnlDirection;
  /** Grouped digits with an explicit sign: `-19,000`, `+1,000`, `0`. */
  signed: string;
}

/** The page's one word for a value the document does not carry. */
export const UNKNOWN = '알 수 없음';

/**
 * A decimal string from the exporter as a signed, grouped figure.
 *
 * Null for null and for anything that is not a number — the caller then prints
 * «알 수 없음» rather than a zero. The exporter sends decimal STRINGS precisely
 * so a round trip through a float cannot move the last won, and this is the one
 * place that parses them.
 */
export function pnlFigure(value: string | number | null | undefined): PnlFigure | null {
  if (value == null || value === '') return null;
  const amount = Number(value);
  if (!Number.isFinite(amount)) return null;
  const direction: PnlDirection = amount > 0 ? 'profit' : amount < 0 ? 'loss' : 'flat';
  const grouped = Math.abs(amount).toLocaleString('ko-KR', { maximumFractionDigits: 2 });
  return {
    amount,
    direction,
    signed: amount > 0 ? `+${grouped}` : amount < 0 ? `-${grouped}` : grouped,
  };
}

/** `-19,000원`, or «알 수 없음». */
export function krwLabel(value: string | number | null | undefined): string {
  const figure = pnlFigure(value);
  return figure ? `${figure.signed}원` : UNKNOWN;
}

/** `+2.94 pt`, or «알 수 없음» — index points, which are not money. */
export function pointsLabel(value: string | number | null | undefined): string {
  const figure = pnlFigure(value);
  return figure ? `${figure.signed} pt` : UNKNOWN;
}

/** A count the document may simply not carry. Zero is a count; null is not. */
export function countLabel(value: number | null | undefined, unit = '회'): string {
  return value == null ? UNKNOWN : `${value.toLocaleString('ko-KR')}${unit}`;
}

/** A quantity string (shares, contracts) the document may not carry. */
export function quantityLabel(value: string | null | undefined, unit: string): string {
  if (value == null) return UNKNOWN;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${parsed.toLocaleString('ko-KR')}${unit}` : `${value}${unit}`;
}
