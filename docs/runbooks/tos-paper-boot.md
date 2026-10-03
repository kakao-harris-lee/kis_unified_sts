# TOS paper 첫 부팅 런북 — 렌더 → 부팅 → 정지 → 확인

- 대상: `tos_runtime` `run` 을 이 호스트의 배포 좌표로 부팅한다.
- 설계: `docs/plans/2026-09-23-tos-paper-coordinates-and-first-boot-design.md`
  (운영자 결정 1·3 · 운영자 선택 (가), 2026-09-23) · 상위 계획
  `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` §7.8.
- 실측 시점: 2026-09-23 (1차) · 2026-09-24 재측정/정정(review-797 조치) ·
  2026-09-24 main `5d618f1c` 병합 후 재측정(#799 캘린더 만기 롤 반영),
  브랜치 `feat/tos-paper-render-and-first-boot` · **2026-09-24 시드 고정 없이 전 구간
  재측정**(정본 집합 순서 복원, 브랜치 `fix/tos-canonical-set-order`).

> ## ✅ 이 런북은 이제 끝까지 간다 (2026-09-24, 시드 고정 없이 실측)
>
> §5 가 실측 상태를 이름으로 적는다. **①②③ 전부 닫혔다.** ①(정본 digest 가 프로세스마다
> 다르다)은 커널 수정으로 해소됐다 —
> `docs/plans/2026-09-24-tos-canonical-set-order-plan.md`, 브랜치
> `fix/tos-canonical-set-order`. **`PYTHONHASHSEED` 를 맞추지 않은 채** §2 의 렌더가
> 통과하고(`activation: ACTIVATED 5 (re-derived in a fresh process)`), §3 의 `run` 이
> 부팅해 SIGTERM 에 종료코드 0 으로 멎는다 — LONG·SHORT 양쪽.
> 남은 것은 **틱이 개장일 장중에만 소비된다**는 평범한 달력 사실뿐이다(§5 ④).
> 만기 공백은 #799 로 해소됐다.

## 0. 이 배포가 무엇이고 무엇이 아닌가

- 채택 스코프는 `SYNTHETIC_FUTURES_ORDER` 다(`config/tos_runtime/paper/broker_scopes.yaml`).
  **브로커에 도달하지 않는다.** 실주문 0 · 외부 호출 0 · `nonlive_broker_consuming.admitted`
  는 `false` 그대로다.
- 전략·construction·marketfeed·critical-input 파일은 **부팅 증명 픽스처**이지 거래 전략이
  아니다. 각 파일 머리에 그렇게 적혀 있다. 커밋된 방향은 LONG 하나뿐이고, SHORT 는
  렌더 플래그로 만든다 — **대칭을 좁히지 않았다는 증거로 양쪽을 모두 부팅시킨다.**
- **실전 `.env` 는 좌표 원천이 아니다.** 그 파일의 선물 계좌는 실전 계좌이고, 비협상 규칙상
  절대 주문 경로에 오르지 않는다. 렌더 CLI 는 이름이 정확히 `.env.mock` 인 파일만 받는다.

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

## 2. 렌더 — 좌표 주입 (저장소 밖 디렉터리 생성)

```bash
cd /home/deploy/project/kis_unified_sts
.venv/bin/python scripts/tos/render_paper_config.py \
    --out ~/.config/tos/paper-config \
    --env-file .env.mock \
    --direction LONG
```

- `--out` 기본값이 `~/.config/tos/paper-config` 다. **저장소 작업트리 안이면 거부한다** —
  gitignore 누락 하나로 계좌번호가 커밋될 수 있기 때문이다.
- `--env-file` 은 이름이 정확히 `.env.mock` 이어야 한다. `.env`/`.env.real` 은 **종료코드 2**.
- 종목은 실행 당일 `shared.instruments.futures.get_front_month_code(product="mini")` 로
  뽑는다(만기마다 바뀌므로 파일에 고정하지 않는다). `--instrument` 로 고정 가능.
- 계좌번호는 **어디에도 출력되지 않는다.** 로그와 `RENDERED.json` 에는
  `account_fingerprint`(`tools/broker_probes/common.py:220-225` 와 같은 값)만.
  ⚠ 그 지문은 **상관자이지 마스킹이 아니다** — 무염 SHA-256 을 12 hex 로 자른 값이고
  입력 공간이 10자리 숫자(10^10)라 역산된다. 저장소 밖 0700 디렉터리 안에만 두고,
  **유출된 지문은 유출된 계좌번호로 취급한다.**
- 저널(`bootproof_journal.jsonl`)은 **렌더 시점에 생성**되고 관측 시각이 그때로 고정된다.
  → **부팅 직전에 렌더한다.** 오래된 렌더로 부팅하면 신선도 한도를 넘겨 값이 UNKNOWN 이 된다.

**실패한 렌더는 아무것도 남기지 않는다**(review-797 MEDIUM-2 · 2차 HIGH 로 범위 정정).
렌더는 형제 작업 디렉터리 `.<name>.partial-<pid>` 에서 조립하고, 성공했을 때만 이름
바꾸기 세 번으로 `--out` 자리와 교체한다(이전 렌더는 `.<name>.replaced-<pid>` 로 **옮겼다가**
교체 성공 뒤에 지운다 — 지우고 옮기면 그 사이에 이전 렌더가 이미 없는데 새 것도 아직 없는
창이 생긴다).

보호 구간은 **계좌 첫 바이트가 디스크에 닿는 순간부터 교체까지 전부**이고, 어떤 실패든
(①의 거부 · `Ctrl-C` · 디스크 꽉 참 · 교체 실패) 두 작업 디렉터리를 모두 지운다.
⚠ **1차 판은 여기까지 못 갔다** — `try` 가 지문 계산 직전에 끝나서, 그 뒤(지문 ·
`RENDERED.json` 쓰기 · 이동)에서 실패하면 **계좌가 든 파일 7개짜리 숨김 디렉터리**가 남았고,
이름에 PID 가 들어가 **다음 실행이 치우지도 알아채지도 못했다.** 이제 실패 지점별 테스트가
경계마다 하나씩 있다.

**이전 실행의 작업 디렉터리가 남아 있으면 렌더가 거부하고 경로를 알려 준다.** 자동으로
지우지 않는다 — 동시에 도는 다른 렌더의 것일 수 있고, PID 생존 여부는 PID 재사용 때문에
믿을 수 없으며, 무엇보다 **계좌가 든 디렉터리를 추측으로 지우는 것**이야말로 이 가드가
막으려는 조용한 동작이다. 다른 렌더가 돌고 있지 않다면 안내대로 `rm -rf` 후 재실행한다.

렌더 결과 확인(좌표 칸 외 차이 0):

```bash
.venv/bin/python scripts/tos/render_paper_config.py --check --out ~/.config/tos/paper-config
```

### SHORT 구성

같은 명령에 `--direction SHORT` 만 바꾼다. `construction.yaml::action_class`/`outbound_side`,
`order_construction_policy.yaml` 의 `DIRECTION` 축, 전략 파일의 `direction`,
`marketfeed.yaml::direction` 이 **함께** 바뀐다(두 번째 사본을 커밋하지 않는 이유).

```bash
.venv/bin/python scripts/tos/render_paper_config.py \
    --out ~/.config/tos/paper-config-short --env-file .env.mock --direction SHORT
```

## 3. 부팅

`$DATA` 는 **새 부팅이 처음부터 만드는** 디렉터리다(비어 있어도 된다 — `run` 이
genesis 로 네 스토어를 만든다). **§4-A 는 이 변수를 쓰지 않는다** — 거기서는 이미 스토어가
들어 있는 기존 corpus 를 운영자가 이름으로 지정하고, §4-A 가 자기 변수(`CORPUS`)를 따로
묶는다. 비어 있는 디렉터리에 `migrate` 를 겨누면 **스토어가 새로 만들어진다**(§4-A 전제).

```bash
DATA=~/.local/state/tos/paper-data          # 저장소 밖 · 새 부팅용 (아직 없으면 만들어진다)
mkdir -p "$DATA"
PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python -c \
  'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' \
  run --config-dir ~/.config/tos/paper-config \
      --data-dir "$DATA" \
      --custody-root "$CUSTODY" \
      --environment-label "$LABEL"
```

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

**시각이 도는지**는 `TIME_HEALTH_SNAPSHOT` 행 수로 본다 — `run` 은 세션이 열려 있으면 **매 패스**,
닫혀 있으면 `marketfeed.yaml::time_evaluate_closed_interval_ms`(paper 60000)마다 시간 건강을 평가한다
(`marketfeed/time_pacer.py`). 닫힌 시각에 2분 넘게 돌렸는데 부팅 2행에서 늘지 않으면 결함이다:

```bash
sqlite3 "$DATA/evidence.sqlite3" "SELECT COUNT(*) FROM entries WHERE kind='TIME_HEALTH_SNAPSHOT';"
```

**장중(세션 열림) 기대치는 「패스마다 1행」이고, `poll_interval_ms: 400` 기준 ≈ 2.4 행/초** 다
(주기 = poll + 패스 소요 ≈ 410 ms). 그 값은 운영자 처분 2026-09-27 §6.1 ·
`docs/plans/2026-09-27-tos-poll-interval-freshness-budget-plan.md` 에서 1000 → 400 으로 내려왔다.
실측(같은 계획 §7.3, 개장 시각 주입 + 실 `run_forever` 90 s, 2회): **216 행(2.39/s) · 220 행(2.43/s)**.
장중 7 h 면 ≈ **61 k 행**이다 — 증거 디스크를 볼 때 이 값이 기준선이다. 초당 1 행 근처면 poll 이
1000 으로 되돌아간 것이고(그 조합은 이제 부팅이 거부한다 — `journal_pass_allowance_ms` 가드),
아예 늘지 않으면 §5 ④ 의 「평가가 멈춘」 결함 형태다.

## 4-A. 스키마 마이그레이션 — 증거 저장소 v1 → v2 (`entries_kind_seq`)

> **⚠ 2026-10-03 운영자 결정으로 이 절의 전제가 날짜를 갖게 됐다 — §7 을 먼저 본다.**
> 상주 data dir `~/.local/state/tos/paper-data` 는 **2026-10-06 첫 세션의 genesis 가**
> 만든다(§7.6). 그러므로 그날 **이후**로는 아래 「상주 paper data dir 이 없다」가 더 이상
> 참이 아니지만, **그 디렉터리에 §4-A 가 적용되는 것도 아니다** — genesis 가 곧장 v2 를
> 만들기 때문이다. 그 전에 그 경로에 `migrate` 를 겨누면 **빈 스토어 넷이 새로 생긴다**
> (아래 ⛔ 와 같은 사고).
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

### 4-A-1. 실행 기록 — 2026-10-02 dry-run (사본에서 실행 · 실 corpus 본체 불변)

운영자 판정은 **「마이그레이션할 대상이 없다」** 였다(위 「적용 범위」). 그래서 실 corpus 에는
`migrate` 를 돌리지 않았고, 대신 **사본**에 돌려 이 절의 절차와 판정 기준을 검증했다. 실행은
분리 워크트리(`origin/main` `ef4009a51d21`)에서 했고 종료코드는 `0` 이다.

**대상 corpus.** `~/.local/state/tos/realclock-20260928T110001-LONG/data` —
**부팅 2026-09-28 11:00:01 KST · 정지 11:15:04 KST**(같은 디렉터리의 `report.json` 의
`started_kst`/`ended_kst`. 디렉터리 이름의 숫자는 **부팅 시각**이고, 파일 mtime 은 **정지
시각**이다 — 한 값으로 뭉치면 다른 런으로 오인된다).
⚠ **이 corpus 는 지금 A1 증거 스캔 캠페인의 살아 있는 `--reference` 파일이다**
(`tools/tos_evidence_scan_bench.py`). 언젠가 이것을 **실제로** 마이그레이션한다면 — §4-A 가
이제 바로 그 경우를 위한 절차라고 적고 있으므로 — 그 리더가 멎은 뒤에 해야 한다.
§4-A 의 「구 코드 프로세스 전부 정지」 전제는 `backup-set` 이 **기계적으로 탐지하지 못하는**
전제다(그 함수의 문서화된 한계). 확인은 손으로 한다: `fuser -v <corpus>/*.sqlite3`.

**사본 뜨는 법 (WAL 이라서 중요하다).** 여기서는 `cp` 로 네 파일을 떴고, 그게 안전했던 이유는
**이 corpus 의 `-wal` 이 전부 0 바이트**였기 때문이다 — 그 조건이 아니면 `cp evidence.sqlite3`
는 **커밋된 행을 조용히 흘린다**(WAL 에만 있고 본체에 아직 없는 꼬리). 그러면 사본끼리는
`COUNT(*)` 도 `chain_digest` 도 서로 일치하므로 **표가 맞아 보이는데 원본과 다르다**. 조건에
기대지 않는 관용구를 쓴다:

```bash
sqlite3 "file:$CORPUS/evidence.sqlite3?mode=ro" ".backup '$COPY/evidence.sqlite3'"
# 또는: 본체와 함께 -wal 도 같이 복사한다 (-shm 은 재생성되므로 불필요)
```

`--store` 없이 돌린 stdout 전문(경로만 `<copy>` 로 줄였다):

```
migrate: evidence at <copy>/evidence.sqlite3 — applied v1 -> v2 (v2)
migrate: rcl at <copy>/rcl.sqlite3 — already at v2, nothing to do
migrate: inbox at <copy>/inbox.sqlite3 — already at v1, nothing to do
migrate: marketfeed at <copy>/marketfeed.sqlite3 — already at v1, nothing to do
```

증거 저장소의 전후는 이렇다(나머지 셋은 이미 최신이라 변화 없음):

| 항목 | 전 | 후 |
| --- | --- | --- |
| `PRAGMA user_version` | 1 | **2** |
| `schema_ledger` | `1\|CREATED` | `1\|CREATED` · **`2\|MIGRATE`** |
| `entries` 행 수 | 2824 | 2824 (불변) |
| 마지막 `chain_digest` | `f324e7eb…5daa1569` | `f324e7eb…5daa1569` (**동일**) |
| `entries_kind_seq` | 없음 | **있음** |
| `PRAGMA integrity_check` | — | `ok` |
| 파일 크기 | 5332992 B | 5427200 B (+94208) |

`sqlite_master` 는 위 기대 목록 8개와 **글자 그대로 일치**했다. append-only 트리거 네 개는
**전후 모두** 있었고, 그래서 `rebuilt …` 줄이 나오지 않았다 — 이 corpus 는 2026-10-02 이전
`migrate` 가 남긴 「대장은 있는데 트리거가 없는」 파일이 **아니다**.

#### 조사가 실 corpus 에 남긴 것 — 「한 바이트도 안 건드렸다」는 틀렸다

이 기록의 1차 판은 실 durable set 을 **「한 바이트도 건드리지 않았다」**고 적었다. **그 문장은
거짓이었다.** 어느 corpus 가 v1 인지 세는 조사 자체가 **라이브 파일을 열었고**, 열린 흔적이
남았다. 정정해서 적는다 — 무엇이 불변이고 무엇이 아닌지 따로.

**본체 네 파일은 바뀌지 않았다.** 열두 corpus 전부 `*.sqlite3` 의 **mtime 과 크기가
2026-09-27/28 그대로**다. 독립 대조도 있다: 이 corpus 의 `report.json` 이 **2026-09-28 정지
시점에** 적어 둔 `evidence_by_kind` 의 합이 **2824** 이고, 오늘 센 `COUNT(*)` 와 같다 —
조사보다 먼저 쓰인 기록이라 조사의 영향을 받지 않는다. ⚠ 다만 **조사 전 sha256 기준선은
뜨지 않았다**. 그래서 바이트 동일성은 해시로 **증명된 것이 아니라** mtime·크기·행 수·
`chain_digest` 네 가지가 일치한다는 **정황**이다. 다음 조사는 먼저 해시를 뜬다.

**사이드카는 생겼다.** `-shm` 의 mtime 이 조사 루프 두 번과 초 단위로 맞는다 —
`inbox`/`marketfeed`/`rcl` 은 **15:48:02**, `evidence` 는 **15:55:17**(둘 다 2026-10-02 KST,
열두 디렉터리를 훑은 두 루프). `-wal` 의 mtime 은 원래 런(2026-09-27/28) 아니면 **13:05**
이고 **조사보다 앞선다** — 그 시각의 접근은 이 조사가 아니다. 즉 이 조사가 확실히 쓴 것은
**`-shm`** 이고, 사이드카가 **없던** 디렉터리였다면 **만들었을 것**이다(아래 실측).

⚠ **`mode=ro` 로는 부족하다. 조사는 이미 `mode=ro` 를 쓰고 있었다.** 읽기 전용 연결도 WAL
인덱스를 쓰기로 열기 때문에 `-shm` 이 생긴다. 2026-10-02 실측(사이드카 없는 사본):

```bash
sqlite3 "file:$P?mode=ro"               "PRAGMA user_version;"   # → .sqlite3-shm, -wal 생성됨
sqlite3 "file:$P?mode=ro&immutable=1"   "PRAGMA user_version;"   # → 아무것도 생기지 않음
```

**그러므로 실 corpus 를 조사할 때의 관용구는 `immutable=1` 이다:**

```bash
for d in ~/.local/state/tos/*/data; do
  for f in evidence inbox marketfeed rcl; do
    [ -f "$d/$f.sqlite3" ] || continue
    printf '%s %s=' "$(basename "$(dirname "$d")")" "$f"
    sqlite3 "file:$d/$f.sqlite3?mode=ro&immutable=1" "PRAGMA user_version;"
  done
done
```

`immutable=1` 은 **파일이 바뀌지 않는다고 sqlite 에 약속하는 것**이므로, 쓰고 있는 런타임이
붙어 있는 파일에는 쓰지 않는다(그때는 애초에 조사할 때가 아니다 — §4-A 전제).

**남은 사이드카는 치우지 않았다.** `-shm` 은 32768 B 라 「빈 파일」이 아니고, 0 B 인 `-wal`
은 **이 조사보다 먼저 있던 것**이다. 즉 지울 자격이 있는 파일과 이 조사가 만든 파일이
서로 다르다. 무해하지만(둘 다 캐시·저널이고 다음 open 이 재생성한다) 실 paper 상태를
건드리는 삭제라, **운영자 지시 없이는 하지 않는다.** 치울 때의 조건은 하나다 —
`fuser -v <corpus>/*.sqlite3` 가 비어 있을 것.

**백업 세대는 뜨지 않았다** — 실 파일을 바꾸지 않았으므로 (0) 단계가 성립하지 않는다. 다만
그 과정에서 확인해 둘 것이 하나 나왔다: **`cold-backup` 은 지금 이 호스트에서 쓸 수 없고,
쓸 수 있게 만드는 것은 두 줄짜리 YAML 변경이 아니다.** 채워진 `evidence_cold_backup.yaml`
이 없고(`~/.local/state/tos/paper-ops` 자체가 없다), 로더는 `minimum_free_bytes` 의 null 을
**거부**한다. 콜드 백업 런북 §2 는 기본값이 없는 것이 **결정**이라고 못박는다 — 「승인되지
않은 한도를 결정된 값처럼 적지 않는다」. 즉 그 숫자는 **운영자가 정하는 값**이고, 에이전트가
호스트 여유 공간을 보고 채워 넣을 자리가 아니다. 설정 없이 지금 당장 쓸 수 있는 백업 경로는
§4-B 의 `backup-set --archive-dir --verify-dir --custody-root` 이며(쓰고 나서 되읽어 검증),
이 플래그 셋은 현재 CLI 에 실재한다(`tos/runtime/src/tos_runtime/compose/cli.py` 의
`backup-set` 파서).

⚠ **2026-10-03 갱신 — 위 문단은 그날 오전까지의 상태이고, 그때는 전부 참이었다.** 그 뒤
운영자 결정 둘이 들어와 `cold-backup` 은 **쓸 수 있는 상태**가 됐다:
`~/.local/state/tos/paper-ops/evidence_cold_backup.yaml` 과 세 보관 경로가 만들어졌고,
`minimum_free_bytes` 는 **53687091200**(50 GiB)으로 채워졌으며, 대상은 **상주 paper
런타임의 `~/.local/state/tos/paper-data`** 다(2026-10-06 genesis 예정). 남은 것은
crontab 한 줄(운영자)과 그 genesis(ops-paper 레인) 둘이다. 호스트에 무엇이 있고 켜는 데
무엇이 남았는지는 `docs/runbooks/tos-evidence-cold-backup.md` §4-5 에 있다.

⚠ 그 절이 함께 기록한 것: **이 호스트의 1회성 corpus 12개는 전부 증거 스키마 v1 이라,
그중 하나를 콜드 백업 대상으로 고른다면 먼저 위 §4-A 의 `migrate` 를 그 corpus 에 돌려야
한다.** 선택된 대상(상주 런타임)에는 해당하지 않는다 — genesis 가 곧장 v2 를 만든다.

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

### ① ✅ 정본 digest 가 프로세스마다 달랐다 — **해소됨 (2026-09-24)**

1차 판에서는 이것이 절차 자체의 결함이었다. 렌더는 `print-policy-digests` 출력을
`safety_activation.yaml::members` 에 전사한 뒤 **새 프로세스에서** 정책을 다시 로드해 그
digest 로 활성화를 재확인하는데, 그 재확인이 거부했다:

```text
render_paper_config: refused — activation read-back refused — the rendered members block
is not activated (exit 1):
tos_runtime.venue.activation.PolicyNotActivated: activation refused for
kind=<BundleMemberKind.VENUE_CONSTRAINT_POLICY: 'VENUE_CONSTRAINT_POLICY'>
member_id='vcp-paper-krx-index-futures' generation=1 digest='<A>':
members[0]: digest '<B>' != '<A>'
```

원인은 한 모델이 아니라 **부류**였다 — `covered_content()` 가 `model_dump(mode="json")`
이라 `frozenset` 이 **집합 순회 순서 그대로의 리스트**가 되고, 정본 인코더는 시퀀스를
순서 유의미로 해시한다. 문자열 집합의 순회 순서는 프로세스별 해시 시드를 따르므로,
covered content 에 집합을 가진 정본 모델 **19종**의 digest 가 프로세스마다 달랐다
(그중 8종만 모델별 `sorted()` 로 막고 있었다).

**처분(2026-09-24): `FrozenModel` 에 JSON 모드 직렬화 훅 하나**
(`tos/src/tos/canonical/_canonical_json.py`;
`docs/plans/2026-09-24-tos-canonical-set-order-plan.md`). 모든 집합이 `sorted()` 순으로
나가므로 `covered_content()`·`event_identity()`·런타임 `compute_digest(model_dump(...))`
가 호출 형태와 무관하게 닫힌다. 이미 정렬하던 8종의 digest 는 **비트 단위로 동일**하고,
모델별 정렬 수단 8개는 삭제됐다.

실측(2026-09-24, 이 호스트, **`PYTHONHASHSEED` 미설정**, 브랜치
`fix/tos-canonical-set-order`, 산출물은 저장소 밖 임시 디렉터리):

```text
$ scripts/tos/render_paper_config.py --out <scratch>/config-long \
      --env-file .env.mock --direction LONG
  activation:      ACTIVATED 5 (re-derived in a fresh process)
$ scripts/tos/render_paper_config.py --check --out <scratch>/config-long
  render_paper_config --check: ... matches config/tos_runtime/paper
$ ... cli run --config-dir <scratch>/config-long --data-dir <scratch>/data-long \
        --custody-root <scratch>/custody --environment-label paper
  (SIGTERM) run: stopped (signal received).      # 종료코드 0
```

SHORT 렌더·부팅도 같다(`--direction SHORT`, 종료코드 0). 세션 시계를 다음 개장일로
주입하면(아래 ④ 의 진단) `TICK OUTCOME: TICKED` 이고 `marketfeed.sqlite3` 의
`snapshots` 가 1 이다 — LONG·SHORT 양쪽:

```text
injected session clock: 2026-09-28T10:00:00+09:00 (unix_ms=1790557200000)
session_context: tz_id='Asia/Seoul' tz_db_version='2026c'
  trading_calendar_version='krx-2026.09.1' phase='CONTINUOUS' is_open=True
  tz_version_conflict=False boundary_value=1790577900000
TICK OUTCOME: TICKED
```

⚠ **`PYTHONHASHSEED` 를 맞춰 통과시키는 것은 진단이지 절차가 아니었다** — 그래서
렌더의 `_subprocess_env()` 는 그 변수를 더 이상 통과시키지 않고, 결함을 고정하던
`tests/unit/scripts/test_render_paper_config.py` 의 테스트·픽스처도 지웠다. 회귀는
`tests/tools/test_tos_canonical_set_order.py` 가 시드 6개 서브프로세스로 막는다.

⚠ **커널 소스를 바꿨으므로 `expected_code_digest` 도 함께 갱신됐다**
(`config/tos_runtime/paper/release.yaml` + `_VALUE_PINS`). 갱신 전에 부팅하면 Stage A 가
`ReleaseAdmissionRefused` 로 거부한다 — 이 재측정에서 실제로 한 번 겪었고, 갱신 후 통과했다.

### ② ✅ 부팅 라벨 — **해소됨 (운영자 결정 2026-09-23: `paper`)**

1차 판에서는 이것이 거부였다:

```text
run: refused — compose_paper_runtime raised VenuePolicyScopeMismatch:
venue policy scope.environment 'paper' != this compose root's environment_label 'non-live-test'
```

**운영자가 `paper` 로 결정했다(2026-09-23).** 그래서 §1·§3 이 `LABEL=paper` 를 쓰고,
`critical_input_policy.yaml::environment` 도 같은 토큰으로 맞췄다. 이 런북은 이제 라벨을
**고른다** — 1차 판의 「이 런북은 둘 중 하나를 고르지 않는다」는 문장은 같은 문서가 이미
`LABEL=paper` 를 박고 있었으므로 그 자리에서 거짓이었다(review-797 MEDIUM-1).

왜 `paper` 인가: 채택된 정책 문서들이 이미 그 환경을 선언한다 —
`venue_constraint_policy.yaml:55` · `order_construction_policy.yaml:88`
`environments: ["paper"]`, 그리고 compose 가 부팅 시점에 대조한다
(`tos_runtime/compose/_venue_wiring.py` `_cross_check_scope`).

⚠ **이 라벨이 무엇을 바꾸는지 알고 쓸 것.** `paper` 는
`tos_runtime/compose/cli.py:215` 의 `_LIVE_ENVIRONMENT_LABELS`
(`{"paper","restricted-live","production"}`) 소속이다. 구체적 귀결:

- `restore-drill` 은 이 라벨로 **실행을 거부한다**(`cli.py:816` — 「drills only ever run
  under a non-live label」). 복구 드릴을 돌리려면 비라이브 라벨의 별도 배포가 필요하다.
- `run` 자체에는 그 검사가 없다. 그리고 이 배포의 실제 스코프는 여전히
  `SYNTHETIC_FUTURES_ORDER`(브로커 미도달)라 **라벨이 라이브 분류라는 것과 실제로
  주문이 나간다는 것은 다른 얘기다** — 라벨은 문서 스코프 일치용이고, 주문 도달 여부는
  `broker_scopes.yaml::active_scope` 가 정한다.
- 커스터디 매니페스트의 `environment_label` 도 같은 값이어야 한다(§1).

⚠ **로더는 `critical_input_policy.yaml::environment` 를 부팅 라벨과 대조하지 않는다**
(실측). 그 토큰은 발행되는 모든 스냅샷·캡슐의 covered content 로 들어가므로
(`marketfeed/snapshot.py:283`), 둘이 갈리면 **증거가 조용히 틀린 라벨을 단다.** 지금은
둘 다 `paper` 이고, 라벨을 바꾸려면 **두 곳을 같이** 바꿔야 한다.

### ③ ✅ Hard Safety Envelope 지배 차원 — **해소됨 (운영자 승인 2026-09-23)**

1차 판에서는 이것이 거부였다:

```text
run: refused — compose_paper_runtime raised RiskPolicyScopeMismatch: aggregate risk policy
governs dimension id(s) ['INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL'] that the Hard Safety
Envelope's own governed_dimensions [] does not declare — every ARE-governed dimension must
have a real envelope ceiling
```

**운영자가 승인했다(2026-09-23): HSE 가 `INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL` 을
`envelope_max = 1`(계약)로 지배한다.** 요구 자체는 이미 문서에 있었다 —
`aggregate_risk_policy.yaml:74` 「HSE must govern … with envelope_max ≥ 1」 — 그리고 1 은
그 정책의 이미 승인된 유효 한도(`:111`)이자 OCP 사이징의 `max_quantity: 1` 이다.

`config/tos_runtime/paper/safety_envelope.yaml` 에 차원을,
`safety_profile.yaml` 에 같은 차원의 `profile_value: "1"` 을 함께 기입했다 — 프로파일이
봉투의 선언 차원을 **누락하면** `profile_within_envelope` 가 거부하고
(`spg/predicates.py:278-283`), **빈 봉투 자체**도 무권한으로 거부된다(`:274-277`). 즉
1차 판의 「둘 다 비었다」 상태는 정합이 아니라 어느 쪽으로도 통과 불가였다. 경계는
`INCLUSIVE` 여야 한다 — EXCLUSIVE 면 `value == max` 가 거부돼 1 계약이 통과하지 못한다.

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

## 6. 정리

- 렌더 산출물(`~/.config/tos/paper-config*`)과 커스터디 루트는 **계좌 좌표/자격증명**을
  담는다. 저장소 밖에 두고, 공유하지 않는다.
- 렌더는 저장소에 아무것도 남기지 않는다 —
  `tests/unit/scripts/test_render_paper_config.py::test_guard_render_leaves_the_repository_byte_identical`
  이 임시 `git clone` 안에서 실제 CLI 를 돌려 `git status --porcelain --ignored` 불변을 단정한다.

## 7. 상주 운영 — 매 거래일 (운영자 결정 2026-10-03 · **2026-10-06(화) 시작**)

> §1–§6 은 **1회성 부팅**의 절차다. 이 절은 그것을 **매 거래일 무인 반복**으로 돌리는
> 배선이고, §3 과 다른 점은 단 하나다 — **data dir 이 영속**이다. 그 하나가 §4-A 의 적용
> 범위, 증거 델타의 셈법, 콜드 백업의 전제를 전부 바꾼다.

### 7.1 결정 — 무엇이 바뀌고 무엇이 그대로인가

- **운영자 결정 2026-10-03**: TOS paper 런타임을 매 거래일 **상주**로 돌리고, 증거를
  **영속 data dir** 한 곳에 쌓는다. 첫 세션은 **2026-10-06(화)** 다 — 10-03(토)·10-05(대체휴일)
  은 비거래일이다(`config/market_schedule.yaml`).
- **바뀌지 않는 것**: 채택 스코프는 여전히 `SYNTHETIC_FUTURES_ORDER` 이고 **실주문 0 ·
  브로커 미도달**이다(§0). 좌표는 `.env.mock` 의 **모의** 선물 계좌다. 실전 선물 계좌는
  비협상 규칙상 영구히 주문 경로에 오르지 않는다.
- **전략이 아니다**: 전략·construction·marketfeed·critical-input 은 여전히 **부팅 증명
  픽스처**다(§0). 상주로 돌린다고 해서 이것이 거래 전략이 되지 않는다. 상주의 목적은
  ① 매일 같은 코드가 실시계로 부팅한다는 증거를 쌓는 것, ② 증거량·부팅 비용의 실제 곡선을
  (합성 이력이 아니라) 실측으로 얻는 것이다.
- ⚠ **바뀌는 것 (1) — 상주는 `LONG` **한 방향**으로만 돈다.** 이것은 §0 에서 바뀌는 점이다:
  §0 은 「대칭을 좁히지 않았다는 증거로 **양쪽을 모두 부팅시킨다**」고 적고, 09-27/28
  캠페인은 실제로 LONG·SHORT 를 각각 띄웠다. 상주 래퍼는 `TOS_PAPER_DIRECTION` 기본값이
  `LONG` 이고, 한 data dir 에 두 방향을 섞는 경로는 설계에 없다(§7.10 3 — 섞으면 §5 ⑤ 때문에
  나중에 digest 로 갈라낼 수 없다). 저장소 규칙 「Futures must preserve long/short symmetry」는
  **전략 코드의 대칭**에 대한 것이고 이 배선은 그 코드를 바꾸지 않지만, **매일 쌓는 증거가
  한 방향뿐**이라는 것은 그 자체로 기록할 변화다. **운영자 결정 자리다 — §7.10 3.**
- ⚠ **바뀌는 것 (2) — 코드가 날마다 움직인다.** 래퍼는 매일 아침 `origin/main` 에서
  워크트리를 새로 만든다. 그래서 **하나의 append-only 코퍼스가 여러 커널 리비전에 걸친다.**
  §7.10 6 을 볼 것.

### 7.2 경로 · 좌표 규율 · 환경 손잡이

| 무엇 | 어디 | 비고 |
| --- | --- | --- |
| 상주 durable set | `~/.local/state/tos/paper-data` | **10-06 genesis 가 만든다**(§7.6) · mode 0755(런타임이 만든다) — 증거는 계좌 지문을 담지 않지만 공유 호스트이므로 운영자가 좁힐 수 있다 |
| 세션 래퍼 | `~/.config/kis-probes/tos-paper-session.sh` | mode 700 · 비커밋 |
| 세션 드라이버 | `~/.config/kis-probes/tos_paper_session.py` | mode 700 · 비커밋 |
| 분리 워크트리 | `~/.local/state/tos/measure/wt-paper` | 매일 `origin/main` 에서 **다시 만든다**(§7.3 3) · **0755** — 좌표를 담지 않는 공개 `origin/main` 내용이라 0700 대상이 아니다 |
| 렌더된 설정 | `~/.config/tos/paper-config` | mode 700 · 매일 부팅 **직전에** 다시 렌더(저널 신선도 §2) |
| 커스터디 | `~/.local/state/tos/paper-custody` | mode 700 · §1 그대로 · `environment_label: "paper"` |
| 일별 로그 | `~/.local/state/tos/paper-logs/<YYYY-MM-DD>.log` | mode 700 디렉터리 · 래퍼+드라이버 stdout/err |
| cron stdout | `~/.local/state/tos/paper-logs/cron.log` | ⚠ **로테이션 없음** — 분기마다 손으로 자른다 |
| 세션 아티팩트 | `~/.local/state/tos/paper-sessions/<date>-<HHMMSS>-<DIR>/` | mode 700 · `report.json` · `render.log` · `run.log` · `bootproof.txt` |
| PID | `~/.local/state/tos/paper-ops/paper-session{,.driver}.pid` | ⚠ **이 디렉터리는 콜드 백업의 `--config-dir` 이기도 하다**(`evidence_cold_backup.yaml` 이 여기 산다). 둘을 가르려면 PID 를 `~/.local/state/tos/paper-run/` 으로 옮긴다 — 지금은 옮기지 않았다 |
| flock | `~/.config/kis-probes/tos-paper-session.lock` | **기동만** 잡는다(§7.4) |

**좌표 규율 (§2·§6 의 연장 — 이 절에도 그대로 적용된다).**
`render.log` 는 **계좌 지문**을 찍는다. §2 가 못박듯 그 지문은 마스킹이 아니라 상관자이고
**유출된 지문은 유출된 계좌번호로 취급한다.** 그러므로 **좌표를 담는 다섯 트리**
— `~/.config/tos/paper-config`(렌더 산출물) · `~/.local/state/tos/paper-custody`(자격증명) ·
`~/.local/state/tos/paper-sessions`(`render.log`) · `~/.local/state/tos/paper-logs`(래퍼 로그) ·
`~/.local/state/tos/paper-ops`(PID·백업 설정) — 는 전부 저장소 밖 **0700**(실측)이고, **`render.log` · 증거 행 · 질의 결과를 PR·계획 문서·텔레그램으로 옮겨
적지 않는다**(이 런북의 인용은 전부 지문·계좌가 없는 줄만 고른 것이다). `.env.mock` 은
`$MAIN` 의 것을 **절대경로로 넘긴다 — 워크트리로 복사하지 않는다**(§7.3 1). 텔레그램 토큰은
`$MAIN/.env` 의 두 줄만 `grep` 으로 읽고 로그에 내보내지 않는다.

**환경 손잡이 (전부 열 개 + 플래그 하나).** ⛔ 표시는 **드라이런 전용이고 cron 줄에 절대
넣지 않는다** — 셋 다 무인 레인의 안전장치를 끈다.

| 손잡이 | 기본값 | 무엇을 하나 |
| --- | --- | --- |
| `TOS_PAPER_DATA_DIR` | `~/.local/state/tos/paper-data` | 상주 durable set |
| `TOS_PAPER_STOP_HHMM` | `15:45` | 정지 시각(KST). 안전망 마감 계산의 기준 |
| `TOS_PAPER_APPEND_EVERY_S` | `5` | 관측 수집 주기(초). `0` 이면 수집기 OFF(§7.3) |
| `TOS_PAPER_DIRECTION` | `LONG` | `LONG`\|`SHORT`. 그 밖의 값은 ABORT |
| `TOS_PAPER_NOTIFY` | `1` | `0` 이면 텔레그램을 보내지 않고 **보낼 본문을 로그에 적는다** |
| `TOS_PAPER_WT` | `~/.local/state/tos/measure/wt-paper` | 분리 워크트리 경로 |
| `TOS_PAPER_BOOTPROOF_CEILING_S` | `600` | 부팅 증명 천장. 래퍼는 여기에 +30 s 를 기다린다(§7.3 7) |
| ⛔ `TOS_PAPER_IGNORE_CALENDAR` | (없음) | `1` 이면 **휴장·주말 검사를 통째로 끈다** |
| ⛔ `TOS_PAPER_FAKE_DATE` | (없음) | 달력 검사만 이 날짜로 본다 |
| ⛔ `TOS_PAPER_MINUTES` | (없음) | 안전망 마감을 직접 준다 — **§7.3 6 의 「마감이 지났다」 검사를 건너뛴다** |
| `--selftest` (플래그) | — | 텔레그램 줄에 `[SELFTEST] ` 접두 |

### 7.3 래퍼의 `start` 가 하는 일 (순서가 전부다)

0. **전제 좌표** — 인터프리터(`$MAIN/.venv/bin/python`) · 드라이버 · `$MAIN/.env.mock` ·
   커스터디 루트와 매니페스트가 있고, 매니페스트의 `environment_label` 이 부팅 라벨과
   **바이트 일치**하며(§1), `TOS_PAPER_DIRECTION` 이 `LONG`/`SHORT` 이고, **살아 있는
   드라이버가 없을 것**. 하나라도 어긋나면 **ABORT rc 2** 이고 텔레그램 ABORT 줄이 나간다.
   ⚠ 이것은 바로 아래 flock 의 **SKIP rc 0** 과 다른 사건이다 — SKIP 은 조용하고(텔레그램 없음)
   ABORT 는 시끄럽다.
1. **flock** — 두 기동이 겹치지 않는다. 겹치면 뒤에 온 쪽이 **기다리지 않고 비켜난다**(`-n`,
   rc 0, 텔레그램 없음).
2. 호스트 여유를 로그에 남긴다. ⚠ **메모리·스왑은 기록만 하고 게이트하지 않는다** — 전역
   `CLAUDE.md` 의 착수 문턱은 무거운 빌드용이고 이 세션은 파이썬 프로세스 하나다.
   **게이트는 디스크 하나**이고 5 GB 미만이면 ABORT 한다(증거가 하루 ≈ 200 MB 쌓인다,
   수집기 on 기준 — §7.8 3).
3. `git fetch`(실패하면 **ABORT**) → 분리 워크트리를 `origin/main` 에 **다시 만든다.**
   공유 체크아웃에서 돌리지 않는 이유는 `MEMORY.md` 「프로브는 분리 워크트리(origin/main)
   에서만」(#793 HIGH)과 같다 — 병렬 레인이 브랜치를 바꾼다.
   ⛔ **「지우고 다시 만든다」를 조건 없이 하지 않는다.** `$WT` 는 환경변수로 바뀌고 그 부모
   디렉터리에는 **다른 레인의 워크트리와 재실행 금지 A1 코퍼스**가 산다. 그래서 (a) 경로가
   존재하면 **이 저장소에 등록된 워크트리일 때만** 지우고 아니면 ABORT, (b) `rm -rf` 폴백은
   **없다**, (c) 살아 있는 드라이버가 그 트리에서 돌면 `--force` 하지 않고 ABORT 한다.
   ⚠ **복구 절차 — `worktree prune` 은 선택이 아니라 매일 돈다.** `worktree remove` 는
   `.git/worktrees` 의 관리 항목을 남길 수 있고, 그러면 다음 `worktree add` 가
   `fatal: … is a missing but already registered worktree` 로 죽는다(실측 §7.9 S1-b).
   래퍼는 `add` 직전에 **항상** `prune` 을 돌린다. 손으로 고칠 때도 같은 명령이다:
   `git -C <repo> worktree prune`.
4. **달력** — `config/market_schedule.yaml` 과 `config/tos_runtime/paper/calendar.yaml` 을
   **둘 다** 본다. 앞의 것은 운영자가 지목한 정본이고, **뒤의 것이 런타임이 실제로 게이트하는
   파일**이다. 한쪽만 보면 「휴장이라고 적힌 날에 부팅」이 조용히 가능하다. 둘이 갈리면
   **보수적으로 건너뛰고** 그 사실을 로그에 남긴다. 휴장·주말이면 **rc 0 · 로그 한 줄 ·
   텔레그램 없음**이고, 아무것도 부팅하지 않는다.
   ⛔ 두 달력 파일 중 하나라도 **없으면 건너뛰기가 아니라 ABORT** 다. 없는 파일에 grep 을
   걸고 결과를 0 으로 읽으면 「달력이 사라졌다」가 「거래일이다」로 접힌다.
   ⚠ grep 은 `- "YYYY-MM-DD"` 라는 **따옴표 있는 형태**를 찾는다. 두 파일의 현 표기가 그것이다.
5. **digest 입장 검사** — 워크트리에서 `print-digests` 를 돌려 같은 워크트리의
   `release.yaml::expected_{code,dependency_set}_digest` 와 대조한다. 다르면 **부팅하지 않고
   거부**한다. 어차피 Stage A 가 `ReleaseAdmissionRefused` 로 거부할 것을, 여기서 **왜**
   거부되는지와 함께 먼저 잡는 것이다(§5 ① ⚠ — 커널 소스를 바꾸면 이 핀을 재도출해야 한다).
   ⚠ **빈 값끼리의 일치는 일치가 아니다.** `print-digests` 가 죽거나 `release.yaml` 의 키
   이름이 바뀌면 비교할 네 값이 모두 빈 문자열이 되고, 그러면 `"" != ""` 가 거짓이라 가드가
   **조용히 통과한다**. 그래서 비교 전에 **넷 모두 64자 소문자 hex 인지** 본다 —
   `case "$_v" in ""|*[!0-9a-f]*)` 로 **전 글자**를 보고 길이도 64 로 고정한다. 접두 몇 글자만
   보는 패턴은 「64 hex」가 아니다(실측 §7.9 E3 `len64`).
6. **안전망 마감** — 정지 크론이 죽어도 세션이 영원히 돌지 않도록 `--max-minutes` 를
   「지금 → 정지 시각 + 15 분」으로 계산해 드라이버에 넘긴다.
   ⚠ **남은 시간을 먼저 보고 나서 15 분을 더한다.** 더한 뒤에 양수인지 보면 마감 5 분
   **뒤**에 뜬 기동이 「10 분 남았다」로 통과해 장 마감 뒤에 세션을 연다.
7. 드라이버를 띄우고, **부팅 증명이 날 때까지 기다렸다가** 텔레그램 기동 줄을 보내고,
   끝날 때까지 `wait` 한다.
   ⚠ **기동 줄을 드라이버보다 먼저 보내면 그 줄에 적을 것이 없다** — 증명은 부팅 몇 초
   뒤에야 안다(2026-10-03 genesis 실측 **2.0 s**). 그래서 드라이버가 증명 직후
   `bootproof.txt` 를 쓰고 래퍼가 그것을 기다린다.
   ⚠ **래퍼의 대기와 드라이버의 천장은 같은 숫자에서 나온다** — `BOOTPROOF_CEILING_S`(600 s)
   하나를 드라이버에 `--boot-proof-timeout-s` 로 넘기고 래퍼는 거기에 +30 s 를 기다린다.
   두 숫자를 따로 두면 어긋나고, **짧은 쪽이 느린 부팅을 「거부」라고 보고한다**(초판이 90 s
   대 600 s 였다). 드라이버가 증명 전에 죽으면(렌더 거부 등) 기동 줄이 그렇게 적는다 —
   **파일이 없는 것과 「MISSING」 이라고 적힌 것은 다른 사건이다**(§7.8 1).

드라이버(`tos_paper_session.py`)가 하는 일은 §2–§4 그대로다: **렌더 → 부팅 → 관측 수집 →
SIGTERM → 보고서**.

**출처.** 이 드라이버는 2026-09-27/28 부팅증명 캠페인의 측정 스크립트
(`~/.local/state/tos/measure/tos_realclock_measure.py`)에서 갈라져 나왔다. §7.8 2 가
STALE·소비를 그 캠페인의 실측과 비교하므로, **무엇이 같고 무엇이 다른지**를 적어 둔다.
같은 것: 합성 밴드 상수(`LOWER`/`UPPER`/`CLOSES` — 렌더의 `_JOURNAL_*` 와 같은 값),
`as_of = 지금 − 200 ms`, 원자적 전체 파일 교체, 필드 이름 여섯 개.
다른 것: `source_id` (`tos-paper-realclock-measure` → `tos-paper-resident-session`),
`raw_event_id` 접두 (`realclock-N` → `resident-N`), **모든 집계가 기준선 델타**,
**SIGTERM/SIGINT 처리**(측정본은 자기 시간이 끝나면 스스로 멎었다), 그리고 아래 세 가지.

상주용으로 다른 셋:

- **모든 집계가 델타다.** 부팅 직전의 `MAX(seq)` 를 기준선으로 잡고 그 **뒤**의 행만 센다.
  누적으로 세면 「오늘 부팅이 증거를 남겼다」가 **어제의 행으로 통과한다**.
  ⚠ `entries.seq` 는 **0 부터** 시작한다(실측 2026-10-03: genesis 첫 행이 `seq=0` 의
  `TIME_SERVICE_STARTUP`). 그래서 「행이 하나도 없다」의 기준선은 0 이 아니라 **−1** 이다.
  0 으로 두면 genesis 부팅의 **첫 행이 모든 델타에서 조용히 빠진다** — 초판이 실제로 그랬고,
  드라이런이 「store 19 행인데 델타 18 행」으로 잡아냈다.
- **부팅 증명을 기계적으로 확인한다.** 기준선 **뒤에** 정책 결속 **다섯 종류**
  (`VENUE_POLICY_BOUND` · `ORDER_CONSTRUCTION_POLICY_BOUND` · `AGGREGATE_RISK_POLICY_BOUND` ·
  `ACTION_FLOW_POLICY_BOUND` · `AUTHORITY_EPOCH_TRANSITION`)가 실제로 생겼는지 본다.
  **이 검사가 실패하는 구체적 입력**: 빈 커스터디 루트 → `KeyContinuityRefused` 로 `run` 이
  즉시 rc 1 (실측 §7.9 E4). 누적으로 셌다면 **어제의 다섯 행이 이것을 통과시킨다**.
  ⚠ **천장은 600 s 이고 튜닝 손잡이가 아니다.** 정책 결속 행은 부팅 **리플레이 뒤에** 쓰이고
  (실측 seq 순서: … 12 `REPLAY_VERDICT_IDENTICAL` → 13·14 정책 결속), 리플레이 비용은 이력에
  비례해 커진다(증거 증가 대응 계획 §0 3 —
  `docs/plans/2026-09-29-tos-evidence-growth-and-purge-plan.md`). 그러므로 짧은 천장은
  「상주가 오래될수록 **멀쩡한 부팅을 MISSING 으로 죽이는**」 가드가 된다. 이 값에
  가까워지는 날이 오면 그것은 조이거나 늘릴 값이 아니라 **보고할 소견**이다(§7.8 2).
- **정지가 밖에서 온다.** SIGTERM/SIGINT 를 받으면 자식(`run`)에게 그대로 넘기고
  **120 s** 기다렸다가(그 뒤 `SIGKILL`; 두 경로가 같은 값을 쓴다) `report.json` 을 쓴다.
  부팅 증명을 기다리는 루프도 정지 신호를 본다 — 보지 않으면 느린 부팅 중의 SIGTERM 이
  최대 10 분 무시되고 래퍼의 180 s 정지 경보가 멀쩡한 세션에 울린다.

**관측 수집기(`TOS_PAPER_APPEND_EVERY_S`, 기본 5 s)** 는 위 합성 밴드로 저널에 관측을
덧붙인다. 기본 on 으로 둔 이유는 **없으면 저널에 렌더의 부팅증명 1건뿐이라 소비도 결정도
0 이고**, 증거 증가 대응 계획 §1 의 「≈ 200 MB/일」 기준선이 바로 이 조건에서 나온 값이기
때문이다. 끄면 하루 ≈ **112 MB**(유도값 — §7.8 3). ⚠ **이것은 운영자 결정이 아직 없는
자리다 — §7.10 1.**

### 7.4 cron 두 줄 — **아직 설치되어 있지 않다**

설치는 운영자가 한다. 래퍼는 crontab 에 손대지 않고 자기 자신을 지우지도 않는다
(날짜 슬롯이 아니라 반복 일정이다).

```cron
CRON_TZ=Asia/Seoul
45 8  * * 1-5 /bin/bash /home/deploy/.config/kis-probes/tos-paper-session.sh start >> /home/deploy/.local/state/tos/paper-logs/cron.log 2>&1 # tos-paper-session
45 15 * * 1-5 /bin/bash /home/deploy/.config/kis-probes/tos-paper-session.sh stop  >> /home/deploy/.local/state/tos/paper-logs/cron.log 2>&1 # tos-paper-session
```

- ⚠ **이 블록은 crontab 의 끝에 붙인다.** `CRON_TZ` 는 **그 뒤에 오는 줄에만** 적용된다.
  이 crontab 에는 이미 `CRON_TZ=Asia/Seoul` 선언이 두 개 있으므로, 중간에 끼워 넣으면
  아래쪽 남의 줄의 시간대까지 바꾼다.
- 시각은 `calendar.yaml` 의 `krx-index-futures` **CONTINUOUS 08:45–15:45 KST MON–FRI** 에
  맞췄다(§5 ④). 런타임은 **마감에 스스로 멎지 않는다** — 세션이 닫히면 틱이
  `SKIPPED_SESSION_CLOSED` 가 될 뿐 `run_forever` 는 계속 돈다. 그래서 정지는 밖에서 온다.
- `1-5` 는 주말을 거르지만 **휴장일은 거르지 못한다.** 휴장 판정은 래퍼가 달력 파일로
  한다(§7.3 4) — cron 줄에 날짜를 적지 않는 이유다.
- ⚠ **cron 줄에 바깥 `flock` 을 붙이지 않았다.** 이 호스트의 다른 슬롯과 다른 점이다.
  기동 줄은 장중 내내(≈ 7 h) 살아 있으므로, 같은 lock 파일을 정지 줄에도 붙이면 **정지가
  기동의 lock 에 막혀 영영 돌지 않는다.** 중복 기동 방지는 래퍼가 자기 lock 으로 이미 한다.
- 기동 줄의 cron 자식은 장중 내내 떠 있다. 이것은 정상이다(`wait`).
- ⛔ §7.2 의 ⛔ 손잡이 셋은 이 줄에 **절대** 넣지 않는다.

### 7.5 정지 의미론

- 정지는 **드라이버에게** `SIGTERM` 을 보낸다. 드라이버가 그것을 `run` 에게 넘기고
  (= §4 의 문서화된 우아한 정지: `install_run_stop_signal_handlers`, 종료코드 0,
  stdout 에 `run: stopped (signal received).`) 종료를 기다린 뒤 `report.json` 을 쓴다.
  ⚠ **텔레그램 종료 줄을 보내는 것은 드라이버가 아니라 기동 프로세스다** — `wait` 에서
  깨어나 `report.json` 을 읽고 보낸다. 그래서 기동 프로세스가 죽어 있으면(cron 자식이
  kill 됐다면) 보고서는 남고 **종료 줄만 없다**.
- ⚠ `run` 에 **직접** SIGTERM 을 보내면 런타임은 멎지만 보고서도 텔레그램 줄도 나오지 않는다.
- 드라이버가 SIGTERM 180 s 뒤에도 살아 있으면 정지 경로는 **에스컬레이션하지 않는다** —
  `SIGKILL` 하지 않고, 지연 사실을 텔레그램으로 알리고 rc 1 로 끝낸다. 열린 sqlite 핸들을
  강제 종료로 끊는 것보다 **사람이 보는 편이 낫다.**
- 안전망: 정지 크론이 죽어도 드라이버는 `--max-minutes`(= 정지 시각 + 15 분, 즉 **16:00 KST**)
  마감에 스스로 같은 경로로 멎는다.

### 7.6 상주 data dir 은 **10-06 genesis 가 만든다** — §4-A 는 적용되지 않는다

- 2026-10-03 현재 `~/.local/state/tos/paper-data` 는 **존재하지 않는다**(실측). 손으로
  만들지 않는다 — **첫 부팅의 genesis 가 네 스토어를 만든다.**
- 그러므로 §4-A(v1 → v2 마이그레이션)는 이 디렉터리에 **적용되지 않는다.** genesis 는 곧장
  v2 를 만든다(드라이런 실측 §7.9 ①).
- ⛔ **`migrate --data-dir ~/.local/state/tos/paper-data` 를 10-06 전에 돌리지 말 것.**
  `apply_migrations` 는 존재 검사를 하지 않으므로 **빈 디렉터리에 스토어 넷을 새로 만들고
  종료코드 0 으로 끝난다**(§4-A ⛔). 그러면 키도 세그먼트도 증거도 없는 빈 스토어가
  「마이그레이션된 예전 corpus」처럼 보이고, 진짜 genesis 는 영영 일어나지 않는다.
- genesis 와 마이그레이션의 서명은 **`schema_ledger` 로 구분된다**: genesis = `2|CREATED`
  한 줄, 마이그레이션 = `1|CREATED`(또는 `1|MIGRATE`) + `2|MIGRATE`.

### 7.7 콜드 백업과의 시간 관계

- 야간 콜드 백업(`docs/runbooks/tos-evidence-cold-backup.md` ·
  `~/.config/kis-probes/cold-backup-nightly.sh`)의 대상은 **같은**
  `~/.local/state/tos/paper-data` 이고 예정 시각은 **18:00 KST** 다.
  ⚠ **그 cron 줄도 아직 설치되어 있지 않다**(PR #851). 두 줄을 같이 넣든 따로 넣든,
  **백업만 먼저 넣는 것은 의미가 없다**(대상이 아직 없다).
- `backup-set`/`cold-backup` 은 **런타임이 정지해 있을 것**을 전제하고, 그 전제를
  **기계적으로 확인하지 못한다**(그 함수의 문서화된 한계). 그래서 시간으로 벌려 둔다:

| 경로 | 정지 시각 | 18:00 까지 여유 |
| --- | --- | --- |
| 정상 (정지 크론이 15:45 에 돈다) | 15:45 + 정지 대기 | **2 h 15 m — 이것이 최대값이다** |
| 안전망 (정지 크론이 안 돌았다) | 16:00 + 렌더·부팅 시간 | **≈ 2 h 00 m** |
| 정지 지연 (§7.5 — 에스컬레이션 없음) | **상한 없음** | **보장 없음** |

- 정지가 지연되면 텔레그램에 그 사실과 함께 **「스토어가 열려 있으면 백업이 뜨지
  않는다」**가 함께 나간다. 그때의 확인은 `fuser -v ~/.local/state/tos/paper-data/*.sqlite3` 다.

### 7.8 다음 날 아침에 볼 것 (5 분)

**0. 텔레그램이 아무것도 없으면 로그에서 가른다.** 침묵에는 여러 뜻이 있다(아래 1).
`~/.local/state/tos/paper-logs/cron.log`(cron 이 돌기는 했나)와 같은 날짜의
`<date>.log`(래퍼가 어디까지 갔나)를 본다.

**1. 텔레그램 — 결말은 네 가지이고 「두 줄」이 전부가 아니다.** 채널은 briefing 이고
자격증명은 `$MAIN/.env` 의 `TELEGRAM_BRIEFING_BOT_TOKEN`/`_CHAT_ID` 두 줄이다.

| 결말 | 텔레그램 | 종료코드 |
| --- | --- | --- |
| 정상 | 기동 + 종료, **두 줄** | 0 |
| ABORT (전제·달력 파일 부재·digest·마감 지남·워크트리) | ABORT **한 줄** | 2 |
| SKIP (휴장·주말·flock 중복) | **없음** — 로그 한 줄뿐 | 0 |
| `stop` 인데 돌던 세션이 없음 | **없음** — 로그 한 줄뿐 | 0 |

⚠ 침묵의 다른 원인: `curl` 실패(로그에 `telegram notify FAILED`, **재시도 없음**),
`TOS_PAPER_NOTIFY=0`, `$MAIN/.env` 에서 자격증명을 못 찾음. **그래서 텔레그램 부재를
「안 돌았다」로 읽지 말고 0 번으로 간다.**

기동 줄의 머리는 `boot proof: OK · boot <N>s · genesis=… · rev … · <종목>` 이다. **네 값**이 있다:

| 머리 | 뜻 | 가르는 법 |
| --- | --- | --- |
| `OK` | 기준선 뒤에 정책 결속 다섯 종류가 생겼다 | — |
| `MISSING` | ① 부팅 거부(증거 0) · ② 600 s 천장 초과(느린 부팅) · ③ 스토어 판독 실패 | `boot_seconds` 가 천장 근처면 ②, `run_log_tail` 에 `run: refused —` 가 있으면 ① |
| `N/A — 부팅 전 종료` | 렌더가 거부돼 부팅 자체가 없었다 | `render.log` |
| `알 수 없음 … 드라이버는 살아 있다` | 630 s 안에 `bootproof.txt` 가 없고 드라이버는 산다 = **느린 부팅이지 거부가 아니다** | 세션 디렉터리를 다시 본다 |

⚠ **2026-10-08(목)·10-09(금)에 볼 것 — 종목이 롤한다(§7.10 7).** 기동 줄 끝의 종목은
10-06·10-07·**10-08 까지 `A05610`**(만기일 당일도 아직 구월물) 이고, **10-09(금)은 한글날이라
텔레그램이 아예 없다**(SKIP — 로그 한 줄뿐, 이 절 1 의 결말 표 SKIP 행). `A05611` 이 처음 보이는 것은
**10-12(월)** 이다. 10-08 세션 자체는 다른 날과 똑같다 — 15:45 정지까지 CONTINUOUS 이고,
거부도 stage-deny 도 없다.

**2. `report.json`** — `~/.local/state/tos/paper-sessions/<날짜>-*/report.json`:

- `boot_proof_ok: true` · `verdict: "ok"` · `exit_code: 0`
- `stop_reason` 은 **셋**이다: `signal`(정상 — 정지 크론) · `deadline`(**정지 크론이 안 돌았다**) ·
  `child_exited`(**`run` 이 스스로 죽었다** — `run_log_tail` 을 본다).
- `boot_seconds` — **이 값이 날마다 커지는지 본다.** 부팅은 이력을 리플레이하므로 증거가
  쌓일수록 느려진다(증거 증가 대응 계획 §0 3). 2026-10-03 genesis 기준선은 **2.0 s**.
- `worktree_commit` — **그날 어느 커널 리비전이 썼는지.** 코퍼스가 리비전을 가로지른다(§7.10 6).
- `events_consumed` · `stale_withheld` — 2026-09-28 실측 기준선은 **15 분 180 건 소비 중
  STALE 1 건**(= 렌더 부팅증명 관측 1건, 고칠 수 없음 §5 ④ ⚠)이다. 이것은 **개수**이고
  장중 전체(≈ 5,000 건 예상)의 비율로 옮겨 쓸 수 있는 값이 아니다 — 그 비율의 첫 실측이
  10-06 이다. 기대는 「STALE 은 부팅당 1 건」이고, 더 많으면 poll/신선도 예산이 어긋난
  것이다(#807 형태).
- `append_errors` — 0 이 아니면 저널 쓰기가 실패하고 있다(보고서는 그래도 남는다).
- ⚠ **`baseline_evidence_seq: -1` 과 `genesis: false` 가 함께 나오면 genesis 가 아니다.**
  드라이버의 기준선 조회는 **DB 부재 · 빈 테이블 · `DatabaseError` 셋 다**에서 −1 을 돌려주는데,
  `genesis` 는 파일 존재만 본다. 둘이 어긋났다는 것은 **파일은 있는데 읽히지 않았다**는 뜻이고,
  그 상태에서는 그날 델타가 「전부 새 행」으로 보인다. 손으로 센다:
  `sqlite3 "file:$DATA/evidence.sqlite3?mode=ro" "SELECT COUNT(*), MAX(seq) FROM entries;"`.
- `evidence_schema_after.user_version == 2` · `matches_expected_v2: true`
- ⚠ **`report.json` 이 없어도 증거는 남아 있다.** 보고서는 드라이버가 마지막에 쓰는 파일이고,
  증거는 런타임이 그 전에 이미 커밋했다. 확인은 sqlite 로 직접 센다:
  `sqlite3 "file:$DATA/evidence.sqlite3?mode=ro" "SELECT COUNT(*), MAX(seq) FROM entries;"`.

**3. data dir 성장** — `du -sb ~/.local/state/tos/paper-data`.

| 숫자 | 출처 | 성격 |
| --- | --- | --- |
| ≈ **200 MB/일** (수집기 5 s) | 2026-09-28 15 분 실측을 **× 28 환산**. 세 파일 합 **7.1 MB**(증거 증가 대응 계획 §1 의 표) · data dir 전체 **7.2 MB**(이 런북 §5 ④) — 둘 다 ≈ 200 | **환산값 — 전 세션 실측 없음.** 10-06 이 첫 실측 |
| 기대 폭 | — | 장 길이·수집기 지연·휴장 반일 등으로 **150–250 MB** 를 정상으로 본다 |
| ≈ **112 MB/일** (수집기 off) | `TIME_HEALTH_SNAPSHOT` 이 증거 바이트의 75 %(3.99/5.33 MB, 계획 §1) → 3.99 × 28 | **유도값 — 측정한 적 없다** |

**4. 콜드 백업 결과** — 전날 18:00 의 텔레그램 줄(`verdict`/`refused`/`failed`)과
`~/.local/state/tos/cold-backup.log`. **그 cron 도 아직 미설치다**(§7.7).

### 7.9 드라이런 기록 — 2026-10-03 (장 마감일 · 스크래치 data dir)

운영자 검토 전이라 cron 은 설치하지 않았고, 상주 data dir 은 건드리지 않았다(§7.6 — 지금도
없다). 아티팩트는 **`~/.local/state/tos/paper-sessions/2026-10-03-*/`** 와 날짜 로그
**`~/.local/state/tos/paper-logs/2026-10-03.log`** 에 있다.

**범위.** 그날 래퍼 `start` 는 **16 회** 돌았고(그중 4 회는 SKIP·ABORT 로 부팅 전에 끝났다),
부팅까지 간 **12 세션 전부 `verdict: ok` · rc 0** 이다. 래퍼는 리뷰 대응 중에 바뀌었으므로
**다섯 리비전**이 로그에 찍혀 있다(`=== tos-paper-session start … sha256=` 줄).
**아래 ①–③ · E4 · S1 · S2 · E2 · E3 가 그 재측정이다.** 라벨은 처분 항목과 1:1 이 아니다 —
①=E1 의 1차 부팅, ②=E1 의 2차 부팅 + E5(계산된 마감), ③=기준선 −1 확인이다. 처분 **S3–S6**
(천장 통합 · 드라이버 예외/신호 · digest 패턴 · 방향 검증)은 별도 실행이 없고 ①②와 E3 의
경로 안에서 함께 돈다. 출하본 두 개:

```text
tos-paper-session.sh  e169e23d4ee190a5c42120d825922b098f5c1868ec8a22163dc35d385a5b86b8
tos_paper_session.py  995ada06d795ba1fd7d988e6b2c83793c1173c3adeeb85a59d33e379d85179b2
```

⚠ **①②·E4·S2·S1 은 그 직전 리비전**(`f452ee0b…` / `b28c188f…`)**에서 돌았다.** 그 뒤의 변경은
텔레그램 본문 로깅(H1) · 헤더 한 줄 · `grep -qxF` · 주석 하나 · 드라이버의 `except` 한 줄이고,
**부팅·정지·스키마·델타 경로를 건드리지 않는다.** 그 리비전들에서 다시 돈 것은 **H1 재실행**과
**E2·E3** 다(아래). 두 리비전의 차이는 `diff` 로 확인할 수 있다.

워크트리는 `origin/main` `36c2a7ccb6b3`(그날 main 이 `aae1cec6` 에서 움직였다).

**① (=E1 1차) genesis + 마감 정지** — `2026-10-03-142657-LONG/`

```text
2026-10-03 14:26:55 worktree …/wt-paper @ 36c2a7ccb6b3 (detached origin/main)
2026-10-03 14:26:55 calendar: 2026-10-06 is a trading day (both files agree)
2026-10-03 14:26:57 digests: match release.yaml (code 38d85110211c… deps 20559763a113…)
boot proof: OK · boot 2.0s · genesis=True · rev 36c2a7ccb6b3 · A05610
verdict ok rc=0 stop=deadline (14:26:57→14:27:38 KST)
evidence schema user_version=2 v2-shape=True
run.log tail: run: stopped (signal received).
```

`evidence_schema_after` 는 §4-A 의 기대 목록과 **글자 그대로 일치**했다:

```json
{"user_version": 2, "schema_ledger": ["2|CREATED"],
 "objects": ["index|entries_kind_seq", "table|entries", "table|outbox", "table|schema_ledger",
             "trigger|entries_no_delete", "trigger|entries_no_update",
             "trigger|schema_ledger_no_delete", "trigger|schema_ledger_no_update"],
 "matches_expected_v2": true}
```

네 스토어의 `user_version` 은 `evidence=2 · rcl=2 · inbox=1 · marketfeed=1` 이다(§4-A ⚠ —
스토어마다 목표 버전이 다르다). `TOS_PAPER_FAKE_DATE=2026-10-06` 을 썼다(장 마감일이라
10-06 의 달력 경로를 보려고). 수집기 5 s, `TOS_PAPER_MINUTES=0.6`.

**② (=E1 2차 + E5) 재부팅(같은 디렉터리) + 밖에서 온 정지 + 계산된 마감** — `2026-10-03-142755-LONG/`.
**상주의 둘째 날 경로**가 이것이다. 여기서는 `TOS_PAPER_MINUTES` 를 **주지 않았다** —
마감을 래퍼가 15:45 에서 계산한다(**E5**).

아래는 날짜 로그에서 **발췌**한 것이다(중간 줄 생략 `…`, 줄 병합 없음).
`--- status ---` 두 줄만은 날짜 로그가 아니라 **드라이런 스크립트의 stdout**
(`status` 하위 명령은 `log()` 를 쓰지 않고 표준출력에 찍는다)이고, 그 전문은 작업 기록
`/tmp/…/scratchpad/ops-paper/e1b.sh` 의 실행 출력에 있다.

```text
2026-10-03 14:27:55 safety deadline: 92 min (stop cron 는 15:45 KST · 마감은 그보다 뒤)
2026-10-03 14:27:55 driver pid=16147
driver: boot proof OK — rev=36c2a7ccb6b3 instrument=A05610
  activation=ACTIVATED 5 (re-derived in a fresh process) genesis=False baseline_seq=17 boot_s=2.0
…
2026-10-03 14:28:55 stop: SIGTERM -> driver pid=16147 (it forwards SIGTERM to run and waits)
2026-10-03 14:29:00 === driver exited rc=0
2026-10-03 14:29:00 notify SUPPRESSED by TOS_PAPER_NOTIFY=0 — 보낼 내용은 아래 로그에 그대로 있다
2026-10-03 14:29:00 notify-body: TOS paper 상주 세션 종료 (2026-10-03 LONG) rc=0
boot proof: OK · boot 2.0s · genesis=False · rev 36c2a7ccb6b3 · A05610
verdict ok rc=0 stop=signal (14:27:55→14:29:00 KST)
관측 덧붙임 11 · 소비 0 · 스냅샷 +0 · STALE 0 (n/a)
결정 none · 증거행 +19
evidence schema user_version=2 v2-shape=True
data dir 0.2 MB (+0.0 MB today)
2026-10-03 14:29:01 stop: driver exited
```

(stdout 쪽)

```text
--- status ---
running: driver pid=16147  run pid=16653  data=…/e1-data
```

`genesis=False`, 기준선 `seq=17`(①이 18 행 = seq 0–17 을 남겼다), 그 **뒤에** 정책 결속
다섯 종류가 다시 생겼고(`REPLAY_VERDICT_IDENTICAL` · `RECOVERY_BARRIER` 포함 — 기존 이력에
대한 리플레이가 돈다), 정지는 SIGTERM **5 초** 만에 끝났다. 92 분은 `14:27:55 → 15:45 + 15`
와 맞는다. 두 부팅 뒤 스크래치 data dir 은 **229,376 B** 였다(지웠다).

**③ 기준선 −1 (genesis 의 첫 행)** — `2026-10-03-143053-LONG/` 외 다수.
초판은 「행 없음」의 기준선을 0 으로 뒀고, `entries.seq` 가 0 부터 시작하므로 genesis 의
**첫 행(`seq=0` `TIME_SERVICE_STARTUP`)이 델타에서 빠졌다** — `store 19 행 / 델타 18 행`.
수정 뒤 모든 genesis 세션이 `baseline_evidence_seq: -1` 이고 델타 = store 다.
⚠ 세션마다 증거행 수가 조금씩 다른 것은(18 · 19) **실행 길이 차이**다 —
`TIME_HEALTH_SNAPSHOT` 이 닫힌 세션에서 60 s 마다 1 행 늘기 때문이다.

**E4 — 부팅 증명 가드의 실패 입력 (빈 커스터디 루트)** —
`2026-10-03-E4-bootproof-missing/`. 출하본 드라이버를 직접 구동했다
(`--custody-root <빈 디렉터리>`):

```text
driver: boot proof MISSING — the boot left no policy-binding row past the baseline seq -1.
run.log: run: refused — compose_paper_runtime raised KeyContinuityRefused: SqliteEvidenceStore:
         key generation continuity refused (HISTORY_UNVERIFIABLE) …
report.json: verdict=boot_proof_missing · boot_proof_ok=false · boot_proof={} · exit_code=1
driver rc=1
```

⚠ 이것은 §7.10 의 예전 주장 — 「digest 가드가 먼저 잡으므로 부팅 증명 가드만 따로 시험할 수
없다」 — 이 **거짓**임을 보인다. `release.yaml` 을 전혀 건드리지 않는 부팅 거부가 있고(§1 의
`KeyContinuityRefused`, 라벨 불일치 등), 두 가드는 **다른 프로세스**에 산다(digest 는 래퍼,
부팅 증명은 드라이버).

**S2 — 요약기의 거짓 초록** — `2026-10-03-S2-render-refused/`. 없는 `.env.mock` 을 주어
**진짜** `render_refused` 보고서를 만들었다(키 14개 · `boot_proof_ok` 없음 · `stale_ratio` 없음):

```text
출하본:  boot proof: N/A — 부팅 전 종료 · boot ?s · genesis=True · rev 36c2a7ccb6b3 · ?
         verdict render_refused rc=? stop=? …                       (요약기 rc=0)
수정 전: bp = OK                                       ← 거짓 초록
수정 전: sr 포맷에서 ValueError: Unknown format code '%' for object of type 'str'
         → 래퍼가 「요약 실패」로 떨어져 위의 거짓 OK 를 가렸다
```

**두 결함은 한 번에 고쳐야 했다** — 포맷 예외를 먼저 고쳤다면 거짓 초록이 그대로 켜졌다.

**S1 — 워크트리 재생성 가드** (출하본 래퍼, 로그 `2026-10-03.log` 14:30 대):

```text
(a) $WT 가 등록된 워크트리가 아닐 때
2026-10-03 14:30:47 ABORT — refusing to touch …/wt-empty — it exists but is NOT a registered
                    worktree of /home/deploy/project/kis_unified_sts.                 rc=2
(b) 관리 항목만 남은 상태 — 맨손 add 는 죽는다
fatal: '…/wt-stale' is a missing but already registered worktree;
use 'add -f' to override, or 'prune' or 'remove' to clear                             rc=128
(b) 같은 상태에서 출하본 래퍼는 prune 으로 복구한다
2026-10-03 14:30:51 worktree …/wt-stale @ 36c2a7ccb6b3 (detached origin/main)
verdict ok rc=0 stop=deadline (14:30:53→14:31:16 KST)
```

**E2·E3 — 달력·digest 가드의 실패 입력.**
⚠ **이 둘은 `start` 를 통해 바깥에서 주입할 수 없다.** `start` 는 달력과 digest 를 읽기
**직전에** 워크트리를 `origin/main` 에서 새로 만들고, 거기서는 두 달력이 다 있고 서로 맞으며
digest 가 핀과 맞는다. 즉 그 가드들이 지키는 것은 **미래의 `origin/main` 과 깨진 워크트리
생성**이지 오늘 주입할 수 있는 상태가 아니다. 그래서 입력은 **함수에** 먹였다. 대신 함수
본문은 베끼지 않고 출하본에서 `sed` 로 **그대로 떼어내** 돌렸다 —
`~/.local/state/tos/paper-sessions/2026-10-03-guard-harness.sh` 와 그 로그
`2026-10-03-guard-harness.log`. 따라서 아래 문자열은 **출하본 `abort()`/`log()` 의 출력**이다.

떼어낸 조각의 sha256 은 **그 로그에 함께** 적힌다(stdout 에만 찍으면 아카이브에 안 남는다):

```text
026fb6e1a835cd7c6bdd30739d44bde1f161a6ee5b0f583ed8606fe9f67044fd  _log.sh
06f5f581b8f4bfbbb88ff096bb8dffa35793e8160c9dc34c04ca4814545c74c6  _notify.sh
8d33e28266b07c3ef7227e7b880bbf9192e16c2107547a96cc3e18aa0c4318c8  _abort.sh
e1fb4f0162d59fec4fe0c0211b9c274d208509f84ddd48888ee95ae12fa05fb0  _cal.sh
691a782ed800050e6b6aaa8fae7743ea3516e0ad15688e6537d0ff79e67e1416  _digest.sh
```

`_digest.sh` 는 모양 검사뿐 아니라 **값 비교와 `abort` 까지** 포함한다 — 비교를 하네스가 다시
타이핑하면 「출하본이 여기서 abort 한다」가 재구성이 되고 아카이브에 실제 ABORT 줄이 남지
않는다. ⚠ `_log.sh` 의 범위는 한 번 틀렸었다: `log()` 가 **한 줄짜리** 함수라
`/^log() {/,/^}/` 가 다음 함수까지 삼켰고, 그래서 `notify()` 를 고칠 때마다 `_log.sh` 의
digest 가 바뀌었다. 지금 범위는 한 줄이다.

| 가드 | 입력 | 출력 |
| --- | --- | --- |
| 달력 | 2026-10-03 (실제 그날, 토) | `calendar: 2026-10-03 is a weekend (dow=6)` → rc 1 |
| 달력 | 2026-10-09 (금, 한글날) | `calendar: 2026-10-09 is a listed holiday (both files)` → rc 1 |
| 달력 | 2026-10-06 (화) | `calendar: 2026-10-06 is a trading day (both files agree)` → rc 0 |
| 달력 | 달력 파일 부재 | `ABORT — calendar file missing in the worktree: …/market_schedule.yaml` rc 2 |
| 달력 | 인위적 불일치(한쪽에만 10-06) | `calendar: ⚠ DIVERGENCE for 2026-10-06 — market_schedule.yaml=1 tos calendar.yaml=0; treating as a holiday (conservative)` → rc 1 |
| digest | `print-digests` 가 예외로 죽은 출력 | `ABORT — digest guard cannot run — CODE_NOW is not a 64-char lowercase hex digest (got '<empty>').` |
| digest | **64자인데 hex 가 아님**(`38d85110zzzz…`) | 같은 ABORT. ⚠ **옛 접두 패턴은 이것을 통과시켰다** |
| digest | 넷 다 64 hex 인데 값 불일치 | `ABORT — digest mismatch — boot would be refused (ReleaseAdmissionRefused).` rc 2 |
| 부팅 증명 | 빈 커스터디 루트 | 위 **E4** |

⚠ **날짜의 출처를 섞지 말 것.** 위 표의 달력 다섯 행은 **하네스**가 날짜를
`is_trading_day` 에 **위치 인자**로 넘긴 것이고 `TOS_PAPER_FAKE_DATE` 를 **읽지 않는다**.
다섯 중 **실제 그날은 2026-10-03 하나뿐**이다. `TOS_PAPER_FAKE_DATE` 를 쓴 것은 위 ①②
**실제 `start` 실행**이고(둘 다 `2026-10-06`), 그 사실은 로그에 ⚠ 줄로 남는다(§7.2 ⛔).

**장이 닫혀 있었으므로 틱은 소비되지 않았다** — `snapshots +0` · `events_consumed 0` ·
`stale_ratio n/a` 다. 이것은 결함이 아니라 §5 ④ 의 세션 게이트이고, **드라이런이 증명한
것은 체인의 소비 쪽이 아니라 부팅·스키마·정지·보고·달력·가드**다. 소비·결정·STALE 의
첫 상주 실측은 **10-06 장중**에 나온다.

**기동 줄 — 실제로 전달되고 로그에 남은 본문** (`2026-10-03-145743-LONG`, `--selftest`,
출하본 `e169e23d…`). 아래 두 줄은 날짜 로그의 **연속된 두 항목**이다: 보내기 직전에 찍은 본문과
그 결과.

```text
2026-10-03 14:57:48 notify-body(sending): [SELFTEST] TOS paper 상주 세션 기동 (2026-10-03 LONG)
boot proof: OK · boot 2.0s · genesis=True · rev 36c2a7ccb6b3 · A05610
activation ACTIVATED 5 (re-derived in a fresh process)
evidence schema user_version=2 v2-shape=True · baseline_seq=-1
worktree 36c2a7ccb6b3 · digests match release.yaml
data dir …/h1-data (genesis=yes) · 수집 5s · 정지 15:45 KST
실주문 0 (SYNTHETIC_FUTURES_ORDER · 모의 계좌 좌표). 로그 …/paper-logs/2026-10-03.log
2026-10-03 14:57:49 telegram notified
```

⛔ **이 줄이 이렇게 남는 것 자체가 리뷰 H1 의 처분이다.** 이 절의 1차 판은 같은 자리에
「실제 briefing 채널에 나간 본문」이라며 블록 하나를 실었는데, **그것은 전달된 본문이 아니었다.**
출처로 적은 13:52 실행(`2026-10-03-135155-LONG`)은 `TOS_PAPER_NOTIFY=0` 이라
`notify SUPPRESSED` 였고(날짜 로그), 그 억제 사본에는 `[SELFTEST] ` 접두가 **없다** — 접두는
문서를 쓰면서 **손으로 붙인 것**이다. 그날 실제로 전달된 네 줄(13:33:43 · 13:34:54 ·
13:56:00 · 13:56:36)은 `telegram notified` **라는 사실만** 남기고 **본문을 어디에도 남기지
않았다.** 즉 인용할 수 있는 전달 본문이 애초에 없었고, 그 공백을 조립으로 메운 것이다.

처분은 둘이다. (a) 래퍼가 **보내기 직전에 본문을 로그에 찍는다**(`notify-body(sending):`) —
그래서 다음부터는 전달된 줄을 **인용**할 수 있고 조립할 이유가 없다. (b) 그 변경을 담은
출하본으로 `--selftest` 를 **다시 돌려** 위 블록을 얻었다. 13:56 실행은 이제 **전달이
일어났다는 사실**의 근거로만 쓰고 본문은 인용하지 않는다.

억제된 사본은 억제된 사본이라고 적을 때에만 쓸모가 있다. 예컨대 13:52:00 의 것은 접두 없이
`TOS paper 상주 세션 기동 (2026-10-03 LONG)` 으로 시작하고, 그것이 `TOS_PAPER_NOTIFY=0`
경로가 로그에 남기는 모양이다.

### 7.10 이 런북이 답하지 못한 것

1. **관측 수집기를 상주에서 계속 돌릴 것인가 — 운영자 결정이 없다.** §7.3 은 기본 on(5 s)
   으로 두었고 그 근거는 ① 없으면 소비·결정이 0 이고 ② 증거 증가 대응 계획 §1 의 200 MB/일
   기준선이 이 조건의 값이라는 것뿐이다. 그 관측은 **합성 밴드**이고 시장 데이터가 아니다.
   끄면 하루 ≈ 112 MB(유도값)에 `TIME_HEALTH_SNAPSHOT` 만 쌓인다. **운영자가 정할 자리다.**
2. **언제까지 쌓을 것인가.** 퍼지는 트랙 B 이고 전제 다섯이 비어 있다(증거 증가 대응 계획 §4).
   디스크로는 333 GB 여유 ÷ 200 MB/일 ≈ **1,665 거래일 ≈ 6.8 년**(거래일 기준 — 달력 날짜가
   아니다)이지만, 그 파일시스템은 콜드 백업·측정 아티팩트와 **공유**이고, 먼저 걸리는 것은
   디스크가 아니라 **부팅 리플레이 시간**이다(§7.8 2). 그 곡선의 첫 실측이 `boot_seconds` 다.
3. **방향 — LONG 하나로 돈다. 운영자 결정 자리다(§7.1 ⚠).** §0 은 대칭의 증거로 양쪽을
   부팅시킨다고 적는데 상주는 한쪽만 쌓는다. LONG/SHORT 를 **같은 날** 돌리려면 두 번째
   data dir 과 두 번째 설정(`paper-config-short`)이 필요하다 — 한 디렉터리에 두 방향을 섞는
   경로는 설계에 없고, §5 ⑤ 가 적듯 **활성화 기록은 방향을 결속하지 않으므로** 섞인 corpus 는
   나중에 digest 로 갈라낼 수 없다.
4. **부팅 증명 가드는 이제 시험했다 (§7.9 E4) — 대신 남은 것은 ② 「천장 초과」 가지다.**
   600 s 를 넘겨 MISSING 이 되는 경로는 이력이 충분히 길어야 재현되므로 오늘 만들 수 없다.
   `boot_seconds` 추이가 그 전조다(§7.8 2).
5. **DST/시각 변경.** KST 는 DST 가 없고 cron 은 `CRON_TZ=Asia/Seoul` 이다.
6. **코퍼스가 커널 리비전을 가로지른다.** 래퍼는 매일 `origin/main` 에서 워크트리를 새로
   만들므로, 하루치마다 **다른 커널 바이트**가 같은 append-only 코퍼스에 쓸 수 있다.
   digest 가드는 **같은 워크트리 안의** `release.yaml` 과 대조하므로 이 변화를 **보지 못한다**
   (핀과 코드가 함께 움직이면 늘 통과한다). 콜드 백업 런북은 반대로 자기 워크트리를
   「의도적으로만」 고정한다. 지금의 대응은 `report.json` 의 `worktree_commit` 뿐이다(§7.8 2).
   **코드를 고정할지(어느 커밋에?) 날마다 따라갈지는 운영자 결정이다.**
7. **✅ 종목 롤 — 실측으로 닫았다(2026-10-03). 운영자 확인 대기 아님.** 현재 근월물
   `A05610` 의 만기는 **2026-10-08(목)** 이다(`calendar.yaml::futures_expiry` = 둘째 목요일).
   렌더가 **실행 당일** `get_front_month_code(product="mini")` 로 종목을 다시 뽑으므로(§2)
   롤은 자동이고, 그래서 물어야 할 것은 셋이었다 — **(a) 어느 날 어떤 코드가 뽑히나 ·
   (b) 만기일 세션은 무엇을 하나 · (c) 한 코퍼스에 두 종목이 섞여도 되나.** 셋 다 측정했다.

   **(a) 렌더가 뽑는 코드.** `shared/instruments/futures.py::get_front_month_code` 는
   `target_date > expiry` **일 때만** 다음 달로 넘어간다. 그러므로 **만기일 당일은 아직
   구월물**이고, 새 코드가 처음 뽑히는 날은 만기 **다음 날**이다.

   | 실행일 | 요일 | 뽑히는 코드 | 그날 부팅하나 |
   | --- | --- | --- | --- |
   | 2026-10-06 | 화 | `A05610` | 부팅 — 상주 1일째(genesis) |
   | 2026-10-07 | 수 | `A05610` | 부팅 |
   | 2026-10-08 | 목 | `A05610` | 부팅 — **만기일 당일** |
   | 2026-10-09 | 금 | `A05611` | **부팅 안 함** — 한글날(휴장 · §7.3 4 · §7.9 가드 표) |
   | 2026-10-12 | 월 | `A05611` | 부팅 — **새 종목의 첫 세션** |

   ⚠ **「3일째에 롤한다」는 틀렸다**(이 항목의 1차 판이 그렇게 적었고, 그 문장이 이 조사의
   출발점이었다). 10-08 은 아직 `A05610` 이고, `A05611` 로 렌더될 첫 세 날
   (10-09 금 · 10-10 토 · 10-11 일)은 **한 번도 부팅하지 않는다.** 롤이 증거에 처음
   나타나는 것은 **네 번째 상주 세션인 2026-10-12(월)** 이다.

   **(b) 10-08 세션 — 평소처럼 부팅하고 장중 내내 거래 위상이다. 거부도 stage-deny 도 없다.**
   `tos_runtime/calendar/phase.py::maturity_at` 은 만기일의 **마지막 정규(비자정넘김) 창이
   끝난 뒤에야** `expired` 를 뒤집는다. `krx-index-futures` 의 창은 CONTINUOUS 08:45–15:45
   이므로 경계는 **15:45:00** 이다. 배포된 `calendar.yaml` 로 실측(출력 전문은 아래 재도출):

   ```text
   instant (KST)        session_phase  effective_phase  expired  next expiry
   2026-10-08 15:44:59  CONTINUOUS     CONTINUOUS       False    2026-10-08
   2026-10-08 15:45:00  CLOSED         EXPIRED          True     2026-10-08
   2026-10-09 10:00:00  CLOSED         CLOSED           False    2026-11-12
   ```

   정지 크론이 **바로 그 15:45** 에 SIGTERM 을 보내므로(§7.4) `EXPIRED` 토큰은 **정지까지의
   몇 초**에만 닿을 수 있다. 닿든 안 닿든 **하류는 같다** — 틱 게이트가 보는 것은 위상
   토큰이 아니라 `session_context.is_open` 이고
   (`tos_runtime/marketfeed/scheduler.py::decide_tick`), `CLOSED` 와 `EXPIRED` 는 둘 다
   `is_open=False` 라 그 몇 초의 틱은 다른 날과 똑같이 `SKIPPED_SESSION_CLOSED` 다.
   유일한 차이는 `SESSION_FACTS_OBSERVED` 가 `phase: "EXPIRED"` · `expired: true` 로 **한 줄
   더** 남을 수 있다는 것뿐이고(`calendar/owner.py::_maybe_record_observed` 는 위상이나
   `expired` 가 **바뀔 때만** 적는다), **그 한 줄이 남는지는 정지와의 경합이라 보장되지
   않는다.** 다른 날 같은 자리에 남는 줄은 `phase: "CLOSED"` 다.
   10-09 는 애초에 부팅하지 않으므로 그날 증거는 **0 행**이고, 만기는 그날부터 다음 룰 월인
   **2026-11-12** 로 넘어간다(클래스가 월말까지 EXPIRED 로 남던 결함은 #799 에서 닫혔다 — §5 ④).

   **(c) 한 코퍼스에 두 종목 — 괜찮다. 방향 섞임(위 3)과 같은 문제가 아니다.**
   3 의 위험은 §5 ⑤ 「활성화 기록은 **방향**을 결속하지 않는다」에서 온 것이다. 종목은
   다르다 — **결정 계열 증거 행은 종목을 자기 안에 들고 있다.** 09-28 실측 코퍼스
   (`~/.local/state/tos/realclock-20260928T100001-LONG/data/evidence.sqlite3`)의 **사본**을
   질의한 결과(1,492 행 중 236 행):

   | 종류 | 행 | `payload.instrument_key` |
   | --- | --- | --- |
   | `DECISION_OUTCOME_EMITTED` | 114 | ✅ `{account, instrument}` |
   | `DECISION_WITHHELD` | 66 | ✅ |
   | `FLOW_HALTED` | 56 | ✅ |
   | `EVENT_CONSUMED` · `EVENT_HANDLING_STARTED` | 180 · 180 | ❌ |
   | `TIME_HEALTH_SNAPSHOT` 외 15 종 | 896 | ❌ (종목과 무관한 런타임 상태) |

   즉 **「어느 종목의 결정인가」는 나중에 행 단위로 갈라낼 수 있다** — 방향과 달리 투영이
   아니라 필드다. 부팅 행도 **간접적으로는** 갈린다: 렌더가 종목을
   `venue_constraint_policy.yaml::scope.instruments` 에 박으므로 `VENUE_POLICY_BOUND` 의
   `canonical_digest` 가 종목마다 다르다(같은 문서에 종목만 바꿔 로더를 두 번 돌린 실측:
   `a85def5d…` vs `3e9ea069…`). ⚠ **그 두 값은 자리표시 계좌로 뽑은 것이라 실제 부팅이 적을
   값이 아니다 — 「다르다」만 읽을 것.** 그리고 ⚠ `VENUE_POLICY_BOUND` **본문에는 종목
   문자열이 없다**(payload 는 `policy_id` · `policy_generation` · `canonical_digest` ·
   `activated_member_digest` · `null_shape_bounds` 뿐). 종목으로 거를 때는 결정 계열 행을
   보고, 부팅 단위로 가를 때는 digest 를 본다.

   ⛔ **인용 금지.** 위 결정 행의 `instrument_key` 는 종목과 **계좌번호**를 함께 담는다.
   §7.2 의 좌표 규율대로 증거 행을 PR·계획 문서·텔레그램에 그대로 옮겨 적지 않는다
   (이 절의 표는 종류와 개수만이다).

   **처분: 그대로 롤하게 둔다 — 코드·래퍼·설정 변경 없음.** 날마다 다시 뽑는 것이 이미
   올바른 동작이고(만기 지난 종목을 달고 부팅하는 날이 하루도 없다), 증거는 종목을
   행마다 들고 있다. 운영자가 대신 결정할 것이 남아 있다면 그것은 「섞을까 말까」가 아니라
   **「10-12 부터 data dir 을 가를까」**이고, 가르지 않는 쪽이 기본이다.

   **재도출.** (a)(b) 는 커밋된 테스트가 CI 에서 같은 사실을 고정한다 —
   `tos/runtime/tests/compose/test_deploy_config.py` 의
   `test_real_calendar_mini_october_expiry_day_before_and_after_close`(10-08 15시 CONTINUOUS /
   16시 EXPIRED) · `test_real_calendar_day_after_mini_october_expiry_rolls_to_november`
   (10-09 는 휴장 CLOSED · 다음 만기 2026-11-12) ·
   `test_real_calendar_declares_every_month_a_rule_month`. 위 표를 손으로 다시 뽑는 스크립트와
   출력은 `~/.local/state/tos/paper-sessions/` 에 있다(0600):
   `2026-10-03-front-month-roll.py` / `.out`(a·b) ·
   `2026-10-03-front-month-roll-digest.py` / `.out`(digest 분리) ·
   `2026-10-03-front-month-roll-corpus.out`(c 의 질의와 출력).
8. **달력은 2027년에 대해 fail-open 이다 — 방향을 분명히 적는다.** 두 파일 모두 2027년
   항목이 **0건**이므로(실측), 2027-01-01 이후 **모든 평일이 「거래일」로 판정된다** —
   건너뛰는 쪽이 아니라 **부팅하는 쪽으로 틀린다**. 또 `calendar.yaml:49` 는
   **2026-12-31(KRX 연말 휴장)** 을 「운영자 검토 후보 · 정본 파일에 없음」으로 적어 두었고
   두 휴장 목록 어디에도 없다 — 그날도 부팅한다. 둘 다 **휴장일 목록을 먼저 고치는 것**이
   해결이고, 래퍼가 손댈 일이 아니다.
