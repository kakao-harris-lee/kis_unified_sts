import { describe, expect, it } from 'vitest';
import {
  PNL_CLASSES,
  PNL_WORDS,
  countLabel,
  krwLabel,
  pnlFigure,
  pointsLabel,
  quantityLabel,
} from './tosMoney';

describe('손익 표기', () => {
  it('prints the sign even on a gain, so the hue is never the only carrier', () => {
    expect(pnlFigure('1000')?.signed).toBe('+1,000');
    expect(pnlFigure('-19000')?.signed).toBe('-19,000');
    expect(krwLabel('-19000')).toBe('-19,000원');
    expect(krwLabel('1000')).toBe('+1,000원');
  });

  it('keeps the Korean convention: a gain is red, a loss is blue', () => {
    expect(pnlFigure('1')?.direction).toBe('profit');
    expect(pnlFigure('-1')?.direction).toBe('loss');
    expect(PNL_CLASSES.profit).toContain('profit');
    expect(PNL_CLASSES.loss).toContain('loss');
    expect(PNL_WORDS.profit).toBe('이익');
    expect(PNL_WORDS.loss).toBe('손실');
  });

  it('treats an asserted zero as a figure, and absence as unknown', () => {
    // A document that says 0 traded and broke even; a document that says
    // nothing has not made that claim.
    expect(pnlFigure('0')?.direction).toBe('flat');
    expect(krwLabel('0')).toBe('0원');
    expect(pnlFigure(null)).toBeNull();
    expect(krwLabel(null)).toBe('알 수 없음');
    expect(krwLabel(undefined)).toBe('알 수 없음');
    expect(krwLabel('')).toBe('알 수 없음');
  });

  it('refuses text it cannot read rather than rendering NaN', () => {
    expect(pnlFigure('없음')).toBeNull();
    expect(krwLabel('없음')).toBe('알 수 없음');
  });

  it('keeps index points out of the won namespace', () => {
    expect(pointsLabel('2.94')).toBe('+2.94 pt');
    expect(pointsLabel('-1.5')).toBe('-1.5 pt');
    expect(pointsLabel(null)).toBe('알 수 없음');
  });

  it('counts: zero is a count, absent is not', () => {
    expect(countLabel(0)).toBe('0회');
    expect(countLabel(2)).toBe('2회');
    expect(countLabel(2, '')).toBe('2');
    expect(countLabel(null)).toBe('알 수 없음');
  });

  it('groups a quantity and passes unreadable text through', () => {
    expect(quantityLabel('1', '주')).toBe('1주');
    expect(quantityLabel('1000', '주')).toBe('1,000주');
    expect(quantityLabel(null, '주')).toBe('알 수 없음');
  });
});
