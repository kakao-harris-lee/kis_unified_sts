# P-VL 실행 증거 — CP-3 결정 9 (a) 보강, 2026-10-08 모의 GET

- 설계: `docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md` v2 §4·§5, **§8 3단계**.
- 프로브: `tools/broker_probes/probes_venue_limits.py` (`P-VL`) · 등재 `tools/broker_probes/registry.py`
  · 절차 `docs/runbooks/kis-capability-probes.md` §5.9.
- 환경: **MOCK_VTS 전용 · GET 4회/런 · 주문 0건.** 실전 자격증명 미사용.
- 실행: 분리 detached 워크트리 `origin/main` = `36afc379`
  (`P-VL-20261008T010644Z.json:repo_commit=36afc379`).

| 아티팩트 | 종목 | KST | 판정 |
|---|---|---|---|
| `P-VL-20261008T010644Z.json` | `A05610` (**당일 만기**) | 10:06:51 | L1·L2·L3 PASS · L4·L5 관측 |
| `P-VL-20261008T010822Z.json` | `A05611` (차근월) | 10:08:27 | L1·L2·L3 PASS · L4·L5 관측 |

두 아티팩트 모두 `errors` 0 · `provenance_class`
`P-VL-20261008T010644Z.json:provenance_class=MEASURED` ·
`P-VL-20261008T010822Z.json:provenance_class=MEASURED`.

## 0. 이 실행이 **확립한 것** (가장 중요한 것부터)

### 0.1 ⭐ 관측된 band 는 **미니 틱 0.02 에서만** 재현된다 — 배포 정책의 `tick_size: 5` 가 틀렸다는 **브로커 측** 증거

이것은 설계가 기대하지 않았던 산출이다. 설계 §2.0 은 정책의 0.05 가 full 의 값이라는 것을
**규정 문서**로만 말할 수 있었다. 이 실행은 **브로커가 공표한 band 자체**로 같은 결론을 준다.

`A05610` 기준가격 `P-VL-20261008T010644Z.json:measurements.l1_quote_fields.values.futs_sdpr=1073.32` 에
시행세칙 제56조(1단계 8% · 상한 내림/하한 올림)를 적용하면:

| 틱 | 상한가 | 하한가 | 관측과 일치? |
|---|---|---|---|
| **0.02** (미니 등록값) | **1159.18** | **987.46** | **일치** |
| 0.05 (배포 정책 `tick_size: 5`) | 1159.15 | 987.50 | 불일치 |

관측값: `P-VL-20261008T010644Z.json:measurements.l1_quote_fields.values.futs_mxpr=1159.18` ·
`P-VL-20261008T010644Z.json:measurements.l1_quote_fields.values.futs_llam=987.46`.
프로브가 1단계만 맞다고 적은 것도 같은 것이다 —
`P-VL-20261008T010644Z.json:measurements.l2_band_rule_arithmetic.matching_stages=[1]` ·
`P-VL-20261008T010644Z.json:measurements.l2_band_rule_arithmetic.tick_points=0.02`.

`A05611` 에서 독립적으로 재현된다. 기준가격
`P-VL-20261008T010822Z.json:measurements.l1_quote_fields.values.futs_sdpr=1076.60` →
관측 `P-VL-20261008T010822Z.json:measurements.l1_quote_fields.values.futs_mxpr=1162.72` ·
`P-VL-20261008T010822Z.json:measurements.l1_quote_fields.values.futs_llam=990.48`;
0.02 는 1162.72/990.48 을, 0.05 는 1162.70/990.50 을 준다.

프로브가 기록한 드리프트 플래그:
`P-VL-20261008T010644Z.json:measurements.resolved_instrument.tick_registry_matches_policy=false` ·
레지스트리 `P-VL-20261008T010644Z.json:measurements.resolved_instrument.registry_tick_points=0.02` ·
정책 `P-VL-20261008T010644Z.json:measurements.resolved_instrument.paper_policy_tick.tick_points=0.05`
(원 스칼라
`P-VL-20261008T010644Z.json:measurements.resolved_instrument.paper_policy_tick.tick_size_scaled_int=5`).

**해석(측정 아님)**: band 는 두 틱 중 0.02 격자에만 떨어지므로, 거래소가 이 상품의
호가가격단위를 0.02 로 쓰고 있다고 읽는 것이 자연스럽다. 다만 이 실행은 band **값**을 관측한
것이고 브로커가 호가가격단위를 **공표**한 것은 아니다(그 TR 은 호가단위 필드를 주지 않는다).
정책을 2 로 고치는 처분은 설계 §6 웨이브의 운영자 항목이다.

### 0.2 틱 격자 정합 (`corroborate_tick`)

다섯 필드 전부 등록 틱의 배수다 —
`P-VL-20261008T010644Z.json:measurements.l1_tick_corroboration.corroborated=true` ·
`P-VL-20261008T010644Z.json:measurements.l1_tick_corroboration.non_multiples=[]` ·
`P-VL-20261008T010822Z.json:measurements.l1_tick_corroboration.corroborated=true`.

### 0.3 모의 계좌는 1계약 이상 주문 가능 (L3)

`P-VL-20261008T010644Z.json:measurements.l3_psbl_at_touch.ord_psbl_qty_int=4` ·
`P-VL-20261008T010822Z.json:measurements.l3_psbl_at_touch.ord_psbl_qty_int=4`.
응답 코드 `P-VL-20261008T010644Z.json:measurements.l3_psbl_at_touch.msg_cd=20310000`
(「모의투자 조회가 완료되었습니다.」).

⚠ **이 4 는 venue 상한이 아니다.** `ord_psbl_qty` 는 예수금·증거금 **과 그 레그의
가격·방향·주문유형 파라미터**의 함수다
(`tools/broker_probes/probes_real_order.py::_preflight_instrument_state` 의 `interpretation` 키).

## 1. 관측 전용 — 해석하지 않는다 (L4·L5)

판정 토큰: `P-VL-20261008T010644Z.json:measurements.leg_verdicts.L4=OBSERVATION_ONLY_NO_VERDICT` ·
`P-VL-20261008T010644Z.json:measurements.leg_verdicts.L5=OBSERVATION_ONLY_NO_VERDICT`.

- **L4 하한가 경계** — 수락. `UNIT_PRICE`
  `P-VL-20261008T010644Z.json:measurements.l4_psbl_at_lower_limit.unit_price_sent=987.46` →
  `P-VL-20261008T010644Z.json:measurements.l4_psbl_at_lower_limit.rt_cd=0` ·
  `P-VL-20261008T010644Z.json:measurements.l4_psbl_at_lower_limit.ord_psbl_qty=4`.
- **L5 상한가 + 1틱 (band 밖)** — **역시 수락**. `UNIT_PRICE`
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.unit_price_sent=1159.20` →
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.rt_cd=0` ·
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.msg_cd=20310000` ·
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.ord_psbl_qty=4`.
  응답의 `bass_idx` 가 보낸 값을 그대로 되돌려준다 —
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.bass_idx=1159.20000000`.
  `A05611` 에서도 같다 —
  `P-VL-20261008T010822Z.json:measurements.l5_psbl_above_upper_limit.unit_price_sent=1162.74` ·
  `P-VL-20261008T010822Z.json:measurements.l5_psbl_above_upper_limit.rt_cd=0`.

**해석(측정 아님)**: 주문가능 **조회면**은 band 밖 가격을 거르지 않는 것으로 보인다. 이것은
**조회 거부 표면의 부재**에 대한 관측이고, 같은 가격으로 **주문**을 넣었을 때 무엇이 일어나는지는
말하지 않는다(그 관측은 이 프로브의 GET-only 범위 밖 — 설계 §4.3 · §7 ④).

## 2. 이 실행이 **확립하지 못한 것**

- **KIS 측 호가수량한도.** GET 으로 관측 불가. 규정값은 별표 17의2 제1호의
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_row.regular_session_contracts=10000`
  (야간 `…night_session_contracts=5000`, 유동성관리상품 지정 시
  `…liquidity_managed_regular_contracts=1000`)이고, 이것은 **맥락**이다 —
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_is_context_only`
  가 그 사실을 적는다. 회원 하향(제61조제3항)·거래소 변경(제61조제1항 단서) 단서는
  `…krx_quantity_limit_row.caveats` 에 함께 있다.
- **기준가격이 「직전 거래일 정산가격」인지.** 두 샘플 모두 `futs_sdpr` 와 `futs_prdy_clpr` 가
  **같아서** 판별되지 않았다 —
  `P-VL-20261008T010644Z.json:measurements.l1_basis_price_distinguishable.differ=false` ·
  `P-VL-20261008T010644Z.json:measurements.l1_basis_price_distinguishable.distinguishes_settlement_from_close=false`
  (`A05611` 도 `P-VL-20261008T010822Z.json:measurements.l1_basis_price_distinguishable.differ=false`).
  **같다는 것은 규정이 틀렸다는 증거가 아니다** — 이 샘플이 그 질문에 무정보라는 뜻이다.
  두 잎 모두 분기월이 아니므로 제55조제1항 단서는 적용되지 않는다
  (`P-VL-20261008T010644Z.json:measurements.l1_basis_price_distinguishable.quarterly_mini_leaf=false`).
- **2/3단계 확대 의미론.** 미관측. 두 샘플 모두 확대 불가 창(08:45~09:00) **밖**이고
  (`P-VL-20261008T010644Z.json:measurements.l1_sample_window.inside_no_escalation_window=false` ·
  `P-VL-20261008T010644Z.json:measurements.l1_sample_window.expected_stage_is_determined=false`)
  그래도 1단계가 관측됐다. 즉 **그날 확대는 없었다**는 사실만 기록된다.
- **설계 §4.2 의 ① 샘플(08:50±3분).** 오늘은 찍지 못했다 — 실행 시각이 10:06 이었다. 이 증거는
  ② 샘플 전용이고, L2 PASS 는 「1단계가 재현됐다」이지 「1단계가 **보장된** 창에서 재현됐다」가
  아니다.
- **band 의 런타임 공급.** 이 프로브는 값을 관측할 뿐이다(설계 §6).

## 3. 처분 — P0-2 복합 토큰

두 아티팩트가 같은 토큰을 파생했다 —
`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.proposed=BAND_SEMANTICS_OBSERVED_ON_MOCK__TICK_FROM_REGULATION_NOT_BROKER__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED`
· `P-VL-20261008T010822Z.json:measurements.p02_disposition_proposal.proposed=BAND_SEMANTICS_OBSERVED_ON_MOCK__TICK_FROM_REGULATION_NOT_BROKER__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED`.

토큰은 판정에서 **파생**된다(한 단어 상태는 프로파일 어휘에 없다 — 설계 v2 §5):
`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.derived_from.L1=PASS` ·
`…derived_from.L2=PASS`. L2 가 통과하지 않았다면 band 축은 `OBSERVED_ON_MOCK` 를 적지 못한다.

미확립 축은 아티팩트가 열거한다 —
`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.still_unestablished[0]`.

## 4. 실행 조건 — 숨기지 않는 사실 셋

1. **`A05610` 은 당일 만기다**(2026-10-08, 둘째 목요일). 호스트 read-model 이
   `roll_state=expired` · `days_to_expiry=0` · `new_entry_front_allowed=false` 로 적고 있었다
   (`futures:contract:latest`, Redis DB 1, `asof_ts 2026-10-08T08:00:00`). 만기일의 시세·band 는
   최종결제 거동을 반영할 수 있으므로, 이 잎의 수치를 **평시 값으로 읽지 말 것**. 차근월
   `A05611`(만기 2026-11-12)을 같은 런에서 찍은 이유가 그것이고, 두 잎에서 §0.1 의 결론이
   **독립적으로** 재현된다.
2. **차근월 코드는 가정하지 않고 read-model 에서 읽었다** — `next_symbol=A05611` ·
   `next_expiry_date=2026-11-12`.
3. **`.env.mock` 의 앱키는 상주 paper 세션의 키와 같다.** 그 세션의 래퍼
   (`/home/deploy/.config/kis-probes/tos-paper-session.sh:59`)가 `ENVFILE=$MAIN/.env.mock` 로
   **같은 파일**을 소싱하므로 지문 비교 이전에 구성상 동일하다(`KIS_FUTURES_APP_KEY`
   sha256[:12] = `cf6e5f9480ad`). 런북 §5.9 선행조건대로 **오늘은 샘플을 하나의 창에서만**
   찍었고, 두 런은 프로브 전용 토큰 캐시를 공유해 토큰 발급은 **1회**였다(N-15 1분 재발급
   한도 회피). 계좌는 마스킹만 기록된다 —
   `P-VL-20261008T010644Z.json:credentials.account_masked=60******03`.

## 4.1 설계 §8 3단계의 부수 과제 — `STAGE_DENIED` 재집계 (2:1 매핑 해소)

설계 §1 「소비 1」 행이 10-07 세션에서 `STAGE_DENIED` 행 5,020 과 사유 문자열 행 2,510 의
**2:1 매핑**을 미해소로 남겨 두었다. 상주 paper 세션의 evidence store 를 읽어 그 구조를
확인했다. **이 수치는 아티팩트가 아니라 DB 스냅샷이므로 인용 토큰을 달지 않는다** — 대신
재현 SQL 과 스냅샷 좌표를 적는다.

- 대상: `~/.local/state/tos/paper-data/A05610/evidence.sqlite3` (append-only · 읽기 전용 열기)
- 스냅샷: `MAX(seq) = 164200` · `COUNT(*) = 164201` · 2026-10-08 10:18:33 KST

| 집계 | 행 수 |
|---|---|
| `payload_json LIKE '%STAGE_DENIED%'` 전체 | 11,164 |
| 그중 `kind = 'EVENT_CONSUMED'` | 5,582 |
| 그중 `kind = 'FLOW_HALTED'` | 5,582 |
| `payload_json LIKE '%quantity constraint is incomplete%'` | 5,582 |

**매핑은 2:1 이 아니라 「1 거부 → 2 행」이다.** 거부 한 건이 `EVENT_CONSUMED` 와
`FLOW_HALTED` 를 **각각 하나** 남기고, 사유 문자열은 `FLOW_HALTED` **에만** 있다 — 사유 행
수가 `FLOW_HALTED` 행 수와 **정확히 같다**(5,582 = 5,582). 따라서 설계가 본 「5,020 ↔ 2,510」은
같은 구조의 이른 스냅샷이고, 사유 문자열이 누락된 거부는 **0 건**이다.

```bash
sqlite3 "file:$HOME/.local/state/tos/paper-data/A05610/evidence.sqlite3?mode=ro" "
SELECT 'stage_denied_total', COUNT(*) FROM entries WHERE payload_json LIKE '%STAGE_DENIED%'
UNION ALL SELECT 'flow_halted', COUNT(*) FROM entries WHERE payload_json LIKE '%STAGE_DENIED%' AND kind='FLOW_HALTED'
UNION ALL SELECT 'reason_rows', COUNT(*) FROM entries WHERE payload_json LIKE '%quantity constraint is incomplete%';"
```

⚠ **두 가지 한계를 숨기지 않는다.** ① store 는 **지금도 기록 중**이다 — 같은 질의를 3분 간격으로
두 번 돌렸을 때 5,580 → 5,582 로 늘었다. 위 표는 `seq 164200` 스냅샷이고 「현재값」이 아니다.
② 이 디렉터리는 **결제월 단위**(`paper-data/A05610`)라 10-06 genesis 이후 전 세션을 담고
있고, payload 최상위에 벽시계 필드가 없어(`masked_keys`·`payload` 뿐) **10-07 하루만 분리한
수치가 아니다**. 설계가 적은 10-07 값과 직접 비교하지 말 것 — 확인된 것은 **비율과 구조**다.

## 5. 재현

```bash
git worktree add --detach <path> origin/main          # 36afc379
install -m 600 <primary>/.env.mock <path>/.env.mock
cd <path> && set -a && . ./.env.mock && set +a
python -m tools.broker_probes.run P-VL --asset futures --symbol A05610            # dry-run
python -m tools.broker_probes.run P-VL --asset futures --symbol A05610 --confirm
python -m tools.broker_probes.run P-VL --asset futures --symbol A05611 --confirm
python tools/tos_evidence_citation_check.py docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/README.md
```

아티팩트는 `tools/broker_probes/results/`(gitignore)에 쓰이고 이 디렉터리로 복사된다.
`approval_status` 는 둘 다
`P-VL-20261008T010644Z.json:approval_status=UNAPPROVED_CANDIDATE` — 프로파일 기입은 P0-2
승인 사슬이 따로 있다.
