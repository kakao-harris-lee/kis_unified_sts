# P-VL 실행 증거 — CP-3 결정 9 (a) 보강, 2026-10-08 모의 GET

- 설계: `docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md` v2 §4·§5, **§8 3단계**.
- 프로브: `tools/broker_probes/probes_venue_limits.py` (`P-VL`) · 등재 `tools/broker_probes/registry.py`
  · 절차 `docs/runbooks/kis-capability-probes.md` §5.9.
- 환경: **MOCK_VTS 전용 · GET 4회/런 · 주문 0건.** 실전 자격증명 미사용.
- 실행 호스트: `NUCBOXM7Ultra` (WSL2, 이 레포의 상주 운영 호스트 — 상주 paper 세션과
  같은 호스트다). 실행자 계정 `deploy`. (`hostname` 출력)
- 실행: 분리 **detached** 워크트리 `/home/deploy/.local/state/tos/measure/wt-pvl-run`,
  `origin/main` = `36afc379` (`P-VL-20261008T010644Z.json:repo_commit=36afc379`).
  실행 시각 `git status --short` = **빈 출력**(clean) · `git rev-parse --abbrev-ref HEAD`
  = `HEAD`(detached) · `git merge-base --is-ancestor HEAD origin/main` = 참. 셋은
  `tools/broker_probes/runners/_common.sh::guard_checkout` 의 세 조건과 같다. ⚠
  `repo_commit` 은 **HEAD 를 적을 뿐 트리가 깨끗했음을 증명하지 않는다** — 그래서
  따로 적는다.
- 라이브 게이트: `config/futures_live.yaml::enabled` = `false` · Redis DB 1 의
  `futures:live:suspended` = **미설정**(키 부재). 둘 다 실행 전 확인. 이 프로브는
  주문을 내지 않으므로 둘 중 어느 것도 이 실행의 전제는 아니지만, 캠페인 README
  관례대로 적는다.

| 아티팩트 | 종목 | KST | 판정 |
|---|---|---|---|
| `P-VL-20261008T010644Z.json` | `A05610` (**당일 만기**) | 10:06:51 | L1·L2·L3 PASS · L4·L5 관측 |
| `P-VL-20261008T010822Z.json` | `A05611` (차근월) | 10:08:27 | L1·L2·L3 PASS · L4·L5 관측 |

두 아티팩트 모두 `errors` 0 · `provenance_class`
`P-VL-20261008T010644Z.json:provenance_class=MEASURED` ·
`P-VL-20261008T010822Z.json:provenance_class=MEASURED` ·
`P-VL-20261008T010644Z.json:mode=live` · `P-VL-20261008T010822Z.json:mode=live` ·
`P-VL-20261008T010644Z.json:skips=[]` · `P-VL-20261008T010822Z.json:skips=[]` ·
`P-VL-20261008T010644Z.json:args.confirm=true` ·
`P-VL-20261008T010822Z.json:args.confirm=true`.

### ⚠ L2 판정은 **쓰여 있는 규칙**으로 읽는다 (아티팩트의 PASS 를 그대로 쓰지 않는다)

두 아티팩트는 `P-VL-20261008T010644Z.json:measurements.leg_verdicts.L2=PASS` 를 담고
있다. **그 PASS 는 판정 순서 결함의 산물이다** — 프로브가 창 검사보다 일치를 먼저
보아서, 확대 불가 창 **밖**의 1단계 재현이 PASS 로 채점됐다. 지배 텍스트 셋이 모두
반대로 적고 있다(설계 v2 §5 「①샘플에서」 · 런북 §5.9 레그 표 「창 밖 =
`OBSERVATION_ONLY_NO_VERDICT`」 · 프로브 `disposition_token` 자신의 docstring). 결함은
**PR #882** 에서 고쳤다(창을 먼저 본다 + 창 밖 일치 레드 증명).

두 샘플 모두 창 **밖**이다 —
`P-VL-20261008T010644Z.json:measurements.l1_sample_window.inside_no_escalation_window=false`
· `P-VL-20261008T010644Z.json:measurements.l1_sample_window.expected_stage_is_determined=false`
· `P-VL-20261008T010822Z.json:measurements.l1_sample_window.inside_no_escalation_window=false`.

따라서 **아티팩트는 기록이므로 고치지 않고**, 프로파일에 착지하는 band 축은
`BAND_SEMANTICS_L2_STAGE_RECORDED_ONLY` 다 —
아티팩트가 적은 `…OBSERVED_ON_MOCK` 토큰
(`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.proposed`)이 아니다.
왜 그래야 하는가: 창 밖에서는 2/3단계 band 가 **적법**하므로 1단계 일치는 제56조와
**양립**하지만 **판별하지 않는다**.

## 0. 이 실행이 **확립한 것** (가장 중요한 것부터)

### 0.1 ⭐ 관측된 band 경계는 **0.05 격자 위에 없다** — 배포 정책 `tick_size: 5` 가 이 잎에 맞지 않는다는 **브로커 측 정황**

이것은 설계가 기대하지 않았던 산출이다. 설계 §2.0 은 정책의 0.05 가 full 의 값이라는 것을
**규정 문서**로만 말할 수 있었다. 이 실행은 **브로커가 공표한 band 자체**로 같은 방향의
정황을 준다.

**가정 없는 형태가 가장 강하다 — 후보 집합도, 재계산도 필요 없다.** 관측된 band 경계
**네 값 전부가 0.05 의 배수가 아니다**:

| 관측 band 경계 | ÷ 0.05 | 0.05 의 배수? | ÷ 0.02 | 0.02 의 배수? |
|---|---|---|---|---|
| 1159.18 (`A05610` 상한) | 23183.6 | 아니오 | 57959 | 예 |
| 987.46 (`A05610` 하한) | 19749.2 | 아니오 | 49373 | 예 |
| 1162.72 (`A05611` 상한) | 23254.4 | 아니오 | 58136 | 예 |
| 990.48 (`A05611` 하한) | 19809.6 | 아니오 | 49524 | 예 |

제56조는 상·하한가를 **호가가격단위로 내림/올림**한 값으로 정의한다. 0.05 체제라면 네 값이
0.05 격자 위에 있어야 하는데 **하나도 없다**. 관측값 여덟 개는 전부 0.02 의 배수다.

⚠ **기준가는 이 논거에 쓰지 않는다 — 갈리기 때문이다.** `A05610` 의 1073.32 는 0.05 의
배수가 아니지만 `A05611` 의 1076.60 **은** 0.05 의 배수다(= 21532). 판별하는 것은 **band
경계 네 값**이다.

참고로 산식을 두 틱 후보로 재계산하면 같은 방향이 나온다. ⚠ **아래 두 행은 이 README 의
산술이고 어느 아티팩트에도 들어 있지 않다**(관측값은 「관측」 열뿐이다):

| 틱 (계산) | 상한가 (계산) | 하한가 (계산) | 관측과 일치? |
|---|---|---|---|
| **0.02** (미니 등록값) | **1159.18** | **987.46** | **일치** |
| 0.05 (배포 정책 `tick_size: 5`) | 1159.15 | 987.50 | 불일치 |

⚠ 이 재계산은 **두 틱 후보 중에서만** 말한다. 위 격자 논거와 달리 후보 집합을 전제한다.
또 `A05610` 기준가 1073.32 자체가 0.05 의 배수가 아니므로(제55조제4항은 기준가를
호가가격단위로 조정한다) 0.05 행은 애초에 정합하지 않는 전제 위의 계산이다.

관측값(위 표의 「관측」 쪽):
`P-VL-20261008T010644Z.json:measurements.l1_quote_fields.values.futs_sdpr=1073.32` ·
`P-VL-20261008T010644Z.json:measurements.l1_quote_fields.values.futs_mxpr=1159.18` ·
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

**해석(측정 아님)**: band 경계가 0.05 격자 위에 없고 0.02 격자 위에 있으므로, 거래소가 이
상품의 호가가격단위를 0.02 로 쓰고 있다고 읽는 것이 자연스럽다. 다만 이 실행은 band
**값**을 관측한 것이고 브로커가 호가가격단위를 **공표**한 것은 아니다 — 정확히는 **이
프로브가 그 TR 에서 호가단위 필드를 읽지 않는다**(`_leg_l1` 은 다섯 가격 필드만 추출하고
출력 목록을 열거하지 않는다). 「그 TR 에 호가단위 필드가 없다」는 **이 실행이 뒷받침하지
않는 더 센 주장**이고, 프로파일의 같은 블록도 「선물 경로에 같은 필드가 있는지 **미확인**」을
그대로 유지한다(주식 TR 은 `aspr_unit` 을 공표한다). 정책을 2 로 고치는 처분은 설계 §6
웨이브의 운영자 항목이다.

⚠ **만기일 단서(§4 1 재진술)**: 위 `A05610` 수치는 **당일 만기** 잎의 것이다. 그래서
결론을 그 잎 하나에 걸지 않고 차근월 `A05611` 에서 **독립 재현**했다 — 격자 논거의 네 값 중
둘이 `A05611` 것이다.

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

판정 토큰(두 아티팩트 **각각** 인용한다 — 「둘 다」를 한쪽만 인용해 적지 않는다):
`P-VL-20261008T010644Z.json:measurements.leg_verdicts.L4=OBSERVATION_ONLY_NO_VERDICT` ·
`P-VL-20261008T010644Z.json:measurements.leg_verdicts.L5=OBSERVATION_ONLY_NO_VERDICT` ·
`P-VL-20261008T010822Z.json:measurements.leg_verdicts.L4=OBSERVATION_ONLY_NO_VERDICT` ·
`P-VL-20261008T010822Z.json:measurements.leg_verdicts.L5=OBSERVATION_ONLY_NO_VERDICT`.

- **L4 하한가 경계** — 수락. `UNIT_PRICE`
  `P-VL-20261008T010644Z.json:measurements.l4_psbl_at_lower_limit.unit_price_sent=987.46` →
  `P-VL-20261008T010644Z.json:measurements.l4_psbl_at_lower_limit.rt_cd=0` ·
  `P-VL-20261008T010644Z.json:measurements.l4_psbl_at_lower_limit.ord_psbl_qty=4`.
  `A05611` 도 수락 —
  `P-VL-20261008T010822Z.json:measurements.l4_psbl_at_lower_limit.unit_price_sent=990.48` ·
  `P-VL-20261008T010822Z.json:measurements.l4_psbl_at_lower_limit.rt_cd=0` ·
  `P-VL-20261008T010822Z.json:measurements.l4_psbl_at_lower_limit.ord_psbl_qty=4`.
- **L5 상한가 + 1틱 (band 밖)** — **역시 수락**. `UNIT_PRICE`
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.unit_price_sent=1159.20` →
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.rt_cd=0` ·
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.msg_cd=20310000` ·
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.ord_psbl_qty=4`.
  `A05611` 에서도 같다 —
  `P-VL-20261008T010822Z.json:measurements.l5_psbl_above_upper_limit.unit_price_sent=1162.74` ·
  `P-VL-20261008T010822Z.json:measurements.l5_psbl_above_upper_limit.rt_cd=0` ·
  `P-VL-20261008T010822Z.json:measurements.l5_psbl_above_upper_limit.ord_psbl_qty=4`.
- **`bass_idx` 에코는 레그 불변이다** — L5 만의 성질이 아니다. 세 레그 모두 보낸
  `UNIT_PRICE` 를 되돌려준다: L3
  `P-VL-20261008T010644Z.json:measurements.l3_psbl_at_touch.bass_idx=1065.56000000` · L4
  `P-VL-20261008T010644Z.json:measurements.l4_psbl_at_lower_limit.bass_idx=987.46000000` · L5
  `P-VL-20261008T010644Z.json:measurements.l5_psbl_above_upper_limit.bass_idx=1159.20000000`.
  L5 아래에만 적으면 「band 밖이라서 에코했다」로 오독된다 — **그 필드는 언제나 에코한다.**

**해석(측정 아님)**: 주문가능 **조회면**은 band 밖 가격을 거르지 않는 것으로 보인다. 이것은
**조회 거부 표면의 부재**에 대한 관측이고, 같은 가격으로 **주문**을 넣었을 때 무엇이 일어나는지는
말하지 않는다(그 관측은 이 프로브의 GET-only 범위 밖 — 설계 §4.3 · §7 ④).

## 2. 이 실행이 **확립하지 못한 것**

- **KIS 측 호가수량한도.** GET 으로 관측 불가. 규정값은 별표 17의2 제1호의 정규
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_row.regular_session_contracts=10000`
  · 야간
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_row.night_session_contracts=5000`
  · 유동성관리상품 지정 시 정규
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_row.liquidity_managed_regular_contracts=1000`
  · 같은 경우 야간
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_row.liquidity_managed_night_contracts=500`
  이고, 이것은 **맥락**이다 — 출처
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_row.source=업무규정 제71조 → 시행세칙 제61조제1항 → 별표 17의2 제1호 (별표 최종개정 2025-05-29)`.
  회원 하향(제61조제3항)·거래소 변경(제61조제1항 단서)·위탁계좌 비적용 단서는
  `P-VL-20261008T010644Z.json:measurements.resolved_instrument.krx_quantity_limit_row.caveats=회원은 시행세칙 제61조제3항으로 더 낮게 정할 수 있고, 거래소는 제61조제1항 단서로 변경할 수 있다. 공표 규정값이지 불변식이 아니다. 누적호가수량한도(제61조제2항)는 위탁계좌에 적용되지 않으므로 여기 없다.`
  에 함께 있다.
  ⚠ 축약(`…`)으로 적으면 **검사기가 보지 못한다** — 토큰은 전부 풀어서 적는다.
- **`ord_psbl_qty` 의 선행 관측이 이 레포에 없다.** 아티팩트가 그 사실을 들고 있다 —
  `P-VL-20261008T010644Z.json:measurements.cannot_establish.no_prior_ord_psbl_qty_observation`
  (P-R5-PRE 08-03 은 예수금 레그 `CTRP6550R` 에서 **그 전에** ABORT 했다). 즉 이 실행의
  `ord_psbl_qty=4` 는 그 필드의 **첫 관측**이고, 비교 기준선이 없다.
- **기준가격이 「직전 거래일 정산가격」인지.** 두 샘플 모두 `futs_sdpr` 와 `futs_prdy_clpr` 가
  **같아서** 판별되지 않았다 —
  `P-VL-20261008T010644Z.json:measurements.l1_basis_price_distinguishable.differ=false` ·
  `P-VL-20261008T010644Z.json:measurements.l1_basis_price_distinguishable.distinguishes_settlement_from_close=false`
  (`A05611` 도 `P-VL-20261008T010822Z.json:measurements.l1_basis_price_distinguishable.differ=false`).
  **같다는 것은 규정이 틀렸다는 증거가 아니다** — 이 샘플이 그 질문에 무정보라는 뜻이다.
  두 잎 모두 분기월이 아니므로 제55조제1항 단서는 적용되지 않는다
  (`P-VL-20261008T010644Z.json:measurements.l1_basis_price_distinguishable.quarterly_mini_leaf=false`).
- **2/3단계 확대 의미론.** 미관측. ⚠ 앞 판은 이것을 「**그날** 확대는 없었다」로 적었는데,
  그것은 **두 순간**(10:06:51 · 10:08:27)이 허락하는 것보다 센 주장이고 아티팩트 자신의
  `not_an_interpretation` 과도 어긋난다. 정확히는 **「두 샘플 시각에는 1단계 산식이
  재현됐다」** 뿐이다 — 그 사이와 그 밖의 시각은 관측되지 않았다. 두 샘플 모두 확대 불가
  창(08:45~09:00) **밖**이고
  (`P-VL-20261008T010644Z.json:measurements.l1_sample_window.inside_no_escalation_window=false` ·
  `P-VL-20261008T010644Z.json:measurements.l1_sample_window.expected_stage_is_determined=false`)
  그래도 1단계가 관측됐다. 즉 **그날 확대는 없었다**는 사실만 기록된다.
- **설계 §4.2 의 ① 샘플(08:50±3분).** 오늘은 찍지 못했다 — 실행 시각이 10:06 이었다. 이 증거는
  ② 샘플 전용이고, L2 PASS 는 「1단계가 재현됐다」이지 「1단계가 **보장된** 창에서 재현됐다」가
  아니다.
- **band 의 런타임 공급.** 이 프로브는 값을 관측할 뿐이다(설계 §6).

## 3. 처분 — P0-2 복합 토큰

**아티팩트가 파생한 토큰**(두 런 동일):
`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.proposed=BAND_SEMANTICS_OBSERVED_ON_MOCK__TICK_FROM_REGULATION_NOT_BROKER__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED`
· `P-VL-20261008T010822Z.json:measurements.p02_disposition_proposal.proposed=BAND_SEMANTICS_OBSERVED_ON_MOCK__TICK_FROM_REGULATION_NOT_BROKER__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED`.

**프로파일에 착지한 토큰**(band 축만 다르다):

```
BAND_SEMANTICS_L2_STAGE_RECORDED_ONLY__TICK_FROM_REGULATION_NOT_BROKER__QUANTITY_CAP_RULE_VALUE_BROKER_UNCONFIRMED
```

⚠ **왜 다른가** — 위 「L2 판정은 쓰여 있는 규칙으로 읽는다」 절. 두 샘플이 확대 불가 창
**밖**이므로 1단계 일치는 판별하지 않고, 아티팩트의 `L2=PASS` 는 창보다 일치를 먼저 본
**판정 순서 결함**(PR #882 에서 수정)의 산물이다. **아티팩트는 기록이라 고치지 않는다.**

토큰은 판정에서 **파생**된다(한 단어 상태는 프로파일 어휘에 없다 — 설계 v2 §5):
`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.derived_from.L1=PASS` ·
`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.derived_from.L2=PASS`
(= 결함이 만든 값). L1 이 PASS 하지 않았다면 band 축은 `NOT_OBSERVED` 가 되고 tick 축은
`TICK_UNCORROBORATED` 가 된다.

미확립 축은 아티팩트가 열거한다 —
`P-VL-20261008T010644Z.json:measurements.p02_disposition_proposal.still_unestablished[0]=the structural 호가수량한도 (별표 17의2) — regulation value only, broker-side limit unconfirmed`.

## 4. 실행 조건 — 숨기지 않는 사실 셋

### 4.1 `A05610` 은 당일 만기다

호스트 read-model 이 그렇게 적고 있었다 — `roll_state=expired` · `days_to_expiry=0` ·
`new_entry_front_allowed=false` · `expiry_date=2026-10-08`. 만기일의 시세·band 는
최종결제 거동을 반영할 수 있으므로 이 잎의 수치를 **평시 값으로 읽지 말 것**. 차근월
`A05611`(`next_expiry_date=2026-11-12`)을 같은 세션에서 찍은 이유가 그것이고, §0.1 의
격자 논거는 네 값 중 둘이 `A05611` 것이라 **두 잎에서 독립 재현**된다.

### 4.2 차근월 코드는 가정하지 않고 read-model 에서 읽었다

`next_symbol=A05611`. **재현**(§4.4 의 DB 질의와 같은 규율 — 아티팩트가 아닌 값에는
재현 경로를 붙인다):

```bash
redis-cli -n 1 HGETALL futures:contract:latest
#   product mini | front_symbol A05610 | next_symbol A05611
#   expiry_date 2026-10-08 | next_expiry_date 2026-11-12 | days_to_expiry 0
#   roll_state expired | new_entry_front_allowed false
#   source calendar | asof_ts 2026-10-08T08:00:00.536853
```

⚠ `HGETALL` 이다 — 이 키는 **해시**이고 `GET` 은 `WRONGTYPE` 을 준다.

### 4.3 `.env.mock` 앱키는 상주 paper 세션과 같다 — 그리고 런북 규칙을 **벗어났다**

**규칙을 쓰여 있는 대로 적는다.** 런북 §5.9 선행조건 3 과 설계 §4.2 는 「키가 같으면 토큰
1분 재발급 한도(N-15)를 피해 **09:20 샘플 하나만** 찍는다」고 말한다.

**실제로 한 것:** `--confirm` 런을 **두 번** 돌렸다(`A05610` 10:06:51 · `A05611` 10:08:27).
즉 **「하나만」을 글자대로 지키지 않았다.**

**왜 그래도 N-15 에 걸리지 않았는가:** 두 런이 **같은 창**의 샘플이고 프로브 전용 토큰
캐시(`results/.token_cache`)를 공유하므로 **토큰 발급은 1회**였다 — 두 번째 런은 캐시된
토큰을 재사용했다. N-15 가 막는 것은 **1분 내 재발급**이고, 발급이 한 번이면 그 한도에
닿지 않는다. 또 상주 세션의 토큰은 08:45 에 받은 것이고 KIS 는 신규 발급으로 기존 토큰을
revoke 하지 않는다(N-15 관측).

**왜 두 번 돌렸는가:** `A05610` 이 당일 만기여서(§4.1) 그 잎 하나로는 결론을 세울 수 없었다.
두 번째 런은 **다른 창의 두 번째 샘플이 아니라 같은 창의 다른 종목**이다 — 설계 §4.2 가
말하는 ①/② 두 샘플 중 **②만** 가진 것은 여전하다.

**설계 §4.2 ① 샘플을 못 찍은 이유는 시각이 아니라 규칙이다.** 실행이 10:06 이었으므로
08:50±3분 창은 지나 있었지만, **키가 같은 날 ①과 ②를 둘 다 찍는 것은 §4.2 가 애초에
금지한다**. 앞 판의 README 가 이것을 「시각 때문」으로만 적은 것은 부정확했다.

**앱키 지문** `cf6e5f9480ad` (sha256[:12], 비가역). ⚠ **이 값은 운영자 증언이고 이 실행의
아티팩트에는 없다** — 상주 세션 래퍼가 같은 파일(`$MAIN/.env.mock`)을 소싱한다는 호스트
파일 사실에서 나왔다. 리뷰어가 증거만으로 재확인할 수 없으므로, 프로브가
`credentials.app_key_fingerprint` 를 **직접 적도록** 고쳤다(**PR #882**) — 다음 런부터는
아티팩트가 그 비교를 들고 있다. 계좌는 마스킹만 기록된다 —
`P-VL-20261008T010644Z.json:credentials.account_masked=60******03` ·
`P-VL-20261008T010644Z.json:credentials.account_fingerprint=46c39c54d3bb`.

## 4.4 설계 §8 3단계의 부수 과제 — `STAGE_DENIED` 2:1 매핑 해소

설계 §1 「소비 1」 행이 10-07 세션에서 `STAGE_DENIED` 행 5,020 과 사유 문자열 행 2,510 의
**2:1 매핑**을 미해소로 남겨 두었다. 상주 paper 세션의 evidence store 를 읽어 그 구조를
확인했다. **이 수치는 아티팩트가 아니라 DB 스냅샷이므로 인용 토큰을 달지 않는다** — 대신
**판별하는** 질의와 스냅샷 좌표를 적는다.

- 대상: `~/.local/state/tos/paper-data/A05610/evidence.sqlite3` (append-only · 읽기 전용 열기)
- 스냅샷 경계: **모든 절에 `seq<=164200`** · `MAX(seq)` = 164200 · `COUNT(*)` = 164201
  (2026-10-08 10:18:33 KST)

| 질의 | 결과 |
|---|---|
| A. 사유 문자열 행을 `kind` 로 쪼갬 | `FLOW_HALTED` **5,582** · `EVENT_CONSUMED` **행 없음** |
| B. `%STAGE_DENIED%` 를 `kind` 로 쪼갬 | `EVENT_CONSUMED` 5,582 · `FLOW_HALTED` 5,582 (합 11,164) |
| C. `FLOW_HALTED` 인데 사유가 **없는** 행 | **0** |
| D. `EVENT_CONSUMED` 인데 사유가 **있는** 행 | **0** |
| E. 사유 행의 `COUNT(DISTINCT event_id)` | **5,582** |
| F. `%STAGE_DENIED%` 행의 `COUNT(DISTINCT event_id)` | **5,582** |

**이제 세 한계 수치가 아니라 교차표가 말한다.** C 와 D 가 둘 다 0 이므로 「사유는
`FLOW_HALTED` 에만 있고 누락은 없다」가 **직접 측정**됐다 — 같은 주변합을 만드는 반대
배치(사유가 양쪽에 흩어진 경우)는 C·D 가 0 이 아니게 된다. E = F = 5,582 는 두 행이 **같은
`event_id` 를 공유**함을 보이므로, 구조는 **「1 거부 → 2 행」**이다.

```bash
DB="$HOME/.local/state/tos/paper-data/A05610/evidence.sqlite3"
sqlite3 "file:$DB?mode=ro" "
SELECT 'A '||kind, COUNT(*) FROM entries
  WHERE seq<=164200 AND payload_json LIKE '%quantity constraint is incomplete%' GROUP BY kind
UNION ALL SELECT 'B '||kind, COUNT(*) FROM entries
  WHERE seq<=164200 AND payload_json LIKE '%STAGE_DENIED%' GROUP BY kind
UNION ALL SELECT 'C flow_halted_missing_reason', COUNT(*) FROM entries
  WHERE seq<=164200 AND kind='FLOW_HALTED' AND payload_json LIKE '%STAGE_DENIED%'
    AND payload_json NOT LIKE '%quantity constraint is incomplete%'
UNION ALL SELECT 'D event_consumed_with_reason', COUNT(*) FROM entries
  WHERE seq<=164200 AND kind='EVENT_CONSUMED'
    AND payload_json LIKE '%quantity constraint is incomplete%'
UNION ALL SELECT 'E distinct_event_id_reason',
  COUNT(DISTINCT json_extract(payload_json,'\$.payload.event_id')) FROM entries
  WHERE seq<=164200 AND payload_json LIKE '%quantity constraint is incomplete%'
UNION ALL SELECT 'F distinct_event_id_denied',
  COUNT(DISTINCT json_extract(payload_json,'\$.payload.event_id')) FROM entries
  WHERE seq<=164200 AND payload_json LIKE '%STAGE_DENIED%'
UNION ALL SELECT 'G max_seq', MAX(seq) FROM entries WHERE seq<=164200
UNION ALL SELECT 'H row_count', COUNT(*) FROM entries WHERE seq<=164200;"
```

⚠ **설계의 5,020 과 직접 비교하지 말 것 — 술어가 다르다.** 설계는
`CANDIDATE_COMMAND_CONSTRUCTION` 계열을 셌고 이 README 는 `%STAGE_DENIED%` 를 셌다. 이
store 에서 두 술어는 **같은 11,164 행**을 고른다(`%CANDIDATE_COMMAND_CONSTRUCTION%` =
11,164, 그중 `%STAGE_DENIED%` 와의 교집합도 11,164)이므로 여기서는 구별되지 않는다. 비교
가능한 것은 **비율(2:1)과 구조**이고, 절대값은 스냅샷이 다르다.

⚠ **두 가지 한계를 숨기지 않는다.** ① store 는 **지금도 기록 중**이다 — 같은 질의를 3분
간격으로 두 번 돌렸을 때 5,580 → 5,582 로 늘었다. 위 표는 `seq<=164200` 으로 **경계가
박힌** 수치이고 「현재값」이 아니다. ② 이 디렉터리는 **결제월 단위**(`paper-data/A05610`)라
10-06 genesis 이후 전 세션을 담고 있고, payload 최상위에 벽시계 필드가 없어
(`masked_keys`·`payload` 뿐) **10-07 하루만 분리한 수치가 아니다**.

## 5. 재현

```bash
git worktree add --detach <path> origin/main          # 36afc379
install -m 600 <primary>/.env.mock <path>/.env.mock   # 600, 실전 env 는 쓰지 않는다
cd <path> && set -a && . ./.env.mock && set +a

# guard_checkout 세 조건 (실행 전 확인)
git status --short              # 빈 출력이어야 한다
git rev-parse --abbrev-ref HEAD # HEAD (detached)
git merge-base --is-ancestor HEAD origin/main

# 라이브 게이트
grep -E '^\s*enabled:' config/futures_live.yaml      # false
redis-cli -n 1 EXISTS futures:live:suspended         # 0

# dry-run 을 종목마다 하나씩 (호스트에서 둘 다 돌렸다)
python -m tools.broker_probes.run P-VL --asset futures --symbol A05610
python -m tools.broker_probes.run P-VL --asset futures --symbol A05611

# 그 다음 --confirm (GET 4회/런)
python -m tools.broker_probes.run P-VL --asset futures --symbol A05610 --confirm
python -m tools.broker_probes.run P-VL --asset futures --symbol A05611 --confirm

python tools/tos_evidence_citation_check.py docs/broker-profiles/evidence/2026-10-08-cp3-venue-limits/README.md
```

dry-run 아티팩트 2건은 `mode: dry-run` 이라 런북 §6.2 를 통과하지 못하므로 증거
디렉터리에 **복사하지 않았다** — 네트워크 접촉이 없어 관측이 아니다.

아티팩트는 `tools/broker_probes/results/`(gitignore)에 쓰이고 이 디렉터리로 복사된다.
`approval_status` 는 둘 다 `UNAPPROVED_CANDIDATE` —
`P-VL-20261008T010644Z.json:approval_status=UNAPPROVED_CANDIDATE` ·
`P-VL-20261008T010822Z.json:approval_status=UNAPPROVED_CANDIDATE`. 프로파일 기입은 **초안
문서(`-draft.yaml`)에 대한 저작 행위**이고, 값을 승인 대상 INSTANCE 로 올리는 것은 P0-2
승인 사슬이 따로 있다(설계 §8 1단계의 운영자 승인은 **여전히 열려 있다** — 이 PR 은 초안과
증거만 움직인다).

## 6. 안전 — 이 실행이 건드리지 않은 것

- **주문 0건.** 프로브는 GET 전용이고 모듈에 주문 경로가 없다. 구조적 통제는 아티팩트가
  적는다 — `P-VL-20261008T010644Z.json:measurements.structural_controls[0]` ·
  `P-VL-20261008T010644Z.json:measurements.structural_controls[1]` ·
  `P-VL-20261008T010644Z.json:measurements.structural_controls[4]`.
- **실전 계좌·실전 자격증명 미사용.** 환경은 둘 다
  `P-VL-20261008T010644Z.json:environment=MOCK_VTS` ·
  `P-VL-20261008T010822Z.json:environment=MOCK_VTS`, base URL 은
  `P-VL-20261008T010644Z.json:credentials.base_url=https://openapivts.koreainvestment.com:29443`.
- **비밀 미기록.** 앱키·시크릿은 존재 여부만 적힌다 —
  `P-VL-20261008T010644Z.json:credentials.app_key_present=true` ·
  `P-VL-20261008T010644Z.json:credentials.app_secret_present=true`. 계좌는 마스킹만.
  `.env.mock` 은 gitignore 이고 이 PR 에 들어 있지 않다.
