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
> `ensure_schema_current` refuses BOTH directions on open (behind OR ahead of the running code's
> expected version), so a `RCL_SCHEMA_VERSION` bump is not safe to roll out in an arbitrary order
> against a running store. The required sequence: (1) fully stop every process still running the
> OLD (v1-expecting) code against this store file — a still-live v1 process would itself get
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
RCL/inbox를 **같은 세대(generation)로 함께** 되돌려야 정합이 맞는다. `backup_set`도 이를
반영해 `evidence`/`rcl`/`inbox` 세 파일이 모두 존재하지 않으면 거부한다
(`backup_set.py:420-425`).

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
<N>`을 돌려두면, 마이그레이션이 잘못됐을 때 `restore-drill`로 **마이그레이션 이전 세대 전체**
(evidence+rcl+inbox, 전부 v1 시절 상태)를 별도 디렉터리에 복원할 수 있다. 위 실측에서
`gen1`을 복원한 뒤 RCL 파일의 `schema_version`이 다시 `1`로 돌아온 것이 그 증거다.

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

1. `restore-drill`로 마이그레이션 **직전 세대**(evidence+rcl+inbox 전체)를 별도 디렉터리에
   복원한다.
2. 복원된 디렉터리를 새 `--data-dir`로 삼아 **구버전 코드**를 그 위에서 기동한다(v1 상태로
   되돌아갔으므로 신버전 코드는 다시 BEHIND로 거부된다 — v1 코드가 필요하다).
3. 원래 `--data-dir`의 마이그레이션된 파일은 그대로 두거나(증거 보존) 폐기한다 — 이 판단은
   운영자 몫이다.

**있지도 않은 롤백을 있는 것처럼 적지 않는다.** 사전 백업이 유일한 안전망이다 — §4의 절차를
마이그레이션 전에 반드시 거쳐야 하는 이유가 이것이다.

## 6. 재현 스크립트 (실제로 실행한 것)

이 문서의 모든 출력은 아래 세 스크립트를 이 저장소의 워크트리(`kis_unified_sts-b2`)에서,
`PYTHONPATH`로 `tos/src`+`tos/runtime/src`+저장소 루트를 얹고(별도 `pip install -e` 없이),
메인 체크아웃의 `tos/.venv/bin/python`(의존성만 재사용, editable 설치 경로는 실제로 이
워크트리를 가리키는지 import 결과로 직접 확인함)으로 실행해 얻었다.

```bash
export PYTHONPATH=<worktree>/tos/src:<worktree>/tos/runtime/src:<worktree>
<main-repo>/tos/.venv/bin/python <script>.py
```

- **§2~§3 (`--help` + 양방향 거부 + 승격)**: `SqliteCommitLog` 생성자로 v1 파일을 직접 열어
  BEHIND를, `ensure_schema_current(..., schema_version=1)` 직접 호출로 AHEAD를 재현하고,
  `apply_migrations(path, "rcl")`로 실제 승격을 수행 —
  `tos/runtime/tests/operations/test_schema_ledger.py:368-433`과 같은 v1 baseline 구성 방식.
- **§2 (CLI 종단 `migrate`)**: `tos_runtime.compose.cli.main(["migrate", "--data-dir", ...,
  "--store", "rcl"])`을 실제로 호출 — `DurableSetPaths.from_data_dir` 경로 파생까지 포함한
  진짜 서브커맨드 디스패치.
- **§4 (백업/복원)**: `SqliteEvidenceStore`/`SqliteEventInbox`로 evidence/inbox를 만들고 RCL은
  v1 baseline으로 직접 구성한 뒤 `backup_set(paths, backup_dir, generation=1)` →
  `apply_migrations(paths.rcl, "rcl")` → `restore_set(backup_dir / "gen1.set.manifest.json",
  restore_dest, key_provider=...)`을 실제로 호출.

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
