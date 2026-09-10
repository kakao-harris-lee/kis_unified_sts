# P0-2 브로커 프로브 — 모의 운영 서버 전달 문서 (2026-09-10)

> **대상**: 모의투자(배포) 서버 운영자. **목적**: VERIFICATION-PROFILE-002 의 브로커 `value_ms: null` 키를 닫기 위한 잔여 프로브 실행 · 산출물을 개발 측으로 돌려보내기.
> 정본은 `docs/runbooks/kis-capability-probes.md`(이하 «런북»)이며, 이 문서는 **지금 남은 것만** 추린 실행 요약이다. 충돌 시 런북이 우선.
> 코드 정본 `tools/broker_probes/registry.py`(프로브 20종) · 캠페인 `docs/broker-profiles/evidence/2026-07-29-p02-t2-campaign/`.

## 0. 한 줄 요약

남은 실행은 **모의(MOCK_VTS) 4건(P-8·P-15→N-15·P-BAL·P-EXT) + 실전 조회(REAL_PROD, GET 전용) 2건(N-16·N-18)**이다. 그 밖에 N-19/P-CA 2건은 코드 미등재로 실행 불가, P-R5 계열은 정책상 영구 금지다. 실주문·실자금 이동은 어디에도 없다.

## 1. 실행 전 확인 (전부 필수)

| # | 항목 | 확인 방법 |
|---|---|---|
| 1 | 체크아웃이 **깨끗하고 커밋이 확정**됐는가 | `git status --short` 비어 있음 · `git rev-parse HEAD` 기록(아티팩트 `repo_commit` 은 실행 코드를 보장하지 않는다 — 작업트리 수정분으로 돌린 적이 있음, 런북 §6.2) |
| 2 | `config/futures_live.yaml::enabled: false` | 주문 계열 프로브는 true 면 `SafetyViolation` 으로 거부 |
| 3 | Redis `futures:live:suspended` 상태 | `redis-cli -n 1 GET futures:live:suspended` |
| 4 | 페이퍼 워커 정지 여부 | P-13(쿼터)·P-14(WS 축출)·P-15/N-15(토큰 재발급)는 가동 시스템을 교란 — 해당 프로브 전에 **정지** |
| 5 | 환경변수(이름만, 값은 셸에서만) | `KIS_FUTURES_APP_KEY/SECRET/ACCOUNT_NO` · `KIS_STOCK_APP_KEY/SECRET/ACCOUNT_NO` · (실전 조회 셸에만) 실전 키. `KIS_TOKEN_CACHE_DIR` 는 무시됨 · 토큰 캐시는 `tools/broker_probes/results/.token_cache` |
| 6 | 계좌 지문 | 모든 아티팩트는 `credentials.account_fingerprint` 를 기록한다 — 첫 실행 후 값을 개발 측에 알릴 것(모의 계좌 식별용). **실전 선물 계좌 지문 불일치**(`00bcc5b3a87b` vs `8304d859b87f`, 2026-08-07 이연)는 이 캠페인으로 해소되지 않는다(해소 절차 `P-R5-PRE --expect-account-fingerprint` 는 실주문 트랙 전용이라 실행 금지) — 운영자 실계좌 확인 사항으로 남긴다(런북 §5.7 ⚠) |
| 7 | 장 시간 | 모의 주문 프로브는 **KRX 선물 정규장 중**(P-8 등) · N-16 은 **18:00–05:00 KST 야간 창** 안에서만 |
| 8 | 안전 모델은 코드가 강제 | 주문 TR `V` 접두만 · 모의 호스트만 · `--confirm` 없이는 브로커 무접촉 · 실전 모듈은 GET+allowlist(POST 경로 자체 없음) — 런북 §2.3 |

명령 공통 접두: 저장소 루트에서 `python -m tools.broker_probes.run <ID> …`. `--list` 로 등재 프로브, `--coverage` 로 커버리지(판본 ① 11키 기준 — §5 주의). 선물 프로브의 `--symbol` 은 **현재 mini 근월물 코드**를 넣는다(예시에 있던 `A05608` 은 2026-08-13 만기 — 런북 `:748`). 근월물 확인 후 이 문서의 `<mini 근월물>` 자리를 채워 실행.

## 2. 실행 목록 (이 순서대로)

| 순서 | 프로브 | 명령 | 선행 | 소요/위험 | 왜 남았나 |
|---|---|---|---|---|---|
| 1 | **P-8** ×5 | `python -m tools.broker_probes.run P-8 --symbol <mini 근월물> --confirm` (기본 `--pace-s 1.1` 유지 · `--symbol` 없으면 즉시 exit 4) | 선물 정규장 · `KIS_FUTURES_ACCOUNT_NO` · P-5 이력 있으면 좋음 | ~10 min/회 · HIGH(모의 정정 주문 발생) | 2026-07-29 5런은 전부 측정 성공이었으나 정리 단계가 결과를 지웠음 → 수정(`4fbf3618`) 후 **재실행 5회 필요**. `protective_request_complete` 의 유일 원천이며 `protection_gap`/`protection_overlap`(인접 키)을 **부분적으로** 정보한다 |
| 2 | **P-15 → N-15** | `python -m tools.broker_probes.run P-15 --confirm` 직후 `python -m tools.broker_probes.run N-15 --symbol <mini 근월물> --trials 1 --confirm` | **앱키 공유 워커 전부 정지**(재발급 소모) | P-15 ~3 min · N-15 ~18 min/trial · HIGH | N-15 4회 전패 기록(`EGW00133`·tokenP 중단) · 재설계본(`PRE_EXISTING` 격리·1200s 창) 미실행 |
| 3 | **P-BAL** (모의) | `python -m tools.broker_probes.run P-BAL --asset stock --env mock --confirm` (런북 §5.6 대상 3종 중 **2번 모의 주식만** — 1·3번은 `--env real` 이라 §2 실전 절차 소관) | 모의 잔고 보유 | ~1 min · LOW | 2026-08-05 예약분 미집행(페이지 크기 실측) |
| 4 | **P-EXT** ×≥5 | `python -m tools.broker_probes.run P-EXT --symbol <mini 근월물> --confirm` | 운영자가 **HTS/MTS 로 수동 모의 주문**을 프로브 대기 중 넣음 · 5회 반복 | ~15 min/trial · MEDIUM | `external_activity_detect` 미실행(운영자 동석 필요) |
| 5 | **N-16** (실전 조회) | 별도 셸: 실전 키 export → `python -m tools.broker_probes.run N-16 --confirm` → 셸 종료 | 야간 창 18:00–05:00 KST · **실전 주식 포지션 보유 상태** · 운영자 승인 | 1 call · MEDIUM | 야간 재실행 필요(보유 상태에서) |
| 6 | **N-18** (실전 조회) | 같은 실전 셸에서 `python -m tools.broker_probes.run N-18 --confirm` | 운영자 승인 | 3 calls · MEDIUM | 미실행 |
| — | **N-19 → P-CA** | **실행 불가** | — | — | `registry.py` 에 **미등재**(2026-08-07 정의만 · diff 초안) — 개발 측이 먼저 등재해야 함. 실행하지 말 것 |
| — | **P-R5 / P-R5-PRE** | **실행 금지** | — | — | 실전 주문 = 정책 영구 차단(preflight 판정 `ABORT_ORDER_AVAILABLE_ZERO_OR_UNREADABLE` 은 terminal · «입금 대기» 아님). P-R5-PRE 도 실전 주문 트랙 전용이라 돌리지 않음 |
| (선택) | P-11 | `… P-11 --asset stock --symbol 005930 --confirm --allow-fill` | 시장가 체결 · 포지션 남음 · **맨 마지막** | ~15 min · HIGH | 재측정 원하면 — 필수 아님 |

**실전 조회 규칙(런북 §5.4)**: 실전 키는 별도 셸에만 · 그 셸에서 모의 프로브 실행 금지 · 실행 후 셸 종료. 반대 방향(실전 키 상태로 모의 주문 프로브)은 코드가 모의 호스트를 강제해 실주문이 날 수 없다.

## 3. 중단 규칙

- 페이싱(`--pace-s 1.1`)을 적용했는데도 `초당 거래건수를 초과` 또는 `EGW00201` 이 나오면 **재시도하지 말고** 중단·보고(런북 §5.5). 한도 가정이 틀렸다는 뜻.
- `SafetyViolation`·`assert_*` 거부는 설정/환경 문제 — 우회 플래그 없음. 그대로 보고.
- 미체결 잔여 주문(P-8 신/구 ODNO, P-2)은 프로브가 정리하지만, 남으면 HTS 에서 수동 취소 후 아티팩트 `note` 에 기록.

## 4. 산출물과 반환

1. 아티팩트: `tools/broker_probes/results/{ID}-{YYYYMMDDTHHMMSS}Z.json` — **gitignored**. 실행 후 전부를 `docs/broker-profiles/evidence/2026-09-XX-p02-t3-campaign/` 로 복사(파일명 유지)해 **커밋 또는 개발 측 전달**(런북 §6.3).
2. 함께 보낼 것: `git rev-parse HEAD` · 각 실행의 시작 KST 시각 · 계좌 지문(§1-6) · 수동 개입 기록(P-EXT 주문 시각 5건) · `python -m tools.broker_probes.run --coverage` 출력.
3. 인용 적격성은 개발 측이 확인(런북 §6.2: `mode: live` · `provenance_class: MEASURED` · `errors: []` · `skips[]` 검토 · `repo_commit` 일치 · 환경 일치). **아티팩트의 `approval_status` 는 손대지 않는다.**
4. 이후 개발 측 처리: fold → INSTANCE `evidence_refs`/`_kis.measurement` 갱신 → Bounds-Approver `value_ms` 기입(후보값 `candidate_only` 는 값이 아님) → `tools/bcp_digest.py` 3필드 → `approvers` 기입 = P0-2 종결.

## 5. «10키» 판본 주의 (보고서 문장에 반드시 판본 명시)

- **판본 ①** = `registry.py::BOUND_KEYS` 11키(설계 #10 10-bullet) — `--coverage` 가 세는 것.
- **판본 ②** = VP-002 `value_ms: null` 브로커 10키.
- 교집합 6키(`external_activity_detect`·`broker_query_consistency`·`final_quantity_proof`·`late_fill_observation`·`rate_limit_recovery`·`protective_request_complete`)만 이 캠페인이 채운다. 판본 ② 전용 4키 중 `non_trade_*` 2키는 N-19/P-CA(미등재) 소관, `protection_gap`/`protection_overlap` 은 `registry.py::ADJACENT_BOUND_KEYS`(P-8 이 **부분 정보** · 프로브 단독 측정 불가 플래그) — P-8 산출만으로 값이 서지 않는다.
- 후보값 3(`fqp` 10421ms · `query_consistency` 8017ms(모의 전용·실전 leg 영구 차단) · `rate_limit_recovery` 1635ms)은 이미 있고 **승인 아님**.

## 6. 개발 측 선행 항목 (서버 실행과 무관하게 진행)

- N-19/P-CA 프로브 `registry.py` 등재(2026-08-07 정의 · 반증형·GET-only·보유 선행·선물 제외) — 등재 후 이 문서 §2 에 행 추가.
- 런북 §9.4 P-BAL 기입면(`position_balance_margin` completeness/pagination 슬롯) 판정은 `docs/broker-profiles/`·tos-spec 템플릿 소관 — 판정 전까지 P-BAL 값은 아티팩트 안에만.
- INSTANCE REAL_PROD 문서 `_model_view` 는 2026-09-10 보강 완료(`cc1a90e9`) — 프로브와 무관.
