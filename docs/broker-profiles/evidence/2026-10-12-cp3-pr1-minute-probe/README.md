# CP-3 PR-1 실행 증거 — 2026-10-12 실전 조회 측정과 δ/G 도출

- 계획: `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md` §3.2 · §3.3 · §4 PR-1 · §5 · §6.
- 런북: `docs/runbooks/tos-cp3-pr1-20261012.md`.
- 프로브: `tools/tos_cp3/minute_probe.py` (PR #894 머지), 설정 `config/tos_probes/cp3-pr1-20261012.yaml`.
- 환경: **실전 키 GET-only 시세 TR `FHKIF03020200` · 주문 0건.** 종목 `A05611`(mini front month).
- 실행: 호스트 user systemd timer `tos-cp3-pr1-20261012.timer`, 2026-10-12 08:44 KST 1회.
  측정 창 08:46–15:46 KST.
- 이 문서는 **장후 오프라인 분석**이다. 분석 과정에서 네트워크·KIS 호출은 0건이고, 10-12 프로브는
  재실행하지 않았다.

## 0. 이 실행의 상태 — 부분 성공

프로브는 장중 수집(M1/M2/M2b)과 당일 전체 파싱 비교(M4 일부)를 끝낸 뒤, **장후 시드 단계에서
`RuntimeError` 로 중단**했다. 그래서 `m3-seed.json` · `m3-full-day.json` · `completion.json` 은
생성되지 않았고, 이 증거의 M3 는 **다른 월물에서 잰 비용 프록시**다(§4).

| 측정 | 상태 | 근거 |
|---|---|---|
| M1 종목·행 모양 | 측정됨 | `requests.jsonl` 원시 `output2` |
| M2 δ/G 브래킷 | 측정됨 → **δ/G 제안**(§1) | `CP3-PR1-M2-brackets.json` |
| M2b 마감 구간 | 측정됨 → **판정 확정**(§2) | `CP3-PR1-M2b-closing.json` |
| M3 `produce_bars` 시간 | ⚠ **프록시만**(다른 월물) | `CP3-PR1-M3-offline-benchmark-proxy.json` |
| M4 Parquet 대조 | 측정됨 → **분류 + 예상 못한 결함**(§3) | `CP3-PR1-M4-*.json` |
| 시드 충족 | **실패**(용량 0/780) → 최단 충족일 도출(§5) | `CP3-PR1-seed-earliest-fill.json` |

### 0.0 ⛔ 정정 (2026-10-13, PR #896 독립 리뷰 REQUEST_CHANGES)

리뷰가 이 문서 초판의 **관측 범위 주장 하나를 반증**했다. 정정했고, 숨기지 않고 남긴다:

| 초판이 적은 것 | 실제 | 어디 |
|---|---|---|
| 「15:45 뒤 **2 분 55 초**를 더 관측했는데 15:46 행이 오지 않았다」 | 당일 조회 관측은 **15:45:21.7** 에 끝났다(+21.7 초). 2 분 55 초는 **다른 날짜를 조회한 장후 시드 호출**의 응답 시각이었다. 그리고 **15:46 경계는 표본되지 않았다** | §2.1 |
| 「G 는 이 날 한 번도 발동하지 않았다」 | 08:45–15:34 에 빠진 봉은 없지만, **후속 행이 없는 봉은 둘**(15:34 · 15:45)이고 G 는 그 둘에 발동한다 | §1.6 |
| 「+15 초 조회는 검열 10 경계에만 쏘였다」 | 마감 창 **16 경계 전부**가 세 offset 을 받았다. 그것이 `present` 421 의 출처다 | §1.2 |
| 전송 오류 0 건 | 재시도에 **흡수된 오류 1 건**이 있었고, 그 때문에 15:45 의 +5 초 조회가 **+7.248 초**에 나갔다 | §1.3 |

원인은 내 분석 스크립트가 **조회 날짜를 가리지 않고** 마지막 수신 시각의 최대값을 취한 것이다.
스크립트를 고치고 필드를 날짜별로 분리했다(§8 의 sha256 갱신). **「세션 종료 시각 경과」 판정
자체는 유지된다** — 다만 근거가 「15:46 을 관측했다」가 아니라 **계획 §3.3 의 완성 규칙 + 런타임
달력의 세션 창**으로 바뀐다(§2.2).

### 0.1 원천 아티팩트 — 비공개, 이 디렉터리에 없다

원천은 호스트의 0700 디렉터리 `~/.local/state/tos/measure/cp3-pr1-20261012/`(파일 0600)에 있다.
`requests.jsonl` 은 14 MB 원시 응답이라 커밋하지 않는다. **이 디렉터리에 커밋한 것은 파생 수치
JSON 여덟 개뿐**이고, 인용 토큰은 그 파생 파일만 가리킨다(원천 파일명을 토큰으로 쓰면 검사기가
파일 부재로 막는다 — 그래서 원천 값은 아래 sha256 과 함께 산문으로 적는다).

분석 시작 시 원천 9 개 전부를 그 디렉터리의 `sha256.json` 과 재대조해 **전부 일치**를 확인했다
(불일치 0건). 이 증거가 인용하는 원천의 지문:

| 원천 파일 | sha256 |
|---|---|
| `boundary-samples.json` | `73c7aa35027d5f4e4c32e71b71ce8128833f1dc6f91e992d2b5f825a683427f2` |
| `requests.jsonl` | `731697c65ca5afa66d183a8fd8a6270181b702185d92fdc1832fec0fafe81a12` |
| `today-bars.json` | `ffae238167e8ffea44ffbd1caba323a03eac69bd73c75e6aa1bef163d67a6d91` |
| `seed-summary.json` | `9617454d12513cce61dc53aa9a0f6d4b6223b403cd958b7aafa59e8ef2110ccc` |
| `run.json` | `4c25b3ec9af65a8aeb8e6960b0d6935e06972d6e64c8d243ccd8705b2896eee4` |
| `summary.json` | `cda16cc32c59a7ba61cad28436a32aba55339ddce30a1f76b33552959b978d0f` |
| `m4-today-parser.json` | `42eb3dfeef2142628b76350cc8901549362dab7d5f858f4146dbeb26a10c5b66` |
| `abort.json` | `0e5aa1baeb76a55f3b654505d1376e695a85d64bd750211513a42af967b2c086` |
| `capture-status.json` | `dc8bb358c8f74afd31a8144d8acc8bccb6ddeb2eea6fe1f623042e316d77066f` |

원천 `summary.json` 의 `boundaries` = 420 · `seen_successors` = 410 · `censored_or_errors` = 10 ·
`max_first_seen_delay_s` = 5.345897 · `orders` = 0. 아래 파생 수치는 모두 이 값들과 일관된다.

## 1. M2 — δ/G 도출 (⚠ **제안이며 확정값이 아니다**)

### 1.1 브래킷의 의미

프로브는 분 경계 `m` 뒤 **+1 / +5 / +15 초**에 조회해 「시각 `m` 으로 도장된 원시 행」의 존재를
본다. 그 행이 곧 봉 `m-1` 의 완성 신호(m+1 규칙)다. 한 경계의 첫 관측은 구간이다:

- **상한** = 그 행이 보인 응답의 **수신 시각** − 경계.
- **하한** = 직전 **부재** 요청의 **시작 시각** − 경계. 첫 offset 에서 이미 보였으면 부재 요청이
  없으므로 **하한이 없다**(0 이하로 열려 있다).

⚠ **표본은 offset 격자까지만 분해한다** —
`CP3-PR1-M2-brackets.json:resolution_caveat=sampling resolves only to the +1/+5/+15s offset grid; a bracket upper bound is a receipt time, not an arrival time`.
상한은 도착 시각이 아니라 수신 시각이다.

### 1.2 분포 — 격자가 만든 쌍봉

표본 `CP3-PR1-M2-brackets.json:source.samples=518` · 경계
`CP3-PR1-M2-brackets.json:source.boundaries=420` · 후속 관측
`CP3-PR1-M2-brackets.json:seen_successors=410` · 검열
`CP3-PR1-M2-brackets.json:censored_boundaries=10`.

**전체 분포의 p90 을 지연의 성질로 읽으면 틀린다.** 프로브는 처음 보인 offset 에서 멈추므로 상한은
+1 초 근처 아니면 +5 초 근처에만 떨어지고 **그 사이는 비어 있다**. 그래서 두 봉을 나눠 적는다:

| 봉 | n | min | p50 | max | mean |
|---|---|---|---|---|---|
| +1 초에서 보임 | `CP3-PR1-M2-brackets.json:upper_bound_s_first_offset_mode.n=343` | `CP3-PR1-M2-brackets.json:upper_bound_s_first_offset_mode.min=1.082358` | `CP3-PR1-M2-brackets.json:upper_bound_s_first_offset_mode.p50=1.107809` | `CP3-PR1-M2-brackets.json:upper_bound_s_first_offset_mode.max=1.765964` | `CP3-PR1-M2-brackets.json:upper_bound_s_first_offset_mode.mean=1.12908` |
| +5 초에서 보임 | `CP3-PR1-M2-brackets.json:upper_bound_s_second_offset_mode.n=67` | `CP3-PR1-M2-brackets.json:upper_bound_s_second_offset_mode.min=5.030515` | `CP3-PR1-M2-brackets.json:upper_bound_s_second_offset_mode.p50=5.037638` | `CP3-PR1-M2-brackets.json:upper_bound_s_second_offset_mode.max=5.345897` | `CP3-PR1-M2-brackets.json:upper_bound_s_second_offset_mode.mean=5.053278` |

전체로는 p50 `CP3-PR1-M2-brackets.json:upper_bound_s.p50=1.110636` · max
`CP3-PR1-M2-brackets.json:upper_bound_s.max=5.345897` ·
min `CP3-PR1-M2-brackets.json:upper_bound_s.min=1.082358`.
⚠ 전체 p90 `CP3-PR1-M2-brackets.json:upper_bound_s.p90=5.036484` 은 **두 봉의 혼합비**를 말할 뿐
「90 % 가 5 초 걸린다」가 아니다 — 83.7 % 는 1.1 초대다.

몇 번째 조회에서 보였는가:
`CP3-PR1-M2-brackets.json:probes_until_first_hit.hits_at_probe_1=343` ·
`CP3-PR1-M2-brackets.json:probes_until_first_hit.hits_at_probe_2=67`.
**세 번째 조회(+15 초)에서 처음 보인 경계는 0 건이다.**

⚠ **그것이 「+15 초 조회를 거의 쏘지 않았다」는 뜻은 아니다.** `sample()` 은 `minute < closing`
동안만 첫 발견에서 멈추므로, **마감 창의 16 경계 전부가 세 offset 을 다 받았다** —
`CP3-PR1-M2-brackets.json:probe_accounting.closing_window_boundaries=16` ·
`CP3-PR1-M2-brackets.json:probe_accounting.boundaries_probed_at_all_three_offsets=16` ·
`CP3-PR1-M2-brackets.json:probe_accounting.third_offset_went_to_every_closing_boundary=true`.
그중 §1.3 의 검열 10 경계는 세 번 다 부재였고, 나머지 6 경계는 **이미 +1/+5 초에 보인 뒤에도**
계속 조회돼 중복 관측을 남겼다. 그래서 `present` 가 경계 수를 넘는다 —
중복 `CP3-PR1-M2-brackets.json:probe_accounting.repeat_present_observations_at_closing_boundaries=11`
이고 `CP3-PR1-M2-brackets.json:probe_accounting.present_equals_first_hits_plus_repeats=true`
(421 = 410 첫 발견 + 11 중복). **경계가 더 있는 것이 아니다.**

하한: 하한이 **박힌** 경계는 `CP3-PR1-M2-brackets.json:lower_bound_s_constrained_only.n=67` 뿐이고
그 값은 min `CP3-PR1-M2-brackets.json:lower_bound_s_constrained_only.min=1.000298` ~ max
`CP3-PR1-M2-brackets.json:lower_bound_s_constrained_only.max=1.001998` 로 사실상 +1 초다. 나머지
`CP3-PR1-M2-brackets.json:lower_bound_unconstrained_boundaries=343` 개는 **하한이 없다**. 즉 그
343 개의 참 지연은 0 과 1.77 초 사이 어디든 될 수 있고 이 표본은 **더 좁히지 못한다**.
하한이 박힌 67 개의 구간 폭은
`CP3-PR1-M2-brackets.json:bracket_width_s_constrained_only.min=4.030172` ~
`CP3-PR1-M2-brackets.json:bracket_width_s_constrained_only.max=4.345511` 초 — 4 초짜리 무지 구간이다.

### 1.3 검열 10 건 — 전부 사유가 같고, 전부 마감 단일가 구간이다

검열 경계는 **정확히 15:35 · 15:36 · 15:37 · 15:38 · 15:39 · 15:40 · 15:41 · 15:42 · 15:43 ·
15:44** 열 개다(`CP3-PR1-M2-brackets.json` 의 `censored_detail`). 열 건 전부:

- 사유가 **`all_3_probed_offsets_absent`** 하나다 — +1 · +5 · +15 초 세 offset 을 모두 쏘고 모두 부재.
- **네트워크 오류가 아니다**: 관측 모양 집계가 `present` 와 `absent` 뿐이고
  `CP3-PR1-M2-brackets.json:observation_shapes.present=421` ·
  `CP3-PR1-M2-brackets.json:observation_shapes.absent=97` 로, **`fetch_error` 0 건 · `skipped_late`
  0 건**(두 키가 집계에 아예 나타나지 않는다).
- **지연으로 offset 을 놓친 표본도 0 건이다.**

⚠ **그래도 「전송 오류 0 건」은 아니다 — 표본에 안 보이는 오류가 하나 있었다.** `Quotes.page` 는
전송·OAuth 오류를 **제한 재시도 안에서 흡수**하므로 재시도가 성공하면 `fetch_error` 관측이
남지 않는다. 이 런에는 그런 사건이 1 건 있었다 —
`CP3-PR1-M2-brackets.json:absorbed_transport_errors_count=1` ·
`CP3-PR1-M2-brackets.json:absorbed_transport_errors[0].error=auth_http_or_json_error` ·
`CP3-PR1-M2-brackets.json:absorbed_transport_errors[0].started_kst=2026-10-12 15:45:05.000335+09:00`.

그 때문에 **15:45 경계의 +5 초 조회가 실제로는 +7.248 초에 나갔다** —
`CP3-PR1-M2-brackets.json:probes_shifted_past_scheduled_offset[0].scheduled_offset_s=5` →
`CP3-PR1-M2-brackets.json:probes_shifted_past_scheduled_offset[0].actual_offset_s=7.248`
(격자를 벗어난 조회는 이 1 건뿐 —
`CP3-PR1-M2-brackets.json:probes_shifted_past_scheduled_offset_count=1`).
`late_tolerance_s` 는 2 인데 이 조회는 거부되지 않았다 — 그 가드는 **예정 시각으로 자기 전에**
한 번만 보고, 재시도로 밀린 시각은 다시 보지 않는다.

⚠ **단 이것은 §1.2 의 δ 수치를 바꾸지 않는다.** 15:45 경계의 **첫 발견은 +1 초 조회**였으므로 그
경계의 상한은 +1 초 봉에서 나왔고, 밀린 조회는 두 번째 관측이다. 2 봉(67 경계) 중에는 격자를
벗어난 조회가 없다.

즉 원천 `summary.json` 의 `censored_or_errors` = 10 은 **오류 10 건이 아니라 「거래가 없어서 행이
존재하지 않은 분」 10 건**이다. 이것은 §2 의 마감 판정과 같은 사실이다.

### 1.4 δ/G 제안

**먼저 δ 의 운영 의미를 정의한다** — 그러지 않으면 「전형적 지연」은 쓸 데가 없는 수다. 제안하는
의미는 **생산자의 첫 폴링 시각**이다: 봉 경계 `m` 뒤 `m+δ` 에 처음 조회하고, m+1 원시 행이 없으면
`m+G` 까지 재폴링한다. 그러면 δ 는 **「첫 폴링이 성공할 비율」과 「매 분 결정이 늦는 시간」의
교환비**가 된다.

**이 날 직접 측정된 두 격자점**(프로브가 실제로 그 offset 에 요청을 쐈으므로 추론이 아니다):

| 첫 폴링 offset | 첫 폴링 성공 | 재폴링 필요 |
|---|---|---|
| **+1.0 초** | `CP3-PR1-M2-brackets.json:first_poll_success.at_offset_1s_succeeded=343` / `CP3-PR1-M2-brackets.json:first_poll_success.at_offset_1s_of_boundaries=410` = `CP3-PR1-M2-brackets.json:first_poll_success.at_offset_1s_pct=83.66` % | `CP3-PR1-M2-brackets.json:first_poll_success.needed_a_second_poll=67` |
| **+5.0 초** | 재폴링 67/67 성공 (`CP3-PR1-M2-brackets.json:first_poll_success.second_poll_at_offset_5s_succeeded=67`) | `CP3-PR1-M2-brackets.json:first_poll_success.boundaries_still_unresolved_after_offset_5s=0` |

**δ 제안값 = 1.2 초** (첫 폴링 1 회 + 늦은 분만 재폴링).

- 근거: +1 봉 상한 p50 1.107809 초 · 전체 p50 1.110636 초이고, **+1.0 초 폴링이 83.66 % 에서
  성공**한다. 즉 제안 운영에서는 **약 16 % 의 분만 재폴링**하면 된다(이 날 기준).
- ⚠ **1.2 초는 +1 봉의 p95 `CP3-PR1-M2-brackets.json:upper_bound_s_first_offset_mode.p95=1.240584`
  보다 작다.** 즉 1 봉 안에서도 첫 폴링이 확실하지 않다. 재폴링을 **반드시** 갖춰야 하고, δ 를
  단독 대기 시간으로 쓰면 안 된다.
- **더 큰 δ 도 합리적 후보다(역시 제안):** δ ≈ 1.8 초(+1 봉 max 1.765964 초 위)로 올리면 1 봉
  전체가 첫 폴링에서 잡히지만 **모든 분의 결정이 0.6 초 더 늦는다**. 반대로 δ 를 +5 초까지 올리면
  재폴링이 거의 사라지는 대신 **매 분 5 초**를 낸다. ⚠ 이 날의 격자는 **+1.0 과 +5.0 두 점만**
  측정했으므로 **그 사이의 어떤 δ 도 성공률이 측정되지 않았다** — 1.2 나 1.8 의 성공률은 상한
  분포에서 읽은 추정이다.
- ⚠ **참값은 이보다 작을 수 있다.** 상한은 수신 시각이고 343 개는 하한이 없다. 이 측정은 δ 를
  **위에서만** 묶는다.
- 계획 §2 2 에 따르면 이 지연은 `as_of_ms` 도장 **전**이라 tenant 의 800 ms 예산 **밖**이다. 따라서
  δ 는 예산 위반이 아니라 **결정 지연**이다.

**G (`missing_no_successor` 타임아웃) 제안값 = 10 초.**

- 하한 제약: 관측된 최대 완성 지연이 5.345897 초이고, **410/410 경계가 +5 초 조회까지 전부
  해소**됐다(세 번째 조회에서 처음 보인 경계 0 건). G 가 5.35 초 이하면 이 날 실제로 완성된 봉을
  버렸을 것이다.
- 상한 제약: G 는 다음 분 경계와 겹치면 안 되므로 60 초보다 충분히 작아야 한다.
- 왜 5.35 가 아니라 10 인가: ① 관측 최대값에 **딱 붙이면** 표본 하나가 경계에 서 있는 꼴이고,
  ② 늦는 봉의 비율이 **시각에 따라 바뀐다** — 09 시대 `CP3-PR1-M2-mechanism.json:late_mode_by_hour.h09.late_pct=3.3` %
  대 11 시대 `CP3-PR1-M2-mechanism.json:late_mode_by_hour.h11.late_pct=23.3` % ·
  15 시대 `CP3-PR1-M2-mechanism.json:late_mode_by_hour.h15.late_pct=25.0` %. 즉 **하루치 최대값은
  모든 장세의 최악값이 아니다.**
- ⚠ **(5.35, 15] 초 구간에 대해 이 표본은 무정보다.** +15 초 조회는 §1.3 의 구조적 부재 10 건에만
  쏘였고 전부 부재였다. G=10 은 그 무지 구간 안에 있고, **그 구간에서 무엇이 관측됐다고 주장하지
  않는다.**
- 오류 비대칭: G 가 작으면 완성될 봉을 **조용히** 버린다(B3 에서 짝 없는 오프라인 레코드로만
  드러난다). G 가 크면 그 분의 건너뛰기 결정이 최대 G 만큼 늦는데, 다음 경계 전이면 해롭지 않다.
  그래서 **큰 쪽으로 틀리는 것이 안전하다.**

**이 두 값은 운영자 검토용 제안이다.** 프로브 자신도 자동 확정을 거부했다(원천 `summary.json` 의
`delta_G` 필드가 「derive after inspection …; no automatic bound claim」). PR-2 가 이 값을 config 로
받아야 하며, 이 문서는 코드에 박는 것을 승인하지 않는다.

### 1.5 늦는 봉의 원인 — 「조용한 분」 가설은 **약하게만** 지지된다

가설: 분 `m` 의 원시 행은 그 분에 **체결이 생겨야** 존재하므로, 늦음은 브로커 지연이 아니라
**첫 체결까지의 시간**이다. 거래량으로 본 교차 검증:

- +1 초 봉 중앙 거래량 `CP3-PR1-M2-mechanism.json:volume_of_boundaries_first_seen_at_plus_1s.median=339.0`
  (n `CP3-PR1-M2-mechanism.json:volume_of_boundaries_first_seen_at_plus_1s.n=343`)
- +5 초 봉 중앙 거래량 `CP3-PR1-M2-mechanism.json:volume_of_boundaries_first_seen_only_at_plus_5s.median=278.0`
  (n `CP3-PR1-M2-mechanism.json:volume_of_boundaries_first_seen_only_at_plus_5s.n=67`)
- 비 `CP3-PR1-M2-mechanism.json:median_volume_ratio_early_over_late=1.219`

**해석(측정 아님)**: 방향은 가설과 같지만 1.22 배이고 두 분포가 크게 겹친다(이르게 보인 봉의
최소 거래량이 늦게 보인 봉의 최대 거래량보다 작다). 그래서 **거래량만으로는 늦음을 설명하지
못한다**. 반면 시간대 의존성은 뚜렷하다(§1.4 의 3.3 % → 23.3 %). 늦음이 뭉치지는 않는다 —
최장 연속 `CP3-PR1-M2-mechanism.json:longest_late_run=3` 분.

### 1.6 G 가 발동하는 봉은 이 날 **둘**이다 (둘 다 마감 구간)

연속 세션 08:45–15:34 의 기대 분 수
`CP3-PR1-M2-mechanism.json:continuous_session_minutes_0845_to_1534_expected=410` · 실제 봉이 있는 분
`CP3-PR1-M2-mechanism.json:continuous_session_minutes_with_a_parsed_bar=410` · 빠진 분
`CP3-PR1-M2-mechanism.json:continuous_session_minutes_missing_a_bar=[]` →
`CP3-PR1-M2-mechanism.json:no_missing_bar_0845_1534=true`.
즉 **08:45–15:34 에는 봉이 빠진 분이 없다.**

⚠ **그것은 「G 가 발동하지 않는다」와 다르다.** G 는 봉이 빠졌을 때가 아니라 **m+1 후속 행이
없을 때** 발동한다. 그리고 마지막 연속 봉 15:34 의 후속(15:35)은 **부재**다(§2). 후속 행이 없는
봉을 전수로 세면 **둘**이다 —
`CP3-PR1-M2b-closing.json:bars_without_raw_m_plus_1_successor_count=2`:

| 봉 | 없는 후속 |
|---|---|
| `CP3-PR1-M2b-closing.json:bars_without_raw_m_plus_1_successor[0].bar=15:34` | `CP3-PR1-M2b-closing.json:bars_without_raw_m_plus_1_successor[0].missing_successor=15:35` |
| `CP3-PR1-M2b-closing.json:bars_without_raw_m_plus_1_successor[1].bar=15:45` | `CP3-PR1-M2b-closing.json:bars_without_raw_m_plus_1_successor[1].missing_successor=15:46` |

(`CP3-PR1-M2-mechanism.json:g_fires_on_two_closing_bars_see_m2b_artifact=2`. 이 날 원시 분 집합과
파싱 봉 집합이 같으므로 — `CP3-PR1-M2b-closing.json:raw_minute_set_equals_parsed_bar_set=true` —
파싱 봉으로 센 이 집합이 원시 행 기준 집합과 같다.)

**정정**: 앞 판은 「G 의 비용은 이 날 0」이라고 적었는데 틀렸다. 정확히는 **연속 세션(08:45–15:34)
구간에서 G 가 발동하는 봉은 없고, 마감 구간에서 두 봉에 발동한다.** 그 둘은 둘 다 §2 의 처분
대상이므로 **G 의 값이 아니라 마감 완성 규칙이 다룬다** — 15:45 는 G 를 아무리 키워도 후속이
오지 않는다. 다른 장세에 무거래 분이 생기면 그때 비로소 G 값 자체가 비용을 만든다.

## 2. M2b — 마감 구간 판정: **「세션 종료 시각 경과」를 써야 한다**

15:30–15:46 의 원시 분은 **여섯 개**뿐이다
(`CP3-PR1-M2b-closing.json:raw_minutes_15_30_to_15_46_count=6`):
`CP3-PR1-M2b-closing.json:raw_minutes_15_30_to_15_46[0].minute=15:30` 부터
`CP3-PR1-M2b-closing.json:raw_minutes_15_30_to_15_46[4].minute=15:34` 까지 연속 다섯 개, 그리고
**열 분을 건너뛴**
`CP3-PR1-M2b-closing.json:raw_minutes_15_30_to_15_46[5].minute=15:45` 하나다.

- **15:35 이후 원시 행이 있는가 — 있다.** 단 하나,
  `CP3-PR1-M2b-closing.json:raw_minute_labels_at_or_after_15_35[0]=15:45`
  (`CP3-PR1-M2b-closing.json:raw_row_at_or_after_15_35_exists=true`). 그 행의 첫 관측은
  `CP3-PR1-M2b-closing.json:raw_minutes_15_30_to_15_46[5].first_seen_kst=2026-10-12 15:45:01.134899+09:00`
  — 경계 뒤 약 1.13 초로 **§1.2 의 +1 초 봉과 같다**. 즉 마감 단일가 결과 행은 늦게 오지 않는다.
- **15:35–15:44 는 행이 아예 없다** —
  `CP3-PR1-M2b-closing.json:raw_minutes_15_35_to_15_44_exist=[]`. §1.3 의 검열 10 건과 같은 사실이다.
- 당일 마지막 원시 분 `CP3-PR1-M2b-closing.json:last_raw_minute_of_day=15:45` · 당일 원시 분 총
  `CP3-PR1-M2b-closing.json:distinct_raw_minutes_of_day=411` · 파싱된 봉
  `CP3-PR1-M2b-closing.json:parsed_bars=411`(원천 `m4-today-parser.json` 의 `full_rows` = 411 ·
  `incremental_rows` = 411 · `different_minutes` = 빈 배열과 일치).

### 2.1 마지막 봉의 후속(15:46)은 **관측되지 않았다** — 측정이 아니라 구조적 추론이다

⛔ **이 절의 앞 판은 틀렸다. 독립 리뷰(PR #896, HIGH)가 잡았고 여기서 정정한다.**
앞 판은 「15:45 경계 뒤 약 2 분 55 초를 더 관측했는데 15:46 행은 오지 않았다」고 적었다. 그 2 분
55 초는 **당일 데이터를 본 시간이 아니다** — 마지막 수신
`CP3-PR1-M2b-closing.json:source.last_response_any_date_received_kst=2026-10-12 15:47:55.691185+09:00`
은 **다른 날짜를 조회한 장후 시드 호출**의 응답이었고, 내 분석 스크립트가 조회 날짜를 가리지 않고
최대값을 취해 그 시각을 당일 관측으로 잘못 돌렸다(스크립트 수정 + 필드 분리 완료).

**실제로 당일(`FID_INPUT_DATE_1=20261012`)을 조회한 마지막 응답은**
`CP3-PR1-M2b-closing.json:source.last_response_target_date_received_kst=2026-10-12 15:45:21.713421+09:00`
이다 — 15:45 경계 뒤
`CP3-PR1-M2b-closing.json:source.observed_seconds_past_last_parsed_bar_boundary=21.713` 초.
(당일 조회 응답 `CP3-PR1-M2b-closing.json:source.responses_with_rows_target_date=524` 건 / 전체
`CP3-PR1-M2b-closing.json:source.responses_with_rows_any_date=664` 건.)

**그리고 15:46 경계는 아예 표본되지 않았다.** 설정
`CP3-PR1-M2b-closing.json:source.sample_end_from_config=15:46:00` 이고 `sample()` 의 루프 조건이
`minute < end` 이므로 마지막 경계는 15:45 다 —
`CP3-PR1-M2b-closing.json:successor_boundary_was_sampled=false`.

그래서 `CP3-PR1-M2b-closing.json:successor_raw_row_seen_within_observation_window=false` 는
**공허하다**: 관측이 끝난 15:45:21.7 에는 15:46 분이 **아직 시작조차 하지 않았다**. 부재는
표본 창의 결과이고 행이 오지 않았다는 관측이 아니다 —
`CP3-PR1-M2b-closing.json:successor_absence_is_structural_inference_not_measurement=true`.

**해석(측정 아님)**: 15:46 행은 존재할 수 없다. 근거는 관측이 아니라 **런타임 달력의 세션 창**이다 —
`CP3-PR1-M2b-closing.json:session_window_from_runtime_calendar.calendar_version=krx-2026.09.1` 의
선물 CONTINUOUS 창이
`CP3-PR1-M2b-closing.json:session_window_from_runtime_calendar.start=08:45` ~
`CP3-PR1-M2b-closing.json:session_window_from_runtime_calendar.end=15:45` 이고, 마지막 파싱 봉이
바로 그 종료 분이며(`CP3-PR1-M2b-closing.json:session_window_from_runtime_calendar.last_parsed_bar_is_session_end_minute=true`)
후속 15:46 은 **세션 밖**이다
(`CP3-PR1-M2b-closing.json:session_window_from_runtime_calendar.successor_is_outside_session=true`).
세션이 끝난 분에는 체결이 없고, 체결이 없으면 원시 행이 없다.

### 2.2 판정

계획 §3.3 「장 마감」은 **후속 행 규칙을 쓸 수 없고, 「세션 종료 시각 경과」를 마지막 봉의 완성
조건으로 써야 한다.** 계획이 예상한 것보다 **구멍이 둘**이다:

1. **봉 15:34 — 측정됨.** 후속 `15:35` 행이 단일가 구간이라 부재이고, **그 경계는 세 offset 전부
   조회해 세 번 다 부재를 확인했다**(§1.3). m+1 규칙을 글자대로 쓰면 이 봉은
   `missing_no_successor` 로 건너뛰어진다. (⚠ 계획 §3.3 이 예상한 바로 그 경우다.)
2. **봉 15:45 — 측정이 아니라 추론.** 후속 `15:46` 경계는 **표본되지 않았다**(§2.1). 그러므로
   「15:46 행이 오지 않았다」는 이 실행의 **관측이 아니다**. 그런데도 이 봉이 m+1 규칙으로 완성될 수
   없다고 말할 수 있는 근거는 둘이고, 둘 다 관측 밖에 있다:
   - **계획 §3.3 자신의 규칙**(계획 §3.3 의 「완성 판정은 원시 행으로」 항목 — 「봉 m 은 원시 응답에 m+1
     시각 행이 있을 때 완성이다」, 그리고 그 처분을 적은 같은 절의 「장 마감」 항목; 행 번호는 계획 v5 에서
     밀렸으므로 항목 이름으로 인용한다): 15:45 는 거래일
     마지막 봉이므로 그 조건을 만족시킬 행이 **미래에 올 수 없다**.
   - **런타임 달력의 세션 창**(§2.1): 세션이 15:45 에 끝나므로 15:46 은 세션 밖이고 체결이 없다.

⚠ **두 번째가 더 무겁고, 완화로 해결되지 않는다.** 1 번은 「후속 행」의 정의를 `m+1` 에서 「`m` 보다
**엄격히 뒤**인 원시 행」으로 넓히면 15:45 행이 15:34 를 완성시켜 해결된다. 2 번은 그 완화로도
해결되지 않는다 — 뒤에 올 행이 없다. 그러므로 **세션 종료 시각 경과 규칙은 선택이 아니라 필수**이고,
생산자는 그 뒤 기록을 멈춘다. ⚠ 이 결론은 **계획의 규칙 + 달력**에서 나오며, 15:46 을 관측해서
얻은 것이 아니다. 관측으로 확정하려면 `sample_end` 를 세션 종료 뒤로(예 15:50) 늘린 새 실행이
필요하다 — 후속 실행의 과제로 남긴다.

**해석(측정 아님)**: 15:35–15:44 의 행 부재는 단일가 호가 접수 구간이라 체결이 없기 때문으로 읽는
것이 자연스럽다. 이 실행이 관측한 것은 **행의 부재**이고 거래소의 구간 정의를 확인한 것은 아니다.

## 3. M4 — Parquet 대조: 분류와 **예상하지 못한 날짜 결함**

### 3.1 방법 — 오프라인 재생이고, 프로브 자신의 기록으로 검증했다

REST 쪽은 프로브가 `requests.jsonl` 에 남긴 **원시 `output2` 행을 그대로 다시 `parse_ohlcv` 에
넣어** 재생했다(네트워크 0). Parquet 쪽은 `minute_probe.seed_and_compare` 와 **같은**
`ParquetMarketDataStore` 경로로, `run.json` 의 `data_root` 를 써서 읽었다.

재생이 프로브의 관측과 같은지 **날마다 검증**했다 — 파싱 행 수 · Parquet 행 수 · 차이 분 집합 셋이
모두 일치해야 통과다. 결과
`CP3-PR1-M4-parquet-classification.json:replay_faithful_all_days=true` ·
`CP3-PR1-M4-parquet-classification.json:replay_mismatches=[]`
(세션 `CP3-PR1-M4-parquet-classification.json:sessions_walked=59` 전부).

### 3.2 분류

Parquet 행이 있는 날 `CP3-PR1-M4-parquet-classification.json:sessions_with_parquet_rows=25` ·
Parquet 행이 0 인 날 `CP3-PR1-M4-parquet-classification.json:sessions_with_zero_parquet_rows=34`.

| 분류 | 분 수 |
|---|---|
| **REST 에만 있는 분** | `CP3-PR1-M4-parquet-classification.json:classification_totals.rest_only=597` |
| **Parquet 에만 있는 분** | `CP3-PR1-M4-parquet-classification.json:classification_totals.parquet_only=52` |
| **양쪽에 있고 값이 다른 분** | `CP3-PR1-M4-parquet-classification.json:classification_totals.both_present_different_values=51` |

**어느 열이 다른가 — 전부 다르다.** 51 건 중 `open` ·`high` ·`low` ·`close` 가 **51 건 전부**,
`volume` 이 50 건에서 다르다:
`CP3-PR1-M4-parquet-classification.json:differing_columns_totals.open=51` ·
`CP3-PR1-M4-parquet-classification.json:differing_columns_totals.close=51` ·
`CP3-PR1-M4-parquet-classification.json:differing_columns_totals.volume=50`.

⚠ **다섯 열이 동시에 다르다는 것은 파서 파라미터 차이의 모양이 아니다** — 반올림이나 거래량 문턱
차이는 일부 열·일부 분만 건드린다. 값이 다른 날은 둘뿐이다: `2026-10-08`
(`CP3-PR1-M4-parquet-classification.json:per_day[0].both_present_different_values=41`) 과
`2026-10-07`(`CP3-PR1-M4-parquet-classification.json:per_day[1].both_present_different_values=10`).

### 3.3 ⭐ 왜 다른가 — Parquet 파티션이 **전 거래일**의 세션을 담고 있다

가정 없이 물었다: **각 A05611 Parquet 행과 같은 시·분에서 다섯 열이 완전히 일치하는 REST 날이
어느 날인가.** 「전날일 것」을 전제하지 않고 재생된 모든 날에 대해 찾았고, 「전 거래일」 여부는
tenant 달력(`config/tos_runtime/cp3-setup-d-long/calendar.yaml`)의 휴장일 집합으로 판정했다.

| 관계 | 행 수 |
|---|---|
| **전 거래일**의 같은 분과 완전 일치 | `CP3-PR1-M4-crossday-match.json:verdict_totals.previous_trading_day_same_minute=77` |
| 자기 날의 같은 분과 완전 일치 | `CP3-PR1-M4-crossday-match.json:verdict_totals.own_day_same_minute=113` |
| 어느 REST 날과도 불일치 | `CP3-PR1-M4-crossday-match.json:verdict_totals.no_rest_match=26` |

**`other_day_same_minute` 는 0 건이다**(그 키가 집계에 없다). 즉 **날이 어긋난 행은 예외 없이
「바로 전 거래일」**이고, 이것은 내가 산문으로 주장한 것이 아니라 달력으로 판정된 값이다.

예: `CP3-PR1-M4-crossday-match.json:per_parquet_day[0].parquet_day=2026-10-08` 파티션의 41 행은
전부 `CP3-PR1-M4-crossday-match.json:per_parquet_day[0].previous_trading_day=2026-10-07` 의 같은
분과 일치한다 — `CP3-PR1-M4-crossday-match.json:per_parquet_day[0].relations.previous_trading_day_same_minute=41`.
반면 `CP3-PR1-M4-crossday-match.json:per_parquet_day[2].parquet_day=2026-10-06` 파티션의 108 행은
**자기 날**과 일치한다 — `CP3-PR1-M4-crossday-match.json:per_parquet_day[2].relations.own_day_same_minute=108`.

**그래서 어긋남은 균일한 시프트가 아니다 — 섞여 있다.** 같은 세션이 두 파티션에 동시에 들어 있는
것도 확인했다: `day=2026-10-07` 파티션 18 행 중 **17 행이 `day=2026-10-06` 파티션의 같은 분과
바이트 동일**하다 —
`CP3-PR1-M4-params-and-duplication.json:cross_partition_duplication[0].shared_clock_minutes=17` ·
`CP3-PR1-M4-params-and-duplication.json:cross_partition_duplication[0].byte_identical_at_shared_minutes=17`,
남은 한 행은 `CP3-PR1-M4-params-and-duplication.json:cross_partition_duplication[0].later_minutes_absent_from_earlier=["14:25"]`
(10-06 파티션에 빠져 있는 10-06 봉이다). 반면 `day=2026-10-08` 은 `day=2026-10-07` 의 복제가
**아니다** —
`CP3-PR1-M4-params-and-duplication.json:cross_partition_duplication[1].byte_identical_at_shared_minutes=0`
(공유 분 `CP3-PR1-M4-params-and-duplication.json:cross_partition_duplication[1].shared_clock_minutes=10`).

`no_rest_match` 26 건은 전부 7 월 파티션이고, 그 날짜의 REST 재조회는 A05611 행을 0 건 돌려줬다
(상장 전/무거래로 읽는 것이 자연스럽다 — **해석(측정 아님)**).

### 3.4 계획 §3.3 가정에 대한 판정: **시험 가능한 범위에서는 지지, 그러나 M4 설계는 교란됐다**

계획 §3.3 은 「기존 Parquet 이 같은 두 env 값(`FID_HOUR_CLS_CODE` 60 · `KIS_MINUTE_BAR_MIN_VOLUME`
10)으로 만들어졌다는 것은 **가정**이고 M4 가 그것을 시험한다」고 적었다. 세 조각으로 나눠 답한다.

1. **거래량 문턱은 지지된다.** A05611 Parquet 전체
   `CP3-PR1-M4-params-and-duplication.json:min_volume_pin_test.parquet_rows_total=277` 행
   (`CP3-PR1-M4-params-and-duplication.json:min_volume_pin_test.distinct_days=57` 일) 중 핀
   `CP3-PR1-M4-params-and-duplication.json:min_volume_pin_test.pinned_min_volume=10` 미만인 행이
   `CP3-PR1-M4-params-and-duplication.json:min_volume_pin_test.rows_below_pinned_min_volume=0` 건이고
   최소 거래량이 정확히
   `CP3-PR1-M4-params-and-duplication.json:min_volume_pin_test.volume_min=10.0` 이다
   (`CP3-PR1-M4-params-and-duplication.json:min_volume_pin_test.consistent_with_pin=true`).
   ⚠ **이것은 일치일 뿐 증명이 아니다** — 더 **높은** 문턱도 같은 0 건을 만든다. 배제되는 것은
   **더 낮은** 문턱이다.
2. **값 일치는 날이 맞는 곳에서 완전하다.** 날이 맞는 113 행은 **다섯 열 전부 완전 일치**한다
   (§3.3 의 `own_day_same_minute`). 가장 큰 표본이 `2026-10-06` 으로, REST
   `CP3-PR1-M4-parquet-classification.json:per_day[2].rest_rows=109` 대 Parquet
   `CP3-PR1-M4-parquet-classification.json:per_day[2].parquet_rows=108` 에서 차이 분이
   `CP3-PR1-M4-parquet-classification.json:per_day[2].diff_total=1` 건(REST 에만 있는 1 분)이고
   값이 다른 분은 `CP3-PR1-M4-parquet-classification.json:per_day[2].both_present_different_values=0`
   이다. 1 분봉 격자에서 108 분이 값까지 같으므로 `HOUR_CLS_CODE` 60 도 같은 방향으로 지지된다.
3. **그러나 51 건의 불일치는 파라미터에 대해 무정보다.** 그 51 건은 **다른 세션의 데이터**이므로
   파서 파라미터 질문을 **판별하지 않는다**. 계획이 설계한 M4(「REST 재파싱 봉 == 기존 Parquet 봉」)는
   10-07·10-08 에서 **파라미터가 아니라 날짜 라벨링을 재고 있었다.**

**정리**: 가정은 **날이 맞는 113 행에서 지지**되고, **불일치 51 건에서는 시험되지 않았다**(교란).
그리고 이 실행은 계획이 묻지 않은 것을 찾았다 — **레거시 A05611 Parquet 의 날짜 라벨은 신뢰할 수
없다.** 이것은 오프라인 대조(§3.6)가 레거시 Parquet 이 아니라 **생산자가 쓴 동결 프레임**을 읽기로
한 결정을 사후적으로 정당화한다.

⚠ **원인은 이 데이터로 정하지 못한다.** 레거시 수집기 코드·빌드 시점 env·실행 로그가 없으므로
「왜 전 거래일이 들어갔는지」는 **UNKNOWN** 이다. 측정된 것은 관계이고 기전이 아니다.

## 4. M3 — ⚠ **다른 월물에서 잰 비용 프록시**

10-12 프로브는 `benchmark()` 에 **도달하지 못했다**(§5). 그리고 A05611 로는 780 창을 **애초에
채울 수 없다**. 그래서 로컬 Parquet 에서 밀집 세션이 긴 유일한 코드인 **full KOSPI200 선물
`101S6000`** 으로 같은 호출을 쟀다 —
`CP3-PR1-M3-offline-benchmark-proxy.json:status=PROXY_MEASUREMENT_DIFFERENT_CONTRACT` ·
`CP3-PR1-M3-offline-benchmark-proxy.json:proxy_symbol=101S6000` ·
`CP3-PR1-M3-offline-benchmark-proxy.json:producer_instrument=A05611` ·
`CP3-PR1-M3-offline-benchmark-proxy.json:proxy_symbol_is_not_the_producer_instrument=true`.

**프로브의 `benchmark()` 와 `seed_capacity` 를 그대로 import 해서** 호출했으므로 재어진 호출은
프로브가 쟀을 호출과 같은 함수다. 라운드
`CP3-PR1-M3-offline-benchmark-proxy.json:benchmark_rounds=3`(프로브 설정값).
시드는 창 충족 규칙대로 거꾸로 쌓아
`CP3-PR1-M3-offline-benchmark-proxy.json:seed_session_count=4` 세션 · 용량
`CP3-PR1-M3-offline-benchmark-proxy.json:seed_capacity=993` (필요
`CP3-PR1-M3-offline-benchmark-proxy.json:vol_window_bars_required=780`), 대상 세션
`CP3-PR1-M3-offline-benchmark-proxy.json:target_session=2026-04-16`.
중복 시각 제거는 `CP3-PR1-M3-offline-benchmark-proxy.json:duplicate_timestamps_dropped_seed=0` 건.

| 프레임 | 행 | 레코드 | 3 회 중 최대 |
|---|---|---|---|
| (a) 창을 막 채운 시드 | `CP3-PR1-M3-offline-benchmark-proxy.json:a_seed_only.rows=1644` | `CP3-PR1-M3-offline-benchmark-proxy.json:a_seed_only.records=1233` | `CP3-PR1-M3-offline-benchmark-proxy.json:a_seed_only.max_s=0.2655322670470923` 초 |
| (b) 시드 + 하루 전체 | `CP3-PR1-M3-offline-benchmark-proxy.json:b_seed_plus_full_day.rows=2055` | `CP3-PR1-M3-offline-benchmark-proxy.json:b_seed_plus_full_day.records=1644` | `CP3-PR1-M3-offline-benchmark-proxy.json:b_seed_plus_full_day.max_s=0.3488136699888855` 초 |

계획 §3.1 은 비용이
`CP3-PR1-M3-offline-benchmark-proxy.json:plan_budget_reference_s=1.0` 초를 넘으면 증분 엔진을
재검토한다고 적었다. **둘 다 그 1/3 이하**이므로 이 프록시 범위에서는 **매 분 배치 재실행을
유지하는 쪽이 지지된다.**

### 4.1 이 프록시의 한계 — 숨기지 않는다

- **다른 상품이다.** `101S6000` 은 full 계약이고 생산자는 mini `A0561x` 로 돈다. 비용은 주로 행
  수에 따르므로 자리 수 추정으로는 쓸 만하지만, **mini 에서의 측정이 아니다.**
- **개장 앵커가 다르다.** 프록시 대상일의 앵커는
  `CP3-PR1-M3-offline-benchmark-proxy.json:open_anchor=OpenAnchor(hour=9, minute=0, source='era-rule')`
  이고 10-12 는 `CP3-PR1-seed-earliest-fill.json:gate.open_anchor_20261012=OpenAnchor(hour=8, minute=45, source='config')`
  다. 진입 창의 위치가 달라 세션당 창 안 봉 수가 같지 않을 수 있다.
- **CPU 경합 아래에서 쟀다.** 측정 시 다른 프로젝트의 Gradle 테스트가 돌고 있었다 —
  `CP3-PR1-M3-offline-benchmark-proxy.json:measurement_conditions.foreign_gradle_processes=6`
  (코어 `CP3-PR1-M3-offline-benchmark-proxy.json:measurement_conditions.cpu_count=16`). 경합은
  시간을 **늘리는** 쪽으로만 작용하므로, 「예산 아래」라는 결론은 **보수적**이다. 반대로 이 값을
  성능의 상한으로 읽어서는 안 된다.
- 레코드 수 < 행 수인 것은 `_inputs_unusable` 생략과 첫 세션 생략 때문이고 계획 §3.1 이 예고한
  거동이다.

## 5. 시드 — 용량 0/780, 그리고 최단 충족일

### 5.1 왜 0 인가

원천 `seed-summary.json` 의 `capacity` = 0 · `required` = 780
(`CP3-PR1-seed-earliest-fill.json:probe_seed_outcome.capacity=0` ·
`CP3-PR1-seed-earliest-fill.json:probe_seed_outcome.required=780`). 프로브는 달력 예산
`CP3-PR1-seed-earliest-fill.json:probe_seed_outcome.calendar_days_budget=90` 일 안에서 거래일
`CP3-PR1-seed-earliest-fill.json:probe_seed_outcome.trading_days_walked=59` 일을
`CP3-PR1-seed-earliest-fill.json:probe_seed_outcome.oldest_day_walked=2026-07-14` 까지 거슬러
갔는데, 밀도 게이트(`CP3-PR1-seed-earliest-fill.json:gate.min_bars_per_day=330`)를 통과한 날이
**단 하루**였다 — `CP3-PR1-seed-earliest-fill.json:probe_seed_outcome.density_passing_days_found=["2026-10-08"]`.

**한 세션짜리 프레임은 구조상 0 밖에 못 낸다**: `seed_capacity` 는 전일 종가가 없는 **가장 이른
세션을 통째로 제외**하므로, 세션이 하나면 셀 것이 남지 않는다. 그래서 90 일을 다 걸어도 0 이고
`RuntimeError("seed window not filled within configured horizon")` 로 끝났다.

⚠ **그 메시지는 아티팩트에 남지 않았다** —
`CP3-PR1-seed-earliest-fill.json:probe_seed_outcome.exception_message_recorded_in_abort_json=false`.
원천 `abort.json` 은 `error_type` = `RuntimeError` 와 **정적 문자열** `stage` 만 담고 있어서, 네 측정
단계 중 어디서 죽었는지도 왜 죽었는지도 말하지 못했다. 이 PR 이 그 결함을 고친다(§7).

측정된 밀도(REST 재조회 기준):

| 세션 | 파싱 봉 | 게이트 통과 | 진입 창 안 봉 |
|---|---|---|---|
| 2026-10-12 | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261012.parsed_rows=411` | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261012.density_pass=true` | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261012.in_entry_window_bars=331` |
| 2026-10-08 | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261008.parsed_rows=411` | 통과 | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261008.in_entry_window_bars=331` |
| 2026-10-07 | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261007.parsed_rows=191` | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261007.density_pass=false` | 165 |
| 2026-10-06 | `CP3-PR1-seed-earliest-fill.json:key_sessions.d20261006.parsed_rows=109` | 미통과 | 93 |

⚠ **10-12 의 411 은 `today-bars.json`(프로브의 1 회 history 파싱)에서 왔다.** 장중 표본 응답을
합쳐 재파싱하면 같은 분이 여러 번(성장 중인 봉으로) 들어가 `_resolve_minute_bars` 의 발산 중복
해소가 분을 떨어뜨리고 **217 행**이 된다. 그 숫자는 그 날의 봉 수가 아니다 — 분석 중 실제로
밟은 함정이라 적어 둔다.

### 5.2 최단 충족일 = **2026-10-15** (10-13 · 10-14 가 게이트를 통과한다는 가정 아래)

진입 창이 완전한 세션은 `CP3-PR1-seed-earliest-fill.json:gate.entry_window_bars_if_complete=331`
봉을 낸다. 가장 이른 세션은 제외되므로 **창 안 세션 세 개**(≈993)가 필요하고, 결국 **게이트를
통과한 날 네 개**가 대상일 **앞에** 있어야 한다. tenant 달력으로 거래일을 걸어 계산한 결과:

| 대상일 | 용량 | 충족 |
|---|---|---|
| `CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[0].target=2026-10-12` | `CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[0].capacity=0` | 아니오 |
| `CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[1].target=2026-10-13` | `CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[1].capacity=331` | 아니오 |
| `CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[2].target=2026-10-14` | `CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[2].capacity=662` | 아니오 |
| **`CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[3].target=2026-10-15`** | **`CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[3].capacity=993`** | **`CP3-PR1-seed-earliest-fill.json:capacity_by_target_date[3].fills=true`** |

→ `CP3-PR1-seed-earliest-fill.json:earliest_seed_fill_date.target=2026-10-15`, 용량
`CP3-PR1-seed-earliest-fill.json:earliest_seed_fill_date.capacity=993` /
`CP3-PR1-seed-earliest-fill.json:earliest_seed_fill_date.required=780`, 쓰이는 날
`CP3-PR1-seed-earliest-fill.json:earliest_seed_fill_date.density_days_used=["2026-10-08","2026-10-12","2026-10-13","2026-10-14"]`.

전제: **10-08 과 10-12 는 측정된 통과**이고 **10-13 · 10-14 는 가정**이다(각 331 봉 기여). 둘 중
하나라도 게이트에 걸리면 그만큼 밀린다. 10-09 는 한글날로 달력상 휴장이다.

### 5.3 롤 블랙아웃 N ≈ 3 거래일

A05611 의 롤 전 밀도(§5.1)는 **직전 월물 만기일(10-08) 하루만** 게이트를 통과한다. 그래서 새
월물이 front 가 된 뒤 게이트 통과일이 네 개 모이기까지 **시드를 채울 수 없는 거래일**이 생긴다 —
`CP3-PR1-seed-earliest-fill.json:roll_blackout_trading_days=["2026-10-12","2026-10-13","2026-10-14"]`
→ `CP3-PR1-seed-earliest-fill.json:roll_blackout_N=3`.

mini 는 **월물**이므로(tenant 달력 `futures_expiry` 의 `months` 가 1..12) 이 창은 **매달 돌아온다**.

⚠ **N=3 은 롤 하나에서 나온 추정이다.** 직전 월물 만기일이 밀집하다는 것(10-08 = 411 봉)과 롤
이후 첫 세 세션이 밀집하다는 것에 의존한다. 만기일이 밀집하지 않은 달에는 N 이 더 커진다.
처분은 계획 §6 의 **열린 운영자 결정**으로 올렸고 이 문서는 **정하지 않는다**.

## 6. 이 실행이 **확립하지 못한 것**

- **δ 의 참값.** 위에서만 묶였다. 343 경계는 하한이 없고, 67 경계는 4 초짜리 구간만 남는다.
  더 촘촘한 offset(예 +0.3/+0.6/+1/+2/+3 초)이 아니면 좁혀지지 않는다.
- **(5.35, 15] 초 구간.** 무정보(§1.4). G=10 은 그 구간 안의 **선택**이고 관측이 아니다.
- **장세 의존성의 범위.** 하루치다. 늦는 봉 비율이 시각에 따라 3.3 %→25 % 로 변하므로 다른
  변동성 국면의 최악값은 모른다.
- **레거시 Parquet 날짜 어긋남의 원인.** UNKNOWN(§3.4).
- **mini 월물에서의 `produce_bars` 비용.** M3 는 프록시다(§4).
- **10-13 · 10-14 의 밀도.** 가정이다(§5.2).
- **15:35–15:44 행 부재의 거래소 측 근거.** 행의 부재만 관측했다(§2.2).
- **15:46 행의 부재.** **관측되지 않았다** — 그 경계는 표본 밖이고(`sample_end` 15:46:00), 당일
  데이터 관측은 15:45:21.7 에 끝났다(§2.1). 세션 종료 뒤까지 표본하는 새 실행이 필요하다.
- **δ 가 +1.0 과 +5.0 초 사이에서 갖는 첫 폴링 성공률.** 두 격자점만 측정됐다(§1.4).

## 7. 도구 결함 하나를 고쳤다 — `abort.json` 이 자기 사유를 말하지 못했다

이 아크에서 실제로 비용을 치른 결함이다. `abort.json` 은 `error_type` 만 담고 `stage` 는 **정적
문자열**이어서, 「시드에서 죽었고 메시지는 `seed window not filled within configured horizon` 였다」를
아티팩트만으로는 알 수 없었다(§5.1). `tools/tos_cp3/minute_probe.py` 가 이제 **실제 단계**와
**예외 메시지**를 적는다.

메시지를 남기면서 모듈의 기존 안전 성질을 약화시키지 않도록, 조회 비밀 두 개를 **치환**한다 —
`Quotes.page` 는 이미 전송·OAuth 오류 텍스트를 고정 토큰으로 줄이고 있고, 이 기록이 그것을
우회하는 통로가 되면 안 된다. 레드 증명을 단계마다 따로 확인했다: `stage` 를 정적 문자열로
되돌리면 `stage` 단언만 실패하고, 치환을 빼면 비밀 단언만 실패한다(두 절이 **독립적으로** 판별한다).

⚠ **치환 범위를 과장하지 않는다**(리뷰 LOW). 치환은 이 프로세스가 들고 있는 **조회 비밀 두 개**
(`KIS_FUTURES_APP_KEY` / `_SECRET`)만 덮고 **bearer 토큰은 덮지 않는다**. 토큰은 `Quotes.page` 의
지역 변수로만 존재하고 그 안에서 난 전송·OAuth 예외는 **이 핸들러에 닿기 전에 고정 토큰 두 개로
축약**되므로 현재 경로에서는 토큰 텍스트가 이 기록에 올 수 없다. 코드 주석도 그 범위로
좁혔다 — `page()` 밖에서 토큰을 품은 텍스트를 던지는 호출자가 생기면 범위를 넓혀야 한다.

테스트: `tests/tools/test_cp3_minute_probe.py::test_abort_records_its_own_stage_and_message`
(hermetic · 네트워크·자격증명 0).

## 8. 재현

분석은 전부 오프라인이다. 스크립트는 레포 밖(비공개 분석 디렉터리)에 두고 지문만 남긴다 —
**이 PR 은 분석 스크립트를 커밋하지 않는다**(일회성 작업이고 레포 표면을 늘리지 않는다).

```bash
# 원천 무결성 (분석 전 필수)
cd ~/.local/state/tos/measure/cp3-pr1-20261012
python - <<'PY'
import hashlib, json
from pathlib import Path
want = json.load(open("sha256.json"))
print([n for n, d in want.items()
       if hashlib.sha256(Path(n).read_bytes()).hexdigest() != d])   # [] 여야 한다
PY

# 분석 (별도 0700 디렉터리, 원천은 읽기만)
cd ~/.local/state/tos/measure/cp3-pr1-20261012-analysis
W=/home/deploy/project/kis_unified_sts
PYTHONPATH=$W $W/.venv/bin/python m2_brackets.py
PYTHONPATH=$W $W/.venv/bin/python m2b_closing.py
PYTHONPATH=$W $W/.venv/bin/python m2_mechanism.py
PYTHONPATH=$W $W/.venv/bin/python m4_parquet_classify.py
PYTHONPATH=$W $W/.venv/bin/python m4_crossday_match.py
PYTHONPATH=$W $W/.venv/bin/python m4_params_and_duplication.py
PYTHONPATH=$W $W/.venv/bin/python m3_offline_benchmark.py $W
PYTHONPATH=$W $W/.venv/bin/python m5_seed_earliest.py $W

# 이 README 의 인용 검사
python tools/tos_evidence_citation_check.py \
  docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md
```

분석 스크립트 sha256 (`~/.local/state/tos/measure/cp3-pr1-20261012-analysis/`):

| 스크립트 | sha256 |
|---|---|
| `m2_brackets.py` | `a0516ec4b20a8628f2486e11b6742a383a06df0a4729f3813e00c2c8d92afbc5` |
| `m2b_closing.py` | `e42f62efa836992d27570892531cc713c6e037eed9612296dccbe7bbd1f7cb30` |
| `m2_mechanism.py` | `22f4805388154b0f53264982b22961b07484838bbe9dd586dae98c7a4aae5ad5` |
| `m4_parquet_classify.py` | `5d30f1f06999c71cbd84b74b9144c9afa2ee88f1124720514da0231cac8e1d78` |
| `m4_crossday_match.py` | `c53f03c16d99fe8e06f23a5d310b1d1de51de72faa7cd076dc6f813b43eda157` |
| `m4_params_and_duplication.py` | `cbdd35513609e28ae9565455dbe40e08b37709607ea3aa88c80a677f3aa18482` |
| `m3_offline_benchmark.py` | `d47f9fac6f2a5f6df9e967531a4cd1b9df70ecb756a85c3a49a9ff9225164724` |
| `m5_seed_earliest.py` | `2528d82bac125f24be53f8f21ba73bf853b1863c4eadcc0430cefae8777c0523` |

## 9. 안전 — 이 분석이 건드리지 않은 것

- **네트워크·KIS 호출 0건.** 전부 기존 아티팩트와 로컬 Parquet 읽기다. 프로브는 재실행하지 않았다.
- **원천 디렉터리 미변경.** 파생 출력은 새 디렉터리
  `~/.local/state/tos/measure/cp3-pr1-20261012-analysis/`(0700)에 썼다.
- **주문 0건.** 원천 `summary.json` 의 `orders` = 0. 이 분석은 주문 경로를 import 하지 않는다.
- **비밀 미기록.** 커밋한 파생 JSON 여덟 개에 토큰·계좌번호·앱키·`msg1` 이 없음을 확인했다.
  원천 `run.json` 의 앱키는 비가역 지문으로만 존재하고 이 문서는 그 값을 옮기지 않았다.
- **공유 venv 미변경.** `pip install` 하지 않고 기존 `.venv` 로만 돌렸다.
