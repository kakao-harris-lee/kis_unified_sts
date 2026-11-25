# tos RCL 스키마 마이그레이션 런북 (v1 → v2)

이 런북은 「v2 롤아웃 순서를 실 배포 스크립트가 지키는가」에 답한다.

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
  (재현 기록은 §3).

## 1. 왜 순서가 문제가 되는가

> ⚠ **이름 정정 (2026-09-30 · #801).** 아래 본문은 부팅 검사를
> `ensure_schema_current`라고 부른다 — 이 문서를 쓴 시점의 함수 이름이다. #801 이후 **스토어
> 생성자가 부르는 것은 `tos_runtime.operations.schema_ledger.open_or_create_schema`**이고,
> 온디스크 버전이 어긋날 때 방향 관계없이 부팅을 거부하는 **규칙은 한 글자도 바뀌지 않았다**
> (`ensure_schema_current` 자체도 하위호환으로 남아 있다).
> 바뀐 것은 제네시스가 이제 `BEGIN IMMEDIATE` 하나 안에서 원자적이라는 점뿐이며, 이 런북의
> 절차·판정·순서 제약은 전부 유효하다.

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
| `apply_migrations`를 구버전 프로세스가 떠 있는 동안 먼저 돌린다 | **안전.** ALTER TABLE ADD COLUMN(nullable)뿐, 기존 행 무손상(커밋된 테스트가 고정한다 — §3) | **깨진다.** 떠 있던 구버전 프로세스가 다음 open/reopen에서 `SchemaVersionRefused(AHEAD)`로 거부당한다 — 계획된 마이그레이션이 계획 안 된 장애가 된다 |
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
  `print-policy-digests`/`rearm`/`ack-alert`)에 없으면 그 앞에 `run`을
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
migrate: rcl at <data_dir>/rcl.sqlite3 — already at v2, nothing to do
```

exit code `0`. `--store`를 생략하면 이 줄이 등록된 스토어 수만큼(현재 4줄) 반복 출력된다.

⚠ **이 줄은 예전에 `"is current"` 였다.** 리뷰 L3 이후 `migrate` 는 서로 다른 세 결과를
구분해 출력한다(아무것도 안 함 · 버전 적용 · 보조 구조 복구 —
`compose/cli.py::_migrate_report`). `"is current"` 를 기대하는 스크립트·grep 은 맞지 않는다.

## 3. 실측 기록 (2026-09-17 · git 이력)

v1→v2 승격을 실제로 돌려 기존 행 보존·양방향 거부·백업 라운드트립을 확인한 기록과
그 재현 스크립트는 2026-11-20 에 지웠다 — `git log --diff-filter=D -- docs/runbooks/`.
같은 사실을 고정하는 것은 커밋된 테스트다:
`tos/runtime/tests/operations/test_schema_ledger.py`(v1→v2 승격 + 기존 행 보존,
양방향 `SchemaVersionRefused`)와 `tos/runtime/tests/recovery/test_drill.py`
(CLI 종단 recompose+replay 드릴).

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

실제로 evidence+rcl(v1)+inbox 셋을 만들고 백업 → 마이그레이션 → 복원까지 돌린 결과:

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
  재현했다 — 실제 custody 파일 구조까지 갖춘 CLI 종단 경로는
  `tos/runtime/tests/recovery/test_drill.py` 가 덮는다.

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

## 8. 관련 문서

- `tos/runtime/src/tos_runtime/operations/schema_migrations.py` — `RCL_MIGRATIONS`/
  `apply_migrations`/롤아웃 순서 독스트링(정본).
- `tos/runtime/src/tos_runtime/operations/schema_ledger.py` — `ensure_schema_current`/
  `SchemaVersionRefused`(양방향 거부 판정 정본).
- `tos/runtime/tests/operations/test_schema_ledger.py:368-433` — v1→v2 승격 + 기존 행 보존
  단위테스트.
- `tos/runtime/tests/recovery/test_drill.py` — 전체 recompose+replay 드릴(이 런북이 실측하지
  않은 CLI 종단 `restore-drill` 경로).
- `docs/runbooks/tos-kis-mock-transport.md` §6 — "콘솔 스크립트 없음, `python -c`로 직접 호출"
  관례의 선례.
