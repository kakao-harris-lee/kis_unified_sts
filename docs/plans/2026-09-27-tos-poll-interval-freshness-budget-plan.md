# paper 틱 폴링 주기를 신선도 예산 안으로 — 계획 (#807 선택지 1)

- 작성: 2026-09-27 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `f6348b19`(#806 머지 직후)
- 요청: 운영자 2026-09-27 「1번으로 가자, 폴링 주기 줄이는 계획 써줘」 — 이슈 #807 선택지 1.
- 성격: 계획 + 구현(같은 PR). 운영자 처분 §6.1.

## 0. 요약

1. **결함**: `journal` 인입에서 관측이 읽히는 나이의 최악값은 `수집기 지연 + poll_interval_ms + 패스 소요`인데,
   예산은 `MAX_time_conservative_freshness_age_ms − Σ지연 한도 = 1000 − 200 = 800 ms`다. 지금 paper 는
   `poll_interval_ms: 1000` 이라 **패스 직후 도착한 관측은 항상 STALE** 이고, 거부된 관측은 소비 처리되어
   재시도되지 않는다. 리허설 18 건 중 7 건(39 %) 거부(#807).
2. **고치는 것**: paper `poll_interval_ms` 를 **1000 → 400**(권고)으로 줄이고, 이 결합이 다시 조용히 어긋나지
   않게 **`journal` 인입 한정 부팅 거부 가드**를 넣는다 — `poll_interval_ms + journal_pass_allowance_ms` 가 예산을
   넘으면 부팅하지 않는다. 승인값(`time.yaml`)은 건드리지 않는다.
3. **`kis_quote` 는 범위 밖이며 가드도 적용하지 않는다.** 그 어댑터는 `as_of_ms` 를 패스의 신선한 시각 판독값으로
   찍으므로(`transport/kis_quote/adapter.py:43-65, 381`) 위상 문제가 없고, 같은 키가 HTTP 요청 속도를 정하는데 모의
   시세 한도는 **1.0 rps clean · 2.0 rps 스로틀**(P-13, `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:1840-1846`)이라
   800 ms 미만으로 줄이면 스로틀된다.

## 1. 실측 (main `f6348b19`, 호스트 로컬 · 2026-09-27)

| 무엇 | 값 | 출처 |
|---|---|---|
| 신선도 판정 | `source_age + Σdelay_bounds > max_age_bound` → STALE (같으면 FRESH) | `tos/src/tos/time/predicates.py:375` `freshness_verdict` |
| `source_age` | 패스 앞 평가의 `wall_clock_now()` − `as_of` | `marketfeed/time_projection.py:220-238` |
| Σ지연 한도 | 4 키 × 50 = 200 (`_DELAY_BOUND_FIELDS`) | `time_projection.py:109-114` · `config/tos_runtime/paper/time.yaml:22-27` |
| `max_age_bound` | 1000 (VER-002 L1078 · APPROVED 2026-09-04) | `time.yaml:32` |
| 루프 | 패스 → `sleep(poll_interval_ms)` — 주기는 `poll + 패스 소요` | `marketfeed/scheduler.py:418-420` |
| `poll_interval_ms` 의 두 역할 | 루프 sleep(`:420`) + 최소 틱 간격(`SKIPPED_INTERVAL`, `:176`) — `kis_quote` 에게는 HTTP 요청 간격(`transport/kis_quote/config.py:41-51`) | — |
| 패스 소요(40 패스) | `evaluate()` p50 7.8 / max 12.3 ms · `tick_once` TICKED p50 27.0 / max 66.3 ms · 유휴 p50 1.0 / max 1.4 ms | 런북 §5 ④ 진단 + 실 `sleep` |
| 위상 효과 | 추가 0.1 s 후 틱 → 4/4 admitted · 1.2 s 후 틱 → 5/5 STALE | 같은 진단 |
| 90 s `run_forever`, 5 s 마다 관측(`as_of = now − 200`) | 18 소비 · **STALE 7** · NoAction 5 · Proposal 6(전부 `STAGE_DENIED` — venue `max_quantity` null, 의도된 fail-closed) | 같은 진단 |
| 렌더 부팅 증명 관측 | `_JOURNAL_AGE_MS = 1000`(`scripts/tos/render_paper_config.py:160-163`) — 렌더 순간부터 이미 1000 + 200 > 1000 | — |

## 2. 결정

### 2.1 예산식 (journal 인입)

```text
수집기 지연 + poll_interval_ms + 패스 소요  ≤  max_age_bound − Σdelay_bounds   (= 800)
```

런타임이 아는 것은 `poll_interval_ms` 와 (측정된) 패스 소요뿐이다. 그래서 가드는 **런타임 몫**만 강제하고, 남는 폭을
**수집기 여유**로 명시한다:

```text
수집기 여유 = 800 − poll_interval_ms − journal_pass_allowance_ms
```

### 2.2 값 (§6 운영자 확인 1·2)

| 안 | `poll_interval_ms` | 수집기 여유 (allowance 100) | 장중 `TIME_HEALTH_SNAPSHOT` | 비고 |
|---|---|---|---|---|
| 현행 | 1000 | **−300** (가드가 거부) | ≈ 25 k 행 ≈ 45 MB/일 | 결함 |
| **(가) 400 — 권고** | 400 | 300 | ≈ 61 k 행 ≈ **110 MB/일** | 리허설 드라이버(지연 200)를 여유 있게 수용 |
| (나) 250 | 250 | 450 | ≈ 97 k 행 ≈ 175 MB/일 | 여유 크지만 증거 1.6 배 |
| (다) 700 | 700 | 0 | ≈ 36 k 행 ≈ 64 MB/일 | 수집기 지연이 1 ms 만 있어도 STALE — 기각 |

행 수 = 장중 7 h(08:45–15:45) × 1000 / (poll + 유휴 패스 ≈ 10 ms), 행당 ≈ 1.8 KB(#806 계획 §1).

`journal_pass_allowance_ms: 100` — 측정 최악 패스(12.3 + 66.3 = 78.6 ms) 위의 올림. **새 필수 키**(`journal` 일 때만),
예시 파일 `null`(부팅 거부) · paper `100` · `_VALUE_PINS` 고정.

### 2.3 가드

- 위치: `compose/_marketfeed_wiring.py::build_tick_scheduler` — `MarketFeedConfig` 와 `TrustworthyTimeConfig` 를
  **둘 다** 받는 유일한 지점(`:481-486`). 크기 예산(100 줄)을 지키려고 헬퍼 하나로 분리.
- **같은 설정값을 읽는다**: Σ지연은 `time_projection._DELAY_BOUND_FIELDS` 튜플을 그대로 순회한다 — 두 번째 사본을
  만들지 않는다(CLAUDE.md Redis TTL 규칙과 같은 원칙: 신선도 판정과 그 가드가 다른 수치를 읽으면 안 된다).
- 조건: `intake_kind == "journal"` 이고 `poll_interval_ms + journal_pass_allowance_ms > max_age − Σdelay` →
  `MarketFeedConfigError`(세 항과 수집기 여유를 메시지에 적는다).
- **이 가드가 실패하는 구체적 입력**(memory 「가드가 자기가 막는다고 말한 것을 허용한다」 대응):
  - 현 paper: 1000 + 100 = 1100 > 800 → **거부**.
  - 경계: 700 + 100 = 800 → 허용(판정식이 `>` 이므로 같음은 FRESH) · 701 + 100 → 거부.
  - 지연 키 하나를 50 → 150 으로 바꾸면 예산 700 → 400 + 100 은 허용, 650 + 100 은 거부 — Σ 에 네 항이 **모두**
    들어가는지 이것으로 핀.
  - `journal_pass_allowance_ms` 누락 · `null` · `"TBD"` · 0 이하 → 거부.
  - `kis_quote` + 1000 → **허용**(가드 비적용 — §0-3).

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| allowance 없이 `poll ≤ 800` 만 검사 | 800 을 허용하지만 800 에서도 패스 소요만큼 STALE 이 남는다 — 가드가 막는다고 말한 것을 허용 |
| 고정 주기 루프(`sleep(max(0, poll − 패스))`) | `run_forever` 계약·스케줄러 테스트 변경, 패스 초과 시 여전히 allowance 필요 — 이득 수십 ms |
| 저널 파일 변경 감시(이벤트 구동) | #807 선택지 3 — 설계 변경, 이번 범위 아님 |
| 신선도 한도 상향 | VER-002 승인값 — 별도 승인 경로(#807 선택지 4) |
| `kis_quote` 에도 가드 적용 | `as_of` 가 패스 판독값이라 위상 문제가 없고, 800 미만 강제 시 모의 시세 한도(1–2 rps) 초과 |
| 렌더 부팅 증명 관측을 신선하게 | 렌더와 부팅 사이 수 초가 이미 예산 초과 — 고칠 수 없다. 첫 관측은 **TICKED 증명**이지 결정 증명이 아니라고 런북에 적는다 |
| 장중 평가 빈도를 폴링과 분리 | `source_age` 기준점이 마지막 평가라 평가 주기도 예산 안이어야 한다 — 증거는 줄지 않고 복잡도만 는다(#807 선택지 2) |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | 가드 헬퍼 + `journal_pass_allowance_ms` 로더(journal 필수 · named-TBD 거부) | §2.3 입력 전부 테스트 · 뮤테이션 red: 가드 제거 / `>`→`>=` / Σ 에서 항 하나 누락 / `kis_quote` 에 적용 |
| T-2 | paper `marketfeed.yaml` `poll_interval_ms` 400 · `journal_pass_allowance_ms` 100 (주석에 이 계획 인용) · 예시 `null` · `_VALUE_PINS` | 현행 값(1000)이면 부팅 거부되는 것을 테스트로 확인 |
| T-3 | 리허설 재측정 — 같은 진단 + 실 `run_forever` 90 s + 5 s 관측(지연 200) | STALE **0** / N, 평가 행 수 ≈ 패스 수 |
| T-4 | 런북 §4·§5 ④(첫 관측은 항상 STALE — TICKED 증명), `expected_code_digest` 재도출(runtime 소스 변경 — 머지 직전 재확인), INDEX 행, #807 링크 | 통상 게이트(방화벽·lint-imports·completion·spec·contract·citation·size budget·black/ruff/mypy) |

## 5. 위험

- **증거 2.4 배**(45 → 110 MB/일). 디스크 여유 344 GB(2026-09-27) — 수년 치지만 퍼지 계획(별도·미착수)의 입력이 된다.
- CPU: 400 ms 마다 평가 ≈ 8 ms + 유휴 틱 1 ms ≈ 2 %.
- 런타임 패스가 allowance 를 넘는 순간(GC·디스크 정지)의 관측은 STALE — fail-closed 이고 재시도는 없다. 측정은 T-3.
- **2026-09-28 장중 cron 실측은 `f6348b19`(poll 1000)로 돈다** — 수정 전 실시계 기준선이 되고, T-3 과 비교한다.
- `kis_quote` 로 전환하는 배포는 이 값(400)을 물려받으면 안 된다 — 예시 파일과 이 키의 주석에 적는다.

## 6. 운영자 확인

1. **`poll_interval_ms`**: **(가) 400 (권고)** / (나) 250 / 기타.
2. **`journal_pass_allowance_ms: 100`** 신설과 `journal` 인입 한정 부팅 거부 가드 — 동의 여부.
3. 구현은 이 브랜치에서 처분 후 진행 — 동의 여부.

### 6.1 운영자 처분 (2026-09-27)

1. **`poll_interval_ms` = (가) 400.**
2. **`journal_pass_allowance_ms: 100` 신설 + `journal` 한정 부팅 거부 가드** — 동의.
3. **구현은 이 브랜치(PR #808)에서** — 동의.
