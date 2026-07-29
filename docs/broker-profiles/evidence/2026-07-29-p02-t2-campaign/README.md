# P0-2 T2 프로브 캠페인 증거 패키지 — 2026-07-29

> **문서 성격**: 증거 보존 사본 (런북 §6.3). `tools/broker_probes/results/`는
> gitignored이므로 인용 가능하도록 여기에 복사했다. **어떤 아티팩트도 승인되지
> 않았다** — 전건 `approval_status: UNAPPROVED_CANDIDATE`. 이 패키지는 INSTANCE
> YAML도 VERIFICATION-PROFILE-002도 수정하지 않는다. bound 기입은 Bounds-Approver,
> capability 승격은 P0-2 승인 사슬의 소관이다.

- **런북**: `docs/runbooks/kis-capability-probes.md`
- **캠페인 커밋(repo_commit)**: 1차 웨이브 `33565835` (15:29–19:54 KST) · 2차 웨이브
  `1fee73ca` (19:56 KST — `732c11b7`의 probes_real 결함 수정 반영 재실행)
- **실행 호스트**: 모의투자 서버(배포 호스트), 실행일 2026-07-29 15:29–19:56 KST
- **실행 환경**: 모의 계열 = `.env.paper` 선물 자격증명(MOCK_VTS), 실전 조회 계열 =
  `.env` 선물 자격증명(REAL_PROD, §5.4 분리 셸·GET+allowlist 전용)
- **워커 정지 창**: P-13/P-15/N-15/P-14 동안 `kis_paper-trader-futures`·
  `kis_paper-scheduler` 정지(15:31–15:50 KST), 이후 정상 재기동 확인

## 실행 결과 요약

| artifact_id | 프로브 | §6.2 적격 | 핵심 관측 |
|---|---|---|---|
| `P-1-20260729T062925Z` | P-1 ORDER_IDENTITY | ✅ (단, env=NONE — repo 코드 사실만, 판정은 N-17) | 클라이언트 주문번호 필드 미전송 확인 (grep 0) |
| `P-16-20260729T063005Z` | P-16 BROKER_TIME | ✅ | Date 헤더 1s 해상도, signed skew ≈ −0.9~−1.9s (헤더 해상도 이내), n=30 |
| `P-13-20260729T063120Z` | P-13 RATE_LIMITS | ✅ | **구간 기록**: clean 하한 1.0 rps / 스로틀 상한 2.0 rps (`EGW00201`, HTTP 500). 회복 1089.6ms (n=1, 폴 1s) → 후보 1635ms `candidate_only`. scope: 모의·futures·query·단일 계좌/세션 |
| `P-15-20260729T063207Z` | P-15 CREDENTIALS | ✅ | 1분 내 2차 재발급 → **HTTP 403, 본문 무코드**. 1차 응답 `expires_in=86400` (브로커 반환값 실측 — auth.py 폴백과 별개) |
| `N-15-20260729T063312Z` | N-15 (1차) | ❌ errors≠[] | 첫 발급 `EGW00133` — 직전 P-15 쿼터 소모 여파 |
| `N-15-20260729T063609Z` | N-15 (2차, +150s) | ❌ errors≠[] | tokenP POST 중 `RemoteDisconnected` |
| `N-15-20260729T064035Z` | N-15 (3차, +266s) | ❌ errors≠[] | `EGW00133` 지속 — 마지막 발급 시도로부터 4.4분 경과에도 거부 |
| `N-15-20260729T064922Z` | N-15 (4차, +8.8min) | ❌ errors≠[] | `EGW00133` 지속. **blackout 창 미확립 — `token_blackout_window_ms`는 null 유지** |
| `P-14-20260729T065011Z` | P-14 SESSIONS | ✅ | 동시 세션 5 수락 = 시험 천장 → **상한은 5 이상** (천장≠한도). 구독 1건(단일 심볼 — dedup 가능성, "41" 주석 승격/반증 불가). displacement 수동 확인 잔여 |
| `N-18-20260729T065131Z` | N-18 (1차) | ⚠ 참고용 | N-18c 심볼 미지정 스킵 — 인용은 2차본으로 |
| `N-18-20260729T065224Z` | N-18 (2차, 정본) | ✅ | N-18a: 150일 요청→**단일 콜 101행**+행 스키마 포착. N-18c: 주간 101S6000·야간 1A01609 모두 `rt_cd=0` 정상 응답(야간 REST 응답 성공 — 해석은 N-17 트랙). N-18b: 구조적 스킵(SOX TR id 미확정, N-17 선행) |

| `N-16-20260729T105405Z` | N-16 (1차) | ❌ **경로 결함** | `33565835`의 배선 결함으로 야간 TR을 **주간 경로**(`inquire-balance`)에 태워 실행됨 (`732c11b7`에서 교정). 감사 추적용 보존 — 인용 금지 |
| `N-16-20260729T105608Z` | N-16 (2차, 정본) | ✅ | 19:56 KST(night=True), 교정된 `inquire-ngt-balance` 경로. envelope 키(rt_cd/msg_cd/msg1) 포착. **output1/output2 빈 배열 = 야간 포지션 부재 — 행 스키마 미확립**(빈 응답을 빈 스키마로 추론하지 않음). `tr_ids.yaml` 편입은 별도 커밋 게이트 |
| `N-18-20260729T105609Z` | N-18 (3차, 정본) | ✅ | `1fee73ca`에서 **skips 0** 전레그 실행. N-18b 해소: 컨트롤 SPX 정상(102행) + **`SOX` 표기 유효 식별**(102행 데이터), `.SOX`/`^SOX`는 rt_cd=0·0행(해당 철자 거부로만 기록). TR=`FHKST03030200`(로드맵 후보 HHDFC55020100은 명세 색인 부재로 **반증**). N-18a 101행 재현·N-18c 2레그 재확인 |

## 정직한 음성 / 캠페인 한계 (§8.4)

- **N-15 미확립.** 4회 시도 전패. `EGW00133` 문언("1분당 1회")과 달리, 연속
  발급 후 **≥8.8분 시점에도 재발급이 거부**되는 확대 잠금을 관측했다. 이는
  `reissue_rejection_semantics`의 실측 보강 증거(거부 표면 2종: P-15의 403
  무본문 / N-15의 EGW00133 본문)이지만, 설계된 측정(invalidate→재발급 공백)은
  성립하지 않았다. `token_blackout_window_ms`는 **null 유지**.
- **P-13 회복 n=1.** `B_rate_limit_recovery` 후보 1635ms는 표본 1의
  `candidate_only`다. Bounds-Approver가 표본 적정성을 판단한다.
- **P-14 구독 상한 미확립.** 단일 심볼 반복 구독은 브로커 dedup 가능성으로
  상한을 과소평가할 수 있다 — `subscription_limit`은 null 유지.
- **프로브 미공급 bound 2키** (`B_capability_claim_to_send`·
  `B_venue_constraint_loss_detect`)와 **프로브 미정의 2키**
  (`B_non_trade_event_detect`·`B_non_trade_reconcile`)는 이 캠페인으로 채워지지
  않는다 (런북 §4.1·§9.2). "전건 실행 = 전 키 확보"가 아니다.

## 미실행 프로브와 사유 (후속 세션 필요)

| 프로브 | 사유 | 재개 조건 |
|---|---|---|
| P-5 / P-5b / P-2 / P-8 / P-FQP | 주문 계열 — 캠페인 개시 시각(15:26 KST)에 모의 정규장 잔여 19분 < 소요 합계 ~70분 | 다음 거래일 모의 개장(08:45 KST~) + 워커 정지 창 |
| P-11 | 상동 + **모의 주식 자격증명 부재** (.env/.env.paper 모두 `KIS_STOCK_MARKET=real`) | 모의 주식 앱키 발급/주입 후 |
| P-EXT | 운영자 HTS/MTS 수동 주문 개입 필요 (≥5 trial) | 운영자 동석 세션 |

**N-17은 별도 트랙에서 완료됨** (`239b175a` —
`docs/plans/2026-07-29-tos-p02-n17-spec-collation.md`, 16항목: 확정 5 · 부분 6 ·
미확인 5). 본 캠페인의 N-16/N-18 2차 웨이브가 그 대조 결과(#14 SOX TR 확정,
#16 야간 잔고 경로)를 소비했다.

## 부수 관측 (승인 대상 아님, 기록만)

- P-15가 `expires_in=86400`을 **브로커 반환값**으로 관측 — N-17 항목 8
  ("우리 fallback 86400은 우리 기본값") 대조에 입력.
- N-18a 행 스키마(`arbt_*`/`nabt_*` 계열)와 N-18c 야간 코드 REST 정상 응답은
  `config/kis/tr_ids.yaml` 편입 판단(별도 커밋)과 야간 캡처 설계 재검토의 입력.
- N-18b: KIS 해외지수 TR에서 SOX의 유효 표기는 **`SOX`(접두 없음)** — 단,
  아티팩트 caveat대로 이는 "이 철자가 데이터를 반환했다"는 관측이며 공식 표기
  보증은 아니다. `.SOX`/`^SOX`는 빈 응답(철자 거부로만 기록).
