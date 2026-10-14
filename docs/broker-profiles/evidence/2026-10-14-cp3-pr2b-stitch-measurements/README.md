# CP-3 PR-2b 측정 S1a·S1b — 월물 교차 시드가 **남긴** 것 (2026-10-14)

- 계획: `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md` §3.2a 「측정 S1a·S1b」.
- 선행 증거: `docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-expired-contract/README.md`
  (전제 실측 — `c_x100` 344 · 스프레드 폭 118 · 15:19 세션 끝) ·
  `docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md` (PR-1, 10-12 수집).
- 구현: PR #900 의 `tools/tos_cp3/stitch.py` · `produce_fields.load_window(stitch_manifest=)` ·
  `tools/tos_cp3/live_producer/stitch_seed.py`.
- **게이트가 아니다** (`CP3-PR2B-summary.json:gate=false`,
  `CP3-PR2B-summary.json:gate_note=plan §3.2a: a measurement, not a gate; a flip is reported, not blocking`).
  뒤집힘이 나오면 운영자에게 올린다.
- 실행: 2026-10-14, 오프라인 재계산
  (`CP3-PR2B-summary.json:method=offline recomputation over recorded raw responses`).
  **주문 0 건** (`CP3-PR2B-summary.json:orders=0`), **GET 6 회**
  (`CP3-PR2B-summary.json:requests=6`) — 그 6 회는 아무도 기록해 두지 않은 완료 세션 하나뿐이다
  (§5). TR 은 PR-1 과 같은 조회 TR (`CP3-PR2B-summary.json:tr_id=FHKIF03020200`).
- **후속(2026-10-14 15:50 KST, 이 문서의 두 번째 판).** 첫 실행 때 열려 있던 **10-14 세션이 닫힌 뒤**
  같은 조회 클라이언트로 GET `CP3-PR2B-summary.json:requests_followup=6` 회를 더 쏴
  (`CP3-PR2B-summary.json:requests_followup_day=2026-10-14`) S1b 의 **완전한** 비교 점을 채웠다.
  합계 GET `CP3-PR2B-summary.json:requests_total=12` 회 · 주문은 여전히 0 건. 두 실행의 역할 구분은
  `CP3-PR2B-summary.json:requests_note=requests counts the first run's GETs (2026-10-13); requests_followup counts this follow-up PR's (2026-10-14); requests_total is their sum. Both read one completed session each, GET-only, from a detached worktree of origin/main.`
  **`CP3-PR2B-S1a.json` 은 바이트 그대로다** — 새 원천은 `(A05611, 2026-10-14)` 만 더하고 S1a 가 읽는
  `(월물, 날)` 중 어느 것도 바꾸지 않는다(§5 의 `cmp` 로 확인).

## 0. 답

| 측정 | 답 |
|---|---|
| **S1a** `c` 민감도 (경로 a) | `CP3-PR2B-summary.json:answer_s1a=no flip: 0 of 118 perturbations across the measured spread range move stall_ok or reversal_ok on 2026-10-12 09:00-09:14` |
| **S1b** ATR 대체 (경로 b) | `CP3-PR2B-summary.json:answer_s1b=1 bar of 993: substituting the splice session's own contract changes hi_vol on exactly one in-entry-window bar across 2026-10-12, 10-13 and 10-14; none of them on 10-14, the plan's complete comparison point, where the percentile reference is identical in both frames` |
| **S1b** 의 **완전한** 비교 점 (10-14) | `CP3-PR2B-summary.json:answer_s1b_complete_day=2026-10-14: 0 of 331 in-entry-window bars change hi_vol and the percentile reference differs on 0 of them, although the substitution changes ALL 118 ATRs 10-08 still contributes to that window — none of those 118 reaches the rank the 90th percentile is read at, in either frame, whereas on 2026-10-12 and 10-13 they do` |

그리고 **계획의 구조 주장 하나가 모호했음이 드러나 명확해졌다** — §3.2a S1a 의 「다른 필드·다른 날은
구조상 움직이지 않으므로 세지 않는다」는 **창(09:00–09:14) 안으로 읽으면 참**이고 대상일 전체로 읽으면
아니다(§3). 독립 리뷰 판정도 「거짓이 아니라 범위가 모호」였고, 계획 문구는 그 판정대로 PR #900 에서
명확화했다.

## 1. S1a — `c` 를 스프레드 폭만큼 흔들었다. 아무것도 뒤집히지 않는다

대상 `CP3-PR2B-S1a.json:target_day=2026-10-12`, 창
`CP3-PR2B-S1a.json:window_kst=09:00-09:14`
(`CP3-PR2B-S1a.json:window_bars=15` 봉). 프레임은 생산자가 그날 만들 바로 그 접합 프레임이고
직전 월물 시드 일자는 `CP3-PR2B-S1a.json:seed_days_previous_contract[0]=2026-10-02` ~
`CP3-PR2B-S1a.json:seed_days_previous_contract[3]=2026-10-08` 넷이다
(창 충족 규칙이 고른 날들 — 10-01 은 필요 없었다).

- 채택 상수 `CP3-PR2B-S1a.json:c_x100=344`, 흔든 폭
  `CP3-PR2B-S1a.json:spread_range_x100=118` (전제 실측 §6 의 [226, 344] 범위).
- **브래킷은 양쪽이다** (`CP3-PR2B-S1a.json:bracket_is_two_sided=true`):
  `CP3-PR2B-S1a.json:bracket_x100[0]=226` ~ `CP3-PR2B-S1a.json:bracket_x100[1]=462`.
  전제 실측이 넘긴 것은 **폭 118** 하나였고 브래킷 선택은 구현의 몫이라 적혀 있다. 한쪽
  (`[c−118, c]`)으로 좁히면 덜 보수적이고 — 그 문서 「관측 2」가 천장 344 를 마지막 1 분이
  혼자 만들었음을 보였으므로 — **위쪽도 돌린다**. 오프라인 재계산이라 비용 차이는 없다.
- 격자 간격 `CP3-PR2B-S1a.json:perturbation_step_x100=2` (미니 틱 0.02)로
  `CP3-PR2B-S1a.json:perturbations_run=118` 번 전부 돌렸다.

**결과: `CP3-PR2B-S1a.json:flips_total=0`** ·
`CP3-PR2B-S1a.json:offsets_with_any_flip=[]` ·
`CP3-PR2B-S1a.json:flips_max_at_one_offset=0`.

### 1.1 ⚠ 「15 봉 중 0 건」이 아니다 — **움직일 수 있는 봉은 하나**다

이 0 을 그대로 읽으면 과대평가다. 창의 15 봉 중 `stall_ok`·`reversal_ok` 가 `c` 에 **반응할 수
있는** 봉은 `CP3-PR2B-S1a.json:window_bars_that_can_flip_at_all_count=1` 개
(`CP3-PR2B-S1a.json:window_bars_that_can_flip_at_all[0]=09:00`)뿐이다. 나머지 14 봉은 |z| 가
진입 문턱 미만이라 `check()` 가 4 단계에서 돌아가고, 두 필드가 **구조상** False 다 — 어떤 `c` 로도
뒤집히지 않는다. 그 14 봉을 분모에 넣으면 0/15 가 0/1 보다 안전해 보이는데, 실제로 측정된 것은
0/1 이다.

그 한 봉은 실제로 깊은 게이트를 통과한 봉이다 — `CP3-PR2B-S1a.json:baseline_window_fields.09:00.hi_vol=true` ·
`CP3-PR2B-S1a.json:baseline_window_fields.09:00.z_x1000=1943`(진입 문턱 1800 이상) ·
`CP3-PR2B-S1a.json:baseline_window_fields.09:00.stall_ok=true` ·
`CP3-PR2B-S1a.json:baseline_window_fields.09:00.reversal_ok=true`. 즉 공허한 0 이 아니라
**실제로 발화 경로에 있는 봉 하나가 흔들리지 않았다**는 관측이다.

### 1.2 여유 — 뒤집으려면 폭이 얼마나 더 커야 하나

브래킷 크기의 0 은 그 가장자리까지의 거리와 함께 읽어야 뜻이 있다. 같은 창에서 `c` 를 양방향으로
넓혀 첫 뒤집힘을 이분 탐색했다:

| 방향 | 첫 뒤집힘 Δ`c_x100` | 스프레드 폭(118)의 배수 |
|---|---|---|
| 아래 | `CP3-PR2B-S1a.json:flip_margin_x100.down=-2578` (−25.78 지수포인트) | `CP3-PR2B-S1a.json:flip_margin_in_spread_ranges=21.85` |
| 위 | `CP3-PR2B-S1a.json:flip_margin_x100.up=null` — `CP3-PR2B-S1a.json:flip_margin_up_searched_to_x100=32768`(+327.68 포인트)까지 **뒤집힘 없음** |  |

즉 이 롤에서 경로 (a) 의 잔여가 판별에 닿으려면 스프레드 변동이 관측값의 약 22 배여야 한다.
⚠ **한 날·한 롤·한 봉의 관측이다.** 다른 롤에서 같을 것이라는 주장은 하지 않는다.

## 2. S1b — 접합일을 새 월물 자신의 봉으로 바꾸면 `hi_vol` 이 한 봉 달라진다

계획 §3.2a S1b 그대로, 접합일 세션(`CP3-PR2B-S1b.json:splice_day=2026-10-08`)만 바꾼 두 프레임을
대조한다. 프레임은 **측정 전용 수기 매니페스트**이고(front month 걸음을 따르지 않는다) `c_x100`
재계산 단언을 적용하지 않는다 — 계획이 그렇게 정한다.

- A(접합) `CP3-PR2B-S1b.json:frame_a_stitched=A05610 ['2026-10-02', '2026-10-06', '2026-10-07', '2026-10-08'] + A05611 ['2026-10-12', '2026-10-13', '2026-10-14']`
- B(대체) `CP3-PR2B-S1b.json:frame_b_substituted=A05610 ['2026-10-02', '2026-10-06', '2026-10-07'] + A05611 ['2026-10-08', '2026-10-12', '2026-10-13', '2026-10-14']`

| 날 | 비교 | 진입 창 봉 | `hi_vol` 다른 봉 | 처음/마지막 | A 의 `hi_vol` True | B 의 `hi_vol` True |
|---|---|---|---|---|---|---|
| 2026-10-12 | 부분 | `CP3-PR2B-S1b.json:per_day.2026-10-12.in_entry_window=331` | **`CP3-PR2B-S1b.json:per_day.2026-10-12.hi_vol_differs=1`** | `CP3-PR2B-S1b.json:per_day.2026-10-12.first_difference_kst=09:47` | `CP3-PR2B-S1b.json:per_day.2026-10-12.hi_vol_true_stitched=115` | `CP3-PR2B-S1b.json:per_day.2026-10-12.hi_vol_true_substituted=114` |
| 2026-10-13 | 부분 | `CP3-PR2B-S1b.json:per_day.2026-10-13.in_entry_window=331` | `CP3-PR2B-S1b.json:per_day.2026-10-13.hi_vol_differs=0` | `CP3-PR2B-S1b.json:per_day.2026-10-13.first_difference_kst=null` | `CP3-PR2B-S1b.json:per_day.2026-10-13.hi_vol_true_stitched=104` | `CP3-PR2B-S1b.json:per_day.2026-10-13.hi_vol_true_substituted=104` |
| **2026-10-14** | **완전** | `CP3-PR2B-S1b.json:per_day.2026-10-14.in_entry_window=331` | **`CP3-PR2B-S1b.json:per_day.2026-10-14.hi_vol_differs=0`** | `CP3-PR2B-S1b.json:per_day.2026-10-14.first_difference_kst=null` | `CP3-PR2B-S1b.json:per_day.2026-10-14.hi_vol_true_stitched=23` | `CP3-PR2B-S1b.json:per_day.2026-10-14.hi_vol_true_substituted=23` |

합계 `CP3-PR2B-S1b.json:hi_vol_differences_total=1` / 진입 창
`CP3-PR2B-S1b.json:in_entry_window_total=993` 봉 (발행 봉 전체는
`CP3-PR2B-S1b.json:bars_compared_total=1233`).

**이것이 경로 (b) 의 본체다** — 직전 월물의 ATR 들이 `_atr_window` 를 채워 `hi_vol` 의 백분위
기준을 정하는 효과. 이 롤에서 그 대체가 바꾼 것은 **진입 창 993 봉 중 한 봉**이고, 그 한 봉이
거래로 이어지는지는 **재지 않았다**(§4).

**뒤집힘은 없다** — 계획이 「게이트가 아니다」라고 적은 그 보고다. 10-14 의 한 봉도 뒤집히지
않았고, 남은 한 봉은 PR #900 이 이미 보고한 10-12 09:47 그대로다(그 봉은 `hi_vol` 이 True→False
로 바뀐다 — 대체 프레임에서 한 봉 **덜** 통과한다).

### 2.1 `c` 와 무관함을 **확인**했다(가정하지 않았다)

계획은 「`hi_vol` 은 월물 안의 ATR 만 보므로 `c` 와 무관」이라 적는다. 그 말에 기대지 않고 두
프레임을 `CP3-PR2B-S1b.json:c_values_checked_x100=[0,226,344,462,1000]` 다섯 값으로 다시 돌려
진입 창 `hi_vol` 이 바뀌는지 셌다 — 전부 0 이다
(`CP3-PR2B-S1b.json:c_independence_check.stitched.hi_vol_differences_by_c_x100.1000=0` ·
`CP3-PR2B-S1b.json:c_independence_check.substituted.hi_vol_differences_by_c_x100.1000=0`,
비교 봉 `CP3-PR2B-S1b.json:c_independence_check.stitched.in_window_bars=993`).

### 2.2 `_atr_window` 내용과 백분위 기준값 — 「완전/부분」을 **재서** 확인했다

계획 §3.2a 가 S1b 에 함께 적으라고 한 둘이다. 창은 발행되지 않는 봉들이 채우므로 published 필드에
없다 — `produce_bars` 의 읽기 전용 관찰자로 **세트업 자신의** 평가 트레이스에서 읽는다
(`ev["vol_ref"]` 가 `_vol_reference` 가 돌려준 그 값이다; 백분위를 다시 구현하지 않는다).
창 크기 `CP3-PR2B-S1b.json:atr_window_bars=780` · 백분위
`CP3-PR2B-S1b.json:vol_percentile=90.0` · 워밍업 `CP3-PR2B-S1b.json:vol_warmup_bars=120` ·
게이트 비 `CP3-PR2B-S1b.json:min_atr_ratio=0.9` 는 전략 YAML 값 그대로다.

각 날의 **첫 기여 봉**(`CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.stitched.first_contributing_bar_kst=09:00`)에서
창 780 칸을 (월물:세션)별로 센 것:

| 날 | A(접합) 창 구성 | B(대체) 창 구성 | 창 안 직전 월물 세션(A 기준) | A 기준값 | B 기준값 | 기준값 다른 진입 창 봉 |
|---|---|---|---|---|---|---|
| 10-12 | 10-06 118 + 10-07 331 + 10-08 331, 전부 A05610 | 10-06·10-07 A05610 + **10-08 A05611** 331 | **셋** | 1.7043 | 1.7537 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-12.vol_ref_differs_in_entry_window=331` / 331 |
| 10-13 | 10-07 118 + 10-08 331 (A05610) + 10-12 331 | 10-07 A05610 + **10-08 A05611** + 10-12 | **둘** | 2.0373 | 2.0534 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-13.vol_ref_differs_in_entry_window=51` / 331 |
| **10-14** | **10-08 118 (A05610)** + 10-12 331 + 10-13 331 | **10-08 118 (A05611)** + 10-12 + 10-13 | **하나** | 2.7719 | 2.7719 | **`CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.vol_ref_differs_in_entry_window=0`** / 331 |

기준값은 `vol_ref_x10000`(1/10000 단위)로 적혀 있다 — 예
`CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.stitched.vol_ref_x10000=27719` ·
`CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.substituted.vol_ref_x10000=27719`.
칸 수는 세 날 모두 꽉 찬 `CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.stitched.bars_in_window=780`
이다(워밍업 창이 아니다).

**이 표가 계획의 「완전/부분」 분류를 측정으로 바꾼다.** 10-12 는 창 안에 직전 월물 세션이 **셋**,
10-13 은 **둘**, 10-14 는 **하나**(10-08 의 118 칸)뿐이고 — 780 − 331 − 331 = 118 — 그 하나를
바꾸는 것이 곧 **완전한** 반사실이다. 10-07·10-06 은 A05611 에서 얇아(전제 실측 §3 의 밀도 게이트)
대체할 수 없으므로 10-12·10-13 은 반사실의 일부만 바꾼 **부분** 비교다. 계획에서 읽어 옮긴 주장이
아니라 창을 센 결과다.

### 2.3 ⚠ 10-14 의 0 은 「대체가 아무것도 안 바꿨다」가 아니다

0 을 그대로 읽으면 과소평가다. 그래서 도구가 **창 안에서 대체가 실제로 바꾼 것**과 **그것이
백분위를 정하는 순위대에 있는지**를 같은 아티팩트에 함께 적는다
(`atr_window_composition.<날>.splice_day_contribution`) — 산문에만 있으면 아무도 재도출할 수 없다는
LOW-4 의 교훈을 이 수치들에도 적용한다.

10-14 창에 남은 10-08 의 칸들은 **대체하면 실제로 달라진다**:

| 10-14 창 안 10-08 기여 | 값 |
|---|---|
| 10-14 창 안 10-08 기여 칸 수 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.splice_day_bars_in_window=118` |
| 그 칸들의 구간 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.splice_day_minutes_kst=12:33-14:30` |
| `atr14` 가 **다른** 칸 | **`CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.atr_differs=118`** — 즉 **전부** |
| 최대 차이 ×10000 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.atr_max_abs_difference_x10000=900` (= 0.09) |
| A 의 `atr14` 범위 ×10000 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.atr_x10000_range_stitched=[9986,13714]` |
| B 의 `atr14` 범위 ×10000 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.atr_x10000_range_substituted=[10371,14214]` |
| 기준값(2.7719) **이상**인 칸 — A | **`CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.splice_day_bars_at_or_above_vol_ref_stitched=0`** |
| 기준값 이상인 칸 — B | **`CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.splice_day_contribution.splice_day_bars_at_or_above_vol_ref_substituted=0`** |
| 창 최대 `atr14` ×10000 | `CP3-PR2B-S1b.json:atr_window_composition.2026-10-14.stitched.window_max_atr_x10000=37886` |

즉 **10-14 의 0 은 「대체가 창을 안 건드렸다」가 아니다** — 118 칸의 `atr14` 가 **전부** 달라졌는데도
기준값이 1/10000 단위까지 같다. 이유는 그 칸들이 90 백분위(2.7719, 창 최대 3.7886) **훨씬 아래**
([0.9986, 1.3714] / [1.0371, 1.4214])에 있어 **백분위가 읽는 순위대에 한 칸도 닿지 않기** 때문이다.

그 118 칸은 10-08 의 **후반부**(12:33–14:30)다 — 창이 780 칸이라 10-12·10-13 이 662 칸을 먹고 남은
꼬리가 접합일의 뒤쪽이기 때문이다.

**이 설명이 공허하지 않다는 증거는 같은 측정의 다른 두 날이다.** 똑같은 수치를 10-12·10-13 에서
재면 10-08 기여 칸이 그 순위대에 **닿는다** — 10-12 는 기준값 이상 칸이
`CP3-PR2B-S1b.json:atr_window_composition.2026-10-12.splice_day_contribution.splice_day_bars_at_or_above_vol_ref_stitched=49`
(A)·`CP3-PR2B-S1b.json:atr_window_composition.2026-10-12.splice_day_contribution.splice_day_bars_at_or_above_vol_ref_substituted=49`
(B), 10-13 은 `CP3-PR2B-S1b.json:atr_window_composition.2026-10-13.splice_day_contribution.splice_day_bars_at_or_above_vol_ref_stitched=18`
→ `CP3-PR2B-S1b.json:atr_window_composition.2026-10-13.splice_day_contribution.splice_day_bars_at_or_above_vol_ref_substituted=23`
이고(A·B 가 **다르다**), 그래서 §2.2 의 기준값 차이가 331 → 51 → 0 으로 줄어든다. 10-14 의 0 은
측정이 둔해서 나온 0 이 아니라 **창에서 접합일이 빠져나가는 과정의 끝**이다.

다른 롤에서 접합일 후반부가 그 세션의 변동 구간이면 같은 결론을 주지 않는다. **한 롤의 관측이다.**

## 3. ⚠ 계획의 구조 주장 하나가 모호했다 — 범위를 명확히 했다

§3.2a S1a 는 「다른 필드·다른 날은 구조상 움직이지 않으므로 세지 않는다」고 적는다. **창
09:00–09:14 안으로 읽으면 참이다.** 대상일 전체로 읽으면 아니다 — 재 보니 창 **밖** 개장 봉들에서
움직인다:

- 움직인 필드: `CP3-PR2B-S1a.json:fields_that_moved_outside_the_window[0]=atr14_x100` ·
  `CP3-PR2B-S1a.json:fields_that_moved_outside_the_window[1]=vwap_reverted` ·
  `CP3-PR2B-S1a.json:fields_that_moved_outside_the_window[2]=z_x1000`
- 움직인 봉: `CP3-PR2B-S1a.json:bars_that_moved_outside_the_window_count=14` 개 —
  `CP3-PR2B-S1a.json:bars_that_moved_outside_the_window[0]=08:45` 부터
  `CP3-PR2B-S1a.json:bars_that_moved_outside_the_window[13]=08:58` 까지
- 0 이 아닌 **모든** 섭동에서:
  `CP3-PR2B-S1a.json:offsets_at_which_something_moved_outside_the_window=118`

원인은 계획 본문이 이미 적은 그것이다 — 접합 true range 는 **08:45 봉**에 있다. 계획은 거기서
「진입 창(09:00~) ATR 의 SMA14 창에 보통 들어가지 않는다」로 이어지는데, 그 말은 맞다. 다만 08:45 봉의
TR 은 **그 뒤 14 봉(08:45–08:58)** 의 ATR14 안에 있고 그 봉들은 B1a 가 **발행하는** 봉이다. 즉 원문은
판별 게이트(창 안)에 대해 참이고, 발행되는 아티팩트 전체에 대해서는 **범위가 적혀 있지 않았다**.

**처분(PR #900 에서 적용됨).** 독립 리뷰 판정은 「거짓이 아니라 범위가 모호」였고, 그 판정대로 계획
§3.2a S1a 의 괄호를 창 범위 명시 + 개장 14 봉 예외로 **명확화**했다(PR #900 의 docs 변경). **파리티와는
무관하다**: 생산자와 B1a·B2 가 같은 매니페스트를 읽으므로 세 쪽 모두 같은 값을 낸다. 이 문단이
말하는 것은 「`c` 가 다르면 아티팩트가 다르다」이지 「두 쪽이 어긋난다」가 아니다.

## 4. 이 측정이 **확립하지 못한 것**

- ~~**2026-10-14.**~~ **해소됨(이 PR).** 첫 실행 때는 그날 세션이 열려 있어 빠져 있었고, 그 공백은
  아티팩트에 `day_not_measured` 로 **적혀** 있었다. 15:45 뒤 GET 6 회로 채웠고 이 판에서는
  `CP3-PR2B-S1b.json:day_not_measured=null` ·
  `CP3-PR2B-S1b.json:day_not_measured_reason=null` 이다 — 즉 **계획이 요구한 세 날이 모두
  측정됐다**는 적극적 주장이고, 키가 없어서 null 인 것이 아니다(그 구분은
  `tests/tools/test_cp3_stitch_measure.py` 의 플래그 쌍 테스트가 지킨다).
- **다른 롤.** 2026-10 만기 하나만 봤다. S1a 의 여유 22 배도 S1b 의 1/993 도, §2.3 의 「기여 칸이
  백분위 아래」도 이 롤의 값이다.
- **거래 영향.** S1b 가 찾은 한 봉이 주문·체결로 이어지는지는 재지 않았다. `hi_vol` 은 게이트
  하나일 뿐이고 그 뒤에 |z| 문턱·정체·반전·신뢰도가 더 있다.
- **파리티.** 이 문서는 생산자와 B1a·B2 가 **같은 값을 내는지**를 재지 않는다. 그것은 PR #900 의
  테스트 5 가 확인한다(생산자 프레임 == `load_window(stitch_manifest=)` 재구성). 이 판에서 더한
  관찰자 훅도 파리티를 바꾸지 않는다 — 관찰자를 주든 안 주든 `produce_bars` 의 레코드가 바이트
  동일함을 `tests/tools/test_cp3_produce_fields.py` 가 단언한다.
- **S1a 의 다른 날.** 계획대로 10-12 만 쟀다. 10-13·10-14 의 09:00–09:14 에서는 경로 (a) 가
  구조상 0 이다(그 봉들의 `_close_window`·`prev_close` 에 직전 월물이 없다).

## 5. 재현

⚠ **분석 스크립트는 커밋했다.** PR-1·#899 는 일회성이라며 커밋하지 않았고, 그 대가가 여기서 나왔다 —
문서가 수치를 적을 수는 있어도 아무도 스크립트를 다시 쓰지 않고는 재도출할 수 없었다(독립 리뷰 LOW-4).
도구는 `tools/tos_cp3/stitch_measure.py` 이고 오프라인이며 원천 경로를 인자로 받는다. 아래 1) 이
**이 디렉터리의 `CP3-PR2B-S1a.json`·`CP3-PR2B-S1b.json` 을 바이트 그대로 재생성**한다(출력에 실행
시각이 없다 — 같은 입력이면 같은 바이트). 그 둘이 **측정**이다.

⚠ **이 명령은 커밋한 바이트를 만든 명령 그대로다 — 플래그 하나까지**(독립 리뷰 LOW-5). 첫 판에서는
`--day-not-measured`·`--day-not-measured-reason` 을 주고 돌린 결과를 커밋했는데 §5 에는 그 둘이 빠져
있어, 적힌 명령을 그대로 돌리면 `diff` 가 비지 않았다. 이 판의 커밋된 `CP3-PR2B-S1b.json` 은 그 두
플래그를 **주지 않고** 돌린 결과이고(세 날 모두 측정됐으므로 → `day_not_measured=null`), 아래 명령에도
없다. 두 `diff` 가 **모두 비어 있음**을 2026-10-14 16:28 KST 실행에서 확인했고, 같은 명령을 한 번 더
돌려(16:31 KST) 두 아티팩트가 커밋된 바이트와 **동일**함도 확인했다 — 각각 91 초·98 초.

⚠ `CP3-PR2B-summary.json` 은 도구가 만들지 않는다 — 산문 판정·GET 횟수·원천 지문처럼 측정이 아닌
값이 들어 있고 실행 시각에 따라 달라지는 항목이 없도록 손으로 조립한 것이다. 도구는 대신 같은
`--out` 에 `CP3-PR2B-sources.json`(원천 sha256 · 세션별 파싱 봉 수 · 게이트 값)을 써서 그 수치들을
기계적으로 대조할 수 있게 한다.

```bash
# 1) S1a·S1b 재계산 — 네트워크 0, 자격증명 0.
#    한가한 이 호스트에서 91~98 초(섭동 118 회 + 이분 탐색 두 방향 + c 독립성 10 회 + 창 관찰 2 회).
#    첫 판은 바쁜 호스트에서 약 8 분이었다 — 같은 입력·같은 바이트, 벽시계만 다르다.
PYTHONPATH=. .venv/bin/python -m tools.tos_cp3.stitch_measure \
  --requests ~/.local/state/tos/measure/cp3-pr2b-expired-20261014/requests.jsonl \
  --requests ~/.local/state/tos/measure/cp3-pr1-20261012/requests.jsonl \
  --requests ~/.local/state/tos/measure/cp3-pr2b-s1b-20261014/requests.jsonl \
  --requests ~/.local/state/tos/measure/cp3-pr2b-s1b2-20261014/requests.jsonl \
  --out /tmp/cp3-pr2b-s1 \
  --symbol A05611 --previous-symbol A05610 \
  --target 2026-10-12 --splice-day 2026-10-08 \
  --previous-day 2026-10-02 --previous-day 2026-10-06 --previous-day 2026-10-07 \
  --compare-day 2026-10-12 --compare-day 2026-10-13 --compare-day 2026-10-14 \
  --c-x100 344 --spread-range-x100 118 \
  --c-value-x100 0 --c-value-x100 226 --c-value-x100 344 \
  --c-value-x100 462 --c-value-x100 1000
diff /tmp/cp3-pr2b-s1/CP3-PR2B-S1a.json \
  docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-stitch-measurements/CP3-PR2B-S1a.json
diff /tmp/cp3-pr2b-s1/CP3-PR2B-S1b.json \
  docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-stitch-measurements/CP3-PR2B-S1b.json

# 1b) 그 도구 자체 (hermetic · 네트워크·자격증명 0) — 창 관찰자 훅은 produce_fields 쪽에 있다
PYTHONPATH=. .venv/bin/python -m pytest \
  tests/tools/test_cp3_stitch_measure.py tests/tools/test_cp3_produce_fields.py -q

# 2) S1b 가 필요로 한 두 조회 (각각 완료 세션 하나, GET-only, 분리 워크트리 origin/main)
#    종목 CP3-PR2B-summary.json:requests_symbol
#    1차 날짜 CP3-PR2B-summary.json:requests_day · GET CP3-PR2B-summary.json:requests 회
#         원시 행 CP3-PR2B-summary.json:requests_raw_rows
#    2차 날짜 CP3-PR2B-summary.json:requests_followup_day · GET CP3-PR2B-summary.json:requests_followup 회
#         원시 행 CP3-PR2B-summary.json:requests_followup_raw_rows
#         파싱 봉 CP3-PR2B-summary.json:requests_followup_parsed_bars
#         구간 CP3-PR2B-summary.json:requests_followup_raw_first_kst ~ CP3-PR2B-summary.json:requests_followup_raw_last_kst
#    합계 CP3-PR2B-summary.json:requests_total 회 · 주문 CP3-PR2B-summary.json:orders 건
#    두 수집 스크립트는 커밋하지 않았다. LOW-4 와 다른 경우다 — 그것들은 아무것도 도출하지 않고
#    (파싱·백분위·대조는 전부 위 1) 의 커밋된 도구 안에 있다) 브로커를 다시 읽을 뿐이라, 재현
#    대상은 스크립트가 아니라 §6 의 sha256 으로 고정된 원시 응답이다. 전송·허용목록·토큰 캐시는
#    커밋된 tools/tos_cp3/quote_client.py 그대로 쓴다.

# 3) 원천 무결성 (두 수집 디렉터리 각각)
cd ~/.local/state/tos/measure/cp3-pr2b-s1b-20261014      # 그리고 .../cp3-pr2b-s1b2-20261014
python - <<'PY'
import hashlib, json
from pathlib import Path
want = json.load(open("sha256.json"))
print([n for n, d in want.items()
       if hashlib.sha256(Path(n).read_bytes()).hexdigest() != d])   # [] 여야 한다
PY

# 4) 이 README 의 인용 검사
python tools/tos_evidence_citation_check.py \
  docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-stitch-measurements/README.md
```

## 6. 원천 — 비공개, 이 디렉터리에 없다

원천 `requests.jsonl` 셋은 호스트의 0700 디렉터리에 있고 합쳐 15 MB 가 넘어 커밋하지 않는다.
커밋한 것은 파생 JSON 셋뿐이고 인용 토큰은 그 파생 파일만 가리킨다. 지문은 커밋한
`CP3-PR2B-summary.json` 의 `source_sha256` 블록에 그대로 있다(파일명에 점이 있어 인용 토큰의
경로 문법으로는 가리킬 수 없으므로 산문 표로 적는다):

| 원천 | sha256 | 무엇 |
|---|---|---|
| `cp3-pr2b-expired-20261014/requests.jsonl` | `aa22d11fa7570212679cdc82a7d6158519a7fd80866869d78d6675741d3c6bef` | #899 전제 실측 — A05610 다섯 세션 + A05611 10-08 |
| `cp3-pr1-20261012/requests.jsonl` | `731697c65ca5afa66d183a8fd8a6270181b702185d92fdc1832fec0fafe81a12` | #896 PR-1 — A05611 10-12 장중 수집 |
| `cp3-pr2b-s1b-20261014/requests.jsonl` | `1689d76082fb830ddbb0f5f7556d46de871d9989759d4fe3bc766df5cbe95eff` | 1차 측정의 GET 6 회 — A05611 10-13 |
| `cp3-pr2b-s1b2-20261014/requests.jsonl` | `8f26e77855769e499763f38f5c39498f3f192b2aa79ff3aae7f9191fe014b09b` | **후속(이 PR)의 GET 6 회 — A05611 10-14 완료 세션** |

앞의 둘은 각 수집기의 `sha256.json` 과 재대조해 일치를 확인했다(불일치 0 건). 뒤의 둘은 각각 그
측정이 만든 것이고 각 디렉터리의 `sha256.json` 에 같은 값이 있다(네 번째도 재대조 일치).

네 번째 원천이 더하는 것은 `(A05611, 2026-10-14)` **하나뿐**이다 — 네 파일을 읽은 `load_raw_rows`
결과를 앞의 셋만 읽은 결과와 대조해 기존 `(월물, 날)` 중 행이 달라진 것이 **0 건**임을 확인했다.
그래서 S1a 는 바이트 그대로일 수밖에 없고, 실제로 `cmp` 가 동일하다고 답한다.

파생 수치의 출처가 되는 세션별 파싱 봉 수는 `CP3-PR2B-summary.json:parsed_bar_counts` 에
그대로 있다 — 예: `CP3-PR2B-summary.json:parsed_bar_counts.A05610:2026-10-08=395`(만기 월물의
짧은 접합일) · `CP3-PR2B-summary.json:parsed_bar_counts.A05611:2026-10-13=411` ·
`CP3-PR2B-summary.json:parsed_bar_counts.A05611:2026-10-14=411`(후속 수집; 원시 416 행,
08:45:00–15:45:00, 밀도 게이트 통과 — 자라는 날이 아니라 **닫힌** 세션이다).
밀도 게이트 `CP3-PR2B-summary.json:density_gate=330` · 창 요구
`CP3-PR2B-summary.json:vol_window_bars=780` 은 B1a·전략 YAML 의 값 그대로다.

## 7. 안전 — 이 측정이 건드리지 않은 것

- **주문 0 건** (`CP3-PR2B-summary.json:orders=0`). 조회 클라이언트는 PR-1 의
  `tools/tos_cp3/quote_client.py` 하나이고 GET + 이 TR + 이 경로만 허용한다;
  `shared/execution` · `probes_real_order` 는 import 하지 않는다.
- **GET `CP3-PR2B-summary.json:requests=6` 회**, PR-1 과 같은 `pace_s` 1.1 페이싱.
  목적은 `CP3-PR2B-summary.json:requests_purpose=the one completed session S1b needed that nothing had recorded`.
- **후속 GET `CP3-PR2B-summary.json:requests_followup=6` 회** — 같은 클라이언트·같은 TR·같은 페이싱.
  목적은 `CP3-PR2B-summary.json:requests_followup_purpose=the completed 2026-10-14 session — the plan's COMPLETE S1b comparison point, which the first run could not read while that session was still open`.
  수집기는 **열린 세션을 거부한다**(요청일이 오늘이고 15:45 KST 전이면 소켓을 열기 전에 중단) —
  15:41 KST 에 돌려 거부되는 것을 확인한 뒤 15:50 KST 에 실행했다
  (`CP3-PR2B-summary.json:followup_requests_started_kst=2026-10-14T15:50:27.350321+09:00`).
  합계 `CP3-PR2B-summary.json:requests_total=12` 회.
- **분리 워크트리.** 두 조회 모두 `origin/main` 의 detached 워크트리에서 돌렸다(공유 체크아웃 아님).
  후속 조회의 워크트리는 `origin/main` `d8194746` 이고, 끝난 뒤 제거했다. 자격증명은 기본 체크아웃의
  `.env.real` 을 그 워크트리에 **권한 600 으로 복사**해 썼고(경로만 기록, 값은 어디에도 남기지 않음)
  워크트리와 함께 지웠다.
- **공유 venv 미변경.** `pip install` 없이 기존 `.venv` 로만 돌렸다.
- **tenant 미기동.** paper 상주 런타임·Redis·Parquet 쓰기 경로에 손대지 않았다.
- **실전 선물 계좌 미펀딩 규칙 무관.** 조회(GET)만이고 주문 경로는 정책상 영구 차단 그대로다.
