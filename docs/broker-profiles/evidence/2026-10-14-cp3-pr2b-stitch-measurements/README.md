# CP-3 PR-2b 측정 S1a·S1b — 월물 교차 시드가 **남긴** 것 (2026-10-14)

- 계획: `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md` §3.2a 「측정 S1a·S1b」.
- 선행 증거: `docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-expired-contract/README.md`
  (전제 실측 — `c_x100` 344 · 스프레드 폭 118 · 15:19 세션 끝) ·
  `docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md` (PR-1, 10-12 수집).
- 구현: 이 PR 의 `tools/tos_cp3/stitch.py` · `produce_fields.load_window(stitch_manifest=)` ·
  `tools/tos_cp3/live_producer/stitch_seed.py`.
- **게이트가 아니다** (`CP3-PR2B-summary.json:gate=false`,
  `CP3-PR2B-summary.json:gate_note=plan §3.2a: a measurement, not a gate; a flip is reported, not blocking`).
  뒤집힘이 나오면 운영자에게 올린다.
- 실행: 2026-10-14, 오프라인 재계산
  (`CP3-PR2B-summary.json:method=offline recomputation over recorded raw responses`).
  **주문 0 건** (`CP3-PR2B-summary.json:orders=0`), **GET 6 회**
  (`CP3-PR2B-summary.json:requests=6`) — 그 6 회는 아무도 기록해 두지 않은 완료 세션 하나뿐이다
  (§5). TR 은 PR-1 과 같은 조회 TR (`CP3-PR2B-summary.json:tr_id=FHKIF03020200`).

## 0. 답

| 측정 | 답 |
|---|---|
| **S1a** `c` 민감도 (경로 a) | `CP3-PR2B-summary.json:answer_s1a=no flip: 0 of 118 perturbations across the measured spread range move stall_ok or reversal_ok on 2026-10-12 09:00-09:14` |
| **S1b** ATR 대체 (경로 b) | `CP3-PR2B-summary.json:answer_s1b=1 bar of 662: substituting the splice session's own contract changes hi_vol on exactly one in-entry-window bar across 2026-10-12 and 10-13` |

그리고 **계획의 구조 주장 하나가 반증됐다** — §3.2a S1a 의 「다른 필드·다른 날은 구조상 움직이지
않으므로 세지 않는다」는 참이 아니다(§3).

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

- A(접합) `CP3-PR2B-S1b.json:frame_a_stitched=A05610 ['2026-10-02', '2026-10-06', '2026-10-07', '2026-10-08'] + A05611 ['2026-10-12', '2026-10-13']`
- B(대체) `CP3-PR2B-S1b.json:frame_b_substituted=A05610 ['2026-10-02', '2026-10-06', '2026-10-07'] + A05611 ['2026-10-08', '2026-10-12', '2026-10-13']`

| 날 | 진입 창 봉 | `hi_vol` 다른 봉 | 처음/마지막 | A 의 `hi_vol` True | B 의 `hi_vol` True |
|---|---|---|---|---|---|
| 2026-10-12 | `CP3-PR2B-S1b.json:per_day.2026-10-12.in_entry_window=331` | **`CP3-PR2B-S1b.json:per_day.2026-10-12.hi_vol_differs=1`** | `CP3-PR2B-S1b.json:per_day.2026-10-12.first_difference_kst=09:47` | `CP3-PR2B-S1b.json:per_day.2026-10-12.hi_vol_true_stitched=115` | `CP3-PR2B-S1b.json:per_day.2026-10-12.hi_vol_true_substituted=114` |
| 2026-10-13 | `CP3-PR2B-S1b.json:per_day.2026-10-13.in_entry_window=331` | `CP3-PR2B-S1b.json:per_day.2026-10-13.hi_vol_differs=0` | `CP3-PR2B-S1b.json:per_day.2026-10-13.first_difference_kst=null` | `CP3-PR2B-S1b.json:per_day.2026-10-13.hi_vol_true_stitched=104` | `CP3-PR2B-S1b.json:per_day.2026-10-13.hi_vol_true_substituted=104` |

합계 `CP3-PR2B-S1b.json:hi_vol_differences_total=1` / 진입 창
`CP3-PR2B-S1b.json:in_entry_window_total=662` 봉.

**이것이 경로 (b) 의 본체다** — 직전 월물의 ATR 들이 `_atr_window` 를 채워 `hi_vol` 의 백분위
기준을 정하는 효과. 이 롤에서 그 대체가 바꾼 것은 **진입 창 662 봉 중 한 봉**이고, 그 한 봉이
거래로 이어지는지는 **재지 않았다**(§4).

### 2.1 `c` 와 무관함을 **확인**했다(가정하지 않았다)

계획은 「`hi_vol` 은 월물 안의 ATR 만 보므로 `c` 와 무관」이라 적는다. 그 말에 기대지 않고 두
프레임을 `CP3-PR2B-S1b.json:c_values_checked_x100=[0,226,344,462,1000]` 다섯 값으로 다시 돌려
진입 창 `hi_vol` 이 바뀌는지 셌다 — 전부 0 이다
(`CP3-PR2B-S1b.json:c_independence_check.stitched.hi_vol_differences_by_c_x100.1000=0` ·
`CP3-PR2B-S1b.json:c_independence_check.substituted.hi_vol_differences_by_c_x100.1000=0`,
비교 봉 `CP3-PR2B-S1b.json:c_independence_check.stitched.in_window_bars=662`).

### 2.2 왜 10-12·10-13 이 「부분」이고 10-14 가 「완전」인가

계획의 분류를 그대로 읽으면: 10-12·10-13 의 `_atr_window` 는 10-08 **외에** 10-07·10-06 도 담는데
그 두 날은 A05611 에서 너무 얇아(전제 실측 §3 의 밀도 게이트) 대체할 수 없다 — 그래서 반사실의
일부만 바꾼 **부분** 비교다. 10-14 에 오면 창 안에 남는 직전 월물 세션이 10-08 하나뿐이라
그것만 바꾸는 것이 **완전한** 반사실이 된다.

## 3. ⚠ 계획의 구조 주장 하나가 반증됐다

§3.2a S1a 는 「다른 필드·다른 날은 구조상 움직이지 않으므로 세지 않는다」고 적는다. 재고 보니
**움직인다**:

- 움직인 필드: `CP3-PR2B-S1a.json:fields_that_moved_outside_the_window[0]=atr14_x100` ·
  `CP3-PR2B-S1a.json:fields_that_moved_outside_the_window[1]=vwap_reverted` ·
  `CP3-PR2B-S1a.json:fields_that_moved_outside_the_window[2]=z_x1000`
- 움직인 봉: `CP3-PR2B-S1a.json:bars_that_moved_outside_the_window_count=14` 개 —
  `CP3-PR2B-S1a.json:bars_that_moved_outside_the_window[0]=08:45` 부터
  `CP3-PR2B-S1a.json:bars_that_moved_outside_the_window[13]=08:58` 까지
- 0 이 아닌 **모든** 섭동에서:
  `CP3-PR2B-S1a.json:offsets_at_which_something_moved_outside_the_window=118`

원인은 계획 본문이 이미 적은 그것이다 — 접합 true range 는 **08:45 봉**에 있다. 계획은 거기서
「진입 창(09:00~) ATR 의 SMA14 창에 보통 들어가지 않는다」로 이어지는데, 그 말은 맞고 **진입 창**에
대해서만 맞다. 08:45 봉의 TR 은 그 뒤 14 봉(08:45–08:58)의 ATR14 안에 있고, 그 봉들은 B1a 가
**발행하는** 봉이다. 즉 「구조상 안 움직인다」는 판별 게이트에 대해 참이고 **아티팩트에 대해 거짓**이다.

처분 제안(운영자 판단): 계획 §3.2a 의 그 한 문장을 「진입 창 밖 개장 14 봉의 `atr14_x100`·
`z_x1000`·`vwap_reverted` 는 `c` 와 함께 움직인다 — 판별에는 닿지 않는다」로 정정. **파리티와는
무관하다**: 생산자와 B1a·B2 가 같은 매니페스트를 읽으므로 세 쪽 모두 같은 값을 낸다. 이 문단이
말하는 것은 「`c` 가 다르면 아티팩트가 다르다」이지 「두 쪽이 어긋난다」가 아니다.

## 4. 이 측정이 **확립하지 못한 것**

- **2026-10-14.** 측정 시각에 그날 세션이 **열려 있었다**
  (`CP3-PR2B-S1b.json:day_not_measured=2026-10-14` ·
  `CP3-PR2B-S1b.json:day_not_measured_reason=the 2026-10-14 session was still open at measurement time (10:18 KST; the futures CONTINUOUS window ends 15:45), and a growing day cannot be parsed as a completed session`).
  계획이 「완전한 비교」라 부른 날이 바로 이 날이므로, **S1b 의 가장 깨끗한 한 점이 빠져 있다.**
  15:45 뒤에 같은 도구로 6 회 GET 을 더 쏘면 채울 수 있다(§5 의 명령 그대로, 날짜만 바꾼다).
- **다른 롤.** 2026-10 만기 하나만 봤다. S1a 의 여유 22 배도 S1b 의 1/662 도 이 롤의 값이다.
- **거래 영향.** S1b 가 찾은 한 봉이 주문·체결로 이어지는지는 재지 않았다. `hi_vol` 은 게이트
  하나일 뿐이고 그 뒤에 |z| 문턱·정체·반전·신뢰도가 더 있다.
- **파리티.** 이 문서는 생산자와 B1a·B2 가 **같은 값을 내는지**를 재지 않는다. 그것은 이 PR 의
  테스트 5 가 확인한다(생산자 프레임 == `load_window(stitch_manifest=)` 재구성).
- **S1a 의 다른 날.** 계획대로 10-12 만 쟀다. 10-13·10-14 의 09:00–09:14 에서는 경로 (a) 가
  구조상 0 이다(그 봉들의 `_close_window`·`prev_close` 에 직전 월물이 없다).

## 5. 재현

```bash
# 1) 오프라인 재계산 — 네트워크 0. 원천은 아래 세 requests.jsonl.
#    (분석 스크립트는 PR-1·#899 와 같은 방침으로 커밋하지 않는다 — 지문은 §6)

# 2) S1b 가 필요로 한 단 하나의 조회 (완료 세션, GET-only, 분리 워크트리 origin/main)
#    종목 CP3-PR2B-summary.json:requests_symbol · 날짜 CP3-PR2B-summary.json:requests_day
#    GET CP3-PR2B-summary.json:requests 회 · 주문 CP3-PR2B-summary.json:orders 건
#    원시 행 CP3-PR2B-summary.json:requests_raw_rows

# 3) 원천 무결성
cd ~/.local/state/tos/measure/cp3-pr2b-s1b-20261014
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
| `cp3-pr2b-s1b-20261014/requests.jsonl` | `1689d76082fb830ddbb0f5f7556d46de871d9989759d4fe3bc766df5cbe95eff` | 이 측정의 GET 6 회 — A05611 10-13 |

앞의 둘은 각 수집기의 `sha256.json` 과 재대조해 일치를 확인했다(불일치 0 건). 세 번째는 이
측정이 만든 것이고 그 디렉터리의 `sha256.json` 에 같은 값이 있다.

파생 수치의 출처가 되는 세션별 파싱 봉 수는 `CP3-PR2B-summary.json:parsed_bar_counts` 에
그대로 있다 — 예: `CP3-PR2B-summary.json:parsed_bar_counts.A05610:2026-10-08=395`(만기 월물의
짧은 접합일) · `CP3-PR2B-summary.json:parsed_bar_counts.A05611:2026-10-13=411`.
밀도 게이트 `CP3-PR2B-summary.json:density_gate=330` · 창 요구
`CP3-PR2B-summary.json:vol_window_bars=780` 은 B1a·전략 YAML 의 값 그대로다.

## 7. 안전 — 이 측정이 건드리지 않은 것

- **주문 0 건** (`CP3-PR2B-summary.json:orders=0`). 조회 클라이언트는 PR-1 의
  `tools/tos_cp3/quote_client.py` 하나이고 GET + 이 TR + 이 경로만 허용한다;
  `shared/execution` · `probes_real_order` 는 import 하지 않는다.
- **GET `CP3-PR2B-summary.json:requests=6` 회**, PR-1 과 같은 `pace_s` 1.1 페이싱.
  목적은 `CP3-PR2B-summary.json:requests_purpose=the one completed session S1b needed that nothing had recorded`.
- **분리 워크트리.** 조회는 `origin/main` 의 detached 워크트리에서 돌렸다(공유 체크아웃 아님).
- **공유 venv 미변경.** `pip install` 없이 기존 `.venv` 로만 돌렸다.
- **tenant 미기동.** paper 상주 런타임·Redis·Parquet 쓰기 경로에 손대지 않았다.
- **실전 선물 계좌 미펀딩 규칙 무관.** 조회(GET)만이고 주문 경로는 정책상 영구 차단 그대로다.
