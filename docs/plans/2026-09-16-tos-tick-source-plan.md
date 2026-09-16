# TOS 틱 원천 웨이브 계획 — `tos.marketfeed` 런타임 어댑터(CIS) + 틱 스케줄러

- **상위**: `compose/cli.py:96-100` 차단 (c) 「No tick source — 모든 실호출자가 테스트 픽스처」 · 운영자 2026-09-16 「다음 웨이브 순서 1. ★ (c) 틱 원천 … 1번부터 병렬 처리 가능한 부분 별도 워크트리로」 · design #32(`docs/plans/2026-07-29-tos-marketfeed-design.md`) · design #38(admitted-snapshot injection port) · design #33 §3.4(yield-order) · FORWARD-OBLIGATION-MS1.
- **선행**: action-flow 관측 웨이브 완료(main `e3e26e3e`) · 런타임 스위트 baseline green(2026-09-16 실측, exit 0).
- **저작**: 세션 모델 단독 · **커널 diff 0**(`tos/src/tos` 무접촉) · 신규 런타임 패키지 `tos_runtime.marketfeed`.
- **브랜치**: `feat/tos-tick-source`(워크트리 `../kis_unified_sts-ticksource`) — 계약 커밋 뒤 레인 A/B/C 를 각자 워크트리로 분기.

## 0. 서베이 실측 (요지)

| 항목 | 실측 (`file:line`) | 함의 |
|---|---|---|
| 틱을 만드는 프로덕션 코드 | 없음. `DecisionContextCapsule.issue`/`CriticalInputSnapshot.issue` 호출자는 전부 테스트 픽스처 — `tos/tests/**` **와 `tos/runtime/tests/**`**(후자에도 5개 파일: `compose/_fixtures.py:280`·`compose/test_preconditions.py:99`·`backtest/test_symmetry.py:111`·`engine/_fixtures.py:84`·`engine/_parity_fixtures.py:258`). 정본 실측은 **`tos/src`·`tos/runtime/src` 합쳐 0건**(계약 리뷰 LOW 지적으로 인용 경로 정정) · 컴포즈 e2e 는 `tests/compose/_fixtures.py:278-355` 이 capsule·value_view·time·reference 를 전부 손으로 만듦 | (c) 는 「어댑터 하나」가 아니라 **CIS(Context Integrity Service) 런타임 부재** |
| 리졸버 | `MarketFeedContextResolver`(`marketfeed/resolver.py:135`)는 이미 실물. 주입 3구: `SnapshotStore`(`:62`) · `ValueCandidateSource`(`:84`) · `TimeCoordinateProjection`(`:103`) | **커널 신규 0** — 런타임은 이 세 포트의 구현자만 만든다 |
| 엔진 슬롯 | `EngineCore` 는 리졸버를 받지 않는다 — `DecisionContextResolver` 는 Protocol 선언뿐(`engine/core.py:94`) | 틱 원천은 **호출자 측**. compose 에 새 코어 인자 0 |
| 순서 좌표 | `EngineDriver._stamp`(`engine/driver.py:397`)가 호출자 reference 를 버리고 자체 카운터로 재스탬프(step 7 웨이브 §7 발견) | 틱 원천은 `reference` 를 **주장하지 않는다**(리졸버 `__call__` 독스트링과 동일 규율) |
| 직접 관측 | lineage 노드가 없는 값은 `VALID` 를 물려받음(`marketfeed/value.py:309-311`) — 파생이 아니므로 재현성을 따질 게 없음 | **직접 관측만 하는 1차 웨이브가 가능** · 파생 지표(밴드 등)는 `TransformationLineage` 필요 → 비범위 |
| VALID 게이트 | 스냅샷의 `FieldEvaluation` 이 그 키를 지명하지 않으면 명시적 `UNKNOWN` 바닥(`value.py:225-229`) | 필드 상태를 무조건 `VALID` 로 찍으면 **팬텀** — 거버넌스된 정책에서 파생해야 함 |
| 값⟺digest | `_admit_one`(`value.py:514-523`)이 preimage 를 재digest 해 관측의 `raw.payload_digest` 와 대조 | CIS 는 preimage 를 **내구 보관**해야 후속 틱에서 후보를 다시 낼 수 있음 |
| 분별(distinctness) | 「완전한 per-bar distinctness 집행은 상류 CIS 소관」(`tos/tests/marketfeed/test_marketfeed_cis_port.py:46-49`) | 이 웨이브가 그 의무를 **인수**한다 — as_of 중복 틱 거부 |
| 가격 (a′) | `OrderConstructionStage._price_for`(`egressgw/construction.py:986-996`): `price_field_key` 가 있고 틱에 view 가 있으면 **view 가 이긴다** → `admitted_price_from_view`(`:200`) | **(a′) 의 `price` 항은 (c) 로 구조적으로 해소** — 별도 웨이브 불필요 · 주입 `construction.price` 는 value-free 틱의 폴백으로 격하 |
| 세션 컨텍스트 | `SessionFactsOwner.session_context(instrument_class)`(`calendar/owner.py:238`) 가 이미 실물 `SessionContext` 를 낸다 | 시간 투영이 `SessionContext` 를 **날조하지 않는다**(픽스처 `_fixtures.py:263-272` 가 손으로 만들던 것) |
| 시간 경계값 | `time.example.yaml` 이 VER-002 키 8종 보유(`:20`~`:84`). marketfeed 가 지명하는 `MAX_critical_input_consumer_receipt_age_ms`·`MAX_time_source_sequence_gap_ms` 는 로더 `_BOUND_KEYS`(`time/config.py:35-64`)에 **없다**. 단 둘 다 VERIFICATION-PROFILE-002 에 **APPROVED 값 보유**(`:1067` = 1000 ms · `:1077` = 50 ms · 둘 다 2026-07-29 Bounds-Approver) | **새 승인 라운드 불필요** — `MAX_clock_domain_conversion_uncertainty_ms` 가 밟은 「승인값을 근거 인용과 함께 verbatim 재사용」 경로를 그대로(`time/config.py:43-53`) |
| 방화벽 | 런타임 스코프는 `socket`/`ssl`/`http`/`urllib.request` 카브아웃(`tools/tos_firewall_check.py:238-249`) · `time.sleep` 선례(`transport/kis_mock/adapter.py:480`) · `shared.*` 는 런타임에서도 전면 금지(규칙 (h)) | 폴 루프는 런타임 스코프에서 **합법** · 레거시 `shared.kis`/`shared.streaming` 재사용은 **불가** |
| 다심볼 | FORWARD-OBLIGATION-MS1 — 라이브 다심볼 EventSource 의 단일 연속성 수집 순서 의무는 **미비준**(`tos/src/tos/backtest/driver.py:78-86`) | 1차 웨이브는 **단일 instrument** · 다심볼은 명시적 비범위 |
| 크기 | `module_max_lines: 1000` · `function_max_lines: 100` · 런타임 스코프 등재 예외는 **9건**(전체 39건 중 — `_wiring.py` 1122행 · `authority/iap.py` 1026행 등). ~~0건~~ 은 저작 시 `config/tos_size_budget.yaml:23-33` 의 **2026-09-07 자 주석**을 실측 대신 인용한 오류(계약 리뷰 MEDIUM 지적) — 주석이 stale 이고 데이터가 정본 | 새 모듈 전부 1000행 이하 · **이번 웨이브는 예외를 등재하지 않는다**(선례가 없어서가 아니라, 예산 상한에 이미 붙어 있는 모듈은 등재가 아니라 분해가 답이기 때문 — `compose/cli.py` 는 직전 웨이브가 정확히 1000행에 맞춰 둬서 헤드룸이 0) |

## 1. 목표 · 범위 · 비범위

**목표**: `tos_runtime` 이 거버넌스된 정책 아래 **실 관측 → 스냅샷 발행 → 내구 보관 → Capsule 발행 → 실 `MarketFeedContextResolver` → `DECISION_TICK`** 을 만들고, 스케줄러가 주입 클록·세션 사실로 그 틱을 `EngineDriver` 에 넣는다. 차단 (c) 를 해소하고, (a′) 의 `price` 항을 구조적으로 해소한다.

**범위**: 신규 `tos_runtime/marketfeed/`(`ports`·`policy`·`snapshot`·`capsule`·`store`·`journal`·`time_projection`·`scheduler`) · 신규 거버넌스 정책 `critical_input_policy.yaml`(VCP/OCP 와 동일 관용구 · `print-policy-digests` 확장) · 스냅샷 내구 스토어 스키마(마이그레이션) · compose 결선 + e2e · `cli.py` 차단 목록 정정 · config 예시 + `config/tos_runtime/paper/` 실파일 · README/INDEX/§7.

**비범위**: 커널 편집 · **파생/지표 값**(`TransformationLineage` 필요) · **다심볼**(FORWARD-OBLIGATION-MS1 미비준) · **KIS 모의투자 시세 HTTP 어댑터**(브로커 스코프 능력·TR id·토큰 커스터디가 별도 — §6 ① 후속 웨이브로 명명) · `run` 서브커맨드의 데몬화((a′) `envelope`/`order_shape` 잔존으로 여전히 차단) · RCL 벡터·브로커 증인(P-BAL).

## 2. 결정

1. **CIS 는 런타임 신규 패키지 `tos_runtime.marketfeed`.** 커널은 손대지 않는다. 포트 3구의 구현자 + 스냅샷/Capsule 발행자 + 스케줄러만 만든다. 리졸버는 커널 실물을 그대로 주입한다.
2. **필드 상태는 거버넌스 정책에서 파생한다 — 절대 `VALID` 를 찍지 않는다.** 신규 **Critical Input Policy (CIP)** YAML(`critical_input_policy.yaml`)이 (i) 관측을 허용하는 `field_key` 집합, (ii) 키별 `unit`/`scale`/`multiplier`/`sign` 매핑, (iii) 키별 신선도 상한(ms), (iv) `intended_use`/`decision_class`/`environment` 스코프를 선언한다. 로더는 VCP/OCP 와 같은 관용구(fail-closed · null 거부 · `policy_id`/`policy_version`/`policy_generation`/`canonical_digest` · `print-policy-digests` 출력 · `safety_activation.yaml` 손채움)를 따른다. `FieldEvaluation.state` = 「정책이 지명한 키인가 ∧ as_of 가 신선도 상한 안인가 ∧ 스칼라 투영이 정확한가」의 **worst** — 하나라도 못 세우면 `UNKNOWN`(VALID 아님).
3. **스냅샷은 내구 보관한다.** 새 sqlite 스키마(`marketfeed_snapshots` + `marketfeed_preimages`), 기존 `operations/schema_migrations.py` 마이그레이션 경로로 도입. 읽기는 content-addressed 이며 **digest 재검증**(`snapshot_id` 일치만으로 본문을 내주지 않는다 — `_slice_fixtures.py:404-408` 의 정직 규칙). 없는 스냅샷은 `None`(대체 금지).
4. **관측 원천은 포트 + 이번 웨이브 구현 1종.** `ObservationIntake` 포트(아래 계약) + **파일 기반 관측 저널**(`journal.py`) — 상류 수집기가 append-only 로 쓰는 JSON Lines. 결정적·헤르메틱하며 네트워크 0. 실 시세 HTTP 어댑터는 §6 ① 후속.
5. **as_of 분별은 CIS 가 집행한다.** 같은 instrument 에서 이미 발행한 as_of 이하의 관측은 **틱을 만들지 않는다**(`TickOutcome.SKIPPED_NOT_NEWER`). design #38 이 상류 의무로 남긴 항목을 여기서 받는다.
6. **시간 투영은 실 서비스에서 읽는다.** `RuntimeTimeProjection` 은 `TrustworthyTimeService.current_snapshot()`(health/anchor)·`wall_clock_now()`·`SessionFactsOwner.session_context()`·`TimeConfig` 의 VER-002 경계값을 조합한다. 어느 하나가 없으면 그 좌표는 `None` 으로 남기고(= 입장 거부, 제한적), 기본값을 날조하지 않는다.
7. **스케줄러는 순수 결정 + 얇은 루프로 분리.** `decide_tick(...)` 은 주입값만 받는 순수 함수(세션이 틱을 허용하는가 · 새 관측이 있는가 · 간격이 찼는가) → `TickOutcome`; `TickScheduler.run_forever()` 는 그 결정을 `time.sleep` 과 `driver.enqueue_and_run` 에 연결하는 얇은 껍데기. 테스트는 전부 순수 함수와 `tick_once()` 를 친다.
8. **`reference` 미주장 · 단일 instrument.** 틱 페이로드는 `reference` 를 비우고 드라이버 `_stamp` 에 맡긴다. 스케줄러는 한 instrument 만 돌리며, 다심볼 요청은 **부팅 거부**(FORWARD-OBLIGATION-MS1 미비준을 사유로 명시).
9. **`run` 은 계속 차단.** (c) 해소를 `cli.py` 차단 목록에 반영하되, (a′) 의 `envelope`/`order_shape` + `intent_id`/`envelope_id`/`command_id`/`generation` 리터럴이 남으므로 `run` 은 파싱 전용 유지. 「(c) 해소」와 「`run` 가동」을 같은 문장에 쓰지 않는다.

### 계약 (레인들이 함께 짓는 표면 — 계약 커밋으로 먼저 착지)

```python
# tos_runtime/marketfeed/ports.py  — 로직 0, 시그니처만
@dataclass(frozen=True)
class RawObservation:
    raw_event_id: str; instrument: str; as_of_ms: int
    fields: tuple[tuple[str, ScalarValue], ...]   # 평면 preimage 엔트리
    source_id: str; received_ms: int | None = None

class ObservationIntake(Protocol):
    def poll(self, *, instrument: str, after_as_of_ms: int | None) -> Sequence[RawObservation]: ...

class DurableSnapshotStore(Protocol):          # SnapshotStore ∪ ValueCandidateSource 의 구현자
    def put(self, snapshot: CriticalInputSnapshot, preimages: Mapping[str, RawPayloadPreimage]) -> None: ...
    def __call__(self, *, snapshot_id: str | None, canonical_digest: str | None) -> CriticalInputSnapshot | None: ...
    def candidates(self, snapshot: CriticalInputSnapshot, *, instrument_key: InstrumentKey) -> Sequence[AdmittedValue]: ...
    def latest_as_of(self, *, instrument: str) -> int | None: ...

class TickOutcome(StrEnum):
    TICKED = "TICKED"; SKIPPED_NO_OBSERVATION = "SKIPPED_NO_OBSERVATION"
    SKIPPED_NOT_NEWER = "SKIPPED_NOT_NEWER"; SKIPPED_SESSION_CLOSED = "SKIPPED_SESSION_CLOSED"
    SKIPPED_INTERVAL = "SKIPPED_INTERVAL"; REFUSED_POLICY = "REFUSED_POLICY"
```

## 3. 기각 대안

| 대안 | 기각 사유 |
|---|---|
| `shared/kis`·`shared/streaming` 의 실 시세 경로 재사용 | 방화벽 규칙 (h) — 런타임 스코프도 `shared.*` 전면 금지(`tos/CLAUDE.md` §firewall) · 「레거시는 tos 의 참조 구현이 아니다」 |
| 커널에 CIS 를 만든다 | design #2 §0.2 가 CIS 런타임을 커널 범위 밖으로 명시 · 커널은 네트워크·클록 금지 |
| 틱마다 `FieldEvaluation(state=VALID)` 를 찍는다 | 「구조 파생 > 자기신고」 위반 · `value.py:202-206` 이 봉한 vacuous validity 를 우회하는 팬텀 |
| 스냅샷을 메모리에만 둔다 | 재시작 후 이전 스냅샷의 view 를 재현할 수 없고, 값⟺digest 재검증에 preimage 가 필요 · 복구/재생 경로가 조용히 끊김 |
| 파생 지표(밴드)까지 이번에 | `TransformationLineage` + 부모 인과(`value.py:320-336`) 가 필요 — 별도 설계 · 직접 관측만으로도 실전략 1개가 성립(전략이 `config` 임계값과 비교하면 `compare_has_capsule_operand` 충족) |
| 다심볼 레인 | FORWARD-OBLIGATION-MS1 미비준 — 단일 연속성 수집 순서 의무가 라이브 쪽에 없다 |
| 시세 HTTP 어댑터를 같은 웨이브에 | 브로커 스코프 능력·TR id·토큰 커스터디·레이트리밋이 별도 거버넌스 — 웨이브가 두 배 · §6 ① 로 분리 |

## 4. 레인 (병렬 — 각자 워크트리)

| 레인 | 파일(배타) | 워크트리 | 의존 |
|---|---|---|---|
| **계약**(세션 모델) | `marketfeed/__init__.py` · `marketfeed/ports.py` · 계획 문서 | `-ticksource` | 없음 — **먼저 착지** |
| **A**(executor·sonnet) | `marketfeed/policy.py`(CIP 로더) · `marketfeed/snapshot.py`(발행) · `marketfeed/capsule.py` · `config/critical_input_policy.example.yaml` · 대응 tests | `-tick-a` | 계약 |
| **B**(executor·sonnet) | `marketfeed/store.py`(sqlite) · `operations/schema_migrations.py` 항목 추가 · 대응 tests | `-tick-b` | 계약 |
| **C**(executor·sonnet) | `marketfeed/journal.py` · `marketfeed/time_projection.py` · 대응 tests | `-tick-c` | 계약 |
| **D**(통합) | `marketfeed/scheduler.py` · `compose/_marketfeed_wiring.py` · `compose/root.py`·`_types.py` · `cli.py` 차단 목록 · e2e | `-ticksource` | A∧B∧C |
| **E**(세션 모델) | README · `docs/plans/INDEX.md` · §7 · `config/tos_runtime/paper/critical_input_policy.yaml` | `-ticksource` | D |
| 리뷰 | `code-reviewer`(**sonnet**, 저자와 다른 패스) 전 PR · **B 는 `migration-reviewer` 추가** | — | PR 별 |

## 5. 종료 조건 · 뮤테이션

- 실증: (1) 저널에 관측 1건 → 스케줄러 `tick_once()` 가 **실 리졸버**를 통해 `value_view` 가 채워진 `DECISION_TICK` 을 만들고 드라이버가 처리 (2) 같은 as_of 재투입 → `SKIPPED_NOT_NEWER`, 틱 0 (3) 정책이 지명하지 않은 `field_key` → 그 값만 탈락하고 view 는 발행(나머지는 통과) (4) 신선도 상한 초과 → `FieldEvaluation` `UNKNOWN` → `FIELD_STATE_NOT_VALID` 로 탈락 (5) preimage 변조 → `DIGEST_MISMATCH` (6) 스토어가 다른 digest 의 본문을 반환 → `BINDING_MISMATCH`(대체 거부) (7) 세션 닫힘 → `SKIPPED_SESSION_CLOSED` (8) 재시작 후 같은 스냅샷 id 로 view 재현(내구성) (9) **compose e2e**: 손으로 만든 `crossing_event()` 대신 CIS 가 만든 틱으로 step 2 가 `admitted_price_from_view` 경로를 타는 것을 `AdmittedPriceObservation.value_payload_digest` 비어있지 않음으로 실증 (10) 다심볼 요청 → 부팅 거부.
- 뮤테이션: M1 `FieldEvaluation` 을 무조건 VALID → (4) red · M2 as_of 분별 제거 → (2) red · M3 스토어 digest 재검증 제거 → (6) red · M4 preimage 내구 저장 생략 → (8) red · M5 `reference` 를 틱에서 주장 → 드라이버 재스탬프 대조 테스트 red · M6 `price_field_key` 미결선 → (9) red · M7 세션 게이트 제거 → (7) red · M8 정책 로더의 null 거부 제거 → 로더 red · M9 다심볼 거부 제거 → (10) red.
- 게이트: `tools/tos_firewall_check.py` · `lint-imports` · `tools/tos_size_budget.py --check`(신규 모듈 전부 예산 내, 예외 등재 0) · `ruff`/`black`/`mypy` · 런타임+커널 스위트.
- 정직 상태(예상): 관측 원천은 **파일 저널 1종**(실 시세 트랜스포트 미착지 — 「라이브 피드」가 아니라 「상류 수집기가 쓴 저널」) · 직접 관측만(파생 지표 0) · 단일 instrument · `run` 은 (a′) `envelope`/`order_shape` 로 계속 차단 · `committed_flow_vectors` 여전히 `()` · 포지션 단일 원천(변화 없음).

## 6. 운영자 확인

1. **시세 트랜스포트**: 이번 웨이브는 파일 저널만(추천 · 결정적·헤르메틱) → 실 KIS 모의투자 시세 HTTP 어댑터는 후속 웨이브 (c2) 로 분리. 아니면 (c) 안에 포함할지.
2. ~~VER-002 경계값 2종 신규 승인~~ — **불요로 판명(저작 중 실측 정정)**. 두 키 모두 VERIFICATION-PROFILE-002 에 2026-07-29 APPROVED 값 보유(`:1067` 1000 ms · `:1077` 50 ms). 레인 C 가 `MAX_clock_domain_conversion_uncertainty_ms` 선례대로 근거 인용과 함께 `_BOUND_KEYS` 에 추가한다. 운영자 조치 없음.
3. **마이그레이션 심사**: 레인 B 는 새 sqlite 스키마 — `migration-reviewer` 는 자동으로 돌린다. **Codex 독립 심판**(되돌리기 어려운 경로 = DB 마이그레이션)은 유료 외부 호출이므로 **범위·비용 승인 시에만** 디스패치 — 붙일지 여부.
4. 다음 순서(잔여): (a′) `envelope`(승인 Intent/IAP) · `order_shape`(전략 제안) → 브로커 증인(P-BAL)/band 원천 → 실 HSE 인스턴스 → 커널 라운드 #4.

## 7. 착지 기록

(웨이브 완료 후 채움)
