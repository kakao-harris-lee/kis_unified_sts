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
  ⚠ **상주(§7)에서는 이 문장이 그대로 적용되지 않는다.** 운영자 결정 2026-10-03 으로
  상주는 **LONG 매일 + SHORT 분기 1회**다(§7.10 3). 이 절은 1회성 부팅의 규율이다.
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

⚠ **PR #888 머지 직후 한 번은 `file missing from the rendered directory: RENDER.yaml` 로 rc 1**
이다(실측). 그 PR 이 상주 트리에 `RENDER.yaml` 을 더했고 `--check` 는 원천과 산출의 **파일 목록**을
비교하는데, 그 전에 렌더된 디렉터리에는 그 파일이 없다. **고장이 아니라 낡은 산출물**이고, 다음 렌더가
원천 전체를 다시 복사하면 사라진다 — 래퍼가 매일 08:45 에 렌더하므로 (런북 §7.10 6) 다음 세션에서
저절로 해소된다. 자동화가 `--check` 를 돌리는 곳은 없다(드라이버·cron 모두 호출하지 않는다, 실측)
— 이 한 줄은 그 사이에 손으로 돌려 보는 운영자를 위한 것이다. 지금 바로 없애려면 그냥 다시 렌더한다.

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
DATA=~/.local/state/tos/paper-oneshot-$(date +%Y%m%d)   # 저장소 밖 · 일회성 자기 디렉터리
mkdir -p "$DATA"
# ⛔ 상주 부모 ~/.local/state/tos/paper-data 도, 그 밑의 잎 paper-data/<종목> 도 여기 쓰지 않는다
#    (§7.2·§7.6, 2026-10-04). 부모에 스토어를 만들면 콜드 백업의 잎 열거 밖이고(백업 안 됨),
#    잎에 일회성 세션을 섞으면 상주 코퍼스가 오염된다. 일회성은 자기 디렉터리에서 genesis 한다.
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

### 4-A-1. 실행 기록 — 2026-10-02 dry-run, 이후 사이드카 추가 기록 10-03·10-04 (사본에서 실행 · 실 corpus 본체 불변)

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
⚠ **위 네 시각은 2026-10-02 당시의 값이고 지금은 더 이상 현재값이 아니다.** 같은 사이드카가
그 뒤 두 번 더 쓰였다 — 10-03 콜드 백업 증명(아래 ✅ 문단)과 10-04 리뷰(같은 문단 끝).
**mtime 은 누적 기록이 아니라 마지막 접근만 남긴다**; 어느 작업이 언제 썼는지는 시각이
아니라 그 작업의 기록으로 짚어야 한다.

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

✅ **운영자 결정 2026-10-03 — 사이드카는 그대로 둔다. 이 항목은 닫혔다.** 그 뒤 콜드 백업
증명이 같은 방식으로 `-shm` 을 한 번 더 썼다: A1 기준 corpus
`~/.local/state/tos/realclock-20260928T110001-LONG/data` 의 네 `-shm` 이 **2026-10-03
14:46:57–58** 로 갱신됐고(`mode=ro` 의 `.backup` 사본 뜨기 — `immutable=1` 이 아니라 위
실측 그대로다), **본체 네 파일은 복사 전후 sha256 이 같았으며 `-wal` 은 건드리지 않았다**.
⚠ 이 네 시각과 해시는 **콜드 백업 런북 §4-5-5 의 기록을 옮겨 적은 것**이고 그 절이 정본이다
(해시 전문과 로그 줄 번호가 거기 있다) — 두 곳이 갈리면 §4-5-5 를 믿는다.
운영자 결정은 **그 네 사이드카를 지우지 않고 그대로 둔다**는 것이다 — 다음 조사가 이
mtime 을 보고 이 항목을 다시 열지 않도록 여기에 적는다.
⚠ **2026-10-04 추가 — 세 번째 작업이 또 사이드카를 썼다. 이번엔 런타임이 아니라 리뷰다.**
PR #856 리뷰 중 한 렌즈가 `~/.local/state/tos/realclock-20260928T100001-LONG/data`
(09-28 **10:00** 세션 코퍼스 — 이 절이 다루는 11:00 세션 코퍼스와 **다른 디렉터리**다)를 열어
`-shm` **둘**(`evidence` · `inbox`)을 다시 썼다. 실측 mtime **2026-10-04 07:39:35**
(리뷰가 보고한 07:36:07 보다 뒤다 — 같은 리뷰 안의 더 나중 접근으로 보이며, **이 런북은
직접 잰 값을 적는다**). **본체 네 파일은 불변**(mtime 2026-09-28 10:15 · 크기 그대로),
`-wal` 도 불변, `marketfeed`/`rcl` 의 `-shm` 은 10-02 값 그대로다.
⛔ **이것은 이 절이 금지한 바로 그 접근이다** — `immutable=1` 없이 열면 읽기만 해도
`-shm` 을 쓴다. 런타임이 아니라 **조사·리뷰 과정**이 위반했고, 다음 조사가 이 mtime 을
보고 「런타임이 건드렸다」로 읽지 않도록 여기에 적는다. **사이드카는 그대로 둔다**
(운영자 결정 2026-10-03 과 같은 처분).
⚠ 날짜만 보고 주인을 짐작하지 말 것(`MEMORY.md` 의 earlyoom 교훈과 같은 형태): 10-02
15:48·15:55 는 v1 조사, 10-03 14:46 은 콜드 백업 증명(09-28 **11:00** 세션 코퍼스),
10-04 07:39 는 PR #856 리뷰(09-28 **10:00** 세션 코퍼스)다 — **셋 다 다른 작업이고 두
코퍼스는 서로 다른 디렉터리다.**

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
런타임의 `~/.local/state/tos/paper-data`** 다(2026-10-06 genesis 예정 — 2026-10-04 개정으로
그 디렉터리는 **부모**이고 래퍼가 밑의 계약월 잎을 순회한다, §7.7). 같은 날
**16:13 KST 에 운영자가 crontab 줄도 넣었으므로**(`0 18 * * 1-5` · `CRON_TZ=Asia/Seoul` ·
§7.7), **남은 것은 그 genesis(10-06) 하나다**(ops-paper 레인). 이 문단은 한동안 「남은 것
둘」이라고 적고 있었고 16:13 뒤로 거짓이었다 — PR #855 가 정정했다. 호스트에 무엇이 있고 켜는 데
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
  한 방향뿐**이라는 것은 그 자체로 기록할 변화다. **운영자 결정 2026-10-03 으로 닫혔다 —
  LONG 단독 유지 + SHORT 부팅증명 분기 1회(§7.10 3).**
- ⚠ **바뀌는 것 (2) — 코드가 날마다 움직인다.** 래퍼는 매일 아침 `origin/main` 에서
  워크트리를 새로 만든다. 그래서 **하나의 append-only 코퍼스가 여러 커널 리비전에 걸친다.**
  §7.10 6 을 볼 것.

### 7.2 경로 · 좌표 규율 · 환경 손잡이

| 무엇 | 어디 | 비고 |
| --- | --- | --- |
| 상주 durable set — **부모** | `~/.local/state/tos/paper-data` | **계약월 잎들의 부모**(운영자 결정 2026-10-04 · §7.10 7 (c)). 첫 기동 때 래퍼가 `umask 077` 로 만들고 기동·종료 때 `chmod 700`. 스토어는 여기 바로 밑에 **없다** — 잎 안에 있다 |
| 상주 durable set — **잎** | `~/.local/state/tos/paper-data/<종목>` (지금 `A05610` · 2026-10-12 부터 `A05611`) | **그 잎의 첫 세션 genesis 가 만든다**(§7.6) · **0700**(디렉터리) · **0600**(스토어 넷) — 기동 시 `umask 077` + 종료 뒤 `chmod 700` 으로 보장한다(✅ 2026-10-04 적용 — 패치 실측 §7.2-a 는 잎 이전 판 `a898e6cb` 의 것이고, 잎 트리의 모드 실측은 §7.9-leaf). 결정 레코드가 계좌번호를 평문으로 싣기 때문이다. 종목은 래퍼가 `get_front_month_code(product="mini")` 로 **한 번** 계산해 렌더 `--instrument` 와 잎 경로 **둘 다**에 준다(§7.3 5-a) |
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
**유출된 지문은 유출된 계좌번호로 취급한다.** 그러므로 **좌표를 담는 여섯 트리**
— `~/.config/tos/paper-config`(렌더 산출물) · `~/.local/state/tos/paper-custody`(자격증명) ·
`~/.local/state/tos/paper-sessions`(`render.log`) · `~/.local/state/tos/paper-logs`(래퍼 로그) ·
`~/.local/state/tos/paper-ops`(PID·백업 설정) · **`~/.local/state/tos/paper-data`(증거 — 잎
`<종목>` 까지 — 결정 행이 계좌번호를 평문으로 싣는다, §7.2-a)** — 는 전부 저장소 밖 **0700**(실측)이고, **`render.log` · 증거 행 · 질의 결과를 PR·계획 문서·텔레그램으로 옮겨
적지 않는다**(이 런북의 인용은 전부 지문·계좌가 없는 줄만 고른 것이다). `.env.mock` 은
`$MAIN` 의 것을 **절대경로로 넘긴다 — 워크트리로 복사하지 않는다**(§7.3 1). 텔레그램 토큰은
`$MAIN/.env` 의 두 줄만 `grep` 으로 읽고 로그에 내보내지 않는다.

**환경 손잡이 (전부 열한 개 + 플래그 하나).** ⛔ 표시는 **드라이런 전용이고 cron 줄에 절대
넣지 않는다** — 넷 다 무인 레인의 안전장치를 끈다(마지막 것은 종목 자동 계산을 덮어쓴다).

| 손잡이 | 기본값 | 무엇을 하나 |
| --- | --- | --- |
| `TOS_PAPER_DATA_DIR` | `~/.local/state/tos/paper-data` | 상주 durable set 의 **부모**. 잎은 `$TOS_PAPER_DATA_DIR/<종목>` 이고 이 손잡이로 잎을 직접 지정할 수는 없다 |
| `TOS_PAPER_STOP_HHMM` | `15:45` | 정지 시각(KST). 안전망 마감 계산의 기준 |
| `TOS_PAPER_APPEND_EVERY_S` | `5` | 관측 수집 주기(초). `0` 이면 수집기 OFF(§7.3) |
| `TOS_PAPER_DIRECTION` | `LONG` | `LONG`\|`SHORT`. 그 밖의 값은 ABORT |
| `TOS_PAPER_NOTIFY` | `1` | `0` 이면 텔레그램을 보내지 않고 **보낼 본문을 로그에 적는다** |
| `TOS_PAPER_WT` | `~/.local/state/tos/measure/wt-paper` | 분리 워크트리 경로 |
| `TOS_PAPER_BOOTPROOF_CEILING_S` | `600` | 부팅 증명 천장. 래퍼는 여기에 +30 s 를 기다린다(§7.3 7) |
| ⛔ `TOS_PAPER_IGNORE_CALENDAR` | (없음) | `1` 이면 **휴장·주말 검사를 통째로 끈다** |
| ⛔ `TOS_PAPER_FAKE_DATE` | (없음) | 달력 검사만 이 날짜로 본다 |
| ⛔ `TOS_PAPER_MINUTES` | (없음) | 안전망 마감을 직접 준다 — **§7.3 6 의 「마감이 지났다」 검사를 건너뛴다** |
| ⛔ `TOS_PAPER_INSTRUMENT_OVERRIDE` | (없음) | 종목 자동 계산(`get_front_month_code`)을 이 값으로 덮어쓴다 — 렌더와 잎 경로 **둘 다**에 같은 값이 간다. `^A0[0-9]{4}$` 가 아니면 ABORT. 쓸 데는 하나뿐이다: 드라이런에서 **다음 월물 잎의 genesis** 를 미리 밟아 보는 것(§7.9-leaf BOOT2) |
| `--selftest` (플래그) | — | 텔레그램 줄에 `[SELFTEST] ` 접두 |

#### 7.2-a ✅ 상주 data dir 은 0700 이다 — 패치 2026-10-04 07:08 · 실측 07:12 KST

이 표의 1차 판은 상주 data dir 을 **0755 로 두어도 된다**고 적고 그 근거로 「증거는 계좌
지문을 담지 않는다」를 들었다. **그 근거는 틀렸다.** 증거가 담지 않는 것은 *지문*이고,
**결정 계열 행은 계좌번호를 평문으로 담는다**:

- `DECISION_OUTCOME_EMITTED` · `DECISION_WITHHELD` · `FLOW_HALTED` 의 payload 에
  `instrument_key: {account, instrument}` 가 있다(09-28 **10:00 세션** 코퍼스 실측 —
  1,492 행 중 236 행. ⚠ 같은 날 **11:00 세션** 코퍼스(§4-A-1 의 A1 기준 corpus)와 다른
  디렉터리다 — 둘 다 「09-28 코퍼스」로 부르면 행 수가 안 맞는다.
  질의와 개수는 §7.10 7 (c)).
- 즉 지문보다 **나쁘다.** §2 는 지문을 두고 「유출된 지문은 유출된 계좌번호로 취급한다」고
  적는데, 여기 있는 것은 취급의 문제가 아니라 **계좌번호 그 자체**다.
- 그러므로 상주 data dir 은 §7.2 의 **좌표를 담는 트리**이고, 다른 다섯과 같은 **0700** 이어야
  한다. 「공유 호스트이므로 운영자가 좁힐 수 있다」는 선택이 아니라 **요건**이었다.

**왜 umask 인가.** 런타임은 디렉터리를 만들 때 모드를 지정하지 않고
(`tos_runtime/operations/*.py` 의 `mkdir` 전부 모드 인자 없음) sqlite 도 마찬가지라,
**실제 모드는 프로세스 umask 가 정한다.** 09-27/28 코퍼스 열두 개가 그 증거다 —
디렉터리 `drwxrwxr-x`(0775) · 본체 `-rw-r--r--`(0644), 곧 당시 umask 002 다.

**적용된 변경 (운영자 승인 2026-10-04).** 저장소 파일이 아니라
`~/.config/kis-probes/tos-paper-session.sh`(비커밋 · mode 700) 두 곳이다. 이전 판 백업은
`~/.config/kis-probes/tos-paper-session.sh.bak.e169e23d`, 새 sha256 은
**`a898e6cb1f2f75d078d91a4cc53ebd0054fa5056316fe073f293da995ce74a8f`**(§7.9 머리 ⚠).

1. **드라이버 기동만** `umask 077` 로 감쌌다. ⛔ **전역으로 걸지 않는다** — `$WT` 분리
   워크트리는 이 표가 **의도적으로 0755** 라고 적은 공개 트리다(좌표를 담지 않는
   `origin/main` 내용). 서브셸 + `exec` 라 `$!` 가 그대로 드라이버 PID 이고
   `wait`/`kill`/pidfile 경로가 **바뀌지 않는다**:

   ```bash
   ( umask 077; exec "$PY" "$DRIVER" \
       --worktree "$WT" --main-repo "$MAIN" \
       ... \
       --pidfile "$PIDFILE" ) >>"$LOG" 2>&1 &
   DRV=$!
   ```

   ⚠ **「`$WT` 는 0755 로 남는다」는 체크아웃 디렉터리에 대해서만 참이다.** `git worktree
   add` 는 래퍼 본체(umask 밖)가 돌리므로 `$WT` 자신은 **0755** 그대로지만, 그 **안에서
   드라이버가 새로 만드는 것**은 umask 를 탄다 — 실측(2026-10-04 07:12): `$WT` 는 `755`,
   그 아래 드라이버가 만든 `__pycache__` 셋은 **`700`**. 공개 트리의 모드는 지켜졌고
   드라이버 산출물만 좁혀졌으니 의도대로지만, **「워크트리는 전혀 손대지 않는다」로 읽으면
   틀린다.**

2. 드라이버가 끝난 뒤(`log "=== driver exited rc=$rc"` 바로 다음) 멱등하게 조인다 —
   **만들지는 않는다**(genesis 전에 디렉터리를 만들면 §4-A 의 「빈 스토어 넷」 사고가 된다):

   ```bash
   [ -d "$DATA" ] && chmod 700 "$DATA" 2>/dev/null || true
   ```

**실측 (스크래치 data dir · 세션 `2026-10-04-071204-LONG` · `verdict ok` rc 0 · genesis=True).**
출하본 `a898e6cb…` 을 `TOS_PAPER_DATA_DIR=<scratch>/data TOS_PAPER_MINUTES=1
TOS_PAPER_IGNORE_CALENDAR=1 TOS_PAPER_NOTIFY=0 … start --selftest` 로 돌린 뒤
`stat -c '%a %n'` — 넘긴 값이 아래 표의 `<scratch>/data` **바로 그 디렉터리**다(경로만
줄였다). **아티팩트**: `~/.local/state/tos/paper-sessions/2026-10-04-071204-LONG/modes.out`
(0600 · 아래 두 블록의 출처):

```text
700 <scratch>/data
600 <scratch>/data/evidence.sqlite3
600 <scratch>/data/evidence.sqlite3-shm
600 <scratch>/data/evidence.sqlite3-wal
600 <scratch>/data/inbox.sqlite3
600 <scratch>/data/marketfeed.sqlite3
600 <scratch>/data/marketfeed.sqlite3-shm
600 <scratch>/data/marketfeed.sqlite3-wal
600 <scratch>/data/rcl.sqlite3
```

**부수 효과 — 세션 아티팩트도 0600 이 됐다.** 드라이버가 같은 umask 아래 돌므로
`$SESSION_DIR` 의 네 파일도 함께 조여졌다. 같은 호스트의 전후 대조(패치 전 10-03 · 후 10-04):

```text
644 …/2026-10-03-145743-LONG/render.log      (패치 전)
600 …/2026-10-04-071204-LONG/render.log      (패치 후)
```

§7.2 가 「`render.log` 는 계좌 지문을 찍는다」고 적는 바로 그 파일이므로, 이것은 덤이 아니라
같은 결함의 두 번째 면이다(디렉터리는 이미 `chmod 700` 이었고 **안의 파일이 0644 였다**).

⚠ **그리고 패치는 과거를 고치지 않는다.** 2026-10-04 현재 `paper-sessions` 아래
`render.log` 는 **0600 두 개 · 0644 열다섯 개**다(실측) — 열다섯은 패치 전 세션들이고
**그대로 0644 로 남아 있다.** 상위 디렉터리가 0700 이라 다른 사용자는 traversal 로 막히지만,
모드 자체를 맞추려면 한 번 돌린다:

```bash
chmod 600 ~/.local/state/tos/paper-sessions/*/render.log
# 확인: 0644 가 0건이어야 한다
find ~/.local/state/tos/paper-sessions -name 'render.log' -perm -004 | wc -l
```

운영자 판단 자리라 이 레인은 돌리지 않았다(남의 세션 아티팩트의 모드를 바꾸는 일이다).

⚠ **남은 경계 하나.** 2 의 `chmod` 는 **디렉터리만** 조인다. 이 패치보다 **먼저** genesis 가
일어났다면 안의 파일은 0644 로 남는다 — 공유 호스트에서 실질 차단은 디렉터리 traversal 이라
그래도 막히지만, 되돌리려면 운영자가 한 번
`chmod 600 ~/.local/state/tos/paper-data/*/*.sqlite3*` 를 손으로 돌린다 — **잎 한 단계 아래의
파일**이다. ⛔ `paper-data/*` 는 잎 **디렉터리**에 맞으므로 거기에 600 을 걸면 진입이 막힌다
(이 줄의 1차 판이 그렇게 적혀 있었다 — 평면 배치 때 쓴 글로브). **이번에는 해당하지 않는다**:
`~/.local/state/tos/paper-data` 는 2026-10-04 현재 **아직 없고**(실측) genesis 는 10-06 이라
패치가 먼저다.

#### 7.2-b CP-3 tenant durable set — **지정만 했다 (2026-10-09) · 디렉터리는 없다**

§7.2 의 표는 **상주 배포**의 것이다. CP-3 첫 tenant(Setup D)는 kickoff 결정 3·4 대로
**방향마다 따로** 돌므로 자기 durable set 과 자기 렌더 산출물을 갖는다. 이 절은 그
**이름을 지정**하는 자리이고, 아래 어느 디렉터리도 **아직 만들지 않았다** — genesis 는
그 잎의 **첫 부팅**이다(§7.6 과 같은 규율; CP-3 kickoff §5 3 ④ 는 미착수).

| 배포 | durable set **부모** | **잎** | 렌더된 설정 | 콜드 백업 **ops**(`COLD_CONFIG_DIR`) | 콜드 **보관소 부모**(`COLD_ROOT`, 유도) |
| --- | --- | --- | --- | --- | --- |
| 상주 paper | `~/.local/state/tos/paper-data` | `paper-data/<종목>` | `~/.config/tos/paper-config` | `~/.local/state/tos/paper-ops` | `~/.local/state/tos/paper-cold` |
| CP-3 tenant **LONG** (`config/tos_runtime/cp3-setup-d-long/`) | `~/.local/state/tos/cp3-setup-d-long-data` | `cp3-setup-d-long-data/<종목>` | `~/.config/tos/cp3-setup-d-long-config` | `~/.local/state/tos/cp3-setup-d-long-ops` | `~/.local/state/tos/cp3-setup-d-long-cold` |
| CP-3 tenant **SHORT** (`config/tos_runtime/cp3-setup-d-short/`) | `~/.local/state/tos/cp3-setup-d-short-data` | `cp3-setup-d-short-data/<종목>` | `~/.config/tos/cp3-setup-d-short-config` | `~/.local/state/tos/cp3-setup-d-short-ops` | `~/.local/state/tos/cp3-setup-d-short-cold` |

⚠ 뒤 두 열은 **콜드 백업을 켤 때 필요한 지정**이고, 켜는 것 자체는 운영자 결정이다(아래 ⛔
문단). `COLD_ROOT` 는 환경변수가 아니라 그 ops 디렉터리의 `evidence_cold_backup.yaml` 세
경로가 **공유하는 부모**로 유도되므로, tenant 보관소를 가르는 유일한 수단은 그 세 경로를
tenant 콜드 부모 아래에 적는 것이다.

**이름 규칙은 「설정 트리 이름 + `-data` / `-config`」다** — data dir 이름을 설정 트리
이름에서 **도출할 수 있어야** 어느 코퍼스가 어느 트리로 부팅됐는지 경로만 보고 알 수 있다
(§5 ⑤: 활성화 기록은 방향을 결속하지 않으므로 경로가 그 역할을 한다).

**모드·규율은 상주와 같다**: 부모·잎 디렉터리 **0700**, 스토어 파일 **0600**(결정 레코드가
계좌번호를 평문으로 싣는다 — §7.2-a), 렌더된 설정 디렉터리 **0700**, 전부 저장소 밖.

⛔ **방향을 한 data dir 에 섞지 않는다. 상주 잎에도 절대 섞지 않는다**(§7.10 3). 섞인
코퍼스는 §5 ⑤ 때문에 나중에 digest 로 갈라낼 수 없다. 그래서 LONG·SHORT 는 **부모부터**
다르다 — 같은 부모 아래 `long/`·`short/` 두 잎을 두는 배치를 쓰지 않은 이유는 그 부모가
콜드 백업 래퍼에게 「계약월 잎들의 부모」로 보이고, 그 래퍼의 잎 열거는 `A0####` 패턴
하나뿐이기 때문이다(아래).

⚠ **콜드 백업에는 아직 들어 있지 않다 — 운영자 결정 자리다.** 실측(2026-10-09):
- 래퍼 `~/.config/kis-probes/cold-backup-nightly.sh` 는 `COLD_DATA_DIR`(기본
  `~/.local/state/tos/paper-data`)의 **직접 자식**만 훑고 `A0[0-9][0-9][0-9][0-9]` 에 맞는
  디렉터리만 잎으로 센다. 나머지는 `STRAY` 경고 한 줄이다. **`~/.local/state/tos/*` 를
  글로브하는 코드는 없다.** 그러므로 위 두 부모는 오늘 래퍼에게 **보이지 않는다** —
  백업되지 않는다.

⛔ **켜는 것은 「`COLD_DATA_DIR` 만 바꿔 한 번 더 돌리기」가 아니다 — 그렇게 하면 tenant
아카이브가 상주 콜드 보관소에 섞인다**(2026-10-09 리뷰 H1, 래퍼 텍스트 재확인).
`COLD_DATA_DIR` 만 바꾼 실행은 나머지를 **기본값 그대로** 쓴다:

| 래퍼 변수 | 기본값 / 유도 | 결과 |
| --- | --- | --- |
| `COLD_CONFIG_DIR` | `/home/deploy/.local/state/tos/paper-ops` (`:132` `CONFIG_DIR=${COLD_CONFIG_DIR:-…}`) | 잎별 파생 설정이 **상주** `paper-ops/leaves/<잎>/` 에 쓰인다 (`:443` `LEAF_CFG_DIR="$CONFIG_DIR/leaves/$leaf"`) |
| `COLD_ROOT` | 환경변수가 **아니다** — 기준 설정 `$CONFIG_DIR/evidence_cold_backup.yaml` 의 `backup_root`·`archive_dir`·`verify_root` 가 **공유하는 부모**로 유도된다 (`:345`·`:353-370`; 셋이 한 부모가 아니면 거부) → 상주 기준 설정에서는 `~/.local/state/tos/paper-cold` | 잎별 보관소가 **상주** `paper-cold/<잎>` 이다 (`:444` `LEAF_ROOT="$COLD_ROOT/$leaf"`) |
| `COLD_TARGET_BORN_ON` | `2026-10-06` (`:131`) | **그 날 이후**이므로 genesis 전인 tenant 부모는 PRE-GENESIS(rc 0)가 아니라 **`refused`(rc 1)** 다 |

**충돌의 기계장치는 `:443-444` 다.** 그 두 경로는 **잎 이름만**으로 키를 잡는다 —
`LEAF_CFG_DIR="$CONFIG_DIR/leaves/$leaf"` · `LEAF_ROOT="$COLD_ROOT/$leaf"`. 그리고 잎 이름은
**계약월**(`A05611` 등)이므로 상주·tenant LONG·tenant SHORT 세 배포가 **같은 잎 이름**을
갖는다. 즉 위 기본값대로 돌리면 셋이 전부 `paper-ops/leaves/A05611` 과 `paper-cold/A05611`
**같은 두 자리**로 해석된다.

그래서 무엇이 되는가는 **동시성에 달려 있다** — 둘을 구분해 적는다:

- **직렬(기본)**: 기본 락은 `:135` `LOCK=${COLD_LOCK:-…nightly.lock}` 로 **공유**이므로
  tenant 실행과 야간 실행은 겹치지 않는다. 그러면 거부는 나지 않고 **섞인다**: 세 배포의
  아카이브가 한 보관소에 쌓이고 세대 번호가 **하나의 카운터**에서 나오므로(세대는
  `backup_root` 단위 — `:49-51`) 어느 세대가 어느 배포의 것인지 보관소만 보고 가를 수 없다.
  더해서 잎별 파생 설정은 **매 실행 재생성**되므로(`:54`) 그 자리를 공유하면 마지막 실행의
  좌표가 앞 실행의 것을 덮는다.
- **동시(락을 우회했을 때만)**: `:49-55` 가 그 결과를 적는다 — 「잎 둘이 한 `backup_root` 를
  공유하면 **같은 밤에 둘 다 같은 세대 번호를 받고 둘째가 산출물 충돌로 거부된다**」.
  그 문단은 래퍼가 그래서 「**잎마다 자기 보관소와 자기 설정**」을 쓴다고 이어지는데,
  tenant 는 **배포마다** 같은 분리가 필요하고 그것을 줄 수 있는 것은 `COLD_CONFIG_DIR` 와
  그 기준 설정의 세 경로뿐이다.

ℹ️ 래퍼 헤더의 **`COLD_LOCK` 항목(`:86-92`)**은 같은 말을 **다른 계기**로 한다 — 그 항목이
경고하는 것은 「`COLD_LOCK` 을 바꿔 공유 락을 우회한 스크래치 실행이 진짜 야간 실행과
겹치는 것」이고, 그 처방도 「그 변수를 쓰는 실행은 `COLD_DATA_DIR`·`COLD_CONFIG_DIR` 도 함께
바꾼 스크래치 실행이어야 한다」다. **기본 설정으로 도는 tenant 실행에 대한 진술이 아니다** —
초판은 그 문장을 이 자리의 근거로 인용했는데 그것은 **오인용**이었다(2026-10-09 재검토).
여기서는 **유사 진술**로만 읽는다: 같은 두 자리를 공유하면 터진다는 성질이 계기와 무관하게
같다는 것.

**그러므로 tenant 콜드 백업 실행은 셋을 함께 지정한다**(아래 §7.2-b 표의 ops·cold 열):

```
COLD_DATA_DIR=~/.local/state/tos/cp3-setup-d-long-data \
COLD_CONFIG_DIR=~/.local/state/tos/cp3-setup-d-long-ops \
COLD_TARGET_BORN_ON=<그 잎의 첫 부팅일>
```

그리고 그 `cp3-setup-d-long-ops/evidence_cold_backup.yaml` 의 **세 경로는 tenant 전용 콜드
부모 아래**여야 한다(`~/.local/state/tos/cp3-setup-d-long-cold/{backups,archives,verify}`) —
래퍼가 `COLD_ROOT` 를 그 셋의 공유 부모로 유도하므로 그것이 잎별 보관소를 가르는 **유일한**
수단이다. SHORT 도 같은 꼴(`cp3-setup-d-short-ops` · `cp3-setup-d-short-cold`)이다.
`COLD_TARGET_BORN_ON` 은 **그 잎의 첫 부팅일**이어야 한다 — 기본값 2026-10-06 을 그대로 두면
genesis 전 부재가 조용한 rc 0 이 아니라 refused 로 난다.

- 상주 설정 `~/.local/state/tos/paper-ops/evidence_cold_backup.yaml` 의 세 경로는 전부
  `~/.local/state/tos/paper-cold/` 아래 **절대경로 리터럴**이고 글로브·`~` 전개가 없다.
  그 파일 자체는 tenant 실행이 건드리지 않는다(기준 파일은 읽기 전용이고, tenant 실행은
  **자기 `COLD_CONFIG_DIR`** 의 기준 파일을 쓴다). ⚠ 위 셋을 함께 바꾸지 않으면 **충돌한다**
  — 초판이 여기에 「충돌 없음」이라고 적었는데 그것은 `COLD_DATA_DIR` 만 비교한 결과였다.
- ⚠ 위 ops·cold 디렉터리도 **아직 만들지 않았다**(이 절은 지정이고 생성이 아니다).

⚠ **상주 세션 래퍼는 이 tenant 를 띄우지 못한다**(실측): `~/.config/kis-probes/
tos-paper-session.sh` 의 렌더 출력 경로 `CONFIG=/home/deploy/.config/tos/paper-config` 는
**환경 손잡이가 아니라 하드코딩**이다(`TOS_PAPER_DATA_DIR` 과 달리 덮어쓸 수 없다).
tenant 부팅은 별도 호출 경로가 필요하고 그것은 ④ 의 일이다.

⚠ **이름 인접 주의**: `~/.config/tos/paper-config-short` 가 **이미 있다** — 2026-09-28
**상주** SHORT 부팅증명 캠페인의 산출물이고(§0 의 양방향 부팅) CP-3 SHORT tenant 와 **무관**
하다. CP-3 쪽은 `cp3-setup-d-short-config` 다.

⛔ **사본 의무 — 상주 설정 파일을 바꾸는 PR 은 같은 PR 에서 tenant 사본도 갱신한다.**
두 tenant 트리는 `config/tos_runtime/paper/` 파일들의 **바이트 사본**을 들고 있다(LONG 23 ·
SHORT 22). 그 중 하나를 바꾸는 PR 은 **같은 PR 에서** 두 트리의 사본을 함께 갱신해야 한다.

⚠ 그 사본 집합에 **`release.yaml` 이 들어 있고 그 파일이 `expected_code_digest` 를 싣는다.**
런타임 코드를 바꾸는 PR 은 그 핀을 상주 트리에서만 재도출한다 — 상주 세션은 매일 재도출해
대조하므로 거기서는 드러나지만(§5 ①), **tenant 트리는 부팅한 적이 없어 낡은 핀이 드러날
레인이 없다.** 첫 tenant 부팅이 digest 불일치로 **ABORT** 한다. 이것은 §7.10 6 이 적는
「어제의 증거를 오늘의 코드로 재해석할 수 없게 만드는 변경」의 사본 판이다.

`tos/runtime/tests/compose/test_tenant_tree_copies.py` 가 이 의무를 고정한다: 사본의 **바이트
동일성** · 선언된 차이가 실제로 다른가 · 분류의 **전수성**(파일을 더하고 분류를 빼먹으면 red) ·
분류됐지만 **어느 검사도 안 하는 이름이 없는가** · `release.yaml` 은 실패 메시지가 「두
트리에서 같은 PR 에 재도출하라」고 말하도록 **따로** 단언한다.

#### 7.2-c CP-3 tenant 부팅 증명 — **스크래치에서 손으로 1회** (코드 2026-10-10 · 실행 미착수)

③(실시간 15 필드 생산자)이 없는 동안 tenant 배선을 한 번 관통시켜 보는 절차다. 계획
`docs/plans/2026-10-09-tos-cp3-tenant-render-and-boot-path-plan.md` §2.5 · §2.6 · §5 3(PR-C).
**§7.2-b 의 지정된 durable set 에는 쓰지 않는다** — 그 네 디렉터리의 첫 genesis 는 ③ 의
실데이터다. 여기서 쓰는 것은 **스크래치 data dir 하나**이고, 세션도 **한 번**이다. cron 에
넣지 않는다(첫 실제 세션은 ③ 뒤 운영자 결정).

**⚠ 무엇을 증명하고 무엇을 증명하지 않는가 — 과장하지 않는다.**
증명하는 것은 **배선**이다: 렌더(`journal.mode: external`) → 활성화 → 전략 로더 → 열다섯
필드 **선언** → 결정 경로 → 거부. 증명하지 **않는** 것은 **필드 소비**다.
tenant 트리의 `critical_input_policy.yaml::max_age_ms` 는 **800** 이고(§7.2-b 가 가리키는
운영자 결정 2026-10-09), `max_age_ms` 와 커널 시간 경로는 **같은 양**(`now_ms - as_of_ms`)을
잰다. 도구가 `as_of_ms` 를 **쓰는 시각**으로 찍어도 **쓰기와 부팅 사이가 800 ms 를 넘으면**
`_derive_field_state` 가 필드마다 `(UNKNOWN, "stale")` 를 돌려주고, 커널의 UNKNOWN 바닥이
그 키들을 떨어뜨려 R1 의 AND 가 거짓 → NO_ACTION → 송신 0 이다(fail-closed). 상주 렌더의
부팅 증명 관측이 `_JOURNAL_AGE_MS` 1000 > 800 때문에 **언제나** STALE 인 것과 같은 모양이다
(아래 §5 ④ 와 같은 절의 STALE 문단). 계획 §2.5 의 「15 필드 **소비**」라는 초판 표현은
**PR #887 에서 하향**됐다. 그러므로 이 절차의 기대 결말은 「부팅 성공 · 정책 결속 다섯 줄 ·
관측 1건 · **STALE 일 공산이 크다**」이고, **실제로 어느 쪽이 나왔는지는 돌린 뒤에 아래
「실행 기록」에 적는다**(소비까지 보려면 부팅 **뒤에** 행을 덧붙이거나 ③ 을 기다린다).

**도구 둘 · 거부 하나.**

| 무엇 | 자리 |
| --- | --- |
| 부팅 증명 저널(한 행, 열다섯 필드, 쓰는 시각 `as_of_ms`) | `tools/tos_cp3/bootproof_journal.py` |
| 실행 템플릿(렌더 → 부팅 → 정지 → 증거 요약) | `tools/tos_cp3/runners/run_tenant_session.sh` |
| 스크래치 전용 강제(두 진입점 **공용**) | `tools/tos_cp3/bootproof_guard.py` |

값은 B1a 실측 창의 **한 봉**을 빌린다. ⚠ **그 봉은 full 계약 `101S6000` 의 것이다** —
부팅 증명 행은 소비되려면 렌더된 **mini** 종목 코드를 달아야 하므로 full→mini **재표지**다.
숨기지 않는다: `source_id` 가 `cp3-bootproof-synthetic:101S6000:<원 raw_event_id>` 이고,
그 `cp3-bootproof-synthetic` 접두가 바로 거부의 입력이다 — **저널의 어느 행이든** 그 접두를
달고 있으면, data dir 의 `Path.resolve()` 가 스크래치 루트 `~/.local/state/tos/scratch/` 의
`Path.resolve()` **아래**이고 **새로 만든 빈 디렉터리**일 때만 진행한다. 그래서 스크래치 루트
안의 심볼릭 링크가 지정 dir 을 가리켜도 거부된다. **결과를 시장 사실로 읽지 않는다.**

**절차 (분리 워크트리 · `origin/main` · clean · 모의 전용).**

```bash
# 0) 분리 워크트리 — 템플릿이 clean·detached·origin/main 조상을 스스로 확인하고 아니면 ABORT 한다.
MAIN=/home/deploy/project/kis_unified_sts
WT=~/.local/state/tos/measure/wt-cp3-bootproof   # 상주 래퍼의 wt-paper 옆, 그 자리는 건드리지 않는다
git -C "$MAIN" fetch origin && git -C "$MAIN" worktree prune
git -C "$MAIN" worktree add --detach "$WT" origin/main
cp -p "$MAIN/.env.mock" "$WT/.env.mock" && chmod 600 "$WT/.env.mock"   # 운영자 2026-10-01

# 1) 계약월 — 템플릿이 쓰는 것과 **같은 한 줄**. 저널도 같은 코드를 달아야 하므로 먼저 본다.
INSTRUMENT=$(cd "$WT" && PYTHONPATH="$WT" "$MAIN/.venv/bin/python" -c \
  'from shared.instruments.futures import get_front_month_code; print(get_front_month_code(product="mini"))')
echo "$INSTRUMENT"

# 2) 스크래치 자리 — 부모만 만든다. 잎(<종목>)은 genesis 의 몫이다.
SESSION=~/.local/state/tos/scratch/cp3-bootproof-$(date +%Y%m%d)
( umask 077; mkdir -p "$SESSION" )

# 3) 저널 한 행. --raw-event-id 는 기본값이 없다 — 빌린 봉이 이 행의 출처 전부이기 때문이다.
#    서브셸로 둔다 — 이 절차는 운영자 셸의 cwd 를 바꾸지 않는다.
( cd "$WT" && PYTHONPATH="$WT" "$MAIN/.venv/bin/python" -m tools.tos_cp3.bootproof_journal \
  --fields ~/.local/state/tos/measure/cp3-short-parity-run1/b1a/fields.jsonl \
  --raw-event-id '101S6000:1m:20251208T092000+0900' \
  --instrument "$INSTRUMENT" \
  --out "$SESSION/journal.jsonl" \
  --data-dir "$SESSION/data/$INSTRUMENT" )

# 4) 세션. 인스턴스 값은 전부 env 이고 **기본값이 하나도 없다** — 지정 경로는 이 런북에만 있다.
TENANT_LOG=$SESSION/session.log \
TENANT_PYTHON=$MAIN/.venv/bin/python \
TENANT_TREE=cp3-setup-d-long \
TENANT_DIRECTION=LONG \
TENANT_RENDER_OUT=$SESSION/config \
TENANT_DATA_PARENT=$SESSION/data \
TENANT_JOURNAL=$SESSION/journal.jsonl \
TENANT_STOP_AT='+5 minutes' \
TENANT_ENV_FILE=$WT/.env.mock \
TENANT_CUSTODY_ROOT=~/.local/state/tos/paper-custody \
TENANT_ENVIRONMENT_LABEL=paper \
  "$WT/tools/tos_cp3/runners/run_tenant_session.sh"
```

- `TENANT_ENV_FILE` 은 **basename 이 `.env.mock` 이어야** 한다 — 렌더러의 같은 가드를 한 걸음
  앞에서 되풀이하므로, 실전 자격증명 파일로는 이 템플릿을 인스턴스화할 수 없다.
- `TENANT_CUSTODY_ROOT` 는 §1 의 커스터디 루트이고 매니페스트의 `environment_label` 이
  `TENANT_ENVIRONMENT_LABEL` 과 **바이트 일치**해야 한다(아니면 부팅이 거부한다).
- `TENANT_DIRECTION` 은 그 트리의 `RENDER.yaml::direction.value` 와 **같아야** 한다 — tenant
  트리는 `declared` 모드라 렌더가 방향을 치환하지 않고 **대조**한다(계획 §2.3).
- 템플릿은 마지막에 그 durable set 의 `snapshots` · `entries` 수와 **kind 별 분포**를 찍는다.
  틱 소비 확인은 로그가 아니라 **지속 저장소**로 한다(§4).

**정리.** 끝나면 워크트리를 접는다(`git -C "$MAIN" worktree remove "$WT"` → `worktree prune`).
`$SESSION` 은 스크래치이므로 콜드 백업 대상이 아니고(§7.2-b 의 래퍼는 `paper-data` 의 직접
자식만 훑는다), 남겨 둘 이유가 없으면 지운다. **지정된 tenant durable set 은 이 절차로 생기지
않는다.**

**실행 기록 — ⛔ 아직 돌리지 않았다 (2026-10-10).** 돌린 뒤 §7.9 형식으로 여기에 적는다:
출하본 sha256 둘(`run_tenant_session.sh` · `bootproof_journal.py`) · 세션 디렉터리 · `verdict`
와 rc · 정책 결속 다섯 줄의 유무 · `snapshots` 와 `entries` 델타 · **그리고 위 ⚠ 의 열린
질문의 답**: 열다섯 필드가 STALE 로 떨어졌는가, 아니면 쓰기→부팅이 800 ms 안에 들어와
소비됐는가. 어느 쪽이든 **그대로** 적는다 — 이 절차의 값은 그 답이지 초록 체크가 아니다.

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
   5-a. **종목 — 한 번 계산해 둘에 준다**(운영자 결정 2026-10-04 · §7.10 7 (c)). 같은
   워크트리에서 `shared.instruments.futures.get_front_month_code(product="mini")` 를 **한 번**
   불러(실패하면 **ABORT**) 그 값으로 **잎** `$TOS_PAPER_DATA_DIR/<종목>` 을 정하고, 드라이버에
   `--instrument` 로 넘겨 렌더가 **같은 값**을 쓰게 한다. 두 자리가 따로 계산하면 어긋난 날
   아무도 모른다 — 그래서 드라이버는 렌더가 적은 종목이 요청과 다르면 **부팅하지 않고**
   `instrument_mismatch` 로 끝낸다(§7.8 1). 값은 `^A0[0-9]{4}$` 여야 하고 아니면 ABORT 다.
   ⛔ `TOS_PAPER_INSTRUMENT_OVERRIDE` 는 이 자동 계산을 덮어쓰는 드라이런 손잡이다(§7.2 표).
   부모 디렉터리는 여기서 `umask 077` 로 만든다(없을 때만) — 잎은 만들지 않는다, 잎은
   genesis 의 몫이다(§7.6).
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
때문이다. 끄면 하루 ≈ **112 MB**(유도값 — §7.8 3). ⚠ **운영자 결정 2026-10-03 으로 닫혔다 —
`on`, 5 s 유지(§7.10 1). 이 기본값은 이제 결정된 값이다.**

### 7.4 cron 두 줄 — ✅ **설치됐다 (운영자 2026-10-03 15:43 KST)**

운영자가 넣었다. 래퍼는 crontab 에 손대지 않고 자기 자신을 지우지도 않는다
(날짜 슬롯이 아니라 반복 일정이다).

- **설치 시각** 2026-10-03 **15:43 KST** · **백업**
  `~/.config/kis-probes/crontab.bak.20261003T154351`(설치 직전 crontab 전문).
- **위치**: 자기 `CRON_TZ=Asia/Seoul` 과 함께 **crontab 의 끝**에 덧붙였다(아래 ⚠ 그대로).
- **확인 한 줄** — `crontab -l | grep -c tos-paper-session` 가 **`2`** 여야 한다(실측 2026-10-03: `2`).
- **첫 발화는 2026-10-05(월) 08:45** 이고 그날은 **대체휴일**이라 래퍼가 **SKIP** 한다
  (rc 0 · 로그 한 줄 · 텔레그램 없음 — §7.3 4 · §7.8 1 의 결말 표). **첫 부팅은
  2026-10-06(화) 08:45** 이고 그것이 genesis 다(§7.6).
  ⚠ 그러므로 **10-05 에 텔레그램이 없는 것은 정상이고 고장이 아니다.**

설치된 줄은 이것이다(설치된 블록 그대로 — 주석 머리 한 줄 포함):

```cron
# TOS paper 상주 세션 (운영자 결정 2026-10-03 · 첫 세션 2026-10-06 · 런북 tos-paper-boot.md §7.4; 크론 끝에 둔다 — CRON_TZ 는 아래 줄에만 적용)
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

### 7.6 상주 data dir 은 **잎마다 그 잎의 첫 세션 genesis 가 만든다** — §4-A 는 적용되지 않는다

- 2026-10-04 현재 `~/.local/state/tos/paper-data` 는 **존재하지 않는다**(실측 — 월물별 잎
  드라이런도 스크래치 부모에서 돌았다, §7.9-leaf). 손으로 만들지 않는다. 첫 기동(10-06)에
  래퍼가 **부모**를 `umask 077` 로 만들고, 그 세션의 genesis 가 **잎 `A05610`** 안에 네
  스토어를 만든다.
- **롤하는 날도 같은 일이 한 번 더 일어난다.** 2026-10-12(월) 첫 세션은 래퍼가 `A05611` 을
  계산해 잎 `paper-data/A05611` 을 가리키고, 그 잎은 비어 있으므로 **그냥 genesis 부팅**이다
  (`genesis=yes`). 어제까지의 `A05610` 잎은 건드리지 않고, 자기 종목으로는 여전히 부팅된다
  (커밋된 테스트 `tos/runtime/tests/compose/test_contract_roll_replay.py` 의 두 번째 보기).
  그래서 §7.10 7 (c) 의 리플레이 발산 경로에 애초에 들어가지 않는다.
- 그러므로 §4-A(v1 → v2 마이그레이션)는 어느 잎에도 **적용되지 않는다.** genesis 는 곧장
  v2 를 만든다(드라이런 실측 §7.9 ① · §7.9-leaf 세 부팅 모두 `user_version=2`).
- ⛔ **`migrate --data-dir` 를 부모(`~/.local/state/tos/paper-data`)에도, 잎
  (`…/paper-data/<종목>`)에도 그 잎의 첫 세션 전에 겨누지 말 것.** `apply_migrations` 는
  존재 검사를 하지 않으므로 **빈 디렉터리에 스토어 넷을 새로 만들고 종료코드 0 으로
  끝난다**(§4-A ⛔). 그러면 키도 세그먼트도 증거도 없는 빈 스토어가 「마이그레이션된 예전
  corpus」처럼 보이고, 진짜 genesis 는 영영 일어나지 않는다. 부모를 겨누면 한 가지가 더
  틀어진다 — 잎이 아닌 자리에 스토어 넷이 생기고, 그것은 콜드 백업 래퍼의 잎 열거 규칙
  (`A0####` 디렉터리만 — §7.7) 밖이라 백업되지 않는다.
- genesis 와 마이그레이션의 서명은 **잎마다** `schema_ledger` 로 구분된다: genesis =
  `2|CREATED` 한 줄, 마이그레이션 = `1|CREATED`(또는 `1|MIGRATE`) + `2|MIGRATE`.

### 7.7 콜드 백업과의 시간 관계

- 야간 콜드 백업(`docs/runbooks/tos-evidence-cold-backup.md` ·
  `~/.config/kis-probes/cold-backup-nightly.sh`)의 대상은 **같은 부모**
  `~/.local/state/tos/paper-data` 이고 예정 시각은 **18:00 KST** 다.
  ✅ **그 cron 줄도 설치됐다 — 운영자 2026-10-03 16:13 KST**(백업
  `~/.config/kis-probes/crontab.bak.20261003T161332`), 역시 자기 `CRON_TZ` 와 함께 crontab
  끝에 `0 18 * * 1-5 … cold-backup-nightly.sh` 한 줄이다. **월물별 잎으로 바뀌면서도 cron
  줄은 그대로다** — 바뀐 것은 래퍼 본체뿐이다.
- ✅ **래퍼는 잎을 순회한다**(2026-10-04 잎 순회 판 `c38078fc…` → **2026-10-06 `umask 077` 판
  `e7579803548b9dcb21dfb813650e51c995a0f25531e1e05add718a98f26d4916`** · 이전 판 백업
  `~/.config/kis-probes/cold-backup-nightly.sh.bak.c38078fcbbe7` · 판본 사본
  `~/.local/state/tos/measure/cold-a3/cold-backup-nightly.e7579803548b.sh`). 두 판의 차이는
  `umask 077` 한 줄이다 — 첫 실전 실행(10-06 18:00)의 아카이브·세대 사본이 cron 의 umask 를
  물려받아 664/644 로 났기 때문이고(콜드 백업 런북 §4-5-4 · 계획 A3-F3), 잎 순회 거동은
  그대로다. 부모 밑의
  `A0####` 디렉터리만 잎으로 세고, 잎마다
  `cold-backup --data-dir <부모>/<잎> --config-dir ~/.local/state/tos/paper-ops/leaves/<잎>`
  을 **한 번씩** 돌린다. 세대 번호가 `backup_root` 단위라(콜드 백업 런북 §4-5-4) 잎마다
  자기 보관소 `~/.local/state/tos/paper-cold/<잎>/{backups,archives,verify}` 와 자기 파생
  설정을 쓴다 — 파생 설정은 `paper-ops/evidence_cold_backup.yaml` 하나를 원본으로
  **실행마다 다시 만들고**, 세 경로 줄만 다른지 대조한 뒤에야 돌린다. 잎이 **하나라도**
  sqlite 핸들이 열려 있으면 실행 전체가 `refused` 다. 텔레그램은 **한 통**이고 머리줄이
  `잎 N개: OK · REFUSED · FAILED · UNCLASSIFIED` 수를, 그 아래 **잎마다 한 줄**을 담는다.
  종료코드는 **가장 나쁜 잎**이다(0 = 전부 verdict). 잎이 아닌 항목(파일 · `A0####` 가
  아닌 디렉터리 · 숨은 항목)은 거부하지 않고 ⚠ 줄로 본문에 싣는다.
  ⚠ 2026-10-03 에 손으로 만든 `paper-cold/{backups,archives,verify}` 세 디렉터리는 **이제
  쓰이지 않고 비어 있다** — 잎 보관소는 그 옆에 선다. 지울지는 운영자 몫이다.
  **증명**(전부 스크래치 좌표 · 호스트 `paper-cold`/`paper-ops` 는 매 실행 전후 동일):
  잎 둘에 세 번 연속 실행 → 잎마다 gen1 → gen2 → gen3 · 잎 셋 중 마지막이 거부 → rc 1 이고
  앞의 둘은 백업됨 · **첫째가 거부돼도 뒤의 둘이 백업됨**(순회가 첫 실패에서 멈추지 않는다는
  증명은 이쪽이다 — 마지막이 거부되는 보기만으로는 그것을 모른다) · 락 보유 중 `SKIP` rc 0 ·
  부모는 있는데 **잎 0개** → `PRE-GENESIS` rc 0(BORN_ON 전) / `refused` rc 1(BORN_ON 뒤) ·
  기준 설정의 세 루트가 한 부모를 안 쓰면 거부 · 파생 설정 대조 (a)·(b) 를 거부하게 하는
  입력 각 하나(`backup_root:` 줄 중복 · 잎 경로가 든 주석 줄) — (c) 는 렌더 경로로는
  도달하지 않는 회귀 뒷받침이다(콜드 백업 런북 §4-5-4).
  **설치본** `--selftest`(2026-10-04 19:20:06 KST · `COLD_NOTIFY=0`): `PRE-GENESIS` rc 0,
  로그 머리의 sha256 이 위 값, `paper-data` 부재 유지 — `~/.local/state/tos/cold-backup.log`
  의 19:20:06 블록. **로그는 전부 `~/.local/state/tos/measure/cold-a3/leaf-selftest-20261004/`
  (700/600)에 있다** — `selftest-*.log` 14 개와 호스트 전후 목록(`hostdirs.*` · `install.*`),
  `wrapper.diff`. 머리 줄의 `sha256=` 은 전부 `c38078fc…` 다.
- 대상이 아직 없는 동안(10-06 genesis 전 — 부모가 없거나 잎이 0개)의 실행은
  **`PRE-GENESIS` rc 0** 으로 끝난다
  (`docs/runbooks/tos-evidence-cold-backup.md` §4-5-3 · §4-5-5 R1) — 그래서 백업 줄을 먼저
  넣어도 무해하다. 1차 판은 「백업만 먼저 넣는 것은 의미가 없다(대상이 아직 없다)」고
  적었는데, **`PRE-GENESIS` 분기가 생긴 뒤로는 그 말이 더 이상 맞지 않는다.**
  ⚠⚠ **「조용히」가 아니다 — `PRE-GENESIS` 는 텔레그램을 보낸다.** 콜드 백업 런북의 결말
  표가 그 칸을 **「보냄」**으로 적고(§4-5 표), 래퍼도 그 분기에서 `notify` 를 호출한다
  (`cold-backup-nightly.sh` · `COLD_NOTIFY` 기본값 1 이고 **cron 줄은 그것을 끄지 않는다**).
  그러므로 **10-05(월) 저녁 18:00 에는 `PRE-GENESIS` 한 줄이 반드시 와야 한다.**
  그날 저녁이 조용하면 그것은 「아직 대상이 없어서」가 아니라 **통지 경로가 깨진 것**이다.
  ⚠ 10-06 **당일부터는** 같은 부재가 `refused` **rc 1** 이다(래퍼의 같은 분기).
- `backup-set`/`cold-backup` 은 **런타임이 정지해 있을 것**을 전제하고, 그 전제를
  **기계적으로 확인하지 못한다**(그 함수의 문서화된 한계). 그래서 시간으로 벌려 둔다:

| 경로 | 정지 시각 | 18:00 까지 여유 |
| --- | --- | --- |
| 정상 (정지 크론이 15:45 에 돈다) | 15:45 + 정지 대기 | **2 h 15 m — 이것이 최대값이다** |
| 안전망 (정지 크론이 안 돌았다) | 16:00 + 렌더·부팅 시간 | **≈ 2 h 00 m** |
| 정지 지연 (§7.5 — 에스컬레이션 없음) | **상한 없음** | **보장 없음** |

- 정지가 지연되면 텔레그램에 그 사실과 함께 **「스토어가 열려 있으면 백업이 뜨지
  않는다」**가 함께 나간다. 그때의 확인은 `fuser -v ~/.local/state/tos/paper-data/*/*.sqlite3`
  다(잎 한 단계 아래 — 부모 바로 밑에는 스토어가 없다).

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

⚠ **2026-10-12(월)에 볼 것 — 그날이 종목이 바뀌는 첫 세션이다(§7.10 7 (c), ✅ 월물별
잎).** 기동 줄 끝의 종목은 10-06·10-07·**10-08 까지 `A05610`**(만기일 당일도 아직 구월물)
이고, 10-09(금)은 한글날이라 **텔레그램이 아예 없다**(SKIP — 이 절 1 의 결말 표 SKIP 행).
**아무것도 10-12 전에는 롤하지 않는다.** 10-08 세션 자체는 다른 날과 똑같다 — 15:45
정지까지 CONTINUOUS, 거부도 stage-deny 도 없다.
10-12 아침에 보는 것은 **셋**이다: ① 날짜 로그의
`instrument=A05611 (auto=A05611) · data leaf …/paper-data/A05611` 줄 · ② 그 다음
`data dir … (genesis=yes)` 줄과 기동 텔레그램의 `genesis=True … A05611` · ③ `report.json`
의 `instrument: "A05611"` · `genesis: true` · `baseline_evidence_seq: -1`.
⛔ **`A05611` 인데 `genesis=no` 면 이미 쓰인 디렉터리에 부팅한 것**(잘못된 잎)이다 — 그때는
§7.9-held 의 질의로 held 여부부터 본다. `verdict: "instrument_mismatch"`(rc 1 · 부팅 없음 ·
그 보고서에만 `requested_instrument` 가 실린다)는 렌더가 적은 종목과 래퍼가 계산한 종목이
다르다는 뜻이다 — 둘은 같은 워크트리의 같은 함수를 부르므로 정상적으로는 나올 수 없고,
나오면 그날 `origin/main` 의 `shared/instruments/futures.py` 가 바뀐 것이다.

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
- ⛔ **`events_consumed` 가 0 인데 `observations_appended` 는 > 0 이고 그날이 거래일이면
  held 런타임을 의심한다** — 부팅은 `OK` 라고 말하는데 틱이 하나도 처리되지 않는 모양이다.
  휴장·장외에는 같은 값이 정상이므로 **장중에만** 신호다. 확정 질의는 **§7.9-held**.
  10-12(월) 첫 롤 세션에서 가장 먼저 볼 값이다(§7.10 7 (c)).
- ⚠ **`baseline_evidence_seq: -1` 과 `genesis: false` 가 함께 나오면 genesis 가 아니다.**
  드라이버의 기준선 조회는 **DB 부재 · 빈 테이블 · `DatabaseError` 셋 다**에서 −1 을 돌려주는데,
  `genesis` 는 파일 존재만 본다. 둘이 어긋났다는 것은 **파일은 있는데 읽히지 않았다**는 뜻이고,
  그 상태에서는 그날 델타가 「전부 새 행」으로 보인다. 손으로 센다:
  `sqlite3 "file:$DATA/evidence.sqlite3?mode=ro&immutable=1" "SELECT COUNT(*), MAX(seq) FROM entries;"`
  (`$DATA` 는 **그날의 잎**이다 — 예 `~/.local/state/tos/paper-data/A05610`, 부모가 아니다.
  세션이 멎은 뒤에만 — `mode=ro` 만으로는 `-shm` 이 생긴다, §4-A-1 의 관용구).
- `evidence_schema_after.user_version == 2` · `matches_expected_v2: true`
- ⚠ **`report.json` 이 없어도 증거는 남아 있다.** 보고서는 드라이버가 마지막에 쓰는 파일이고,
  증거는 런타임이 그 전에 이미 커밋했다. 확인은 sqlite 로 직접 센다:
  `sqlite3 "file:$DATA/evidence.sqlite3?mode=ro&immutable=1" "SELECT COUNT(*), MAX(seq) FROM entries;"`
  (`$DATA` 는 **그날의 잎**이다 — 예 `~/.local/state/tos/paper-data/A05610`, 부모가 아니다.
  세션이 멎은 뒤에만 — `mode=ro` 만으로는 `-shm` 이 생긴다, §4-A-1 의 관용구).

**3. data dir 성장** — **잎 단위**로 센다: `du -sb ~/.local/state/tos/paper-data/A05610`
(10-12 부터는 `A05611` 잎이 0 에서 다시 시작한다 — 부모 합계로 보면 롤 날 새 잎의 첫 하루가
어제 잎의 크기에 묻힌다).

| 숫자 | 출처 | 성격 |
| --- | --- | --- |
| ≈ **200 MB/일** (수집기 5 s) | 2026-09-28 15 분 실측을 **× 28 환산**. 세 파일 합 **7.1 MB**(증거 증가 대응 계획 §1 의 표) · data dir 전체 **7.2 MB**(이 런북 §5 ④) — 둘 다 ≈ 200 | **환산값 — 전 세션 실측 없음.** 10-06 이 첫 실측 |
| 기대 폭 | — | 장 길이·수집기 지연·휴장 반일 등으로 **150–250 MB** 를 정상으로 본다 |
| ≈ **112 MB/일** (수집기 off) | `TIME_HEALTH_SNAPSHOT` 이 증거 바이트의 75 %(3.99/5.33 MB, 계획 §1) → 3.99 × 28 | **유도값 — 측정한 적 없다** |

**4. 콜드 백업 결과** — 전날 18:00 의 텔레그램 줄과 `~/.local/state/tos/cold-backup.log`.
✅ **그 cron 도 설치됐다**(운영자 2026-10-03 16:13 · §7.7).

| 텔레그램 | rc | 뜻 |
| --- | --- | --- |
| 머리줄 `잎 N개: OK N · REFUSED 0 · FAILED 0 · UNCLASSIFIED 0` + 잎마다 `<잎> OK — …` 한 줄 | 0 | **모든 잎**의 백업이 떠서 되읽기 검증까지 끝났다. 10-07~10-09 아침은 잎 하나(`A05610`), **10-13 아침부터 둘**(`A05610`·`A05611`) |
| `PRE-GENESIS` | 0 | 잎이 아직 없다(`BORN_ON` 전). **10-05 저녁의 정상값** |
| `SKIP` | 0 | 다른 실행이 락을 쥐고 있다 |
| 머리줄의 `REFUSED`/`FAILED`/`UNCLASSIFIED` 가 0 이 아니고 그 잎의 줄이 그렇게 적힘 | 1 | **가장 나쁜 잎**이다 — 다른 잎의 `OK` 줄은 그대로 백업된 것이다. 「아무것도 안 됐다」가 아니라 「전부 되지는 않았다」 |
| `ABORT` | 2 | **텔레그램이 못 간다** — 통지 수단을 세우기 전에 끝났다 |

⚠ 머리줄 네 수의 합은 잎 수와 같아야 한다 — 다르면 그것부터 의심한다. ⚠ 본문에
`계약월 잎이 아닌 항목` 줄이 있으면 부모 밑에 무언가가 잎 밖에 썼다는 뜻이다(§7.6 ⛔ 의
`migrate` 오발 포함). 거부는 아니지만 그냥 두지 않는다.

⚠ **10-05(월) 저녁에 아무것도 오지 않는 것은 정상이 아니다.** 이 줄의 1차 판은 그 반대로
적었는데 **틀렸다** — `PRE-GENESIS` 는 **보냄**이다(§7.7 ⚠⚠). 침묵의 뜻은 둘뿐이다:
통지 경로가 깨졌거나, cron 이 아예 안 돌았거나.
⚠ **rc 2(ABORT)는 텔레그램에도 `cold-backup.log` 에도 남지 않는다.** 그 경우를 잡는
유일한 자리는 cron 리다이렉트가 받는 **`~/.local/state/tos/cold-backup.cron.log`** 다
(콜드 백업 런북 §4-5-6). 침묵을 만나면 거기부터 본다.

### 7.9 드라이런 기록 — 2026-10-03 (장 마감일 · 스크래치 data dir)

드라이런 시점에는 cron 이 아직 없었고(그날 **15:43**·**16:13** 에 설치됐다 — §7.4 · §7.7),
상주 data dir 은 건드리지 않았다(§7.6 — 지금도 없다). 아티팩트는 **`~/.local/state/tos/paper-sessions/2026-10-03-*/`** 와 날짜 로그
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

⚠ **래퍼는 그 뒤 세 번 더 바뀌었다** — 2026-10-04 07:08 KST 의 §7.2-a 0700 패치 판
`a898e6cb1f2f75d078d91a4cc53ebd0054fa5056316fe073f293da995ce74a8f`(이전 판 백업
`~/.config/kis-probes/tos-paper-session.sh.bak.e169e23d`), **월물별 잎 판
`fd554b2a3c1496d26c70dcce414ae529fec81f89abc131e41f7b4046aa0ab763`**(같은 날 18:19 KST 전 ·
10-06 20:00 까지의 출하본 — 10-06 첫 상주 세션이 이 판으로 돌았다 ·
백업 `.bak.a898e6cb1f2f` · 드라이런과 변경 내용은 **§7.9-leaf**).
⚠ **그리고 2026-10-06 20:00 KST 에 한 번 더 — CP-1 projection 배선(Codex, PR #861 의 패치
`docs/runbooks/patches/tos-paper-projection.patch`)으로 지금 출하본은 래퍼
`2c3284a4ec3a1312018c0d6c730b7f2dbfb891c53fb4a2ea86aecb8980aaccef` · 드라이버
`3ce14fb685a009b993ba9fcaa1b4693c38efd4279e60fa4e0622140336b8624e` 다**(원본 백업
`~/.local/state/tos/paper-ops/projection-connection-20261006/` · 절차는
`docs/runbooks/tos-paper-projection-connection.md`). 백업과 설치본의 `diff` 로 확인한 변경은
**projection 경로뿐**이다 — 래퍼: `PROJECTION_PATH` 기본값(`TOS_PAPER_PROJECTION_PATH`) ·
selftest/우회 세션이면 세션 디렉터리로 격리 · 절대경로 검사 · 드라이버에 `--projection-path`
(코드 6줄); 드라이버: `--projection-path` 인자를 `run` 에 전달(3줄). **종목 계산·잎 경로·달력·
digest·부팅증명·정지·보고 경로는 바뀌지 않았으므로 §7.9-leaf 의 기록은 그대로 유효하다.**
10-06 첫 상주 세션은 아직 `fd554b2a` 로 돌았고(날짜 로그 머리), `2c3284a4` 의 첫 세션은
10-07 이다 — 그날 아침 §7.8 에 더해 projection 파일 생성(`paper-projection/operator_projection.json`)
을 본다(`docs/runbooks/tos-paper-projection-connection.md` 의 「다음 세션에서 확인」 네 항목). 이 문단의 나머지는
**첫 번째** 변경(`e169e23d` → `a898e6cb`)을 적은 것이다. **아래 ①–③·E1–E5·S1–S6 은 전부
`e169e23d…` 또는 그 직전 두 판(`f452ee0b…`/`b28c188f…`)에서 돈 기록이다** — 어느 실행이 어느 판인지는 바로 아래 ⚠ 문단이 이름으로 가른다. 두 판의 차이는 `diff` 로 확인한 **셋뿐**이고
— ① 드라이버 기동을 `( umask 077; exec … )` 서브셸로 감싼 것, ② 종료 뒤
`[ -d "$DATA" ] && chmod 700 "$DATA"` 한 줄, ③ 그 둘을 설명하는 주석 블록 둘 — **달력·digest·
부팅증명·정지·보고 경로는 한 글자도 바뀌지 않았다.** 그러므로 아래 기록은 그대로 유효하다.
`a898e6cb…` 에서 돈 것은 **두 세션**이다 — 패치 직후 적용 쪽이 돌린
`2026-10-04-070746-LONG`(그 스크래치 data dir 은 이미 지워졌다)과, 이 레인이 독립
재측정으로 돌린 `2026-10-04-071204-LONG`(§7.2-a 의 출력이 이쪽 것이다).
`tos_paper_session.py` 는 그 시점까지 불변(`995ada06…`)이었고, 월물별 잎 판에서 처음
바뀌었다(`21b583bd…` — §7.9-leaf).

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
| 달력 | 2026-10-09 (금, 한글날) | `calendar: 2026-10-09 is a listed holiday (both files)` → **`is_trading_day` rc 1** |
| 달력 | 2026-10-06 (화) | `calendar: 2026-10-06 is a trading day (both files agree)` → rc 0 |
| 달력 | 달력 파일 부재 | `ABORT — calendar file missing in the worktree: …/market_schedule.yaml` rc 2 |
| 달력 | 인위적 불일치(한쪽에만 10-06) | `calendar: ⚠ DIVERGENCE for 2026-10-06 — market_schedule.yaml=1 tos calendar.yaml=0; treating as a holiday (conservative)` → rc 1 |
| digest | `print-digests` 가 예외로 죽은 출력 | `ABORT — digest guard cannot run — CODE_NOW is not a 64-char lowercase hex digest (got '<empty>').` |
| digest | **64자인데 hex 가 아님**(`38d85110zzzz…`) | 같은 ABORT. ⚠ **옛 접두 패턴은 이것을 통과시켰다** |
| digest | 넷 다 64 hex 인데 값 불일치 | `ABORT — digest mismatch — boot would be refused (ReleaseAdmissionRefused).` rc 2 |
| 부팅 증명 | 빈 커스터디 루트 | 위 **E4** |

⚠ **위 달력 행의 rc 는 `is_trading_day` 함수의 반환값이지 래퍼의 종료코드가 아니다.**
`rc 1` = 「거래일이 아니다」이고, 그것을 받은 래퍼 `start` 는 **SKIP 으로 rc 0** 에 끝난다
(§7.4 · §7.8 1 의 결말 표). 두 숫자를 같은 축으로 읽으면 「휴장일에 래퍼가 실패한다」가 된다.
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

#### 7.9-held ⛔ 「부팅은 OK 인데 아무것도 처리되지 않는다」 — held 런타임 (실측 2026-10-04)

§7.9 의 가드 표는 **부팅이 거부되는** 결말만 이름 붙인다(`MISSING` · `N/A` · ABORT).
**거부되지 않는 고장**이 하나 더 있고, 그것이 종목 롤이 만드는 모양이다(§7.10 7 (c) ③).

**증상.** 복구 배리어가 걸리면 `compose_paper_runtime` 은 **정상 종료한다** — rc 0 ·
정책 결속 다섯 줄 생김 · 증거 쌓임 · 기동 텔레그램 `boot proof: OK`. 그런데 엔진 드라이버가
붙지 않아(`driver is None`) **틱이 하나도 처리되지 않고** 전부
`MARKETFEED_QUEUED_UNTIL_RECOVERY` 로 쌓인다
(`tos_runtime/marketfeed/scheduler.py:271` · `513-517`).

**판별 — `report.json` 두 값의 조합으로 본다.**

| 신호 | held | 정상 장중 | 정상 휴장/장외 |
| --- | --- | --- | --- |
| `observations_appended` | > 0 | > 0 | > 0 |
| `events_consumed` | **0** | > 0 | **0** |
| `evidence_by_kind_delta` 의 `MARKETFEED_QUEUED_UNTIL_RECOVERY` | **> 0** | 없음 | 없음 |
| 증거의 `REPLAY_DIVERGED` 행 | **>= 1** | 0 | 0 |

⚠⚠ **「`events_consumed` 0 + `observations_appended` > 0」만으로는 판별이 안 된다** —
세션이 닫혀 있을 때의 정상값과 **같은 모양**이기 때문이다(실측: 2026-10-04 07:12 의 주말
세션이 바로 그 값이다 — 12 / 0 인데 멀쩡하다). **장중에** 그 조합이면 의심하고, 확정은
아래 두 줄로 한다. 소비 0 을 그 자체로 고장이라고 읽으면 토·일·휴장일마다 거짓 경보가 난다.

```bash
# (1) 결정적 신호 — 이 행이 하나라도 있으면 그 코퍼스는 held 다
sqlite3 "file:$DATA/evidence.sqlite3?mode=ro&immutable=1" \
  "SELECT COUNT(*) FROM entries WHERE kind='REPLAY_DIVERGED';"
# (2) 그날 큐에만 쌓였는지
sqlite3 "file:$DATA/evidence.sqlite3?mode=ro&immutable=1" \
  "SELECT COUNT(*) FROM entries WHERE kind='MARKETFEED_QUEUED_UNTIL_RECOVERY';"
```

(⚠ `immutable=1` — §4-A-1 의 관용구다. `mode=ro` 만으로는 `-shm` 을 쓴다.)

**되돌릴 수 없다.** `REPLAY_DIVERGED` 행은 예외보다 **먼저** 내구 저장되고
`_replay_verdict_ok`(`recovery/inputs.py:89-107`)는 그 행이 **0 개**일 것을 요구한다 —
설정을 되돌려도 배리어는 그대로 걸려 있다(실측 §7.10 7 (c) ③). 즉 **이것은 아침에 고칠 수
있는 고장이 아니라, 일어나기 전에 막아야 하는 고장이다.**

### 7.10 이 런북이 답하지 못한 것 (✅ 닫힘 · ⛔ 열림/재개 · 표시 없음 = 질문이 아니라 사실)

> 범례: **✅** 는 결정이나 측정으로 닫힌 항목, **⛔** 는 열려 있거나 다시 열린 항목이다.
> 표시가 없는 항목(2 · 5)은 **열린 질문이 아니라** 그냥 적어 둘 사실이다 — 5(DST)는
> 물을 것이 없고, 2 는 수치가 계속 갱신되는 관측 항목이다.

1. **✅ 관측 수집기 — 운영자 결정 2026-10-03: `on`, 5 s(기본값 유지).**
   (원 질문) §7.3 은 기본 on(5 s)으로 두었고 그 근거는 ① 없으면 소비·결정이 0 이고
   ② 증거 증가 대응 계획 §1 의 200 MB/일 기준선이 이 조건의 값이라는 것뿐이다. 그 관측은
   **합성 밴드**이고 시장 데이터가 아니다. 끄면 하루 ≈ 112 MB(유도값)에
   `TIME_HEALTH_SNAPSHOT` 만 쌓인다.
   **결정 사유**: 커널에는 아직 실브로커 피드가 없다. 합성 밴드를 끄면 하루치가
   TIME_HEALTH 하트비트뿐이고 **소비 → 결정 → 거부 체인이 한 번도 돌지 않는다.**
   밴드가 합성이라는 사실은 증거에 **라벨로 남는다**(`source_id`
   `tos-paper-resident-session` — §7.3 「출처」). ≈ 200 MB/일 은 계속 **계획용 추정치**다
   (첫 실측은 10-06 — §7.8 3).
   ⚠ 그러므로 `TOS_PAPER_APPEND_EVERY_S` 는 **결정된 값**이다. 바꾸려면 이 줄을 먼저 고친다.
2. **언제까지 쌓을 것인가.** 퍼지는 트랙 B 이고 전제 다섯이 비어 있다(증거 증가 대응 계획 §4).
   디스크로는 333 GB 여유 ÷ 200 MB/일 ≈ **1,665 거래일 ≈ 6.8 년**(거래일 기준 — 달력 날짜가
   아니다)이지만, 그 파일시스템은 콜드 백업·측정 아티팩트와 **공유**이고, 먼저 걸리는 것은
   디스크가 아니라 **부팅 리플레이 시간**이다(§7.8 2). 그 곡선의 첫 실측이 `boot_seconds` 다.
3. **✅ 방향 — 운영자 결정 2026-10-03: 상주는 `LONG` 단독 유지. 보완으로 SHORT 부팅증명을
   분기 1회 손으로 돌린다.**
   (원 질문) §0 은 대칭의 증거로 양쪽을 부팅시킨다고 적는데 상주는 한쪽만 쌓는다.
   LONG/SHORT 를 **같은 날** 돌리려면 두 번째 data dir 과 두 번째 설정
   (`paper-config-short`)이 필요하다 — 한 디렉터리에 두 방향을 섞는 경로는 설계에 없고,
   §5 ⑤ 가 적듯 **활성화 기록은 방향을 결속하지 않으므로** 섞인 corpus 는 나중에 digest 로
   갈라낼 수 없다.
   **결정**: 상주 코퍼스는 `TOS_PAPER_DIRECTION=LONG` 하나로 쌓는다. 그러므로 **§0 의
   「매일 양방향」은 「LONG 매일 + SHORT 분기 1회」로 대체된다** — 대칭의 증거를 버리는 것이
   아니라 **빈도를 낮춰 한 코퍼스의 순도를 사는 것**이다. 어느 쪽이든 **실주문은 0**
   (`SYNTHETIC_FUTURES_ORDER` · 모의 계좌 좌표 — §0).
   **SHORT 보완 실행의 형태**: §3 의 1회성 절차 그대로, **스크래치 data dir** 에 **한 세션**.
   상주 data dir(`~/.local/state/tos/paper-data`)에는 **절대 섞지 않는다.** 운영자가 손으로
   돌리며 cron 에 넣지 않는다(분기 1회짜리를 반복 일정으로 두지 않는다 — §7.4 와 같은 이유).
   **분기 1회인 이유**: 이 부팅은 **전략 성과가 아니라 대칭을 재는 것**이고, 대칭이 깨지는
   계기는 날짜가 아니라 **코드 변경**이다(`construction.yaml::action_class`/`outbound_side` ·
   `order_construction_policy.yaml` 의 DIRECTION 축 · 전략 파일의 `direction`). 매일 돌리면
   같은 사실을 매일 다시 사면서 코퍼스 순도만 잃고, 1년에 한 번이면 그 사이 변경을 놓친다.
   분기는 그 사이의 타협이다. ⚠ **그러므로 분기를 기다리지 않는 계기가 하나 있다** —
   위 네 자리 중 하나라도 바뀌면 **그 PR 에서** SHORT 를 한 번 돌린다.
   📌 **TODO(운영자 · 첫 회 마감 2026-10-16(금))** — SHORT 부팅증명 1 세션.
   10-06 주는 상주 **첫 주**이고 세션이 셋뿐이라(10-06·10-07·10-08) 「자리잡은 뒤」가 그 주
   안에 성립하지 않는다. 그래서 **둘째 주 끝**을 마감으로 둔다. 이후 분기마다 반복
   (다음 마감 2027-01-15 · 이하 같은 방식).
   ⚠ **2026-10-16 이 지나도 §7.9 식 실행 기록이 없으면 「돌았는데 안 적었다」가 아니라
   「안 돌았다」로 읽는다.** 기록이 곧 실행의 정의다.
4. **부팅 증명 가드는 이제 시험했다 (§7.9 E4) — 대신 남은 것은 ② 「천장 초과」 가지다.**
   600 s 를 넘겨 MISSING 이 되는 경로는 이력이 충분히 길어야 재현되므로 오늘 만들 수 없다.
   `boot_seconds` 추이가 그 전조다(§7.8 2).
5. **DST/시각 변경.** KST 는 DST 가 없고 cron 은 `CRON_TZ=Asia/Seoul` 이다.
6. **⛔ 코퍼스가 커널 리비전을 가로지른다 — 코드 핀 결정은 열려 있다.** 래퍼는 매일 `origin/main` 에서 워크트리를 새로
   만들므로, 하루치마다 **다른 커널 바이트**가 같은 append-only 코퍼스에 쓸 수 있다.
   digest 가드는 **같은 워크트리 안의** `release.yaml` 과 대조하므로 이 변화를 **보지 못한다**
   (핀과 코드가 함께 움직이면 늘 통과한다). 콜드 백업 런북은 반대로 자기 워크트리를
   「의도적으로만」 고정한다. 지금의 대응은 `report.json` 의 `worktree_commit` 뿐이다(§7.8 2).
   **코드를 고정할지(어느 커밋에?) 날마다 따라갈지는 운영자 결정이다.**
   ⚠ **이 항목은 출처 표시에서 멈춰 있는데, 같은 위험의 실제 피해가 7 (c) 에서 측정됐다.**
   부팅은 예전 이벤트를 **그날의 배선**으로 다시 돌려 예전 영수증과 대조한다
   (`compose/_finalize_wiring.py:114-123`). 그러므로 **어제의 증거를 오늘의 코드로 재해석할
   수 없게 만드는 변경**은 전부 같은 모양으로 터진다 — 종목(7 (c) · 실측)뿐 아니라 전략
   레지스트리 키·스테이지 구성·정책 스코프가 그렇다. 「리비전이 섞여도 `worktree_commit`
   만 남기면 된다」는 **출처에는 참이고 부팅 가능성에는 거짓이다.**
   ✅ 그중 **종목 축**은 월물별 잎(7 (c))으로 닫혔다 — 잎 안에서 종목은 상수다. ⚠ 나머지 축
   (전략 레지스트리 키 모양 · 스테이지 구성 · 정책 스코프 · 리플레이가 재해석하는 어떤
   배선이든)은 **그대로 열려 있다**: 그런 변경이 `origin/main` 에 들어간 다음 날 아침의
   증상은 7 (c) ③ 과 같다(부팅 OK · held · 틱 전부 `MARKETFEED_QUEUED_UNTIL_RECOVERY`).
   커밋된 테스트도 종목 축만 고정한다. 그래서 그 자리들을 건드리는 PR 은 **같은 PR 에서**
   상주 잎의 **사본**으로 두 번 부팅을 돌리거나, 운영자가 새 잎으로 시작할 날을 정한다.
   코드 핀 결정 자체는 여전히 열려 있다.
7. **✅ 종목 롤 — (a)(b) 는 10-03 에, (c) 는 2026-10-04 에 닫혔다(REOPENED 뒤 같은 날,
   월물별 잎으로).** 현재 근월물
   `A05610` 의 만기는 **2026-10-08(목)** 이다(`calendar.yaml::futures_expiry` = 둘째 목요일).
   렌더가 **실행 당일** `get_front_month_code(product="mini")` 로 종목을 다시 뽑으므로(§2)
   롤은 자동이고, 그래서 물어야 할 것은 셋이었다 — **(a) 어느 날 어떤 코드가 뽑히나 ·
   (b) 만기일 세션은 무엇을 하나 · (c) 한 코퍼스에 두 종목이 섞여도 되나.** 셋 다 측정했고,
   **(a)(b) 는 닫혔다(✅). (c) 는 1차 답이 틀려서 2026-10-04 에 다시 열렸다가** — 리뷰가
   같은 질문을 **부팅 리플레이** 쪽에서 다시 물어 반증했다 — **같은 날 운영자 결정과
   배선·증명 셋으로 닫혔다(✅).** 아래 (c) 를 볼 것.

   **(a) 렌더가 뽑는 코드.** `shared/instruments/futures.py::get_front_month_code` 는
   `target_date > expiry` **일 때만** 다음 달로 넘어간다. 그러므로 **만기일 당일은 아직
   구월물**이고, 새 코드가 처음 뽑히는 날은 만기 **다음 날**이다.

   | 실행일 | 요일 | 뽑히는 코드 | 그날 부팅하나 |
   | --- | --- | --- | --- |
   | 2026-10-05 | 월 | `A05610` | **안 함** — 대체휴일. 크론의 **첫 발화**다(§7.4) |
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

   (아티팩트 `…/2026-10-03-front-month-roll.out` 에서 **발췌**한 세 줄이다 — 전문은 다섯
   날짜 × 일곱 시각이다. ⚠ 이 블록의 1차 판에는 **아티팩트에 없는 줄**이 하나 있었다:
   10-09 10:00 행은 사실로는 맞지만 당시 스크립트 격자에 10:00 이 없었다. 조립한 줄을
   「실측」 블록에 넣는 것은 #854 H1 과 같은 형태이므로, 격자에 10:00 을 넣어 **다시 돌리고**
   아티팩트를 교체했다. 인용은 이제 출력에 그대로 있는 줄이다.)

   정지 크론이 **바로 그 15:45** 에 SIGTERM 을 보내므로(§7.4) `EXPIRED` 토큰은 **정지까지의
   몇 초**에만 닿을 수 있다. 닿든 안 닿든 **하류는 같다** — 틱 게이트가 보는 것은 위상
   토큰이 아니라 `session_context.is_open` 이고
   (`tos_runtime/marketfeed/scheduler.py::decide_tick`), `CLOSED` 와 `EXPIRED` 는 둘 다
   `is_open=False` 라 그 몇 초의 틱은 다른 날과 똑같이 `SKIPPED_SESSION_CLOSED` 다.
   ⚠ **설령 그 게이트를 지나더라도 두 번째 방어가 있다**: 배포된
   `venue_constraint_policy.yaml` 의 `admitting_phase_rules` 는 세 액션 모두
   `admitting_phases: ["CONTINUOUS"]` 이므로, 커널의 `session_phase_admits` 가 `EXPIRED`
   를 **집합 밖**으로 보고 INADMISSIBLE 을 돌려준다(송신 0). 런타임이 「만기니까 거부」라고
   판정하는 것이 아니라 **커널이 이미 아는 토큰을 건네줄 뿐**이다.
   유일한 차이는 그 한 줄의 **내용**이다 — 다른 날에는 `phase: "CLOSED"` 로 남는 자리가
   10-08 에는 `phase: "EXPIRED"` · `expired: true` 로 남는다. **줄이 하나 늘어나는 것이
   아니다**(`calendar/owner.py::_maybe_record_observed` 는 위상이나 `expired` 가 **바뀔 때만**
   적으므로, 어느 날이든 15:45 경계에서 한 줄이다). ⚠ **그 줄이 남는지 자체는 정지와의
   경합이라 보장되지 않는다.**
   10-09 는 애초에 부팅하지 않으므로 그날 증거는 **0 행**이고, 만기는 그날부터 다음 룰 월인
   **2026-11-12** 로 넘어간다(클래스가 월말까지 EXPIRED 로 남던 결함은 #799 에서 닫혔다 — §5 ④).

   **(c) ✅ 한 코퍼스에 두 종목 — 2026-10-04 REOPENED, 같은 날 「계약월마다 잎 하나」로
   닫혔다. 1차 답(「괜찮다」)은 틀렸다.** ①②③ 은 그 반증의 기록이고(평면 배치 한 개의
   data dir 에 대한 사실로 지금도 참이다), 처분과 증거는 그 아래에 있다.
   아래 ①이 1차 답이고 **그 자체는 지금도 참**이다. 틀린 것은 ①에서 「그러므로 섞어도
   된다」로 건너뛴 것이다 — ①은 **사후에 갈라낼 수 있나**에 답하고, 정작 물었어야 할 것은
   **애초에 두 번째 부팅이 되나**였다. ②가 그 답이고, **안 된다**.

   **① 사후 분리는 된다(1차 답 · 유효).** 3 의 위험은 §5 ⑤ 「활성화 기록은 **방향**을
   결속하지 않는다」에서 온 것이다. 종목은 다르다 — **결정 계열 증거 행은 종목을 자기 안에
   들고 있다.** 09-28 10:00 세션 코퍼스
   (`~/.local/state/tos/realclock-20260928T100001-LONG/data/evidence.sqlite3` — ⚠ 같은 날
   11:00 세션의 코퍼스와 **다른 디렉터리**다)의 **사본**을 질의한 결과(1,492 행 중 236 행):

   | 종류 | 행 | `payload_json → $.instrument_key` |
   | --- | --- | --- |
   | `DECISION_OUTCOME_EMITTED` | 114 | ✅ `{account, instrument}` |
   | `DECISION_WITHHELD` | 66 | ✅ |
   | `FLOW_HALTED` | 56 | ✅ |
   | `EVENT_CONSUMED` · `EVENT_HANDLING_STARTED` | 180 · 180 | ❌ |
   | `TIME_HEALTH_SNAPSHOT` 외 15 종 | 896 | ❌ (종목과 무관한 런타임 상태) |

   부팅 행도 **간접적으로** 갈린다: 렌더가 종목을
   `venue_constraint_policy.yaml::scope.instruments` 에 박으므로 `VENUE_POLICY_BOUND` 의
   `canonical_digest` 가 종목마다 다르다(종목만 바꿔 로더를 두 번 돌린 실측:
   `a85def5d…` vs `3e9ea069…`). ⚠ 그 두 값은 **자리표시 계좌**로 뽑은 것이라 실제 부팅이
   적을 값이 아니다 — 「다르다」만 읽을 것. ⚠ `VENUE_POLICY_BOUND` **본문에는 종목 문자열이
   없다**(payload 는 `policy_id` · `policy_generation` · `canonical_digest` ·
   `activated_member_digest` · `null_shape_bounds` 뿐).

   **② 그런데 (평면 배치에서는) 두 번째 부팅이 안 된다 — 부팅 리플레이가 어긋난다(실측
   2026-10-04).**
   `run` 은 부팅할 때마다 durable inbox 의 이벤트를 **그날의** 레지스트리로 **다시 돌려**
   예전 영수증과 대조한다(`compose/_finalize_wiring.py:114-123` → `verify_replay_or_halt`).
   그 레지스트리는 **`(account, instrument)` 로 키가 잡힌다**
   (`tos/src/tos/engine/registry.py:71` `_key_tuple`). 그래서 종목이 롤한 날:

   1. 렌더가 `A05611` 로 설정을 깐다 → 레지스트리 키가 `(…, A05611)` 뿐이다.
   2. 리플레이가 `A05610` 시절의 `EVENT_CONSUMED` 영수증을 돌린다 → 그 키가 없어
      `REGISTRY_MISSING` 으로 멎는다(`tos_runtime/engine/replay.py:100` 의
      `_PIPELINE_NEVER_RAN_HALT_REASONS`).
   3. 그런데 **그 영수증은 실제 `outcome_digest` 를 갖고 있다**(그날 체결 경로가 끝까지
      돌았으므로). 「영수증엔 digest 가 있는데 재실행은 파이프라인 전에 멎었다」는
      일치가 아니다 → `INCONCLUSIVE` → `REPLAY_DIVERGED`
      (`replay.py:316-375` — `expected_digest` 대 `actual_digest` 비교와
      `_record_divergence_halt`).
   4. `_boot_integrity.py:155-160` 이 `EngineReplayDiverged` 를 던진다.

   실측(출하 코드 그대로 `compose_paper_runtime` 두 번 — 아티팩트는 아래 재도출):

   ```text
   BOOT1 instrument: A05610 | pipeline digest: 2cbdf3b7424cf64c ...
   BOOT1 EVENT_CONSUMED receipts: 1 | with real digest: 1
   CONTROL  (A05610 again): BOOT OK
   ROLLED   (A05611):        EngineReplayDiverged -> engine replay diverged for 1 of 1 compared events: ('event-75b5cb57ff2c21720cc0e51aea32d431df7b34641b516ea20ee8c6ad3979afcd',)
     evidence rows REPLAY_VERDICT_IDENTICAL: 2
     evidence rows REPLAY_DIVERGED: 1
   ```

   **대조군이 핵심이다** — 같은 data dir 에 **같은 종목**으로 다시 부팅하면 `BOOT OK` 다.
   어긋나게 만드는 것은 두 번째 부팅도, 코퍼스 크기도 아니라 **종목이 바뀐 것** 하나다.
   ⚠ 리플레이 창(`replay_window_events` = 1,000,000)으로는 벗어나지 못한다 — 하루 ≈ 5,000
   건이라 롤 시점의 영수증이 창 안에 한참 남아 있다.

   **③ 그리고 되돌려도 안 풀린다 — 피해가 영구적이다(실측).** `REPLAY_DIVERGED` 행은
   예외를 던지기 **전에** 내구 저장된다. 복구 배리어의 `_replay_verdict_ok`
   (`recovery/inputs.py:89-107`)는 **`REPLAY_DIVERGED` 가 0 행일 것**을 요구하므로, 설정을
   `A05610` 으로 **되돌려 부팅해도** 배리어가 런타임을 잡아 둔다:

   ```text
   REVERTED (A05610):        BOOT OK
     recovery barrier driver is None (held runtime)? True
     _replay_verdict_ok(evidence store): False
   ```

   ⚠⚠ **이 모양이 가장 위험하다 — 부팅은 「성공」이라고 말한다.** rc 0 이고 부팅 증명 다섯
   줄도 생기고 증거도 쌓인다. 그런데 `driver is None` 이라 **틱이 하나도 처리되지 않고**
   전부 `MARKETFEED_QUEUED_UNTIL_RECOVERY` 로 쌓인다(§7.3 의 「held 런타임」 분기).
   §7.9 의 가드 표에 **이 결말의 이름이 없다** — 증상과 판별은 §7.9 끝 「held」 절에 넣었다.

   ⚠ **그러므로 이 항목의 1차 판이 적은 닫는 말(「가르지 않는 쪽이 기본이다」)은 뒤집힌다.**
   **가르지 않기는 코드 변경 없이는 실패한다 — 측정됐다.** 평면 배치 그대로 10-12 에
   부팅했다면 상주 코퍼스는 첫 롤에서 held 로 떨어졌을 것이다.

   **처분 방향은 정해졌다 — 운영자 결정 2026-10-04: 계약월마다 durable set 을 가른다**
   (`~/.local/state/tos/paper-data/<종목>`). 롤하는 날은 **그냥 genesis 부팅**이 되므로 위
   ②③ 의 경로에 애초에 들어가지 않고, **커널 바이트는 건드리지 않는다.** 함께 기각된 셋과
   그 이유:

   | 기각된 안 | 이유 |
   | --- | --- |
   | 리플레이 범위 축소 | 완결성 공백 — `ERI-INV-007` |
   | 지난 달 종목을 레지스트리에 존치 | **세 번째 롤부터 부족하다**(한 달치만 남겨서는 모자람) |
   | 이벤트마다 레지스트리 재해석 | 커널 변경이 크다 |

   ✅ **닫혔다 — 2026-10-04. 들어와야 했던 셋이 전부 들어왔다(결정만으로는 ✅ 가 아니었다):**
   ⓐ 세션 래퍼 `fd554b2a…` / 드라이버 `21b583bd…`(10-06 20:00 부터 `2c3284a4…`/`3ce14fb6…` —
   projection 경로 인자만 더해졌다, §7.9 머리) — 종목을 **한 번** 계산해 렌더
   `--instrument` 와 `--data-dir` 잎에 **같은 값**(§7.3 5-a · 드라이런 세 부팅 §7.9-leaf:
   자동 잎 genesis · 다음 월물 잎 genesis · 같은 잎 재부팅 IDENTICAL).
   ⓑ 콜드 백업 래퍼 `c38078fc…`(10-06 부터 `umask 077` 판 `e7579803…`, 잎 순회 거동 동일 — §7.7) — **잎 순회**(§7.7 · 콜드 백업 런북 §4-5-4). 잎마다 보관소와
   파생 설정, 한 통에 잎마다 한 줄, 가장 나쁜 잎의 종료코드.
   ⓒ 커밋된 **두 번 부팅 레드 증명** `tos/runtime/tests/compose/test_contract_roll_replay.py`
   — 같은 dir 롤 = `EngineReplayDiverged` 이고 `REPLAY_DIVERGED` 행이 영수증 수만큼
   (같은 종목 재부팅 대조군 포함) · 자기 잎 롤 = clean 이고 이전 잎도 자기 종목으로 재부팅
   clean. 위 ② 가 다시 생기면 CI 에서 먼저 깨진다.
   그에 따라 §7.2 경로표 · §7.3 5-a · §7.6 · §7.7 · §7.8 은 **잎 기준**으로 고쳐 적었다.
   남는 것은 **첫 실제 롤 2026-10-12** 다 — 그날 아침의 확인은 §7.8 1 ⚠ 문단, 그날 18:00
   콜드 백업은 처음으로 **잎 둘** 메시지다(§7.8 4). 잔여 위험은 6 에 적었다(닫힌 것은
   **종목 축**뿐이다).
   ⚠ 10-12 는 **월요일**이다. 그 전 거래일은 10-08(목)이고 그 뒤 사흘이 비거래일이다 —
   10-08 세션은 `A05610` 잎에 마지막으로 쓰고, 10-12 세션은 `A05611` 잎을 새로 만든다.

   ⛔ **인용 금지.** 위 결정 행의 `instrument_key` 는 종목과 **계좌번호**를 함께 담는다.
   §7.2 의 좌표 규율대로 증거 행을 PR·계획 문서·텔레그램에 그대로 옮겨 적지 않는다
   (이 절의 표는 종류와 개수만이다).


   **재도출.** (a)(b) 는 커밋된 테스트가 CI 에서 같은 사실을 고정한다 —
   `tos/runtime/tests/compose/test_deploy_config.py` 의
   `test_real_calendar_mini_october_expiry_day_before_and_after_close`(10-08 15시 CONTINUOUS /
   16시 EXPIRED) · `test_real_calendar_day_after_mini_october_expiry_rolls_to_november`
   (10-09 는 휴장 CLOSED · 다음 만기 2026-11-12) ·
   `test_real_calendar_declares_every_month_a_rule_month`. 위 표를 손으로 다시 뽑는 스크립트와
   출력은 `~/.local/state/tos/paper-sessions/` 에 있다(0600):
   `2026-10-03-front-month-roll.py` / `.out`(a·b) ·
   `2026-10-03-front-month-roll-digest.py` / `.out`(digest 분리) ·
   `2026-10-03-front-month-roll-corpus.out`(c ①의 질의와 출력).
   **(c) ②③ 의 두 보기**는 `~/.local/state/tos/paper-sessions/2026-10-04-roll-replay-probe/`
   에 있다(0600): `roll_twoboot_probe.py` / `.out`(②) ·
   `roll_permanence_probe.py` / `.out`(③) · `roll_replay_probe.py` ·
   `roll_control_driver.py`(앞선 두 단계). 저장소 테스트 픽스처
   (`tos/runtime/tests/compose`)를 그대로 쓰므로 스크래치 디렉터리 밖에는 쓰지 않는다:

   ```bash
   cd <워크트리> && PYTHONPATH=tos/runtime:tos/runtime/src:tos/src \
     .venv/bin/python <그 디렉터리>/roll_twoboot_probe.py
   ```

   ⚠ `roll_permanence_probe.py` 는 **두 보기를 이어서** 돌려야 한다 — 앞 probe 가 만든
   `twoboot/day1` 코퍼스를 그대로 쓴다.
8. **달력은 2027년에 대해 fail-open 이다 — 방향을 분명히 적는다.** 두 파일 모두 2027년
   항목이 **0건**이므로(실측), 2027-01-01 이후 **모든 평일이 「거래일」로 판정된다** —
   건너뛰는 쪽이 아니라 **부팅하는 쪽으로 틀린다**. 또 `calendar.yaml:49` 는
   **2026-12-31(KRX 연말 휴장)** 을 「운영자 검토 후보 · 정본 파일에 없음」으로 적어 두었고
   두 휴장 목록 어디에도 없다 — 그날도 부팅한다. 둘 다 **휴장일 목록을 먼저 고치는 것**이
   해결이고, 래퍼가 손댈 일이 아니다.
