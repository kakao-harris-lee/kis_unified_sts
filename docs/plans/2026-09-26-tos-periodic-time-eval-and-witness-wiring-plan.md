# 주기적 시간 건강 평가 + KIS 증인 배선 — 후속 계획

- 작성: 2026-09-26 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `f3856576`(#805 머지 직후)
- 요청: 운영자 2026-09-26 「do it」 — #805 §8.1 이 남긴 두 후속(주기 평가 · KIS 증인 배선)의 계획.
- 성격: **계획 문서다. 코드는 넣지 않았다.** 착수는 §6 운영자 확인 후.

## 0. 요약 — 조사가 계획을 바꿨다

1. **주기 평가는 위생이 아니라 결함 수정이다.** `evaluate()` 는 부팅 때 두 번만 돈다(`compose/_wiring.py:388-389`,
   주석 :381-387 「ONGOING health-check cycles ... remain the caller's own job」). `wall_clock_now()` 는 마지막 평가의
   관측치를 돌려주므로(`time/service.py:697-711`) `run` 의 모든 시각이 **부팅 시각에 멈춘다.** 틱 스케줄러는 그 값을
   쓰고(`marketfeed/scheduler.py:347`), `now_ms - last_tick_wall_clock_ms < poll_interval_ms` 이면
   `SKIPPED_INTERVAL`(`:174-178`) — 멈춘 시계에서 그 차는 늘 0 이다. **paper `run` 은 첫 틱 하나만 소비하고 이후 전부
   건너뛴다.** 세션 위상(`calendar/owner.py`)도 같은 값을 읽으므로 **닫힌 시각에 부팅하면 세션이 영영 열리지 않는다.**
   런북 §5 의 「주입 시계로 TICKED」 실측은 주입 시계라서 이 결함을 가렸다.
2. **KIS 증인은 지금 paper 에 배선하면 해롭다.** paper 는 `krx-index-futures` + `SYNTHETIC_FUTURES_ORDER`(주문이 KIS 에
   가지 않음)인데 증인은 주식 전용이다(`recon/witness_kis_config.py:97-115`). 설령 선물 증인이 있어도 합성 주문은
   브로커에 없으니 **모든 시도가 `STALE_RESERVATION`** 이 되어 복구 해제·캐파시티 해제가 **영구 차단**된다
   (`recovery/reconciliation.py:313`, `posttrade/release_consumer.py:640`). 증인 배선은 **주문이 실제로 모의 서버에
   가는 단계(kis-mock 전송 + `nonlive_broker_consuming.admitted`)** 와 함께여야 한다.

→ 이 후속의 착수 범위는 **W1 주기 평가** 와 **W2 C-2 자격증명 단일 소유자(결정됨·미착수)** 이고, 증인 배선(W3)은
전제가 채워질 때까지 **보류**를 제안한다.

## 1. 실측 (main `f3856576`)

| 무엇 | 어디 | 상태 |
|---|---|---|
| 평가 호출 | 부팅 2회뿐(`_wiring.py:388-389`, `rearm` CLI `cli.py:740-741`) | 주기 호출 **없음** |
| 실행 루프 | `dispatch_run`(`compose/_run_dispatch.py:134`) → `TickScheduler.run_forever`(`scheduler.py:392-408`: `while not stop(): tick_once(); sleep(poll_interval)`) | 패스별 훅 없음. `EngineDriver.bind_after_turn` 은 **단일 슬롯**이고 처리된 턴에서만 불리며 이미 exporter 가 점유(`_operations_wiring.py:469-470`) — 평가 자리로 부적합 |
| 평가 1회의 일 | 참조 원천 읽기 — 운영은 `LocalSystemClockReader`(`time/sources.py:118-134`, 로컬 시계만 · 네트워크 없음) · 커널 술어 · **매 사이클 `TIME_HEALTH_SNAPSHOT` 증거 1행**(`service.py:651-655`, 「영수증 없으면 일어나지 않았다」 계약 :647-650) | 비용 작음 · 증거는 매번 쌓임 |
| 증거 크기 | 로컬 부팅 실측: `TIME_HEALTH_SNAPSHOT` 행당 약 **1.8 KB**(페이로드+digest) | 1 s 주기면 86,400 행/일 ≈ **158 MB/일** |
| 중단(suspension) 판정 | `max(0, Δwall − Δmono)`(`service.py:330-356`) — **사이클 간격은 중단이 아니다** | 주기는 자유롭게 정할 수 있음(조사 보고의 「2 s 넘으면 중단」은 틀림) |
| 틱과 평가의 관계 | 틱 간격 판정이 평가 시각으로 계산되므로 **틱 주기 ≥ 평가 주기** | 1 s 틱을 원하면 1 s 평가가 필요 |
| 거래일 신선도 | `MAX_time_conservative_freshness_age_ms: 1000`(paper `time.yaml:32`) · #805 의 `wall_clock_now_if_fresh` | 평가가 틱마다 돌면 ACK 직후 날짜가 대체로 신선 |
| C-2 | `docs/plans/2026-09-23-tos-kis-credential-ownership-decision-c2.md` §4 — 운영자 (C) 확정 2026-09-23, **「구현: 미착수」**(:189) · `tos/runtime/src` 에 `KisCredentialSession` 0건 | 밀폐 테스트로 구현 가능 |
| 증인 설정 | `tos/runtime/config/kis_witness.example.yaml` 만 · paper `kis_witness.yaml` 없음 · 운영 토큰 세션 없음 | W3 전제 |
| 선물 증인 | 체결조회 `VTTO5201R`(`/uapi/domestic-futureoption/v1/trading/inquire-ccnl`) — 프로필 `:770-775` CODE-EVIDENCED · 측정 아티팩트 **0건** · 모의 선물 잔고 TR 은 공식문서(`VTFO6118R`)와 레거시 클라이언트(「모의 미지원」)가 **모순** | 측정 먼저 |

## 2. 결정

### W1 — 주기 평가 (착수)

1. **자리: `TickScheduler.run_forever` 의 매 패스 앞.** `run_forever` 에 주입 인자 `before_pass: Callable[[], None] | None`
   을 추가하고, 컴포즈가 `time_service.evaluate` 를 넘긴다(스케줄러는 시간 서비스를 이미 주입받음 — 새 결합 없음).
   `tick_once` 는 그대로 순수하게 두고 테스트에서 가짜로 몰 수 있게 한다.
2. **주기: §6 운영자 결정 1.** 권고안 **(나)**:
   - (가) 매 패스(= `poll_interval_ms`, paper 1 s) 무조건 — 단순 · 약 158 MB/일.
   - **(나) 세션이 열려 있으면 매 패스, 닫혀 있으면 `time_evaluate_closed_interval_ms`(time.yaml 신설, 권고 60000)** —
     틱은 열린 세션에서만 일어나므로 정확성은 (가)와 같고, 증거는 약 **46 MB/일**(선물 주간 7 h 기준) + 닫힌 시간 약 1천 행.
     닫힌 상태에서 개장을 알아채는 지연은 최대 그 간격. 세션 판정 자체가 평가 시각을 쓰므로, 닫힌 동안에도 평가가
     돌아야 개장을 본다(그래서 「닫히면 멈춤」은 불가).
   - (다) 단일 설정값 `time_evaluate_interval_ms` — 운영자가 한 값으로 고름. 틱 주기가 그 값 이상으로 늘어난다.
3. **평가 실패는 루프를 멈추지 않는다.** 증거 추가 실패 등으로 `evaluate()` 가 던지면 그 패스의 `tick_once` 는 건너뛰고
   (낡은 시각으로 틱하지 않음) 다음 패스에 재시도 — 실패는 기존 비상 로그 관례로 기록. 연속 실패 시 상태는 시간 서비스가
   이미 강등 규칙으로 처리한다(새 판정 없음).
4. **증거 보존(퍼지)은 이 작업이 아니다.** 되돌리기 어려운 데이터 파기라 별도 계획·승인. W1 은 증가율을 문서에 적는다.

### W2 — C-2 `KisCredentialSession` (착수, 결정대로)

C-2 문서 §4 그대로: `transport/kis_mock` 옆에 앱키당 단일 소유자 `KisCredentialSession` 을 두고 주문 전송·시세 인입·
증인에 주입, 증인 Protocol 을 `request_credentials()` 컨텍스트 하나로. **증인 배선 자체는 C-2 문서도 범위 밖**으로
명시했다 — 여기서도 그대로.

### W3 — KIS 증인 배선 (보류 제안)

전제: ① 주문이 모의 서버에 실제로 간다(kis-mock 전송 + `nonlive_broker_consuming.admitted` — 별도 승인) ② 배포 자산에
맞는 증인(선물이면 `VTTO5201R` GET-only 실측 → 선물 증인 구현) ③ W2 ④ paper 좌표(`account`/`instrument` 렌더).
전제 없이 배선하면 §0-2 대로 해제 경로가 영구 차단된다.

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| `bind_after_turn` 에 평가 연결 | 단일 슬롯(exporter 가 점유) · 처리된 턴에서만 불림 — 유휴 패스에서 시계가 다시 멈춘다 |
| 평가를 백그라운드 스레드로 | 이 런타임은 단일 스레드 루프 규율(sqlite 연결 공유) — 경쟁 조건만 늘린다 |
| `wall_clock_now()` 가 단조시계로 외삽 | 신뢰 판정 없이 시각을 만들어 내는 것 — 시간 서비스의 「관측만 노출」 원칙 위반 |
| 스냅샷 증거를 상태 전이 때만 기록 | 「영수증 없으면 일어나지 않았다」(`service.py:647-650`) 계약을 깨고 관측 가능한 상태를 영수증 없이 노출 |
| 합성 전송 그대로 KIS 증인 배선 | §0-2 — 모든 시도 STALE → 해제 영구 차단 |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | `run_forever(before_pass=...)` + 세션 상태별 주기(§6 결정 1) + 평가 실패 시 그 패스 틱 생략 | 가짜 시계로: 두 번째 패스에서 **TICKED**(현 결함 재현 테스트가 먼저 red) · 닫힘→열림을 간격 안에 감지 · 평가 실패 패스에서 틱 0 |
| T-2 | `time.yaml` 키 신설(결정 (나)/(다)일 때) · 로더·예시·paper 값·`_VALUE_PINS` | 설정값 없으면 부팅 거부(기존 named-TBD 규율) |
| T-3 | 컴포즈 배선 + 런북 §5 정정(「주입 시계라서 가려진 결함」) + 실제 시계로 N 초 부팅해 TICKED ≥ 2 실측 | 실 시계 부팅에서 틱이 계속 소비됨 |
| T-4 | C-2 `KisCredentialSession` + 세 소비자 주입 + 증인 Protocol 교체 | C-2 문서의 종료 조건 그대로 |
| T-5 | digest 재도출 · 상위 계획 착지 기록 | 통상 |

**뮤테이션**: `before_pass` 호출 제거 → 두 번째 틱 테스트 red · 닫힌 주기 무시 → 개장 감지 테스트 red · 평가 실패인데도
틱 → red.

## 5. 위험

- **증거 증가**: 권고 (나)로도 약 46 MB/일이 쌓인다. 퍼지 계획 전까지 디스크 여유를 운영자가 확인.
- **T-1 은 틱 소비를 실제로 켠다** — 지금까지 사실상 한 틱만 돌던 paper 가 매 초 틱한다. 합성 주문 경로라 브로커 도달은
  0 이지만, 전략·위험 경로가 처음으로 연속 가동된다(실측 부팅 T-3 에서 확인).

## 6. 운영자 확인

1. **평가 주기**: (가) 매 패스 / **(나) 열림 매 패스 · 닫힘 60 s (권고)** / (다) 단일 값.
2. **범위**: W1 + W2 착수, **W3 증인 배선 보류**(전제 미충족) — 동의 여부.
3. **증거 퍼지**는 별도 계획(데이터 파기 — 되돌리기 어려운 경로)으로 — 동의 여부.
