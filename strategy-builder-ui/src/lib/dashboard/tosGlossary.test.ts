import { describe, expect, it } from 'vitest';
import { GLOSSARY, glossaryKey, glossaryLabel, glossaryTerm, haltPairLabel } from './tosGlossary';
import { parseCompare } from './tosDecision';
import { futuresBarsDocument, stockBarsDocument } from '@/test/tosBarsFixture';

const documents = [futuresBarsDocument(), stockBarsDocument()];

/** Every raw string the two fixtures would put on screen as a term. */
function jargon(): string[] {
  const names = new Set<string>();
  for (const document of documents) {
    for (const bar of document.bars ?? []) {
      if (bar.decision_rule_id) names.add(bar.decision_rule_id);
      if (bar.decision_kind) names.add(bar.decision_kind);
      if (bar.evidence?.halt_reason) names.add(bar.evidence.halt_reason);
      if (bar.evidence?.halt_step) names.add(bar.evidence.halt_step);
      if (bar.evidence?.withheld_reason) names.add(bar.evidence.withheld_reason);
      if (bar.evidence?.outcome_type) names.add(bar.evidence.outcome_type);
      for (const rule of bar.rules ?? []) {
        if (rule.rule_id) names.add(rule.rule_id);
        for (const compare of rule.compares ?? []) {
          const parsed = parseCompare(compare.expression);
          if (parsed) {
            names.add(parsed.left);
            if (parsed.right.startsWith('config.')) names.add(parsed.right);
          }
        }
      }
    }
    if (document.default?.rule_id) names.add(document.default.rule_id);
  }
  return [...names];
}

describe('the glossary', () => {
  it('explains every term the fixtures put on screen', () => {
    // This is the whole point of the page change: a rule id, a gate code or a
    // published field that reaches an operator without a plain-Korean name is
    // the defect being fixed, so a new one has to be added here to land.
    const missing = jargon().filter((name) => glossaryTerm(name) === null);
    expect(missing).toEqual([]);
  });

  it('resolves a scaled alias through its bare name', () => {
    expect(glossaryKey('close_x100')).toBe('close');
    expect(glossaryKey('z_x1000')).toBe('z');
    expect(glossaryKey('entry_window')).toBe('entry_window');
    expect(glossaryTerm('close_x100')).toBe(glossaryTerm('close'));
  });

  it('shows a term this page has never seen as itself, rather than hiding it', () => {
    // A tenant may publish a field no release of this page knows about.
    expect(glossaryTerm('a_brand_new_field')).toBeNull();
    expect(glossaryLabel('a_brand_new_field')).toBe('a_brand_new_field');
    expect(glossaryLabel(null)).toBe('알 수 없음');
  });

  it('words a REASON@STEP pair as the stage first, then what it did', () => {
    expect(haltPairLabel('STAGE_DENIED', 'VENUE_ADMISSIBILITY_DECISION')).toBe(
      '거래소 수용 판정 — 단계에서 거절',
    );
    expect(haltPairLabel('TIME_NOT_ADMITTED', null)).toBe('시간 미인정');
  });

  it('keeps every meaning a sentence, not a label repeated', () => {
    for (const [key, term] of Object.entries(GLOSSARY)) {
      expect(term.label, key).not.toBe('');
      expect(term.meaning.length, key).toBeGreaterThan(term.label.length);
    }
  });
});
