# 스키마 제네시스를 원자적으로 — #801 수정 계획

- 작성: 2026-09-30 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `341a4430`
- 요청: 운영자 2026-09-30 「#801 수정 계획 써줘」.
- 성격: 계획. 운영자 처분(§6) 뒤 같은 브랜치에서 구현한다.
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
