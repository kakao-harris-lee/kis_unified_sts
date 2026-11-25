import { describe, expect, it } from 'vitest';
import {
  barGate,
  barVerdict,
  conditionRow,
  conditionRows,
  entryBlockers,
  entryProgress,
  fieldScale,
  formatFieldValue,
  gateTally,
  isProbeRule,
  latestCountedBar,
  parseCompare,
  ruleRoles,
  verdictTimeline,
} from './tosDecision';
import type { TosBarsBar } from './tosBars';
import {
  NO_APPROVAL_DETAIL,
  ZERO_POSITION_DETAIL,
  futuresBarsDocument,
  stockBarsDocument,
} from '@/test/tosBarsFixture';

const futures = futuresBarsDocument();
const stock = stockBarsDocument();
const bars = futures.bars as TosBarsBar[];
const [withheld, quiet, reverted, unjoined, entry, eod] = bars;

describe('units', () => {
  it('reads the scale factor out of the published name', () => {
    expect(fieldScale('close_x100')).toBe(100);
    expect(fieldScale('z_x1000')).toBe(1000);
    expect(fieldScale('entry_window')).toBe(1);
  });

  it('divides a scaled integer back into the number an operator reads', () => {
    // The document carries 73564 because the tenant published close ×100.
    expect(formatFieldValue('close_x100', '73564')).toBe('735.64');
    expect(formatFieldValue('close_x100', '17560000')).toBe('175,600');
    expect(formatFieldValue('z_x1000', '-2377')).toBe('-2.38');
    expect(formatFieldValue('z_x1000', '-1800')).toBe('-1.8');
  });

  it('says 예/아니오 for a boolean and nothing at all for an absent value', () => {
    expect(formatFieldValue('hi_vol', 'true')).toBe('예');
    expect(formatFieldValue('hi_vol', 'false')).toBe('아니오');
    expect(formatFieldValue('hi_vol', null)).toBeNull();
  });
});

describe('one comparison as a sentence', () => {
  it('parses the DSL shape and refuses anything else', () => {
    expect(parseCompare('z_x1000 LE config.z_entry_max_x1000')).toEqual({
      left: 'z_x1000',
      op: 'LE',
      right: 'config.z_entry_max_x1000',
    });
    expect(parseCompare('z_x1000 BETWEEN 1 AND 2')).toBeNull();
    expect(parseCompare(null)).toBeNull();
  });

  it('names the threshold from the DOCUMENT, not from a constant in this bundle', () => {
    const row = conditionRow(
      {
        index: 5,
        expression: 'z_x1000 LE config.z_entry_max_x1000',
        left_value: '-2377',
        right_value: '-1800',
        passed: true,
      },
      0,
    );
    expect(row.name).toBe('VWAP 이탈 z');
    expect(row.actual).toBe('-2.38');
    expect(row.threshold).toBe('≤ -1.8');
    expect(row.short).toBe('VWAP 이탈 z ≤ -1.8');
    expect(row.distance).toBeNull();
  });

  it('says how far a failing numeric condition was from passing', () => {
    const row = conditionRow(
      {
        index: 5,
        expression: 'z_x1000 LE config.z_entry_max_x1000',
        left_value: '-451',
        right_value: '-1800',
        passed: false,
      },
      0,
    );
    // -0.451 has to reach -1.8: 1.349 further down, in the field's own units.
    expect(row.distance).toEqual({ amount: '1.35', direction: 'down' });
  });

  it('turns a boolean gate into 예 rather than a number', () => {
    const row = conditionRow(
      { index: 2, expression: 'hi_vol EQ true', left_value: 'false', right_value: 'true', passed: false },
      0,
    );
    expect(row.name).toBe('변동성 충분');
    expect(row.actual).toBe('아니오');
    expect(row.threshold).toBe('예');
    expect(row.distance).toBeNull();
  });

  it('names a config binding on the right-hand side instead of printing true', () => {
    const row = conditionRow(
      {
        index: 2,
        expression: 'entry_window EQ config.m2_probe_entry_enabled',
        left_value: 'true',
        right_value: 'true',
        passed: true,
      },
      0,
    );
    expect(row.threshold).toBe('프로브 진입 스위치(예)');
  });

  it('shows an unparseable expression rather than guessing at it', () => {
    const row = conditionRow(
      { index: 1, expression: 'something entirely new', left_value: 'x', right_value: 'y', passed: false },
      0,
    );
    expect(row.name).toBe('something entirely new');
    expect(row.threshold).toBeNull();
  });
});

describe('which rule is which', () => {
  it('separates the strategy entry from the order-path probe', () => {
    expect(isProbeRule('R4-M2-PROBE-ENTRY-LONG')).toBe(true);
    expect(isProbeRule('R1-ENTRY-LONG')).toBe(false);
    const roles = ruleRoles(stock.bars?.[1].rules);
    expect(roles.entry?.rule_id).toBe('R1-ENTRY-LONG');
    expect(roles.probe?.rule_id).toBe('R4-M2-PROBE-ENTRY-LONG');
    expect(roles.exits.map((rule) => rule.rule_id)).toEqual([
      'R2-EXIT-VWAP-REVERTED',
      'R3-EXIT-EOD',
    ]);
  });

  it('counts how close a bar was to entering, and names what was missing', () => {
    expect(entryProgress(entry)).toEqual({
      passed: 5,
      total: 5,
      failing: [],
      ruleId: 'R1-ENTRY-LONG',
    });
    const quietProgress = entryProgress(quiet);
    expect(quietProgress?.passed).toBe(0);
    expect(quietProgress?.failing).toEqual([
      '진입 시간대',
      '변동성 충분',
      '추가 하락 멈춤',
      '반전 확인',
      'VWAP 이탈 z',
    ]);
  });

  it('reports no score at all for a bar the engine never judged', () => {
    // 0/5 would claim the conditions were checked and came out false.
    expect(entryProgress(withheld)).toBeNull();
  });

  it('reads the comparisons in the document order', () => {
    expect(conditionRows(ruleRoles(entry.rules).entry).map((row) => row.index)).toEqual([1, 2, 3, 4, 5]);
  });
});

describe('gates, as distinct from conditions', () => {
  it('does not call a quiet bar blocked', () => {
    // NO_ACTION_OUTCOME is the record that there was nothing to send.
    expect(barGate(quiet)).toBeNull();
  });

  it('reports the stage that refused a decided bar, with its own sentence', () => {
    expect(barGate(entry)).toEqual({
      reason: 'STAGE_UNKNOWN',
      step: 'INDEPENDENT_APPROVAL',
      label: '독립 승인 — 단계 결과 모름',
      detail: NO_APPROVAL_DETAIL,
    });
    expect(barGate(reverted)?.detail).toBe(ZERO_POSITION_DETAIL);
  });

  it('reports a withheld bar through its own reason, with no stage', () => {
    expect(barGate(withheld)).toMatchObject({ reason: 'TIME_NOT_ADMITTED', step: null });
  });

  it('tallies the session gates, commonest first', () => {
    expect(gateTally(futures.summary)).toEqual([
      { code: 'STAGE_DENIED@CANDIDATE_COMMAND_CONSTRUCTION', label: '주문서 작성 — 단계에서 거절', count: 2 },
      { code: 'STAGE_UNKNOWN@INDEPENDENT_APPROVAL', label: '독립 승인 — 단계 결과 모름', count: 1 },
    ]);
  });
});

describe('the verdict for one bar', () => {
  it('distinguishes «no signal» from «signal, then blocked»', () => {
    const quietVerdict = barVerdict(quiet);
    expect(quietVerdict.kind).toBe('none');
    expect(quietVerdict.blocked).toBe(false);
    expect(quietVerdict.gate).toBeNull();

    const entryVerdict = barVerdict(entry);
    expect(entryVerdict.kind).toBe('entry');
    expect(entryVerdict.blocked).toBe(true);
    expect(entryVerdict.gate?.reason).toBe('STAGE_UNKNOWN');
  });

  it('calls the probe a probe, not an entry signal', () => {
    const verdict = barVerdict(stock.bars?.[1] as TosBarsBar);
    expect(verdict.kind).toBe('probe');
    expect(verdict.headline).toBe('시험 진입');
    expect(verdict.blocked).toBe(false);
  });

  it('never reports an unevaluated bar as «no signal»', () => {
    expect(barVerdict(withheld).kind).toBe('withheld');
    expect(barVerdict(withheld).failing).toEqual([]);
    expect(barVerdict(unjoined).kind).toBe('unjoined');
  });

  it('names the exit rule that fired', () => {
    expect(barVerdict(eod)).toMatchObject({ kind: 'exit', ruleId: 'R3-EXIT-EOD', blocked: true });
  });
});

describe('the timeline', () => {
  it('emits one row per change, and nothing for a repeat', () => {
    const timeline = verdictTimeline(bars);
    expect(timeline.map((row) => row.timeKst)).toEqual([
      '08:45',
      '08:46',
      '08:48',
      '09:00',
      '09:14',
      '15:45',
    ]);
    expect(timeline.every((row) => row.run === 1)).toBe(true);
  });

  it('collapses a run of identical verdicts into one row that counts them', () => {
    const repeated = [quiet, { ...quiet, time_kst: '08:47' }, { ...quiet, time_kst: '08:49' }, entry];
    const timeline = verdictTimeline(repeated);
    expect(timeline).toHaveLength(2);
    expect(timeline[0]).toMatchObject({ timeKst: '08:46', run: 3 });
    expect(timeline[1]).toMatchObject({ timeKst: '09:14', run: 1 });
  });

  it('separates a gated decision from the same decision ungated', () => {
    // The probe fires twice on 005930: once through, once into the approval
    // gate. Collapsing them would hide the only interesting difference.
    const timeline = verdictTimeline(stock.bars as TosBarsBar[]);
    expect(timeline.map((row) => row.verdict.blocked)).toEqual([false, false, true, true]);
  });
});

describe('the day in aggregate', () => {
  it('ranks the entry conditions by how often they were false', () => {
    const blockers = entryBlockers(futures.summary);
    expect(blockers[0].name).toBe('진입 시간대');
    expect(blockers[0].failedPct).toBe(75);
    // hi_vol held on two of four judged bars, so it is the least of the five.
    expect(blockers[blockers.length - 1]).toMatchObject({ name: '변동성 충분', failedPct: 50 });
  });

  it('ranks the STRATEGY entry rule, never the probe', () => {
    // R4's id also contains ENTRY. Ranking its comparisons would answer «무엇이
    // 시험 주문을 막았나» under a heading that promises «무엇이 진입을 막았나».
    expect(entryBlockers(stock.summary).map((blocker) => blocker.expression)).toEqual([
      'stall_ok EQ true',
      'reversal_ok EQ true',
      'entry_window EQ true',
      'hi_vol EQ true',
      'z_x1000 LE config.z_entry_max_x1000',
    ]);
  });

  it('finds the last bar the engine actually judged', () => {
    expect(latestCountedBar(bars)?.time_kst).toBe('15:45');
    expect(latestCountedBar([withheld])).toBeNull();
    expect(latestCountedBar([])).toBeNull();
  });
});
