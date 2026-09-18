# tos RCL 스키마 마이그레이션 런북 (v1 → v2)

이 런북은 커널 라운드 #4 계획(`docs/plans/2026-09-17-tos-kernel-round-4-plan.md`) §7.4 항목
4가 미해소로 남긴 질문 — 「v2 롤아웃 순서를 실 배포 스크립트가 지키는가」 — 를 닫는다.

**결론부터: 그 질문은 성립하지 않는다. 실 배포 스크립트가 없다.** `apply_migrations` 호출부는
`tos_runtime.compose.cli`의 `migrate` 서브커맨드(`tos/runtime/src/tos_runtime/compose/cli.py:844`)
**하나뿐**이고, `docs/runbooks/`를 통틀어 이 커맨드를 자동으로 순서대로 실행하는 스크립트·CI 잡·
cron은 존재하지 않는다. 순서를 지키는 장치는 **사람과 이 런북뿐**이다.

## 0. 범위

- 이 런북은 **RCL 커밋 로그(`rcl.sqlite3`)의 v1→v2 마이그레이션**(커널 라운드 #4 K-4 —
  `reservations` 테이블에 `committed_vector_json` 컬럼 추가)을 실제로 실행해보고 그 결과를
  기록한 것이다.
- 같은 `migrate` 서브커맨드가 `evidence`/`inbox`/`marketfeed` 스토어에도 쓰이지만(모두 현재
  baseline v1 하나뿐 — 실제 v1→v2 승격 사례는 RCL이 처음이다), 이 문서는 RCL을 실측
  worked example로 삼는다. 다른 스토어에 두 번째 버전이 추가되면 같은 절차가 그대로
  적용된다(`store_name`만 바뀐다).
- 코드는 고치지 않았다. 아래 모든 출력은 이 문서를 쓰면서 실제로 실행한 명령의 결과다
  (재현 방법은 §6).

## 1. 왜 순서가 문제가 되는가

`tos_runtime.operations.schema_ledger.ensure_schema_current`는 스토어 생성자(`__init__`)에서
매번 불리며, 온디스크 `PRAGMA user_version`이 그 코드가 기대하는 스키마 버전과 **다르면 방향에
관계없이 부팅을 거부한다** — 뒤처져도 거부, 앞서도 거부(fail-closed, 자동 마이그레이션 0).
`tos_runtime.operations.schema_migrations` 모듈 독스트링이 이미 이렇게 적고 있다(원문 인용,
`schema_migrations.py:15-26`):

> **Rollout order (round #4 review LOW — first genuine v1->v2 bump, so this module carried no
> prior worked example of the deploy-time ordering it requires).**
> `ensure_schema_current` refuses BOTH directions on open (module docstring's points 3/4: behind
> OR ahead of the running code's expected version), so a `RCL_SCHEMA_VERSION` bump is not safe to
> roll out in an arbitrary order against a running store. The required sequence: (1) fully stop
> every process still running the OLD (v1-expecting) code against this store file — a still-live
> v1 process would itself get
> refused the instant `apply_migrations` stamps the file at v2 out from under it; (2) run
> `apply_migrations(path, "rcl")` to bring the file to v2; (3) start the NEW (v2-expecting) code.
> Running `apply_migrations` first, while a v1 process is still up, does not corrupt anything —
> the v1 process simply gets `SchemaVersionRefused` on its next open/reopen — but it does turn a
> planned migration into an unplanned outage of that still-live process.

**핵심을 다시 적는다 — 「손상되지 않는다」와 「거부당한다」는 둘 다 참이고, 서로 다른 축이다.**

| | 데이터 안전성 | 운영 연속성 |
|---|---|---|
| `apply_migrations`를 구버전 프로세스가 떠 있는 동안 먼저 돌린다 | **안전.** ALTER TABLE ADD COLUMN(nullable)뿐, 기존 행 무손상(§3 실측) | **깨진다.** 떠 있던 구버전 프로세스가 다음 open/reopen에서 `SchemaVersionRefused(AHEAD)`로 거부당한다 — 계획된 마이그레이션이 계획 안 된 장애가 된다 |
| 구버전을 먼저 완전히 내리고 마이그레이션 후 신버전을 올린다 | 안전 | 안전(무중단은 아니다 — 정지 구간이 생긴다) |

「위험하다」/「안전하다」로 뭉뚱그리지 말 것 — 데이터는 항상 안전하고, 운영 연속성만 순서에
좌우된다.

## 2. `migrate` 서브커맨드 실사용법

`tos_runtime.compose.cli`에는 콘솔 스크립트 진입점이 등록돼 있지 않다(`tos/runtime/pyproject.toml`
에 `console_scripts` 없음, `cli.py`에도 `if __name__ == "__main__"` 없음). 오늘 실제로 존재하는
호출면은 `python -c`로 `main()`을 직접 부르는 것뿐이다 — `tos-runtime-compose` 같은 실행 파일은
없다(같은 관례를 이미 `docs/runbooks/tos-kis-mock-transport.md` §6이 기록해 두었다).

```bash
python -c "
from tos_runtime.compose.cli import main
import sys
sys.exit(main(['migrate', '--help']))
"
```

실제로 돌려 받은 출력(그대로 인용):

```
usage: tos-runtime-compose migrate [-h] --data-dir DATA_DIR
                                   [--store {evidence,inbox,marketfeed,rcl}]

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR
  --store {evidence,inbox,marketfeed,rcl}
```

- `--data-dir`는 **필수**다. RCL 파일은 `<data-dir>/rcl.sqlite3`로 고정 파생된다
  (`tos_runtime.operations.backup_set.DurableSetPaths.from_data_dir` + `RCL_FILE_NAME =
  "rcl.sqlite3"`) — 파일 경로를 직접 지정하는 옵션은 없다.
- `--store`는 **선택**이다. 생략하면 `STORE_MIGRATIONS`에 등록된 네 스토어
  (`evidence`/`inbox`/`marketfeed`/`rcl`) 전부를 순서대로 마이그레이션한다. RCL만 올리려면
  `--store rcl`을 명시한다.
- **주의 — 최상위 `--help`는 서브커맨드 목록을 보여주지 않는다.** `parse_args`는 첫 토큰이
  `_SUBCOMMANDS`(`run`/`backup-set`/`restore-drill`/`migrate`/`rotate-key`/`print-digests`/
  `print-policy-digests`/`rearm`/`ack-alert`/`nontrade-eval`)에 없으면 그 앞에 `run`을
  끼워 넣는다(`cli.py:544-545`, "토큰 없음 = run"이라는 모듈독스트링 규칙). `--help`도 그
  분기를 그대로 타므로 `main(["--help"])`는 실제로 `run --help`가 되어 `run`의 옵션만
  보여준다(실측 확인). 서브커맨드 목록을 보려면 `--help` 대신 이 문서의 `_SUBCOMMANDS`
  나열을 보거나 `migrate --help`처럼 서브커맨드 이름을 먼저 준다.

실제 `migrate` 실행 명령과 출력(임시 데이터 디렉터리, RCL이 v1로 미리 존재):

```bash
python -c "
from tos_runtime.compose.cli import main
import sys
sys.exit(main(['migrate', '--data-dir', '<data_dir>', '--store', 'rcl']))
"
```

```
migrate: rcl at <data_dir>/rcl.sqlite3 is current
```

exit code `0`. `--store`를 생략하면 이 줄이 등록된 스토어 수만큼(현재 4줄) 반복 출력된다.

## 3. 승격을 실제로 해봤다 — 기존 행 보존 확인

`tos/runtime/tests/operations/test_schema_ledger.py:368-433`(`test_rcl_v1_data_dir_promotes_to_v2_preserving_existing_rows`)
와 같은 방법으로, 등록된 v1 baseline 문장(`RCL_MIGRATIONS[0].statements`)만으로 진짜
"pre-existing v1 파일"을 만들고 `apply_migrations`를 돌렸다. 아래는 그 실행의 실제 stdout이다
(스크립트는 §6):

```
### step1: created v1 rcl.sqlite3 at <tmp>/rcl.sqlite3, schema_version=1
### step2: current code (RCL_SCHEMA_VERSION=2) opens the v1 file WITHOUT migrating first:
### step2 SchemaVersionRefused: rcl: on-disk schema user_version=1 is BEHIND this code's schema_version=2 — run the operator `migrate` CLI (tos_runtime.operations.schema_migrations.apply_migrations) before booting; boot never auto-applies a migration
### step3: apply_migrations(rcl_path, 'rcl')
### step3: schema_version now = 2
### step3: preserved row = ('resv-runbook-demo', 'POTENTIALLY_LIVE', 3, 'acct-9', 'K200F', None)
### step4: pre-K4 code (schema_version=1 literal) opens the now-v2 file:
### step4 SchemaVersionRefused: rcl: on-disk schema user_version=2 is AHEAD of this code's schema_version=1 — this file was created or migrated by newer code than what is running now
```

읽는 법:

- **step2**는 「신버전 코드가 미마이그레이션 v1 파일을 연다」 방향의 실제 거부 메시지다 —
  `SqliteCommitLog(rcl_path, evidence_port=evidence)`를 v1 파일에 그대로 생성자 호출해서
  받았다(모의 문자열이 아니다).
- **step3**은 `apply_migrations(path, "rcl")`을 실제로 돌린 결과다. `reservations` 행
  (`resv-runbook-demo`)이 v1 시절 5개 컬럼 값 그대로 보존되고, 새 컬럼 `committed_vector_json`은
  `None`(NULL)으로 채워졌다 — **가짜 값이 아니라 "v1 시절에는 committed vector를 기록한 적이
  없다"는 정직한 NULL**이다(`schema_migrations.py:291-296`의 의도 그대로).
- **step4**는 「구버전(v1 기대) 코드가 이미 마이그레이션된 v2 파일을 연다」 방향이다. 이 저장소에는
  실제 pre-K4 코드가 더 이상 없으므로(K-4 커밋 `982dea35`에서 `RCL_SCHEMA_VERSION`이 1→2로
  바뀌었다), `ensure_schema_current`를 K-4 이전 리터럴 값(`schema_version=1`)으로 직접 호출해
  재현했다. `ensure_schema_current`/`SchemaVersionRefused`의 판정 로직 자체는 K-4 커밋에서
  **한 글자도 바뀌지 않았다**(`git diff 982dea35^ 982dea35 -- tos_runtime/operations/schema_ledger.py`
  는 빈 diff) — 바뀐 것은 호출자가 넘기는 `schema_version` 리터럴 하나뿐이므로, 이 재현은
  "구버전 코드를 그대로 복원해 돌린 것"과 판정 결과가 동일하다. 다만 **진짜 pre-K4 프로세스
  바이너리로 돌린 것은 아니라는 점은 정직하게 남긴다.**

## 4. 백업 — 마이그레이션 전에 durable set 전체를 백업한다

`migrate`는 원본 파일을 in-place로 바꾼다(백업을 자동으로 만들지 않는다). 이 저장소에는
이미 backup/restore 경로가 있다 — `backup-set`/`restore-drill` 서브커맨드
(`tos_runtime.operations.backup_set.backup_set`/`restore_set`). **RCL 파일 하나만 복사해두는
것은 부족하다** — RCL의 `entries`는 evidence store의 seq를 참조하므로, 되돌릴 때는 evidence/
RCL/inbox를 **같은 세대(generation)로 함께** 되돌려야 정합이 맞는다.

durable set은 실제로는 **다섯 파일**이다 — `evidence`/`rcl`/`inbox`(필수 3) +
`composite_state`/`marketfeed`(선택 2, `_OPTIONAL_FILES`, `backup_set.py:128`). `backup_set`은
`file_specs` 딕셔너리(`backup_set.py:421-427`)에 다섯을 전부 등록해두고, 필수 3 중 하나라도
파일이 없으면 거부하며(`backup_set.py:428-435`), 선택 2는 없으면 조용히 건너뛰고 **있으면
백업에 포함**한다. 즉 실제 배포에서 `composite_state.sqlite3`/`marketfeed.sqlite3`가 존재하는
데이터 디렉터리라면, `backup-set`은 그 둘도 같은 세대로 함께 백업한다.

실제로 evidence+rcl(v1)+inbox 셋을 만들고 백업 → 마이그레이션 → 복원까지 돌린 결과(스크립트는
§6):

```bash
python -c "
from tos_runtime.compose.cli import main
import sys
sys.exit(main(['backup-set', '--help']))
"
```

```
usage: tos-runtime-compose backup-set [-h] --data-dir DATA_DIR --dest DEST
                                      --generation GENERATION
                                      [--readiness-verdict READINESS_VERDICT]

options:
  -h, --help            show this help message and exit
  --data-dir DATA_DIR
  --dest DEST
  --generation GENERATION
  --readiness-verdict READINESS_VERDICT
```

실제 절차 (함수 레벨 재현 — `backup_set`/`restore_set`은 `cli.py`의 `backup-set`/`restore-drill`
서브커맨드가 그대로 호출하는 바로 그 함수다):

```
### pre-migrate rcl schema_version=1
### backup-set gen1 written under <tmp>/backups
### now running migrate (rcl v1 -> v2)
### post-migrate rcl schema_version=2
### restore-drill restored gen1 into <tmp>/restored
### restored rcl schema_version=1
```

즉 마이그레이션 전에 `backup-set --data-dir <data_dir> --dest <backup_root> --generation
<N>`을 돌려두면, 마이그레이션이 잘못됐을 때 `restore-drill`로 **마이그레이션 이전 세대 전체**를
별도 디렉터리에 복원할 수 있다. 위 실측은 필수 3파일(evidence+rcl+inbox, 전부 v1 시절 상태)만
갖춘 데이터 디렉터리로 돌렸다 — `composite_state`/`marketfeed`가 함께 있었다면 그 둘도 같은
세대로 복원됐을 것이다(§4 위 문단, `restore_set`은 매니페스트의 `files` 전부를 순회한다). 위
실측에서 `gen1`을 복원한 뒤 RCL 파일의 `schema_version`이 다시 `1`로 돌아온 것이 그 증거다.

CLI 레벨에서는:

```bash
python -c "
from tos_runtime.compose.cli import main
import sys
sys.exit(main(['restore-drill', '--help']))
"
```

```
usage: tos-runtime-compose restore-drill [-h] --manifest MANIFEST --dest DEST
                                         --environment-label ENVIRONMENT_LABEL
                                         --custody-root CUSTODY_ROOT

options:
  -h, --help            show this help message and exit
  --manifest MANIFEST
  --dest DEST
  --environment-label ENVIRONMENT_LABEL
  --custody-root CUSTODY_ROOT
```

- `--manifest`는 `backup-set`이 `<dest>/gen<N>.set.manifest.json`에 쓴 파일 그 자체를
  가리킨다(디렉터리가 아니다 — 실측으로 확인한 실제 파일명 패턴, `backup_set.py:130,466`의
  `_MANIFEST_SUFFIX = ".set.manifest.json"`).
- `--environment-label`은 **non-live 라벨만** 허용한다. `paper`/`restricted-live`/`production`을
  주면 아래 메시지로 거부한다(`cli.py:816-822`, 원문):

  ```
  restore-drill: refused — environment_label={label!r} is a live label; drills only ever run
  under a non-live label
  ```

- `--custody-root`는 `restore_set`에 넘길 evidence 키를 여는 `FileKeyProvider`의 근거
  디렉터리다(`FileKeyProvider(args.custody_root, expected_owner_uid=os.getuid())`,
  `cli.py:824-826`) — 실 배포에서는 그 스토어를 만든 프로세스와 같은 custody 구조여야 한다.
  이 런북의 §4 실측은 함수 레벨(`restore_set` 직접 호출, `FixedKeyProvider` 테스트 더블)까지만
  재현했다 — 실제 custody 파일 구조까지 갖춘 CLI 종단 재현은 **미실행**이다(아래 §7 참고).

## 5. 롤백 — 스키마 역마이그레이션은 없다

`RCL_MIGRATIONS`(`schema_migrations.py:260-305`)에는 v1(baseline)과 v2(`committed_vector_json`
추가) 두 항목만 있고, **v2→v1로 되돌리는 마이그레이션은 등록돼 있지 않다.** 코드 전체를 뒤져도
`DROP COLUMN`/`rollback`/`downgrade` 계열은 이 모듈에 없다(실측 grep 결과 0건).

**즉 "마이그레이션을 롤백한다"는 개념 자체가 이 코드베이스에 없다.** 대신 있는 것은 §4의
백업/복원이다 — 마이그레이션이 잘못됐다고 판단되면:

1. `restore-drill`로 마이그레이션 **직전 세대**를 별도 디렉터리에 복원한다. `restore_set`은
   백업 매니페스트의 `files`에 실린 항목을 **전부** 순회하며 복원한다(`backup_set.py:538`) —
   최소 evidence+rcl+inbox, 그리고 그 세대에 `composite_state`/`marketfeed`가 백업돼 있었다면
   **그것도 함께** 되돌아간다(§4). "RCL만 되돌린다"는 선택지는 없다 — 세대 전체가 단위다.
2. 복원된 디렉터리를 새 `--data-dir`로 삼아 **구버전 코드**를 그 위에서 기동한다(v1 상태로
   되돌아갔으므로 신버전 코드는 다시 BEHIND로 거부된다 — v1 코드가 필요하다).
3. 원래 `--data-dir`의 마이그레이션된 파일은 그대로 두거나(증거 보존) 폐기한다 — 이 판단은
   운영자 몫이다.

**있지도 않은 롤백을 있는 것처럼 적지 않는다.** 사전 백업이 유일한 안전망이다 — §4의 절차를
마이그레이션 전에 반드시 거쳐야 하는 이유가 이것이다.

## 6. 재현 스크립트 (실제로 실행한 것 — 그대로 복사해서 돌아간다)

아래 세 스크립트가 이 문서 §2~§4의 모든 출력을 만들었다. 각자 `tempfile.mkdtemp`로 자기
작업 디렉터리를 만들고 끝에 정리하므로 인자 없이 그대로 실행할 수 있다. 실행 환경은
공통이다 — 이 저장소의 워크트리에서, `PYTHONPATH`로 `tos/src`+`tos/runtime/src`+저장소
루트를 얹고(별도 `pip install -e` 없이), 메인 체크아웃의 `tos/.venv/bin/python`(의존성만
재사용 — editable 설치 경로가 실제로 이 워크트리를 가리키는지는 import 결과로 직접 확인함)
으로 실행한다:

```bash
export PYTHONPATH=<worktree>/tos/src:<worktree>/tos/runtime/src:<worktree>
<main-repo>/tos/.venv/bin/python <script>.py
```

### 6.1 양방향 거부 + v1→v2 승격 (§3 출력의 출처)

`tos/runtime/tests/operations/test_schema_ledger.py:368-433`
(`test_rcl_v1_data_dir_promotes_to_v2_preserving_existing_rows`)와 같은 v1 baseline 구성
방식을 그대로 쓴다.

```python
"""Reproduction script for the RCL v1->v2 migration runbook.
Every step here is real: real SqliteCommitLog construction, real apply_migrations,
real ensure_schema_current. No fabricated output.
"""
import shutil
import sqlite3
import tempfile
from pathlib import Path

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.operations.schema_ledger import SchemaVersionRefused, ensure_schema_current
from tos_runtime.operations.schema_migrations import RCL_MIGRATIONS, apply_migrations, schema_version
from tos_runtime.rcl.log import SqliteCommitLog
from tos_runtime.rcl.schema import RCL_SCHEMA_VERSION


class FixedKeyProvider:
    """Same test double as tos/runtime/tests/engine/conftest.py::FixedKeyProvider (inlined here
    to avoid fighting the tests package's relative-import layout in a standalone script)."""

    def __init__(self, key_generation: int = 1, key: bytes = b"engine-test-fixed-key") -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        return (self._key_generation, self._key)

    def generations(self) -> tuple[int, ...]:
        return (self._key_generation,)


tmp = Path(tempfile.mkdtemp(prefix="rcl-migration-runbook-"))
print(f"### workdir: {tmp}")

# ---- Step 1: build a genuine pre-existing v1 RCL file (baseline statements, no shortcuts) ----
rcl_path = tmp / "rcl.sqlite3"
baseline = RCL_MIGRATIONS[0]
assert baseline.version == 1
conn = sqlite3.connect(str(rcl_path))
for stmt in baseline.statements:
    conn.execute(stmt)
conn.execute(
    "INSERT INTO reservations (reservation_id, state, last_seq, scope_account, "
    "scope_instrument) VALUES (?, ?, ?, ?, ?)",
    ("resv-runbook-demo", "POTENTIALLY_LIVE", 3, "acct-9", "K200F"),
)
conn.execute("PRAGMA user_version = 1")
conn.commit()
conn.close()
print(f"### step1: created v1 rcl.sqlite3 at {rcl_path}, schema_version={schema_version(rcl_path)}")

# ---- Step 2: NEW code (current, expects v2) opens the un-migrated v1 file directly ----
evidence_path = tmp / "evidence.sqlite3"
evidence = SqliteEvidenceStore(evidence_path, key_provider=FixedKeyProvider())
print("### step2: current code (RCL_SCHEMA_VERSION="
      f"{RCL_SCHEMA_VERSION}) opens the v1 file WITHOUT migrating first:")
try:
    SqliteCommitLog(rcl_path, evidence_port=evidence)
    print("### step2: UNEXPECTED — did not refuse")
except SchemaVersionRefused as exc:
    print(f"### step2 SchemaVersionRefused: {exc}")
evidence.close()

# ---- Step 3: run the real migrate path (apply_migrations) ----
print("### step3: apply_migrations(rcl_path, 'rcl')")
apply_migrations(rcl_path, "rcl")
print(f"### step3: schema_version now = {schema_version(rcl_path)}")

conn = sqlite3.connect(str(rcl_path))
row = conn.execute(
    "SELECT reservation_id, state, last_seq, scope_account, scope_instrument, "
    "committed_vector_json FROM reservations WHERE reservation_id = ?",
    ("resv-runbook-demo",),
).fetchone()
conn.close()
print(f"### step3: preserved row = {row}")

# ---- Step 4: OLD code (pre-K4, expected v1) opens the now-migrated v2 file ----
# Real ensure_schema_current, unchanged since before K-4 (git diff 982dea35^..982dea35 on
# schema_ledger.py is empty) -- only the schema_version ARGUMENT differs between old/new code,
# which is exactly what this call pins to reproduce the pre-K4 constant (RCL_SCHEMA_VERSION was
# 1 before commit 982dea35).
print("### step4: pre-K4 code (schema_version=1 literal) opens the now-v2 file:")
conn = sqlite3.connect(str(rcl_path))
try:
    ensure_schema_current(
        conn,
        store_name="rcl",
        schema_version=1,
        was_fresh=False,
        migration_digest="unused-on-this-path",
        monotonic_ns=lambda: 0,
    )
    print("### step4: UNEXPECTED — did not refuse")
except SchemaVersionRefused as exc:
    print(f"### step4 SchemaVersionRefused: {exc}")
finally:
    conn.close()

shutil.rmtree(tmp)
print("### cleanup done")
```

### 6.2 CLI 종단 `migrate` (§2의 실행 명령/출력의 출처)

`tos_runtime.compose.cli.main(["migrate", ...])`를 실제로 호출한다 —
`DurableSetPaths.from_data_dir` 경로 파생까지 포함한 진짜 서브커맨드 디스패치.

```python
"""Reproduces the actual `migrate` subcommand as an operator would invoke it (main()), against
a data-dir holding a genuine pre-existing v1 rcl.sqlite3 -- exercising cli.py's own dispatch,
not just apply_migrations directly."""
import shutil
import sqlite3
import tempfile
from pathlib import Path

from tos_runtime.compose.cli import main
from tos_runtime.operations.schema_migrations import RCL_MIGRATIONS, schema_version

tmp = Path(tempfile.mkdtemp(prefix="rcl-cli-runbook-"))
data_dir = tmp / "data"
data_dir.mkdir()
rcl_path = data_dir / "rcl.sqlite3"

baseline = RCL_MIGRATIONS[0]
conn = sqlite3.connect(str(rcl_path))
for stmt in baseline.statements:
    conn.execute(stmt)
conn.execute("PRAGMA user_version = 1")
conn.commit()
conn.close()
print(f"### before: schema_version={schema_version(rcl_path)}")

print("### invoking: migrate --data-dir <data_dir> --store rcl")
rc = main(["migrate", "--data-dir", str(data_dir), "--store", "rcl"])
print(f"### exit code: {rc}")
print(f"### after: schema_version={schema_version(rcl_path)}")

shutil.rmtree(tmp)
```

### 6.3 백업 → 마이그레이션 → 복원 라운드트립 (§4의 실행 결과의 출처)

`SqliteEvidenceStore`/`SqliteEventInbox`로 evidence/inbox를 만들고 RCL은 v1 baseline으로
직접 구성한 뒤, `cli.py`의 `backup-set`/`restore-drill`이 그대로 호출하는 `backup_set`/
`restore_set` 함수를 직접 호출한다(이 스크립트는 필수 3파일만 구성한다 — §4에서 설명한
선택 2파일(`composite_state`/`marketfeed`)은 여기서 실측하지 않았다).

```python
"""Reproduces the backup-before-migrate / restore-as-rollback path for the RCL migration runbook.
Real backup_set + real restore_set (the same functions cli.py's backup-set/restore-drill
subcommands call), against a real evidence+rcl+inbox durable set.
"""
import shutil
import sqlite3
import tempfile
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.operations.backup_set import DurableSetPaths, backup_set, restore_set
from tos_runtime.operations.schema_migrations import (
    RCL_MIGRATIONS,
    apply_migrations,
    schema_version,
)

SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


class FixedKeyProvider:
    def __init__(self, key_generation: int = 1, key: bytes = b"engine-test-fixed-key") -> None:
        self._key_generation = key_generation
        self._key = key

    def current(self) -> tuple[int, bytes]:
        return (self._key_generation, self._key)

    def generations(self) -> tuple[int, ...]:
        return (self._key_generation,)


tmp = Path(tempfile.mkdtemp(prefix="rcl-rollback-runbook-"))
data_dir = tmp / "data"
data_dir.mkdir()
backup_dir = tmp / "backups"
restore_dest = tmp / "restored"

key_provider = FixedKeyProvider()
evidence = SqliteEvidenceStore(data_dir / "evidence.sqlite3", key_provider=key_provider)
evidence.append({"n": 1}, kind="EVENT_CONSUMED", record_class="EVENT_CONSUMED")
evidence.close()
inbox = SqliteEventInbox(data_dir / "inbox.sqlite3", scheme=SCHEME)
inbox.close()

# rcl.sqlite3 built directly from the registered v1 baseline (never via SqliteCommitLog's own
# constructor, which would stamp a FRESH file straight to the current RCL_SCHEMA_VERSION=2 --
# the whole point here is a genuinely pre-existing, un-migrated v1 file).
rcl_baseline = RCL_MIGRATIONS[0]
assert rcl_baseline.version == 1
conn = sqlite3.connect(str(data_dir / "rcl.sqlite3"))
for stmt in rcl_baseline.statements:
    conn.execute(stmt)
conn.execute(
    "INSERT INTO reservations (reservation_id, state, last_seq, scope_account, "
    "scope_instrument) VALUES (?, ?, ?, ?, ?)",
    ("resv-rollback-demo", "POTENTIALLY_LIVE", 1, "acct-9", "K200F"),
)
conn.execute("PRAGMA user_version = 1")
conn.commit()
conn.close()

print(f"### pre-migrate rcl schema_version={schema_version(data_dir / 'rcl.sqlite3')}")

paths = DurableSetPaths.from_data_dir(data_dir)
manifest_pre = backup_set(paths, backup_dir, generation=1)
print(f"### backup-set gen{manifest_pre.generation} written under {backup_dir}")

print("### now running migrate (rcl v1 -> v2)")
apply_migrations(paths.rcl, "rcl")
print(f"### post-migrate rcl schema_version={schema_version(paths.rcl)}")

# Simulate "the migration/rollout went wrong, restore the pre-migration generation".
restored = restore_set(backup_dir / "gen1.set.manifest.json", restore_dest, key_provider=key_provider)
restored_rcl_path = restore_dest / "rcl.sqlite3"
print(f"### restore-drill restored gen{restored.manifest.generation} into {restore_dest}")
print(f"### restored rcl schema_version={schema_version(restored_rcl_path)}")

shutil.rmtree(tmp)
```

세 스크립트 모두 이 조치 커밋 시점에 다시 실행해 §2~§4에 인용된 출력과 **바이트 단위로
동일**함을 재확인했다(작업 디렉터리 경로 문자열만 매 실행 랜덤).

## 7. 못 한 것 (정직하게 남긴다)

- `restore-drill` **CLI 서브커맨드 자체**(즉 `main(["restore-drill", ...])`, custody_root 기반
  `FileKeyProvider`까지 포함)는 종단 재현하지 않았다 — `restore_set` 함수 레벨(같은 테스트 스위트가
  쓰는 `FixedKeyProvider`)까지만 재현했다. 실 custody 매니페스트(0600 파일 + scope 파일 +
  `evidence.key.<generation>`)를 갖춘 CLI 종단 리허설은 이 런북의 범위 밖으로 남긴다 — 필요하면
  `tos/runtime/tests/recovery/test_drill.py`(전체 recompose+replay 드릴, `compose_paper_runtime`
  기반)가 그 종단 경로를 이미 커버한다고 모듈독스트링에 적혀 있다(§8 참고).
- 이 런북은 RCL 하나만 실측했다. `evidence`/`inbox`/`marketfeed`는 현재 baseline v1 하나뿐이라
  v1→v2 승격을 실측할 대상이 없다 — 두 번째 버전이 등록되면 §3의 방법을 그대로 재사용하면 된다.
- 코드를 고치지 않았다(요청 범위 밖) — `migrate --help`가 서브커맨드 목록을 보여주지 않는 점
  (§2의 주의)은 사용성 흠이지 이 런북이 해소할 항목이 아니다. 팀리드에게 별도로 보고한다.

## 8. 관련 문서

- `tos/runtime/src/tos_runtime/operations/schema_migrations.py` — `RCL_MIGRATIONS`/
  `apply_migrations`/롤아웃 순서 독스트링(정본).
- `tos/runtime/src/tos_runtime/operations/schema_ledger.py` — `ensure_schema_current`/
  `SchemaVersionRefused`(양방향 거부 판정 정본).
- `tos/runtime/tests/operations/test_schema_ledger.py:368-433` — v1→v2 승격 + 기존 행 보존
  단위테스트(이 런북의 §3 실측과 같은 구성 방식).
- `tos/runtime/tests/recovery/test_drill.py` — 전체 recompose+replay 드릴(이 런북이 실측하지
  않은 CLI 종단 `restore-drill` 경로).
- `docs/plans/2026-09-17-tos-kernel-round-4-plan.md` §7.4 항목 4 — 이 런북이 닫는 미해소 질문의
  원문.
- `docs/runbooks/tos-kis-mock-transport.md` §6 — "콘솔 스크립트 없음, `python -c`로 직접 호출"
  관례의 선례.
