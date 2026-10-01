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
  - 새 대기 상수가 없다. 대기의 단위는 연결에 이미 설정된 timeout 이다(`PRAGMA busy_timeout`, 기본 5000 ms ·
    rcl 은 주입값). ⚠ 상한은 그 **3배**다 — §5 (리뷰 F4).
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

### 2.2 커널 `CompositeStateStore` — 이 PR(#818) 범위 밖 · **#823 에서 닫힘**

- `tos/src/tos/staterestore/store.py:124` 에도 같은 줄이 있다. 하지만 이것은 **커널**이라 런타임 헬퍼를
  import 할 수 없다(방화벽).
- 부팅 때가 아니라 복구 기록자가 **필요할 때** 연다(`recovery/composite_state_writer.py:110`).
- 커널 쪽 사본을 만들면 DRY 위반 + 커널 변경이다. 노출이 다르므로 별도 결정으로 남긴다(§5).
- ⚠ **정정(리뷰 F7, 2026-09-30)**: 이 절의 초판은 「한 프로세스 안에서만 열린다」고 적었는데 **틀렸다**.
  compose 가 같은 공유 `data_dir` 아래로 이 스토어를 배선하고
  (`compose/_engine_wiring.py:267-269`, `data_dir / COMPOSITE_STATE_STORE_FILE_NAME`), 기록자는 **쓸 때마다
  새 연결을 열고 닫는다**(`recovery/composite_state_writer.py:110` —
  `with CompositeStateStore(self._store_path) as store:`). 두 런타임이 같은 빈 `data_dir` 로 부팅해
  **첫 composite-state 기록에 동시에 도달**하면 같은 경합이 난다. 범위 밖이라는 판단(처분 §6.1 3항)은
  유지하되, 근거는 「한 프로세스」가 아니라 「방화벽 + 노출 시점이 다름」이다. 추적: **issue #823**.
- ⚠ **후속 정정(#823 착지, 2026-09-30)**: 셋째 줄의 「사본 = DRY 위반」은 **결론이 아니라 비용**이었다.
  #823 은 사본을 만들되(`tos/src/tos/staterestore/_wal.py` — stdlib `sqlite3` 만, 방화벽 통과) 그 비용을
  **드리프트 핀**으로 갚는다: `tests/tools/test_tos_wal_mechanism_drift.py` 가 두 모듈을 텍스트로 읽어
  메커니즘 일곱 가지가 같은지 대조한다. 노출 경로도 이 절이 적은 그대로 실측됐다 — 실제 커널 생성자로
  N=8 × 40라운드에서 **손실 96/320 · clean 라운드 6/40(q=0.150)**. 착지 기록은 §8.

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
  처음 쓰는 경우에 드러난다 — **issue #823 으로 열었다**(리뷰 F7).
- 대기의 단위는 연결에 이미 설정된 timeout 이고 새 설정 키는 만들지 않는다(evidence·inbox·marketfeed 는 파이썬
  기본 5 s, rcl 은 주입값). ⚠ **정정(리뷰 F4)**: 그 timeout **하나**가 상한은 아니다. 첫 PRAGMA 자체가 기다릴
  수 있고(SHARED/EXCLUSIVE 획득은 busy handler 를 탄다 — 건너뛰는 것은 RESERVED 승급뿐), 그 뒤
  `BEGIN IMMEDIATE` 가 기다리고, 재시도 PRAGMA 가 또 기다린다. 거부까지 최악 **약 3배**(기본값이면 ~15 s)다.
  부팅 데드라인은 5 s 가 아니라 이 값에 맞춰 잡을 것 — 스토어 넷을 순차로 열면 **~60 s** 다.
  그 침묵을 깨기 위해 재시도 경로에 로그 한 줄을 넣었다(라운드-2 F6, §7.10) — 설정 노브는 없다.
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
| T-5 | digest 재도출 · 이 절 · `docs/plans/INDEX.md` | `99c63ea5` · `968a4885` |
| 리뷰 처분 | F2 판별자 수정(+F3·F4 독스트링) · F1·F5·F6 테스트 · F7 issue #823 · 계획 §7.8-7.9 · digest 재도출 | §7.8 표 |

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
| `pytest tos/runtime/tests -p no:cacheprovider` | 최초 **3226**(8:24) · 리뷰 처분 뒤 **3228**(4:23) · 라운드-2 뒤 **3232**(4:26) · main 머지 뒤 **3245**(4:41, #822 테스트 포함) · 라운드-3 뒤 **3246 passed**(4:12). ⚠ digest 재도출 **전**에는 stale `expected_code_digest` 때문에 compose·recovery **184건**이 `ReleaseAdmissionRefused` 로 red 였다 — 런타임 소스를 바꾸면 이 스위트는 digest 를 다시 찍기 전까지 green 이 될 수 없다 |
| `pytest tos/tests -p no:cacheprovider` (커널 · CI `tos-firewall` 스텝) | **9601 passed** (1:46, 커널 무변경 — 라운드마다 재실행) |
| `mypy tos/runtime/src --ignore-missing-imports` | `Success: no issues found in 189 source files` |
| `mypy tos/runtime/tests --ignore-missing-imports --disable-error-code=no-untyped-def` | `Success: no issues found in 238 source files` |
| `cd tos && mypy src --ignore-missing-imports` | `Success: no issues found in 265 source files` |
| `mypy tos/tests --ignore-missing-imports --disable-error-code=no-untyped-def` | `Success: no issues found in 585 source files` |
| `ruff check tos/runtime/src tos/runtime/tests` | `All checks passed!` |
| `black --check tos/src tos/tests tos/runtime/src tos/runtime/tests tools/tos_*.py tests/tools/test_tos_*.py tests/tools/test_u17_verify.py` (CI 스텝 그대로) | `1299 files would be left unchanged` |
| `python tools/tos_firewall_check.py` | `PASS — no import-firewall violations` |
| `lint-imports` | `Contracts: 3 kept, 0 broken` |
| `python tools/tos_size_budget.py --check` | `PASS: 0 violations` |
| `bash tools/tos_entry_harness.sh` | `d0a_entry_state=ENTRY_OK` |

### 7.6 digest

`expected_code_digest`: **d75a3616 → e4cf4908 → 569aac29 → f2ab3d49 → 2e30d5a8 → 9595ef63**
(`9595ef63fa82fd76657fbf979865bdc6d8e7aca7a8edaeec6eedd4e6731032cb`).

다섯 번 도출했다. 릴리스 파일의 회차 번호는 두 계열이 머지에서 합류하며 다시 매겨졌다 —
main 쪽 #821/#822 가 19~21, 이 PR 이 22~26이다.

| 회차 | 무엇이 바뀌어서 | 커밋 |
|---|---|---|
| 22 | 최초 구현(#818) | `968a4885` |
| 23 | 리뷰 처분 §7.8 — F2 판별자 + F3·F4 독스트링 | `3be56a86` |
| 24 | 라운드-2 처분 §7.10 — F3 생성자 가드 · F2 구조 · F6 로그 · 예산 분해 | `8c828161` |
| 25 | **origin/main a342236a 머지** — 소스 수정 0, 두 계열이 한 트리에서 처음 만남 | `5f568656` |
| 26 | 라운드-3 처분 §7.12 — F2 restore 가드 · F3 공용 컨텍스트 매니저 · F5 로그 · F6 | 마지막 커밋 |

매번 `print-digests` 와 `observe_source_tree_digest()` 두 경로가 일치했다.
`expected_dependency_set_digest` 는 무변경(`20559763…`). 갱신은 항상 두 곳 —
`config/tos_runtime/paper/release.yaml`(회차별 재측정 주석 포함)과
`tos/runtime/tests/compose/test_deploy_approved_values.py::_VALUE_PINS`.

**25차가 이 PR 의 F1(라운드-2)을 닫았다.** #822 가 먼저 머지된 뒤 `git merge origin/main` 으로
합류한 트리에서 다시 찍었다 — 두 브랜치의 마지막 값 중 **어느 것도** 그 트리에 맞지 않았다.
⚠ **CI 는 이 종류의 stale 을 못 잡는다**: `tests/compose/conftest.py` 의 `EXPECTED_CODE_DIGEST` 는
살아 있는 트리에서 다시 계산하고 `_VALUE_PINS` 는 커밋된 두 문자열끼리만 대조하므로, 둘이 함께
stale 이면 CI 는 green 이고 **부팅만** `ReleaseAdmissionRefused` 로 떨어진다(#814 전례).
직렬 머지에서 나중에 들어가는 PR 이 병합 트리 위에서 다시 찍는 것이 유일한 방어다.

### 7.7 남긴 것

- 커널 `CompositeStateStore`(§2.2)는 여전히 맨 PRAGMA 다. 방화벽 때문에 런타임 헬퍼를 쓸 수 없고,
  노출 시점도 다르다(부팅이 아니라 첫 복구 기록). **issue #823 으로 열었다** — 재현 경로와 제안 셋,
  수용 기준이 거기 있다. → **해소됨**: #823 이 별도 PR 로 닫았다(§8).
- `test_schema_genesis_concurrency._precreate_wal_file` 은 그대로 남는다. 이제 「열린 결함을
  가린다」가 아니라 「두 경합을 서로 다른 픽스처로 갈라 둔다」가 이유다 — 실패가 어느 쪽인지 이름으로
  말해 준다.

### 7.8 리뷰 처분 (독립 리뷰 high, 2026-09-30 · 7건)

| # | 지적 | 처분 |
|---|---|---|
| F2 | 잠금 판별이 `sqlite_errorname == "SQLITE_BUSY"` 정확일치라 **확장 코드**(`SQLITE_BUSY_RECOVERY`/`_SNAPSHOT`/`_TIMEOUT`)가 전부 「재시도 안 함」 가지로 샌다 | **수정.** `_is_lock_contest()` 신설 — `(errorcode & 0xFF) == sqlite3.SQLITE_BUSY`. 실측 확인: 정체 스냅샷 쓰기가 `SQLITE_BUSY_SNAPSHOT`·517·메시지 `database is locked` 를 낸다(하위 바이트 5). 특히 `SQLITE_BUSY_RECOVERY` 는 **재시도가 존재하는 바로 그 경우**(늦은 opener 가 승자의 WAL recovery 를 만남)라 실제 결함이다 |
| F1 | 다중 프로세스 테스트의 red 보장이 과대 — `p<1e-20` 은 **맨 PRAGMA 비율**이고 실제 구동하는 것은 생성자 비율(inbox 4/80) → 5라운드면 옛 코드가 13 % 확률로 green | **수정.** 라운드 5 → **20**. 근거를 「가장 낮게 측정된 생성자 비율(5 %)」로 바꿔 상수 주석에 산술까지 적었다: `0.95**160 = 0.03 %`. 실측 재확인 §7.9 |
| F3 | 「재시도는 이미 WAL 인 파일에 대한 무동작」은 **무조건 참이 아니다** — RESERVED 를 쥐고 있던 쪽이 전환자가 아니었다면 재시도가 진짜 전환이고, 그 RESERVED 승급도 busy handler 를 건너뛴다 | **수정(문서).** 독스트링에 조건을 명시하고, 그 형태가 드문 이유를 「불가능해서」가 아니라 「이 패키지의 스토어 파일은 전부 생성자에서 WAL 로 태어나서」로 고쳤다 |
| F4 | 「대기 상한 = 연결 timeout」이 과소 — 첫 PRAGMA + `BEGIN IMMEDIATE` + 재시도 PRAGMA 로 **약 3배**(기본값 ~15 s) | **수정(문서).** 독스트링·계획 §0·§5 전부 정정. 운영자가 부팅 데드라인을 잡을 때 읽는 숫자라 명시적으로 「5 s 가 아니라 이 값」이라고 적었다 |
| F5 | 「no WAL sidecars」를 독스트링이 약속하는데 본문은 확인하지 않는다 | **수정.** 거부 뒤 `-wal`·`-shm` 부재를 실제로 assert |
| F6 | 새 테스트가 3-튜플 `_STORES` 로 파라미터화하면서 `pause_after_sql` 를 쓰지 않는 죽은 인자 | **수정.** `_BIRTH_RACE_STORES` 2-튜플로 분리 |
| F7 | 커널 `CompositeStateStore` 후속 이슈가 안 열렸고, §2.2 의 「한 프로세스 안에서만 열린다」가 부정확 | **수정.** **issue #823** 개설(재현 경로·제안 3안·수용 기준). §2.2 의 서술은 정정했고, 범위 밖 판단 자체는 처분 §6.1 3항대로 유지 |

기각 0건.

### 7.9 리뷰 처분 실측

**F2 — 확장 코드가 실제로 새어 나갔다.** 파이썬은 확장 결과 코드/이름을 올린다:

```text
정체 스냅샷 쓰기 → sqlite_errorname='SQLITE_BUSY_SNAPSHOT' · sqlite_errorcode=517
                   메시지='database is locked'             · 517 & 0xFF = 5
```

새 테스트 `test_an_extended_busy_code_is_still_a_lock_contest` 는 수정 전 판별자에서 **red** 다
(잡아 둔 실제 오류가 생성자를 그대로 빠져나온다). 반대 방향 `SQLITE_LOCKED`(primary 6)은
`test_a_locked_table_is_not_treated_as_a_lock_contest` 로 고정했다 — 「메시지에 locked 가 있으면
재시도」로 과잉 수정되지 않게 한다.

**F1 — 라운드 재산정.** 수정 전 생성자 손실률(10라운드 × 8)과 그에 따른 「깨진 코드가 green 으로
나올 확률」:

| 스토어 | 손실률 | 5라운드(40 opener) | 20라운드(160 opener) |
|---|---|---|---|
| evidence | 15/80 = 18.75 % | 0.025 % | < 1e-6 % |
| **inbox** | **4/80 = 5.00 %** | **12.85 %** | **0.027 %** |
| marketfeed | 5/80 = 6.25 % | 7.57 % | 0.0033 % |
| rcl | 30/80 = 37.5 % | < 1e-6 % | < 1e-6 % |

가장 낮은 inbox 기준 5라운드는 **여덟 번에 한 번꼴로 green** 이었다 — 회귀 테스트가 아니다.
20라운드로 올린 뒤 재확인: 헬퍼를 맨 PRAGMA 로 되돌린 상태에서 **연속 3회 모두 4/4 파라미터 red**,
수정 후 4/4 green. 모듈 벽시계 16.4 s(네 파라미터 합 ~10 s).

**교훈(기록용).** 「p < 1e-20」은 계산은 맞았고 **어느 비율에 대입했는지가 틀렸다** — 맨 PRAGMA 로 잰
값을 실제로 구동하는 생성자 경로의 보장으로 썼다. 확률 경계를 적는 가드는 **그 숫자가 어느 실측에서
왔는지**를 같은 줄에 적어야 한다. [[guards-that-admit-what-they-name]] 계열의 같은 실패 형태다.

### 7.10 라운드-2 리뷰 처분 (독립 리뷰 high, 2026-09-30 · 6건)

| # | 지적 | 처분 |
|---|---|---|
| F1 | `expected_code_digest` 는 이 브랜치 트리에만 유효 — #822 가 먼저 머지되면 나중에 들어가는 쪽이 stale digest 를 싣는다. **CI 는 못 잡는다**(`tests/compose/conftest.py` 의 `EXPECTED_CODE_DIGEST = observe_source_tree_digest()` 가 살아 있는 트리에서 다시 계산하고, `_VALUE_PINS` 는 커밋된 두 문자열끼리만 비교한다 — 실측 확인) | **연기(해소 예정).** 알고 있는 사항이고 §7.6 · INDEX · PR 본문에 이미 적혀 있다. **#822 머지 뒤 `git merge origin/main` + 마지막 재도출**로 닫는다. 지금 할 수 있는 것이 없다 — 병합 트리가 존재하지 않는다 |
| F2 | 대기·재시도가 `except` **안**에서 돌아, 두 번째 실패가 처리 완료된 첫 `SQLITE_BUSY` 를 `__context__` 로 달고 「During handling of the above exception」 로 연쇄 출력된다 | **수정.** `except` 는 분류만 하고 플래그를 세운다. 대기·재시도는 블록 **밖**(`_wait_out_the_lock_and_retry`). 거부 테스트가 `__context__ is None`·`__cause__ is None` 을 단언하고, 옛 구조에서 red |
| F3 | 네 생성자가 `self._conn` 을 열고 바로 실패 가능 코드를 부르는데 try/close 가 없다 — 거부된 부팅이 열린 연결(과 -wal·-shm)을 남긴다. refcount 로도 안 닫힌다(예외 traceback 이 프레임을 잡고 있다) | **수정.** 네 생성자 모두 「WAL 전환 ~ 생성 끝」을 `try/except BaseException: self._conn.close(); raise` 로 감쌌다. 스토어별 파라미터 테스트가 거부 뒤 연결이 닫혔는지 단언(traceback 으로 그 연결 객체에 도달 — `/proc` 미사용, 플랫폼 무관). close 를 빼면 4/4 red |
| F4 | 독스트링이 `SQLITE_LOCKED` 테스트 객체를 「잡아온 진짜 오류」라고 하는데 실제로는 **조작**이다 | **수정(정직한 쪽).** 「이것 하나는 조작이다」를 두 독스트링에 명시하고, 여기서만 타당한 이유(**음성** 방향 단언 — 조작된 객체가 「재시도 안 함」을 통과시킬 수는 없다)를 함께 적었다 |
| F5 | 20라운드 근거가 4/80 **점추정**이고 라운드 내 opener 실패가 독립이 아니다 — 신뢰구간 하단(~1.4 %)이면 깨진 코드가 ~10 % 확률로 green | **수정(근거 교체).** 모델링 대신 **라운드 단위 clean 비율을 직접 실측**했다(40라운드×8, §7.11). 최악 rcl q=0.600 → 20라운드 3.7e-5, 95 % Wilson **상한** q=0.737 로도 2.2e-3 < 1 %. 라운드 수 변경 불필요 → 벽시계 비용 0 |
| F6 | 스토어당 최악 ~3배 timeout, 넷이면 ~60 s 를 **아무 기록 없이** 블록한다 — 시작 예산이 짧은 supervisor 는 fail-closed 거부가 출력되기 전에 프로세스를 죽인다 | **수정.** 재시도 경로에서 `logging.WARNING` 한 줄(파일명 + 「대기 상한은 이 연결의 busy timeout」). ⚠ **`tos_runtime` 최초의 logging 사용** — 기존 채널이 CLI 의 `print(stderr)` 뿐이라 라이브러리 모듈이 쓸 것이 없었고, `logging.lastResort` 가 핸들러 없이도 stderr 로 내보내므로 **설정 키 0** 으로 운영자에게 닿는다. 설정 노브는 만들지 않았다 |

기각 0건. 연기 1건(F1).

**부수(리뷰의 findings cap 밖 메모, 실재 확인함).** `tools/tos_evidence_run.py` 가
`tos/src/tos/staterestore/store.py` 를 **AST 로 파싱해** `execute(...)` 인자의 리터럴
`PRAGMA journal_mode=WAL`·`synchronous=FULL` 을 요구한다(설계 §6.2 게이트 3). 따라서 **#823 에서
커널 스토어에 같은 헬퍼 리팩터를 적용하면 그 게이트가 조용히 red 가 된다** — 이슈에 코멘트로 적었다.

### 7.11 라운드 단위 clean 비율 실측 (F5 근거)

수정 전 트리(맨 PRAGMA), 스토어별 **40라운드 × 8프로세스**, 「손실 자녀 0인 라운드」 수:

| 스토어 | 손실 자녀 | clean 라운드 | q | 95 % Wilson 상한 | 1 % 미만에 필요한 라운드(q / 상한) | 20라운드 green 확률(상한 기준) |
|---|---|---|---|---|---|---|
| evidence | 98/320 | 13/40 | 0.325 | 0.480 | 4.1 / 6.3 | 4.2e-7 |
| inbox | 54/320 | 15/40 | 0.375 | 0.530 | 4.7 / 7.2 | 3.0e-6 |
| marketfeed | 49/320 | 14/40 | 0.350 | 0.505 | 4.4 / 6.7 | 1.2e-6 |
| **rcl** | 47/320 | **24/40** | **0.600** | **0.737** | **9.0 / 15.1** | **2.2e-3** |

이것이 F1·F5 가 두 번 놓친 **올바른 양**이다. 라운드 내 opener 실패는 독립이 아니고(누군가는 전환에
이긴다 — 8 중 최대 7 만 질 수 있다) 한 라운드가 통째로 green 이어야 테스트가 통과하므로, 측정해야 할
것은 opener 비율이 아니라 **라운드 clean 비율**이다. 20은 점추정으로도 상한으로도 1 % 아래인 가장
가까운 라운드 수다(상한 기준 필요 라운드 15.1).

### 7.12 라운드-3 리뷰 처분 (독립 리뷰 high, 2026-09-30 · 6건 · 최종 라운드)

리뷰어 판정: **운영 재시도 경로에 정정할 correctness 결함 없음**(sqlite btree/pager 잠금 동작과
대조해 확인). 6건은 누수·중복·표현 문제다.

| # | 지적 | 처분 |
|---|---|---|
| F2 | `evidence/backup.py::restore_evidence` 가 스토어를 **다 만든 뒤** 검증한다 — 검증이 거부하면 그 스토어를 아무도 닫지 않고, traceback 이 연결(과 -wal·-shm)을 붙들고 있다. **25차에서 네 생성자에 넣은 가드와 같은 결함이 한 프레임 위에 남아 있었다** | **수정.** 같은 가드를 씌웠다. 백업 파일의 `chain_digest` 를 손상시켜 거부를 유발하고, traceback 으로 그 연결에 도달해 닫혔는지 단언하는 테스트 추가 — 가드를 빼면 red |
| F3 | 8줄 근거 + `try/except BaseException: close(); raise` 가 네 생성자에 **복붙**돼 있다 | **수정.** `schema_ledger.closing_on_failure` 컨텍스트 매니저 **하나**로 모으고 근거도 거기 한 번만. 기계적 변경(같은 문장·같은 순서·테스트 무변경 green). F2 가 스토어를, 생성자가 연결을 넘기므로 인자는 `close()` 를 가진 무엇이든 받는다 |
| F5 | 경고가 「최대 **3배**」라고 하는데 그 줄을 쓰는 시점엔 첫 PRAGMA 대기가 이미 소진돼 남은 상한은 **2배**다. 게다가 결과를 안 적어 로그만으로 「회복」과 「아직 멈춤」을 구별할 수 없다 | **수정.** 문구 정정 + **결과 줄 둘**(복구됨 / 거부함). 거부 줄은 `raise` 로 같은 객체를 다시 올리므로 연쇄되지 않는다(F2 성질 유지) |
| F6 | `mode = ""` + `contended` 가 한 사실을 두 변수로 들고 있다 | **수정.** `mode: str \| None` 하나로 |
| F4 | `_WAIT_AND_RETRY` 가 로그용 진단 읽기(`PRAGMA database_list`)를 **메커니즘 단언에 못박아** 뒀다 — 경고 문구를 무해하게 바꾸면 네 테스트가 동시에 깨지고, 정작 중요한 주장(전환 시도 둘이 대기 하나를 감싼다)은 따로 서술돼 있지 않았다 | **수정.** 상수는 메커니즘만, 비교 전에 진단을 걸러낸다. 진단이 실제로 돈다는 것은 한 테스트에서 따로 단언해 로그 경로 커버리지를 잃지 않는다 |
| F1 | `_construct('rcl')` 가 사설 evidence 스토어를 열고 안 닫는다 — **거부된 부팅이 핸들을 남기지 않음을 단언하는 바로 그 테스트가 하나 흘리고 있었다** | **수정.** `ExitStack` 등록. `-W error::ResourceWarning` 으로 확인 |

기각 0건.

## 8. 후속 착지 — 커널 `CompositeStateStore` (2026-09-30 · **issue #823 / PR #827** · 브랜치 `fix/tos-kernel-store-wal-birth-race`)

§2.2 가 #818 범위 밖으로 남기고 §7.7 이 「여전히 맨 PRAGMA」로 적었던 그 한 줄을 닫는다. 결정은
세션 모델이 이미 내렸다 — **이슈 #823 의 1안(커널 독립 구현)**. 2안(헬퍼를 커널로 내림)은 여섯 순수
commons 집합을 바꾸는 설계 문서 개정이고, 3안(compose 선생성)은 §3 이 이미 기각한 이유가 그대로
적용된다(스토어를 여는 경로가 compose 하나가 아니다).

### 8.1 실측 — 수정 전

실제 커널 생성자(`CompositeStateStore(path)` → `commit_composite`)로, 갓 만든 경로에 N=8 동시 오픈:

| 조건 | 손실 자녀 | clean 라운드 | q | 95 % Wilson 상한 |
|---|---|---|---|---|
| 40라운드 × 8 | **96 / 320** (전부 `OperationalError: database is locked`) | **6 / 40** | **0.150** | 0.291 |

라운드 수는 이 **라운드 단위** 비율에서 나왔다(§7.11 이 세운 규율 그대로 — opener 비율을 거듭제곱하지
않는다). 1 % 아래로 내리는 데 필요한 라운드는 점추정 3, 상한 4. `_BIRTH_RACE_ROUNDS = 10` 은 둘 다를
한 자릿수 이상 넘기는 가장 가까운 라운드 수다 — 점추정 5.8e-9 · 상한 4.3e-6 · 벽시계 2.3 s.
(#820 의 20 은 네 스토어 중 최악이 q=0.600 이라 필요 라운드가 15.1 이었기 때문이다. 같은 규율,
다른 입력.)

### 8.2 무엇이 어디로 갔나

| 작업 | 착지 |
|---|---|
| 커널 헬퍼 | `tos/src/tos/staterestore/_wal.py` 신설 — `enable_wal_journal` · `_switch_journal_to_wal` · `_wait_out_the_lock_and_retry` · `_is_lock_contest` · 새 예외 `JournalModeRefused`. stdlib `sqlite3` 만 쓴다(방화벽 통과). `store.py::__init__` 가 이것을 부르고, **연 뒤 실패하면 연결을 닫는다** |
| **로그 없음** | 런타임 헬퍼의 `logging.WARNING` 세 줄은 옮기지 **않았다**. 커널에는 로깅 관례가 아예 없다(실측: `tos/src` 아래 `import logging` 0건). 버그 수정의 부수효과로 tos 전체 결정을 내리지 않는다 — 모듈 독스트링에 그 사실과, 커널 쪽 침묵의 경계가 다른 이유(부팅 때 스토어 넷이 아니라 기록마다 파일 하나)를 적었다 |
| DRY 장치 | `tests/tools/test_tos_wal_mechanism_drift.py` — 두 모듈을 **텍스트로 읽어** AST 로 메커니즘 일곱 가지를 뽑아 대조한다. import 를 하지 않으므로 어느 방향으로도 방화벽 간선이 생기지 않고, `tests/tools` 에 두어 어느 쪽 스위트에도 속하지 않게 했다 |
| 테스트 | `tos/tests/staterestore/test_staterestore_wal_journal.py`(모서리 10건) · `test_staterestore_wal_birth_race.py`(N=8 × 10라운드 + 재오픈) · 폐쇄 테스트에 `_wal` 서브모듈 추가 |
| EV-L3 게이트 | `tools/tos_evidence_run.py` — §7.10 부수 메모가 예고한 red 를 실측하고 닫았다(§8.4) |
| digest | `9595ef63 → 3ea8f6dc` (§8.6) |

### 8.3 뮤테이션 (red 확인 · 전건)

| 뮤테이션 | red 가 된 테스트 |
|---|---|
| M1 수정 전 생성자 전체(맨 PRAGMA · close 가드 없음) | `test_concurrent_first_open_of_a_brand_new_store_admits_every_process` **연속 3회 red** · `test_a_refused_open_closes_the_store_connection` red |
| M2 반환값 확인 제거 | `test_a_journal_mode_that_is_not_wal_refuses` (단독) |
| M3 `SQLITE_BUSY` 아닌 오류도 재시도 | `test_an_operational_error_that_is_not_a_lock_is_not_retried` · `test_a_locked_table_is_not_treated_as_a_lock_contest` |
| M4 재시도를 한 번 더(드리프트 핀) | `test_a_second_retry_is_refused_by_the_comparison` — 스크래치 사본으로 실제 변이시켜 확인 |

### 8.4 EV-L3 게이트 — 예고된 red 를 실측하고 닫았다

§7.10 의 부수 메모가 옳았다. 헬퍼로 옮긴 직후 실측:

```text
check_persistence_substrate: met=False  pragmas_missing=['journal_mode=WAL']
```

처분은 이슈 코멘트의 **1안**이다 — 게이트가 리터럴의 새 위치를 보게 하되 **게이트의 의도를
보존하는 방향으로**:

- `PERSISTENCE_PRAGMA_DELEGATE_PATH` 신설. 위임 모듈의 pragma 도 읽는다.
- **단, `CompositeStateStore.__init__` 이 그 위임을 실제로 «호출»할 때만 센다**(`ast.Call` 노드로 확인 —
  언급이 아니라 호출). 이 조건이 없으면 「독스트링에 적혀 있을 뿐 실행되지 않는 pragma」라는 원래의
  구멍이 파일 하나 건너에서 그대로 재현된다. 그것이 `_executed_pragmas` 가 존재하는 이유다.
  판정은 **그 클래스의** `__init__` 으로 좁혔다 — 모듈 전체에서 「어떤 `__init__` 이든」 찾으면 옆
  클래스의 생성자가 대신 만족시켜 주고 스토어 자신은 전환을 건너뛸 수 있다. 같은 구멍이 한 겹 밖에서
  반복되는 형태라 자기 리뷰에서 좁혔다.
- 위임 모듈도 「연결은 정확히 하나」·in-memory 토큰 검사 **안쪽**에 둔다 — 헬퍼가 자기 연결을 열어
  거기에 WAL 을 걸면 준수한 substrate 로 읽히는 것을 막는다.
- 두 파일이 같은 pragma 를 **다른 값**으로 실행하면 해석하지 않고 conflict 로 기록하고 missing 처리한다.

새 테스트 7건 중 **6건이 음성**이다 — 호출되지 않는 위임 · 옆 클래스가 대신 호출 · WAL 아닌 위임 ·
위임 파일 삭제 · 위임 안의 두 번째 연결 · 값 충돌. 전부 `met=False`.

### 8.5 게이트

모두 워크트리 루트에서, `PYTHONPATH=tos/src:tos/runtime/src` · 저장소 루트 `.venv`.

| 게이트 | 결과 |
|---|---|
| `pytest tos/tests -p no:cacheprovider` (커널 · CI `tos-firewall` 스텝) | **9616 passed** (1:57). 기준선 9601 + 이번 아크 15 |
| `pytest tos/runtime/tests -p no:cacheprovider` | **3246 passed** (6:24, 라운드-3 뒤). 커널만 바꿨는데도 이 스위트를 도는 이유는 compose 가 이 스토어를 배선하기 때문이다 — 그리고 digest 를 먼저 찍지 않았으면 여기가 `ReleaseAdmissionRefused` 로 떨어진다(§8.6 ⚠) |
| `pytest tests/tools/test_tos_*.py tests/tos_l3 -p no:cacheprovider` (CI 거버넌스 배터리, `test_u17_verify.py` 제외 — 로컬 `yq` 미설치) | **883 passed** (4:03, 라운드-3 뒤 — F9 가 위임 분석기 테스트를 걷어내고 측정 테스트를 더한다) |
| `cd tos && mypy src --ignore-missing-imports` | `Success: no issues found in 266 source files` |
| `mypy tos/tests --ignore-missing-imports --disable-error-code=no-untyped-def` | `Success: no issues found in 587 source files` |
| `mypy tos/runtime/src --ignore-missing-imports` | `Success: no issues found in 189 source files` |
| `mypy tos/runtime/tests --ignore-missing-imports --disable-error-code=no-untyped-def` | `Success: no issues found in 238 source files` |
| `black --check` (CI 스텝 그대로) | `1303 files would be left unchanged` |
| `ruff check` | `All checks passed!` |
| `python tools/tos_firewall_check.py` | `PASS — no import-firewall violations` |
| `lint-imports` | `Contracts: 3 kept, 0 broken` |
| `python tools/tos_size_budget.py --check` | `PASS: 0 violations (38 registered exception(s))` |

### 8.7 리뷰 처분 (독립 리뷰 high, 2026-10-01 · 8건)

| # | 지적 | 처분 |
|---|---|---|
| F1 | EV-L3 게이트가 위임 호출을 **이름만** 보고 인정한다 — `store.py` 가 `def enable_wal_journal(conn): return None` 을 자기 안에 정의해도 호출 노드가 맞아 `met=True`. 「적혀 있을 뿐 실행되지 않는」 구멍이 **바인딩 하나 건너**에서 다시 열린다 | **수정.** 세 조건의 논리곱으로 바꿨다 — (a) `from tos.staterestore._wal import enable_wal_journal` 을 **별칭 없이** import 하고, (b) 그 이름이 모듈/생성자 어디서도 재바인딩되지 않으며, (c) 생성자가 호출한다. 음성 테스트 5건(지역 stub · import 뒤 재바인딩 · 별칭 import · 다른 모듈에서 import · `ImportError` 폴백 stub) 전건 **수정 전 red** |
| F1+ | (자기 리뷰) F1 수정의 재바인딩 검사가 **모듈 본문만** 훑어 `try: from … import … / except ImportError: def …(conn): return None` 을 그대로 통과시킨다 — 같은 결함이 문장 하나 안쪽에 | **수정.** 정당한 바인딩은 `ImportFrom` 하나뿐이므로 `def`/`class`/대입은 **어디에 있든** 재바인딩이다 → 스캔을 트리 전체로 넓혔다. 테스트 1건 추가, 모듈 본문 스캔으로 되돌리면 red(`46ba985f`) |
| F2 | 읽기 전용 경로(`reload_conservative`·L3 reader)가 fail-closed WAL 전환을 타게 됐다 — 읽히던 스토어가 거부된다 · 새 예외가 문서화도 분류도 안 됐다 | **부분 수정 + 부분 기각(실측).** 「읽히던 것이 거부된다」는 **재현되지 않는다**: 읽기 전용 롤백저널 파일에서 맨 `PRAGMA journal_mode=WAL` 은 **수정 전에도** `attempt to write a readonly database` 로 죽었다(§8.8 표 — 같은 문장, 같은 오류, 양쪽 트리). `SQLITE_READONLY` 는 잠금 경합이 아니므로 첫 시도에서 그대로 올라가고 `JournalModeRefused` 가 되지도 않는다 — 결정적 테스트로 고정했다. 읽기 전용 오픈으로 바꾸는 쪽은 **기각**: 이 스토어의 생성자는 하나뿐이고 그것이 파일·테이블을 만든다(없는 경로 → 지금은 빈 스토어 + `IncompleteStoreError`, `mode=ro` 로 바꾸면 `unable to open database file`). 스키마 생성 경로를 읽기/쓰기로 가르는 것은 #823 범위 밖 결정이다. **문서·분류는 수정**: `reload_conservative` 의 `Raises:` 에 두 경우를 적고, L3 reader 에 `STORE_UNOPENABLE_EXIT = 71` 을 신설했다(전에는 분류 없는 traceback 으로 exit 1 — `_CRASH_EXIT` 주석이 구별하려고 존재한다던 바로 그 값). 「읽혔지만 불완전」은 여전히 `IncompleteStoreError` 로 exit 0 이 아닌 제 경로를 탄다 |
| F3 | 드리프트 핀의 「재시도 정확히 1회」가 **호출 지점 수**라 루프로 감싸면 2 를 유지한다 | **수정.** `_reject_repetition` 신설 — `enable`·`wait`·`switch` 안의 `For`/`While`/재귀를 `MechanismNotFound` 로 거부한다. 리뷰가 함께 지목한 `Try` 는 **기각**: 양쪽이 정당하게 갖고 있다(`enable` 의 분류 핸들러, 런타임 wait 의 로깅 re-raise) — 금지하면 **현재의 올바른 코드에서 red** 다. 루프 변종을 런타임 텍스트에 실제로 적용해 확인: `switch_attempts` 는 그대로 **2**, `wait_sql` 도 그대로 → 옛 핀은 green 이었다 |
| F4 | 커널 독스트링이 런타임의 리뷰-F3 문단(재시도가 항상 무동작인 것은 아니다)을 빠뜨렸다 | **수정.** 문단을 옮기고 상한 문구를 고쳤다 — 최악 3배는 유지하되 「빠른 거부 = 안 기다렸다」로 읽히지 않도록 명시 |
| F5 | 자녀가 멈추면 `finally` 가 자녀마다 60 s 씩 join 해 약 9분을 잡아먹는다 | **수정.** `_reap()` 하나로 모으고 **공유 데드라인 10 s**. `terminate` 는 그 join **뒤에만** 돌아, 정상 경로에서 `-SIGTERM` exitcode 를 만들지 않는다 |
| F6 | `PR #823` — #823 은 이슈고 PR 은 #827 | **수정.** release.yaml 27차 항목과 §8 제목 둘 다 |
| F7 | 위임 파일을 세 번 읽고, `delegate_sha256` 를 새 `is_file()` 로 판단해 `delegate_called=True` 옆에 `None` 이 기록될 수 있다 | **수정.** 파일마다 **바이트 한 번** 읽어 그 바이트로 파싱하고 그 바이트로 해시한다. `delegate_sha256` 는 **파싱된 트리**에 걸었다. `sha256_file` 과 값이 같음을 테스트로 확인(둘 다 원시 바이트 sha256) |
| F8 | 코드 주석 「~3 s」와 계획 「2.3 s」가 다르다 | **수정.** 실제로 세 번 재어 모듈 전체 **1.4 / 2.0 / 2.0 s** 를 주석과 이 문서에 같은 값으로 적었다 |

기각 0건(부분 기각 2건 — F2 의 읽기 전용 오픈, F3 의 `Try` 금지. 둘 다 사유는 위 표에 실측/현재 코드 기준으로 적었다).

### 8.8 F2 실측 — 읽기 전용 스토어는 수정 전후가 같다

`PRAGMA journal_mode=WAL` → `PRAGMA synchronous=FULL` → `CREATE TABLE IF NOT EXISTS` → `SELECT` 를
파일 권한별로 한 문장씩 돌린 결과:

| 파일 | 디렉터리 | `journal_mode=WAL` | `synchronous=FULL` | `CREATE TABLE IF NOT EXISTS` | `SELECT` |
|---|---|---|---|---|---|
| 롤백저널 · 읽기전용 | 쓰기가능 | **OperationalError: attempt to write a readonly database** | OK | OK | OK |
| 롤백저널 · 읽기전용 | 읽기전용 | **같은 오류** | OK | OK | OK |
| WAL · 읽기전용 | 쓰기가능 | OK (`wal`) | OK | OK | OK |
| WAL · 읽기전용 | 읽기전용 | 오류 | 오류 | 오류 | 오류 |

즉 거부는 **첫 줄에서** 났고 그 줄은 #823 이 바꾸기 전에도 똑같이 있었다. 생성자 전체로도 확인했다 —
수정 전 트리와 수정 후 트리 모두 `CompositeStateStore(path)` 가 `attempt to write a readonly database`
로 실패한다(문구·타입 동일). `mode=ro` URI + `SELECT` 는 롤백저널 파일에서 **OK** 다: 읽는 방법이
없는 것이 아니라, 이 생성자가 그 방법이 아닌 것이다.

### 8.9 라운드-2 리뷰 처분 (독립 리뷰 high, 2026-10-01 · 7건 · 최종 라운드)

F1·F2 는 리뷰가 **이 브랜치의 게이트로 직접 실행**해 녹색임을 보였다. 재현해 확인한 뒤 고쳤다.

| # | 지적 | 처분 |
|---|---|---|
| F1 | 재바인딩 검사가 **문장 종류를 열거**해서, 별칭 import · 튜플 타깃 · `for` 타깃 · `import os as …` · `with … as` · 왈러스는 전부 못 본다 | **수정.** 재현: 여섯 형태 **전부 `met=True`**(아래). 열거를 버리고 **바인딩 발생**으로 바꿨다 — `Store` 문맥의 모든 `Name`(대입 전 형태·`for`·`with as`·컴프리헨션·왈러스를 한 번에 덮는다) + 모든 `alias.asname` + `except … as` + `def`/`class` + 파라미터. 파라미터 포함 7형태를 파라미터라이즈드 음성 테스트로 고정 |
| F2 | 위임의 pragma 를 **모듈 단위**로 읽어, 아무도 부르지 않는 헬퍼 안의 `PRAGMA journal_mode=WAL` 이 게이트를 만족시킨다 | **수정.** 재현: 죽은 헬퍼가 pragma 를 들고 있어도 `met=True`. 추출을 **진입점에서 도달 가능한 호출 그래프**(bare-name 호출 추이)로 좁혔다. 실제 `_wal.py` 는 네 함수 전부 도달하므로 그대로 green. 양방향 테스트 — 죽은 헬퍼는 unmet, 진입점이 부르는 헬퍼는 met |
| F3 | writer 의 오픈 실패는 아직 분류 없이 exit 1 — F2 가 reader 만 고쳤다 | **수정.** writer 도 **생성자만** 감싸 `STORE_UNOPENABLE_EXIT`. 커밋 실패는 감싸지 않는다(그건 이 워커나 카탈로그의 결함이지 「스토어가 없다」가 아니다) |
| F4 | reader 의 `except (…, sqlite3.Error)` 가 `reload_conservative` **전체**를 감싸, 오픈에 성공한 **뒤** 나는 오류(손상 페이지 · 없는 컬럼 · `ProgrammingError`)까지 「열지 못했다」로 접는다 | **수정(구조).** 타입만 좁히는 것으로는 부족하다 — 읽기 실패도 `OperationalError` 일 수 있다. `reload_conservative` 가 **오픈과 읽기를 두 문장으로 분리**하고 오픈 거부만 새 `StoreOpenRefused` 로 싸서 올린다. reader 는 그 하나만 잡는다. 양방향 테스트: 디렉터리 → 71, **열리지만 컬럼이 없는 파일 → 71 아님**(이 테스트는 타입 좁히기로는 통과하지 못한다) |
| F5 | 커널이 런타임과 **같은 이름**의 다른 예외 클래스를 쓴다 — 한쪽을 잡는 `except` 가 다른 쪽을 조용히 놓친다 | **수정.** 커널 쪽을 `StoreJournalModeRefused` 로 개명하고 **양쪽 독스트링에 상호참조**를 적었다(런타임 `schema_ledger.py` 는 이 한 문단만 바뀐다) |
| F6 | `_reap` 의 공유 데드라인이 **첫 join 에만** 걸려, 그 뒤 자녀마다 `terminate` + 10 s join 이면 다시 자녀 수에 비례한다 | **수정.** 세 국면 각각 **전체 공유** 데드라인 — join → terminate+join → kill+join. 자녀가 몇이든 상한은 `3 × _REAP_TIMEOUT_S` |
| F7 | 드리프트 핀이 **일곱 가지 사실의 투영**이라 그 밖의 의미 변화(예: `.lower()` 누락)를 못 본다 | **수정.** 투영을 버리고 네 함수의 **정규화한 AST** 를 통째로 대조한다. 벗겨내는 것은 셋뿐이고 각각 이유를 적었다 — 독스트링 · `_LOG` 호출과 그것만 먹이는 대입 · 본문이 bare `raise` 뿐인 핸들러 — 그리고 각 모듈의 refusal 클래스는 플레이스홀더로 치환(F5 가 이름을 일부러 갈라놨다). 루프·재귀 거부는 유지. 커널 wait 의 꼬리를 런타임과 같은 문장 모양으로 맞췄다 |

기각 0건.

### 8.10 라운드-2 실측

**F1·F2 — 수정 전 게이트는 일곱 형태 모두 green 이었다.** 합법 import 를 그대로 둔 채
이름만 다른 것에 묶는다:

| 형태 | 수정 전 | 수정 후 |
|---|---|---|
| `from … import noop as enable_wal_journal` | `met=True` · `rebound=[]` | `met=False` · `module:import-as` |
| `enable_wal_journal, _ = (lambda c: None), 0` | `met=True` · `rebound=[]` | `met=False` · `module:assign` |
| `for enable_wal_journal in [...]` | `met=True` · `rebound=[]` | `met=False` · `module:assign` |
| `import os as enable_wal_journal` | `met=True` · `rebound=[]` | `met=False` · `module:import-as` |
| `with … as enable_wal_journal` | `met=True` · `rebound=[]` | `met=False` · `module:assign` |
| `(enable_wal_journal := lambda c: None)` | `met=True` · `rebound=[]` | `met=False` · `module:assign` |
| 죽은 헬퍼가 pragma 를 소유(F2) | `met=True` | `met=False` · `reached=['enable_wal_journal']` |

**F7 — 투영이 못 보는 것을 실제로 재어 봤다.** `_switch_journal_to_wal` 의 `.lower()` 를 떼면:

```text
원본   switch_sql=('PRAGMA journal_mode=WAL',) wait_sql=('BEGIN IMMEDIATE','ROLLBACK') attempts=2 contest='code & _SQLITE_PRIMARY_CODE_MASK == sqlite3.SQLITE_BUSY'
변이후 switch_sql=('PRAGMA journal_mode=WAL',) wait_sql=('BEGIN IMMEDIATE','ROLLBACK') attempts=2 contest='code & _SQLITE_PRIMARY_CODE_MASK == sqlite3.SQLITE_BUSY'
AST 대조가 차이를 본다: True
```

일곱 사실이 **전부 동일**하다. 투영으로는 원리적으로 못 잡는다는 F7 의 지적이 맞다.

### 8.11 라운드-3 리뷰 처분 (독립 리뷰 high, 2026-10-01 · 9건 · 최종)

**이 라운드의 결정은 F9 채택이다** — 게이트 3 의 판정 근거를 **소스 분석에서 파일 측정으로** 옮긴다.

| # | 지적 | 처분 |
|---|---|---|
| **F9** | 게이트가 「pragma 가 실행된다」를 증명하려고 정적 분석기를 계속 키우는데, 하네스는 **writer 가 만든 실제 스토어 파일**을 갖고 있고 거기서 저널 모드를 그냥 읽을 수 있다 | **채택.** 크래시 시나리오마다 writer 가 죽은 **직후**(reader 보다 **먼저** — 안 그러면 reader 가 세운 모드를 재게 된다) 실제 파일을 `mode=ro` URI 로 열어 `PRAGMA journal_mode` 를 읽고 `store_journal_mode` 로 행에 적는다. `summarise_crash_schedule` 이 **모든 행에 `wal` 을 요구**한다. 필드가 없는 행은 **만족이 아니라 deviation**(∅-seal). 정적 검사는 **보조 신호**로 축소 — 연결 1개 · 리터럴 타깃 없음 · in-memory 타깃 없음 · 두 pragma 가 실행 리터럴로 존재. **위임 바인딩/도달성 분석기는 삭제**했다 |
| F1 | 두 번째 **별칭 없는** `from <other> import enable_wal_journal`(또는 `import *`)는 재바인딩으로 안 보인다 | **F9 로 소멸.** 그 분석기가 사라졌다 |
| F2 | 위임 pragma 병합이 DFS pop 순서라 나중 `journal_mode=DELETE` 가 WAL 로 기록될 수 있다 | **F9 로 소멸** |
| F6 | `_reachable_functions` 가 「모듈 수준 함수」라고 적고는 `ast.walk` 로 중첩 함수·메서드까지 줍고, `async def` 진입점은 조용히 버린다 | **F9 로 소멸** |
| F7 | in-memory 검사가 **파일 텍스트** substring 이라, `_wal.py` 산문에 `:memory:` 가 들어가면 게이트가 red 가 된다(런타임 쌍둥이 독스트링에 이미 그 문장이 있고 드리프트 핀은 정렬을 권한다) | **수정.** `connect(...)` **인자 리터럴**만 본다. 산문이 게이트를 깨지 못함을 테스트로 고정 |
| F3 | 오픈 경계가 `StoreJournalModeRefused`·`sqlite3.Error` 만 잡는데, 생성자의 부모 `mkdir` 은 **sqlite 호출 전에** `OSError` 로 실패한다 | **수정.** 경계를 `OSError` 까지 넓혔다. 실측: 부모가 일반 파일이면 `FileExistsError`. reader·writer 양쪽 |
| F8 | writer 가 `reload.py` 의 오픈 분류를 **복붙**해 두고 있다 — 세 번째 사본이 될 참 | **수정.** `reload.open_store(path)` **하나**가 `StoreOpenRefused` 를 올리고 reader·writer 가 그 한 타입만 잡는다. F3 의 확장이 한 곳에서 끝났다 |
| F4 | 캐시 버리기가 오픈 **전**이라, 거부된(그리고 이제 재시도 가능하다고 구분해 둔) 오픈이 캐시를 이미 지워 버린다 | **수정(오픈 먼저).** 테스트된 계약을 바꾸지 않는다 — 기존 계약은 「성공한 reload 는 캐시를 버리고 참조하지 않는다」뿐이고 S-3 는 읽기 **전**이기만 하면 된다. 거부된 오픈이 캐시를 남기는지 테스트 추가 |
| F5 | writer 가 쓰기마다 여는데 그 오픈이 이제 busy timeout **약 3배**(~15 s) 블록할 수 있고, 아무도 그 숫자로 데드라인을 잡지 않는다 | **수정(기록).** `compose/_engine_wiring.py` 배선 자리에 최악값을 적었다. **설정 키는 만들지 않았다** — `CompositeStateStore` 는 timeout 인자가 없고 `config/tos_runtime/**` 에 둘 자리도 없다(`sqlite_timeout_s` 는 `SqliteCommitLog` 의 생성자 기본값일 뿐이다). 키를 만드는 것은 배선이 아니라 설정 결정이라 범위 밖 |

기각 0건.

### 8.12 왜 F9 인가 — 세 라운드가 같은 자리를 세 번 뚫었다

게이트 3 의 소스 쪽 절반은 #823 이후 「위임을 따라가되 호출을 요구한다」로 자라났고, **리뷰 라운드마다
그때의 규칙 집합에 우회로가 있었다.**

| 라운드 | 그때의 규칙 | 뚫린 방법 |
|---|---|---|
| 1 | 「`__init__` 이 호출한다」 | 옆 클래스의 `__init__` · `try/except ImportError` 안의 `def` |
| 2 | 「`Store` 문맥 이름 + asname 재바인딩 없음」+「모듈이 pragma 를 실행」 | 별칭 import · 튜플/`for`/`with`/왈러스 타깃 · `import os as …` · 죽은 헬퍼의 pragma |
| 3 | 「별칭 재바인딩 없음」+「도달 가능 함수의 pragma」 | **별칭 없는** 두 번째 import · `import *` · 도달 가능한 헬퍼가 전환을 **되돌림** |

매 라운드의 수정은 규칙 하나를 더하는 것이었고, 매 라운드 다음 리뷰어가 다음 형태를 찾았다. 이것이
**실제 측정이 가능한데 대리 측정을 키울 때** 나는 모양이다. 원하는 성질 — 「크래시한 writer 가 남긴
파일이 WAL 이다」 — 은 stdlib `sqlite3` 로 `mode=ro` 로 열어 한 줄로 읽을 수 있고 `tos` 를 import 하지
않는다(TOS-FW-R 유지). 그래서 그것을 잰다. 소스 검사는 「구성요소가 애초에 on-disk sqlite 가 아닐 수
없다」만 말하는 보조 신호로 남는다 — 한 번의 실행이 말할 수 없는 것, 딱 그것만.

[[guards-that-admit-what-they-name]] 계열의 같은 실패 형태이고, 이번 교훈은 한 줄로: **가드를 규칙으로
키우기 전에, 재려는 성질을 직접 잴 수 있는지 먼저 보라.**

### 8.6 digest

`expected_code_digest`: **9595ef63 → 3ea8f6dc → 7ea0d6d4 → 9fa70b6c → e58cecd4**
(`3c4be1d9d3422f25aa3aa7f15361e9edb228f676b8367e9bcde26bcb54f80f35`). 네 번 도출했다 —
27차 최초 구현 · 28차 §8.7 라운드-1 · 29차 §8.9 라운드-2 · 30차 §8.11 라운드-3
(단일 오픈 경계와 `OSError`, 캐시 버리는 순서, 배선 주석). ⚠ 라운드-3 의 가장 큰 변경(F9,
게이트 3 의 판정 근거를 소스에서 **파일**로)은 `tools/`·`tests/` 에만 있어 이 값에 들어가지 않는다.

27차. **26차까지와 달리 바뀐 것이 커널 소스다** — 이 digest 는 `tos/src/**.py` 와
`tos/runtime/src/**.py` 를 함께 접으므로 커널만 바꿔도 값이 바뀐다(6차 전례). `print-digests` 와
`observe_source_tree_digest()` 두 경로가 일치했고, `expected_dependency_set_digest` 는 무변경
(`20559763…`). 갱신은 늘 두 곳 — `config/tos_runtime/paper/release.yaml` 과
`tos/runtime/tests/compose/test_deploy_approved_values.py::_VALUE_PINS`.

⚠ digest 커밋 **뒤에** 두 커밋이 더 있다(위임 판정의 클래스 범위 한정 + 이 문서). 둘 다 `tools/`·
`tests/tools/`·`docs/` 만 건드리므로 digest 가 접는 두 패키지 트리 밖이다 — 그래도 **가정하지 않고**
마지막 HEAD 에서 다시 찍어 커밋된 값과 같음을 확인했다(`git diff --name-only 71f43174 HEAD` 로 대상
파일도 함께 확인). 「안 건드렸으니 같을 것」이 아니라 「같은 것을 쟀다」로 남긴다 — 26차 주석과 같은 규율.

⚠ 순서: **커널 소스를 바꾼 뒤 digest 를 다시 찍기 전에는 런타임 스위트가 green 이 될 수 없다** —
compose·recovery 가 `ReleaseAdmissionRefused` 로 떨어진다(§7.5 가 런타임 소스에 대해 적은 것과 같은
함정이 커널 변경에서도 그대로 성립한다).
