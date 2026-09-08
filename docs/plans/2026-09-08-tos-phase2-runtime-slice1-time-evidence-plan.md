# TOS Phase 2 런타임 슬라이스 #1 — Trustworthy Time 서비스 · durable Evidence Store (설계 #40 §5 순서 1·2)

- **상위**: 설계 #40 (`docs/plans/2026-09-07-tos-phase2-runtime-shell-preliminary-decisions.md`, **운영자 비준 2026-09-08**) D1·D3·D4 · 개발계획 §6 Phase 2 구현 순서 1·2 · 장애 계약 7종
- **운영자 지시 (2026-09-08)**: 「1,2,3,4 모두 비준, 승인」 → §5 순서 1·2 병렬 착수
- **저작**: 세션 모델 단독 · **권한 부여 없음** · 어떤 EV 행도 닫지 않음(EV 실행은 Phase 6)
- **위치**: 전부 `tos/runtime/src/tos_runtime/` (D1 · 방화벽 R1) · 테스트 `tos/runtime/tests/` (D1.4 hermetic — 루프백만 · tmp_path 안 쓰기만 · env 0)

## 0. 공통 규율

- 커널 Protocol 심을 **구현**한다. 커널을 편집하지 않는다(필요한 커널 포트가 없으면 보고 — 이 슬라이스에서 커널 diff 는 0 이 목표).
- 정상 API 보다 **장애 계약 테스트를 먼저** 쓴다(상위 계획 Phase 2). 각 서비스 파일 상단 docstring 에 «이 서비스가 만족하는 장애 계약 번호 ①~⑦» 표를 둔다.
- 임계값·기간·경로는 코드 상수가 아니다: 런타임 설정 `tos/runtime/config/*.yaml` 예시 파일 + 로더(pyyaml) — 값은 `named-TBD` 허용(운영자 승인 대상), 부재 시 기동 거부(fail-closed).
- 클록·RNG·파일·소켓은 런타임에서만, 그리고 **주입 가능**해야 한다(테스트에서 가짜 단조 소스·가짜 파일시스템 경로).
- 모든 durable 쓰기는 «영수증 없으면 일어나지 않았다»(D3 · `EvidenceAppendReceipt`/`AppendReceipt` 는 커밋 후에만).
- 크기 budget(모듈 1000·함수 100)·Black·Ruff·mypy·방화벽 R1·lint-imports 3계약 전부 green.

## 1. 레인 K — `tos_runtime.time` (순서 1: Trustworthy Time + generation/epoch)

**소비 대상(커널)**: `tos.time` 의 `MonotonicReading`·`ReferenceSource`·`Bounds`·`TimeContinuityIdentity`·`EvaluatedMonotonicAnchor`·`TimeHealthSnapshot`(DigestBoundArtifact)·`HealthState`·술어 `freshness_verdict`/`health_transition_allowed`/`transition_to_trusted_requires_new_generation`/`recovery_generation_revives_nothing`/`anchor_valid`/`snapshot_age_admissible`/`independent_reference_count`/`source_disagreement_within_bound`. **`tos.workload.RuntimeIdentity`**(D4) 를 스냅샷에 결속.

**산출물**
1. `tos_runtime/time/sources.py` — `MonotonicSource` Protocol + `ProcessMonotonicSource`(`time.monotonic_ns` — 커널이 금지하는 «클록 읽기»가 런타임에 처음 실재) + `ReferenceSourceReader` Protocol(참조 시각원: Phase 2 는 «로컬 시스템 시각» 1종만 구현 · NTP/브로커 시각은 미구현으로 명시 — ADR-002-008 :184 단일 소스 잔여 위험은 등재).
2. `tos_runtime/time/service.py` — `TrustworthyTimeService`: 기동 시 `TimeContinuityIdentity` 발급(RuntimeIdentity.runtime_generation 과 같은 트랜잭션 개념 — Phase 2 에서는 «같은 기동 이벤트에서 함께 발급» 으로 실현하고 D2 로그 결합은 순서 3 소관) · 주기 평가로 `TimeHealthSnapshot` 생성(커널 술어로 판정 · 런타임은 판정하지 않고 **입력을 모아 커널 술어를 호출**) · `HealthState` 전이는 `health_transition_allowed` 를 통과한 것만 · UNTRUSTED/DEGRADED→TRUSTED 는 `transition_to_trusted_requires_new_generation` 대로 새 generation 발급 · 스냅샷은 `tos_runtime.evidence` 로 **evidence 화**(레인 L 의 store 포트에 의존 — 인터페이스는 `EvidenceAppendPort` Protocol 로 주입, L 이 없을 때 테스트는 인메모리 더블).
3. `tos_runtime/time/generation.py` — `GenerationCounter`: 단조 증가 generation 발급(durable 은 순서 3 에서 RCL 로그와 결합 · 이 슬라이스에서는 «프로세스 수명 내 단조 + 기동 시 evidence 에 기록» 까지).
4. 설정 `tos/runtime/config/time.example.yaml`: `MAX_time_source_precision_ms`·`MAX_time_transport_and_queue_uncertainty_ms`·`MAX_time_conservative_freshness_age_ms` 등 VER-002 프로파일 키 **이름을 그대로** 쓰되 값은 `null`(named-TBD) — 값 부재 = 기동 거부.

**장애 계약**: ⑥ 클록 역행/왜곡 — 단조 소스 역행 관측 시 `HealthState` 를 DEGRADED/UNTRUSTED 로만 이동(TRUSTED 로 자동 복귀 없음) · ⑦ 소스 불가 — 스냅샷 생성 실패 = 마지막 스냅샷 만료 후 «신선도 없음» (커널 `freshness_verdict` 가 거부) · 재기동 ⑤ — 새 generation 은 이전 스냅샷을 되살리지 않음(`recovery_generation_revives_nothing`).

**테스트(hermetic · 가짜 단조 소스 주입)**: 역행 주입 → TRUSTED 불가 · 새 generation 후 옛 스냅샷 `snapshot_consumer_binding_ok` False · 설정 키 부재 → 기동 거부 · 스냅샷 digest 결속(`DigestBoundArtifact`) · 단일 참조 소스일 때 `independent_reference_count` 가 1 을 정직히 보고(2 를 요구하는 프로파일이면 DEGRADED).

## 2. 레인 L — `tos_runtime.evidence` (순서 2: durable Evidence Store · D3 전부)

**소비 대상(커널)**: `tos.evidence` 의 `Sha256HmacChainScheme`·`EvidenceAppendReceipt`·`ChainedEntry`·`verify_chain`·`scrub_secret_fields`·`retention_deletable`·`Tombstone`·`RetentionRecordClassRule`·`DurabilityClass`; 싱크 Protocol `tos.engine.sink.EvidenceSink`·`tos.egressgw.gateway.GatewayEvidenceSink`; `tos.workload.RuntimeIdentity`.

**산출물**
1. `tos_runtime/evidence/store.py` — `SqliteEvidenceStore`: 파일 1개 · `journal_mode=WAL` · `synchronous=FULL` · 테이블 `entries(seq PK, segment_id, kind, record_class, runtime_identity_json, payload_json, entry_digest, chain_digest, key_generation, appended_at_monotonic_ns)` · **UPDATE/DELETE 거부 트리거**(append-only 표현 불가능화) · `append(record) -> EvidenceAppendReceipt` 는 `BEGIN IMMEDIATE` 안에서 스크럽(D4 비밀 필드 목록 주입)→정본 직렬화→digest→체인 링크→INSERT→COMMIT 후에만 영수증 · 실패 시 예외(영수증 0) · `replay() -> Iterator[ChainedEntry]` + `verify(keys_by_generation)` 는 `verify_chain` 재사용 · 체인 불일치 = `EvidenceCorruption` 예외(비-live 고정은 소비자 소관 · store 는 보고만).
2. `tos_runtime/evidence/emergency.py` — `EmergencyAppendLog`: 별 파일 JSON Lines · 한 줄 write + `os.fsync` · sqlite 의존 0 · HALT/보호 조치 레코드 class 만 수신 · 두 경로 기록 헬퍼 `record_halt(...)` 는 **둘 다 성공해야 성공**(하나라도 실패 = 예외 · 성공 과대 보고 금지).
3. `tos_runtime/evidence/outbox.py` — 같은 DB 의 `outbox(seq, entry_seq, target, delivered_at)` 테이블 · `enqueue` 는 append 와 같은 트랜잭션 · `OutboxConsumer` Protocol + `drain(consumer)` at-least-once · 멱등 키 `(segment_id, seq)` · 실제 외부 싱크 구현 0.
4. `tos_runtime/evidence/backup.py` — `backup(store, dest_dir, generation) -> BackupManifest{file_digest, last_seq, chain_digest, key_generation}`(sqlite `Connection.backup`) · `restore(manifest_path) -> RestoredStore` 는 **항상 새 세대 번호 + `non_live=True` 플래그**를 반환하고 살아남은 브랜치 대조 결과를 `RestoreComparison` 레코드로 evidence 화(ADR-002-016 :449-459).
5. `tos_runtime/evidence/retention.py` — `RetentionPolicy` 로더(`tos/runtime/config/evidence_retention.example.yaml` · 클래스별 최소 보존 · 값 `null` named-TBD) · `evaluate(store, now, holds) -> tuple[RetentionVerdict, ...]` 는 커널 `retention_deletable` 로 판정만 · **삭제 잡 없음** · 툼스톤 INSERT 만(`Tombstone` 레코드 · dual_control_ref 필수).
6. 커널 싱크 어댑터 `tos_runtime/evidence/sinks.py` — `EngineEvidenceSinkAdapter(EvidenceSink)`·`GatewayEvidenceSinkAdapter(GatewayEvidenceSink)`: 커널 레코드를 store.append 로 넘기고, **`SEND_STARTED` kind 는 영수증을 받은 뒤에만 반환**(ADR-002-016 :19 — 현재 gateway 는 sink.record 반환값을 보지 않으므로 «record 가 반환되면 durable» 계약을 어댑터가 보장 · 실패는 예외 전파 = gateway 의 §4.6 크래시 경로).
7. 키: `Sha256HmacChainScheme` 의 키 바이트는 D4 custody 에서 오지만 custody 는 순서 4 소관 — 이 슬라이스는 `KeyProvider` Protocol 주입(테스트는 고정 바이트) · 회전 `rotate(new_generation, new_key)` 는 «회전 커밋 항목» 을 append 하고 그 seq 부터 새 세대 사용(겹침 0).

**장애 계약**: ④ durable commit 전/후 크래시 — `tests/tos_l3` 의 주입 하네스 방식(프로세스 종료 지점 주입)을 런타임 테스트에서 재사용해 «영수증 반환 후 재기동 시 항목 존재 · 영수증 전 크래시 시 항목 부재 또는 체인 정합» 실증 · ⑦ 저장소 불가/부분 커밋 — 파일 잠금/읽기전용/디스크 가득 모사 시 예외·영수증 0 · ⑤ replay 불일치 → `EvidenceCorruption` · ② 같은 seq 재삽입 거부(PK).

**테스트(hermetic · tmp_path sqlite)**: append→영수증→replay 일치 · UPDATE/DELETE 트리거 거부 · 크래시 주입 2지점 · 비상 경로 fsync 호출 실증(몽키패치 카운터) · 두 경로 중 하나 실패 시 실패 · outbox 같은 트랜잭션(append 실패 시 outbox 행 0) · backup→restore 새 세대·non_live · 회전 후 옛 세대 서명 무효/검증 유효 · 스크럽이 store 에 도달하기 전에 적용됨(평문 비밀 grep 0) · 보존 평가는 삭제하지 않음(행 수 불변).

## 3. 레인 간 계약

- K 는 L 의 `EvidenceAppendPort` Protocol(이름·시그니처는 **L 이 먼저 `tos_runtime/evidence/ports.py` 에 정의**, K 는 그 파일만 임포트)에 의존. 착수 순서: L 이 ports.py 를 먼저 쓰고(첫 30분) 그 뒤 K 가 임포트. K 의 테스트는 인메모리 더블.
- 둘 다 `tos_runtime.compose` 를 만들지 않는다(순서 3~6 뒤 composition root 한 자리에서).
- 순서 3(RCL 로그)과의 결합(generation 을 RCL 트랜잭션에 넣기)은 후속 슬라이스.

## 4. 종료 조건

- `tos/runtime/tests` green(hermetic 가드 위반 0) · 커널 `tos/tests` 불변 green · 방화벽/lint-imports/budget/Black/Ruff/mypy 0
- 장애 계약 ④⑤⑥⑦(+②) 각각에 red-선행 테스트 존재 · 독립 리뷰 approve
- 어떤 EV 행도 상태 변경 없음 · 실 브로커 transport 0 · 자격증명 파일 로드 코드 0(순서 4)

## 5. 실행 결과·독립 리뷰 처분 (2026-09-08)

- 착지: `ba7d438f`(레인 K `tos_runtime.time` 865줄·테스트 28 · 레인 L `tos_runtime.evidence` 1,489줄·테스트 51 · `tos/src/tos/py.typed` · CI `mypy (tos runtime)` 스텝) → 리뷰 **needs-attention**(HIGH-1 비상 로그 평문 · HIGH-2 같은 클록 2인스턴스 독립 계수+비교 없이 disagreement 0 · MEDIUM-3 rotate 가 스킴을 먼저 교체 · LOW-4/5/6) → 처분 `1872af9d` → **재심 approve**(6/6 재현 소멸 · 되돌림 뮤테이션 전부 사망 · runtime tests 108).
- 리뷰 판정 기록: LOW-5 처분(회복 시 세대 발급 + TRUSTED 진입 시 재발급)은 ADR-002-008 §16 항목 1 «새 generation» 과 커널 `transition_to_trusted_requires_new_generation` 이 별개 요구라 이중 계수가 아님 · `DEGRADED_HOLDOVER` 회복은 TRUSTED 진입 시만 발급(앵커 무효화가 없었으므로 정합) · `_ratchet_anchor` 는 fail-closed 방향 · hermetic 쓰기 가드는 C-level `sqlite3.connect` 를 못 보므로 그 절반은 관례(정직 한계 기록).
- 무결함 렌즈(1차): 크래시 주입 2지점 · append-only 트리거(독립 연결로 UPDATE/DELETE 시도) · WAL/FULL 연결마다 · 스크럽 직렬화 전 · outbox 같은 트랜잭션 · record_halt 두 경로 · fsync 1회 · backup/restore 새 세대 non_live · retention 삭제 0 · 커널 술어 8종 호출(자체 판정 0) · EvidenceAppendPort 계약 정확 일치 · 뮤테이션 4/6 사망(생존 2 는 benign).
