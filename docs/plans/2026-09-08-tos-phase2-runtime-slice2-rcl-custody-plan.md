# TOS Phase 2 런타임 슬라이스 #2 — 선형화 RCL 커밋 로그 (순서 3) · 파일 custody/키 제공자 (D4 · 순서 4 전제)

- **상위**: 설계 #40(운영자 비준 2026-09-08) D2 · D4 · §5 순서 3 · 슬라이스 #1 `docs/plans/2026-09-08-tos-phase2-runtime-slice1-time-evidence-plan.md`(착지 `ba7d438f`·`1872af9d`)
- **저작**: 세션 모델 단독 · **권한 부여 없음** · EV 행 상태 변경 없음
- **위치**: `tos/runtime/src/tos_runtime/{rcl,custody}/` · 테스트 `tos/runtime/tests/{rcl,custody}/` · §0 공통 규율은 슬라이스 #1 과 동일(커널 편집 0 목표 · 장애 계약 먼저 · 임계값/경로 주입 · hermetic)

## 1. 레인 M — `tos_runtime.rcl.SqliteCommitLog` (설계 #40 D2.1 전부)

**소비 대상(커널)**: `tos.rcl.commitlog` — `CommitLog` Protocol · `CommitEntry`/`AppendReceipt`/`AppendRefusal`/`LogView`/`CapacityReservationTransition` · `AppendRefusalReason` · 술어 `stale_writer_epoch`/`duplicate_command`/`replay_reproduces_state`/`release_admissible`/`reservation_transition_structurally_legal` · `tos.rcl.predicates.transition_allowed`(+`TransitionCause`) · `tos.rcl.CapacityState` · `tos.workload.RuntimeIdentity` · 슬라이스 #1 의 `EvidenceAppendPort`(모든 커밋 전이는 evidence 를 남긴다 — ADR-002-012 :489).

**산출물**
1. `tos_runtime/rcl/log.py` — `SqliteCommitLog(CommitLog)`: 파일 1개(evidence 와 **다른 파일**) · `WAL`·`synchronous=FULL` · 테이블 `epochs(epoch PK, issued_at_monotonic_ns, runtime_identity_json)` · `entries(seq PK, writer_epoch, command_id UNIQUE, command_digest, kind, payload_digest, payload_json)` · `reservations(reservation_id PK, state, last_seq)` · **모든 변이는 `BEGIN IMMEDIATE` 안에서**: (a) 현재 epoch 읽기 (b) `stale_writer_epoch(current, attempted)` → 거부 (c) `expected_seq == MAX(seq)` 아니면 `SEQ_MISMATCH` (d) `duplicate_command(existing_digest_for_id, attempted)` → 거부/INTEGRITY (e) INSERT (f) evidence append(포트) — **evidence 영수증 실패 = ROLLBACK + 거부**(전이는 증거 없이 존재하지 않는다) (g) COMMIT 후에만 `AppendReceipt(durable=True)`. 캐시 없음.
2. **Writer fencing** `acquire_epoch(identity) -> WriterEpoch`: `epochs` 에 새 행을 원자 삽입(MAX+1) · 이후 모든 쓰기는 «내 epoch == MAX(epochs)» 를 같은 트랜잭션에서 검사 · OS 파일 잠금은 보조(`fcntl.flock` 은 stdlib — 사용 시 «보조» 라고 명시하고 없어도 정확성에 의존하지 않음).
3. **선형화 읽기** `read_linearizable(*, writer_epoch)`: 같은 트랜잭션에서 epoch 확인 + `seq` 스냅샷 → `LogView` · stale epoch 는 읽기도 거부(`AppendRefusal` 반환 또는 전용 예외 — Protocol 시그니처를 따른다).
4. **예약 생명주기** `apply_reservation_transition(transition: CapacityReservationTransition, cause: TransitionCause, finality_witness: bool | None)`: `reservation_transition_structurally_legal` **과** `transition_allowed(cause)` 둘 다 통과해야 하며(커널 docstring 의무) · RELEASED/POSITION_CONSUMED 목적지는 `release_admissible(…, finality_witness)` 추가 통과 · 통과한 전이만 `entries`+`reservations` 갱신(같은 트랜잭션).
5. `replay()` 전량 재생 + `replay_reproduces_state(replayed_digest, held_digest)` — 재생으로 재구성한 `reservations` 상태 digest 가 저장된 것과 다르면 `CommitLogCorruption` 예외(비-live 고정은 소비자 소관).
6. 컴팩션 없음(항목 삭제 0 · UPDATE/DELETE 거부 트리거 — evidence store 와 같은 규율) · `reservations` 만 UPDATE 허용(그것이 투영).
7. `tos_runtime/rcl/projection.py` — engine 이 읽는 `ReservationProjectionReader`: `SqliteCommitLog` 의 읽기 투영(Protocol 은 커널 `engine/state.py` 의 `ProvisionalReservationLedger` 가 요구하는 최소 인터페이스를 **읽어서** 맞춘다 — 커널 편집 없이 어댑터 가능하면 그렇게, 불가능하면 필요한 커널 포트를 보고만).

**장애 계약**: ① stale epoch writer — 두 로그 핸들이 같은 파일을 열고 둘째가 epoch 를 획득하면 첫째의 쓰기는 `STALE_EPOCH` 거부 + evidence ② 중복 command / 같은 ID 다른 바이트 — `DUPLICATE_COMMAND_ID` / `COMMAND_BYTES_MISMATCH`(+INTEGRITY evidence) ③ 파일 접근 불가 — 모든 append/read 거부(`STORE_UNAVAILABLE`) ④ 크래시 주입 2지점(commit 전 · commit 후 영수증 전 — 슬라이스 #1 의 `crash_hook` 패턴) ⑤ 재기동 replay 불일치 → `CommitLogCorruption` ⑥ 로그는 클록을 쓰지 않는다(`issued_at_monotonic_ns` 는 기록용 · 순서는 seq 만 — 테스트: 단조 소스 역행 주입해도 seq 순서 불변) ⑦ 부분 커밋(sqlite 실패 모사) → 거부 · 영수증 0.

## 2. 레인 N — `tos_runtime.custody` (설계 #40 D4 · 순서 4 전제 · order 스코프는 **미구현**)

**산출물**
1. `tos_runtime/custody/ports.py` — `CredentialCustody` Protocol(`load(scope) -> CredentialHandle`) · `KeyProvider` Protocol(슬라이스 #1 store 가 요구하는 것을 **읽어서** 그 시그니처에 맞춘다).
2. `tos_runtime/custody/file_custody.py` — `FileCustody(root_dir, *, environment_label, expected_owner_uid)`: 스코프 파일 `read.principal`·`evidence.key`·`replay.params` 만(**`order.*` 스코프는 열거하지 않으며 요청 시 `CustodyScopeNotProvisioned` — Phase 4 소관·선물 REAL 은 영구 부재**) · 로드 전 검사: 파일 모드 `0600` 정확·소유자 uid 일치·매니페스트 `custody.manifest.yaml` 의 `environment_label` 이 기동 라벨과 `environment_label_consistent`(커널 술어) — 하나라도 실패 = 거부 · 로드 시 evidence 에 **principal id 와 파일 digest 만**(비밀 0 · `scrub_secret_fields` 로 이중 방어) · `CredentialHandle` 은 컨텍스트 매니저로 사용 후 `bytearray` 0 채움.
3. `tos_runtime/custody/key_provider.py` — `FileKeyProvider(KeyProvider)`: `evidence.key` 를 세대별 파일(`evidence.key.<generation>`)로 · 회전은 새 세대 파일 존재 + 슬라이스 #1 `rotate()` 호출 순서(파일 먼저, 로그 커밋 뒤) · 옛 세대 키는 검증용으로 읽기만.
4. 매니페스트 예시 `tos/runtime/config/custody.manifest.example.yaml`(`environment_label` · 스코프 목록 · 각 파일의 기대 digest 는 `null` named-TBD 허용 — null 이면 digest 검사만 생략하고 evidence 에 «digest 미고정» 기록).

**장애 계약**: 모드 0644 → 거부 · 소유자 불일치 → 거부 · 라벨 불일치 → 기동 거부 · `order` 스코프 요청 → `CustodyScopeNotProvisioned` · 부재 파일 → 거부 · evidence 레코드에 비밀 바이트 부재(raw grep).

**테스트 환경 주의(hermetic)**: `os.chmod`·`os.stat` 는 tmp_path 안에서만 · uid 는 `os.getuid()` 주입 가능하게 · macOS/Linux 공통 동작만 사용.

## 3. 레인 간·후속 계약

- M 과 N 은 파일 교집합 0. M 은 슬라이스 #1 `EvidenceAppendPort` 만, N 은 슬라이스 #1 `store.KeyProvider`(있으면) 시그니처만 소비.
- 순서 3 의 «generation 을 RCL 트랜잭션에 결합»(슬라이스 #1 K 가 이연): M 이 `acquire_epoch` 와 함께 `runtime_generation` 을 `epochs` 행에 기록하되 **두 epoch 를 동일시하지 않는다**(설계 #40 v1.1 ②) — `GenerationCounter` 의 durable 시드는 이 행에서 읽는다(`tos_runtime.time.generation` 에 `seed_from(log)` 헬퍼 — K 의 파일을 M 이 최소 편집; 충돌 방지 위해 M 만 편집).
- `tos_runtime.compose` 는 아직 만들지 않는다(순서 4~6 뒤).

## 4. 종료 조건

- 두 패키지 테스트 green · 커널 `tos/tests` 불변 · mypy runtime 0 · 방화벽/lint-imports/budget/Black/Ruff 0
- 장애 계약 ①~⑦(M) · custody 6종(N) red-선행 테스트 · 독립 리뷰 approve
- 실 브로커 transport 0 · `order` 자격증명 로드 경로 0 · EV 상태 변경 0
