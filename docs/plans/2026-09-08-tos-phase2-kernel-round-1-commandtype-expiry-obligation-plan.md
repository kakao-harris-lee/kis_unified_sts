# TOS Phase 2 커널 라운드 #1 — `CommandType` 4멤버 · 결정 만료 술어 · worst-credible-capacity 보존 의무 · OBS-1 `| None` 균일화

- **상위**: 슬라이스 #3 계획 §7 «커널 라운드 목록 3건» + «비차단 관찰 OBS-1» (`docs/plans/2026-09-08-tos-phase2-runtime-slice3-authority-risk-currentness-compose-plan.md`) · 개발계획 §6 Phase 2 종료 조건 유지 · 운영자 지시 2026-09-08 «추천 순서대로 착수 — 커널 라운드 3건 + OBS-1 슬라이스 계획부터».
- **저작**: 세션 모델 단독 · 권한 부여 없음 · EV 행 상태 변경 0 · 실 브로커 transport 0 · tos-spec 무편집(ADR 은 «semantics equivalent to … at minimum» 이라 열거 확장에 규범 개정 불요 · 아래 §1 근거).
- **서베이 실측(2026-09-08 · main `aa348ce1`)**:
  - `CommandType` 재사용 4곳: `authority/epoch.py:99`(`ADVANCE_RESTORE_GENERATION`) · `authority/iap.py:116`(`CONSUME_TRANSMISSION_CAPABILITY`) · `risk/flow.py:123`(`AUTHORIZE_TRANSMISSION_CAPABILITY`, STANDALONE permit) · `currentness/proof.py`(`AUTHORIZE_TRANSMISSION_CAPABILITY`) — 넷 다 «reported gap» 도크스트링으로 등재. 읽기 측은 `kind is <상수> and command_id.startswith(prefix)`(epoch.py:330-332 · iap.py:416/472-474). `SqliteCommitLog` 는 kind 를 `CommandType(kind)` 로 역직렬화(log.py:345) — 스키마 버전 없음.
  - 결정 만료: `tos.iap` 은 clock-free(`records.py:336` «injected opaque validity age») · 런타임 로더는 non-null `max_decision_age_ms` 를 **거부**(`iap.py:201-232`) · 승인 파일에 발행시각 없음 · `TradingApprovalPolicy` 에 age 필드 없음. `tos.time` 은 이미 5-step 교차-연속성 age 경로를 갖는다: `ConsumerReceiptAnchor`(elements.py:197) · `effective_snapshot_age_bound`(predicates.py:218) · `snapshot_age_admissible`(predicates.py:287) · `anchor_valid`(:104) · `elapsed_within_continuity`(:73). 런타임 time 설정은 `MAX_time_transport_and_queue_uncertainty_ms`·`MAX_future_timestamp_tolerance_ms` 를 이미 적재(`time/config.py:37-68`) · `TimeHealthSnapshot.wall_clock_observation`(covered).
  - 보존 의무: `cur.unknown_preserves_capacity`(predicates.py:592) 결과가 `egressgw/gateway.py:1165-1178` 에서 **사유 문자열에만** 접힘 · `VerifyItemVerdict`(records.py:441) 에 타입 좌표 없음 · `GatewayEvidenceRecord(kind="SEND_REFUSED")` 도 `detail` 문자열뿐(gateway.py:1503-1510) · 값의 출처는 운영자 attestation(`_egress_attestations.py` item 16 · Phase 5 대체 명시). 해제 게이트는 커널 `rcl.commitlog.release_admissible`(:463) 이 finality 증인 `is True` 만 admit — **해제 자체는 이미 구조적으로 막혀 있다**; 빠진 것은 의무의 «기록·검증» 이지 «차단» 이 아니다.
  - OBS-1: 커널 `are/predicates.py:615-632` 는 `numerically_safe is not True or not valuation_ok` 라 `None` 이 들어와도 UNKNOWN(안전) — 타입만 `| None` 을 거부. 런타임 `risk/aggregate.py:240-241` 동일 · `_risk_attestations._restrictive_merge` 는 `None` 분기 기구비.
  - 크기 register: `egressgw/gateway.py`(모듈·`__call__`·`_check_construction`) 등재 — 모듈 성장은 클래스 (f) 래칫이라 **의도적 재등재** 필요.

## 0. 공통 규율

슬라이스 #1 §0 · 슬라이스 #3 §0 그대로. 추가:
- 커널 편집은 레인 K 한 곳에서만, 런타임 레인은 커널 diff 0.
- «판정은 커널 술어만 한다» — 런타임이 age 비교·만료 판정·보존 판정을 자체 작성하면 결함. 런타임은 좌표를 모아 술어를 호출하고 결과를 증거에 남긴다.
- 레거시 데이터 호환은 **fail-closed 거부**로만(아래 §1.3). 마이그레이션 코드는 쓰지 않는다(Phase 2 런타임 로그는 테스트 밖에 배포 실체 없음 — 가정 A1).
- 공유 트리 규율: `git commit -- <paths>` 만 · stash/checkout/reset 금지 · 대조는 `git worktree add --detach`.

## 1. 레인 K — 커널 (`tos/src/tos/` · 선행 · 단일 실행자)

### 1.1 `CommandType` 4멤버 (`rcl/vocabulary.py`)

세 번째 블록 «Runtime-realized authority/currentness commands (design #40 Phase 2 · slice #3 §7 reported gaps)»:

| 멤버 | 값 | 대체 대상 | 규범 좌표 |
|---|---|---|---|
| `ADVANCE_AUTHORITY_EPOCH` | `AdvanceAuthorityEpoch` | epoch.py `ADVANCE_RESTORE_GENERATION` | ADR-002-003 §5 Safety Authority epoch · ADR-002-012 §10 «Safety Authority … may submit … restrictive-generation commands but cannot mutate capacity» |
| `CONSUME_APPROVAL_DECISION` | `ConsumeApprovalDecision` | iap.py `CONSUME_TRANSMISSION_CAPABILITY` | ADR-002-023 §12 Approval Consumption Record(단일 소비) |
| `ISSUE_ACTION_FLOW_PERMIT` | `IssueActionFlowPermit` | flow.py STANDALONE `AUTHORIZE_TRANSMISSION_CAPABILITY` | afg §5.5 «permit 은 Transmission Capability 가 아니다» |
| `ISSUE_EGRESS_CURRENTNESS_PROOF` | `IssueEgressCurrentnessProof` | proof.py `AUTHORIZE_TRANSMISSION_CAPABILITY` | ADR-002-024 §12 Egress Currentness Proof |

근거: ADR-002-012 §10 은 16종을 «at minimum … semantics equivalent to» 로 두고, 같은 절이 Safety Authority·Currentness Sequencer 의 **비-capacity 명령 제출**을 명시한다. 기존 도크스트링(«semantic-equivalence names, not a closed literal enum») 그대로. 넷 다 capacity 를 만들지 않는다 — `rcl/predicates.py` 의 명령 분류(`:331` COMMIT_RESERVATION 분기 등)에 **불포함**을 테스트로 고정. 커널 안 소비자 0(런타임만 사용)이므로 커널 diff 는 enum+도크스트링+테스트뿐.

### 1.2 결정 만료 술어 (`iap/predicates.py`)

`decision_unexpired(*, max_decision_age_ms: int | None, decision_age_bound_ms: int | None) -> bool` — `snapshot_age_admissible` 와 동형(fail-closed: 둘 중 하나라도 `None` ⇒ `False` · 음수 age bound ⇒ `False` · `bound <= max` 만 `True`). iap 는 여전히 클록을 읽지 않는다 — age bound 는 `tos.time` 이 만든 주입값. `tos.iap.__init__` 재-export · 도크스트링에 ADR-002-023 §12 항목 2 «unexpired» 와 §18 «expiry prevents future consumption or send, releases nothing» 인용. **`IndependentApprovalDecision` 레코드는 무편집**(covered 집합 변경 = 기존 digest 픽스처 전부 붕괴 · 발행시각은 소비 시점 런타임 사실이라 §12 «receipt time» 대로 Consumption 증거 소관).

### 1.3 보존 의무 타입화 (`egressgw/records.py` · `egressgw/gateway.py` · `cur/predicates.py`)

- `VerifyItemVerdict.preserved_worst_credible_capacity: int | None = None` — item 16 이 non-ADMIT 일 때 `unknown_preserves_capacity(False, context.worst_credible_capacity)` 의 반환값을 **필드에** 싣는다(사유 문자열은 유지). validator: item 16 이 아닌 verdict 에 non-None 이면 `ArtifactIntegrityError`(다른 항목이 의무를 저작 못 함).
- `GatewayEvidenceRecord.preserved_worst_credible_capacity: int | None = None` — `_halt` 가 item 16 verdict 에서 값을 옮겨 `SEND_REFUSED` 에 싣는다(gateway.py:1560 루프에서 첫 non-SATISFIED 가 item 16 일 때).
- 커널 술어 `cur.obligation_preserved(obligation: int | None, reservation_state: CapacityState | None) -> bool`: `obligation is None` ⇒ `True`(의무 없음) · `reservation_state is None` ⇒ `False` · 상태가 `rcl.predicates._LIVE_COMMITTED_STATES`(capacity 소비 상태) 안이면 `True`, `RELEASED`/`POSITION_CONSUMED` 등 해제·종결 상태면 `False`. cur 는 여전히 all-false(판정만).
- 크기 register: gateway.py 모듈 `measured` 재등재(래칫 규칙 · reason 에 «kernel round #1 item 16 typed obligation +N lines»).

### 1.4 OBS-1 (`are/predicates.py`)

`_decide_result`/`risk_decision` 의 `numerically_safe: RiskDecisionResult | bool | None` · `valuation_ok: bool | None` · 도크스트링 «None = no opinion ⇒ UNKNOWN». 로직 무변경(`is not True` / `not valuation_ok` 가 이미 None 을 UNKNOWN 으로).

### 1.5 레인 K 테스트(TDD · red 선행)

enum 값·개수 핀(+4) · 분류 집합 불포함 · `decision_unexpired` 극성표 6셀 · `VerifyItemVerdict` validator(item≠16 non-None 거부) · gateway item 16 UNKNOWN/DENIED 두 분지에서 필드 채움 + `SEND_REFUSED` 전달(기존 슬라이스 e2e 픽스처 재사용) · `obligation_preserved` 상태 전수 · `_decide_result(None, …)`→UNKNOWN 두 필드 각각. 이후 `tos/tests` 전체 · mypy/ruff/black · firewall · budget `--check` · contract/completion/spec `--check`.

## 2. 레인 A — 런타임 authority (레인 K 착지 후 · `tos_runtime.authority` · `tos_runtime.risk` · `tos_runtime.currentness.proof`)

### 2.1 `CommandType` 전환 + 레거시 kind 거부

4모듈의 `_*_KIND` 상수를 §1.1 멤버로 교체 · «reported gap» 도크스트링을 «resolved by kernel round #1» 으로 갱신. 읽기 측 규칙 변경: **prefix 가 일치하는데 kind 가 새 멤버가 아니면 `CommitLogCorruption`** (기존 예외 재사용 · 조용히 건너뛰면 epoch floor 가 0 으로 퇴행 = fail-open). 테스트: 레거시 kind 항목이 든 로그를 픽스처로 만들어 `current_state`/`decision_current`/permit 조회가 거부되는 것을 red 선행으로 고정.

### 2.2 결정 만료 런타임 경로

- 승인 파일 신규 선택 키 `issued_at_unix_ms: int | null` — 운영자가 파일을 쓰는 순간이 곧 **발행자**(가정 A2 · Phase 5 서명 발행자 도입 전 임시 · custody 0600+owner 검사가 서명 대용). 로더 규칙: `max_decision_age_ms` non-null 이면 `issued_at_unix_ms` **필수**(부재 ⇒ 기존 거부 문구 유지·갱신) · `issued_at` 가 수신 wall-clock 보다 `MAX_future_timestamp_tolerance_ms` 이상 미래면 거부.
- 수신 시(로드): `TrustworthyTimeService.current_snapshot()` 에서 `ConsumerReceiptAnchor`(런타임 자신의 continuity id + monotonic 값)와 `wall_clock_observation` 을 취해 `issuer_signed_age = wall_now − issued_at`, `issuer_age_uncertainty = MAX_clock_domain_conversion_uncertainty_ms`(time 설정 · 없으면 null-거부 키로 추가). 로더 반환은 `LoadedApproval(decision, issued_at_unix_ms, receipt_anchor, issuer_signed_age, …)` — 커널 레코드 무편집.
- 소비 시(`IntentRegistry.decision_current` 및 `consume`): `max_decision_age_ms is None` ⇒ 기존 동작(«expiry NOT_CONFIGURED» 를 증거 `reason_context` 에 기록) · non-None ⇒ `tos.time.anchor_valid` + `effective_snapshot_age_bound(…)`(transport/queue 불확실성 = time 설정값) 로 bound 산출 → `decision_unexpired(max, bound)` · `False` ⇒ `decision_current` 는 `False`(admit 불가 · UNKNOWN 경로) · time health 가 TRUSTED 아님/`TimeServiceNotStarted` ⇒ bound `None` ⇒ `False`. 소비 증거에 `receipt_anchor`·`age_bound_ms`·`expiry_verdict` 결속(§12 «receipt time»).
- 테스트: 로더 3분기(null/필수 부재/미래) · 만료 전 admit·만료 후 deny(모의 monotonic 소스 전진) · 재기동(continuity 변경) 후 bound `None` ⇒ deny · 뮤테이션: `decision_unexpired` 호출 제거 시 red.

### 2.3 OBS-1 런타임 측

`AggregateRiskDecisionInputs.numerically_safe: RiskDecisionResult | bool | None` · `valuation_ok: bool | None` · `_risk_attestations` 도크스트링 «on the fields that allow it» → 6필드 전부 · `_restrictive_merge` 테스트에 두 필드 `None` 케이스 추가.

## 3. 레인 B — 런타임 보존 의무 소비 (레인 K 착지 후 · `tos_runtime.evidence.sinks` · `tos_runtime.compose` · 신규 `tos_runtime.rcl.obligation`)

- `GatewayEvidenceSinkAdapter` 에 선택 관찰자 `on_refusal: Callable[[GatewayEvidenceRecord], None] | None` — durable append **후** 호출(증거가 먼저). sink 는 RCL 을 쓰지 않는다.
- 신규 `CapacityObligationRecorder`(`tos_runtime/rcl/obligation.py`): `SEND_REFUSED` 이고 `preserved_worst_credible_capacity is not None` 이면 ① `ReservationProjectionReader.reservation_state(reservation_id)` 조회 ② 커널 `cur.obligation_preserved(obligation, state)` 호출 ③ 증거 `CAPACITY_OBLIGATION_PRESERVED`(attempt_id·reservation_id·obligation·state·verdict) append ④ verdict `False` 면 `record_halt`(기존 `_boot_integrity` 경로 재사용 — 권위-투영 불일치 경보) . reservation_id 는 `SendBoundaryContext.reservation_identity` 를 `GatewayEvidenceRecord` 가 이미 갖는지 확인, 없으면 레인 K 에 필드 추가 요청(보고 후 대기 · 직접 커널 편집 금지).
- compose `_wiring.py` 에서 recorder 를 sink 관찰자로 결선 · e2e: item 16 non-admit 시나리오(기존 거부 attestation e2e 재사용)에서 증거 행 1 + halt 0 · 예약이 RELEASED 인 합성 상태에서 halt 1(뮤테이션 M-B1: 관찰자 결선 제거 시 red).
- 의무 **값**의 출처는 attestation 그대로(Phase 5 대체 명시 유지) — 이 레인은 «기록·검증» 만 실현한다(§0 서베이 «차단은 이미 구조적»).

## 4. 기각 대안

- **레거시 kind 마이그레이션 코드**: 배포 실체 없음 · 마이그레이션은 새 안전 기구(기각). 거부만.
- **`IndependentApprovalDecision` 에 `issued_at` 추가**: covered 집합 변경으로 digest 픽스처 전부 붕괴 + 발행시각은 수신 사실(§12) — 런타임 `LoadedApproval` 로.
- **`max_decision_age_ms is None` ⇒ deny**: Phase 5 발행자 전까지 모든 승인 파일이 만료 설정을 강제받아 e2e 전량 붕괴 · ADR §8 은 만료를 policy 사실로 두므로 «미설정» 은 정직한 상태 — 증거 기록으로 가시화.
- **item 16 non-admit 시 예약을 `QUARANTINED_UNKNOWN` 으로 전이**: pre-send 거부는 potentially-live 가 아니며 해제는 이미 finality 증인 게이트 뒤 — 상태 전이는 새 기구·발명. 기록+검증만.
- **sink 가 RCL 쓰기**: 증거 어댑터에 권위 부작용 결합(D3 실패 도메인 분리 위반). 관찰자 분리.

## 5. 종료 조건

- `tos/tests` · `tos/runtime/tests` green(독립 실측 rc + «N passed» 줄) · 커널 diff 는 레인 K 커밋에만 · mypy/ruff/black 0 · firewall PASS · lint-imports KEPT · budget 0 위반(재등재 포함) · contract/completion/spec `--check` 통과.
- 4모듈 어디에도 `ADVANCE_RESTORE_GENERATION`/`CONSUME_TRANSMISSION_CAPABILITY`/`AUTHORIZE_TRANSMISSION_CAPABILITY` 재사용 없음(grep 0 · `currentness/stages.py` 의 실 TransmissionCapability 사용은 정당 · 유지).
- 뮤테이션: K-1 enum 멤버 제거 → A 테스트 red · A-1 `decision_unexpired` 호출 제거 → red · A-2 레거시 kind 건너뛰기 → red · B-1 관찰자 결선 제거 → red · K-2 item 16 필드 채움 제거 → red.
- 독립 리뷰(Claude 측 `code-reviewer` · 저작자와 분리) approve · 비협상 위반 0 · 권한 부여 0 · EV 상태 변경 0.

## 6. 가정(명시)

- **A1** Phase 2 런타임 sqlite 로그는 테스트 밖 배포 실체가 없다(모의투자 서버의 tos 실측은 이 런타임 로그를 쓰지 않는다). 있다면 새 코드가 거부하며 폐기는 운영자 결정.
- **A2** 승인 파일의 `issued_at_unix_ms` 는 운영자 수기 = 임시 발행자. Phase 5 서명 발행자 도입 시 이 키는 서명 앵커로 대체된다(커널 술어·런타임 경로는 그대로).

## 7. 실행 결과·독립 리뷰 처분

### 7.1 착지 (2026-09-08 · 브랜치 `feat/tos-phase2-kernel-round-1` · 10커밋 `89202006..f51ceaf3`)

| 레인 | 커밋 | 내용 |
|---|---|---|
| K | `89202006` `f46992a3` `1e06f0b8` `cba1972c` `286e82b5` | §1.1 enum +4(핀 27→31 · reducer 비-capacity 분기 실증) · §1.2 `decision_unexpired` · §1.3 `VerifyItemVerdict`/`GatewayEvidenceRecord` 타입 필드 + item 16 두 분지 + `_halt` 전달(gateway.py 1792→1806 · `__call__` 248→257 재등재) · §1.3 `cur.obligation_preserved` · §1.4 `\| None` |
| A | `08bf6d74` `1b1df3ec` `f51ceaf3` | §2.1 4모듈 kind 전환 + prefix 일치·kind 불일치 ⇒ `CommitLogCorruption`(epoch·iap 읽기; flow/proof 는 write-only) · §2.3 · §2.2 `load_operator_approval_with_receipt`+`LoadedApproval`(기존 로더 시그니처 불변) · `IntentRegistry` `time`/`receipt` 주입 · 소비 증거 `expiry_verdict`/`age_bound_ms`/`receipt_anchor` · 신규 키 `MAX_clock_domain_conversion_uncertainty_ms`(VERIFICATION-PROFILE-002.yaml:1070 인용) |
| B | `31649d22` `8a0b83e7` | §3 `GatewayEvidenceSinkAdapter.on_refusal`(durable append 후) · `tos_runtime.rcl.obligation.CapacityObligationRecorder`(주입 resolver · 단일 상품 root 는 `resv-{account}-{instrument}` 정확 일치) · compose 결선 · 뮤테이션 M-B1 red |

**계획 편차(전부 보고·수용)**: ① `obligation_preserved(obligation, reservation_state: str \| None, capacity_consuming_states: frozenset[str])` — cur 임포트 폐쇄(§7.1 allowlist)가 `tos.rcl` 힌트조차 금지 · 계획 예시의 «POSITION_CONSUMED=해제» 는 커널 `_LIVE_COMMITTED_STATES`(RELEASED 만 비소비)와 모순이라 커널 집합 채택 ② `decision_unexpired` 는 `iap/predicates.py` 모듈 `__all__` 에 미등재 — 등재 시 EVIDENCE-SURFACE-MAP 행 핀(IAP-EV-003/004/007) 이탈로 completion `--check` RED 실측 · 패키지 재수출로만 공개 ③ `load_operator_approval_file` 무변경 + 신규 함수(호출처 ~15 보존) ④ `queue_bound=0`(Phase 2 time 설정은 transport+queue 결합 키 하나) ⑤ 레인 A 도크스트링 축약으로 크기 예외 신규 0.

**보고된 갭 2건(이 라운드에서 고치지 않음 · 다음 결정 항목)**:
- **G-1 만료 admit 경로 도달 불가(리뷰 #3 로 정정)**: 착지 시점 블로커는 셋이었다 — ① `TrustworthyTimeService._issue_snapshot` 이 `wall_clock_observation` 을 채우지 않음(`LocalSystemClockReader` 는 값을 «도달성 프로브» 로만 씀 · 슬라이스 #1 설계) ② compose 가 `load_operator_approval_file` 만 호출해 receipt 가 생성되지 않음 ③ `IntentRegistry` 가 `time`/`time_config` 없이 구성됨. ②③은 처분 A2-#3 에서 결선했다. **잔여 블로커는 둘(재심 R#1 로 정정)** — ① `wall_clock_observation` 미충전, ①′ `suspension_status.suspension_ms` 미충전(`_issue_snapshot` 이 둘 다 안 채움 · 후자는 #2 정직 수정으로 IAP 가 관측값을 읽게 되면서 새로 하중을 받음 · 재심이 실 compose 런타임에서 실측: TRUSTED 인데 두 필드 None). 실 서비스에서는 `max_decision_age_ms` 설정 시 두 경로가 각각 독립으로 fail-closed deny(정직 · 안전). admit 은 `FakeTimeService` 로만 실증. 해소 = 슬라이스 #1 time 설계의 «값 비노출» 결정 개정 + `time/service.py:258` 의 자기 `anchor_valid` 호출에 남은 `suspension_ms=0` 리터럴 동반 정리(재심 carry-forward · 운영자 결정 · 다음 라운드 게이트).
- **G-2 보존 의무 기능의 프로덕션 도달성 0(리뷰 #6 로 문언 정정)**: `EgressCurrentnessProofIssuer.issue()` 는 `proof_admissible`(CURRENT 필수) 자체검사 후에만 proof 를 내고, 런타임은 `egress_currentness_result = proof.result` 로 결속하므로 admissible 한 proof 가 non-ADMIT verdict 를 낼 수 없다(두 겹 잠금 · 리뷰어 독립 검증). 따라서 `CapacityObligationRecorder` 는 현재 런타임에서 **도달 불가 코드로 착지**했다 — 분기는 커널 테스트가 덮고, 런타임 e2e 는 실제 결선된 sink 에 `SEND_REFUSED` 형상을 직접 주입해 관찰자·증거·예약 id 해석(«결선»)을 증명한다. 트리거를 살리는 발행자 변경은 다음 라운드의 게이트 항목(운영자 결정).

**환경 결함 1건(코드 아님)**: 로컬 `.venv` 의 tos editable `.pth` 가 삭제된 워크트리(`../kis_unified_sts-tos-phase2/tos/src`)를 가리켜 `tos` 가 네임스페이스 패키지로 폴백 → `lint-imports` BROKEN(239행)·런타임 mypy 15건이 «기저 실패» 로 보였다. `pip install -e ./tos` 재설치 후 `lint-imports` 3 KEPT · 런타임 mypy clean. CI 는 매 실행 새로 설치하므로 무관.

**독립 실측(최종 트리 `f51ceaf3` · 재설치 venv)**: runtime tests **462 passed** rc=0 · kernel tests **9078 passed** rc=0 · mypy 커널 253파일/런타임 53파일 clean · ruff 0 · black 924 unchanged · firewall PASS · lint-imports 3 KEPT · budget 0 위반(29 등재) · contract PASS · completion GREEN · spec PASS · 커널 diff(`286e82b5..HEAD -- tos/src/`) 0.

### 7.2 독립 리뷰 처분 (Claude 측 `code-reviewer` 레인 · 저작자와 분리 · 2026-09-08)

1차 verdict **needs-attention** · 비협상 위반 0 · 뮤테이션 M1~M6 전부 red + 리뷰어 추가 M7(`suspension_ms=0`→`None`) red(= #2 의 증거) · 스펙 정합(ADR-002-012 §10 «at minimum … semantics equivalent» · 편차 ① 커널 집합 채택 정당) 수용 · 레거시 kind 읽기 3곳 전수(epoch:344 · iap:603/677) 전부 raise 확인 · fail-open 프로브 9종 clean.

| # | 심각도 | 지적 | 처분 |
|---|---|---|---|
| 1 | HIGH | item 16 의무가 «첫 halt 항목이 16일 때» 만 `SEND_REFUSED` 로 전달 — 앞 항목이 같이 실패하면 의무 유실(실측: construction=None+currentness None ⇒ oblig None) · 기존 테스트는 item 16 SATISFIED 픽스처라 거짓 안심 | 수용 — K2-#1: halt item 무관하게 item 16 verdict 의 의무 전달 · 동시 실패 테스트 · 거짓 안심 테스트 재명명 |
| 2 | HIGH | `iap.py:744` `suspension_ms=0` 리터럴 — 관측 없이 0 을 단언해 `anchor_valid` 의 suspension 가드가 영구 통과 · M7 이 admit 테스트 2건을 red 로 | 수용 — A2-#2: `snapshot.suspension_status.suspension_ms`(None ⇒ fail-closed) 로 교체 · None/초과 deny 테스트. 형제 `time/service.py:258` 의 동일 리터럴은 슬라이스 #1 기존 코드 — time 슬라이스 결정 항목으로 기록 |
| 3 | MEDIUM | G-1 이 블로커를 하나로 축소 서술 — compose 미결선(receipt 로더·time 포트) 2건 추가 | 수용 — A2-#3: compose 결선 + `stages.py` receipt 전달 · G-1 문언 정정(위) |
| 4 | MEDIUM | «의무 없음» 과 «의무 크기 UNKNOWN» 을 구별 못 함 — 가장 위험한 입력이 가장 조용한 처리로 강등(attestation null 거부로 잠재) | 수용 — K2-#4: `preserved_obligation_magnitude_unknown` 타입 필드 + `obligation_preserved(magnitude_unknown)` 필수 kwarg(True ⇒ False) · B2-#4: 레코더 제3 분기(증거+halt) |
| 5 | MEDIUM | resolver 가 attempt 를 버리고 (account, instrument) 고정 id 를 냄 — «EXACT» 과대 문언 · 같은 id 아래 새 예약이 오면 옛 의무를 새 상태로 검증 | 수용 — B2-#5: attempt→예약 결속이 로그/스테이지에 있으면 그것으로 해석, 없으면 문언 정정 + 한계 테스트(선택 근거 보고) |
| 6 | MEDIUM | 레인 B e2e 는 결선만 증명 · G-2 는 «분기 도달 불가» 가 아니라 «기능의 프로덕션 도달성 0» | 수용 — G-2 문언 정정(위) · 발행자 변경은 다음 라운드 게이트 · e2e 도크스트링 1문장 |
| 7 | LOW | receipt 없는 로더가 non-null `max_decision_age_ms` 거부를 잃음(소비에서 영구 deny 로 밀림 · `_decision_provider` 가 로더 오류를 None 으로 삼킴) | 수용 — A2-#7: receipt-less 로더 거부 복원 · 로더 거부를 `IAP_APPROVAL_FILE_REFUSED` 증거로 가시화 |
| 8 | LOW | 관찰자 결선으로 거부 경로가 예외를 낼 수 있음(계약 변경) | 수용(fail-closed) — B2-#8: 계약 변경 문서화 |
| 9 | LOW | `None` 경우 열거 누락(래치/구조 게이트 halt · 크기 UNKNOWN) · «halt 가 16이 아니거나» 오기 | 수용 — K2-#9 / B2-#9 도크스트링 4경우 전수 |

**처분 착지(7커밋 `b7f497e3..d38fb5f1`)**: A2-#2 `b7f497e3` · B2-#5/#8/#9 `9c0771ab` · K2-#1/#9 `3522a608` · K2-#4 `5521ec7b` · A2-#3 `a8aab25c` · B2-#4 `5a77d366` · A2-#7 `d38fb5f1`. 처분 중 확인된 사실: #5 는 attempt→예약 결속이 로그·스테이지 어디에도 없어(전이 행에 attempt 없음 · step 9 캐시 없음 · step 14 는 nonce 만 보존) (b) 문언 정정 + 비-attempt-scoping 실증 테스트 채택, «RELEASED 후 재사용» 경쟁은 `check_reservation_from_state` 게이트가 이미 차단(프로브 실측) · #4 런타임 측은 별 분기가 아니라 기존 resolve→술어→증거→halt 경로 공유(커널 술어가 `magnitude_unknown=True` 를 무조건 False 로) · #3 결선 후 G-1 잔여 블로커는 `wall_clock_observation`·`suspension_status.suspension_ms` 미충전 **둘**(A2 는 «하나» 로 보고 → 재심 R#1 이 실 런타임 실측으로 정정). 크기 예외 +2(`_wiring.py`·`iap.py` · tos-runtime 소유 · 정렬 위치는 후속 정리). 공유 트리 경합 재발: K2 `5521ec7b`·B2 `9c0771ab` 커밋이 A2 의 미커밋 `_wiring.py`/budget 헝크를 함께 실음(내용 손실 0 · `[A2-#3]` 본문에 경위 기록).

**독립 실측(최종 트리 `d38fb5f1`)**: runtime **471 passed** rc=0 · kernel **9099 passed** rc=0 · mypy 253/53 clean · ruff 0 · black 925 unchanged · firewall PASS · lint-imports 3 KEPT · budget 0 위반(31 등재) · completion GREEN · spec PASS · contract PASS · 커널 diff(`5521ec7b..HEAD -- tos/src/`) 0 · tos-spec/계약 문서 무편집.

### 7.3 재심 (2026-09-08 · 같은 리뷰어)

verdict **needs-attention → 열린 항목 1건(문서 전용)**: 9건 전부 동작으로 종결(#1 동시 실패 프로브 oblig=1 · #2 관측 경로 · #3 결선 3좌표 · #4 양 레코드 플래그+커널 단락+레코더 halt · #5 (b) 수용 + `check_reservation_from_state` 프로브로 RELEASED 종단 확인 · #6/#8/#9 문언 · #7 거부 복원+증거) · 재심 뮤테이션 R-M1~R-M5 전부 red · 크기 등재 4건 `measured`=실측 · 공유 트리 오귀속 내용 손실 0 · 신규 리터럴 0 · 신규 fail-open 0. **R#1(MEDIUM · 문서)**: G-1 잔여 블로커는 둘(위 문언 정정 + `_wiring.py` 주석 정정으로 처분). carry-forward: `time/service.py:258` `suspension_ms=0`(G-1 게이트 항목에 병기 · 위 반영). 재심이 든 spec 기준선 경고(163→164)는 이 라운드 이전부터 존재(세션 시작 실측) — 개발계획 §1 표의 별도 문서 정정 항목. **최종 verdict approve**(`e06b2768` 확인 · 리뷰어가 기준선 경고 귀속 정정 인정: `aa348ce1..HEAD -- tos-spec` 공집합). 이 라운드 종결 · push/PR 은 운영자 수동.
