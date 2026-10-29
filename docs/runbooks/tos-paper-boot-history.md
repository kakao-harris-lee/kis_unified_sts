# TOS paper 런북 — 이력 · 측정 기록

- 운영 절차는 [`tos-paper-boot.md`](tos-paper-boot.md) 다. 이 파일은 그 런북이 2026-09-23 ~
  2026-10-20 사이에 쌓은 **실측 · 수용 기록 · 드라이런 · 설계 근거 · 닫힌 질문**을 담는다.
- 내용은 **한 줄도 고치지 않고 그대로 옮겼다.** 절 번호도 원래대로다 — 다른 문서가 가리키는
  `§4-A` · `§5 ④` · `§7.10 7 (c)` 따위는 이 파일에서 같은 번호로 찾는다.
- 날짜가 박힌 문장은 **그 날의 기록**이다. 오늘의 상태로 읽지 말 것.

---

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

#### 7.2-b CP-3 tenant durable set — **data dir 은 아직 없다 · ops/cold 는 2026-10-09 에 생겼다**

§7.2 의 표는 **상주 배포**의 것이다. CP-3 첫 tenant(Setup D)는 kickoff 결정 3·4 대로
**방향마다 따로** 돌므로 자기 durable set 과 자기 렌더 산출물을 갖는다. 이 절은 그
**이름을 지정**하는 자리다. **durable set 부모와 잎(`cp3-setup-d-*-data`)과 렌더된 설정
(`~/.config/tos/cp3-setup-d-*-config`)은 아직 없다** — genesis 는 그 잎의 **첫 부팅**이고
(§7.6 과 같은 규율) 그 부팅은 ③ 을 기다린다(§7.2-c).

✅ **그러나 뒤 두 열(ops·cold)은 더 이상 「없다」가 아니다 — 운영자가 2026-10-09 23:28 KST 에
만들었다(실측 2026-10-10).** 아래 ⚠ 문단들이 「아직 만들지 않았다」로 적던 상태가 그날 바뀌었다.

#### 7.2-b (이력) 지정의 배경 · 켜기 실측

⚠ 뒤 두 열은 **콜드 백업을 켤 때 필요한 지정**이었고, **운영자가 2026-10-09 에 그대로
켰다** — 아래 ✅ 절이 그 실측이다(그러므로 이 절의 「켜는 것은 운영자 결정이다」류 문장은
**이미 내려진 결정**을 설명하는 것으로 읽는다). `COLD_ROOT` 는 환경변수가 아니라 그 ops
디렉터리의 `evidence_cold_backup.yaml` 세
경로가 **공유하는 부모**로 유도되므로, tenant 보관소를 가르는 유일한 수단은 그 세 경로를
tenant 콜드 부모 아래에 적는 것이다.

**이름 규칙은 「설정 트리 이름 + `-data` / `-config`」다** — data dir 이름을 설정 트리
이름에서 **도출할 수 있어야** 어느 코퍼스가 어느 트리로 부팅됐는지 경로만 보고 알 수 있다
(§5 ⑤: 활성화 기록은 방향을 결속하지 않으므로 경로가 그 역할을 한다).

**모드·규율은 상주와 같다**: 부모·잎 디렉터리 **0700**, 스토어 파일 **0600**(결정 레코드가
계좌번호를 평문으로 싣는다 — §7.2-a), 렌더된 설정 디렉터리 **0700**, 전부 저장소 밖.

#### 7.2-b (이력) 왜 셋을 함께 지정해야 하나

⚠ **아래 실측은 「켜기 전」의 상태 기록이다(2026-10-09, 켜기 직전).** 왜 `COLD_DATA_DIR`
하나만 바꾸면 안 되는지를 설명하므로 남겨 둔다 — **실제로 어떻게 켰는지는 아래 ✅ 절**이다:
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
##### ✅ 켰다 — 운영자 2026-10-09 23:28 KST (실측 2026-10-10, 읽기 전용)

위 ⛔·⚠ 문단들이 「운영자 결정 자리」로 적던 것이 결정됐다. **호스트 상태**(만든 것은
운영자이고, 이 절은 기록이다):

| 무엇 | 실측 |
| --- | --- |
| `~/.local/state/tos/cp3-setup-d-{long,short}-ops` | **0700**, 각각 `evidence_cold_backup.yaml` **0600** 한 개 |
| `~/.local/state/tos/cp3-setup-d-{long,short}-cold` | **0700**, `backups`·`archives`·`verify` 세 하위 **0700** |
| 그 `evidence_cold_backup.yaml` 의 세 경로 | 전부 자기 tenant 콜드 부모 아래 절대경로 리터럴 — 즉 `COLD_ROOT` 가 `cp3-setup-d-{long,short}-cold` 로 유도된다(위 표대로) |
| `minimum_free_bytes` | `53687091200`(= 50 GiB, 바이트 정수 — 상주와 같은 값) |

**크론 두 줄 등록됨**(`crontab -l | grep cp3-setup-d` → 2행, 평일만 `1-5`):

```
20 18 * * 1-5  COLD_DATA_DIR=…/cp3-setup-d-long-data  COLD_CONFIG_DIR=…/cp3-setup-d-long-ops  COLD_TARGET_BORN_ON=2026-10-12 … # cold-backup-cp3-long
40 18 * * 1-5  COLD_DATA_DIR=…/cp3-setup-d-short-data COLD_CONFIG_DIR=…/cp3-setup-d-short-ops COLD_TARGET_BORN_ON=2026-10-12 … # cold-backup-cp3-short
```

셋을 함께 지정했으므로 위 ⛔ 문단이 경고하던 **상주 보관소와의 섞임은 일어나지 않는다**
(18:20·18:40 로 야간 상주 실행과도 시각이 갈린다).

⛔ **결과 — 2026-10-12 부터 매일 밤 거부가 난다.** `COLD_TARGET_BORN_ON` 이 **2026-10-12**
인데 tenant data dir 의 genesis 는 ③ 을 기다리므로(위), 그날부터 래퍼는 부모 부재를
「아직 아님」이 아니라 **「없어진 대상」**으로 읽는다 — `cold-backup-nightly.sh:335` 의
`abort_refused` 가 **종료코드 1** 로 끝내고 **텔레그램 REFUSED 한 줄**을 보낸다(`:233-243`).
10-11 까지는 같은 부재가 PRE-GENESIS(rc 0 · 텔레그램 한 줄)다(`:327-334`).
⚠ **그러므로 10-12 부터의 그 야간 알림은 고장이 아니라 「③ 이 아직 없다」는 말이다.**
없애려면 ③ → 첫 genesis 로 잎을 만들거나, 운영자가 `COLD_TARGET_BORN_ON` 을 미루거나
두 크론 줄을 잠시 빼야 한다. **이 런북은 호스트를 바꾸지 않는다 — 셋 다 운영자 결정이다.**

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
`python tools/tos_redigest.py --write` 는 **세 사본을 한 번에** 쓰므로 아래 함정에 빠지지
않는다(2026-10-22). 손으로 고치면 그 핀을 상주 트리에서만 재도출하게 된다 — 상주 세션은 매일 재도출해
대조하므로 거기서는 드러나지만(§5 ①), **tenant 트리는 부팅한 적이 없어 낡은 핀이 드러날
레인이 없다.** 첫 tenant 부팅이 digest 불일치로 **ABORT** 한다. 이것은 §7.10 6 이 적는
「어제의 증거를 오늘의 코드로 재해석할 수 없게 만드는 변경」의 사본 판이다.

`tos/runtime/tests/compose/test_tenant_tree_copies.py` 가 이 의무를 고정한다: 사본의 **바이트
동일성** · 선언된 차이가 실제로 다른가 · 분류의 **전수성**(파일을 더하고 분류를 빼먹으면 red) ·
분류됐지만 **어느 검사도 안 하는 이름이 없는가** · `release.yaml` 은 실패 메시지가 「두
트리에서 같은 PR 에 재도출하라」고 말하도록 **따로** 단언한다.

#### 7.2-c CP-3 tenant 부팅 증명 — **스크래치에서 손으로 1회** (코드 2026-10-10 · 실행 미착수)

> ⛔ **2026-10-14 부터 이 절차는 이력이다 — 실제 세션은 §7.2-d 로 돈다.** ③ 이 PR-2 로
> 들어오면서 러너의 순서가 바뀌었고(생산자가 저널을 만든다), 아래의 「저널 한 행을 손으로
> 만든다」 단계는 이제 생산자의 기동 거부를 부른다. 아래는 ③ **이전**에 무엇을 증명하려
> 했는지의 기록으로 남긴다.

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
잰다. 도구가 `as_of_ms` 를 **쓰는 시각**으로 찍어도 `_derive_field_state` 가 필드마다
`(UNKNOWN, "stale")` 를 돌려주고, 커널의 UNKNOWN 바닥이 그 키들을 떨어뜨려 R1 의 AND 가
거짓 → NO_ACTION → 송신 0 이다(fail-closed).

⛔ **「공산이 크다」가 아니라 구조상 확정이다(초판의 약한 표현을 정정 — PR #892 리뷰 LOW).**
이 절차에서 쓰기와 첫 평가 사이에는 **가드 · 렌더 · 부팅 · 리플레이**가 들어간다. 렌더만
해도 다섯 digest 도출과 스테이징 스왑이고, 부팅 리플레이는 이력에 비례해 커진다(§7.3 7 의
600 s 천장이 그래서 있다). **초 단위**가 800 ms 를 넘지 않을 길이 없다. 그러므로 기대 결말은
「부팅 성공 · 정책 결속 다섯 줄 · 관측 1건 · **열다섯 전부 STALE**」이다. 상주 렌더의 부팅
증명 관측이 `_JOURNAL_AGE_MS` 1000 > 800 때문에 **언제나** STALE 인 것과 같은 모양이고
(아래 §5 ④ 와 같은 절의 STALE 문단), 계획 §2.5 의 「15 필드 **소비**」라는 표현은 **PR #887
에서 하향**됐다. **소비를 보려면 부팅 뒤에 행을 덧붙이는 경로가 필요한데 그것은 만들지
않았다**(계획 §2.5 의 PR-C 선택: 지금 만들면 ③ 이전에 두 번째 생산자가 생긴다). 그래서
「STALE 이냐 아니냐」는 이 절차가 답할 질문이 **아니다** — 아래 「실행 기록」은 STALE 이
실제로 그렇게 나왔는지를 **확인**해 적는 자리이고, 열린 질문은 ③ 으로 넘어간다.

**도구 둘 · 가드 하나.**

| 무엇 | 자리 |
| --- | --- |
| 부팅 증명 저널(한 행, 열다섯 필드, 쓰는 시각 `as_of_ms`) | `tools/tos_cp3/bootproof_journal.py` |
| 실행 템플릿(렌더 → 부팅 → 정지 → 증거 요약) | `tools/tos_cp3/runners/run_tenant_session.sh` |
| data-dir 가드(두 진입점 **공용**) | `tools/tos_cp3/bootproof_guard.py` |

값은 B1a 실측 창의 **한 봉**을 빌린다. ⚠ **그 봉은 full 계약 `101S6000` 의 것이다** —
부팅 증명 행은 소비되려면 렌더된 **mini** 종목 코드를 달아야 하므로 full→mini **재표지**다.
숨기지 않는다: `source_id` 가 `cp3-bootproof-synthetic:101S6000:<원 raw_event_id>` 다.
⚠ 그 표지는 **출처 표시이고 판정 기준이 아니다** — 판정은 아래 **allowlist** 가 한다.
**결과를 시장 사실로 읽지 않는다.**

**가드가 하는 일 — allowlist · fail-closed** (계획 §2.5 의 ⛔⛔ 문단, PR #892 리뷰 HIGH 로
초판의 denylist 를 뒤집은 것):

1. **상주 durable set `~/.local/state/tos/paper-data` 는 어떤 저널로도 대상이 아니다**(무조건).
2. **모든 행**의 `source_id` 가 `APPROVED_REAL_PRODUCER_PREFIXES` 의 접두면 §7.2-b 의 지정된
   tenant 저장소가 허용된다. ⛔ **그 목록은 ③ 이 생길 때까지 비어 있다** — 그래서 **오늘은
   스크래치 밖 부팅이 전부 거부된다.** ③ 의 PR 이 자기 접두를 더하는 것이 첫 실제 genesis 가
   가능해지는 순간이다.
3. 그 밖에는 data dir 이 스크래치 루트 `~/.local/state/tos/scratch/` **아래**(양쪽 `resolve()`)
   의 **새 빈 디렉터리**여야 하고, 스크래치 루트 자신이 심볼릭 링크가 아니어야 하며, 경로에
   `cp3-setup-d-*-data`·`paper-data` 같은 durable-set 이름 조각이 없어야 한다.

초판이 **왜** 틀렸는지도 적어 둔다(같은 모양을 또 만들지 않기 위해): 초판은 「합성 표지가
붙은 저널」만 스크래치에 가뒀는데, **오늘 이 호스트의 저널은 전부 합성이고 대부분 그 표지를
달고 있지 않다.** 상주 렌더의 `~/.config/tos/paper-config/bootproof_journal.jsonl`
(`tos-paper-bootproof-render` · `tos-paper-resident-session`)을 근월물로 바꿔 지정 dir 에
겨누면 가드가 **「ok」를 찍었다**(리뷰어 실측).

⚠ 도구의 `--out` 도 스크래치 아래여야 한다 — 이 도구는 출력 파일을 **통째로 원자적 교체**
하므로, 제약이 없으면 위의 **살아 있는 상주 저널**을 합성 한 행으로 덮어쓴다(리뷰 LOW).

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
- `TENANT_ENVIRONMENT_LABEL` 은 **렌더된 트리의 `critical_input_policy.yaml::environment` 와도**
  같아야 하고, 템플릿이 렌더 직후 대조한다(PR #892 리뷰 LOW). critical-input 로더는 그 둘을
  **대조하지 않으므로**, 어긋난 라벨은 조용히 부팅하고 그 세션의 모든 스냅샷·캡슐 covered
  content 에 틀린 환경이 박힌다 — append-only 저장소에 **틀린 증거**가 남는 것이다.
- **정지 경로 둘 — 무엇이 덮이고 무엇이 안 덮이는지 정확히 적는다.**
  ① 템플릿이 **TERM/INT/HUP 를 받으면** 자식 `run` 에 SIGTERM → 120 s → SIGKILL 을 적용한다
  (상주 드라이버와 같은 블록). 그래서 Ctrl-C 나 `kill` 로 멈춰도 `run` 이 고아로 남지 않는다.
  그 `trap` 은 `run` 을 띄우기 **전에** 걸린다 — 띄운 뒤에 걸면 그 사이에 도착한 신호가
  기본 처분으로 템플릿만 죽이고 자식을 남긴다.
  ② ⚠ **그러나 trap 은 템플릿이 살아서 볼 수 있는 신호만 덮는다.** 템플릿에 `SIGKILL` 이
  가거나 호스트가 죽으면 핸들러는 **돌지 않는다**. 그래서 자식은 `timeout` 아래에서 뜬다 —
  `timeout --kill-after=120s <정지창+120>s`. 별도 감독 프로세스의 자기 알람이므로 템플릿이
  한마디도 못 하고 죽어도 `run` 은 그 천장에서 끝난다. 천장이 「정지창 + 120 s」인 이유는
  ① 의 우아한 정지가 진행 중일 때 외부 알람이 **먼저 끼어들지 않게** 하기 위해서다.
  ⛔ 덮이지 **않는** 것: 템플릿과 `timeout` 이 **둘 다** SIGKILL 되는 경우. 그때는 `run` 이
  정말 고아가 되므로, 손으로 확인한다 — `pgrep -af "tos_runtime.compose.cli"`.
- `TENANT_DIRECTION` 은 그 트리의 `RENDER.yaml::direction.value` 와 **같아야** 한다 — tenant
  트리는 `declared` 모드라 렌더가 방향을 치환하지 않고 **대조**한다(계획 §2.3).
- 템플릿은 마지막에 그 durable set 의 `snapshots` · `entries` 수와 **kind 별 분포**를 찍는다.
  틱 소비 확인은 로그가 아니라 **지속 저장소**로 한다(§4).

**정리.** 끝나면 워크트리를 접는다(`git -C "$MAIN" worktree remove "$WT"` → `worktree prune`).
`$SESSION` 은 스크래치이므로 콜드 백업 대상이 아니고(§7.2-b 의 래퍼는 `paper-data` 의 직접
자식만 훑는다), 남겨 둘 이유가 없으면 지운다. **지정된 tenant durable set 은 이 절차로 생기지
않는다.**

**실행 기록 — ⛔ 아직 돌리지 않았다 (2026-10-10).** 돌린 뒤 §7.9 형식으로 여기에 적는다:
출하본 sha256 셋(`run_tenant_session.sh` · `bootproof_journal.py` · `bootproof_guard.py`) ·
세션 디렉터리 · rc · **정책 결속 다섯 줄의 유무**(이것이 이 절차의 본 주장이다) ·
`snapshots` 와 `entries` 델타 · kind 별 분포 · 그리고 **열다섯이 STALE 로 떨어진 것이
맞는지의 확인**(위 ⛔ 대로 구조상 그래야 한다 — 아니었다면 그쪽이 소견이다).
⚠ **「소비되는가」는 이 절차가 답할 질문이 아니다** — 답하려면 부팅 뒤에 행을 덧붙이는 경로가
있어야 하고 그것은 만들지 않았다. 그 질문은 ③ 의 것이다.

#### 7.2-d CP-3 tenant 세션 — ③ 이 **있는** 지금의 절차 (PR-3, 2026-10-14)

§7.2-c 는 ③ 이 **없던** 동안의 절차다(한 행짜리 합성 저널로 배선만 관통). ③(실시간
15 필드 생산자, `tools/tos_cp3/live_producer`)이 PR-2 로 들어오면서 러너의 순서가
바뀌었다 — 계획 `docs/plans/2026-10-10-tos-cp3-live-field-producer-plan.md` §3.4·§3.5·§3.6.
**실제 genesis 세션은 이 절차로 돈다.** §7.2-c 는 이력으로 남긴다.

**무엇이 바뀌었나 — 여섯 가지**(5 번은 band 계획 PR-A, 2026-10-15 · 6 번은 PR-B, 2026-10-16)**.**

1. **저널은 운영자가 만들지 않는다. 생산자가 만든다.** 러너는 ① 생산자 기동(시드)
   → ② 첫 **실제** `tos-cp3-live/…` 줄이 생길 때까지 대기(상한 `FIRST_LINE_TIMEOUT_S`
   = 600 s, 넘으면 ABORT) → ③ 가드 → 렌더 → 부팅 순으로 간다. #892 가드는 빈 저널을
   거부하고 모든 행이 **승인된 생산자**의 것이기를 요구하는데, 그것을 참으로 만드는
   것이 ③ 이다. 가드의 의미는 그대로다.
   ⛔ 그래서 `TENANT_JOURNAL` 은 **아직 없는 경로**여야 한다. 이미 있는 저널에는
   생산자가 기동을 거부한다(그 파일을 통째로 교체해 버리므로).
2. **첫 줄은 부팅이 끝날 때 이미 STALE 이다.** 러너는 부팅 직전의 저널 행 수를
   `consumed_stale_at_boot` 로 로그에 남기고, 그 id 들을
   `<TENANT_PRODUCER_SESSION_DIR>/boot-journal-snapshot.json` 에 적는다. 그 파일이
   §3.6 추출기가 「구조상 소비될 수 없던 부팅 전 줄」과 「런타임이 소비하지 못한 줄」을
   가르는 근거다(계획 §5 M5 는 전자를 두 계수에서 뺀다).
3. **정리(trap)가 생산자 기동 *전에* 걸린다.** 생산자는 가드·렌더·라벨 검사보다
   먼저 뜨므로, 그 사이의 어떤 `die` 든 생산자를 멈춰야 한다 — 안 그러면 러너는 죽고
   생산자만 남아 하루 종일 **실전 조회 API** 를 부른다(계획 §3.5 v2 재리뷰 M1).
   EXIT trap 이 그것이고, 두 자식 모두 자기 `timeout` 천장 아래에서 뜬다(러너가
   SIGKILL 되면 trap 은 돌지 않는다). 종료 신호는 **프로세스 그룹**으로 간다 —
   손에 든 pid 는 `timeout` 의 것이고, `timeout` 에만 KILL 을 보내면 실제 작업
   프로세스가 감독자보다 오래 산다(#892 재리뷰 L2).
4. **자격증명 분리(계획 §3.4).** 환경은 **넷**이고(band 계획 v3 가 band 프로세스를
   더했다) 실전 키를 가질 수 있는 것은 **조회 둘**뿐이다:
   - 러너 — 모의 전용. `TENANT_ENV_FILE` 은 basename 이 `.env.mock` 이어야 한다.
   - 생산자 — 선물 **조회** 키 두 개(`KIS_FUTURES_APP_KEY`/`SECRET`)를 **자기가**
     읽는다. 어디서? 자기 config(`TENANT_PRODUCER_CONFIG`)의 `env_file:` 이 가리키는
     파일(`/home/deploy/project/kis_unified_sts/.env.real`). 러너는 그 값을 읽지도
     전달하지도 로그하지도 않는다. 토큰 캐시 경로도 앱 키의 **지문**만 쓴다.
   - band 프로브 — **생산자와 똑같은 방식**으로 같은 두 키를 **자기가** 읽는다. 러너는
     config 경로와 월물·세션 dir 만 넘기므로, 프로세스가 하나 늘었어도 러너 환경에
     실전 키가 들어가는 일은 없다. 토큰 캐시도 같은 지문 경로를 **공유**한다(정상
     경로에서는 생산자가 받아 둔 유효 토큰 재사용 → 발급 0 회).
   - 런타임 — 모의 전용이고, 실전 자격증명을 절대 들면 안 되는 **그** 프로세스.
   자식은 환경을 물려받으므로, 셸에 그 두 키가 export 돼 있으면 **런타임에도** 들어간다.
   러너는 그래서 자기 환경에 둘 중 하나라도 있으면 **기동을 거부한다**. 생산자에게
   키를 주려고 `export KIS_FUTURES_APP_KEY=…` 하지 말 것 — 생산자는 파일에서 읽는다.
   ⛔ GET 전용이다. 생산자의 import 그래프에 `shared.execution` 주문 경로도
   `probes_real_order` 도 `probes_order` 도 없고, 테스트가 그것을 고정한다. 실전 주문
   TR 은 0 건이어야 하고, 그 0 은 세션 뒤 요청 로그로 확인한다 — 기대 TR 집합은
   **조회 둘**(`FHKIF03020200` 분봉 · `FHMIF10000000` band)이다(아래 「세션 뒤」).
5. **band 를 별도 단명 프로세스가 읽는다**(band 계획 v3, 2026-10-16 운영자 결정 —
   PR-A 의 원 설계는 생산자 안이었고 그것이 왜 틀렸는지는 계획 §3.1 의 v3 블록).
   러너가 **개장 + 한 경계**에 `python -m tools.tos_cp3.live_producer.band_probe` 를
   `timeout --kill-after=5s $BAND_PROCESS_TIMEOUT_S` 아래 띄우고, 그 프로세스가 실전
   시세 키로 `FHMIF10000000` 을 한 번 GET-only 로 읽어 생산자 세션 dir 의
   `band.jsonl` 에 한 줄을 쓰고 **끝난다**. 실패하면 **다음 경계에 한 번만** 더 띄운다.
   러너는 런타임 부팅 **전에 그 줄**(오늘 · 이 월물 · 개장 이후)을 확인하고, 없으면
   `BAND ABSENT` 를 크게 적고 **계속 간다**. ⛔ 단 band 프로세스의 **rc 1**(게이트 거부)
   은 부팅 전 ABORT 다. 자세한 것은 아래 「세션 뒤 — band」.
   ⛔ **`bash -x` 로 돌리지 않는다 — 돌려도 추적은 나오지 않는다**(Codex 리뷰 HIGH,
   2026-10-14). 템플릿은 첫 줄에서 `set +x +v` 를 하고, 그 뒤 자격증명 가드는 값이 아니라
   **이름**을 본다(`${!name+x}`). 추적을 켠 셸에서 호출해도(`SHELLOPTS=xtrace` 포함) 값이
   로그에 찍히지 않는다는 뜻이고, 거꾸로 디버깅용 추적은 얻을 수 없다는 뜻이기도 하다 —
   읽을 것은 `TENANT_LOG` 다(경로·pid·거부 사유가 다 있고 값은 없다).
6. **런타임이 그 줄을 읽는다 — LONG 트리만**(band 계획 PR-B, 2026-10-16 · 계획 §3.3·§4).
   `config/tos_runtime/cp3-setup-d-long/venue_constraint_policy.yaml` 의
   `_runtime.band_source.kind` 가 `"producer_journal"` 이고, 런타임은 부팅 때
   `band.jsonl` 의 **마지막 줄 하나**를 읽어 유효 shape 제약의 `price_min`/`price_max`
   를 채운다. 소켓 0 · 자격증명 0 은 그대로다 — 파일 하나를 열 뿐이다.
   - 러너가 **매니페스트를 보고** `--band-journal-path` 를 넘긴다. 상주 `paper` 와 SHORT
     트리는 슬롯이 없어 그 인자를 받지 **않는다**(주면 렌더가 거부한다). 세션 로그의
     `render: <tree> declares a band_journal_path slot -> …` 줄이 어느 쪽인지 적는다.
   - 읽기 실패는 전부 **band None + 사유**다(파일 부재 · 파싱 불가 · 어제 날짜 · 다른
     월물 · 승인 밖 `source_id` · 격자/척도/순서) → 커널 `UNKNOWN` → **송신 0**. 즉
     최악이 「오늘과 같은 상태」이고, 사유는 `VENUE_BAND_OBSERVED` 행에 남는다
     (아래 「세션 뒤 — band 를 런타임이 실제로 썼는가」).
   - ⛔ **앞 줄로 물러나지 않는다.** 마지막 줄이 무효면 그 전 줄이 유효해도 band 는
     없다 — 「한때 유효했던 band」를 믿지 않기 위해서다.
   - ⚠ `_runtime` 은 VCP `canonical_digest` 가 덮지 않으므로 **활성화 기록은 그대로**다
     (실측 2026-10-16: 렌더된 LONG 정책에서 band 블록을 떼고 다시 로드해도 digest 가
     `ec0ea97d…` 로 같다). 바뀌는 것은 `release.yaml::expected_code_digest` 뿐이고,
     그것은 재도출해야 한다. **재도출은 한 명령이다 (2026-10-22):**
     `python tools/tos_redigest.py --write` 가 세 사본의 핀 줄을 함께 다시 쓰고,
     `--check` 는 낡았으면 exit 1 로 멈춘다(`tos-firewall` CI 스텝 · 런타임 수트의
     `test_release_code_digest_pin_equals_the_measured_source_tree` 가 같은 대조다.
     운영 절차는 `tos-paper-boot.md` 「digest 재도출」).
     ⛔ **여기에 값과 이력을 더 적지 않는다 — 기록은 git 이력이다.** 기준은
     `config/tos_runtime/*/release.yaml` 이고, 어딘가와 어긋나면 **그 파일이 맞다.**
     아래 이력 줄은 2026-10-22 이전의 기록으로 남긴다(더 잇지 않는다):
     `fb4ac519…` → `2aa597aa…` → `bb1e9c93…` → `b06d01f9…` → `ba1de6b2…`.

**⚠ 운영자 단계 — 같은 월물로 두 번째 세션을 돌리면 durable set 을 이어 쓴다.**
가드(#892)의 **승인된 생산자** 분기에는 「data dir 이 비어 있어야 한다」가 없다 — 비어 있는
스크래치를 요구하는 것은 **승인되지 않은** 저널일 때의 규칙(규칙 3)이고, 모든 행이
`tos-cp3-live/…` 이면 지정된 tenant 저장소가 그냥 허용된다. 그래서 같은
`TENANT_DATA_PARENT`·같은 월물로 두 번째 세션을 돌리면 **기존 코퍼스에 이어 붙는다**
(append-only 이므로 덮어쓰지는 않는다). 그것이 의도일 때도 있고(하루치를 이어 가는 운영),
아닐 때도 있다(실험을 섞어 버림). ⛔ 생산자 쪽은 다르다 — `TENANT_PRODUCER_SESSION_DIR` 은
**매번 새 디렉터리**여야 하고, 기존 파티션이 있으면 생산자가 기동을 거부한다(계획 §3.6
v4 재리뷰 L2). 요약하면: **저널과 생산자 세션 dir 은 세션마다 새로, durable set 은
운영자가 의도한 대로.** ⚠ 이어 쓴 durable set 에서는 §7.2-d 의 추출기가 **두 세션의
틱·id 를 모두** 읽는다(저장소가 append-only 이므로 당연하다) — 그래서 그 날짜의
오프라인 3종만 들고 B3 를 돌리면 `--consumed-ids` 가 **닫히는 쪽으로 실패한다**
(`diff_decisions.py::apply_consumed_filter` 가 「소비 id 가 조인된 아티팩트에 없다」로
거부한다). 두 세션을 한 번에 대조하려면 오프라인 3종도 두 날을 덮어야 하고, 하루만
보려면 **그 하루의 durable set**(= 새 잎)으로 돌려야 한다.

**⚠ 운영자 단계 — 개장 지연일에는 tenant 세션을 돌리지 않는다.**
수능일처럼 개장이 늦춰지는 날이 있다. 그런 날 생산자는 정규 개장 시각 기준으로 세션
창과 앵커를 잡으므로 프레임이 실제 장과 어긋난다. **기계적 거부는 없다, 그리고 그것은
의도다**(계획 §3.5, v2 재리뷰 M3): `resolve_open_anchor("auto")` 는 정적
`market_schedule.futures.regular.open` 을 돌려주고 날짜별 예외(`special_days`)가 비어
있어서, 그 값과의 비교는 **언제나 통과한다** — 아무것도 막지 않는 가드를 달면 막힌다고
믿게 만들 뿐이다. 그래서 이 줄은 운영자 체크리스트 항목이다. 날짜 목록이 config 에
생기면 그때 그 목록을 읽는 거부와 **구체 날짜 레드 테스트**를 같이 단다.

#### 7.2-d (이력) 종료 코드가 못 잡는 것 · 모드 · §3.6 대조 · 수용 기준

  - ⚠ **「세션 중에 멈췄다」≠「정지 시각 전에 사라졌다」** (2026-10-15 수정). 생산자는 세션의
    마지막 봉(15:45)을 발행한 **직후 설계대로 끝난다** — 경계 루프가
    `end_boundary`(15:46)를 지나면 `run_session` 이 반환하고 `main` 이 0 을 돌려준다. 정지
    시각은 늘 그보다 뒤이므로(genesis 는 15:50) **온전히 하루를 돈 세션은 전부** 생산자가
    먼저 사라진 상태이고, 이전 판 러너는 그 전부를 exit 5 로 보고했다(실측 2026-10-15
    15:50:02, `producer rc=0, run rc=0`).
  - **판정은 생산자의 종료코드 한 가지다**(PR #904 리뷰 1 라운드). 요약
    (`producer-summary.json`)으로는 가를 수 없다 — `finish()` 는 `main` 의 `finally` 에서
    돌고 `main` 은 그 뒤에야 0 을 돌려주므로, **rc 0 이면 `stage: finish` 요약은 이미 있다.**
    rc 0 은 「세션을 끝냈다」, rc 0 이 아니면(1 = 거부, 137 = 피살) 「세션 중에 멈췄다」이고,
    러너 로그의 `producer end: rc=…` 줄이 그것을 적는다.
  - 그래서 **「멈춤」의 실질은 생산자 쪽 거부로 들어왔다**(같은 리뷰): ① 연속
    `produce_error`(기존) · ② **폴링이 하나도 성공하지 않은 분이 연속
    `max_consecutive_fetch_error_minutes`** — 토큰이 끊긴 하루는 이전 판에서 `fetch_error`
    324 · `published` 0 인데도 rc 0 이었다 · ③ **장 마감 뒤 부팅**(경계 루프가 한 번도 안
    도는 경우). 셋 다 rc 1 이고 따라서 exit 5 다.
  - ⛔ **이 코드가 못 잡는 것 하나 — 「살아 있지만 멈춘」 생산자.** 정지 시각에 프로세스가
    살아 있으면 `SELF_STOPPED=0` 이고 우리 stop 경로가 SIGTERM 으로 끝내므로 exit 5 조건에
    걸리지 않는다. 생산자 자기 거부도 **경계 사이에서만** 검사하므로, 타임아웃 없는 소켓
    읽기나 돌아오지 않는 `sleep` 에 걸려 다음 경계에 도달하지 못하는 생산자는 양쪽 모두를
    통과한다 — 그 세션은 깨끗하다고 보고된다.
  - ⛔ **같은 공백의 두 번째 얼굴 — 「대답은 하는데 낡은」 피드.** 폴링은 정상
    (`rt_cd` 0 · 행도 온다)인데 그 행이 **갱신되지 않는** 경우다. 전송 포기 조건은
    폴링 성공을 보므로 트립하지 않고, 경계마다 그 분의 행이 없으니
    `no_raw_row_for_minute` 가 쌓이는데 — **그것은 점심 비거래 구간과 글자 그대로 같은
    모양이다**(§3.6 의 사유 이름도 같다). 그래서 세션은 rc 0 으로 끝나고 러너도 할 말이
    없다. 가르려면 「행이 오는데 시각이 안 움직인다」를 재는 계수가 필요하고, 그것도
    이번 라운드 밖이다.
  - **그 둘의 확인은 하나다 — 손으로**: 세션 뒤 `journal.jsonl` 의 **마지막 줄 시각이
    마감(15:45) 근처인지** 본다. 멈춘 생산자든 낡은 피드든 그 시각이 훨씬 이르다.
    닫으려면 생존 신호(러너가 읽는 하트비트, 또는 경계별 watchdog)와 위의 「행 신선도」
    계수가 필요하다.

    ```bash
    # tz 를 명시한다 — naive fromtimestamp 는 호스트 로컬 존을 쓰므로 이 호스트에서만
    # «우연히» 맞는다(CLAUDE.md: 비교·표시 전부 KST).
    tail -1 "$SESSION/journal.jsonl" | python3 -c \
      'import json,sys,datetime,zoneinfo; r=json.load(sys.stdin); \
       print(r["raw_event_id"], datetime.datetime.fromtimestamp(
           r["as_of_ms"]/1000, tz=zoneinfo.ZoneInfo("Asia/Seoul")))'
    ```
- **모드** — 러너는 맨 앞에서 `umask 077` 을 건다(프로세스 전체 · 모든 자식). 그래서 **이
  세션이 만드는 것은 전부 0700 디렉터리 · 0600 파일**이다 — 렌더 산출물 · data parent/잎과
  네 스토어 · 저널 · 세션 로그 · 생산자 아티팩트. ⚠ **2026-10-15 이전 판에는 `umask` 가
  세 `mkdir` 을 감싼 서브셸에만 있었고**, 그래서 디렉터리만 0700 이고 그 안의 **파일은
  0644** 였다(첫 genesis 세션 실측). §7.2-a 의 「왜 umask 인가」가 상주 래퍼에 대해 적은
  것과 **같은 결함·같은 처방**이다. 상주 래퍼가 전역으로 걸지 않는 이유(공개 0755 워크트리)는
  여기 해당하지 않는다 — 이 템플릿은 워크트리를 만들지 않고, 만드는 경로는 전부 좌표를 담는다.
  - ⛔ **러너는 정지 뒤에 모드 복구(`chmod` 훑기)를 «하지 않는다» — 의도된 거부다**
    (PR #904 Codex 재리뷰 MEDIUM). 상주 래퍼는 `umask` + 종료 뒤 `chmod` **둘**인데 이
    템플릿은 앞의 하나만 쓴다. 이유: `find … -exec chmod` 는 **검사와 syscall 사이에 창이
    있다** — step 6b 뒤에 조상이 심링크로 바뀌면 훑기 전체가 돌려지고, `find` 의 판정과
    `chmod` 사이에 교체되거나 두 번째 이름이 붙은 항목은 `find` 가 승인한 이름을 통해
    chmod 된다. `-P` 와 `-links 1` 은 **미리 만들 수 있는 모양**만 막고 이 창은 못 막는다
    (막으려면 매 단계 `O_NOFOLLOW` 의 fd 기반 순회가 필요하고, 그건 쉘 템플릿이 가질
    물건이 아니다). 그래서 모드는 **창이 없는 한 가지 기구**에서만 온다 — `umask`.
  - ⚠ **그래서 남는 것 하나, 운영자 손일이다.** 이 수정 **전에** genesis 된 durable 잎은
    태어날 때의 모드를 그대로 갖고 있다. 그 잎마다 **한 번** 돌린다(세션이 돌지 않을 때):

    ```bash
    LEAF=~/.local/state/tos/cp3-setup-d-long-data/<종목>
    chmod 700 "$LEAF" && chmod 600 "$LEAF"/*.sqlite3*
    # 확인: 0 건이어야 한다
    find "$LEAF" -maxdepth 1 -type f ! -perm 600 | wc -l
    ```

    ✅ **오늘(2026-10-15) genesis 된 잎은 이미 처리했다.** 2026-10-15 이후 세션이 만든
    잎은 처음부터 0600/0700 이므로 대상이 아니다.
  - ⛔ 그리고 **지정된 durable set 경로에 심링크를 끼우지 말 것** — step 6b 가 자식을 띄우기
    **전에** 세션 경로 넷(data parent · 잎 · 생산자 세션 dir · 렌더 산출물)에 심링크 성분이
    있거나 resolve 결과가 준 경로와 다르면 **거부한다**(세션이 기동하지 않는다. 의도된
    거동이고, 로그에 어느 성분이 링크인지 찍힌다). 그 검사는 **경로가 쓰여진 그대로인지**를
    묻는 것이고 — 증거가 운영자가 고르지 않은 곳에 떨어지는 것을 막는다 — 세션 내내
    유지되는 보장이 **아니다**. 그 구분이 위의 복구 거부 이유 그 자체다.

**세션 뒤 — §3.6 대조 (계획 §5 수용 기준).**

추출기는 세션 data dir 의 **세 저장소**를 읽는다: `marketfeed.sqlite3`(소비된 id),
`evidence.sqlite3`(결정), `inbox.sqlite3`(결정 ↔ 봉을 잇는 **키**. 커널 증거 레코드는
`capsule_id` 만 들고 있고 inbox 의 `DECISION_TICK` 이벤트가 그 capsule 의 snapshot_id 를
들고 있다). 셋 다 읽기 전용으로 열고 각자의 `PRAGMA user_version` 을 핀한다.

```bash
# ① 런타임이 실제로 소비한 id + 짝 없는 봉의 사유별 계수 + M5 의 value_view 계수
"$MAIN/.venv/bin/python" "$WT/tools/tos_cp3/session_inputs.py" consumed-ids \
  --data-dir "$SESSION/data/$INSTRUMENT" \
  --producer-log "$SESSION/producer/producer-log.jsonl" \
  --boot-snapshot "$SESSION/producer/boot-journal-snapshot.json" \
  --out "$SESSION/b3/consumed-ids.json"

# ② 실시간 결정 레코드(B1b 트레이스와 같은 모양)
#    ⛔ --boot-snapshot 은 2026-10-29 부터 필수다. ① 과 같은 이유 — 지정 잎은 세션을
#    누적하므로, 이 파일이 잎 전체를 담으면 ⑥ 이 거부한다(「live decision(s) name bars
#    that are not compared」). 실측: 10-28 세션 1,939 건.
"$MAIN/.venv/bin/python" "$WT/tools/tos_cp3/session_inputs.py" live-decisions \
  --data-dir "$SESSION/data/$INSTRUMENT" \
  --boot-snapshot "$SESSION/producer/boot-journal-snapshot.json" \
  --out "$SESSION/b3/live"

# ③ B1a 를 **생산자가 쓴 동결 프레임**에 돌리고(§3.6: 레거시 Parquet 이 아니다),
#    B2·B1b 를 잇고, B3 를 그 둘을 더해 돌린다.
#    --data-root 는 $SESSION/producer/market 이다.
#    START 는 stitch 의 **첫 날**(= `stitch.json` 의 가장 이른 세그먼트 날짜,
#    생산자 로그 `seed` 레코드의 `days_used` 첫 값과 같다), END 는 세션 당일.
"$MAIN/.venv/bin/python" "$WT/tools/tos_cp3/produce_fields.py" \
  --data-root "$SESSION/producer/market" \
  --symbol "$INSTRUMENT" --start "$STITCH_FIRST_DAY" --end "$SESSION_DAY" \
  --strategy-yaml "$WT/config/strategies/futures/setup_d_vwap_reversion.yaml" \
  --stitch-manifest "$SESSION/producer/market/stitch.json" \
  --out "$SESSION/b1a"

"$MAIN/.venv/bin/python" "$WT/tools/tos_cp3/emit_legacy_decisions.py" \
  --data-root "$SESSION/producer/market" \
  --symbol "$INSTRUMENT" --start "$STITCH_FIRST_DAY" --end "$SESSION_DAY" \
  --strategy-yaml "$WT/config/strategies/futures/setup_d_vwap_reversion.yaml" \
  --stitch-manifest "$SESSION/producer/market/stitch.json" \
  --out "$SESSION/b2"

# B1b — ⚠ 전략·바인딩은 **그 세션이 렌더한 트리**($TENANT_RENDER_OUT)의 것이다.
PYTHONPATH="$WT/tos/src:$WT/tos/runtime/src:$WT/tos/runtime" \
  "$MAIN/.venv/bin/python" -m cp3.runner \
  --fields   "$SESSION/b1a/fields.jsonl" \
  --strategy "$TENANT_RENDER_OUT/strategies/setup_d_long.strategy.yaml" \
  --bindings "$TENANT_RENDER_OUT/strategy_bindings.yaml" \
  --out      "$SESSION/b1b"

"$MAIN/.venv/bin/python" "$WT/tools/tos_cp3/diff_decisions.py" \
  --fields  "$SESSION/b1a/fields.jsonl" \
  --legacy  "$SESSION/b2/decisions.jsonl" \
  --tos     "$SESSION/b1b/trace.jsonl" \
  --consumed-ids "$SESSION/b3/consumed-ids.json" \
  --live    "$SESSION/b3/live/live.jsonl" \
  --out     "$SESSION/b3/report"
```

⚠ **B1b 가 세션의 «렌더된» 트리를 쓰는 이유 — 커밋된 사본 둘 다 이 저널에 못 쓴다.**
B1b 하네스의 커밋 사본(`tos/runtime/cp3/strategies/setup_d_long.strategy.yaml`)은 좌표가
**백테스트 리터럴**로 박혀 있다(`instrument: 101S6000` · `account: cp3-b1b-long`). 그 전략으로
`A05611` 저널을 돌리면 거절된다 — 선언한 종목과 들어온 봉의 종목이 다르다. 반대로 tenant 트리의
커밋 사본(`config/tos_runtime/cp3-setup-d-long/strategies/…`)은 바로 그 좌표 칸이 **`"TBD"`**
(앵커 두 줄 `&account`·`&instrument`, R2·R3 는 별칭)라 로더가 거절한다. 두 칸을 그 세션의 실제
계좌·월물로 치환한 유일한 사본이 렌더 산출물이므로, **B1b 는 `$TENANT_RENDER_OUT` 를 가리킨다.**
(그래서 이 대조는 세션 디렉터리를 지우기 전에 돌려야 한다 — 렌더 트리가 거기 있다.)

적어 둘 것(계획 §5):

- **M5** — 「STALE 로 소비된 줄」과 「소비되지 않은 줄」. **부팅 전 줄은
  두 계수에서 뺀다**(구조상 소비되지 않는다) — 그 수는 러너 로그의
  `consumed_stale_at_boot` 와 boot-journal-snapshot 에 있고, 그 스냅샷은 **부팅 직전에**
  다시 찍힌다(가드·렌더 동안 발행된 봉도 부팅 전 줄이다).
  - ⚠ **판정은 2026-10-23 부터 「둘 다 0」이 아니다**(운영자 지시 · 2026-10-22 실측):
    ① 수는 `session_day` **한 세션 날짜로 한정**해 읽고(지정 잎은 세션을 누적한다 — §4;
    문서의 **모든** 계수가 그 한 범위다 — `counts.snapshots` · `consumed_raw_event_ids` ·
    `raw_event_ids` 포함. 잎 전체 수는 `*_all_days` 로 따로 실린다. 그래서 이 문서는
    `diff_decisions.py` 에 **손으로 거르지 않고** 그대로 넣을 수 있다),
    ② stale 거절은 `post_boot_consumed_ids` 의 **0.5% 이하**면 통과(10-22 실측 1/409 =
    0.244%, 원인은 호스트 스케줄러 지터이지 늦은 생산자가 아니다 — 그 봉의 `as_of` 는
    분 마감 +2258 ms 로 세션 p50 2221 과 같고, 읽은 패스가 408 ms 루프에서 1280 ms 늦어
    922 ms 대 `max_age_ms` 800 이 됐다), ③ **stale 이 아닌 사유의 거절은 1건이라도
    소견**이다. `max_age_ms` 는 800 그대로다(운영자 결정 2026-10-09). ③ 을 가를 수 있는
    것은 런타임의 `MARKETFEED_FIELD_REFUSED` 행뿐이다 — M5 수 자체는
    「stale 이거나 시계 불명」의 상한이다.
  - ⛔ **스토어에서 stale 을 가리려 할 때 쓰면 안 되는 두 필드.** `validity.result` 는
    저장된 스냅샷 **전부**가 `INVALID` 이고(10-22 실측 712/712), `observations[0]
    .field_state` 는 stale 한 봉에서도 `VALID`/`ADMITTED` 다(레코드 적격성만 본다 —
    `_derive_observation_state`). 유일한 신호는 `field_evaluations[*].state == "UNKNOWN"`,
    그리고 이제 사유와 실측 age 를 실은 `MARKETFEED_FIELD_REFUSED` 행이다.
  - ⛔ **지속 레코드에 `STALE` 은 찍히지 않는다.** 발행기
    (`tos_runtime/marketfeed/snapshot.py::_derive_field_state`)는 `now_ms - as_of_ms
    > max_age_ms` 인 필드를 `FieldState.UNKNOWN` 으로 적고, 사유 문자열 `"stale"` 은
    **메모리 안**(`IssuedSnapshot.field_reports`)에만 남는다. 그래서 「지속된 STALE 을
    센다」는 계수는 아무리 stale 한 세션에서도 **언제나 0** 이다(실측: 정책
    `max_age_ms` 5000, `as_of+5001` 발행 → 지속 상태 `['UNKNOWN','UNKNOWN']`).
    2026-10-14 이전 판의 이 절과 추출기가 그 계수였다 — 둘 다 폐기한다.
  - 「**STALE 로 소비된 줄**」은 이제 **발행기가 값을 쥐고도 거절한 줄**로 센다:
    `consumed-ids.json` 의 `consumed_field_states` 가 소비된 id 마다
    `snapshots.snapshot_json` 의 `field_evaluations[*]` 와
    `preimages.preimage_json` 의 토큰을 **같이** 읽는다.
    **M5 의 첫 수 = `m5_post_boot_consumed_ids_with_a_present_value_refused_as_unknown`**
    — 「UNKNOWN 인 필드 평가 중, 그 `field_ref` 가 **그 봉의 preimage 에 있고**
    토큰이 **투영 가능**(bool/int/str; float 은 커널 `project_scalar` 가 거절)한
    것을 하나라도 가진 **부팅 후** 소비 id 의 수」(id 당 1 회). 읽는 법은
    **「stale 이거나, 평가 시각을 세울 수 없었거나」** — STALE 의 **상한**이고,
    낱말을 세는 계수와 달리 **stale 한 줄이 있는데 0 이 될 수 없다**.
    `_derive_field_state` 의 UNKNOWN 사유는 넷뿐이다: `absent_from_payload` ·
    `now_ms_unknown` · `stale` · `unprojectable`. 첫째는 **키 유무**로, 넷째는
    **투영 가능성**으로 갈라지고, 가운데 둘이 위의 수다. 갈라낸 둘은
    `unknown_field_causes` 에 **사유 이름별로** 따로 나오고 M5 수에 합치지 않는다 —
    페이로드에 없던 필드는 신선도에 대해 아무 말도 하지 않고, 투영 불가 토큰은 다른
    결함이다. 부팅 전 줄은 `pre_boot_…` 키로 따로 세고 그 수에서 뺀다(계획 §5 M5 가
    두 계수 모두에서 빼는 것과 같다). 관측 쪽 상태(`observations[*].field_state`)도
    `observation_field_states_not_valid` 로 따로 나온다 — 커널의 VALID 게이트
    (`tos.marketfeed.value.value_field_state`)가 둘 중 **나쁜 쪽**을 취하므로 한쪽이
    다른 쪽을 대신할 수 없다. `STALE`·`CONFLICTED`·`INVALID` 가 혹시 찍히면
    `other_field_evaluation_states` 에 이름 그대로 나온다(오늘은 전부 0 이어야 하고,
    STALE 이 0 이 아니면 **발행기가 바뀐 것**이므로 위 정의를 다시 좁힐 때다).
  - ⚠ **한 군데 빈틈, 적어 둔다**: `now_ms` 가 없을 때 발행기는 **투영 검사 전에**
    돌아가므로, 「있지만 투영 불가」인 필드는 시계 실패였을 수도 있는데 이 쪽은
    `unprojectable` 로 적힌다. 수 옆에 그 계수가 같이 나오니 사라지지는 않고, 시계가
    없으면 **선언된 모든 필드**가 UNKNOWN 이 되므로 같은 스냅샷에 투영 가능한 필드가
    하나라도 있으면 M5 수가 잡는다.
  - ⚠ **`consumed_value_view` 는 M5 의 수가 아니다.** 그 블록은 리졸버가 무엇을
    했는지를 적는다(`no_view` · `empty_view` · `values_admitted`). `_admit_one`
    (`tos/src/tos/marketfeed/value.py`)은 값 후보를 **열 가지** 사유로 떨어뜨리고,
    그중 상태에 관한 하나(`FIELD_STATE_NOT_VALID`)마저 STALE 과 UNKNOWN·CONFLICTED·
    INVALID 를 **같이** 접는다. 「`empty_view` + `no_view` 가 M5 의 첫 수」라고 적었던
    이 문서의 이전 판(그리고 추출기 docstring)은 **너무 넓고 방향이 거꾸로였다** —
    그 읽기는 ③ 이 **없던** §7.2-c 의 한 행짜리 합성 저널 논증이다(2026-10-14 정정).
  - **genesis 에서의 기대**: ③ 이 **있고** M6(교체 지연)가 `max_age_ms` 800 에 대해
    0.300 s 미만이면, **부팅 후 줄은 값이 허용된 채 소비되는 것이 정상**이다. 즉
    `m5_…_present_value_refused_as_unknown` 이 0 이고 `values_admitted` 가 소비 수에
    가까운 것이 통과한 모양이며, `empty_view` 가 세션 전체인 쪽이 **소견**이다.
  - ⛔ `consumed-ids` 는 **`--boot-snapshot` 없이는 거부**한다(2026-10-14). 문서가
    항상 M5 계수를 싣는데 그 계수는 부팅 전 줄을 빼야 하고, 플래그가 없으면 부팅 전
    줄이 **조용히** 부팅 후 수에 들어간다. 「부팅 전 줄 없음」은 **빈 리스트**이지
    파일 없음이 아니다.
  - 「**소비되지 않은 줄**」은 `unpaired_reason_counts` 의 `published_not_consumed` 다
    (`pre_boot` 와 생산자 사유들은 그 수에서 빠진다).
  - ⛔ **세션의 마지막 봉은 그 수에 들어가지 않는다** — `published_after_session_close`
    라는 제 사유로 나온다(2026-10-15 추가). 15:45 봉은 15:46 이 지나야 완성되므로
    (`SessionWindow.end_boundary`) 발행 스탬프가 **장 마감 뒤**이고, 스케줄러의 첫 절이
    `SKIPPED_SESSION_CLOSED` 라(`tos_runtime/marketfeed/scheduler.py`) 구조상 소비될 수
    없다. `pre_boot` 가 하루의 **앞** 끝에서 같은 일을 하는 것과 대칭이다. 판정은 **발행
    스탬프(`as_of_ms`) vs 그 봉 날짜의 마감**이고, 마감은 생산자 `seed` 레코드의
    `session_window` 에서 읽는다 — 15:45 는 어디에도 적혀 있지 않다. 마감 직전에
    발행됐는데 소비되지 않은 줄은 **진짜 누락**이라 `published_not_consumed` 로 남는다.
    ⚠ 그 수가 0 일 때 「없었다」인지 「묻지 못했다」인지는
    `generated_from.producer_session_close` 로 가른다(null = 생산자 로그에 seed 레코드가
    없어 애초에 판정 불가).
- **M6** — `producer-summary.json` 의 `max_stamp_to_replace_s` 가 0.300 미만인가.
- **B3** — `summary.json` 의 `unresolved.count` 가 0 인가. 대조 범위는
  `session_scope.consumed_id_filter`, 짝 없는 봉은
  `session_scope.unpaired_offline_records_by_reason` 에 사유별로 있다.
  - ⚠ `seed_day` 는 **세션 날짜보다 앞선 날의 봉**이다(2026-10-15 추가). 오프라인 삼총사는
    stitch 된 **시드 날들까지** 포함한 프레임 전체를 덮는데 생산자 로그는 당일 분(分)만
    처분하므로, 그 전부가 `unexplained` 로 떨어지고 있었다(genesis 실측: 1,233 = 411 봉 ×
    시드 3일, 당일 사유 79 건 대비). 지금 `unexplained` 는 **당일인데 설명되지 않는 봉**만
    세므로 다시 소견으로 읽을 수 있다. 세션 날짜는
    `session_scope.consumed_id_filter.session_day` 이고, null 이면(소비 id 가 한 날로
    모이지 않는 경우) 어떤 봉도 `seed_day` 로 부르지 않는다.
  `live_comparison.divergent` 는 **실시간 런타임이 오프라인 리플레이와 다르게 결정한
  봉 수**다 — 0 이 아니면 그것이 소견이고, B3 는 그것을 거부가 아니라 보고로 낸다.
  `live_comparison.kind_only_matches` 는 **반만 잰** 봉이다: 실시간 쪽이 `PROPOSAL`
  (「결정이 나왔고 no-action 은 아니다」)이고 오프라인이 ACTION 또는 FLAT 인 경우로,
  ACTION/FLAT 구분은 어떤 지속 레코드에도 없다(`position_effect` 는 `tos/src/tos/engine`
  어디에도 없다 — 실측). 정확 일치와 **합치지 않는다**: 합친 수는 「같게 결정했다」로
  읽히는데 절반은 재지 않았다.
- **`live.jsonl` 의 귀속** — `lineage.json` 의 `counts.attributed_by` 가
  `capsule_id`(결정이 자기 캡슐을 적은 경우)와 `evidence_seq_range`(캡슐을 적지 않는
  withheld/coordinator 거부)의 수를 가른다. **위치로 귀속하는 경로는 없다**:
  캡슐 없는 레코드는 그 증거 seq 를 품는 **유일한** 틱의 처리 구간
  (인박스 `handling_started_evidence_seq` < seq ≤ `consumed_evidence_seq`, 드라이버가
  각 이벤트 둘레에 쓰는 영수증 쌍)에 붙고, 둘 이상이거나 하나도 없으면 **거부**한다.
  캡슐로 붙은 레코드도 같은 구간으로 **교차 확인**한다(2026-10-14 정정 — 그 전까지는
  파일 순서의 「남은 다음 틱」이었고, 안 돈 틱 하나가 뒤의 모든 비-키 레코드를 **조용히**
  옆 봉으로 밀었다).
  `counts.ticks_without_a_decision` 이 0 이 아니면 큐에만 들어가고 안 돈 틱이 있었다는
  뜻이다(거부가 아니라 보고 — 돌아간 결정들은 그대로 키로 귀속된다).
- **실전 주문 TR 0 건** — 요청 로그 **둘 다**의 TR id 집합이 **조회 TR 둘의
  부분집합**이어야 하고(`FHKIF03020200` 분봉 · `FHMIF10000000` band) **메서드가 전부
  GET** 이어야 한다. 로그가 둘인 이유는 band 가 **별도 프로세스**이기 때문이다
  (band 계획 v3, 2026-10-16): 생산자는 `producer-log.jsonl`, band 프로브는
  `band-log.jsonl` 에 적는다. ⚠ **한쪽만 보면 band 호출을 아예 보지 못한다** — 그
  둘을 한 파일에 몰면 두 프로세스의 append 가 섞여 깨진 줄이 생기므로 파일을 가른
  것이고, 그 대가가 「검사가 두 파일을 읽어야 한다」다.

#### 7.2-d (이력) band — 설계 근거 · 실패 사유 · 판정

  ⚠ 이 확인이 유효한 이유는 **band GET 이 시도마다 자기 `tr_id` 를 적기 때문**이다
  (band 계획 §3.1 리뷰 LOW-2). 분봉 경로의 `page()` 는 모듈 상수 `TR` 을 적으므로, band
  호출이 그 경로로 로그됐다면 이 검사는 **그 호출을 보지 못한 채** 통과한다.

**세션 뒤 — band (band 계획 §3.1·§3.2·§4 수용 1 · v3 2026-10-16).**

band 원천은 **별도 단명 프로세스**다(band 계획 v3, 2026-10-16 운영자 결정):
`python -m tools.tos_cp3.live_producer.band_probe`. 실전 시세 키로 `FHMIF10000000` 을
한 번 GET-only 로 읽어 `<TENANT_PRODUCER_SESSION_DIR>/band.jsonl` 에 한 줄을 쓰고
(세 필드 `futs_mxpr`·`futs_llam`·`futs_sdpr` 를 **문자열 그대로** + 원 응답 바이트의
sha256) 끝난다. 런타임은 계속 **소켓 0 · 자격증명 0** 이다.

**왜 프로세스인가.** 네 번의 리뷰가 「생산자가 자기 HTTP 호출의 총 시간을 정직하게
묶을 수 없다」를 세 번 다른 방식으로 확인했다(phase 타임아웃은 청크 하나 ·
`iter_bytes()` 마감은 디코드된 바이트만 · 워커 스레드는 `close()` 에서 막히고 토큰
락을 쥔다). 상한은 이제 **감독 프로세스**가 쥔다 —
`timeout --kill-after=5s $BAND_PROCESS_TIMEOUT_S`. SIGKILL 은 협상하지 않는다.

**자격증명 분리는 그대로다**(③ 계획 §3.4). band 프로브는 실전 조회 키 두 개를
**자기가** 읽는다 — 자기 config 의 `env_file` 에서, 생산자와 똑같이. 러너 환경과
런타임 환경에는 실전 키가 들어가지 않고, 러너의 3b 가드도 그대로다.

**토큰 캐시는 생산자와 공유한다**(지문 경로 하나). 정상 경로에서 프로브는 생산자가
이미 받아 둔 **유효한 캐시 토큰을 재사용**하므로 발급 호출이 없다 — KIS 는 토큰
발급에 레이트 리밋이 있어서 이것이 중요하다. 두 프로세스가 같은 파일을 쓰므로
`shared/kis/auth.py::_save_token_cache_secure` 를 **임시 파일 + `os.replace`** 로
고쳤다(2026-10-16): 그 전에는 `O_TRUNC` 로 대상 파일을 비우고 썼으므로 읽는 쪽이
잘린 파일을 볼 수 있었고, 그 피해는 「캐시 무시 → 불필요한 재발급」이다.

**종료 코드**(러너가 읽는 유일한 인터페이스):
`0` 줄을 썼다 · `2` GET 전에 거부(기존 `band.jsonl` · 개장 전 · config/자격증명) ·
`3` 소프트 실패(GET 은 했고 쓸 줄이 없다) · `4` **드라이런**(`--confirm` 없음 — 아무것도
시도하지 않았다; 0 과 가른 이유는 0 이 「이제 줄이 있다」는 신호이기 때문이고, 러너는
항상 `--confirm` 을 주므로 이 코드를 보지 않는다) · **`1` 게이트 거부 또는 예상 밖
예외(달력 읽기 실패 포함) — 이 저장소의 결함이므로 러너가 부팅 전에 ABORT 한다.**

- 러너는 band 프로세스들이 끝난 뒤 **줄 하나**를 기다린다 — 파일 존재가 아니라
  **줄**이다: `trading_date` == 오늘(KST) · `instrument` == 그 세션의 월물 ·
  `as_of_ms` ≥ 개장. 세 조건 전부 필요하다: 파일만 보면 롤 날 어제 줄을, 날짜만 보면
  옆 월물 줄을, 그 둘만 보면 개장 전 기준가 줄을 믿는다. 개장 시각은 러너가 따로
  들고 있지 않고 **생산자 config 의 달력**에서 온다.
- 줄이 없거나 위 셋 중 하나라도 어긋나면 러너는 **멈추지 않고** 크게 적는다:

  ```text
  ⛔⛔ BAND ABSENT — 이 세션 전체 band UNKNOWN(송신 0)
  ```

  그 세션은 §4 수용 1 **실패로 기록**되지만 부팅은 그대로 간다 — 가격 수집과 B3 대조는
  그래도 가치가 있고, band 부재는 **보수 방향**이다(런타임에서 `UNKNOWN` → 송신 0).
- band GET 실패(전송 오류 · `rt_cd ≠ 0` · 필드 부재 · **압축 응답** · 크기 상한
  초과)는 줄을 **쓰지 않고** `band-log.jsonl` 에 사유를 남기고 **rc 3** 으로 끝난다.
  한 줄에 **두 층**이 적힌다: 호출 레코드의 `error` 가 사유 셋을 가르고
  (`band_auth_http_or_json_error` · `band_response_encoded` ·
  `band_response_too_large`), 프로브가 그 위에 `stage: band_fetch_failed` 와
  예외 문자열(`why`)을 남긴다. 사유를 보려면 `error` 를 볼 것 — `band_fetch_failed`
  는 「실패했다」까지만 말한다.
  ⚠ `band_response_encoded` 가 보이면 **서버가 압축을 시작했다**는 뜻이다 — 그때
  band 는 그 세션 내내 부재가 된다(요청은 `accept-encoding: identity` 인데 서버가
  압축하면, 푸는 것은 메모리 상한이 없는 일이라 거부한다 — 리뷰 5 라운드 Codex A:
  16,328 바이트가 16 MiB 첫 청크로 풀렸다). 처분은 운영자 결정 사항이고, 코드가
  조용히 풀어 주지 않는 것이 요점이다. ⚠ 그 실패는
  `max_consecutive_fetch_error_minutes`(분봉 폴링의 포기 조건)에 **넣지 않는다** —
  넣으면 가격 피드가 멀쩡한 세션이 band 하나로 하루를 잃는다.
- ⛔ `TENANT_PRODUCER_SESSION_DIR` 에 `band.jsonl` 이 이미 있으면 **band 프로브가 기동을
  거부한다**(계획 §3.2) — 모든 쓰기가 파일을 통째로 교체하므로, 롤 날 세션 dir 재사용은
  어제·다른 월물의 band 를 그날 내내 믿게 만든다. 세션 dir 은 **매번 새로**.
- 기동은 **`개장 + 한 경계`** 부터다(러너가 그때까지 잠든다, STOP_S 로 cap). 8b 는
  **승인된 아무 줄**에나 돌아오고 개장 전 줄로도 돌아올 수 있으므로, 그 대기가
  「개장 전에 읽지 않는다」를 집행하는 자리다. 세션 로그의
  `band launch: computed …s until open + one boundary` 줄이 그 계산을 적는다.
- 프로세스는 **한 번 + 실패 시 다음 경계에 한 번**, 정확히 둘이다. 두 번째도 실패하면
  그날 band 는 없다(`BAND ABSENT`). 러너 로그의 `=== BAND PROCESS #1/#2` 와
  `band process #N rc=…` 로 확인한다. rc 124/137 은 `timeout` 이 죽인 것이다.
- ⛔ **세션 stop 을 넘지 않는다.** 시도마다 **기동 직전에** 남은 시간을 다시 재고
  (`STOP_S − now − 1 − 마진 5 s`), 그 값이 SIGKILL 유예 이하면 **아예 띄우지 않는다**
  (`NO attempt started` → `BAND ABSENT`). 천장도 그 값으로 깎이므로
  `=== BAND PROCESS` 줄의 `ceiling + grace` 는 항상 `stop_in − margin` 이하다 —
  그 네 수가 한 줄에 같이 찍히는 이유가 이것이고, 그 부등식이 깨져 있으면 소견이다.
  ⚠ **남는 위험은 숨기지 않는다**: 그 마지막 계산과 실제 spawn 사이에 호스트가
  마진(5 s)보다 오래 멈추면 셸 스크립트로는 막을 방법이 없다. 그것까지 묶으려면
  시계를 쥔 쪽이 마감을 소유해야 하고(감독 프로세스가 `timeout` 을 계산), 그것은
  이 변경의 범위가 아니다(리뷰 7 라운드 Codex, 실측 0.68 s 초과).
- 재조회는 **PR-A 범위에서 빠졌다**(v3, 계획 §L L6). 기본값이 null 이었으므로 거동
  변화는 없다. 다시 필요해지면 프로브를 여러 번 띄우는 쪽이 자연스럽다.
- 줄 대기(`BAND_LINE_EXTRA_WAIT_S`, 기본 20 s)는 **프로세스들이 이미 제 차례를 쓴
  뒤**의 여유다 — 두 프로세스 타임아웃과 그 사이 경계는 위에서 이미 흘렀다. 실제
  상한은 세션 로그의 `band wait: allowance=…s … waiting up to …s` 줄에 찍힌다.

#### 7.2-d (이력) band 를 런타임이 실제로 썼는가

**세션 뒤 — band 를 런타임이 실제로 썼는가 (band 계획 §3.3·§4 수용 · PR-B, 2026-10-16).**

PR-B 부터 **LONG tenant 트리만** `band_source.kind: "producer_journal"` 을 선언한다
(상주 `paper` 와 SHORT 는 null — band 계획 §5). 그 트리의 세션에서는 위의 「줄이 쓰였나」
확인에 더해 **런타임이 그 줄을 읽었는지**를 증거로 확인한다. 상주·SHORT 세션에는
`VENUE_BAND_OBSERVED` 행이 **아예 없는 것이 정상**이다.

- ⛔ **`BAND ABSENT` 가 찍힌 세션은 여기까지다** — 그 세션의 band 는 UNKNOWN 이고 아래
  ②~④ 는 전부 「행 0건」으로 끝난다. 그것 자체가 §4 수용 1 **실패**의 기록이고,
  판정(ADMISSIBLE/INADMISSIBLE)은 믿지 않는다.
- ⚠ **2026-10-22 재범위 계획 M1 부터 ① 은 그 세션에서도 행 1건이다** — 읽기 시점이
  첫 스냅샷에서 **부팅(서비스 생성)** 으로 옮겨졌으므로, band 를 선언한 트리는 제안이
  하나도 venue 단계에 닿지 않아도 `outcome=REFUSED` + `reason=journal_absent` 한 행을
  남긴다. 그래서 **band 선언 트리의 ① 이 0 행이면 그 자체가 소견**이다(부팅하지
  않았거나 트리가 band 를 선언하지 않은 것). 2026-10-22 첫 세션이 ①=0 행으로 끝나
  수용 1c·2·3 을 「미집행」으로 적어야 했던 것이 이 변경의 이유다
  (`docs/broker-profiles/evidence/2026-10-22-cp3-band-first-session/README.md` §2).

```bash
# ① 런타임이 band 를 관측했는가 — 성공이면 outcome=OBSERVED 한 행.
#    실패면 같은 kind 에 outcome=REFUSED 와 **reason** 이 있다(journal_absent ·
#    trading_date_mismatch · instrument_mismatch · source_id_unapproved ·
#    off_tick_grid · non_integral_scale · band_not_ordered · line_key_set …).
sqlite3 -json "$SESSION/data/$INSTRUMENT/evidence.sqlite3" \
  "SELECT json_extract(payload_json,'\$.payload') FROM entries
     WHERE kind='VENUE_BAND_OBSERVED' ORDER BY seq" | python3 -m json.tool | head -40
```

- **digest 가 그 줄의 것과 같은가**(§4 수용 1). 행의 `raw_payload_digest` 는 **생산자가
  본 원 바이트**의 sha256 이고 런타임은 그것을 그대로 싣는다 — 그래서 같아야 하고, 행의
  `raw_payload_digest_source: "producer"` 가 출처를 적는다. 런타임은 그 바이트를 보지
  못했으므로 이 확인은 **두 기록의 일치**이지 디지스트 재계산이 아니다.

  ```bash
  # 기대: EQUAL
  python3 -c 'import json,sqlite3,sys; \
   line=json.loads(open(sys.argv[1],encoding="utf-8").read().strip().split("\n")[-1]); \
   db=sqlite3.connect("file:"+sys.argv[2]+"?mode=ro",uri=True); \
   rows=[json.loads(r[0])["payload"] for r in db.execute( \
     "SELECT payload_json FROM entries WHERE kind=? ORDER BY seq",("VENUE_BAND_OBSERVED",))]; \
   obs=[r for r in rows if r.get("outcome")=="OBSERVED"]; \
   print("rows:",len(rows),"observed:",len(obs)); \
   print("EQUAL" if obs and obs[0]["raw_payload_digest"]==line["raw_payload_digest"] \
         and obs[0]["raw_payload_digest_source"]=="producer" else "FINDING"); \
   print("line as_of_ms:",line["as_of_ms"],"evidence producer_as_of_ms:", \
         obs[0]["producer_as_of_ms"] if obs else None)' \
    "$SESSION/producer/band.jsonl" "$SESSION/data/$INSTRUMENT/evidence.sqlite3"
  ```

  ⚠ 행의 `as_of_ms` 가 아니라 `producer_as_of_ms` 와 비교한다. 관측의 `as_of_ms` 는
  **런타임의 단조 시계**(읽기 직전)이고 줄의 것은 생산자의 벽시계라, 두 수는 비교
  대상이 아니다(계획 §3.3).

- **스냅샷에 band 가 실렸는가**(§4 수용 3). `VENUE_SNAPSHOT_ISSUED` 행에 `band_digest`
  가 있고 `absent_fields` 에서 세 필드(`critical_input_snapshot_digest` ·
  `source_continuity_id` · `max_age`)가 **빠져** 있어야 한다. band 가 없는 세션에서는
  그 셋이 그대로 `absent_fields` 에 남는다 — 그것이 두 상태를 가르는 자리다.

  ```bash
  sqlite3 -json "$SESSION/data/$INSTRUMENT/evidence.sqlite3" \
    "SELECT json_extract(payload_json,'\$.payload.constraint_generation') AS gen,
            json_extract(payload_json,'\$.payload.band_digest')           AS band_digest,
            json_extract(payload_json,'\$.payload.absent_fields')         AS absent
       FROM entries WHERE kind='VENUE_SNAPSHOT_ISSUED' ORDER BY seq"
  ```

- ⭐ **그날 소비된 모든 가격이 band 안인가**(§4 수용 2 — 이 세션의 **가장 중요한** 확인).
  하나라도 밖이면 **band 원천이나 척도가 틀린 것**이고, 그 세션의 ADMISSIBLE/INADMISSIBLE
  판정을 믿지 않는다. 비교는 `price_min ≤ close_x100 ≤ price_max` 이고, 소비된 봉은
  위 「세션 뒤 — §3.6 대조」의 `consumed-ids.json` 이 이미 들고 있다.

  ⛔ **가격은 `consumed-ids.json` 에서 나오지 않는다**(2026-10-16 실측): 그 파일은
  `raw_event_ids` 와 계수만 싣고 **값은 싣지 않는다**(`session_inputs.py` 의 payload —
  `counts`·`raw_event_ids`·`unpaired_reason*`·`consumed_field_states`·
  `consumed_value_view`). 그래서 소비된 **id** 와 B1a `fields.jsonl` 의 **값**을 조인한다.
  값을 들고 있는 유일한 산출물이 B1a 이고, 그것은 §3.6 대조가 이미 만든다.

  ```bash
  # 기대: outside 0. band 행이 없으면 "SKIPPED (no band)" — 그 세션은 수용 1 실패다.
  python3 -c 'import json,sqlite3,sys; \
   ids=set(json.load(open(sys.argv[1],encoding="utf-8"))["raw_event_ids"]); \
   db=sqlite3.connect("file:"+sys.argv[2]+"?mode=ro",uri=True); \
   obs=[json.loads(r[0])["payload"] for r in db.execute( \
     "SELECT payload_json FROM entries WHERE kind=? ORDER BY seq",("VENUE_BAND_OBSERVED",))]; \
   obs=[r for r in obs if r.get("outcome")=="OBSERVED"]; \
   print("SKIPPED (no band)") or sys.exit(0) if not obs else None; \
   lo,hi=obs[0]["price_min"],obs[0]["price_max"]; \
   rows=[json.loads(l) for l in open(sys.argv[3],encoding="utf-8") if l.strip()]; \
   closes={r["raw_event_id"]:(r.get("fields") or {}).get("close_x100") \
           for r in rows if r.get("raw_event_id") in ids}; \
   vals=[(i,c) for i,c in closes.items() if c is not None]; \
   outside=[v for v in vals if not (lo<=int(v[1])<=hi)]; \
   print("band:",lo,hi,"joined:",len(vals),"of",len(ids),"consumed ids"); \
   print("outside:",len(outside),outside[:10]); \
   print("OK" if vals and not outside else "FINDING")' \
    "$SESSION/b3/consumed-ids.json" "$SESSION/data/$INSTRUMENT/evidence.sqlite3" \
    "$SESSION/b1a/fields.jsonl"
  ```

  ⚠ **`joined` 가 소비 id 수보다 작으면 그것도 소견이다** — 「밖이 없다」가 아니라
  「전부 묻지 못했다」이므로 두 수를 **함께** 출력한다. 추출기에 값 계수를 넣는 것은 별도
  변경이고, 넣기 전까지 이 조인이 수용 2 를 재는 자리다.

  ⚠ **`close_x100` 은 최상위가 아니라 `fields` 밑에 있다.** B1a 줄의 최상위 키는 다섯
  뿐이고(`raw_event_id`·`source_id`·`instrument`·`as_of_ms`·`fields` —
  `tools/tos_cp3/produce_fields.py`), 봉 값은 전부 `fields` 안이다. 그래서 위 조인은
  `(r.get("fields") or {}).get("close_x100")` 으로 읽는다.

  ✅ **이 명령은 돌려 봤다 — 진짜 B1a 산출물에 대고**(2026-10-20,
  `~/.local/state/tos/measure/cp3-short-parity-run1/b1a/fields.jsonl` 의 앞 200줄과 그
  `raw_event_id` 들을 소비 id 로, band 는 손으로 만든 `VENUE_BAND_OBSERVED` 행):

  ```text
  # band 가 전부를 담을 때 (57790–58540 = 그 200봉 종가의 실제 min/max)
  band: 57790 58540 joined: 200 of 200 consumed ids
  outside: 0 []
  OK

  # band 가 일부를 잘라낼 때 (57790–58165)
  band: 57790 58165 joined: 200 of 200 consumed ids
  outside: 93 [('101S6000:1m:20251208T084500+0900', 58345), …]
  FINDING

  # band 행이 없을 때
  SKIPPED (no band)
  ```

  ⛔ **2026-10-16 의 「돌려 봤다」는 거짓이었다**(PR #907 리뷰 HIGH-1). 그때의 입력은
  세 산출물의 모양을 **흉내 낸** 것이었고 B1a 의 중첩을 틀리게 흉내 냈다 —
  최상위 `close_x100` 을 읽는 그 명령을 위 진짜 파일에 돌리면 band 가 전부를 담아도
  `joined: 0 of 200 … FINDING` 이다(2026-10-20 재측정). 즉 **수용 2 는 통과할 수 없는
  확인이었다**. 시끄럽게 틀리므로 거짓 OK 는 아니었지만, 좋은 세션을 증명하지 못한다.
  교훈은 명령 쪽이 아니라 증거 쪽이다 — **흉내 낸 입력으로 「돌려 봤다」를 적지 말 것.**

- **기준가 대 전일 종가**(band 계획 §4.4a 잔여 위험의 **측정**). REAL 원천이 된 덕분에
  이제 오프라인 대조가 가능하다: 행의 `basis`(=`futs_sdpr` × 100)를 생산자 동결 프레임의
  **전일 종가**와 맞춰 보고, `symmetric_about_basis` 와 함께 증거 PR 에 적는다. 어긋나면
  「브로커가 전일 band 를 내줬다」의 첫 실측이다. ⚠ `symmetric_about_basis` 는 1단계
  **필요조건**이지 1단계 판별이 아니다 — 2·3단계도 기준가 대칭이다.

- 실패한 세션의 사유 읽는 법: `outcome: "REFUSED"` 행의 `reason` 이 어느 절이
  떨어뜨렸는지 **하나**를 지목한다. `journal_absent`/`journal_empty` 는 프로브가 쓰지
  못한 것(위 「세션 뒤 — band」로 간다) · `trading_date_mismatch`/`instrument_mismatch`
  는 세션 dir 재사용(롤 날) · `source_id_unapproved` 는 승인 밖 writer ·
  `off_tick_grid`/`non_integral_scale`/`band_not_ordered` 는 값 자체 ·
  `line_key_set`/`line_kind_unknown` 은 줄 모양이다.

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

### 7.4 (이력) cron 설치 기록

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

### 7.4 (이력) crontab 끼워 넣기 · flock 을 붙이지 않은 이유

- ⚠ **이 블록은 crontab 의 끝에 붙인다.** `CRON_TZ` 는 **그 뒤에 오는 줄에만** 적용된다.
  이 crontab 에는 이미 `CRON_TZ=Asia/Seoul` 선언이 두 개 있으므로, 중간에 끼워 넣으면
  아래쪽 남의 줄의 시간대까지 바꾼다.

- ⚠ **cron 줄에 바깥 `flock` 을 붙이지 않았다.** 이 호스트의 다른 슬롯과 다른 점이다.
  기동 줄은 장중 내내(≈ 7 h) 살아 있으므로, 같은 lock 파일을 정지 줄에도 붙이면 **정지가
  기동의 lock 에 막혀 영영 돌지 않는다.** 중복 기동 방지는 래퍼가 자기 lock 으로 이미 한다.
- 기동 줄의 cron 자식은 장중 내내 떠 있다. 이것은 정상이다(`wait`).

### 7.6 (이력) 2026-10-04 시점의 부재 기록

- 2026-10-04 현재 `~/.local/state/tos/paper-data` 는 **존재하지 않는다**(실측 — 월물별 잎
  드라이런도 스크래치 부모에서 돌았다, §7.9-leaf). 손으로 만들지 않는다. 첫 기동(10-06)에
  래퍼가 **부모**를 `umask 077` 로 만들고, 그 세션의 genesis 가 **잎 `A05610`** 안에 네
  스토어를 만든다.

### 7.7 (이력) 야간 콜드 백업 cron · 래퍼 잎 순회 증명

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

### 7.8 (이력) 2026-10-12 첫 롤 세션에서 볼 것

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

### 7.8 (이력) report.json 의 나머지 값 · data dir 성장 · 콜드 백업 결말 표

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

#### 7.9-held (이력) 되돌릴 수 없다

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
