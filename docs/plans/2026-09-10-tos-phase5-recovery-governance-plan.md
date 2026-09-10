# TOS Phase 5 계획 — 복구·조정·관측·운영 완성 (recovery barrier · 3자 reconciliation · 안전 메시 런타임 owner · 운영 기층)

- **상위**: 개발계획 `docs/plans/2026-08-11-tos-completion-development-plan.md` §6 Phase 5(작업 1~7 · 종료 조건 5항) · §3 G1(«non-authoritative stand-in 0 · 모든 권위 actor 와 durable state owner 가 실제 구현») · 설계 #17 SBR · #9 recon · #24 post-trade · #26 WDR · #28 SIR · #30 STM · #12 SPG · #11 protective · #18 replacement · #20 HAG · #29 SCI · #21 non-trade · #8 orthostate · #40 런타임 shell.
- **선행**: PR #663(main `1362fa60`) — Phase 1~3 완료 · Phase 4 구조 완결(EC-5 이월). Phase 3 §7.11 이월 10건 · Phase 4 잔여 계획 §9.5 처분 · KIS MOCK transport 계획(`2026-09-10-tos-kis-mock-transport-plan.md`, 병행 가능).
- **저작**: 세션 모델 단독 · 권한 부여 0 · 실 브로커 송신 0 · 라이브 권한 0 · EV 행 상태 변경 0(Phase 6 소관).

## 0. 서베이 실측 (2026-09-10 · `1362fa60`)

**커널(순수 모델+술어 · EV-L1)**: `sbr`(2140 · 안전 부팅/복구 장벽/보수 재개) · `recon`(924 · reconciliation confidence) · `posttrade`(4187) · `sir`(3791) · `wdr`(2878) · `stm`(3935) · `spg`(2256) · `protective`(1660) · `replacement`(2364) · `hag`(2292 · dual control/break-glass) · `sci`(3406 · 의존 admission) · `nontrade`(2847 · 기업행위/비거래 상태) · `orthostate`(1324) · `failuredomain`(1055) · `rlp`(2453 · restricted-live) · `staterestore`(1027 · **EV-L3 on-disk composite state + 보수 재로드** — 유일한 «실 기판» 커널 패키지) · `cur`(1861 · 21차원 currentness). 전부 «입력을 모아 술어를 호출하는 런타임» 이 없으면 하중 0.

**런타임(`tos_runtime`)**: `evidence`(store sqlite WAL·backup(`Connection.backup`+manifest)·retention(판정만·삭제 0)) · `rcl`(log·gates·obligation) · `custody`(file custody·key provider) · `engine`(inbox·driver·replay·orthostate_projection) · `posttrade/finality.py`(**SYNTHETIC 전용** finality producer · quantity-only) · `release` · `time`(단조·신뢰 시간) · `authority`(epoch·iap) · `risk`(aggregate·flow·ledger stages) · `currentness`(vector·proof) · `brokercap` · `strategy` · `compose`. Redis 0 · API/대시보드 표면 0 · 캘린더 0.

**stand-in 잔존(G1 위반 목록 = 이 Phase 의 대상)**:
| 표면 | 현재 | owner 후보 |
|---|---|---|
| currentness 17차원(`compose/_pending_dimensions.py`) | 운영자 attestation(spg profile·deviation·incident·monitoring·release·post_trade·critical_input·context·constraint·construction·trading_approval·egress_identity·environment_scope·currentness_policy·recovery·decision_proof_intent·aggregate_risk) | 차원별 런타임 서비스(W3) |
| egress item 12 `venue_session_account_facts_current` · item 16 `restrictive_latch_state`·`worst_credible_capacity` | attestation(`_egress_attestations.py` — Phase 5 명시) | venue/session 캘린더 owner(W5) · 래치·용량 owner(W3) |
| 17항목 deferred 4·5·7·8·9·10 | `NON_BROKER_SYNTHETIC`→N/A · 그 외 UNKNOWN | 4 authority epoch(런타임 존재) · 5 liveauth(NOT_AUTHORIZED 구조) · 7 SPG · 8 WDR · 9 SIR · 10 STM(W3) |
| Phase 3 이월 ⓐ 전역 new-risk 래치+재무장 정책 · ⓑ legacy 영수증 부팅 게이트 · ⓒ release trigger(`PROJECTION_ORDER` RELEASED 부재 → 슬롯 영구 점유) · ⓔ `GatewayEvidenceRecord.step` 필수화 · ⓖ TIMEOUT 해소 세대 · ⓗ 크래시 후 possibly-live 재구성 · ⓘ 설정값 · ⓙ G-1 시간 스냅샷·G-2 proof 발행 | 열림 | W1(ⓑⓗ) · W2(ⓒⓖ) · W3(ⓐⓙ) · 커널 라운드(ⓔ) · 운영자(ⓘ) |
| broker witness | 합성 transport 자체 원장뿐 | KIS MOCK 조회(transport 계획 이후) — 이 Phase 는 **witness 포트**만 |

## 1. 범위

| 포함 | 제외 (이유) |
|---|---|
| 작업 1~7 전부의 **런타임 owner 착지**(합성 transport 기준 · 실 브로커 witness 는 포트+합성 구현) · G1 stand-in 0 달성 · 종료 조건 5항 실증 · Phase 4 웨이브 3(deferred 4·5)을 W3 에 흡수 | EV 행 `PASS` 이동(Phase 6) · 실 KIS witness 어댑터(transport 계획 후속) · 대시보드 UI 구현(레거시 `strategy-builder-ui` — 이 Phase 는 **읽기 전용 투영 export** 만) · Redis 신규 도입(런타임은 sqlite — 종료 조건 4 는 «Redis 키 0» 으로 공허 충족을 **기록**, 주장 아님) · 실선물 어떤 것도 |

## 2. 결정 (Phase 공통)

1. **owner 교체는 1차원=1커밋**: 각 attestation 을 실 서비스로 바꿀 때 (a) RED 테스트(«attestation 제거 시 부팅 거부» → «서비스 verdict 로 대체») (b) 서비스는 커널 술어 호출만(판정 저작 0) (c) `owner_identity` 를 서비스 identity 로 스탬프 (d) `_pending_dimensions`·`_egress_attestations` 의 해당 키 **삭제 + 잔존 키 = 부팅 거부**(Phase 4 레인 D 관용구). 남는 attestation 은 문서화된 owner 부재 사유가 있어야 한다.
2. **복구는 부팅 전 장벽**: `tos_runtime/recovery/` 신설 — compose 는 `RecoveryBarrier.verdict()` 가 `RESUME_CONSERVATIVE`(커널 `sbr` 어휘) 가 아니면 엔진 드라이버를 **결선하지 않는다**(정지 사유 evidence). 장벽 입력 = staterestore composite state · RCL log tip/generation · evidence tip · inbox 미소비 · 재생 verdict(Phase 3) · possibly-live attempt 집합(ⓗ) · legacy 영수증 잔존(ⓑ). 전부 구조 파생, 운영자 «정상» 선언 입력 0.
3. **3자 reconciliation**: `tos_runtime/recon/` — 커널 `recon` 술어에 (RCL 예약/커밋, evidence 영수증, broker witness) 3자 관측을 주입 → `ReconciliationConfidence`. broker witness 는 **포트** `BrokerWitness.observe(scope) -> WitnessSnapshot`; Phase 5 구현은 합성 transport 의 자체 원장(`SyntheticLedgerWitness`) · KIS 는 후속. confidence 가 양성 아니면 **재무장 0·용량 반환 0**(종료 조건 1).
4. **용량 반환은 finality witness 로만**: `PROJECTION_ORDER` 에 `RELEASED` 를 넣는 것은 finality 소비자(W2)가 `FinalityProof` 를 evidence 에 **선기록**한 뒤. `UNKNOWN`/`TIMEOUT` 은 만료·해소 전까지 점유(ⓒ·ⓖ). orphan broker order(witness 에만 있는 주문) 는 예약 없는 결과와 같은 «기록된 보수 결과»(Phase 3 `ResultDisposition`) + 사고 후보.
5. **안전 메시 4 서비스는 같은 형상**: `SafetyProfileService`(spg · item 7 envelope/profile version) · `DeviationService`(wdr · 8) · `IncidentService`(sir · 9) · `MonitoringService`(stm · 10) — 각각 «정책 문서(설정 YAML, named-TBD)·현 세대·활성 집합·scope» 를 로드해 커널 술어로 verdict 를 내고, (i) currentness 차원 owner (ii) `SendBoundaryContext` 의 해당 deferred item 입력 (iii) coordinator 전제조건 셋에 동시 공급. 커널 diff: `SendBoundaryContext` 에 deferred 6 입력 필드(`safety_authority_epoch_current`·`live_scope_valid`·`safety_profile_current`·`deviation_clear`·`incident_clear`·`monitoring_clear`: `bool|None`) + `_deferred_item_verdict` 주입 분기(NON_BROKER_SYNTHETIC→N/A 불변 · True 만 SATISFIED · None→UNKNOWN). `gateway.py` 등재 한계(2007) 상 deferred 판정을 `egressgw/mesh.py` 로 분리(커널 라운드 · 등재 갱신).
6. **보호 행위·통제 종료·재무장**: `ProtectiveActionService`(protective+replacement) · `ControlledShutdown`(sir) · `ReArmWorkflow`(hag dual control · break-glass 는 evidence 선기록 + 2인 승인 파일 · 자동 재무장 0). ⓐ 전역 new-risk 래치 정책은 **운영자 결정 입력**(§7) — 결정 전엔 «기록만+instrument 단위» 대안으로 착지하고 정책 승인 시 설정 전환.
7. **운영 기층**: backup/restore drill(evidence backup 존재 → RCL log·inbox·staterestore 까지 확장 · restore 후 `replay_engine` digest 동일 = drill 통과) · schema migration(sqlite `user_version` + migration ledger 테이블 · 전방 전용 · 부팅 시 미적용 마이그레이션 = 정지) · key rotation(custody `KeyProvider` 세대 회전 · 이전 세대 검증 유지 · 회전 evidence) · dependency admission(sci 커널 → 부팅 시 `uv.lock`/설치 digest 를 admitted manifest(설정)와 대조 · 불일치 = 정지).
8. **authority-neutral operator state**: `tos_runtime/operator/projection.py` — 읽기 전용 투영(JSON 파일 export · 주기 없음 · 드라이버 턴마다) · 어떤 write 포트도 없음(negative-grep) · 레거시 `services/dashboard` 는 이 파일을 **읽기만**(Caddy 뒤 · 별도 커밋). alert ownership: STM 서비스가 alert 를 evidence 로 발행, 전달(Telegram)은 레거시 alert-manager 소관 — 런타임은 전달 채널을 모른다.
9. **KST 세션·캘린더·기업행위·롤오버**: `tos_runtime/calendar/`(KST-native 설정 YAML: 휴장일·세션·야간·만기) → venue/session facts owner(item 12 attestation 대체) · `nontrade` 커널 소비자(기업행위 이벤트 → composite state 조정 · 합성 이벤트 픽스처) · 선물 롤오버 시나리오(만기 전 포지션 전환은 **전략 결정** — 런타임은 만기 도달 시 신규 주문 거부 + 사고 후보) · long/short 대칭 시나리오 테스트(엔진 레벨 · 합성 · 대칭 위반 = red).
10. 값형 설정은 전부 named-TBD null → 부팅 거부 · ⓘ 값은 운영자.

## 3. 기각 대안

- 운영자 «정상» 선언으로 장벽 통과 → SBR §(보수 재개는 구조 파생) 위반.
- 주문 응답으로 finality 판정 → witness 없는 용량 반환(종료 조건 1 위반).
- 대시보드에 write 경로(kill-switch 등) → 종료 조건 3(«authority source 아님») 위반 · 레거시 kill_switch 는 레거시 런타임 소관 그대로.
- Redis 를 런타임 상태에 도입 → 설계 #40 D3(sqlite) 와 충돌 · 종료 조건 4 는 «정책 준수» 이지 «Redis 사용» 이 아니다.
- 안전 메시 4 서비스를 하나로 → 각 ADR 의 세대·scope 가 독립 · 1차원=1owner 원칙.

## 4. 웨이브 (순차 · 각 웨이브 독립 리뷰→처분→재심 · 파일 소유 1레인)

| 웨이브 | 작업 | 산출 | 종료 조건 대응 |
|---|---|---|---|
| **W1 복구 기층** | 1 · 2 · ⓑ · ⓗ | `recovery/`(barrier·possibly-live 재구성·legacy 영수증 게이트) · `recon/`(3자 · witness 포트+합성) · orphan/stale 예약 처리 · **복구 drill** 테스트(크래시 창 3분기 × 재기동 × duplicate send 0 · Phase 3 창 확장) | 1(재무장 0) · 2(duplicate 0) |
| **W2 post-trade·용량** | 3 · ⓒ · ⓖ | finality 소비자(합성 witness) · `RELEASED` 투영 · 용량 반환 · obligation 만료 · TIMEOUT 해소 세대 | 1 |
| **W3 안전 메시 owner** | 4 · Phase 4 웨이브 3 · ⓐ · ⓙ · 17차원 · 래치/용량 | 4 서비스 + deferred 6 입력(커널 `egressgw/mesh.py`) · 보호 행위·통제 종료·재무장 · G-1/G-2 owner · `_pending_dimensions` 17→0 · `_egress_attestations` 래치/용량 제거 | 1 · G1 |
| **W4 운영 기층** | 5 · 6 | backup/restore drill · migration ledger · key rotation · dependency admission · operator projection export(읽기 전용) | 3 · 4(공허 기록) |
| **W5 시나리오** | 7 · item 12 | `calendar/`(KST) · nontrade 소비자 · 롤오버 · 대칭 테스트 · `_egress_attestations` → 0 | 5(EOD 청산 0 · 대칭) · G1 |

각 웨이브 착지 조건: 런타임·커널 green · ruff/black/mypy 0 · 크기 예산(신규 모듈 ≤1000 · 함수 ≤100 · `_wiring.py` 는 성장 금지 — compose 모듈 분리) · firewall · `tos_completion_status --check` GREEN(**bound 문서 무접촉**) · EV 상태 변경 0.

## 5. 종료 조건 대응 (개발계획 Phase 5 · 5항)

| # | 조건 | 실증 |
|---|---|---|
| 1 | evidence/broker truth 불명확 ⇒ 자동 re-arm/용량 반환 0 | W1 confidence 비양성 ⇒ 장벽 정지 + W2 witness 없는 RELEASED 0(뮤테이션: 응답으로 RELEASED ⇒ red) |
| 2 | 복구 drill duplicate send 0 | W1 크래시 창 × 재기동 전수 · 게이트웨이 at-most-one + 재생 digest 동일 |
| 3 | dashboard 가 authority source 아님(API·UI) | W4 projection 은 write 포트 0(negative-grep) · 레거시 대시보드 결선은 읽기 전용 커밋 |
| 4 | Redis DB1·TTL 정책 · authoritative durability = storage ADR | 런타임 Redis 키 0(공허 · 기록) · durability = 설계 #40 D3 sqlite WAL(evidence)·RCL log · migration ledger |
| 5 | stock swing blanket EOD 청산 0 | W5 캘린더 owner 는 세션 facts 만 공급 · 청산 결정 경로 부재를 negative-grep(«EOD»/«liquidat» 소비자 0) |

## 6. 규모·순서

- W1→W2→W3→W4→W5 순차(W4 는 W2 후 병행 가능 · W5 캘린더는 W3 와 병행 가능). KIS MOCK transport T1~T3 는 W1~W2 와 병행 가능(파일 무접촉).
- 웨이브당 실행 레인 2~3(sonnet) + 리뷰 1 · 커널 diff 는 W3 만(mesh 분리) — 커널 라운드 규율.

## 7. 운영자 확인 지점

1. ⓐ 전역 new-risk 래치 + 명시 재무장 정책(승인 / instrument 단위 / 기록만) — W3 착수 전.
2. ⓘ 설정값: `max_send_result_wait_ms` · `replay_window_events` · finality 정책 · calibration 예산(Phase 3 이월) + 이 Phase 신설(장벽 timeout·migration 정책·key rotation 주기·admitted dependency manifest).
3. authoritative durability 의 «선택된 storage ADR» 지목(설계 #40 D3 sqlite 를 그 ADR 로 확인).
4. 레거시 `services/dashboard` 의 투영 읽기 결선 시점(Phase 5 안 / 후속).
5. 커널 `egressgw/mesh.py` 분리(등재 갱신) 승인 — 커널 라운드 #2 로 묶을지.

## 8. 운영자 처분 (2026-09-10)

| # | 처분 |
|---|---|
| 1 | **전역 new-risk 래치 + 명시 재무장(seq 결속·attestation·증거 선기록·HAG 2인) 승인** — W3 에서 구현 · 대안 불채택 |
| 2 | 설정값 ⓘ + 이 Phase 신설값 = **개발 측 근거 제안표 → 운영자 승인** · 승인 전 named-TBD null |
| 3 | authoritative durability 의 storage ADR = **설계 #40 D3 sqlite WAL** 로 확정(신규 ADR 없음) · 런타임 Redis 키 0 은 종료 조건 4 의 공허 충족으로 기록 |
| 4 | 레거시 `services/dashboard` 의 읽기 전용 투영 결선은 **W4 안에서**(write 포트 0 negative-grep 으로 종료 조건 3 실증) |
| 5 | **커널 라운드 #2 로 묶어 승인**: `egressgw/mesh.py` 분리 + `SendBoundaryContext` deferred 6 입력 필드 + Phase 3 이월 ⓔ(`GatewayEvidenceRecord.step` 필수화) + item 6/12 reason 문언 정정 · **W1 착지 후 시작, W3 착수 전 선행** |
| 착수 | **즉시 — W1 ∥ MOCK transport T1** · 브랜치 `feat/tos-phase5-w1-recovery`(워크트리 `../kis_unified_sts-phase5-w1`, main `296c0e5f` 기점) |

## 9. 실행 결과 — W1 착지 (2026-09-10 · PR #670 → main `7579196c`)

- **착지**(레인 W1-a/W1-b/W1-c · 9커밋): `tos_runtime/recovery/`(barrier · inputs · possibly_live · legacy_receipts · reconciliation · composite_state_writer) · `tos_runtime/recon/`(ports · witness_synthetic · evidence_reader · service) · `compose/_recovery_wiring.py` · `_engine_wiring.py`(`REPLAY_VERDICT_IDENTICAL` durable 기록) · `driver.py`(composite-state 쓰기 · 영수증 이전 · 실패 = halt) · 테스트 recovery 57 · recon 39 · 크래시 drill 11. 런타임 1038(T1 병합 포함) · 커널 diff 0 · 예산 재등재 2(root.py 109 · `_process_next` 141).
- **정직 상태**: 합성 witness 는 evidence 와 같은 저장소를 읽으므로 **비독립으로 표기**되어 `WITNESS_NOT_INDEPENDENT` HOLD — **실 broker witness(KIS 조회 어댑터) 전까지 어떤 possibly-live 도 자동 해제되지 않는다**(종료 조건 1 의 구조적 실증). 스코프 단위 permit 은 보수적(같은 instrument 의 무관한 attempt 가 실패하면 좋은 attempt 도 HOLD) — 수용·문서화.
- **독립 리뷰**: 1차 needs-attention(HIGH 2 · MEDIUM 5 · LOW 1 · 뮤테이션 생존 1) → 처분(attempt 단위 reconciliation · 비독립 표기 · SEND_HANDED_OFF 키잉 · `FlowFingerprint` 검증 · durable replay verdict · inbox 전행 파싱 · 상수 단일화 · typed invariant · 쓰기 실패 halt) → 재심 F1~F8 전건 동작 종결 · 뮤테이션 9종 red · 잔여 3(mypy·assert·문언) 처분.
- **이월**: obligation 1 의 양성 행은 그 행을 쓰는 호출이 자기 성공을 증언(음성 행만 부팅 간 하중 · LOW) · W1-a 의 `_reconciliation_service_available` 프로브는 실 결선으로 대체됨 · 실 broker witness 는 MOCK transport T2/T3 이후.
- **공유 워크트리 충돌 1회**(W1-a 재가동 ↔ W1-c · 파일 clobber → ImportError) — 복구 완료 · 교훈은 메모리(`subagent-reports-arrive-out-of-order`)에 기록: 끝난 레인에 메시지 금지.

## 10. W2 설계 정정 — 서베이 실측 후 (2026-09-10 · main `7f3ffa52`)

**실측(§4 W2 행의 전제 수정)**: (a) `RELEASED` 는 커널 `CapacityState`(`tos/src/tos/rcl/vocabulary.py:31`)에 있고 RCL 원장 게이트 `release_admissible`(`rcl/commitlog.py:463`) + 런타임 `rcl/gates.py:343` + `rcl/finality_witness.py::release_reservation` 시임까지 **전부 존재**하나 **프로덕션 호출 지점 0** · (b) 엔진 in-memory 투영 `PROJECTION_ORDER`(`tos/src/tos/engine/state.py:74-82`)에는 `RELEASED` 가 **부재**(커널 테스트 3건이 부재를 직접 핀) · (c) ⓖ TIMEOUT 해소 세대는 커널 dedup 서명(`engine/state.py:258-271`)에 산다 · (d) driver 는 `attempt_finality_witness` 행과 `POSTTRADE_FINALITY_PROOF` evidence 를 **쓰기만** 하고 읽는 프로덕션 소비자 0 · (e) W1 recon 이 `ReconciliationReport.permits_capacity_release` · `EgressReceiptObservation.finality_proof_recorded` · `WitnessSnapshot.independent_of_evidence_store` 를 이미 공급 · (f) 헤드룸 0 파일: `_wiring.py` 1197(성장 금지) · `rcl/log.py` 1000 · `engine/driver.py` 994.

**분리 결정**: W2 를 **W2-R(런타임 · 커널 diff 0 · 즉시)** 과 **W2-K(커널 라운드 #2 번들 확장 · 운영자 확인)** 로 나눈다.

| 레인 | 내용 | 결선 |
|---|---|---|
| **W2-R** | ① `tos_runtime/posttrade/release_consumer.py`(신설) — **RCL 원장(권위·durable)** 에 대한 유일한 용량 반환 호출 지점. APPLIED `EGRESS_RESULT` 뒤 매 턴: durable witness 행 + `POSTTRADE_FINALITY_PROOF` evidence(재로드 · 메모리 객체 아님) + `ReconciliationService.reconcile(scope)` 보고(`permits_capacity_release is True` ∧ 해당 attempt `MATCHED`) + 커널 `finality_proof_non_transferable`/`finality_proof_current` 양성 → **evidence 선기록 `CAPACITY_RELEASE_INTENT`** → `release_reservation`(FULL_FILL ⇒ `POSITION_CONSUMED` · CANCEL_ACK/EXPIRED/REJECT ⇒ `RELEASED`, 비체결 FQP(filled 0 · remaining 0)은 **witness 대조 후에만** 생산 — 응답 단독 금지 §3). 어느 게이트든 비양성 ⇒ 전이 0 + `CAPACITY_RELEASE_HELD`(사유) ② `engine/finality_projection.py`(신설) — `driver._project_finality` 본문 순수 이동(driver 헤드룸 확보) + 소비자 호출 ③ `compose/_release_wiring.py`(신설) — W1 `recovery/reconciliation.py:216` 과 **같은 생성 경로**로 recon 서비스 재사용 · `_engine_wiring` 은 1호출만 ④ obligation 만료 = `release_proof_wait_ms`(설정 named-TBD null) 초과한 `RELEASE_PENDING_PROOF`/`QUARANTINED_UNKNOWN` 예약에 `RELEASE_PROOF_OVERDUE` evidence(기록만 · 상태 변경 0 · 사고 후보) | driver 훅 · `_engine_wiring` 1호출 |
| **W2-K** (운영자 확인 6) | 커널 라운드 #2 번들에 추가 제안: `PROJECTION_ORDER` 에 `RELEASED` + `ProvisionalReservationLedger` 의 **finality-proof-token 게이트** release 메서드(응답 kind 로는 불가) + ⓖ dedup 서명에 해소 세대 · 커널 테스트 3건 개정 | 커널 라운드 |

**정직 상태(W2-R 착지 시)**: 합성 witness 는 비독립이므로 composed 런타임에서 `permits_capacity_release` 는 항상 False ⇒ **실 반환 0** — 소비자의 하중은 독립 witness fake 를 주입한 테스트에서만 실증되고, 실 KIS 조회 witness(transport T2/T3 이후)가 붙는 날 코드 변경 0 으로 첫 반환이 일어난다(T1 과 같은 «구조 완결» 논리). 엔진 in-memory 투영은 W2-K 전까지 프로세스 수명 동안 점유 유지(재부팅 시 RCL RELEASED 와 정합) — 한계로 기록.

**운영자 확인 지점 6**: W2-K 를 커널 라운드 #2(처분 5 번들)에 묶을지. 권고: 묶는다(둘 다 W3 착수 전 선행 조건).

### 10.1 실행 결과 — W2-R 착지 (2026-09-10 · 브랜치 `feat/tos-phase5-w2-finality` · main `7f3ffa52` 기점)

- **착지** `d99e4456`·`bf5a68e4`: `posttrade/release_consumer.py`(`FinalityReleaseConsumer` — RCL 원장 `RELEASED`/`POSITION_CONSUMED` 의 유일 프로덕션 호출 지점 · durable proof/obligation 재로드 · `CAPACITY_RELEASE_INTENT` 선기록(evidence seq 순서 핀) · 비양성 ⇒ `CAPACITY_RELEASE_HELD`(사유) · `RELEASE_PROOF_OVERDUE` 기록만) · `engine/finality_projection.py`(driver `_project_finality` 순수 이동 + 소비자 호출 · driver 994→974) · `compose/_release_wiring.py`(`_recovery_wiring` 관용구 — `EngineDriver.bind_release_consumer` 후결선 · `_wiring.py`/`_engine_wiring.py` 무접촉) · `posttrade/finality.py` `produce_non_execution`(FULL_FILL_*/NON_EXECUTION_* 키 접두 분리) · `finality.yaml::release_proof_wait_ms`(null=부팅 거부) · `rcl/reservation_identity.py::scope_reservation_id`(수기 6곳 대체).
- **독립 리뷰**: 1차 needs-attention(HIGH 2 · MEDIUM 7 · LOW 4 · 뮤테이션 생존 5/14) → 처분 `3b0ada34`·`9b768593`(게이트 4 입력을 RCL 예약 행 scope·evidence obligation 세대로 독립화 · 단조 클록 영속 제거 + TRUSTED 시간에서만 만료 평가 · 점유 단위(last_seq) 키잉 · 비체결 경로도 게이트 4 통과 · 접두 분리·재로드 kind 선택 · e2e 사유·예약 id 핀 · MATCHED 핀) → 재심 신규 MEDIUM 1(import 순환 `release_consumer→engine→driver→finality_projection`) → `ddd7de3e`·`28bbacbb`(`TYPE_CHECKING` 가드 · 헤르메틱 순환 재발 테스트 — subprocess/importlib 는 firewall TOS-FW-B/D 차단이라 `sys.modules` 축출+정적 import) → **최종 approve** · 뮤테이션 전건 red. 런타임 **1080** · 커널 9405 · 커널 diff 0.
- **정직 상태(e2e 실증)**: `compose_paper_runtime` 경로의 실 FULL_FILL 핸드오프 → RCL `RELEASED`/`POSITION_CONSUMED` 행 0 · `CAPACITY_RELEASE_INTENT` 0 · `CAPACITY_RELEASE_HELD` 1(`NOT_CORROBORATED` · `WITNESS_NOT_INDEPENDENT`). 게이트 4 입력은 **기제상 독립이나 오늘 도달 가능한 입력에서는 값이 일치**(compose root 가 `InstrumentKey` 1개 · `finality.py` 가 `obligation_generation=0` 고정) — 다중 instrument compose root 또는 실 정정 레인이 붙어야 분기 도달.
- **구조적 발견(리뷰어 확인)**: CANCEL_ACK/EXPIRED/REJECT ⇒ `RELEASED` 경로는 witness 독립성과 **무관하게** 도달 불가 — `ReconciliationService._quantity_observations` 가 수량 CORROBORATED 에 독립 수치 관측 2개를 요구하나 `EgressResultPayload` 검증기가 이 세 kind 의 수량을 금지하고, `field_reconciled_proof_ok`(`tos/src/tos/recon/predicates.py:377`) 자체가 «cancel ACK ⇒ FQP 토큰 없음 ⇒ False» 를 의도 케이스로 명시. → **운영자 확인 지점 7**: (a) recon 서비스/커널 술어에 «종단 비체결 상태의 0-수량 대조 경로» 확장(커널 diff · 라운드 #2 후보) 또는 (b) 비체결 반환은 확장 전까지 영구 HOLD 수용. 권고: (a) 를 커널 라운드 #2 검토 항목으로 등재, 착지 전까지 (b).
- **이월(LOW)**: 반환 시도당 evidence 클라이언트 측 스캔 6회(규약상 수용 · 병목 시 후속) · `finality_projection` 순환 테스트의 `sys.modules` 복원 잔여 1줄.
