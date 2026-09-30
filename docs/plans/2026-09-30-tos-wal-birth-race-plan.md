# 새 스토어 파일의 WAL 전환 경합 — #818 수정 계획

- 작성: 2026-09-30 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 기준 main `7d039339`
- 요청: 운영자 2026-09-30 「#818 수정 계획 써줘」.
- 성격: 계획 + 구현(같은 PR). 운영자 처분 §6.1.
- ⚠ **순서 제약**: PR #817(#801 원자적 제네시스)이 같은 생성자 줄들(`PRAGMA journal_mode=WAL` 바로 뒤의
  `open_or_create_schema`)을 고친다. 구현은 **#817 머지 뒤** 그 main 위에서 시작한다.

## 0. 요약

- **결함**: 두 프로세스가 **완전히 새** 스토어 파일을 동시에 열면, `PRAGMA journal_mode=WAL` 이
  `OperationalError: database is locked` 로 실패한다.
  - 원인: 저널 모드를 롤백 저널 → WAL 로 바꾸려면 배타 잠금이 필요한데, 이 PRAGMA 는 sqlite 의 busy
    handler(연결의 timeout)를 **거치지 않는다**. 진 쪽은 기다리지 않고 바로 실패한다.
  - #817 은 그 뒤의 제네시스 경합(R-1 · R-2)을 닫았다. 그러나 「같은 빈 `data_dir` 동시 첫 부팅이 죽는다」는
    사용자 증상은 이 한 줄 앞에서 남는다.
- **수정 — 기다린 뒤 한 번 더**: PRAGMA 가 잠금으로 실패하면 `BEGIN IMMEDIATE; ROLLBACK` 으로 **sqlite 자신의
  busy handler 로 기다린 뒤** PRAGMA 를 다시 부른다.
  - 전환을 끝낸 쪽이 잠금을 놓으면, 기다린 쪽의 두 번째 PRAGMA 는 이미 WAL 인 파일에 대한 무동작이다.
  - 새 대기 상수가 없다. 대기 상한은 연결에 이미 설정된 timeout 이다(`PRAGMA busy_timeout`, 기본 5000 ms ·
    rcl 은 주입값).
  - 반환값이 `wal` 이 아니면 **부팅 거부** — 지금은 반환값을 확인하지 않는다.

## 1. 실측 (2026-09-30 · 스크래치 · 호스트 로컬)

`multiprocessing`(fork) N 개가 `Barrier` 로 동시에 **새 파일**에 `sqlite3.connect(…, isolation_level=None)`
(기본 timeout) → `PRAGMA journal_mode=WAL` 을 부른다.

| 방식 | N=2 | N=8 |
|---|---|---|
| 지금 코드(재시도 없음) | **17 / 80 실패**(21 %) | **22 / 320 실패** |
| 잠금 실패 시 `BEGIN IMMEDIATE; ROLLBACK` 로 기다린 뒤 한 번 더 | **0 / 120** | **0 / 480** |
| (참고) 5 ms 간격 재시도 · 상한 = `busy_timeout` | 0 / 80 | 0 / 320 |

- 실패는 전부 `database is locked` 다.
- 성공한 모든 연결의 반환값은 `wal` 이었다.
- PR #817 리뷰의 실측(실제 `SqliteEvidenceStore` · N=2 22/80 · N=4 57/160 · N=8 90/320)과 같은 결함이다.
  그쪽 비율이 더 높은 것은 PRAGMA 뒤의 부팅 단계가 창을 넓히기 때문이다.

## 2. 결정

### 2.1 공유 헬퍼

`tos_runtime/operations/schema_ledger.py`(네 스토어가 이미 여는 모듈)에 `enable_wal_journal(conn)` 을 둔다.

```text
try:    mode = PRAGMA journal_mode=WAL
except OperationalError("database is locked"):
        BEGIN IMMEDIATE ; ROLLBACK        ← sqlite busy handler 로 대기 (연결의 timeout 까지)
        mode = PRAGMA journal_mode=WAL    ← 두 번째도 실패하면 그대로 올린다 (부팅 거부)
if mode != "wal": raise (부팅 거부 — 조용히 롤백 저널로 돌지 않는다)
```

- **재시도는 딱 한 번**이다. 무한 루프도 새 횟수 상수도 없다. 두 번째 실패는 「연결의 timeout 동안 다른 쪽이
  잠금을 놓지 않았다」는 뜻이므로 fail-closed 가 맞다.
- `database is locked` 가 아닌 `OperationalError` 는 재시도하지 않고 그대로 올린다.
- `BEGIN IMMEDIATE` 는 롤백 저널 파일에서는 RESERVED 잠금이다. 곧바로 `ROLLBACK` 하므로 쓰기는 0 이다.
- 네 스토어(evidence · inbox · marketfeed · rcl)의 `self._conn.execute("PRAGMA journal_mode=WAL")` 한 줄을 이
  헬퍼 호출로 바꾼다(DRY).

### 2.2 커널 `CompositeStateStore` — 범위 밖

- `tos/src/tos/staterestore/store.py:124` 에도 같은 줄이 있다. 하지만 이것은 **커널**이라 런타임 헬퍼를
  import 할 수 없다(방화벽).
- 부팅 때가 아니라 복구 기록자가 **필요할 때** 연다(`recovery/composite_state_writer.py:110`). 한 프로세스
  안에서만 열린다.
- 커널 쪽 사본을 만들면 DRY 위반 + 커널 변경이다. 노출이 다르므로 별도 결정으로 남긴다(§5).

## 3. 기각한 대안

| 대안 | 기각 이유 |
|---|---|
| 짧은 간격 sleep 재시도(상한 = `busy_timeout`) | 동작은 같지만(§1) 새 간격 상수가 생긴다. sqlite 의 busy handler 를 쓰면 대기 정책이 연결 하나에 모인다 |
| compose 가 모든 스토어 파일을 먼저 만들고 WAL 로 전환 | 스토어를 여는 경로가 compose 하나가 아니다 — 운영자 CLI(`migrate`·`backup-set`·`rearm` 등), 테스트, 프로브. 결함을 스토어 생성자에서 닫아야 모든 경로가 덮인다 |
| `data_dir` 잠금 | #817 계획 §3 과 같은 이유 — D2.1 이 flock 을 정확성에 기대지 않는다 |
| 반환값 확인 없이 재시도만 | 전환이 조용히 실패해 롤백 저널로 돌면 `synchronous=FULL`·WAL 을 전제한 내구성 논증이 깨진다 |

## 4. 작업

| # | 내용 | 종료 조건 |
|---|---|---|
| T-1 | `enable_wal_journal(conn)` + 단위 테스트 | 잠금 실패 → 대기 → 성공 · 두 번째 실패는 그대로 올림 · `database is locked` 가 아닌 오류는 재시도 없음 · 반환값 `wal` 아님 → 거부 |
| T-2 | 네 스토어 생성자를 헬퍼로 | 기존 스위트 무변경 통과 · 새 파일 모양·`user_version`·CREATED 행 바이트 동일(#817 의 `_PRE_CHANGE_SHAPES` 핀 재사용) |
| T-3 | **#817 의 동시성 테스트에서 `_precreate_wal_file` 을 뺀 변종**(스토어별 · N=8 · 시작 장벽) | 수정 전 코드에서 `database is locked` 가 **재현되어 먼저 red** · 수정 후 N 개 모두 성공 · CREATED 행 1 |
| T-4 | 타임아웃 초과 시 명시적 거부(한쪽이 배타 잠금을 timeout 넘게 쥔다 · 테스트에서 짧은 timeout 주입) | `OperationalError` 로 부팅 거부 · 파일 무손상 |
| T-5 | digest 재도출(마지막 커밋) · 계획 §7 착지 · INDEX · #818 링크 · #817 의 「#818 로 추적」 문구 정리 | 통상 게이트 + mypy(저장소 루트 · `PYTHONPATH=tos/src:tos/runtime/src` · 마지막 줄 `Success`) |

**뮤테이션**(red 확인):
- 재시도 제거 → T-3 red
- 반환값 확인 제거 → T-1 red
- `database is locked` 가 아닌 오류도 재시도 → T-1 red

## 5. 위험·범위 밖

- **#817 머지 뒤 시작**(같은 줄). #817 의 `_precreate_wal_file` 은 T-3 에서 뺀 변종과 함께, 원래 목적(제네시스
  트랜잭션만 격리해 보기)을 그대로 두고 문구만 갱신한다.
- **커널 `CompositeStateStore`**(§2.2)는 이번 범위 밖이다. 두 런타임이 같은 `data_dir` 에서 복구 기록을 동시에
  처음 쓰는 경우에만 드러난다. 필요하면 별도 이슈로 연다.
- 대기 상한은 연결의 timeout 이다. evidence·inbox·marketfeed 는 파이썬 기본 5 s, rcl 은 주입값이다. 새 설정 키는
  만들지 않는다.
- 런타임 소스 변경 → digest 재도출.

## 6. 운영자 확인

1. **「기다린 뒤 한 번 더」(§2.1)** — sleep 재시도나 compose 선생성이 아니라 sqlite busy handler 로 대기. 동의 여부.
2. **반환값이 `wal` 이 아니면 부팅 거부** — 동의 여부.
3. **커널 `CompositeStateStore` 는 범위 밖**(§2.2) — 동의 여부.
4. 구현은 **#817 머지 뒤** 이 브랜치에서 — 동의 여부.

### 6.1 운영자 처분 (2026-09-30)

1. **「기다린 뒤 한 번 더」(§2.1)** — 동의.
2. **반환값이 `wal` 이 아니면 부팅 거부** — 동의.
3. **커널 `CompositeStateStore` 는 범위 밖** — 동의.
4. **구현은 #817 머지 뒤 이 브랜치(PR #820)에서** — 동의.
   - 세션 모델 메모: 순서는 #817 → #821(`verify_archive` 결정성, 런타임 소스) → 이 PR 이다. 세 PR 이 모두
     `expected_code_digest` 를 바꾸므로 **직렬로** 머지한다.

## 7. 착지 기록 (2026-09-30 · 브랜치 `fix/tos-wal-birth-race` · PR #820)

운영자 처분 §6.1 4항대로 **#817 머지 뒤**에 시작했다: main(#817 포함)을 이 브랜치에 병합
(`87fe788c`)한 뒤 그 위에서 구현했다.

### 7.1 무엇이 어디로 갔나

| 작업 | 착지 | 커밋 |
|---|---|---|
| T-1 | `operations/schema_ledger.py` — `enable_wal_journal(conn)` 신설(+ 한 번만 쓰는 `_switch_journal_to_wal` · 새 예외 `JournalModeRefused`). `SQLITE_BUSY` 면 `BEGIN IMMEDIATE; ROLLBACK` 으로 대기 후 PRAGMA **한 번만** 재시도 · 반환값이 `wal` 아니면 거부 · `SQLITE_BUSY` 가 아닌 `OperationalError` 는 첫 시도에서 그대로 올림 | `c29b0fb8` |
| T-2 | 네 스토어의 맨 PRAGMA 한 줄을 헬퍼 호출로 — `evidence/store.py` · `engine/inbox.py` · `marketfeed/store.py` · `rcl/log.py` | `b6e0bcdd` |
| T-3·T-4 | `tests/operations/test_wal_journal.py` 신설(헬퍼 네 모서리 · 결정적) + `test_schema_genesis_concurrency.py` 에 **미리 만들지 않은** 파일 변종(스토어별 8프로세스 × 5라운드) · #818 을 「열려 있음」으로 적던 독스트링 셋 정정 | `43407863` |
| T-5 (부수) | 수정이 무효로 만든 문구 둘 — `enable_wal_journal` 독스트링의 실측 출처 귀속(계획 §1 값과 이번에 잰 값과 #801 리뷰 값이 뒤섞여 있었다) · `tests/compose/test_store_probe_isolation.py` 의 「진 쪽이 `database is locked` 로 죽는다」(이제 기다렸다 재시도한다 — 미리 만드는 이유는 그 **대기**가 두 party 사이에 끼어들기 때문으로 바뀐다) | `98066a6d` |
| T-5 | digest 재도출 · 이 절 · `docs/plans/INDEX.md` | 마지막 커밋들 |

### 7.2 계획에서 벗어난 것 (전건 사유 포함)

1. **잠금 판별을 메시지가 아니라 `sqlite_errorname == "SQLITE_BUSY"` 로 한다.** 계획 §2.1 은
   `OperationalError("database is locked")` 라고 적었다. 실측: 맨 PRAGMA 로 N=8 × 40라운드를
   돌린 320건 중 실패 73건이 **전부** `database is locked` / `SQLITE_BUSY`(code 5)였다. 문자열
   부분일치보다 기계 판독 식별자가 좁고 안전하다 — 다만 그 대가로, **손으로 만든**
   `sqlite3.OperationalError("database is locked")` 에는 `sqlite_errorname` 이 아예 없다(실측).
   그래서 단위 테스트는 오류를 **지어내지 않고** 진짜 sqlite 연산에서 잡아온 인스턴스를 재생한다
   (배타 잠금을 쥔 두 번째 연결 · 없는 테이블 SELECT). 판별자가 실제 운영 형태를 못 잡으면 §7.4 의
   다중 프로세스 테스트가 red 가 된다 — 판별자 자체를 고정하는 테스트가 따로 있는 셈이다.
2. **T-3 을 별도 모듈로 만들지 않고 기존 `test_schema_genesis_concurrency.py` 에 넣었다.**
   그 모듈의 독스트링 셋이 #818 을 「아직 열려 있음」으로 적고 있었고(`_precreate_wal_file` 은
   「이 헬퍼가 그것을 가린다」까지 적었다), 그 문구를 고치는 것 자체가 T-5 의 항목이었다. 같은
   자리에서 「무엇이 닫혔고 무엇을 여전히 가리는지」를 말하는 편이 갈라 놓는 것보다 정확하다.
   헬퍼 자체의 네 모서리는 결정적이고 경합이 없으므로 새 모듈 `test_wal_journal.py` 로 분리했다.
3. **rcl 쪽 대상 파일은 `rcl/schema.py` 가 아니라 `rcl/log.py`** 다(계획 §2.1 은 「네 스토어」라고만
   적었다). RCL 의 PRAGMA 는 연결을 여는 `SqliteCommitLog.__init__` 에 있다.
4. **커널 `CompositeStateStore` 는 손대지 않았다**(§2.2 · 운영자 처분 §6.1 3항).
   `tos/src/tos/staterestore/store.py:124` 의 맨 PRAGMA 는 그대로다.

### 7.3 실측 — 수정 전

전부 이 브랜치에서 `enable_wal_journal` 의 본문만 **수정 전 코드**(맨
`conn.execute("PRAGMA journal_mode=WAL")`)로 되돌려 잰 값이다.

| 대상 | 조건 | 실패 |
|---|---|---|
| 맨 PRAGMA(스크래치) | N=8 · 40라운드 · 갓 만든 파일 | **73 / 320** (전부 `SQLITE_BUSY`) |
| 실제 스토어 생성자 | N=8 · 10라운드 · 스토어별 | evidence **15/80** · inbox **4/80** · marketfeed **5/80** · rcl **30/80** |
| `test_concurrent_first_boot_on_a_brand_new_file_admits_every_process` | 연속 3회 실행 | **3회 모두 4/4 파라미터 red** (전부 `OperationalError: database is locked`) |

### 7.4 뮤테이션 (계획 §4 「red 확인」 전건)

| 뮤테이션 | red 가 된 테스트 |
|---|---|
| M1 재시도 제거(= 수정 전 코드 전체) | `test_a_lock_lost_once_is_waited_out_and_the_switch_retried` · `test_a_lock_still_held_when_the_retry_runs_refuses_the_boot` · `test_a_journal_mode_that_is_not_wal_refuses_the_boot` + §7.3 의 다중 프로세스 테스트 |
| M2 반환값 확인 제거 | `test_a_journal_mode_that_is_not_wal_refuses_the_boot` (단독) |
| M3 `SQLITE_BUSY` 가 아닌 오류도 재시도 | `test_an_operational_error_that_is_not_a_lock_is_not_retried` (단독) |

M3 가 red 가 되는 근거는 **문장 로그**다 — 올라오는 예외는 두 코드에서 같으므로 「예외가 무엇이냐」로는
구분되지 않는다. 그래서 테스트는 PRAGMA 시도 횟수와 `BEGIN IMMEDIATE` 유무를 본다.

### 7.5 게이트

모두 워크트리 루트에서, `PYTHONPATH=tos/src:tos/runtime/src` · 저장소 루트 `.venv`.

| 게이트 | 결과 |
|---|---|
| `pytest tos/runtime/tests -p no:cacheprovider` | **3226 passed** (8:24). ⚠ digest 재도출 **전**에는 stale `expected_code_digest` 때문에 compose·recovery **184건**이 `ReleaseAdmissionRefused` 로 red 였다 — 런타임 소스를 바꾸면 이 스위트는 digest 를 다시 찍기 전까지 green 이 될 수 없다 |
| `pytest tos/tests -p no:cacheprovider` (커널 · CI `tos-firewall` 스텝) | **9601 passed** (2:02, 커널 무변경 확인) |
| `mypy tos/runtime/src --ignore-missing-imports` | `Success: no issues found in 189 source files` |
| `mypy tos/runtime/tests --ignore-missing-imports --disable-error-code=no-untyped-def` | `Success: no issues found in 238 source files` |
| `cd tos && mypy src --ignore-missing-imports` | `Success: no issues found in 265 source files` |
| `mypy tos/tests --ignore-missing-imports --disable-error-code=no-untyped-def` | `Success: no issues found in 585 source files` |
| `ruff check` (변경 `*.py` 9개) | `All checks passed!` |
| `black --check tos/src tos/tests tos/runtime/src tos/runtime/tests tools/tos_*.py tests/tools/test_tos_*.py tests/tools/test_u17_verify.py` (CI 스텝 그대로) | `1299 files would be left unchanged` |
| `python tools/tos_firewall_check.py` | `PASS — no import-firewall violations` |
| `lint-imports` | `Contracts: 3 kept, 0 broken` |
| `python tools/tos_size_budget.py --check` | `PASS: 0 violations` |
| `bash tools/tos_entry_harness.sh` | `d0a_entry_state=ENTRY_OK` |

### 7.6 digest

`expected_code_digest`: **d75a3616 → e4cf4908**
(`e4cf49080a416cdfe90094e2b9514fb0558704461f70a25771c3e8a8f2619613`).
`print-digests` 와 `observe_source_tree_digest()` 두 경로가 일치했다.
`expected_dependency_set_digest` 는 무변경(`20559763…`). 갱신은 두 곳 —
`config/tos_runtime/paper/release.yaml`(19차 재측정 주석 포함)과
`tos/runtime/tests/compose/test_deploy_approved_values.py::_VALUE_PINS`.

⚠ **#821(`fix/tos-verify-archive-determinism`)이 이 PR 보다 먼저 머지된다.** 그쪽도 런타임 소스를
바꾸므로, 머지 뒤 이 브랜치는 `git merge origin/main` 후 **digest 를 한 번 더 재도출**해야 한다
(계획 §6.1 4항 메모의 직렬 머지 규율).

### 7.7 남긴 것

- 커널 `CompositeStateStore`(§2.2)는 여전히 맨 PRAGMA 다. 두 런타임이 같은 `data_dir` 에서 복구
  기록을 **동시에 처음** 쓸 때만 드러나며, 방화벽 때문에 런타임 헬퍼를 쓸 수 없다. 별도 이슈 대상.
- `test_schema_genesis_concurrency._precreate_wal_file` 은 그대로 남는다. 이제 「열린 결함을
  가린다」가 아니라 「두 경합을 서로 다른 픽스처로 갈라 둔다」가 이유다 — 실패가 어느 쪽인지 이름으로
  말해 준다.
