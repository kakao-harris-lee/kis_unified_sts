# CP-3 PR-2b 전제 실측 — 만기 월물 `A05610` 과거 분봉 조회 (2026-10-14)

- 계획: `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md` §3.2a 「**전제 실측**」 · §3.3 · §4 PR-2b.
- 선행 증거: `docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md` (PR-1, 같은 TR).
- 도구: `tools/tos_cp3/expired_history_probe.py`, 설정 `config/tos_probes/cp3-pr2b-expired-20261014.yaml`.
  조회 클라이언트·허용목록·토큰 캐시·비공개 레코더는 PR-1 `tools/tos_cp3/minute_probe.py` 의 것을
  그대로 쓴다(두 번째 HTTP 클라이언트 없음).
- 환경: **실전 키 GET-only 시세 TR `FHKIF03020200` · 주문 0 건** —
  `CP3-PR2B-summary.json:method=GET` · `CP3-PR2B-summary.json:tr_id=FHKIF03020200` ·
  `CP3-PR2B-summary.json:orders=0` · 요청 `CP3-PR2B-summary.json:requests=35`.
- 실행: 2026-10-14 `CP3-PR2B-summary.json:run_started_kst=2026-10-14 00:56:21.864554+09:00` KST,
  수동 1 회. 장과 무관한 **과거 세션만** 읽으므로 자라는 하루를 관측하지 않는다.

## 0. 답

> **질문**(`CP3-PR2B-summary.json:question=does FHKIF03020200 return historical minute bars for the EXPIRED mini contract A05610 (expiry 2026-10-08)?`)
>
> **답 = `CP3-PR2B-summary.json:answer=YES`.**

`FHKIF03020200` 은 만기(2026-10-08)가 지난 mini 월물 `A05610` 의 과거 분봉을 **돌려준다**.
요청한 `CP3-PR2B-sessions.json:expired_sessions_requested=5` 세션 전부에서 봉이 왔고
(`CP3-PR2B-sessions.json:expired_sessions_with_bars=5`), 전부 §3.2a 가 B1a 와 공유하는 밀도
게이트를 통과했다(`CP3-PR2B-sessions.json:expired_sessions_passing_density=5`).

따라서 **§3.2a 의 정지 조건(「돌려주지 않으면 이 절은 멈추고 운영자에게 올린다」)은 발생하지
않았다.** 이 문서는 그 전제 하나만 닫는다 — 생산자도, §6.2 의 대안(만기 전 동결 프레임 보관)도
여기서 설계하거나 승인하지 않는다(`CP3-PR2B-summary.json:verdict_scope=prerequisite only; neither the producer nor the §6.2 fallback is designed or approved here`).

### 0.1 원천 아티팩트 — 비공개, 이 디렉터리에 없다

원천은 호스트의 0700 디렉터리 `~/.local/state/tos/measure/cp3-pr2b-expired-20261014/`(파일 0600)에
있다. `requests.jsonl` 은 731 KB 원시 응답이라 커밋하지 않는다. **커밋한 것은 파생 수치 JSON
네 개뿐**이고 인용 토큰은 그 파생 파일만 가리킨다. 원천 지문(아래 여섯 값은 커밋한
`CP3-PR2B-summary.json` 의 `source_sha256` 블록에 그대로 들어 있다 — 파일명에 점이 있어 인용
토큰의 경로 문법으로는 가리킬 수 없으므로 산문 표로 적는다):

| 원천 파일 | sha256 |
|---|---|
| `requests.jsonl` | `aa22d11fa7570212679cdc82a7d6158519a7fd80866869d78d6675741d3c6bef` |
| `sessions.json` | `d27a07e98b47be0892d2a8946ed87b8086aecc89f1f225267cb057a8479ec2fb` |
| `junction.json` | `5c1e4b0b8cd66644f4fb181b32a9ce59818e6f938511f2c8ef45db0e2bf5163d` |
| `s1a-spread.json` | `bc7b80d312b30c6cfbd6307a3011da096b5ec456300c0db7f021aeec707d4819` |
| `summary.json` | `dac503c8b65538356627e8f659a1cbb9bd5b4ef753fb7cbec764eedca4cf2760` |
| `run.json` | `ba08af1c537334a222954898af2f050aa563c87156f2734ec11effa55a5b71c4` |

파생 전에 원천 여섯 개를 그 디렉터리의 `sha256.json` 과 재대조해 **전부 일치**를 확인했다
(불일치 0 건). 원천 `run.json` 의 앱 키는 비가역 지문으로만 존재하고 이 문서는 그 값을 옮기지
않았다. 커밋한 JSON 에 토큰·요청 헤더·계좌번호·`msg1` 텍스트는 없다 — 메시지는 **분류 코드**
(`msg_cd`)로만 기록한다.

## 1. 요청 계획 — 종목은 §3.2a 의 걸음이 정했다

설정에는 종목을 적지 않는다. 접합일 `2026-10-08` 로부터
`shared/instruments/futures.py::get_front_month_code(product="mini", target_date=d)` — 오늘의 종목을
정하는 바로 그 함수 — 가 각 세션의 월물을 정하고, 승계 월물은 접합일 **다음 거래일**(달력상
2026-10-12, 10-09 는 한글날)에 같은 함수를 한 번 더 적용해 얻는다. 두 번째 롤 규칙은 쓰지 않는다.

그렇게 나온 요청 여섯 개: `A05610` × {10-08, 10-07, 10-06, 10-02, 10-01} + `A05611` × {10-08}.
10-05 는 대체휴일, 10-03 은 토요일이라 시드 걸음에 없다(런타임 달력
`config/tos_runtime/cp3-setup-d-long/calendar.yaml`).

도구는 **빈 응답을 엉뚱한 이유로 「답」이라 읽지 않도록** 기동 전에 다섯 가지를 거부한다:
휴장일 · 미완료 세션(오늘/미래) · 접합일 이후의 시드일 · 접합이 둘 이상인 창 · 달력이 덮지 않는
연도. 각 거부는 hermetic 테스트가 **커밋된 달력에 대고** 재현한다
(`tests/tools/test_cp3_expired_history_probe.py::test_plan_refuses_a_response_that_would_be_empty_for_another_reason`).

## 2. 행 모양

여섯 세션 전부 같은 여덟 키다 —
`CP3-PR2B-sessions.json:sessions[0].raw_row_keys=["acml_tr_pbmn","cntg_vol","futs_hgpr","futs_lwpr","futs_oprc","futs_prpr","stck_bsop_date","stck_cntg_hour"]`.

⚠ **날짜·시각 키가 `futs_` 가 아니라 `stck_` 접두다**(`stck_bsop_date` · `stck_cntg_hour`)
— OHLC 는 `futs_` 접두인데 도장만 주식 접두를 쓴다. `minute_probe.raw_stamp` 와
`ohlcv_parser.parse_ohlcv` 가 양쪽 접두를 모두 보므로 현재 경로는 영향이 없지만, 선물 TR 응답을
`futs_` 만 보고 파싱하는 새 코드는 **조용히 0 행**을 얻는다.

응답 상태는 여섯 세션 전부 동일하다 — `CP3-PR2B-sessions.json:sessions[0].rt_cd=["0"]` ·
`CP3-PR2B-sessions.json:sessions[0].msg_cd=["MCA00000"]` ·
`CP3-PR2B-sessions.json:sessions[0].http_status=[200]` ·
`CP3-PR2B-sessions.json:sessions[0].transport_errors=[]` ·
`CP3-PR2B-sessions.json:sessions[0].fetch_error=null`. **만기 월물에만 오는 거부 코드는 없었다.**

### 2.1 원시 행 수 ≠ 분 수 — 페이지 겹침이고 중복 봉이 아니다

프로브의 세션별 원시 행 수는 페이지 응답을 그대로 이어붙인 값이라 **분 수보다 크다**. 10-08
`A05610` 은 `CP3-PR2B-sessions.json:sessions[0].raw_rows_as_probe_counted=399` 행 ·
`CP3-PR2B-sessions.json:sessions[0].raw_rows_distinct=395` 로 차이가
`CP3-PR2B-sessions.json:sessions[0].pagination_overlap_rows=4` 인데, 이는 **페이지 경계 수와
정확히 같다**(5 페이지 → 4 경계) —
`CP3-PR2B-sessions.json:sessions[0].pagination_overlap_equals_page_boundaries=true`.
여섯 세션 전부 그렇다(6 페이지 세션은 겹침 5 —
`CP3-PR2B-sessions.json:sessions[1].pagination_overlap_rows=5` ·
`CP3-PR2B-sessions.json:sessions[1].pagination_overlap_equals_page_boundaries=true`).
`FID_INPUT_HOUR_1` 커서가 가리킨 분이 다음 페이지에 한 번 더 실려 오는 것이고, 한 분에 서로
다른 OHLC 가 둘 오는 #516 류 중복과는 다르다.

## 3. 세션별 밀도 — 다섯 세션 전부 게이트 통과

게이트 값과 출처: `CP3-PR2B-sessions.json:density_gate=330` ·
`CP3-PR2B-sessions.json:density_gate_source=tools/tos_cp3/produce_fields.py::DEFAULT_MIN_BARS_PER_DAY`
(§3.2 「밀도 게이트를 B1a 와 같게 … 같은 상수를 같은 함수로」). 거래량 하한은 §3.3 핀과 같은
`CP3-PR2B-sessions.json:volume_floor=10` 이고 `parse_ohlcv` 가 적용한다.

| # | 종목 | 거래일 | 페이지 | 원시 분 | **파싱 봉** | 게이트 330 | 원시 첫 분 | **원시 마지막 분** | 분 구간 | 구간 내 부재 분 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | `A05610` | `CP3-PR2B-sessions.json:sessions[0].day=2026-10-08` | `CP3-PR2B-sessions.json:sessions[0].pages=5` | `CP3-PR2B-sessions.json:sessions[0].raw_minutes=395` | `CP3-PR2B-sessions.json:sessions[0].parsed_bars=395` | `CP3-PR2B-sessions.json:sessions[0].density_pass=true` | `CP3-PR2B-sessions.json:sessions[0].raw_first_kst=08:45:00` | **`CP3-PR2B-sessions.json:sessions[0].raw_last_kst=15:19:00`** | `CP3-PR2B-sessions.json:sessions[0].raw_minute_span=395` | `CP3-PR2B-sessions.json:sessions[0].absent_minutes_in_span=0` |
| 1 | `A05610` | `CP3-PR2B-sessions.json:sessions[1].day=2026-10-07` | `CP3-PR2B-sessions.json:sessions[1].pages=6` | `CP3-PR2B-sessions.json:sessions[1].raw_minutes=411` | `CP3-PR2B-sessions.json:sessions[1].parsed_bars=411` | `CP3-PR2B-sessions.json:sessions[1].density_pass=true` | `CP3-PR2B-sessions.json:sessions[1].raw_first_kst=08:45:00` | `CP3-PR2B-sessions.json:sessions[1].raw_last_kst=15:45:00` | `CP3-PR2B-sessions.json:sessions[1].raw_minute_span=421` | `CP3-PR2B-sessions.json:sessions[1].absent_minutes_in_span=10` |
| 2 | `A05610` | `CP3-PR2B-sessions.json:sessions[2].day=2026-10-06` | `CP3-PR2B-sessions.json:sessions[2].pages=6` | `CP3-PR2B-sessions.json:sessions[2].raw_minutes=411` | `CP3-PR2B-sessions.json:sessions[2].parsed_bars=411` | `CP3-PR2B-sessions.json:sessions[2].density_pass=true` | `CP3-PR2B-sessions.json:sessions[2].raw_first_kst=08:45:00` | `CP3-PR2B-sessions.json:sessions[2].raw_last_kst=15:45:00` | `CP3-PR2B-sessions.json:sessions[2].raw_minute_span=421` | `CP3-PR2B-sessions.json:sessions[2].absent_minutes_in_span=10` |
| 3 | `A05610` | `CP3-PR2B-sessions.json:sessions[3].day=2026-10-02` | `CP3-PR2B-sessions.json:sessions[3].pages=6` | `CP3-PR2B-sessions.json:sessions[3].raw_minutes=411` | `CP3-PR2B-sessions.json:sessions[3].parsed_bars=411` | `CP3-PR2B-sessions.json:sessions[3].density_pass=true` | `CP3-PR2B-sessions.json:sessions[3].raw_first_kst=08:45:00` | `CP3-PR2B-sessions.json:sessions[3].raw_last_kst=15:45:00` | `CP3-PR2B-sessions.json:sessions[3].raw_minute_span=421` | `CP3-PR2B-sessions.json:sessions[3].absent_minutes_in_span=10` |
| 4 | `A05610` | `CP3-PR2B-sessions.json:sessions[4].day=2026-10-01` | `CP3-PR2B-sessions.json:sessions[4].pages=6` | `CP3-PR2B-sessions.json:sessions[4].raw_minutes=411` | `CP3-PR2B-sessions.json:sessions[4].parsed_bars=411` | `CP3-PR2B-sessions.json:sessions[4].density_pass=true` | `CP3-PR2B-sessions.json:sessions[4].raw_first_kst=08:45:00` | `CP3-PR2B-sessions.json:sessions[4].raw_last_kst=15:45:00` | `CP3-PR2B-sessions.json:sessions[4].raw_minute_span=421` | `CP3-PR2B-sessions.json:sessions[4].absent_minutes_in_span=10` |
| 5 | `A05611` | `CP3-PR2B-sessions.json:sessions[5].day=2026-10-08` | `CP3-PR2B-sessions.json:sessions[5].pages=6` | `CP3-PR2B-sessions.json:sessions[5].raw_minutes=411` | `CP3-PR2B-sessions.json:sessions[5].parsed_bars=411` | `CP3-PR2B-sessions.json:sessions[5].density_pass=true` | `CP3-PR2B-sessions.json:sessions[5].raw_first_kst=08:45:00` | `CP3-PR2B-sessions.json:sessions[5].raw_last_kst=15:45:00` | `CP3-PR2B-sessions.json:sessions[5].raw_minute_span=421` | `CP3-PR2B-sessions.json:sessions[5].absent_minutes_in_span=10` |

세션 0 의 411 → 395 차이는 **거래량 하한이나 결손이 아니다**: 원시 분이 저장되지 못한 건수는
여섯 세션 모두 0 이고(`CP3-PR2B-sessions.json:sessions[0].raw_minutes_not_stored=0` ·
`CP3-PR2B-sessions.json:sessions[5].raw_minutes_not_stored=0`), 세션 0 은 **구간 자체가 395 분**이고
그 안에 부재 분이 **0** 이다. 즉 만기 월물의 10-08 은 얇아진 것이 아니라 **일찍 끝났다**(§4).

PR #881(P-VL)의 **미니 틱 0.02** 관측과 일치한다: 여섯 세션 전부 저장 종가의 100 배가 짝수다 —
`CP3-PR2B-sessions.json:sessions[0].closes_x100_all_even=true` ·
`CP3-PR2B-sessions.json:sessions[5].closes_x100_all_even=true`.

## 4. §3.2a 의 경고가 실측됐다 — 만기 월물은 접합일에 **15:19** 에 끝난다

계획 §3.2a: 「⚠ **접합일의 두 월물은 세션 끝이 다를 수 있다**: … 레포 달력 테스트는 그날도
08:45–15:45 로 둔다 … 레포에 실측이 없다.」 이제 있다.

- 만기 월물 마지막 원시 분 `CP3-PR2B-junction.json:expired_raw_last_kst=15:19`
- 승계 월물 마지막 원시 분 `CP3-PR2B-junction.json:successor_raw_last_kst=15:45`
- 차이 `CP3-PR2B-junction.json:minutes_the_expired_leg_is_short_by=26` 분
- 그 뒤 만기 월물 원시 분 `CP3-PR2B-junction.json:expired_raw_minutes_after_last_common=0`,
  같은 구간의 승계 월물 원시 분 `CP3-PR2B-junction.json:successor_raw_minutes_after_last_common=16`
  (15:20–15:34 의 15 분 + 15:45 의 1 분 — 그 사이 15:35–15:44 는 §6 의 부재 구간이라 승계 월물에도
  없다)

**이것은 한쪽 다리만의 조기 종료이지 양쪽 공통의 자료 결손이 아니다** — 같은 날 같은 창에서
승계 월물은 16 분을 더 돌려줬다. 결과적으로 §3.2a 의 규칙(「마지막 공통 분은 만기 월물의 마지막
원시 행 시각 **이하**」)은 이 롤에서 **등호**로 성립한다:
`CP3-PR2B-junction.json:last_common_is_expired_last_parsed=true` ·
`CP3-PR2B-junction.json:last_common_is_successor_last_parsed=false`.

⚠ **15:19 가 거래소 규칙이라는 증거는 여기 없다.** 관측한 것은 **이 응답에 15:20 이후 만기 월물
행이 없다**는 사실 하나이고, 최종결제 절차·단일가·종료 시각에 대한 거래소 측 근거는 조회하지
않았다. 롤 하나(2026-10 만기)만의 관측이다(§7).

## 5. `c_x100` — 마지막 **공통 파싱** 분에서

§3.2a 의 정의대로 각 월물 자신의 마지막 종가가 아니라 **두 월물 모두 저장 봉이 있는 마지막 같은
분**에서 구한다. 두 월물의 공통 파싱 분은
`CP3-PR2B-junction.json:common_parsed_minutes=395` 개이고
`CP3-PR2B-junction.json:first_common_minute_kst=08:45` 부터
**`CP3-PR2B-junction.json:last_common_minute_kst=15:19`** 까지다.

| 항목 | 값 |
|---|---|
| `P_old` (`A05610` 15:19 종가 ×100) | `CP3-PR2B-junction.json:expired_close_x100=104900` |
| `P_new` (`A05611` 15:19 종가 ×100) | `CP3-PR2B-junction.json:successor_close_x100=105244` |
| **`c_x100` = `P_new` − `P_old`** | **`CP3-PR2B-junction.json:c_x100=344`** |
| 0.02 격자(짝수) | `CP3-PR2B-junction.json:c_x100_is_even=true` |
| 그 분의 거래량 (만기 / 승계) | `CP3-PR2B-junction.json:expired_volume_at_last_common=667` / `CP3-PR2B-junction.json:successor_volume_at_last_common=449` |

즉 이 롤의 차분 상수는 **+3.44 지수포인트**(172 틱)다. 두 종가 모두 §3.3 거래량 하한을 넘은
**저장 봉**에서 왔으므로(667 · 449 ≫ 10) 생산자와 오프라인이 같은 분을 고르는 §3.2a 의 조건을
이 롤에서는 만족한다.

프로브가 적은 값과 이 파생이 원시 응답에서 **독립 재계산**한 값이 일치한다 —
`CP3-PR2B-junction.json:matches_probe_artifact.c_x100=true` ·
`CP3-PR2B-junction.json:matches_probe_artifact.last_common_minute=true` ·
`CP3-PR2B-junction.json:matches_probe_artifact.common_parsed_minutes=true`.

⚠ **접합 직후 세션의 `prev_close` 는 15:19 의 정렬 종가다** — `A05611` 자신의 10-08 마지막 종가
(15:45)가 아니다. §3.2a 가 그렇게 규정하고, 그 두 분이 **실제로 다르다**는 것이 §4 다.

## 6. S1a 입력 — 10-08 [14:16, 공통 분] 스프레드

§3.2a S1a: 변동 폭은 「**10-08** 의 [14:16, 공통 분] 구간에서 두 월물 거래량이 모두 §3.3 하한
이상인 공통 분들의 스프레드 범위로 정하고, 쓴 분의 수를 적는다」.

창: `CP3-PR2B-s1a-spread.json:window_start_kst=14:16` ~
`CP3-PR2B-s1a-spread.json:window_end_kst=15:19`
(`CP3-PR2B-s1a-spread.json:window_end_source=last common PARSED minute, measured on 2026-10-08` —
설정값이 아니라 §5 의 실측 분이다).

| 항목 | 값 |
|---|---|
| **쓴 분의 수** | **`CP3-PR2B-s1a-spread.json:minutes_used=64`** |
| 스프레드 ×100 최소 | `CP3-PR2B-s1a-spread.json:spread_x100_min=226` |
| 스프레드 ×100 최대 | `CP3-PR2B-s1a-spread.json:spread_x100_max=344` |
| **범위(최대−최소)** | **`CP3-PR2B-s1a-spread.json:spread_x100_range=118`** |
| 중앙값 | `CP3-PR2B-s1a-spread.json:spread_x100_median=270` |
| 창 첫 분(14:16) / 마지막 분(15:19) | `CP3-PR2B-s1a-spread.json:spread_x100_first=274` / `CP3-PR2B-s1a-spread.json:spread_x100_last=344` |
| 0.02 격자(짝수) | `CP3-PR2B-s1a-spread.json:spread_x100_all_even=true` |

거래량 하한이 실제로 지켜졌음: 하한
`CP3-PR2B-s1a-spread.json:volume_floor=10`,
적용 주체 `CP3-PR2B-s1a-spread.json:volume_floor_applied_by=parse_ohlcv KIS_MINUTE_BAR_MIN_VOLUME`,
창 안 두 다리의 **관측 최소 거래량** `CP3-PR2B-s1a-spread.json:min_volume_observed=14` (≥ 10).
그리고 이 창에서 하한·한쪽 부재로 빠진 분은 **없다** —
창 안 원시 분(어느 한쪽이라도 있는) `CP3-PR2B-s1a-spread.json:raw_minutes_in_window_either_leg=64`
와 쓴 분 64 의 차이가 `CP3-PR2B-s1a-spread.json:minutes_dropped_by_floor_or_one_sided=0` 이다.
분 단위 전체 계열(64 행, 분·스프레드·양쪽 거래량)은 `CP3-PR2B-s1a-spread.json:series[0].minute_kst=14:16`
부터 `CP3-PR2B-s1a-spread.json:series[63].minute_kst=15:19` 까지 아티팩트에 그대로 있다.

**그래서 S1a 가 흔들 구간은 [226, 344] 이고, 폭은 118(= 59 틱)이다.** ⚠ **채택한 `c_x100` =
344 가 이 창의 최대값과 같으므로 그 구간은 `c` 를 중심으로 대칭이 아니다** — 창이 지지하는 섭동은
`c − 118 ≤ c' ≤ c` 한쪽이다(`c` 는 §5 의 규칙대로 창의 **마지막** 분에서 나오고, 그 분이 마침
스프레드 최대 분이었다). S1a 를 ±118 로 돌리면 창이 관측하지 않은 위쪽 절반을 지어내는 것이다.
S1a 자체(09:00–09:14 의 `stall_ok`·`reversal_ok` 뒤집힘 수)는 접합 프레임이 필요하므로 PR-2b
구현에서 돌린다 — 이 문서는 **입력만** 제공한다.

⚠ 스프레드는 창 안에서 단조롭지 않지만(최소 226) **창 끝에서 최대**다(14:16 의 274 → 15:19 의
344). 만기 수렴·롤 압력과 방향이 같은 모습이지만, 하루·한 롤의 관측이므로 **원인을 주장하지
않는다**. S1a 가 써야 하는 것은 이 구간이고 추세 해석이 아니다.

## 7. 부수 관측 — 15:35–15:44 부재가 다섯 세션에서 재현됐다

PR-1 은 10-12 **하루**에서 「세 offset 모두 부재」인 경계 열 개가 정확히 15:35–15:44 임을 관측했다
(그 문서 §1.3). 이 실측의 **다른 다섯 세션**(10-01 · 10-02 · 10-06 · 10-07 의 `A05610`, 10-08 의
`A05611`)에서 같은 열 분이 **그대로 부재**다 —
네 세션의 첫·마지막 부재 분이 모두 같다:
`CP3-PR2B-sessions.json:sessions[1].absent_minutes_kst[0]=15:35` /
`CP3-PR2B-sessions.json:sessions[1].absent_minutes_kst[9]=15:44` ·
`CP3-PR2B-sessions.json:sessions[2].absent_minutes_kst[0]=15:35` /
`CP3-PR2B-sessions.json:sessions[2].absent_minutes_kst[9]=15:44` ·
`CP3-PR2B-sessions.json:sessions[3].absent_minutes_kst[0]=15:35` /
`CP3-PR2B-sessions.json:sessions[3].absent_minutes_kst[9]=15:44` ·
`CP3-PR2B-sessions.json:sessions[4].absent_minutes_kst[0]=15:35` /
`CP3-PR2B-sessions.json:sessions[4].absent_minutes_kst[9]=15:44` ·
`CP3-PR2B-sessions.json:sessions[5].absent_minutes_kst[0]=15:35` /
`CP3-PR2B-sessions.json:sessions[5].absent_minutes_kst[9]=15:44`.
부재 분이 각각 열 개이므로(§3 표) 그 열 개는 15:35~15:44 연속 구간이다. 15:45 로 끝나는 세션은
전부 분 구간 421 · 부재 10 · 저장 411 이다.

⚠ PR-1 과 같은 한계가 그대로 남는다: 관측한 것은 **행의 부재**이고 거래소 측 근거는 아니다.
그리고 이것은 과거 조회 응답이라 **PR-1 의 실시간 완성 지연(δ/G)과는 다른 측정**이다 — 여기서
지연은 전혀 재지 않았다.

## 8. 이 실측이 **확립하지 못한 것**

- **만기 뒤 조회 가능 기간의 상한.** 실행일은 만기 **6 일 뒤**(10-08 만기 · 10-14 실행)이고 가장
  오래된 요청은 접합일 7 일 전(10-01)이다. 더 오래된 만기 월물, 또는 만기 뒤 몇 주가 지난 코드에
  대해서는 **아무것도 관측하지 않았다**. §3.2a 의 생산자는 롤 **직후** 며칠 안에 조회하므로 이
  관측 범위 안에 들어가지만, 그보다 긴 공백은 측정 대상이 아니었다.
- **롤 하나.** 2026-10 만기만 봤다. 만기 월물이 15:19 에 끝나는 것이 매 롤의 성질인지, 이 달의
  값인지 모른다. 11-12 롤에서 다시 재야 한다.
- **시드 창 충족.** 밀도 게이트 통과(다섯 세션)는 §3.2 의 **창 충족**(`vol_window_bars` = 780 의
  진입 창 용량)과 다른 판정이다. `seed_capacity` 는 이 실행에서 **돌리지 않았다**.
- **접합 프레임과 파리티.** `load_window(stitch_manifest=)`·B1a·B2·B3 는 구현 전이고 이 문서는
  그 경로를 실행하지 않았다. S1a·S1b 의 **결과**도 없다(S1a 의 **입력**만 있다).
- **지연·성능.** `produce_bars` 비용, 응답 지연, δ/G 중 어느 것도 재지 않았다. 요청 수
  (35)와 페이지 수만 사실이다.
- **15:35–15:44 · 15:19 부재의 거래소 측 근거.** 행의 부재만 관측했다(§4 · §7).
- **`A05610` 의 과거 Parquet 대조.** PR-1 M4 가 한 레거시 파티션 비교는 여기서 하지 않았다.

## 9. §3.2a 로의 귀결

§3.2a 의 전제는 **충족됐다**: 만기 월물의 과거 분봉이 오고(§0 · §3), 접합일의 두 월물에 공통 파싱
분이 395 개 있으며(§5), 그중 마지막 분에서 `c_x100` 이 정수·짝수로 떨어진다(§5). 정지 조건이 발생하지 않았으니
**「§3.2a 정지 — 운영자 결정 필요(10-23 까지)」는 이 실측에 해당하지 않는다**. §6.2 대안을 11 월
만기 전에 미리 돌려야 하는지에 대한 판단 역시 이 문서의 범위가 아니다 — 설계도 하지 않는다.

남은 PR-2b 작업(월물별 걸음 · `stitch.json` · `produce_fields.load_window(stitch_manifest=)` ·
B1a·B2 의 `--stitch-manifest` · B3 창 정체성 · S1a·S1b · 테스트 6 종)은 그대로 계획 §3.2a 에 있다.

## 10. 재현

```bash
# 1) 도구 자체 (hermetic · 네트워크·자격증명 0)
PYTHONPATH=. .venv/bin/python -m pytest tests/tools/test_cp3_expired_history_probe.py -q

# 2) 조회 계획만 확인 (네트워크 없음 — 거부 다섯 종류가 여기서 걸린다)
PYTHONPATH=. .venv/bin/python -m tools.tos_cp3.expired_history_probe \
  --config config/tos_probes/cp3-pr2b-expired-20261014.yaml

# 3) 실제 조회 (--confirm). 분리 워크트리에서, 공유 venv 는 변경하지 않는다.
PYTHONPATH=<worktree> /home/deploy/project/kis_unified_sts/.venv/bin/python \
  -m tools.tos_cp3.expired_history_probe \
  --config config/tos_probes/cp3-pr2b-expired-20261014.yaml --confirm

# 4) 원천 무결성
cd ~/.local/state/tos/measure/cp3-pr2b-expired-20261014
python - <<'PY'
import hashlib, json
from pathlib import Path
want = json.load(open("sha256.json"))
print([n for n, d in want.items()
       if hashlib.sha256(Path(n).read_bytes()).hexdigest() != d])   # [] 여야 한다
PY

# 5) 이 README 의 인용 검사
python tools/tos_evidence_citation_check.py \
  docs/broker-profiles/evidence/2026-10-14-cp3-pr2b-expired-contract/README.md
```

⚠ **같은 출력 디렉터리로는 재실행되지 않는다** — `Recorder` 가 `exist_ok=False` 로 만들기 때문에
기존 수집을 덮어쓸 수 없다. 재실행은 새 `output` 경로를 지정한다.

파생은 오프라인이고 원천을 읽기만 한다. PR-1 과 같은 방침으로 **분석 스크립트는 커밋하지
않는다**(일회성이고 레포 표면을 늘리지 않는다). 지문:

| 스크립트 (`~/.local/state/tos/measure/cp3-pr2b-expired-20261014-analysis/`) | sha256 |
|---|---|
| `derive.py` | `b98801217ef97cbfe658566143384bf6155bf0d1d9ae37d320ebbf720aef1cfc` |

## 11. 안전 — 이 실행이 건드리지 않은 것

- **주문 0 건** (`CP3-PR2B-summary.json:orders=0`). 허용목록은 GET + 이 TR + 이 경로 하나뿐이고
  (`tools/tos_cp3/minute_probe.py::ALLOWLIST`), `shared/execution`·`probes_real_order` 는 import 하지
  않는다. hermetic 테스트가 POST·주문 경로·주문 TR 세 가지를 전송 **전에** 거부함을 확인한다.
- **GET 35 회** (`CP3-PR2B-summary.json:requests=35`), PR-1 과 같은 `pace_s` 1.1 페이싱.
- **tenant 미기동.** paper 상주 런타임·Redis·Parquet 쓰기 경로에 손대지 않았다.
- **공유 venv 미변경.** `pip install` 없이 기존 `.venv` 로만 돌렸다.
- **비밀 미기록.** 비공개 원천과 커밋 JSON 모두에 토큰·요청 헤더·계좌번호·`msg1` 이 없다.
  메시지는 분류 코드(`msg_cd`)로만 남고, 그 한 줄을 `minute_probe` 에 더하면서 hermetic 테스트가
  **`msg_cd` 는 남고 `msg1` 텍스트는 남지 않음**을 양쪽으로 단언한다
  (`tests/tools/test_cp3_expired_history_probe.py::test_transport_records_msg_cd_class_without_msg1`).
- **원천 디렉터리 미변경.** 파생 출력은 새 디렉터리
  `~/.local/state/tos/measure/cp3-pr2b-expired-20261014-analysis/`(0700)에 썼다.
- **실전 선물 계좌 미펀딩 규칙 무관.** 조회(GET)만이고 주문 경로는 정책상 영구 차단 그대로다.
