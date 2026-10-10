# CP-3 ③ 실시간 필드 생산자 계획

- 상태: 초안 v1 (2026-10-10) · 저자: 세션 모델 단독(운영자 지시 2026-09-04) · 검토: 운영자
- 상위: kickoff `docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §5 3 ③ ·
  렌더·부팅 경로 계획 `docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md` §2.4–§2.6
- 운영자 결정(2026-10-10, 대화): ③ 착수 수락 · ③ 뒤 첫 실제 genesis 와 band 원천 켜기 승인 ·
  **데이터 원천 = 실전 키 REST 분봉 GET(`FHKIF03020200`)**
- 범위 밖: band 원천 켜기(③ 뒤 별도 PR) · SHORT 상주화 · 체결 비교(B4 포기, kickoff 결정 8)

## 1. 무엇을 만드는가

장중(08:45–15:45 KST)에 mini KOSPI200 선물 front month(`get_front_month_code(product="mini")`, 10-12 부터
`A05611`)의 **완성된 1분봉마다 저널 한 줄**을 append 하는 호스트 프로세스. 한 줄의 모양은 B1a
(`tools/tos_cp3/produce_fields.py`)의 레코드와 같고 다른 것은 셋뿐이다:

| 키 | B1a(오프라인) | ③(실시간) |
| --- | --- | --- |
| `as_of_ms` | 봉 라벨 = OPEN (`derive_as_of_ms`) | **저널에 append 하는 벽시계 시각** (구속 요구, §2) |
| `source_id` | `tos-cp3-b1a/<ver>` | `tos-cp3-live/<ver>` |
| `received_ms` | 없음 | REST 응답을 받은 벽시계 시각 |

`raw_event_id`(`{symbol}:1m:{bar_kst}`, `derive_raw_event_id`)와 열다섯 필드(`FIELD_ORDER`)는 **B1a 와
같은 함수가 만든다** — 그래야 같은 봉에 대해 실시간 줄과 오프라인 줄이 B3(`diff_decisions.py`)의
`raw_event_id` 조인으로 대조된다.

## 2. 구속 요구 (이미 머지된 결정에서 온다 — 이 계획이 바꾸지 않는다)

1. **`as_of_ms` = append 시각.** tenant `critical_input_policy.yaml` 의 열다섯 `max_age_ms` 가 800
   (= 커널 시간 예산 1000 − 지연 한도 4×50, 운영자 결정 2026-10-09, #887)이므로 라벨 도장은 최소
   나이 60,000 ms 로 전부 STALE 이다. 한도를 올리는 것은 배제됐다(tenant README §7.1).
2. **예산 분배.** tenant `marketfeed.yaml` 의 `poll_interval_ms: 400` · `journal_pass_allowance_ms: 100`
   과 함께 append→소비 최악 나이 = 400 + 100 + (append 와 읽기 사이 파일시스템 지연)이다. 생산자 쪽
   계산·네트워크 지연은 **append 이전**이라 이 예산에 들어가지 않는다 — 대신 봉 마감에서 결정까지의
   지연(§5 측정 M2)으로 따로 잰다.
3. **원자적 기록.** `JsonLinesObservationJournal.poll` 은 매번 파일 전체를 다시 읽고 반쯤 쓴 마지막 줄도
   전체 거부한다(`marketfeed/journal.py` 모듈 docstring). 그러므로 매 append 는 **임시 파일 + `os.replace`**
   로 파일 전체를 교체한다(상주 드라이버 `append_observation` 과 PR-C `bootproof_journal.py` 가 같은 꼴).
4. **`as_of_ms` 단조 증가.** 리더는 `after_as_of_ms` 보다 큰 줄만 돌려준다 — 같은/작은 값은 영원히
   소비되지 않는다. 생산자는 직전 줄의 `as_of_ms` 이하가 되면 +1 ms 가 아니라 **그 append 를 거부하고
   로그**한다(시계 역행은 결함이지 보정 대상이 아니다).
5. **부팅 증명 가드(#892) 허용 목록.** `bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES` 는 의도적으로
   비어 있고 「③ 의 PR 이 생산자를 진짜로 만드는 그 PR 에서 접두를 더한다」고 적혀 있다. 접두
   `tos-cp3-live` 를 PR-2 에서 더한다(구분자 규칙상 `source_id` 는 `tos-cp3-live/<ver>`).
6. **설계된 data dir 첫 기록 = ③ 실데이터.** §2.5 의 「`cp3-setup-d-*-data` 에는 ③ 이전에 절대 쓰지
   않는다」를 그대로 지킨다. 첫 genesis 는 PR-3 이후 운영자 지정 세션(승인됨, 날짜는 미정).

## 3. 설계

### 3.1 재사용 — 새 계산 코드를 쓰지 않는다

열다섯 필드의 수학은 **`produce_fields.produce_bars` 를 그대로 호출**해 얻는다. 매 분:

```
frame = 시드 봉(직전 N 세션) ++ 오늘 완성된 봉 전부      # pandas DataFrame, B1a 와 같은 열
produced = produce_bars(frame, symbol=…, strategy=…, contract_spec=…, anchor=08:45)
last = produced.records[-1]                                # 방금 완성된 봉이어야 한다 — 아니면 거부
line = {**last 의 raw_event_id/instrument/fields, as_of_ms=now_ms(), source_id=…, received_ms=…}
```

- **왜 증분 엔진이 아니라 매 분 배치 재실행인가.** `produce_bars` 는 `check()` 를 봉마다 정확히 한 번
  부르는 것으로 레거시의 인과 창(ATR 780 · close 15 · VWAP 30)을 전진시킨다. 같은 함수를 같은
  프레임에 돌리면 마지막 봉의 값은 **정의상** 오프라인 B1a 와 같다 — 증분 구현은 그 동일성을 별도
  테스트로 증명해야 하는 두 번째 구현이다(교훈 「두 구현 동일성은 정규화 AST 대조로」 — 아예 두 번째를
  만들지 않는다). 비용은 하루 ~3–4 세션 × ~400 봉 재생 / 분 — PR-1 에서 실측(M3)하고 1 초를 넘으면
  그때 증분화를 재검토한다.
- 기각: `CandleAccumulator`(`shared/indicators/streaming/candles.py`) — 틱 입력용이고 REST 분봉에는
  불필요. 기각: TOS `transport/kis_quote` — MOCK 봉인·현재가 전용이고 방화벽상 `tools/` 에서 import 불가.

### 3.2 데이터 원천 — `FHKIF03020200` 실전 GET 한 원천으로 시드와 장중

- 엔드포인트 `/uapi/domestic-futureoption/v1/quotations/inquire-time-fuopchartprice`, 파라미터는
  `shared/collector/historical/backfill.py::fetch_minute_async` 의 날짜 지정 형태(`FID_HOUR_CLS_CODE` ·
  `FID_PW_DATA_INCU_YN=Y` · `FID_INPUT_DATE_1`)를 따른다. 재사용 대상: 그 함수의 요청·페이지네이션·
  파싱(필요하면 동기 래퍼만 추가). 토큰은 기존 `_get_token("futures")` 캐시.
- **GET-only.** 실전 계좌 정책(Non-Negotiable)상 허용되는 범위다. 주문 TR 은 import 하지 않는다 —
  PR-2 테스트가 모듈 그래프에 주문 경로(`shared/execution`·`probes_real_order`)가 없음을 고정한다.
- **시드.** 부팅 시 직전 3 거래일(ATR 780 창 ≈ 2.4 세션 + 리플레이 워밍업 60 봉 + 전일 종가 요구)을
  날짜 지정 페이지 조회로 받는다. Parquet(`data/market/futures/minute/`)은 레거시 수집이 10-08 에
  멈춰 끊겼으므로 쓰지 않는다. 시드 결과는 세션 디렉터리에 `seed.parquet` + sha256 으로 남긴다.
- **장중 폴링.** 분 경계 + δ 초에 한 번 조회. 봉 m 은 **응답에 m+1 행이 있을 때만** 완성으로 본다
  (m+1 행이 없으면 다음 초 재조회, 경계 + G 초까지 없으면 그 분은 「무거래」가 아니라 **결측**으로
  로그하고 건너뛴다 — 무거래 봉을 합성하지 않는다). δ·G 는 PR-1 실측값으로 정한다.
- 호출량: 장중 ≈ 1–3 콜/분, 시드 ≈ 수십 콜(5 rps 한도 안).

### 3.3 프로세스와 수명

- 위치: `tools/tos_cp3/live_producer/`(방화벽 바깥 — `shared.*` import 가능, `tos*` import 불가).
  모듈은 크기 예산 범위에 넣는다(`tools/tos_cp3` 의 기존 큰 모듈들처럼 예외로 남기지 않는다).
- 순수 부분과 I/O 분리: `build_line(frame, now_ms, received_ms, prev_as_of_ms) -> dict` 는 순수 함수,
  루프·HTTP·파일 교체는 얇은 바깥 층(스케줄러의 `decide_tick`/`run_forever` 분리와 같은 꼴).
- 기동: PR-C 의 `run_tenant_session.sh` 가 렌더 **전에** 생산자를 띄운다(렌더러는 저널 파일 존재를
  요구한다 → 생산자가 시드 후 빈 저널을 원자적으로 만든 뒤 `READY` 표지를 남긴다) · 세션 종료 시
  같은 trap/`timeout` 감독 아래 함께 멈춘다. 같은 저널을 쓰는 생산자가 둘이면 거부(`flock`).
- 롤: 생산자는 instrument 를 인자로만 받고 스스로 계산하지 않는다 — 래퍼가 상주와 같은 규칙으로 한
  번 계산해 렌더·data dir·생산자에 같은 값을 준다(상주 잎 규칙, 런북 §7).

## 4. PR 분할

| PR | 내용 | 시장 필요 |
| --- | --- | --- |
| **PR-1 프로브** | `FHKIF03020200` 실전 GET-only 측정 도구 + 결과 증거: M1 mini `A0561x` 응답 여부·행 모양 · M2 분 경계 후 m 행이 「완성」(m+1 행 출현)되기까지 초 단위 분포 · M3 `produce_bars` 재실행 시간(시드 3 세션 + 장중 최대) · M4 시드 페이지 수와 전일 행 정합(같은 날 Parquet 가 있는 10-08 이전 날짜로 대조) | **예 — 10-12(월) 장중**, 분리 워크트리(origin/main)에서 |
| **PR-2 생산자** | `build_line` + 루프 + 원자적 writer + `tos-cp3-live` 허용 접두 + 테스트: ① 같은 프레임에서 마지막 줄 필드 == B1a 배치 레코드(바이트) ② `as_of_ms` 단조·역행 거부 ③ m+1 미출현 시 미발행 ④ 반쯤 쓴 파일이 리더에 보이지 않음 ⑤ 주문 경로 import 0 ⑥ 리더(`JsonLinesObservationJournal`) 로 왕복 — 마지막은 `tos/runtime/tests` 쪽 픽스처로(방화벽) | 아니오 |
| **PR-3 배선·첫 세션 준비** | `run_tenant_session.sh` 에 생산자 기동/정지 · 런북 §7.2 갱신 · tenant 콜드 백업 BORN_ON 정합 안내 | 아니오 |
| 첫 실제 genesis | 운영자 지정 날짜에 LONG tenant 세션 1회(승인됨) → M5: append→소비 나이 분포(800 ms 안인지) · 결정 수 · B3 로 같은 날 오프라인 B1a 와 대조(UNRESOLVED 0 목표) | 예 |
| band 원천 켜기 | `2026-10-08-tos-cp3-band-source-wave-plan.md` 의 스위치 — genesis 세션이 깨끗한 뒤 별도 PR(승인됨) | — |

PR-2 는 #892 머지 뒤에 연다(허용 목록이 그 PR 의 모듈에 있다).

## 5. 수용 기준

- [ ] M1–M4 실측이 증거 디렉터리에 sha256 과 함께 있고 δ·G 가 그 값에서 도출된다
- [ ] 같은 프레임에서 ③ 의 필드 == B1a 필드(테스트) — 「같은 함수를 부르니 같다」를 주장으로 두지 않는다
- [ ] 첫 genesis 세션에서 append→소비 나이가 800 ms 를 넘은 관측 수 = 0, 넘으면 원인 기록
- [ ] 같은 세션의 B3 대조에서 UNRESOLVED 0
- [ ] 실전 주문 TR 호출 0 (요청 로그로 증명)

## 6. 열린 위험

- **분봉 완성 판정(M2)이 느리면** 결정 지연이 분 단위로 커진다 — Setup D 는 1분 결정이라 수 초는
  수용, 수십 초면 운영자에게 WebSocket 재검토를 올린다(DUAL-WS: 레거시 `market_ingest` 를 다시 켜면 충돌).
- **mini 코드 응답(M1) UNVERIFIED** — 백필은 `A056xx` 코드로 Parquet 을 만들었으므로 응답할 공산이
  크지만 실측 전에는 가정이다.
- **800 ms 창**: 줄 하나는 append 후 ~800 ms 동안만 신선하다 → 런타임은 그 사이 1–2 패스에서만 그 봉을
  VALID 로 본다. 의도된 동작(봉당 한 결정)이지만 M5 에서 「신선한 패스 0」인 봉 수를 따로 센다.
- 10-12 는 월물 롤 날이다. PR-1 프로브는 `A05611` 로 잰다.
