# TOS paper 런북 — 남은 부록 (절 번호는 운영 런북과 같다)

- 운영 절차는 [`tos-paper-boot.md`](tos-paper-boot.md) 다. 이 파일은 **다른 문서·코드·설정이
  절 번호로 가리키는 조각들**만 남긴 부록이다.
- 2026-11-20 에 2026-09~10 의 실측·수용·드라이런 서사 약 2,000 줄을 지웠다. 남긴 것은
  §1 · §4 · §4-A · §4-B · §5 ④⑤ · §7.2 · §7.9-leaf · §7.10 뿐이고, 그 안에서도 §7.10 은
  결론만 남겼다. 지운 내용은 git 이력에 그대로 있다:
  `git log --diff-filter=D -- docs/runbooks/`.
- 날짜가 박힌 문장은 **그 날의 기록**이다. 오늘의 상태로 읽지 말 것.
- 여기서 인용하는 계획 문서 중 다수는 2026-11-14 에 은퇴했다 — git 이력에 있다
  (`git log --diff-filter=D -- docs/plans/`).

---

## 1. 준비 — 커스터디 루트 (호스트 로컬 · 비커밋)

`run` 은 증거 저장소 서명 키를 커스터디에서 읽는다. 없으면 부팅 전에 거부한다:

```text
run: refused — compose_paper_runtime raised KeyContinuityRefused: SqliteEvidenceStore:
key generation continuity refused (HISTORY_UNVERIFIABLE) ... : no key generation files
present under the custody root — nothing to sign or verify with
```

커스터디는 **자격증명** 계층이라 렌더 스크립트의 소관이 아니다(계좌 좌표는 커스터디
대상이 아니다 — review F2). 형식은 `tos/runtime/config/custody.manifest.example.yaml`,
키 파일 관례는 `tos_runtime/custody/key_provider.py`(`evidence.key.<generation>`).

```bash
CUSTODY=~/.local/state/tos/paper-custody          # 저장소 밖 · 호스트 로컬
LABEL=paper                                        # §5 ② 참고 — 부팅 라벨과 반드시 같아야 한다
mkdir -p "$CUSTODY/approvals"
cat > "$CUSTODY/custody.manifest.yaml" <<YAML
environment_label: "$LABEL"
scopes:
  read.principal: {file: read.principal, principal: read-principal-v1, expected_sha256: null}
  evidence.key:   {file: evidence.key,   principal: evidence-key-v1,   expected_sha256: null}
  replay.params:  {file: replay.params,  principal: replay-params-v1,  expected_sha256: null}
YAML
for f in read.principal evidence.key replay.params evidence.key.1; do
  head -c 32 /dev/urandom > "$CUSTODY/$f"; chmod 600 "$CUSTODY/$f"
done
chmod 700 "$CUSTODY"
```

- `environment_label` 은 부팅 인자와 **바이트 일치**해야 한다(`FileCustody` 가 부팅 시점에
  거부한다). 파일 모드는 정확히 `0600`, 소유자는 실행 uid.
- 이 디렉터리는 절대 커밋하지 않는다.


## 4. 정지와 확인

- 정지: `SIGTERM`(또는 `SIGINT`). 정상 종료는 stdout 에 `run: stopped (signal received).`
  를 찍고 **종료코드 0** 이다.
- 틱 소비 확인은 로그가 아니라 **지속 저장소**로 한다 — `run_forever` 는 패스마다 아무것도
  기록하지 않고(`marketfeed/scheduler.py` `run_forever`), TICKED 가 아닌 패스는 행을 남기지
  않는다:

```bash
sqlite3 "$DATA/marketfeed.sqlite3" 'SELECT COUNT(*) FROM snapshots;'
sqlite3 "$DATA/evidence.sqlite3"   'SELECT COUNT(*) FROM entries;'
```

`snapshots` 가 0 이면 틱이 소비되지 않은 것이다. 이유는 §5 ④ 를 본다.

**시각이 도는지**는 `TIME_HEALTH_SNAPSHOT` 행 수로 본다. `run` 은 세션이 열려 있으면 **매 패스**,
닫혀 있으면 `marketfeed.yaml::time_evaluate_closed_interval_ms`(paper 60000)마다 시간 건강을
**평가**한다(`marketfeed/time_pacer.py`) — 그 평가 주기는 그대로다. 다만 **증거 행은 평가마다
쓰지 않는다**(2026-11-13 이후): 판정 내용이 바뀔 때 즉시, 그 밖에는
`time.yaml::time_health_snapshot_heartbeat_ms`(paper **55000**)마다 한 행이다
(`tos_runtime/time/service.py` 모듈 docstring).

```bash
sqlite3 "$DATA/evidence.sqlite3" "SELECT COUNT(*) FROM entries WHERE kind='TIME_HEALTH_SNAPSHOT';"
```

**기대치는 열림·닫힘 모두 ≥ 1 행/분** 이다. 하트비트 55 s 가 닫힌 세션의 평가 주기 60 s 보다
**짧기 때문에** 닫힘에서는 평가마다 한 행(=1 행/분)이고, 열림에서는 55 s 마다 한 행이다.
두 값이 같으면(둘 다 60000) 하트비트가 한 번씩 빗나가 건강한 세션에도 약 120 초 구멍이
생기므로, 그 부등식은 `tests/compose/test_deploy_approved_values.py` 가 고정한다.

따라서 **2분 넘게 돌렸는데 전혀 늘지 않으면** §5 ④ 의 「평가가 멈춘」 결함 형태다 — 이 문턱은
위 부등식 덕분에 이제 거짓 양성이 없다(건강한 세션은 2분 안에 반드시 1행 이상 늘린다).
반대로 **분당 수백 행이면** 판정이 계속 흔들리고 있다는 뜻이니(열림/닫힘 플래핑, 참조 원천
단속, 앵커 거절) 그 행들의 `health_state` 를 본다.

⚠ **이 수를 「패스가 도는지」로 읽으면 안 된다.** 틱 소비는 위의 `marketfeed.sqlite3::snapshots`
(또는 `EVENT_CONSUMED`)로 본다. 2026-11-13 이전의 「패스마다 1행 · `poll_interval_ms: 400`
기준 ≈ 2.4 행/초 · 장중 7 h ≈ 61 k 행」(실측: 2026-09-27 계획 §7.3, 216 행 2.39/s · 220 행
2.43/s)은 **그 시점의 사실**이고, 아래 세션 표의 옛 행 수도 그 규칙으로 읽는다.

## 4-A. 스키마 마이그레이션 — 증거 저장소 v1 → v2 (`entries_kind_seq`)

> **⚠ 2026-10-03 운영자 결정으로 이 절의 전제가 날짜를 갖게 됐다 — §7 을 먼저 본다.**
> 상주 data dir 은 **부모** `~/.local/state/tos/paper-data` 와 그 밑의 **계약월 잎**
> `<종목>` 둘이다(2026-10-04 · §7.2). 부모는 2026-10-06 첫 기동 때 **래퍼가** 만들고 스토어를
> 담지 않으며, 잎은 **그 잎의 첫 세션 genesis 가** 만든다(§7.6). 그러므로 그날 **이후**로는
> 아래 「상주 paper data dir 이 없다」가 더 이상 참이 아니지만, **어느 쪽에도 §4-A 가 적용되는
> 것은 아니다** — 잎은 genesis 가 곧장 v2 를 만들고, 부모에는 스토어가 없다. 그 전에 부모나
> 잎에 `migrate` 를 겨누면 **빈 스토어 넷이 새로 생긴다**(아래 ⛔ 와 같은 사고 — 부모에
> 생기면 콜드 백업의 잎 열거 밖이라 백업도 안 된다, §7.6 ⛔).
>
> **적용 범위 — 이 호스트에는 상주 paper data dir 이 없다 (2026-10-02 실측).** 위 §3 이
> 예시로 쓰는 `~/.local/state/tos/paper-data` 는 **존재하지 않고**, 렌더된 설정
> (`~/.config/tos/paper-config`)에는 data dir 키가 **아예 없다** — 그 경로는 `run --data-dir`
> 인자일 뿐이라 설정에서 읽어 낼 것이 없다. `RENDERED.json` 에도 **data dir 키가 없다** —
> 거기 있는 키는 `account_fingerprint` · `activation_check` · `direction` · `instrument` ·
> `journal_as_of_ms` · `journal_path` · `note` · `policy_digests` · `rendered_at_kst` ·
> `rendered_keys` · `source_dir` · `source_revision` 이다. ⚠ 그중 `journal_path` 와
> `source_dir` 는 **경로**지만 둘 다 상태 루트가 아니다(각각 렌더된 부팅증명 저널과 설정
> 원본 디렉터리다) — data dir 로 오인하지 말 것.
> 디스크에 실재하는 durable set 은 2026-09-27/28 부팅증명 캠페인이 만든 1회성 디렉터리
> (`~/.local/state/tos/{realclock,t3}-*/data`)뿐이고, 그 뒤로 부팅된 적이 없다.
> **새 `run` 은 genesis 로 곧장 v2 증거 저장소를 만든다.** 그러므로 이 절은 「새 배포」의
> 절차가 아니라 **예전 corpus 를 지금 코드로 다시 부팅할 때**의 절차다. 대상 디렉터리를
> 짐작하지 말 것 — 어느 corpus 를 올릴지는 운영자가 이름으로 지정한다.

증거 성장 계획(`docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md` §2 A2) 이후
`EVIDENCE_SCHEMA_VERSION` 은 **2** 다. **이 커밋 이전에 만들어진 data dir 은 부팅이 거부된다** —
자동 적용은 없다(`operations/schema_ledger` 의 「부팅 시 자동 적용 0」):

```
evidence: on-disk schema user_version=1 is BEHIND this code's schema_version=2 — run the
operator `migrate` CLI ... before booting; boot never auto-applies a migration
```

순서는 **반드시** (0) `backup-set` → (1) 구 코드 프로세스 전부 정지 → (2) `migrate` →
(3) 신 코드 기동이다. `migrate` 를 먼저 돌리면 아직 살아 있는 v1 프로세스가 다음 open 에서
거부된다.

**(0) 먼저 백업 세대를 뜬다.** RCL v2 와 달리 이 마이그레이션의 롤백에는 백업 복원이
**필요 없다**(아래 「롤백」 — 인덱스는 보조 구조다). 그래도 세대를 먼저 뜨는 이유는 롤백
수단이어서가 아니라, 되돌리기 어려운 경로를 건드리기 전의 일반 배포 위생이기 때문이다 —
선례와 절차는 `docs/runbooks/tos-rcl-schema-migration.md` §4 다. `--archive-dir` 을 주면
압축본을 쓰고 **되읽어 검증**한다(`operations/backup_archive.verify_archive` — 계획 §2 A3).
`backup-set` 도 런타임이 정지해 있어야 한다.

⛔ **`migrate` 를 겨누기 전에 네 파일이 「이미」 있는지 확인한다 — 이것이 전제다.**
`apply_migrations` 는 **존재 검사를 하지 않는다**: 바로 `sqlite3.connect(str(path))` 를
부르므로 **없는 파일은 만들어진다**(`operations/schema_migrations.py`). 그래서 빈 디렉터리를
가리키면 조용히 스토어 넷이 새로 생기고 **종료코드 0** 으로 끝난다. 실측(2026-10-02, 빈
디렉터리):

```
migrate: evidence at <EMPTYDIR>/evidence.sqlite3 — applied v0 -> v2 (v1, v2)
migrate: rcl at <EMPTYDIR>/rcl.sqlite3 — applied v0 -> v2 (v1, v2)
migrate: inbox at <EMPTYDIR>/inbox.sqlite3 — applied v0 -> v1 (v1)
migrate: marketfeed at <EMPTYDIR>/marketfeed.sqlite3 — applied v0 -> v1 (v1)
```

첫 줄은 이 절이 **「대장 이전 파일」의 서명**이라고 설명하는 바로 그 줄이다. 즉 **아무것도
없는 곳에 만든 빈 스토어가 「마이그레이션된 예전 corpus」처럼 보인다** — 키도 세그먼트도
증거도 없이. 그래서 대상은 §3 의 `$DATA`(새 부팅용, 비어 있을 수 있다)가 **아니라**
운영자가 이름으로 지정한 **기존 corpus** 이고, 전제 검사를 먼저 돌린다:

```bash
# 운영자가 이름으로 지정한다 — 짐작하지 않는다 (위 「적용 범위」)
CORPUS=/home/deploy/.local/state/tos/<operator-named-run>/data

missing=""
for f in evidence rcl inbox marketfeed; do
  [ -s "$CORPUS/$f.sqlite3" ] || missing="$missing $f"
done
if [ -n "$missing" ]; then
  echo "ABORT: $CORPUS 에 없는 스토어:$missing — migrate 를 돌리지 말 것" >&2
else
  PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python -c \
    'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
    migrate --data-dir "$CORPUS" --store evidence
fi
# v1 파일을 올릴 때:
#   migrate: evidence at .../evidence.sqlite3 — applied v1 -> v2 (v2)
# 이미 v2 인 파일에 다시 돌렸을 때:
#   migrate: evidence at .../evidence.sqlite3 — already at v2, nothing to do
```

§4-A 안의 확인·롤백 명령은 **전부 같은 `$CORPUS`** 를 가리킨다(읽기 전용 관용구는
§4-A-1). §3 의 `$DATA` 는 여기서 쓰지 않는다.

⚠ 이 줄은 예전에 `"is current"` 였다. 리뷰 L3 이후 `migrate` 는 **서로 다른 세 결과**를
구분해 출력한다 — `compose/cli.py::_migrate_report`. 아래 「롤포워드」의 목록은 **`evidence`
(목표 v2) 가 낼 수 있는 줄의 전부**이지, 명령 전체가 낼 수 있는 줄의 전부가 아니다 —
`--store` 를 생략하면 스토어마다 **목표 버전이 달라서** 같은 템플릿의 숫자가 바뀐다
(`inbox`·`marketfeed` 는 목표가 v1 이다). 스토어별 실측 출력은 §4-A-1 에 있다.
**그러므로 그 일곱 줄을 리터럴로 비교하는 점검을 쓰지 말 것** — 템플릿으로 읽는다.

**검증은 세 가지를 모두 본다.** 인덱스 이름 하나만 보는 것으로는 부족하다 —
`user_version` 이 안 올라갔으면 다음 부팅이 거부되고, 대장 행이 없으면 「언제 적용됐나」가
남지 않는다:

```bash
sqlite3 "$CORPUS/evidence.sqlite3" "PRAGMA user_version;"
# 2
sqlite3 "$CORPUS/evidence.sqlite3" "SELECT version, applied_by FROM schema_ledger ORDER BY version;"
# 1|CREATED   (또는 1|MIGRATE — 대장 이전 파일을 올린 경우)
# 2|MIGRATE
sqlite3 "$CORPUS/evidence.sqlite3" "SELECT type, name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name;"
# index|entries_kind_seq
# table|entries
# table|outbox
# table|schema_ledger
# trigger|entries_no_delete
# trigger|entries_no_update
# trigger|schema_ledger_no_delete
# trigger|schema_ledger_no_update
```

세 번째 목록은 **genesis 로 만들어진 v2 파일과 글자 그대로 같아야 한다**. 같다는 것이
테스트로 고정돼 있다(`test_a_migrated_file_converges_on_the_genesis_schema`). ⚠ 2026-10-02
이전의 `migrate` 는 `schema_ledger` 의 append-only 트리거 **둘을 만들지 않았다** — 대장
이전 파일을 `migrate` 로 올렸다면 그 파일의 대장은 지금도 UPDATE·DELETE 가 가능하다.
위 목록에 `schema_ledger_no_*` 가 없으면 `migrate` 를 한 번 더 돌린다(복구 패스가 다시
만들고, 무엇을 만들었는지 출력한다).

v2 가 더하는 것은 **인덱스 하나뿐**이다. 행 바이트·`entry_digest`·`chain_digest` 는 움직이지
않고 체인 검증 결과도 그대로다(`tests/operations/test_schema_ledger.py
::test_evidence_v1_promotes_to_v2_without_moving_a_single_row_byte`).

**롤백.** 인덱스는 저장 표현이 아니라 보조 구조이므로 되돌리는 데 백업 복원이 필요 없다.
지원되는 절차는 **하나뿐이고, 두 문장을 반드시 함께** 실행한다:

```bash
sqlite3 "$CORPUS/evidence.sqlite3" "DROP INDEX IF EXISTS entries_kind_seq; PRAGMA user_version = 1;"
```

⚠ **`user_version` 을 2 로 둔 채 인덱스만 지우는 것은 롤백이 아니다.** 그 상태는 v2 코드가
멀쩡히 부팅하면서 모든 by-kind 읽기를 조용히 전체 스캔으로 되돌린다. 그리고 아무것도 못
잡는다 — `compute_schema_shape_digest` 는 `PRAGMA table_info` 를 읽고, 그것은 인덱스를 보지
못한다. 실수로 그 상태가 됐다면 아래 롤포워드가 복구한다.

**롤포워드(= 복구).** 손으로 `CREATE INDEX` 를 치지 않는다. 항상 `migrate` 다:

```bash
PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python -c \
  'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
  migrate --data-dir "$CORPUS" --store evidence
```

`migrate` 는 두 반쪽 상태를 모두 복구한다 — `user_version=1` 이면 v2 를 다시 적용하고,
이미 2 인데 인덱스만 없으면 **복구 패스**가 다시 만든다. 출력이 무엇을 했는지 말해 준다:

```
migrate: evidence at ... — already at v2, nothing to do
migrate: evidence at ... — applied v1 -> v2 (v2)
migrate: evidence at ... — applied v0 -> v2 (v1, v2)
migrate: evidence at ... — applied v1 -> v2 (v2); ledger row(s) already present for v2, not re-recorded (append-only)
migrate: evidence at ... — already at v2, but REBUILT missing entries_kind_seq — the file was running without it
migrate: evidence at ... — already at v2, but REBUILT missing schema_ledger_no_update, schema_ledger_no_delete — the file was running without it
migrate: evidence at ... — applied v1 -> v2 (v2); rebuilt schema_ledger_no_update, schema_ledger_no_delete
```

**일곱** 형태 전부를 실제로 실행해서 받은 문자열이다(리뷰 MEDIUM-2: 이 목록이 「전부」라고 적혀
있었는데 **대장 이전 파일이 실제로 내는 줄이 빠져 있었다**). 3번째가 그 줄이다 — 대장 이전
data dir 은 v0 에서 출발하므로 `applied v0 -> v2 (v1, v2)` 다. 마지막 줄은 버전도 뒤처지고
대장 트리거도 없는 파일로, 적용과 복구가 **한 줄에 같이** 나온다.

⚠ **위 일곱 줄은 전부 `evidence`(목표 v2) 로 적혀 있다 — 「nothing to do」 줄의 버전 숫자는
스토어마다 다르다.** `--store` 를 생략하면 `STORE_MIGRATIONS` 에 등록된 네 스토어가 모두
돌고, `inbox` 와 `marketfeed` 는 **등록된 최신이 v1** 이라 `already at v1, nothing to do` 를
낸다(`rcl` 은 v2). 새 형태가 아니라 첫 번째 템플릿의 **버전 자리**가 다른 것뿐이지만,
**`"already at v2"` 를 리터럴로 grep 하는 스크립트·점검은 이 줄을 놓친다.** 네 스토어를 한
번에 돌린 실측 출력은 아래 §4-A-1 에 있다.

⚠ **「rebuilt …」 는 대장이 «이미 있었는데» 트리거가 없었을 때만 나온다.** `migrate` 가
대장을 처음 만드는 경우(신규 배포 · 대장 이전 파일)는 복구가 아니므로 **적히지 않는다** —
리뷰 MEDIUM-1 전에는 여기서도 「rebuilt」 를 찍어서, 멀쩡한 제네시스에도 경고가 울렸다.
그래서 이 줄을 보면 **실제로 무방비였던 파일**이라고 읽어도 된다.

2026-10-02 에 추가된 복구의 배경: `migrate` 가 대장을 직접 만들어야 했던 파일은 테이블만
받고 append-only 트리거 둘을 받지 못했고, 그 상태는 스스로 낫지 않았다 —
`open_or_create_schema` 의 정상 부팅 빠른 경로가 「버전 일치 + 대장 테이블 존재」에서
DDL 을 돌리기 전에 반환하기 때문이다. 지금은 양쪽 경로가 `create_schema_ledger_objects`
하나를 지나므로 genesis 파일과 마이그레이션 파일의 `sqlite_master` 가 같다(evidence ·
inbox · marketfeed. `rcl` 은 v2 가 `ALTER TABLE ADD COLUMN` 이라 **표 본문 텍스트**만
sqlite 내부 공백이 다르고 `PRAGMA table_info` 는 동일 — 테스트가 그렇게 고정한다).

`schema_ledger` 는 append-only 이고 `version` 이 PK 라서 롤백 뒤에도 v2 행이 남는다. 그래서
재적용은 대장 행을 다시 쓰지 않는다(대장은 「언제 처음 적용됐나」의 기록이지 실행 횟수가
아니다). 부팅은 이 인덱스를 **절대 만들지 않는다** — 생성은 신규 파일의 genesis 와 `migrate`
뿐이라, 위 롤백이 다음 부팅에 조용히 덮이지 않는다.

## 4-B. 장 마감 뒤 압축 백업

계획 §2 A3. **아무것도 지우지 않는다** — 라이브 파일도, 비압축 백업 트리도 읽기만 한다.
디스크는 줄지 않고, 검증된 콜드 사본이 쌓인다(트랙 B 가 언젠가 지울 때의 전제,
ADR-002-016 §17).

전제: 런타임이 **정지**해 있을 것(`backup-set` 은 다른 프로세스가 연 핸들을 감지하지 못한다).
`--archive-dir` 은 **옵트인**이다. 생략하면 `backup-set` 은 종전과 완전히 동일하게 동작한다.

```bash
COLD=~/.local/state/tos/paper-cold          # 보관 경로 = 인자. 하드코딩된 기본값 없음
GEN=1                                       # 기존 최고 세대보다 커야 한다 (backup_set 이 강제)
PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python -c \
  'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
  backup-set --data-dir "$DATA" --dest ~/.local/state/tos/paper-backups \
             --generation "$GEN" \
             --archive-dir "$COLD" \
             --verify-dir "$(mktemp -du ~/.local/state/tos/verify-XXXXXX)" \
             --custody-root "$CUSTODY"
```

출력(둘 다 나와야 성공이다):

```
backup-set: wrote gen1 manifest under /home/.../paper-backups
backup-set: archived gen1 to /home/.../paper-cold/gen1.set.tar.xz (7449088 -> 512000 bytes),
            read back and verified: 5 file digest(s) + evidence chain
```

압축본은 **쓰고 나서 반드시 되읽어 검증한다**: 압축 해제 → 매니페스트 동일성 → 파일별
digest 대조 → `verify_or_raise` 로 증거 체인 재검증. 하나라도 실패하면 **종료코드 1** 과
stderr 의 거부 사유로 끝나고, 그때도 **비압축 스냅샷은 그대로 남는다**. 「압축했지만 검증
안 된」 상태는 만들어지지 않는다.

- `--verify-dir` 은 **존재하지 않는** 경로여야 한다(이미 있는 디렉터리는 빠진 멤버를 오래된
  파일로 가려 검증을 통과시킬 수 있다). 검증이 끝나면 지워도 된다.
- 같은 세대의 `.tar.xz` 가 이미 있으면 덮어쓰지 않고 거부한다.
- 보관 중인 콜드 사본을 나중에 다시 검사할 때는 새 압축 없이
  `tos_runtime.operations.backup_archive.verify_archive(archive, manifest, verify_dir,
  key_provider=...)` 를 쓴다.
- 압축률은 `--xz-preset`(기본 6). 계획 §1 실측 기준 증거 파일 ≈ 14 ×.

**무인 반복은 `cold-backup` 으로 옮겨졌다 (2026-10-02, 계획 §7.1.18).** 위 `backup-set
--archive-dir` 는 **대화형 1회성** 경로로 그대로 남는다(세대를 손으로 올린다). 장 마감 뒤
반복 실행 — 설정 기반 보관 경로 · 자동 세대 · 용량 바닥 · JSON 보고서 · KST cron 한 줄 —
은 `docs/runbooks/tos-evidence-cold-backup.md` 를 따른다. 데몬은 여전히 없다.

## 5. 실측 차단의 이력 — 2026-09-24 현재 (이름으로)

> ①②③ 은 전부 해소돼 2026-11-20 에 지웠다(git 이력). 남은 ④⑤ 는 다른 문서가 번호로
> 가리키는 항목이고, ⑤ 는 지금도 유효한 **알려진 한계**다.

### ④ 틱은 **세션 게이트**에 막힌다 — 만기 공백은 해소됨(#799)

`run` 은 **부팅하고 `run_forever` 에 들어가 SIGTERM 에 정상 종료(코드 0)** 한다
(① 해소 이후 실측). 틱이 소비되는지는 그 시점의 **세션**이 정한다:

```text
session_context: ... trading_calendar_version='krx-2026.09.1' phase='CLOSED' is_open=False ...
TICK OUTCOME: SKIPPED_SESSION_CLOSED
```

- `decide_tick` 1순위 게이트(`marketfeed/scheduler.py` — 세션이 닫혀 있으면
  `SKIPPED_SESSION_CLOSED`).
- `config/tos_runtime/paper/calendar.yaml` — `krx-index-futures` 는 CONTINUOUS
  **08:45–15:45 KST MON–FRI**, 휴장일 목록은 같은 파일의 `holidays:`.
- ✅ **만기 공백은 해소됐다(운영자 2026-09-24 · PR #799).** `futures_expiry`
  `months` 가 분기 `[3,6,9,12]` → **매월 `[1..12]`** 로 바뀌면서(mini 는 월물),
  「둘째 목요일 이후 분기 내내 `EXPIRED`」가 사라졌다. `calendar_version` 은
  `krx-2026.09.1` 이고 `time.yaml::trading_calendar_version` 과 같아야 한다.
  실측(10:00 KST, 이 배포 파일 그대로): 2026-09-11 · 09-28 · 09-30 · 10-01 **전부
  CONTINUOUS**(이전 규칙에서는 전부 EXPIRED 였다).
- ⚠ **그래도 휴장일에는 창 자체가 없다.** 예: 2026-09-24 는 추석 연휴
  (`calendar.yaml` `holidays:`)라 phase 가 **`CLOSED`** 이고, 그날은 시각과 무관하게
  틱이 소비되지 않는다. `boundary_value` 가 다음 개장 시각을 가리킨다.
- 개장일 장중에 렌더·부팅하면 `TICKED` 되고 `marketfeed.sqlite3` 에 스냅샷이 남는다.
  장 밖에서 확인하려면 아래 진단으로 개장 시각을 주입한다.

세션 게이트만 따로 확인하려면 `run` 이 아니라 합성 루트를 직접 부른다(진단):

```bash
PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python - <<'PY'
from pathlib import Path
from tos_runtime.compose._construction_config import load_construction_config
from tos_runtime.compose.root import compose_paper_runtime
cfg = Path.home() / ".config/tos/paper-config"
rt = compose_paper_runtime(cfg, Path("/tmp/tos-probe/data"), Path("/tmp/tos-probe/custody"),
                           "paper", construction=load_construction_config(cfg / "construction.yaml"))
print(rt.session_facts.session_context("krx-index-futures"))
print(rt.marketfeed.tick_once().outcome.value)
PY
```

개장 시각을 주입해 확인하려면 위 `compose_paper_runtime(...)` 에
`wall_clock=FixedWallClockReference(<개장 시각의 unix ms>)` 를 넘긴다
(`tos_runtime.calendar.ports.FixedWallClockReference` · `compose/root.py` 의 `wall_clock`
인자). **주입되는 것은 세션 판정용 시계 하나뿐**이고, 신선도 검사가 쓰는 시계는 실
시스템 시계 그대로다 — 그래서 저널은 여전히 **부팅 직전에 렌더**해야 한다.

⚠ **정정 (2026-09-26, 계획 `docs/plans/2026-09-26-tos-periodic-time-eval-and-witness-wiring-plan.md`)**:
위 「TICKED · `snapshots` 1」 실측은 **틱 하나**만 본 것이고, 세션 시계를 주입한 진단이라 결함을 가렸다.
당시 `run` 은 시간 평가를 부팅 때 두 번만 해서 `wall_clock_now()` 가 부팅 시각에 멈췄고, 두 번째 패스부터
`SKIPPED_INTERVAL` 이었다 — **paper 는 첫 틱 하나만 소비했다.** 닫힌 시각에 부팅하면 세션도 영영 열리지 않았다.
이제 `run_forever` 가 패스마다 평가한다(§4 의 확인 쿼리). 재측정: 같은 진단(개장 시각 주입) + 실 `sleep` 8 패스 +
중간에 더 새 관측 추가 → **스냅샷 2**, 평가를 떼면 **1**. 실 `run` 닫힌 세션 150 s → 평가 +0.1 · +60.2 · +120.2 s.

⚠ **렌더가 만든 부팅 증명 관측은 부팅 시점에 이미 STALE 이다 — 고칠 수 없고, 그래서 그것은
「TICKED 증명」이지 「결정 증명」이 아니다 (2026-09-27, 계획
`docs/plans/2026-09-27-tos-poll-interval-freshness-budget-plan.md` §3).** 렌더는 저널 첫 줄의
`as_of` 를 렌더 시각 − 1000 ms 로 찍는데(`scripts/tos/render_paper_config.py` `_JOURNAL_AGE_MS`),
신선도 예산은 `MAX_time_conservative_freshness_age_ms`(1000) − Σ지연 한도(200) = **800 ms** 다.
렌더와 부팅 사이가 0 초라 해도 1000 > 800 이므로 그 한 건은 언제나 `DECISION_WITHHELD`
(`TIME_NOT_ADMITTED | freshness verdict is STALE`)로 끝난다. 즉 이 관측이 증명하는 것은 **틱이
소비되기까지의 체인**(세션 게이트 → 인입 → 스냅샷 → 엔진)이지, 결정이 났다는 것이 아니다.
실측 2회(계획 §7.3) 모두 STALE 은 정확히 이 첫 관측 1건뿐이었고, 그 뒤 수집기가 넣은 관측
17·18건은 **전건 신선**했다. 결정까지 보려면 부팅 후 새 관측을 저널에 덧붙인다(원자적 전체 파일
교체 — `marketfeed/journal.py`).

⚠ **패스 순서가 바뀌었다 (2026-09-27 · 이슈 #809 · 계획
`docs/plans/2026-09-27-tos-freshness-read-order-plan.md`)**: 한 패스는 이제 **저널 판독 →
시간 평가 → 결정** 순으로 돈다(전에는 평가가 먼저였다). 그래서 평가와 판독 사이에 덧붙인
관측이 «미래 시각» 으로 보여 `CONFLICTED` 로 버려지던 일이 사라진다 — 평가 뒤 80 ms 정지를
주입한 리허설에서 수정 전 CONFLICTED **15/162**, 수정 후 **0/166**(계획 §7.3). 시간 평가가
실패한 패스는 `SKIPPED_TIME_NOT_EVALUATED` 이고 **관측을 소비하지 않는다** — 다음 패스가
같은 줄을 다시 읽는다.

✅ **첫 장중 실시계 실측 (2026-09-28 월, 개장일)** — 이 런북 §2–§4 그대로다.
- 조건: 렌더 → 실 `run`(시계 주입 없음) 15 분 → SIGTERM. 별도 프로세스 수집기가 5 s 마다 관측 1 건을 원자적으로
  덧붙였다(`as_of = 추가 시각 − 200 ms`). 네 회 모두 종료코드 0 · 회당 덧붙임 180 · 소비 180(부팅 증명 1 +
  덧붙인 관측 179 — 차이 1 건은 정지 직전의 미소비로 본다).
- 실주문 0 · 네트워크 호출 0. 산출물: 호스트 `~/.local/state/tos/realclock-20260928T*/report.json`.

| 시각 (KST) | 코드 | 방향 | STALE / 소비 | CONFLICTED | NoAction · Proposal | `TIME_HEALTH_SNAPSHOT` | data dir |
|---|---|---|---|---|---|---|---|
| 10:00 | `f6348b19` (poll 1000) | LONG | **66 / 180 (37 %)** | 0 | 58 · 56 | 881 (≈ 0.98 /s) | 4.4 MB |
| 10:20 | `f6348b19` (poll 1000) | SHORT | **76 / 180 (42 %)** | 0 | 54 · 50 | 886 | 4.5 MB |
| 10:40 | `4b1144d3` (#808, poll 400) | LONG | **1 / 180** | 0 | 90 · 89 | 2183 (≈ 2.4 /s) | 7.2 MB |
| 11:00 | `ac2efb0f` (#811, 판독 → 평가) | LONG | **1 / 180** | 0 | 90 · 89 | 2180 | 7.2 MB |

- #807 의 폴링/신선도 불일치가 **실시계에서도 그대로** 나타났다(주입 시계 리허설 39 % ↔ 실측 37–42 %). #808 뒤에는
  사라졌다.
- 수정 뒤 남은 STALE 1 건은 두 회 모두 **첫 번째로 처리된 이벤트** = 렌더 부팅 증명 관측이다(위 ⚠ — 고칠 수 없음).
  소비된 덧붙인 관측은 **179 / 179 신선**했다.
- **CONFLICTED 는 네 회 모두 0**(720 건). 수집기가 별도 프로세스이고 인위적 정지가 없을 때 #809 의 창은 드러나지
  않았다. #811 은 정지(GC·fsync)가 낄 때의 꼬리 위험을 닫은 것이다.
- Proposal 은 전부 `STAGE_DENIED | the venue / broker quantity constraint is incomplete` 다(venue `max_quantity`
  null — 의도된 fail-closed). LONG·SHORT 양쪽이 같은 사유로 멎는다.
- 증거량: poll 400 에서 data dir 이 15 분에 약 7.2 MB 쌓인다. 장중 7 h 로 환산하면 **약 200 MB/일**(5 s 관측 포함)이다.
  poll 1000 에서는 약 125 MB/일. 증거 퍼지 계획(별도, 미착수)의 입력이다.

### ⑤ 활성화 기록은 **방향을 결속하지 않는다** (알려진 한계)

LONG 렌더와 SHORT 렌더는 `print-policy-digests` 가 찍는 5종 digest 가 **전부 바이트
동일**하다 — `_runtime.construction.axes` 의 `DIRECTION` 과 `admitted_quantity_bases` 는
OCP 의 정본 covered content **밖**이기 때문이다(DR-0002 §2.3 이 digest 를 `policy_id`/
`policy_generation`/`policy_version` 에만 결속한다).

귀결: `safety_activation.yaml::members` 활성화는 「이 배포가 어느 방향으로 구성됐는지」를
**증명하지 않는다.** 이 배포에서 방향 일관성을 지키는 것은 (a) 렌더가 네 슬롯을 함께
바꾸는 것과 (b) `tos/runtime/tests/compose/test_deploy_approved_values.py` 의 방향 일관성
핀이지, digest 가 아니다. (review-797 LOW-6 · 이 PR 이 만든 문제가 아니라 `_runtime` 블록
규약의 선행 성질이다.)

### 7.2 좌표 규율 (환경 손잡이 표는 운영 런북)

**좌표 규율 (§2·§6 의 연장 — 이 절에도 그대로 적용된다).**
`render.log` 는 **계좌 지문**을 찍는다. §2 가 못박듯 그 지문은 마스킹이 아니라 상관자이고
**유출된 지문은 유출된 계좌번호로 취급한다.** 그러므로 **좌표를 담는 여섯 트리**
— `~/.config/tos/paper-config`(렌더 산출물) · `~/.local/state/tos/paper-custody`(자격증명) ·
`~/.local/state/tos/paper-sessions`(`render.log`) · `~/.local/state/tos/paper-logs`(래퍼 로그) ·
`~/.local/state/tos/paper-ops`(PID·백업 설정) · **`~/.local/state/tos/paper-data`(증거 — 잎
`<종목>` 까지 — 결정 행이 계좌번호를 평문으로 싣는다, §7.2-a)** — 는 전부 저장소 밖 **0700**(실측)이고, **`render.log` · 증거 행 · 질의 결과를 PR·계획 문서·텔레그램으로 옮겨
적지 않는다**(이 런북의 인용은 전부 지문·계좌가 없는 줄만 고른 것이다). `.env.mock` 은
`$MAIN` 의 것을 **절대경로로 넘긴다 — 워크트리로 복사하지 않는다**(§7.3 1). 텔레그램 토큰은
`$MAIN/.env` 의 두 줄만 `grep` 으로 읽고 로그에 내보내지 않는다.


#### 7.9-leaf ✅ 월물별 잎 — 드라이런 2026-10-04 18:20–18:23 KST (스크래치 부모)

운영자 결정 2026-10-04(§7.10 7 (c))의 배선 ⓐ 를 호스트에 적용한 뒤, **상주 부모
(`~/.local/state/tos/paper-data`)는 건드리지 않고** 스크래치 부모에서 세 번 부팅했다.
당시 출하본 둘(`~/.config/kis-probes/` · 700 · 비커밋 — 10-06 20:00 부터는 §7.9 머리의
`2c3284a4…`/`3ce14fb6…`; 변경은 projection 경로 인자뿐이라 아래 기록은 유효하다):

```text
tos-paper-session.sh  fd554b2a3c1496d26c70dcce414ae529fec81f89abc131e41f7b4046aa0ab763   (이전 판 백업 .bak.a898e6cb1f2f)
tos_paper_session.py  21b583bdb72b178d1b1f568df78fc4dd5cd788dce893a086e634cd726665fe11   (이전 판 백업 .bak.995ada06d795)
```

`a898e6cb` → `fd554b2a` 의 코드 변경은 `diff` 로 확인한 **넷**이다: ① `DATA` 가 `DATA_BASE`
(부모)가 되고 잎은 `DATA=$DATA_BASE/$INSTRUMENT` · ② 워크트리를 만든 뒤
`get_front_month_code(product="mini")` 를 **한 번** 불러 `INSTRUMENT_AUTO` 로 두고,
`TOS_PAPER_INSTRUMENT_OVERRIDE` 가 있으면 그것을 쓰되(경고 로그) `^A0[0-9]{4}$` 가 아니면
ABORT · ③ 드라이버 호출에 `--instrument "$INSTRUMENT"` · ④ 부모를 `umask 077` 로 만들고
기동·종료 때 `chmod 700`. 드라이버 `995ada06` → `21b583bd` 는 **둘**이다: `--instrument`
필수 인자를 렌더에 그대로 넘기고, 렌더가 적은 종목이 요청과 다르면 **부팅하지 않고**
`verdict: "instrument_mismatch"` · rc 1 로 끝낸다(그 보고서에만 `requested_instrument` 키가
실리고 **정상 보고서에는 그 키가 없다** — 10-04 세 보고서 실측 0건; `jq` 는 없는 키를 `null`
로 보여 주므로 그것을 「값이 null」로 읽지 말 것). 달력·digest·부팅증명·정지·보고 경로는 바뀌지
않았다.

| 부팅 | 호출 | 로그의 `instrument=` 줄 | 잎 | `genesis` | `baseline_evidence_seq` | 리플레이 | rc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BOOT1 | 자동 | `A05610 (auto=A05610)` | `base/A05610` | yes | −1 | `REPLAY_VERDICT_IDENTICAL: 1` | 0 |
| BOOT2 | `TOS_PAPER_INSTRUMENT_OVERRIDE=A05611` | `A05611 (auto=A05610)` + ⚠ 드라이런 경고 줄 | `base/A05611` | yes | −1 | `REPLAY_VERDICT_IDENTICAL: 1` | 0 |
| BOOT3 | 자동 (BOOT1 과 같은 잎) | `A05610 (auto=A05610)` | `base/A05610` | **no** | **18** | `REPLAY_VERDICT_IDENTICAL: 1` · `REPLAY_DIVERGED` 없음 | 0 |

셋 다 `boot proof: OK`(2.0 s · 2.0 s · 3.0 s) · `verdict: ok` · `stop_reason: deadline`
(`TOS_PAPER_MINUTES=1`) · `user_version=2` · 델타 19 · 18 · 19 행. **BOOT2 가 롤 날의
모양**이다 — 어제의 잎(`A05610`, 19 행)이 옆에 있는데도 새 잎은 genesis 로 뜬다. **BOOT3 은
같은 잎 재부팅**이고 어제의 19 행(seq 0–18) 위에서 리플레이가 IDENTICAL 이다 — 잎을 가르는
것이 같은 종목의 연속성을 깨지 않는다는 뜻이다. 트리 모드는 부모 700 · 잎 둘 700 · 스토어
파일(`-wal`/`-shm` 포함) 전부 600 이었고, 실행 뒤에도 `~/.local/state/tos/paper-data` 는
**없었다**.

⚠ 이 드라이런이 **재지 않은 것**: 실제 롤 — 어제의 잎에 실 hand-off 영수증이 있는 상태에서
새 종목으로 부팅하는 것 — 은 1 분짜리 세션에는 hand-off 가 없어 스크래치에서 만들 수 없다.
그 경우는 커밋된 테스트 `tos/runtime/tests/compose/test_contract_roll_replay.py` 가
픽스처로 hand-off 까지 만든 뒤 **같은 dir 은 `EngineReplayDiverged`, 자기 잎은 clean** 을
고정한다(ⓒ). 호스트의 첫 실제 롤은 2026-10-12 이고 그날 볼 것은 §7.8 1 의 ⚠ 문단이다.

아티팩트: 세션 디렉터리 `~/.local/state/tos/paper-sessions/2026-10-04-18{2005,2118,2230}-LONG/`
(700 · 파일 600 · `report.json` 셋) · 날짜 로그 `~/.local/state/tos/paper-logs/2026-10-04.log`
(**644** · 부모 700) 257 행부터 끝까지(`=== tos-paper-session start [SELFTEST] sha256=fd554b2a…`
머리 셋). 구동 스크립트와 출력은 이 레인의 스크래치라 **세션이 끝나면 사라진다** — 남는
증거는 그 둘이다. ⚠ **세션 디렉터리는 좌표 트리다**(§7.2): 세 `render.log` 마다 계좌 지문
줄이 하나씩 있다(개수만 셈 — 유출된 지문은 유출된 계좌번호). 이 절이 옮겨 적은 것은 그중
지문·계좌가 없는 줄(`instrument=` · `boot proof` · `report.json` 의 필드 이름)뿐이고, 날짜
로그에는 지문이 없다(실측). 재도출은 §7.2 규율대로 **그 디렉터리에서 직접** 읽는다.


### 7.10 결정과 남은 위험 (다른 문서가 번호로 가리키는 항목만)

> 2026-11-20 에 이 절의 측정 서사를 지우고 **결론과 아직 열린 위험**만 남겼다. 지워진
> 측정·반증 기록은 git 이력에 있다.

1. **✅ 관측 수집기 — 운영자 결정 2026-10-03: `on`, 5 s.** 끄면 하루치가 `TIME_HEALTH`
   하트비트뿐이고 **소비 → 결정 → 거부 체인이 한 번도 돌지 않는다.** 밴드가 합성이라는
   사실은 증거에 `source_id` 라벨로 남는다. ⚠ 그러므로 `TOS_PAPER_APPEND_EVERY_S` 는
   **결정된 값**이다 — 바꾸려면 이 줄을 먼저 고친다.
3. **✅ 방향 — 운영자 결정 2026-10-03: 상주는 `LONG` 단독. SHORT 부팅증명은 분기 1회
   손으로.** LONG/SHORT 를 한 data dir 에 섞는 경로는 설계에 없고, §5 ⑤ 때문에 섞인
   코퍼스는 나중에 digest 로 갈라낼 수 없다. SHORT 보완 실행은 **스크래치 data dir** 에
   한 세션이고 상주 잎에는 절대 섞지 않는다. cron 에 넣지 않는다.
   ⚠ **분기를 기다리지 않는 계기**: `construction.yaml::action_class`/`outbound_side` ·
   `order_construction_policy.yaml` 의 DIRECTION 축 · 전략 파일의 `direction` 중 하나라도
   바뀌면 **그 PR 에서** SHORT 를 한 번 돌린다. 기록이 없으면 「안 돌았다」로 읽는다.
5. **DST/시각 변경.** KST 는 DST 가 없고 cron 은 `CRON_TZ=Asia/Seoul` 이다.
6. **⛔ 코퍼스가 커널 리비전을 가로지른다 — 코드 핀 결정은 열려 있다.** 래퍼는 매일
   `origin/main` 에서 워크트리를 새로 만들므로 하루치마다 다른 커널 바이트가 같은
   append-only 코퍼스에 쓸 수 있다. digest 가드는 **같은 워크트리 안의** `release.yaml`
   과 대조하므로 이 변화를 보지 못한다.
   부팅은 예전 이벤트를 **그날의 배선**으로 다시 돌려 예전 영수증과 대조한다
   (`compose/_finalize_wiring.py`). 그러므로 **어제의 증거를 오늘의 코드로 재해석할 수
   없게 만드는 변경**은 전부 같은 모양으로 터진다 — 증상은 7 (c) 와 같다(부팅 OK · held ·
   틱 전부 `MARKETFEED_QUEUED_UNTIL_RECOVERY`).
   ✅ 그중 **종목 축**은 월물별 잎(7 (c))으로 닫혔다. ⚠ 나머지 축(전략 레지스트리 키 모양 ·
   스테이지 구성 · 정책 스코프 · 리플레이가 재해석하는 어떤 배선이든)은 **열려 있다**:
   커밋된 테스트도 종목 축만 고정한다. 그 자리들을 건드리는 PR 은 같은 PR 에서 상주 잎의
   **사본**으로 두 번 부팅을 돌리거나, 운영자가 새 잎으로 시작할 날을 정한다.
7. **✅ 종목 롤 — (c) 운영자 결정 2026-10-04: 계약월마다 durable set 을 가른다**
   (`~/.local/state/tos/paper-data/<종목>`).
   **왜.** 부팅 리플레이의 레지스트리는 `(account, instrument)` 로 키가 잡히므로
   (`tos/src/tos/engine/registry.py::_key_tuple`), 같은 data dir 에서 종목이 롤하면 예전
   영수증이 `REGISTRY_MISSING` → `INCONCLUSIVE` → `REPLAY_DIVERGED` 로 가고
   `EngineReplayDiverged` 가 뜬다(실측 2026-10-04). **되돌려도 안 풀린다** —
   `REPLAY_DIVERGED` 행은 예외보다 먼저 내구 저장되고 복구 배리어
   (`recovery/inputs.py::_replay_verdict_ok`)는 그 행이 0 일 것을 요구한다. 그 상태에서
   부팅은 rc 0 으로 「성공」이라고 말하면서 **틱을 하나도 처리하지 않는다**(held 런타임 —
   증상과 판별은 운영 런북 §7.8).
   잎을 가르면 롤하는 날은 그냥 genesis 부팅이 되므로 이 경로에 애초에 들어가지 않고
   **커널 바이트는 건드리지 않는다.** 기각된 셋: 리플레이 범위 축소(완결성 공백
   `ERI-INV-007`) · 지난 달 종목 존치(세 번째 롤부터 부족) · 이벤트마다 레지스트리
   재해석(커널 변경이 크다).
   **고정하는 테스트**: `tos/runtime/tests/compose/test_contract_roll_replay.py` — 같은
   dir 롤 = `EngineReplayDiverged`, 자기 잎 롤 = clean.
   ⛔ **인용 금지.** 결정 행의 `instrument_key` 는 종목과 **계좌번호**를 함께 담는다.
   §7.2 좌표 규율대로 증거 행을 PR·계획 문서·텔레그램에 옮겨 적지 않는다.
8. **⛔ 달력은 2027년에 대해 fail-open 이다.** `config/tos_runtime/*/calendar.yaml` 의
   `holidays` 에 2027 항목이 **0건**이므로, 2027-01-01 이후 **모든 평일이 거래일로
   판정된다** — 건너뛰는 쪽이 아니라 **부팅하는 쪽으로** 틀린다. 해결은 휴장 목록을 먼저
   채우는 것이고, 래퍼가 손댈 일이 아니다. (2026-12-31 KRX 연말 휴장은 2026-10-25 에
   목록에 들어갔다.)
