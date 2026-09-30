# 스키마 제네시스를 원자적으로 — #801 수정 계획

- 작성: 2026-09-30 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `341a4430`
- 요청: 운영자 2026-09-30 「#801 수정 계획 써줘」.
- 성격: 계획 + 구현(같은 PR). 운영자 처분 §6.1.
- ⚠ **순서 제약**: 진행 중인 PR #816(증거 증가 트랙 A)이 같은 모듈(`operations/schema_ledger.py` ·
  `schema_migrations.py` · `evidence/store.py`)을 고치고 있다. 구현은 **#816 머지 뒤** 그 main 위에서 시작한다(§5).

## 0. 요약 — 경합은 둘이다

같은 **빈** `data_dir` 로 두 런타임이 동시에 첫 부팅하면, 네 스토어(evidence · inbox · marketfeed · rcl) 각각에서:

| # | 경합 | 결과 | #801 에 적힘 |
|---|---|---|---|
| R-1 | A·B 둘 다 `file_is_fresh = True` 를 **트랜잭션 밖**에서 읽는다 → A 가 제네시스 도장을 찍는다 → B 가 낡은 `was_fresh=True` 로 다시 INSERT | `UNIQUE constraint failed: schema_ledger.version`(부팅 크래시) | 예 |
| R-2 | A 가 `CREATE TABLE` 을 실행한 뒤, 도장을 찍기 전에 B 가 연다 → B 는 `was_fresh = False`, `user_version = 0` 을 본다 | B 가 「BEHIND — `migrate` 를 돌려라」로 **부팅을 거짓 거부**(`SchemaVersionRefused`) | **아니오 — 이번 조사에서 발견** |

#801 이 권고한 수정(「`BEGIN IMMEDIATE` 안에서 `file_is_fresh`/`user_version` 재확인」)은 R-1 만 닫는다. R-2 에서 B 는
`was_fresh = False` 로 이미 비-제네시스 분기에 있고, 그 분기에는 트랜잭션이 없다.

**수정 — 제네시스 전체를 한 트랜잭션으로.** 「신선한가 확인 → 스토어 DDL → `schema_ledger` DDL → 도장」을
`BEGIN IMMEDIATE … COMMIT` 하나로 묶는다. 이 로직은 `operations/schema_ledger.py` 의 공유 헬퍼 하나로 모으고,
네 스토어가 그것을 부른다(DRY). 이제 두 번째 프로세스는 첫 번째의 COMMIT 을 기다린 뒤(sqlite busy 대기)
**완성된 파일**을 본다. 그래서 R-1(중복 INSERT)과 R-2(반쯤 만든 파일)가 둘 다 표현 불가능해진다.

## 1. 코드 (main `341a4430`)

| 무엇 | 위치 |
|---|---|
| `ensure_schema_current` — `was_fresh` 를 인자로 받아 제네시스일 때만 `BEGIN IMMEDIATE` · 비-제네시스는 트랜잭션 없이 버전 비교 | `tos/runtime/src/tos_runtime/operations/schema_ledger.py:134-196` |
| `file_is_fresh` — 「호출자의 `CREATE TABLE` 전에 불러야 한다」 | `schema_ledger.py:98-106` |
| 호출자 넷: `file_is_fresh` → 자기 DDL(autocommit) → `ensure_schema_current` | `evidence/store.py:419-431` · `engine/inbox.py:270-286` · `marketfeed/store.py:230-238` · `rcl/log.py:184-190`(→ `rcl/schema.py` `apply_schema_ledger`) |
| sqlite busy 대기: evidence·inbox·marketfeed 는 `sqlite3.connect` 기본값(5 s) · rcl 은 `sqlite_timeout_s` 주입 | `evidence/store.py` · `engine/inbox.py:265` · `marketfeed/store.py:225` · `rcl/log.py:179-181` |
| RCL `fcntl.flock` 은 「보조 — 정확성에 기대지 않는다」(D2.1) · 정확성은 writer epoch 펜싱 | `rcl/log.py:203-224` |
| 펜싱은 스토어를 **다 연 뒤** 시작된다 → 이 경합은 펜싱보다 **앞**이다 | `compose/_wiring.py:422` `acquire_epoch` |
| `apply_migrations` 는 「단독 오픈」을 문서로만 요구 | `operations/schema_migrations.py:485-492` |

## 2. 결정

### 2.1 공유 헬퍼

`schema_ledger.py` 에 `open_or_create_schema(conn, *, store_name, schema_version, create_ddl, shape_tables, monotonic_ns)` 를 둔다.

```text
BEGIN IMMEDIATE                      ← 쓰기 잠금: 다른 프로세스는 여기서 busy 대기
  fresh = file_is_fresh(conn)        ← 잠금 안에서 판단 (R-1 · R-2 의 뿌리를 제거)
  create_ddl(conn)                   ← 스토어 자신의 CREATE TABLE/TRIGGER (전부 IF NOT EXISTS)
  schema_ledger DDL + 트리거
  if fresh: user_version = schema_version · CREATED 행 INSERT (digest = shape_tables 모양)
COMMIT
if not fresh: 기존 버전 비교 (같음 → 통과 · 뒤/앞 → SchemaVersionRefused)  ← 기존 규칙 그대로
```

- sqlite 는 DDL 도 트랜잭션 안에서 원자적이다. 두 번째 프로세스는 `BEGIN IMMEDIATE` 에서 기다렸다가 완성된
  파일을 보고 `fresh = False`, `user_version = schema_version` → 통과한다.
- 예외 시 `ROLLBACK` — 반쯤 만든 테이블이 남지 않는다(지금은 DDL 이 autocommit 이라 남을 수 있다).
- `PRAGMA journal_mode=WAL` 은 트랜잭션 **밖**(연결 직후)에 그대로 둔다 — 트랜잭션 안에서는 바꿀 수 없다.
- `ensure_schema_current` 와 `file_is_fresh` 는 **하위 호환으로 남긴다**. 테스트와 `schema_migrations` 가 쓴다.
  네 스토어 생성자만 새 헬퍼로 옮긴다.

### 2.2 같은 버전 · 다른 모양

두 번째 프로세스가 **다른 코드**(같은 `schema_version`, 다른 DDL)라면: 잠금 안에서 `fresh = False`, 버전은 같아
통과한다. 그러나 모양이 다르다. 지금 코드도 이 경우를 검사하지 않는다(비-제네시스는 버전만 본다).
→ **이번 범위 밖**으로 두고 §5 에 적는다. 모양 digest 비교를 부팅 검사에 넣는 것은 별도 결정이다.

### 2.3 busy 대기 값

- 두 번째 프로세스의 대기는 첫 번째의 제네시스 트랜잭션 길이(수 ms)면 충분하다. 기본 5 s 로 넉넉하다.
- **새 설정 키를 만들지 않는다.** rcl 은 이미 주입값을 쓰고, 나머지 셋은 파이썬 기본값이다.
- 대기가 넘치면 `sqlite3.OperationalError: database is locked` 가 나고 부팅이 거부된다(fail-closed · 크래시가
  아니라 명시적 오류). 테스트로 고정한다.

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| #801 의 권고 그대로 — `BEGIN IMMEDIATE` 안에서 재확인만 | R-2(DDL 이 트랜잭션 밖에서 먼저 실행 → 반쯤 만든 파일 → 거짓 BEHIND 거부)를 닫지 못한다 |
| `INSERT OR IGNORE` | 진짜 버전 충돌까지 가린다(#801 본문도 같은 이유로 기각) |
| `data_dir` 단위 `fcntl` 잠금 | 비준된 D2.1 이 flock 을 「보조 — 정확성에 기대지 않는다」로 규정했다. 정확성을 잠금에 기대면 그 원칙을 뒤집는다. 두 런타임 동시 가동 자체를 막는 것은 writer epoch 펜싱의 몫이다 |
| 스토어마다 따로 고치기 | 같은 결함 네 벌 — DRY(CLAUDE.md). 공유 헬퍼 하나 |
| `apply_migrations`(운영자 CLI)에도 같은 처리 | 운영자 단독 오픈 전제가 문서화돼 있고 경로가 다르다 — §5 에 남긴다 |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | `open_or_create_schema` 헬퍼 + 단위 테스트 | fresh → 도장 1행 · 기존 같은 버전 → 통과 · 뒤/앞 → 거부 · DDL 중 예외 → ROLLBACK 뒤 **사용자 테이블 0**(반쯤 만든 파일 없음) |
| T-2 | 네 스토어 생성자를 헬퍼로 이전(evidence · inbox · marketfeed · rcl) | 네 스토어의 **모양 digest 가 이전과 바이트 동일**(같은 DDL · 같은 CREATED 행) · 기존 스위트 무변경 통과 |
| T-3 | **다중 프로세스 경합 테스트**(스토어별 · `multiprocessing` 로 N=8 프로세스가 같은 빈 파일을 동시에 연다 · 시작 장벽으로 동시성 강제) | 수정 전 코드에서 R-1(`IntegrityError`) 또는 R-2(`SchemaVersionRefused`)가 **재현되어 먼저 red** · 수정 후 N 개 모두 성공 · CREATED 행 정확히 1 |
| T-4 | busy 초과 시 명시적 거부 테스트(첫 프로세스가 잠금을 오래 쥐는 대역) | `OperationalError` 로 부팅 거부 · 파일 무손상 |
| T-5 | digest 재도출(마지막 커밋) · 계획 §7 착지 · INDEX · #801 링크 | 통상 게이트 + CI 와 같은 mypy(마지막 줄 `Success`) |

**뮤테이션**(red 확인):
- `file_is_fresh` 를 잠금 밖으로 되돌림 → T-3 red
- DDL 을 트랜잭션 밖으로 → T-3(R-2) red
- ROLLBACK 제거 → T-1 반쯤 만든 파일 red

## 5. 위험·범위 밖

- **#816 과 같은 파일을 만진다.** #816 은 `EVIDENCE_SCHEMA_VERSION` 1 → 2 와 인덱스를 `migrate` 경로로 넣는 중이다.
  #801 구현은 #816 머지 뒤 시작한다. 새 헬퍼의 `create_ddl` 에 #816 의 인덱스 DDL 이 들어가야 **새 파일도 v2 모양**이
  된다 — #816 이 제네시스 경로에 인덱스를 어떻게 넣었는지 확인하고 맞춘다.
- **다중 프로세스 테스트의 신뢰성**: 시작 장벽(`multiprocessing.Barrier`) + 반복 횟수로 경합을 강제한다. 수정 전
  코드에서 재현되지 않으면(경합 창이 너무 좁으면) DDL 과 도장 사이에 테스트 전용 지연 훅을 주입해 창을 벌린다 —
  운영 코드에 훅을 남기지 않는 형태로(생성자 주입 · 기본 no-op).
- **범위 밖**: 같은 버전·다른 모양(§2.2) · `apply_migrations` 동시 실행 · 두 런타임의 **동시 가동** 자체(펜싱의 몫).
- 런타임 소스 변경 → digest 재도출.

## 6. 운영자 확인

1. **원자적 제네시스(§2.1)** — #801 의 권고(재확인만)가 아니라 DDL 까지 한 트랜잭션으로. 동의 여부.
2. **R-2 를 같은 수정에 포함** — 동의 여부.
3. 구현은 **#816 머지 뒤** 이 브랜치에서 — 동의 여부.

### 6.1 운영자 처분 (2026-09-30)

1. **원자적 제네시스(§2.1)** — 동의.
2. **R-2 를 같은 수정에 포함** — 동의.
3. **구현은 #816 머지 뒤 이 브랜치(PR #817)에서** — 동의. 시작할 때 최신 main 을 병합하고, #816 의 인덱스 DDL 이
   제네시스 경로에 들어갔는지 먼저 확인한다(§5).

## 7. 착지 기록 (2026-09-30 · 브랜치 `fix/tos-schema-genesis-toctou` · PR #817)

운영자 처분 §6.1 3항대로 **#816 머지 뒤**에 시작했다: main `7d039339`(#816 포함)을 이 브랜치에
병합(`b88737ef`, 충돌은 `docs/plans/INDEX.md` 한 줄뿐 — 두 행을 날짜순으로 보존)한 뒤 그 위에서 구현했다.

### 7.1 무엇이 어디로 갔나

| 작업 | 착지 | 커밋 |
|---|---|---|
| T-1 | `operations/schema_ledger.py` — `open_or_create_schema` 신설: `BEGIN IMMEDIATE` 하나 안에서 「`file_is_fresh` → `create_ddl(conn, fresh)` → 대장 DDL·트리거 → (fresh 면) `user_version` 스탬프 + `CREATED` INSERT」 · COMMIT **뒤**에 기존 버전 비교 · 예외 시 `ROLLBACK` · BEHIND/AHEAD 거부를 `_refuse_version` 으로 두 진입점이 공유 · `ensure_schema_current`·`file_is_fresh` 는 하위호환으로 유지 | `c0673ea5` |
| T-2 | 네 스토어를 헬퍼로 이전 — `evidence/store.py`(`_create_evidence_schema`) · `engine/inbox.py`(`_create_inbox_schema`) · `marketfeed/store.py`(`_create_marketfeed_schema`) · `rcl/schema.py`(`_create_rcl_schema`, `apply_schema_ledger` 가 DDL 을 소유) · `rcl/log.py`(DDL 4줄·`file_is_fresh` 제거) | `0ba91e92` |
| T-3·T-4 | `tests/operations/test_schema_genesis_concurrency.py` 신설 — 스토어별 8프로세스 동시 첫 부팅 + busy 초과 거부 | `a7a72763` |
| T-5 | digest 재도출 · 이 절 · `docs/plans/INDEX.md` | 마지막 커밋 |

**#816 의 제네시스 전용 인덱스는 보존됐다.** `create_ddl` 은 **잠금 안에서 판정된** `fresh` 를 인자로
받으므로 `entries_kind_seq` 는 여전히 제네시스에서만 생성된다 — v1 파일은 인덱스를 만들지 않은 채 그대로
거부되고, 운영자가 롤백으로 드롭한 인덱스를 부팅이 다시 만들지도 않는다(#816 이 남긴 고정 테스트
`test_a_refused_v1_boot_does_not_build_the_index` 는 무변경으로 통과한다).

### 7.2 모양 불변 (T-2 종료조건)

두 방향으로 확인했다. 어느 쪽도 「같아 보인다」가 아니라 **main `7d039339` 에서 실측한 값과의 대조**다.

1. **커밋된 고정값** — `test_schema_ledger.py::_PRE_CHANGE_SHAPES`: 네 스토어 각각의 `sqlite_master`
   객체 전수(type·name), 그 객체들의 `sql` 텍스트를 접은 sha256, `CREATED` 행의 `version` ·
   `migration_digest` · `applied_by`, `PRAGMA user_version`. 전건 일치.
   (`applied_at_monotonic_ns` 는 제외 — 같은 코드를 두 번 돌려도 정당하게 달라지는 유일한 칸이다.)
2. **파일 바이트** — 주입 가능한 `monotonic_ns` 를 고정값으로 묶고 갓 만든 파일의 sha256 을 두 트리에서
   비교: evidence `e365d6a0…` · marketfeed `92b3e9f8…` · rcl `eb0fdb9e…` 가 **바이트 동일**
   (inbox 는 `time.monotonic_ns` 를 직접 읽어 주입점이 없으므로 크기만 대조 — 40960 동일).

### 7.3 T-3 실측 — 수정 전 red, 수정 후 green

**red 먼저.** 헬퍼를 쓰기 전에 T-3 를 먼저 써서 **수정 전 스토어 코드**(병합 직후 = main `7d039339`
의 네 생성자)에 걸었다:

| 테스트 | 수정 전 | 수정 후 |
|---|---|---|
| `test_the_genesis_transaction_is_atomic_under_concurrent_first_boot` (아크 도중 개명 — 리뷰 HIGH-1) | **4/4 파라미터 red** | 4/4 green |
| `test_a_store_created_by_a_race_is_immediately_reopenable` | **4/4 파라미터 red** | 4/4 green |
| `test_a_write_lock_held_past_the_busy_timeout_refuses_boot_explicitly` | pass — T-4 는 뮤테이션 검출기가 아니라 fail-closed 고정이다(§7.4 8항) | pass |
| 합계 | **8 failed, 1 passed** | **9 passed** (연속 3회) |

수정 전 관측된 실패 형태 전수: `IntegrityError: UNIQUE constraint failed: schema_ledger.version`
**24건(R-1)** · `SchemaVersionRefused: … user_version=0 is BEHIND` **4건(R-2)** ·
`OperationalError: database is locked` 4건. **R-2 가 실제로 재현된다** — 계획 §0 이 「#801 에 적히지
않았다」로 분류한 두 번째 경합이 가설이 아니었다는 뜻이다.

그 red 측정 뒤 테스트를 두 군데 고쳤다(rcl 자녀마다 **사설** evidence 파일 — 공유하면 evidence 파일에
별개 경합이 생겨 `OperationalError` 로 흐려진다 · 자녀 본문 전체를 `try` 안으로 — 보고 전에 죽으면
부모가 타임아웃까지 막힌다). **최종 테스트 파일로 같은 결함을 재현한 것은 §7.5 의 M1·M2** 이고, 거기서는
R-1 40건 · R-2 4건이다. 창을 벌리지 않은 상태의 실측(10라운드 × 8프로세스, 스토어별 실패 자녀 수):
evidence **7/80** · inbox **6/80** · marketfeed **21/80** · rcl **8/80** — 경합은 진짜지만 확률적이고,
8 % 확률로 재현되는 것은 테스트가 아니다. 그래서 창을 **테스트 쪽에서만** 벌린다(§7.4 2항).

창을 벌리지 않은 상태의 실측(10라운드 × 8프로세스, 스토어별 실패 자녀 수): evidence **7/80** ·
inbox **6/80** · marketfeed **21/80** · rcl **8/80**. 즉 경합은 진짜지만 확률적이고, 8 % 확률로
재현되는 것은 테스트가 아니다 — 그래서 창을 **테스트 쪽에서만** 벌린다(§7.4 2항).

### 7.4 계획에서 벗어난 것 (전건 사유 포함)

1. **`create_ddl` 은 `(conn, fresh)` 2인자 콜러블**이다. 계획 §2.1 의 서명에는 `create_ddl` 이 인자
   하나처럼 적혀 있지만, #816 의 `entries_kind_seq` 는 **제네시스에서만** 만들어야 하므로 스토어 DDL 이
   신선도 판정을 알아야 한다. 잠금 안에서 판정한 값을 그대로 넘긴다.
2. **창 확대 훅을 운영 코드에 넣지 않았다.** 계획 §5 는 「생성자 주입 · 기본 no-op」 훅을 허용했지만, 그러려면
   네 생성자에 테스트 전용 인자가 하나씩 늘어난다. 대신 **자녀 프로세스가 자기 `sqlite3.connect` 를
   패치**해 그 스토어의 첫 `CREATE TABLE` 직후 50 ms 잠들게 한다(`_DelayedConnection`). 운영 코드는
   한 줄도 모르고, 같은 훅이 수정 전/후 코드 양쪽에 동일하게 걸린다.
3. **T-3 은 파일을 `journal_mode=WAL` 로 미리 만든다.** 이미 저장소에 있는 관용구
   (`test_store_probe_isolation._precreate_wal_file`)이고 이유도 그 docstring 에 적혀 있다: 갓 생긴 파일의
   저널 모드를 WAL 로 바꾸는 데 필요한 잠금은 `PRAGMA journal_mode` 가 sqlite busy 타임아웃으로 **재시도하지
   않는다**. 그래서 동시 첫 연결은 스토어 코드가 한 줄도 돌기 전에 한쪽을 `OperationalError: database is
   locked` 로 잃을 수 있다(micro-probe 실측 **47/240**). 이 경합은 #801 범위 밖(계획 §2.1 이 pragma 를
   트랜잭션 밖에 둔다)이고 이 수정에 영향받지 않는다 — WAL 은 파일에 지속되므로 한 번 설정된 뒤의 같은
   pragma 는 잠금 없는 no-op 이다. 여기서 발화시키면 검증 대상만 흐려진다.
   ⚠ **그리고 이 경합은 여전히 열려 있다 — `#818`**(리뷰 HIGH-1, §7.9). 리뷰어 실측으로 갓 생긴 파일에서
   N=2 **22/80** · N=4 **57/160** · N=8 **90/320** 이 잃는다. 즉 이 스위트가 증명하는 것은 **제네시스
   트랜잭션**이고 「동시 첫 부팅이 된다」가 아니다 — 그래서 HIGH-1 처분으로 테스트 이름을
   `test_the_genesis_transaction_is_atomic_under_concurrent_first_boot` 로 좁히고, 모듈 독스트링 ·
   `_precreate_wal_file` · `schema_ledger` 모듈 독스트링 세 곳에 #818 을 적었다.
4. **기존 스위트가 「무변경 통과」하지 않았다 — 두 테스트를 고쳐야 했다.** 계획 T-2 의 종료조건은
   「기존 스위트 무변경 통과」였는데, `tests/compose/test_store_probe_isolation.py` 의
   `test_two_concurrent_store_constructions_on_a_fresh_file_lose_the_genesis_race` 는 **이 수정이 없애는
   결함을 고정**하고 있었다(두 party 가 한 창 안에 있고 패자가 `IntegrityError` 로 죽는다). 이제 그 결과는
   도달 불가이고, 제네시스 창 안의 2-party barrier 는 **두 party 가 닿을 수조차 없다**(두 번째는 쓰기 잠금
   대기 중이다). 삭제가 아니라 더 강한 성질로 재작성했다 —
   `test_a_second_store_construction_cannot_enter_the_first_ones_genesis_window`: 첫 party 가 창 안에
   멈춰 있는 동안 두 번째는 **자기 신선도 판정에 닿지 못하고**(호출 계수 1 유지), 풀어주면 둘 다 부팅하고
   `CREATED` 행은 하나다. 이 테스트는 뮤테이션 M1 에서 red 다.
   두 테스트의 `file_is_fresh` monkeypatch 대상도 `marketfeed.store` → `operations.schema_ledger` 로
   옮겼다. 호출이 헬퍼 안으로 들어갔으므로 예전 대상에 패치하면 **조용히 아무 일도 하지 않고 두 테스트가
   공허하게 통과**한다.
5. **이웃 테스트의 「뮤테이션에서 무엇이 깨지나」 주장은 다시 측정했다.** 「저장소를 만드는 예전 프로브를
   되살린다」 뮤테이션에서 assertion 2(`-wal` 바이트 변화)는 여전히 발화한다(실측). 그러나 assertion 3 의
   **메커니즘이 바뀌었다** — 뮤테이션된 프로브는 이제 제네시스를 훔치지 못하고 쓰기 잠금에 걸리므로, 예전의
   `IntegrityError: UNIQUE constraint failed: schema_ledger.version` 대신 핸드셰이크 타임아웃
   (`the probing thread never released the construction`)이 난다. 예전 문구를 남기지 않고 실측값으로 고쳤다.
   `test_run_e2e.read_only_latest_as_of` 의 docstring 도 같은 이유로 갱신했다 — 프로브가 읽기 전용이어야
   하는 이유는 이제 「제네시스 경합」이 아니라 「구성 중인 런타임이 쥔 쓰기 잠금」이다.
6. **T-3 은 `fork` 로 자녀를 만든다**(커널 import-closure 테스트의 `spawn` 과 다르다). 깨끗한 인터프리터가
   필요한 게 아니라 **별개 OS 프로세스**가 필요하고, `spawn` 은 스토어 하나당 8회 스위트 재import 를 물린다.
7. **T-4 는 `SqliteCommitLog` 로 한다.** 네 스토어 중 busy 타임아웃 주입점(`sqlite_timeout_s`)을 이미 가진
   것이 그것뿐이다(fault ③ 스위트가 쓴다). 계획의 「새 설정 키 없이 테스트에서 짧은 타임아웃 주입」 그대로다.
8. **T-4 는 수정 전에도 통과한다.** fail-closed 고정이지 뮤테이션 검출기가 아니다(계획 §2.3 「테스트로
   고정한다」). 수정 전 코드에서는 첫 `CREATE TABLE` 이 autocommit 으로 실패해 같은 `OperationalError` 가
   나므로 판별력이 없다 — 그렇게 기록한다.
9. **`no-any-return` 두 건을 명시 annotation 으로 없앴다**(`test_schema_ledger.py` ·
   `test_schema_genesis_concurrency.py`). 이 두 건은 `PYTHONPATH` 없이 돌린 mypy 에서만 나타난다 — 그 호출에서는
   `tos_runtime` 이 경로에 없어 모든 심볼이 `Any` 가 된다. **정정(세션 모델, 2026-09-30)**: 원 기록은 이것을
   「CI mypy」라고 적었으나 틀렸다. CI 는 `tos_runtime` 을 해석한다(#812 에서 CI 가 `TickScheduler` 의 실제
   타입으로 오류를 냈다). annotation 자체는 무해하므로 그대로 둔다.

### 7.5 뮤테이션 (전건 red 확인 후 복구 · `schema_ledger.py` 백업 대조로 복구 검증)

| # | 뮤테이션 | red |
|---|---|---|
| M1 | `file_is_fresh` 를 잠금 **밖**으로 (DDL·도장은 트랜잭션 안) | **9건** — T-3 8건 + `test_a_second_store_construction_cannot_enter_the_first_ones_genesis_window`(호출 계수가 `[True, True]` 로 관측됨) · 실패 형태 R-1 40 · R-2 4 |
| M2 | 신선 판단과 스토어 DDL 을 **둘 다** 트랜잭션 밖으로 (= #801 이전 형태, 도장만 트랜잭션 안 — #801 자신의 권고가 도달하는 지점) | **11건** — M1 의 9건 + T-1 ROLLBACK 2건 · 실패 형태 R-1 40 · R-2 4 |
| M3 | `except BaseException: ROLLBACK` 제거 | **1건** — `test_open_or_create_schema_rolls_a_failed_genesis_all_the_way_back`(같은 살아 있는 연결에 `widgets` 테이블이 남는다). 짝 테스트(별 연결로 디스크를 다시 읽는 쪽)는 green 이다 — sqlite 가 close 때 암묵 롤백하므로 **그 한 건만 판별력을 가진다**. 그 테스트 docstring 이 이미 그렇게 적고 있고, 이제 실측으로 확인됐다 |

계획 §4 의 뮤테이션 3종이 각각 red 이고, M2 가 **#801 의 원 권고만으로는 부족하다**는 것을 같은 관측으로
보여준다(R-2 4건). 이웃 테스트의 test-side 뮤테이션(예전 저장소-생성 프로브 복원)은 §7.4 5항.

### 7.6 게이트 / 테스트

| 항목 | 결과 |
|---|---|
| `tos_firewall_check.py` | PASS — no import-firewall violations |
| `lint-imports` | Contracts: 3 kept, 0 broken |
| `tos_contract_check.py` (+ `--self-test`) | PASS · 뮤테이션 145종 전건 판별 |
| `tos_completion_status.py --check` | GREEN (violations=0) |
| `tos_spec_status.py --check` | PASS (비차단 baseline-plan 경고는 기존) |
| `tos_evidence_citation_check.py` | PASS — 8 citation(s) in 3 README(s) resolve |
| `tos_named_tbd_guard.py` | PASS — 46 candidate file(s), 0 violations |
| `tos_size_budget.py --check` | PASS — 0 violations (38 registered exception(s)) |
| black · ruff (변경한 `*.py` 12개) | 12 files would be left unchanged · All checks passed |
| mypy `tos/runtime/tests` (저장소 루트 · `PYTHONPATH=tos/src:tos/runtime/src` · `--ignore-missing-imports --disable-error-code=no-untyped-def`) | `Success: no issues found in 237 source files` |
| mypy `tos/runtime/src` (같은 `PYTHONPATH` · `--ignore-missing-imports`) | `Success: no issues found in 189 source files` |
| mypy `tos/src` (`cd tos && mypy src`) | `Success: no issues found in 265 source files` |
| `pytest tos/runtime/tests` | **3215 collected · 전건 pass** (main 기준선 3189 → 신규 26건: T-1 6 · T-2 4 · T-3/T-4 9 · 리뷰 처분 7 — §7.9) |
| `pytest tests/tools -k tos` | 783 collected · 전건 pass |
| `pytest tests/unit/scripts/test_render_paper_config.py` | 42 collected · 전건 pass |

**정정(세션 모델, 2026-09-30)**: 원 기록의 mypy 두 줄(`Found 122 errors …` · `Found 27 errors …`)은
`PYTHONPATH` 없이 돌린 값이었다. 이 표의 세 줄은 CI 와 같은 해석 경로(`PYTHONPATH=tos/src:tos/runtime/src`)로
세션 모델이 다시 잰 값이다. main 과의 오류 수 비교는 판정 기준으로 쓰지 않는다 — #812 에서 그 방식이 CI 실패를
가렸다. 판정은 CI 호출의 마지막 줄 `Success` 다.

### 7.7 배포 영향

- **동작 변경은 부팅 경로 하나뿐**이고, 갓 만든 파일의 모양은 바이트 동일하다(§7.2). 마이그레이션도,
  순서 제약도 새로 생기지 않는다.
- ⚠ **「이미 배포된 `data_dir` 에 대한 영향은 0」은 처음 판이 틀렸다**(리뷰 MEDIUM-1, §7.9). 파일 내용은
  그대로지만 **부팅이 하는 잠금 행동**이 바뀌었다: 원래 판은 모든 부팅을 `BEGIN IMMEDIATE` 로 시작해,
  현재 버전의 기존 파일을 여는 부팅조차 **쓰기 잠금을 이겨야** 했다(수정 전에는 쓰기 잠금이 전혀 필요
  없었다). 살아 있는 런타임의 증거 append · 운영자 CLI(`rearm`/`ack-alert`/`rotate-key`) · 긴
  `apply_migrations` 인덱스 빌드 중 아무거나와 경합했고, `SqliteCommitLog(sqlite_timeout_s=0)` 은 즉시
  실패했다. 처분으로 **정상 상태 부팅은 잠금 없는 판독 둘**(`user_version` 일치 + `schema_ledger` 존재)로
  결정해 트랜잭션에 아예 들어가지 않는다. 그래서 **지금은** 정상 상태 부팅의 잠금 행동이 수정 전과 같다.
  잠금을 잡는 부팅은 **실제로 스키마를 써야 하는 부팅**(제네시스 · 버전 불일치)뿐이다.
- #816 이 세운 전제(증거 스키마 v2 — 구 코드 정지 → `migrate` → 신 코드, 런북 §4-A)는 **그대로**다.
  이 PR 은 그 전제를 바꾸지 않는다.
- `expected_code_digest` 갱신은 필수다. 어긋나면 Stage A probe 가 **부팅을 거부**한다 — 이 브랜치에서
  실수로 스위트 도중에 런타임 소스를 고쳐 실측했다: `tests/recovery/test_drill.py` 14건이
  `ReleaseAdmissionRefused: release admission denied at the pre-I/O STAGE A probe` 로 red 였다.
  값은 `release.yaml` 과 `test_deploy_approved_values.py::_VALUE_PINS` **두 곳**을 함께 갱신했고,
  `expected_dependency_set_digest` 는 건드리지 않았다.
- 새 설정 키 0 · 승인된 `time.yaml` 값 무변경 · Phase-0 완료 계약 본문 바이트 동일
  (`git diff 7d039339 -- docs/plans/2026-08-12-...-contract-design.md` 가 비어 있다).

### 7.8 비차단 관찰 — 재현되지 않은 실패 1건

이 브랜치의 **첫** 전체 스위트 실행에서 `tests/operations/test_backup_archive.py::
test_a_corrupted_archive_is_refused` 가 한 번 red 였다. 재현되지 않았고, 원인을 이 수정으로 돌릴 근거도
없다:

- 그 실행은 이미 오염돼 있었다 — 아직 고치지 않은 probe-isolation 테스트 2건이 함께 red 였고, 실행 중에
  테스트 파일을 편집했다.
- 같은 트리의 **깨끗한** 전체 스위트는 전건 pass(§7.6) · `tests/operations` 단독 실행 pass · 그 테스트
  단독 20회 pass.
- main `7d039339` 트리의 전체 스위트도 전건 pass.
- 그 테스트가 의존하는 「xz 스트림 중앙 1바이트 반전이 읽기를 깨뜨린다」를 **main 트리에서** 실제 durable
  set 40회로 확인했다 — 40/40 「could not be read back」로 거부. 즉 그 테스트가 내용 변동에 흔들린다는
  증거는 없다.
- 이 수정은 그 테스트가 압축하는 파일의 **바이트를 바꾸지 않는다**(§7.2).

기록만 남긴다. 재발하면 이 항을 근거로 추적할 것.

### 7.9 리뷰 처분 (2026-09-30 · needs-attention 4건 → 전건 대응 · 잠정)

심판 레인은 **같은 모델 계열(Sonnet)의 Claude-side 패스**다 — 다른 모델 계열의 독립 심판이 아니므로
이 처분은 **잠정**이다(CLAUDE.md 하네스 규율: 되돌리기 어려운 경로만 Codex 로 가고, 이 디프는 그 범주가
아니다). 저자와 심판이 분리된 것은 맞다.

| # | 지적 | 처분 |
|---|---|---|
| HIGH-1 | **주장 과대.** 갓 생긴 파일의 동시 첫 부팅은 여전히 `PRAGMA journal_mode=WAL` 에서 실패한다(busy handler 없음) — 실측 N=2 **22/80** · N=4 **57/160** · N=8 **90/320**. 그런데 테스트 이름이 `..._admits_every_process` 였다 | **수용.** ① 테스트 개명 → `test_the_genesis_transaction_is_atomic_under_concurrent_first_boot`(이름이 고정하는 것을 그대로 말한다: WAL 로 미리 만든 파일에서 제네시스 트랜잭션이 원자적·비교차라는 것) ② `schema_ledger` 모듈 독스트링에 「무엇이 닫혔고 무엇이 아닌가」 한 단락 신설 — 제네시스 트랜잭션 경합은 닫혔고 **`journal_mode` 출생 경합은 닫히지 않았다 · #818** ③ #818 을 `_precreate_wal_file` docstring · T-3 모듈 독스트링 · 헬퍼 docstring · 이 계획 §7.4 3항에 적었다. 범위는 #818(별도) |
| MEDIUM-1 | **모든 부팅이 배타 쓰기 잠금을 잡는다.** 수정 전에는 현재 버전의 기존 파일을 여는 부팅에 쓰기 잠금이 필요 없었다. `BEGIN IMMEDIATE` 를 무조건 걸면 살아 있는 writer(런타임 append · 운영자 CLI · 긴 `apply_migrations`)와 경합하고 `sqlite_timeout_s=0` 은 즉시 실패한다 | **수용.** `open_or_create_schema` 에 **정상 상태 fast path**: 먼저 잠금 없이 `PRAGMA user_version` 을 읽고, `schema_version` 과 같고 `schema_ledger` 가 존재하면 트랜잭션을 건너뛰어 기존 non-fresh 경로(DDL 0)를 그대로 탄다. 안전 방향이 성립한다 — 도장과 테이블이 **같은 트랜잭션에서** 커밋되므로 `user_version == schema_version` 관측은 제네시스(또는 `apply_migrations`)가 끝났다는 뜻이다. 그 밖의 모든 상태(버전 0 · 뒤/앞 · 대장 부재)는 `BEGIN IMMEDIATE` 로 떨어지므로 R-1·R-2 는 닫힌 채다. 동시 **첫** 부팅은 누군가 도장을 커밋하기 전까지 `user_version` 이 0 이라 fast path 에 절대 들어가지 못한다 |
| LOW-1 | 예외 처리의 `ROLLBACK` 이 스스로 던질 수 있다(`cannot rollback - no transaction is active`) → 원래 예외가 가려진다 | **수용.** `try: ROLLBACK except sqlite3.OperationalError: pass` 로 감싸고 원래 예외를 re-raise 한다 |
| LOW-2 | `isolation_level is None` 전제가 문서에만 있다 | **수용.** 헬퍼 진입에서 명시 `ValueError`(assert 아님 — `-O` 가 벗긴다). sqlite3 의 암묵 트랜잭션 모드에서는 `BEGIN IMMEDIATE` 가 제네시스 도중에 터져 원자성 논증이 무효가 된다 |

**red-before / green-after (처분 테스트 4건, 수정 전 헬퍼로 실측):**

| 테스트 | 수정 전(literal) | 수정 후 |
|---|---|---|
| `test_an_already_current_file_boots_while_another_writer_holds_the_lock` | `sqlite3.OperationalError: database is locked` | pass |
| `test_a_real_store_boots_beside_a_held_write_lock`(실 `SqliteCommitLog` · `sqlite_timeout_s=0`) | `sqlite3.OperationalError: database is locked` | pass |
| `test_a_create_ddl_that_ends_the_transaction_surfaces_its_own_exception` | `sqlite3.OperationalError: cannot rollback - no transaction is active`(원래 `RuntimeError` 가 가려졌다) | pass — `RuntimeError: the real failure…` 가 그대로 나온다 |
| `test_a_connection_not_in_autocommit_mode_is_refused_with_a_clear_error` | `DID NOT RAISE <class 'ValueError'>` | pass |

fast path 가 **거짓 통과 경로가 되지 않는다**는 것도 따로 고정했다(이 셋은 수정 전에도 green — 새 경로의
가드이지 구 코드의 회귀 검출기가 아니다, 그렇게 적는다):
`test_the_fast_path_still_refuses_a_behind_or_ahead_version_under_a_held_lock` ·
`test_a_matching_version_without_a_schema_ledger_does_not_take_the_fast_path` ·
`test_a_v1_evidence_file_is_still_refused_and_never_fast_pathed`(실 evidence v1 파일 — `user_version` 1 ≠ 2
라 fast path 에 들어갈 수 없고, #816 대로 인덱스도 만들지 않은 채 거부된다).

**부수 효과 — 크기 예산.** 위 세 처분으로 `open_or_create_schema` 가 141줄이 되어 100줄 함수 예산을
넘겼다(`tools/tos_size_budget.py` 가 red: `[unregistered] … open_or_create_schema: 141 lines exceeds
100`). **예외 등재가 아니라 분해했다** — 트랜잭션 본문을 `_run_genesis_transaction(conn, …) ->
(was_fresh, on_disk_version)` 으로 빼고, fast path 근거 문단은 모듈 독스트링으로 옮겼다(순수
decomposition: 같은 문장 · 같은 순서 · 같은 한 트랜잭션 · 버전 비교는 COMMIT 뒤 호출자에 그대로 남는다).
분해 뒤 `tos size budget PASS: 0 violations`.

**부수 정정**: `a2b54e6b` 이 바로잡은 mypy 기록에 따라, 첫 판에서 `no-any-return` 회피용으로 달았던 주석
두 개의 전제가 거짓이 됐다(「저장소 루트에서 `tos_runtime` 이 mypy 경로에 없다」 — `PYTHONPATH` 를 주면
있다). `test_schema_ledger.py` 쪽은 annotation 자체가 불필요해 **되돌렸고**,
`test_schema_genesis_concurrency.py` 쪽은 실제로 필요하지만 이유가 다르므로(`**kwargs: Any` 래퍼)
**이유를 실측에 맞게 고쳤다**. 거짓 전제 주석을 남기지 않는다.
