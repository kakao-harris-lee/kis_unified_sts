// The ONE plain-Korean glossary for /tos. Every jargon term, rule id, gate code
// and flag the page can render resolves through here, so a term explained in
// one section cannot be explained differently — or left unexplained — in
// another.
//
// SOURCE OF TRUTH, and the direction of the dependency: the *numbers* in these
// meanings restate tenant content —
// `config/tos_runtime/<tree>/fields.yaml` (field definitions and thresholds)
// and `config/tos_runtime/<tree>/strategies/*.strategy.yaml` (`rationale:`).
// They are identical across all five CP-3 tenants today, which is the only
// reason one shared sentence can carry a number at all. A tenant that repoints
// one of them makes the sentence here stale, so the number the operator ACTS on
// is never read from this file: the per-bar checklist prints the threshold the
// bars document itself carries (`compares[].right_value`), and this text stays
// the conceptual explanation beside it.
//
// Nothing here is read from an API. It is UI vocabulary, which is why it is a
// TS map rather than a field on a response: phase 2 may add an exporter-side
// description, and that will replace this map's values rather than this map's
// callers.

export interface GlossaryTerm {
  /** The plain-Korean name that REPLACES the jargon on screen. */
  label: string;
  /** One sentence: what it means, in the operator's terms. */
  meaning: string;
}

/**
 * Keys are the raw strings the documents carry — published field names, config
 * binding names, rule ids, halt reasons, halt steps, decision kinds, evidence
 * outcome types, bar flags and basis names.
 *
 * A key absent here is NOT an error: `glossaryTerm` returns null and callers
 * fall back to the raw string. A tenant may publish a field this page has never
 * seen, and showing its raw name is strictly better than hiding it.
 */
export const GLOSSARY: Record<string, GlossaryTerm> = {
  // --- published fields: prices and indicators ------------------------------
  close: { label: '종가', meaning: '그 1분봉이 닫힌 가격입니다.' },
  open: { label: '시가', meaning: '그 1분봉이 열린 가격입니다.' },
  high: { label: '고가', meaning: '그 1분봉의 최고가입니다.' },
  low: { label: '저가', meaning: '그 1분봉의 최저가입니다.' },
  volume: { label: '거래량', meaning: '그 1분봉 동안 체결된 수량입니다.' },
  vwap: {
    label: 'VWAP',
    meaning: '거래량으로 가중한 그날의 평균가입니다. 전략은 가격이 여기서 얼마나 벌어졌다가 돌아오는지를 봅니다.',
  },
  atr14: {
    label: 'ATR(14)',
    meaning: '최근 14봉의 평균 변동폭입니다. 가격 차이를 「ATR 몇 배」로 환산하는 자입니다.',
  },
  z: {
    label: 'VWAP 이탈 z',
    meaning: '(종가 − VWAP) ÷ ATR. 가격이 평균가에서 ATR 몇 배만큼 벌어졌는지로, 음수면 평균가 아래입니다.',
  },
  session_token: { label: '세션 날짜표', meaning: '그 봉이 속한 거래일을 가리키는 표식입니다.' },

  // --- published fields: boolean gates --------------------------------------
  entry_window: {
    label: '진입 시간대',
    meaning: '장 시작 15분 뒤부터 345분까지입니다. 이 창 밖에서는 새로 진입하지 않습니다.',
  },
  hi_vol: {
    label: '변동성 충분',
    meaning:
      '진입 시간대 안에서 ATR(14)이 최근 분포(780봉 90퍼센타일)의 0.9배 이상인지입니다. 시간대 밖에서는 언제나 거짓이고, 기준 분포가 아직 쌓이지 않은 장 초반에는 통과로 봅니다.',
  },
  stall_ok: {
    label: '극단 이탈 뒤 멈춤',
    meaning:
      '먼저 「변동성 충분」이 서고 평균가 이탈 z의 절댓값이 1.8 이상이어야 합니다. 그 상태에서 가격이 최근 15봉의 고·저로부터 ATR 1.5배 안에 머물러 더 밀리지 않았으면 통과입니다. 극단까지 벌어지지 않은 평범한 봉에서는 거짓입니다.',
  },
  reversal_ok: {
    label: '반전 확인',
    meaning:
      '「극단 이탈 뒤 멈춤」이 선 위에, 직전 봉 대비 방향이 돌아섰고 평균가 이탈 폭이 ATR 0.2배 이상 줄었는지입니다. 직전 종가를 아직 모르면 거짓입니다.',
  },
  vwap_reverted: {
    label: 'VWAP 복귀',
    meaning: '가격이 평균가 근처(이탈 z의 절댓값 0.2 이하)로 돌아왔는지 — 되돌림을 노린 보유를 닫는 신호입니다.',
  },
  eod: { label: '장 마감 시각', meaning: '15:15 이후인지 — 그날 안에 보유를 닫기 위한 시각 조건입니다.' },
  rsi_oversold: {
    label: 'RSI 과매도',
    meaning: 'RSI(14)가 30 이하인지 — 단기 과매도 구간입니다. 지표가 아직 충분히 쌓이지 않았으면 거짓입니다.',
  },
  wr_oversold: {
    label: '윌리엄스 %R 과매도',
    meaning:
      '윌리엄스 %R(14)이 −80 이하인지 — 최근 범위의 바닥 쪽이라는 뜻입니다. 지표가 아직 충분히 쌓이지 않았으면 거짓입니다.',
  },
  rsi_recovered: {
    label: 'RSI 회복',
    meaning:
      'RSI(14)가 50 이상으로 돌아왔는지 — 과매도 해소로 보는 청산 조건입니다. 지표가 아직 충분히 쌓이지 않았으면 거짓입니다.',
  },

  // --- config bindings (the operator-set numbers a rule compares against) ----
  'config.z_entry_max_x1000': {
    label: '진입 z 상한',
    meaning: '진입을 허용하는 평균가 이탈의 한계입니다. 이탈 z가 이 값 이하로 벌어져야 매수 진입 조건이 섭니다.',
  },
  'config.z_entry_min_x1000': {
    label: '진입 z 하한',
    meaning: '매도(SHORT) 진입을 허용하는 평균가 이탈의 한계입니다. 이탈 z가 이 값 이상이어야 조건이 섭니다.',
  },
  'config.m2_probe_entry_enabled': {
    label: '프로브 진입 스위치',
    meaning: '운영자가 켜 둔 주문 경로 점검용 스위치입니다. 전략 신호가 아니라 시험 주문을 내기 위한 값입니다.',
  },

  // --- rule ids --------------------------------------------------------------
  'R0-DEFAULT-NO-ACTION': {
    label: '해당 규칙 없음',
    meaning: '어떤 규칙도 발화하지 않아 보유를 그대로 둔 봉입니다.',
  },
  'R1-ENTRY-LONG': {
    label: '매수 진입',
    meaning: '진입 시간대·변동성·추가 하락 멈춤·반전이 모두 서고 평균가 이탈이 진입 기준까지 벌어졌을 때 매수를 제안합니다.',
  },
  'R1-ENTRY-SHORT': {
    label: '매도 진입',
    meaning: '같은 조건을 반대 방향으로 본 것으로, 평균가 위쪽으로 벌어졌을 때 매도를 제안합니다.',
  },
  'R1-ENTRY-LONG-RSI-WR': {
    label: 'RSI·%R 매수 진입',
    meaning: '진입 시간대에 RSI(14)와 윌리엄스 %R(14)이 함께 과매도일 때 매수를 제안합니다.',
  },
  'R2-EXIT-VWAP-REVERTED': {
    label: 'VWAP 복귀 청산',
    meaning: '가격이 평균가로 돌아와 되돌림 가설이 실현됐으므로 보유를 닫습니다.',
  },
  'R2-EXIT-RSI-RECOVERED': {
    label: 'RSI 회복 청산',
    meaning: 'RSI(14)가 중앙선으로 돌아와 과매도가 해소됐으므로 보유를 닫습니다.',
  },
  'R3-EXIT-EOD': { label: '장 마감 청산', meaning: '그날의 마감 시각이 되어 보유를 닫습니다.' },
  'R4-M2-PROBE-ENTRY-LONG': {
    label: '시험 진입(프로브)',
    meaning: '전략 신호가 아닙니다. 승인·예약·검증·모의 전송·결과 확정까지 주문 경로가 끝까지 도는지 확인하려고 내는 시험 주문입니다.',
  },

  // --- decision kinds ---------------------------------------------------------
  ACTION: { label: '진입 제안', meaning: '새 포지션을 여는 쪽으로 판단한 봉입니다.' },
  FLAT: { label: '청산 제안', meaning: '보유를 닫는 쪽으로 판단한 봉입니다.' },
  NO_ACTION: { label: '신호 없음', meaning: '어떤 규칙도 서지 않아 아무 것도 하지 않은 봉입니다.' },

  // --- gates: halt reasons and the stage they fired at -------------------------
  STAGE_DENIED: {
    label: '단계에서 거절',
    meaning: '판단은 섰지만 커널의 한 단계가 명시적으로 거절해 주문이 나가지 않았습니다.',
  },
  STAGE_UNKNOWN: {
    label: '단계 결과 모름',
    meaning: '판단은 섰지만 커널의 한 단계가 결과를 알려 주지 않았습니다. 모르는 것은 허가로 치지 않으므로 주문은 나가지 않습니다.',
  },
  INDEPENDENT_APPROVAL: {
    label: '독립 승인',
    meaning: '제안된 주문을 따로 승인하는 단계입니다. 승인 결과가 없으면 막습니다.',
  },
  VENUE_ADMISSIBILITY_DECISION: {
    label: '거래소 수용 판정',
    meaning:
      '거래소 규칙상 그 시각에 그 주문을 낼 수 있는지 TOS 가 스스로 보는 단계입니다. 거래소에 물어본 결과가 아니라 TOS 의 판정입니다.',
  },
  AGGREGATE_RISK_DECISION: {
    label: '총 위험 한도 판정',
    meaning:
      '진행 중인 주문과 이미 보유한 수량까지 합쳐 한도를 넘지 않는지 보는 단계입니다.',
  },
  CANDIDATE_COMMAND_CONSTRUCTION: {
    label: '주문서 작성',
    meaning:
      '수량·가격을 넣어 실제 주문서를 만드는 단계입니다. 수량을 정하지 못하는 사유가 스무 가지쯤 되며, 닫을 보유가 없는 경우는 그중 하나입니다.',
  },
  TIME_NOT_ADMITTED: {
    label: '시간 미인정',
    meaning: '그 봉의 시각을 커널이 인정하지 않아 아예 평가하지 않았습니다. 조건이 거짓이었던 것과는 다릅니다.',
  },
  DECISION_WITHHELD: { label: '판단 보류', meaning: '그 봉에서는 판단 자체를 하지 않았습니다.' },
  NO_ACTION_OUTCOME: {
    label: '신호 없음 결과',
    meaning: '막힌 것이 아니라 낼 주문이 없었다는 기록입니다. 게이트가 아닙니다.',
  },

  // --- evidence outcome types ---------------------------------------------------
  Proposal: { label: '주문 제안 생성', meaning: '규칙이 서서 주문 제안이 만들어진 봉입니다.' },
  NoActionOutcome: { label: '주문 없음', meaning: '낼 주문이 없다는 결과가 기록된 봉입니다.' },

  // --- bar flags ------------------------------------------------------------------
  V: { label: '엔진 값 ≠ 기록 값', meaning: '엔진이 실제로 본 값과 생산자가 남긴 기록이 달랐던 봉입니다.' },
  D: { label: '결정 ≠ 엔진 결과', meaning: '기록된 결정이 엔진이 낸 결과와 달랐던 봉입니다.' },
  W: { label: '보류', meaning: '평가하지 않은 봉이라 조건의 참·거짓을 말할 수 없습니다.' },
  U: { label: '기록으로 대체', meaning: '엔진 값을 얻지 못해 생산자 기록으로 대신 본 봉이며, 통계의 분모에서 빠집니다.' },

  // --- the shapes this page distinguishes ------------------------------------------
  paper_cell: {
    label: 'paper 셀',
    meaning:
      'TOS 커널이 상주해 도는 모의 운영 셀입니다. 아래 tenant 세션과는 별개의 기록이라, 이 값이 신선하다고 해서 tenant 가 정상이라는 뜻은 아닙니다.',
  },
  decision_only: {
    label: '판단 전용',
    meaning: '주문을 내지 않고 판단만 기록하는 tenant 입니다. 체결도 손익도 없습니다.',
  },
  mock_account: {
    label: '모의 계좌',
    meaning: 'KIS 모의투자 계좌입니다. 실제 자금이 오가지 않습니다.',
  },
  counted_bars: {
    label: '판단한 봉',
    meaning: '엔진이 실제로 값을 보고 규칙을 따져 본 봉의 수입니다. 보류된 봉과 기록으로 대체한 봉은 빠집니다.',
  },

  // --- money: what each figure is, and is not ---------------------------------------
  realized_pnl: {
    label: '실현 손익',
    meaning:
      '그날 실제로 사고팔아 닫힌 수량의 손익입니다. FIFO 로 짝지어 계산하며 수수료·세금·슬리피지는 빼지 않았습니다. 아직 들고 있는 수량의 평가 손익은 들어 있지 않습니다.',
  },
  hypothetical_pnl: {
    label: '가상 손익(체결 가정)',
    meaning:
      '실제 손익이 아닙니다. 주문을 내지 않는 tenant 의 판단만 모아, 그대로 체결됐다면 얼마였을지를 계산한 값입니다. 실현 손익과 더하지 않습니다.',
  },
  fill_assumption: {
    label: '체결 가정',
    meaning:
      '가상 손익이 서 있는 가정들입니다 — 판단 봉의 종가에 반드시 체결되고, 수수료와 슬리피지가 없으며, 한 번에 한 계약만 들고 있다고 봅니다. 셋 다 숫자를 좋은 쪽으로 밀어 줍니다.',
  },
  round_trip: {
    label: '왕복',
    meaning:
      '사서 다시 판 한 쌍입니다. FIFO 로 닫힌 lot 조각마다 세므로, 매수 둘을 한 번에 턴 매도는 왕복 2 입니다.',
  },
  unresolved_order: {
    label: '미해결 주문',
    meaning:
      '손익 집계에 넣지 못한 주문 시도입니다. 브로커가 받지 않았거나(비체결 종료), 결과를 끝내 확인하지 못했습니다(미해결). 체결이 아니므로 손익에 들어가지 않습니다.',
  },
  EXECUTION: {
    label: '체결가 기준',
    meaning: '브로커가 찍은 평균 체결가로 계산한 손익입니다.',
  },
  ORDER_PRICE: {
    label: '지정가 기준',
    meaning:
      '체결가를 얻지 못해 보낸 주문의 지정가로 계산한 손익입니다. 실제 체결가와 다를 수 있습니다.',
  },
  MIXED: {
    label: '기준 섞임',
    meaning: '한쪽 다리는 체결가, 다른 쪽은 지정가로 계산된 손익입니다.',
  },
  UNRESOLVED: {
    label: '미해결',
    meaning: '주문을 보낸 뒤 결과를 끝내 확인하지 못했습니다. 체결로도 비체결로도 세지 않습니다.',
  },
  NO_FILL: {
    label: '비체결 종료',
    meaning: '브로커가 받지 않아 체결 없이 끝난 주문입니다.',
  },

  // --- the hypothetical total's assumptions, as the document names them --------------
  FILL_AT_DECISION_BAR_CLOSE: {
    label: '판단 봉 종가 체결',
    meaning: '판단이 선 그 1분봉의 종가에 들어가고 나왔다고 봅니다.',
  },
  FILL_ALWAYS_ASSUMED: {
    label: '체결 보장 가정',
    meaning: '주문이 언제나 체결됐다고 봅니다. 호가가 비어 못 샀을 경우를 세지 않습니다.',
  },
  NO_FEES: { label: '수수료 없음', meaning: '수수료와 세금을 빼지 않았습니다.' },
  NO_SLIPPAGE: {
    label: '슬리피지 없음',
    meaning: '주문이 원하는 가격 그대로 체결됐다고 봅니다.',
  },
  ONE_CONTRACT: { label: '1계약', meaning: '언제나 한 계약만 거래했다고 봅니다.' },
  ONE_POSITION_AT_A_TIME: {
    label: '동시 보유 1건',
    meaning: '이미 들고 있는 동안의 새 진입 판단은 세지 않습니다.',
  },

  // --- why a decision bar is outside the hypothetical total -------------------------
  NOT_ENGINE_COUNTED: {
    label: '엔진 판단이 아님',
    meaning:
      '엔진이 실제로 판단한 봉이 아니라 점검이 되짚어 본 봉입니다. 전략의 성과로 치면 하지 않은 일을 센 것이 됩니다.',
  },
  ENGINE_DISAGREES: {
    label: '엔진과 불일치',
    meaning: '기록된 결정이 엔진이 낸 결과와 달랐던 봉이라 합계에서 뺐습니다.',
  },
  PROBE_ENTRY: {
    label: '시험 진입',
    meaning: '주문 경로 점검용 진입이라 전략의 성과로 세지 않습니다.',
  },

  // --- the status board's vocabulary ------------------------------------------------
  clean_streak: {
    label: '깨끗한 날 누적',
    meaning:
      '막힘 없이 끝난 거래일이 연달아 몇 날인지입니다. paper 승격 기준(목표 일수)까지 세며, 하루라도 막히면 처음부터 다시 셉니다.',
  },
  level_blocked: {
    label: '막힘',
    meaning: '그 세션이 멈췄거나 더 진행할 수 없는 상태입니다. 먼저 볼 줄입니다.',
  },
  level_check: {
    label: '확인',
    meaning: '돌긴 했지만 사람이 한 번 봐야 하는 일이 있었다는 뜻입니다. 멈춘 것은 아닙니다.',
  },
  resident_paper: {
    label: '상주 paper',
    meaning:
      '장중 내내 떠 있는 모의 운영 셀입니다. 런타임과 드라이버 두 프로세스가 살아 있어야 「상주 중」이며, 지난 날짜의 상태판은 이를 확인하지 않습니다.',
  },
  field_definition: {
    label: '필드 정의',
    meaning:
      '그 값을 무엇으로 계산하는지를 tenant 의 필드 카탈로그(fields.yaml)에서 그대로 가져온 것입니다. 연산 이름과 입력, 설정값 순서로 적혀 있습니다.',
  },

  // --- bases ------------------------------------------------------------------------
  TOS_LEDGER_FIFO_OPEN_LOTS: {
    label: 'TOS 기준 보유',
    meaning: '브로커 잔고 조회가 아니라 TOS 자신의 증거에서 아직 닫히지 않은 수량입니다.',
  },
  ORDER_BAR: {
    label: '주문 봉 시각',
    meaning: '브로커가 체결한 시각이 아니라 그 주문을 낸 결정 봉의 시각입니다.',
  },
};

/**
 * A published field's name without its scale suffix.
 *
 * The tenant's `publish:` block renames a field with the factor it multiplied
 * by (`close` → `close_x100`, `z` → `z_x1000`), so the glossary is keyed on the
 * bare name and every scaled alias of it resolves to the same entry.
 */
export function glossaryKey(name: string): string {
  return name.replace(/_x\d+$/, '');
}

/** The term for a raw document string, or null when this page has never seen it. */
export function glossaryTerm(name: string | null | undefined): GlossaryTerm | null {
  if (!name) return null;
  return GLOSSARY[name] ?? GLOSSARY[glossaryKey(name)] ?? null;
}

/** The plain-Korean name, falling back to the raw string rather than hiding it. */
export function glossaryLabel(name: string | null | undefined): string {
  if (!name) return '알 수 없음';
  return glossaryTerm(name)?.label ?? name;
}

/**
 * A `REASON@STEP` pair as one plain phrase — the shape the summary's
 * `evidence_halts` keys use (`STAGE_DENIED@VENUE_ADMISSIBILITY_DECISION`).
 */
export function haltPairLabel(reason: string | null, step: string | null): string {
  const left = glossaryLabel(reason);
  if (!step) return left;
  return `${glossaryLabel(step)} — ${left}`;
}

/**
 * What a stop MEANT, in one Korean sentence, per `REASON@STEP` pair.
 *
 * The evidence writes its own English sentence into `halt_detail`, and the
 * page still shows it verbatim — it is the authoritative record and a
 * translation would be this bundle's claim about it, not the kernel's. But an
 * operator reading the day should not have to parse English first, so this
 * leads and the original follows as secondary text.
 *
 * Absent for a pair this page has not seen: the caller then shows the two
 * glossary meanings it already has, rather than a sentence nobody wrote.
 */
const HALT_EXPLANATIONS: Record<string, string> = {
  'STAGE_DENIED@VENUE_ADMISSIBILITY_DECISION':
    '거래소 규칙상 그 시각에 받을 수 없는 주문이라고 TOS 가 판정했습니다.',
  'STAGE_DENIED@AGGREGATE_RISK_DECISION':
    '총 위험 한도 판정에서 거절했습니다 — 진행 중이거나 이미 보유한 수량과 합치면 한도를 넘습니다.',
  'STAGE_UNKNOWN@INDEPENDENT_APPROVAL':
    '승인 단계가 결과를 돌려주지 않았습니다. 모르는 것은 허가로 치지 않으므로 주문은 나가지 않았습니다.',
  TIME_NOT_ADMITTED: '그 봉의 시각을 커널이 인정하지 않아 아예 평가하지 않았습니다.',
};

/** The one construction denial this page can name from the code alone. */
const ZERO_POSITION_MARKER = 'ZERO_POSITION';

const ZERO_POSITION_SENTENCE =
  '닫을 보유가 없어 주문서를 만들지 못했습니다. 보유를 모르는 채로 수량을 가정해 내보내지 않습니다.';

const CONSTRUCTION_SENTENCE = '수량·가격을 정하지 못해 주문서를 만들지 못했습니다.';

/**
 * What a stop MEANT, in one Korean sentence.
 *
 * The evidence writes its own English sentence into `halt_detail`, and the page
 * still shows it verbatim — it is the authoritative record, and a translation
 * would be this bundle's claim about it rather than the kernel's. This leads
 * only so that an operator does not have to parse English first.
 *
 * `CANDIDATE_COMMAND_CONSTRUCTION` takes `detail` and `decisionKind` because
 * the step denies for roughly two dozen distinct reasons (sizing, rounding,
 * price bands, …) and only one of them is «closing with no position». Naming
 * that one for all of them was wrong on most of an entry-heavy day, so the
 * close sentence is used only when the evidence says ZERO_POSITION or the
 * decision was a close; everything else gets the generic sentence and relies on
 * the verbatim detail beneath it to say which.
 *
 * Null for a pair this page has not seen: the caller then shows the two
 * glossary meanings it already has, rather than a sentence nobody wrote.
 */
export function haltExplanation(
  reason: string | null,
  step: string | null,
  detail?: string | null,
  decisionKind?: string | null,
): string | null {
  if (!reason) return null;
  if (step === 'CANDIDATE_COMMAND_CONSTRUCTION') {
    const closing = detail?.includes(ZERO_POSITION_MARKER) === true || decisionKind === 'FLAT';
    return closing ? ZERO_POSITION_SENTENCE : CONSTRUCTION_SENTENCE;
  }
  const pair = step ? `${reason}@${step}` : reason;
  return HALT_EXPLANATIONS[pair] ?? HALT_EXPLANATIONS[reason] ?? null;
}
