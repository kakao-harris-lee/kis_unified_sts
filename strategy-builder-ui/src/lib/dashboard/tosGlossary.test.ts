import { describe, expect, it } from 'vitest';
import {
  GLOSSARY,
  glossaryKey,
  glossaryLabel,
  glossaryTerm,
  haltExplanation,
  haltPairLabel,
} from './tosGlossary';
import { parseCompare } from './tosDecision';
import {
  futuresBarsDocument,
  rsiStockBarsDocument,
  stockBarsDocument,
  symbolsDocument,
} from '@/test/tosBarsFixture';

// All three tenant shapes, because they do NOT share a vocabulary: 005380
// publishes rsi/wr fields and its own rule ids, and a glossary that covered
// only Setup D would pass on four tenants and leave that one in raw English.
const documents = [futuresBarsDocument(), stockBarsDocument(), rsiStockBarsDocument()];

/** Every raw string the fixtures would put on screen as a term. */
function jargon(): string[] {
  const names = new Set<string>();
  // The P2 blocks put three more families of raw code on screen: the rule ids
  // and field names the explanation carries, the assumption codes beside the
  // hypothetical total, and the reason each skipped decision was left out.
  for (const document of documents) {
    for (const rule of document.explain?.rules ?? []) {
      if (rule.rule_id) names.add(rule.rule_id);
      if (rule.decision_kind) names.add(rule.decision_kind);
      for (const field of rule.fields ?? []) names.add(field);
    }
    if (document.explain?.default?.rule_id) names.add(document.explain.default.rule_id);
    const hypothetical = document.hypothetical_pnl;
    for (const code of hypothetical?.assumptions ?? []) names.add(code);
    for (const skipped of hypothetical?.skipped_decisions ?? []) {
      if (skipped.reason) names.add(skipped.reason);
      if (skipped.rule_id) names.add(skipped.rule_id);
      if (skipped.decision_kind) names.add(skipped.decision_kind);
    }
    for (const trade of hypothetical?.trades ?? []) {
      if (trade.entry_rule_id) names.add(trade.entry_rule_id);
      if (trade.exit_rule_id) names.add(trade.exit_rule_id);
    }
  }
  // …and the per-symbol document prints the PnL basis and the status of every
  // order the FIFO could not account for.
  for (const row of symbolsDocument().symbols ?? []) {
    for (const period of [row.pnl?.today, row.pnl?.cumulative]) {
      if (period?.pnl_basis) names.add(period.pnl_basis);
    }
    for (const attempt of row.pnl?.unresolved?.attempts ?? []) {
      if (attempt.status) names.add(attempt.status);
    }
  }
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

  it('guards the harvest itself, so the check above cannot be vacuous', () => {
    // If the fixtures ever stop carrying the P2 blocks, the loop above would
    // pass by inspecting nothing.
    const names = jargon();
    expect(names).toContain('R4-M2-PROBE-ENTRY-LONG');
    expect(names).toContain('FILL_AT_DECISION_BAR_CLOSE');
    expect(names).toContain('NOT_ENGINE_COUNTED');
    expect(names).toContain('EXECUTION');
    expect(names).toContain('NO_FILL');
  });

  it('explains every word the money columns add', () => {
    // Requirement 6 of the legibility plan: a new term on screen gets a
    // sentence, or this job fails rather than the operator guessing.
    for (const key of [
      'realized_pnl',
      'hypothetical_pnl',
      'fill_assumption',
      'round_trip',
      'unresolved_order',
      'clean_streak',
      'level_blocked',
      'level_check',
      'resident_paper',
      'field_definition',
    ]) {
      expect(glossaryTerm(key), key).not.toBeNull();
    }
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

  describe('주문서 작성 단계의 거절', () => {
    const STEP = 'CANDIDATE_COMMAND_CONSTRUCTION';

    it('names the zero-position case only when the evidence says so', () => {
      expect(
        haltExplanation('STAGE_DENIED', STEP, "quantity_basis 'ZERO_POSITION' closes a position…"),
      ).toMatch(/닫을 보유가 없어/);
      expect(haltExplanation('STAGE_DENIED', STEP, null, 'FLAT')).toMatch(/닫을 보유가 없어/);
    });

    it('stays generic for the other denials of the same step', () => {
      // tos/src/tos/egressgw/construction.py denies here for roughly two dozen
      // reasons, most of them sizing on an ENTRY. Calling all of them
      // «닫을 보유가 없어» was wrong on most of an entry-heavy day.
      const sizing = haltExplanation('STAGE_DENIED', STEP, 'risk sizing produced zero quantity', 'ACTION');
      expect(sizing).toBe('수량·가격을 정하지 못해 주문서를 만들지 못했습니다.');
      expect(haltExplanation('STAGE_DENIED', STEP, null, 'ACTION')).toBe(sizing);
    });
  });

  it('puts TOS, not the exchange, behind the venue verdict', () => {
    // The web tier never calls KIS and neither does this stage: it is TOS's
    // own check against the venue's rules.
    expect(haltExplanation('STAGE_DENIED', 'VENUE_ADMISSIBILITY_DECISION')).toMatch(
      /TOS 가 판정했습니다/,
    );
  });

  it('explains the aggregate-risk stage that older documents carry', () => {
    expect(glossaryTerm('AGGREGATE_RISK_DECISION')).not.toBeNull();
    expect(haltExplanation('STAGE_DENIED', 'AGGREGATE_RISK_DECISION')).toMatch(/한도를 넘습니다/);
  });

  it('offers no sentence for a stop this page has never seen', () => {
    expect(haltExplanation('STAGE_DENIED', 'SOME_FUTURE_STAGE')).toBeNull();
    expect(haltExplanation(null, null)).toBeNull();
  });

  it('keeps every meaning a sentence, not a label repeated', () => {
    for (const [key, term] of Object.entries(GLOSSARY)) {
      expect(term.label, key).not.toBe('');
      expect(term.meaning.length, key).toBeGreaterThan(term.label.length);
    }
  });
});
