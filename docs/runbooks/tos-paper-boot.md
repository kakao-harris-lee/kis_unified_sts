# TOS paper 운영 런북 — 상주 세션 · CP-3 tenant 세션 · 콜드 백업

- 이 파일은 **오늘 운영자가 돌리는 절차**만 담는다. 명령 · 경로 · 결말 표 · 분류 질의.
- 과거 실측 · 수용 기록 · 드라이런 · 설계 이력은 **git 이력에 있다**
  (`git log --diff-filter=D -- docs/runbooks/`). 다른 문서·코드·설정이 절 번호로 가리키는
  조각만 [`tos-paper-boot-history.md`](tos-paper-boot-history.md) 에 부록으로 남겼다 —
  §1 · §4 · §4-A · §4-B · §5 ④⑤ · §7.2 · §7.9-leaf · §7.10. 절 번호는 **양쪽에서 같다**.
- ⛔ 이 런북은 호스트를 바꾸지 않는다. cron · 설정 파일 · 모드 변경은 전부 운영자 결정이다.

## 0. 이 배포가 무엇이고 무엇이 아닌가 (요약 — 전문은 이력 §0)

- 채택 스코프는 `SYNTHETIC_FUTURES_ORDER` 다. **브로커에 도달하지 않는다 — 실주문 0.**
  좌표는 `.env.mock` 의 **모의** 선물 계좌이고, 실전 선물 계좌는 비협상 규칙상 영구히
  주문 경로에 오르지 않는다.
- 전략·construction·marketfeed·critical-input 은 **부팅 증명 픽스처**이지 거래 전략이 아니다.
- 상주는 **LONG 매일 + SHORT 분기 1회**다(운영자 결정 2026-10-03 · 이력 §7.10 3).

## 7. 상주 운영 — 매 거래일 (운영자 결정 2026-10-03 · **2026-10-06(화) 시작**)

> §1–§6 은 **1회성 부팅**의 절차다. 이 절은 그것을 **매 거래일 무인 반복**으로 돌리는
> 배선이고, §3 과 다른 점은 단 하나다 — **data dir 이 영속**이다. 그 하나가 §4-A 의 적용
> 범위, 증거 델타의 셈법, 콜드 백업의 전제를 전부 바꾼다.

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

**좌표 규율.** 위 여섯 트리(렌더 산출물 · 커스터디 · 세션 아티팩트 · 로그 · ops · 증거)는
전부 저장소 밖 **0700** 이고, `render.log` 의 계좌 지문 · 증거 행 · 그 질의 결과를 PR ·
계획 문서 · 텔레그램으로 **옮겨 적지 않는다**(전문은 이력 §7.2 「좌표 규율」·§7.2-a).

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

#### 7.2-b CP-3 tenant — 경로 (지정)

| 배포 | durable set **부모** | **잎** | 렌더된 설정 | 콜드 백업 **ops**(`COLD_CONFIG_DIR`) | 콜드 **보관소 부모**(`COLD_ROOT`, 유도) |
| --- | --- | --- | --- | --- | --- |
| 상주 paper | `~/.local/state/tos/paper-data` | `paper-data/<종목>` | `~/.config/tos/paper-config` | `~/.local/state/tos/paper-ops` | `~/.local/state/tos/paper-cold` |
| CP-3 tenant **LONG** (`config/tos_runtime/cp3-setup-d-long/`) | `~/.local/state/tos/cp3-setup-d-long-data` | `cp3-setup-d-long-data/<종목>` | `~/.config/tos/cp3-setup-d-long-config` | `~/.local/state/tos/cp3-setup-d-long-ops` | `~/.local/state/tos/cp3-setup-d-long-cold` |
| CP-3 tenant **SHORT** (`config/tos_runtime/cp3-setup-d-short/`) | `~/.local/state/tos/cp3-setup-d-short-data` | `cp3-setup-d-short-data/<종목>` | `~/.config/tos/cp3-setup-d-short-config` | `~/.local/state/tos/cp3-setup-d-short-ops` | `~/.local/state/tos/cp3-setup-d-short-cold` |

⛔ **방향을 한 data dir 에 섞지 않는다. 상주 잎에도 절대 섞지 않는다**(§7.10 3). 섞인
코퍼스는 §5 ⑤ 때문에 나중에 digest 로 갈라낼 수 없다. 그래서 LONG·SHORT 는 **부모부터**
다르다 — 같은 부모 아래 `long/`·`short/` 두 잎을 두는 배치를 쓰지 않은 이유는 그 부모가
콜드 백업 래퍼에게 「계약월 잎들의 부모」로 보이고, 그 래퍼의 잎 열거는 `A0####` 패턴
하나뿐이기 때문이다(아래).

#### 7.2-d CP-3 tenant 세션 — 오늘 돌리는 절차

**절차 (분리 워크트리 · `origin/main` · clean · 모의 전용).** §7.2-c 의 0)~2) 와 같고,
3) 저널 수기 생성이 **없어지고**, 4) 의 env 가 둘 늘어난다.

```bash
# 0)~2) §7.2-c 와 동일 — 워크트리, 계약월(INSTRUMENT), 스크래치 자리($SESSION)

# 3) (삭제) 저널은 생산자가 만든다. $SESSION/journal.jsonl 이 **없는지** 확인만 한다.
[ -e "$SESSION/journal.jsonl" ] && echo "이미 있다 — 새 세션 디렉터리를 쓴다"

# 4) 세션. 인스턴스 값은 전부 env 이고 기본값이 하나도 없다.
TENANT_LOG=$SESSION/session.log \
TENANT_PYTHON=$MAIN/.venv/bin/python \
TENANT_TREE=cp3-setup-d-long \
TENANT_DIRECTION=LONG \
TENANT_RENDER_OUT=$SESSION/config \
TENANT_DATA_PARENT=$SESSION/data \
TENANT_JOURNAL=$SESSION/journal.jsonl \
TENANT_STOP_AT='15:50' \
TENANT_ENV_FILE=$WT/.env.mock \
TENANT_CUSTODY_ROOT=~/.local/state/tos/paper-custody \
TENANT_ENVIRONMENT_LABEL=paper \
TENANT_PRODUCER_CONFIG=$WT/config/tos_probes/cp3-live-producer.yaml \
TENANT_PRODUCER_SESSION_DIR=$SESSION/producer \
  "$WT/tools/tos_cp3/runners/run_tenant_session.sh"
```

- 지정된 durable set 으로 genesis 하려면 `TENANT_DATA_PARENT` 를 §7.2-b 의 경로로
  바꾼다 — 이제 가드가 그것을 **허용한다**(모든 행이 `tos-cp3-live/…` 이므로). 그
  판단은 운영자의 것이고, 그 디렉터리의 첫 genesis 는 되돌릴 수 없다.
- 러너는 끝에 생산자 요약(`producer-summary.json`: 계수와 동결 프레임 sha256)과
  durable set 의 `snapshots`·`entries` 분포를 찍는다.
- **종료 코드**: 0/143 은 정상(정지창까지 간 세션은 우리 stop 경로의 SIGTERM 으로 끝나므로
  143 이 보통이다) · 3 은 가드·렌더·라벨 등의 ABORT · 4 는 가드 모듈 세대 불일치 ·
  **5 는 「런타임은 요청대로 끝났는데 생산자가 세션 «중에» 멈췄다」**(그 분부터 저널이 자라지
  않았으므로 깨끗한 세션이 아니다 — 계획 §3.5) · 143/130/129 는 받은 신호.
- **런타임의 종료 코드는 `timeout` 에게 묻지 않는다** (#987). 런타임은 자기 코드를
  `$TENANT_LOG.run-rc` 에 「이 부팅의 토큰 + 코드」로 적고, 러너의 12단계가 그것을 읽어
  기록한다 — 그래서 호스트의 coreutils 가 9.4 든 9.10 이든(9.10 은 우리가 보낸 SIGTERM 에
  대해 124 를 답한다) 같은 코드가 남는다. 정지 중 **실패**(예: durable set 을 닫다 rc 1)는
  정상 정지(143)로 보이지 않는다. 그 파일이 **없는데** `timeout` 이 124 를 답했다면 런타임이
  적기 전에 SIGKILL 된 것이므로 정상 정지로 기록하지 않고 124 를 남긴다(WARN 한 줄).

**세션 뒤 — §3.6 B3 대조는 은퇴했다 (2026-11-13).** 레거시 Setup D 증인과의 장후
대조(러너 step 14 · `tools/tos_cp3/post_session_b3.py` · `config/tos_cp3_b3.yaml` ·
B2/B3 도구와 `tos` 쪽 B1b 러너)는 P2-b 동등성 측정이 끝나면서 삭제했다 — 선언형 생산
경로가 레거시 경로와 626,745 셀 0 불일치로 같다는 측정(#1065 · #1066)이
`docs/plans/2026-11-11-tos-platform-roadmap.md` §7 결정 3 이 건 조건이었다. 세션 디렉터리에
`b3/` 는 더 생기지 않고, `sts tos status` 도 그 줄을 보여 주지 않는다. 그때의 실측
(세 세션 409 봉 · unresolved 0 · divergent 0)과 선언된 차이 B1b-D1 의 해설은 git 이력에
있다 (`git log --diff-filter=D -- docs/runbooks/`).

깨끗한 거래일 판정은 이제 「세션이 기동해 `clean_run_rcs` 안의 rc 로 끝났다」 하나다
(`config/tos_status_board.yaml::clean_streak`).

**세션 뒤 — 실전 주문 TR 0 건.** 요청 로그 **둘 다**(`producer-log.jsonl` ·
`band-log.jsonl`)의 TR id 집합이 조회 TR 둘(`FHKIF03020200` · `FHMIF10000000`)의
부분집합이고 메서드가 전부 GET 이어야 한다. 왜 두 파일인지는 이력 §7.2-d.

  ```bash
  # TR 과 메서드의 분포. 기대: 두 TR 뿐 · method 는 GET 뿐. 두 로그를 함께 넘긴다.
  # 한 줄 꼴로 둔다 — 들여쓴 heredoc 은 종료 표지를 못 만나 붙여 쓰면 멈춘다.
  python3 -c 'import json,sys; \
   rows=[json.loads(l) for f in sys.argv[1:] for l in open(f,encoding="utf-8") if l.strip()]; \
   trs={r["tr_id"] for r in rows if r.get("tr_id")}; \
   mth={r["method"] for r in rows if r.get("method")}; \
   print("files:",len(sys.argv)-1,"tr_ids:",sorted(trs),"methods:",sorted(mth)); \
   print("OK" if trs<={"FHKIF03020200","FHMIF10000000"} and mth<={"GET"} else "FINDING")' \
    "$SESSION/producer/producer-log.jsonl" "$SESSION/producer/band-log.jsonl"
  ```
  ⚠ 두 파일 중 하나가 **없으면** 그것도 소견이다. 단 `band-log.jsonl` 부재의 원인은
  **둘**이다: ① band 프로세스가 한 번도 뜨지 않았다 ② 떴지만 **GET 전에 거부**했다
  (rc 2 — `config` 에서 거부되면 로그를 열기 전에 끝난다, `refused at config`). 그
  둘은 러너 로그가 가른다 — `=== BAND PROCESS` 줄이 **없으면** ①, 있고 `rc=2` 와
  `band_probe: REFUSED —` 가 있으면 ②다. 「로그가 없으니 안 떴다」로 단정하지 말 것.
  `producer-log.jsonl` 이 없으면 세션이 시작되지도 않았다.

**세션 뒤 — band 가 쓰였는가.** 판정 기준과 설계는 이력 §7.2-d. ⚠ 2026-10-22 재범위 M1
부터 런타임은 **부팅 때** band 를 읽으므로, band 를 선언한 트리(LONG tenant)는 제안이
하나도 없어도 `VENUE_BAND_OBSERVED` 가 **최소 1 행**(OBSERVED 또는 사유 있는 REFUSED)
이다 — **0 행이 소견**이다(이력 §7.2-d ①). 1 행보다 많은 것은 소견이 아니다:
`read_on` 에 `"phase_change"` 가 있으면 세션 구간이 바뀔 때마다 한 행이 더 붙는다.

- 확인:

  ```bash
  cat "$SESSION/producer/band.jsonl"                 # 줄 하나
  grep -c 'BAND ABSENT' "$SESSION/session.log"       # 0 이어야 한다
  grep 'band_published\|band_fetch_failed' "$SESSION/producer/band-log.jsonl"
  ```

#### 7.2-e CP-3 tenant 세션 — 매 거래일 무인 cron (재범위 M1 · 운영자 2026-10-22 · M2 주식 2026-11-05)

§7.2-d 를 거래일마다 LONG·SHORT 한 번씩, §7.2-f 를 **주식 tenant 마다** 한 번씩 무인으로 돌린다
(운영자 지시 2026-11-19 — 종목당 tenant 하나, §7.2-f 「종목당 tenant 하나」). 2026-10-22 에
손으로 넣은 두 줄(비커밋 `~/.config/kis-probes/run-cp3-tenant-daily.sh`)을 저장소가 소유하는
형태로 바꾼 것이고, **STOCK 은 운영자 결정 2026-11-05**(「주식 트리 매일 cron 등록 진행해」)로
11-03 의 위임받은 1회 절차(`~/.config/kis-probes/run-stock-mock-20261103.sh`)를 같은 래퍼의 세
번째 방향으로 옮긴 것이다 — 11-20 전에 M2(첫 모의 체결)가 매 거래일 한 번씩 기회를 갖도록.
LONG·SHORT 는 synthetic 이라 **아무것도 송신하지 않고**, 주식 tenant 들은 **모의 계좌로 실제
송신한다**(실주문 0 · 1주 · 종목당 1 포지션).

| 무엇 | 어디 |
| --- | --- |
| 래퍼 원본(추적) | `tools/tos_cp3/runners/cp3_tenant_daily.sh` — 방향 `LONG`·`SHORT`·`STOCK` |
| 래퍼 설치본 | `~/.config/kis-probes/run-cp3-tenant-daily.sh` (mode 700 · 설치기가 **`origin/main` 에서** 복사) |
| 설치기 | `tools/tos_cp3/runners/install_tenant_cron.sh` — **기본 dry-run** · `--apply` · `--remove` · 멱등 |
| cron 블록 | `# BEGIN CP3_TENANT_DAILY` … `# END CP3_TENANT_DAILY` — LONG `38 8 * * 1-5` · SHORT `40 8 * * 1-5` · **STOCK `53 8 * * 1-5`** + 같은 블록의 `@reboot` catch-up 세 줄(아래) |
| cron stdout | `~/.local/state/tos/cp3-{long,short,stock}-tenant-daily.cron.log` (⚠ 로테이션 없음) |
| 세션 아티팩트 | `~/.local/state/tos/cp3-sessions/{long,short}-<YYYYMMDD>/` · 주식은 `stock-r1-<YYYYMMDD>/` (`runner.out` · `session.log` · `producer/` · 렌더본 — 선물은 `config/`, 주식은 `render/` · 주식만 `runner.pid`·`approval.out`) |
| 그날의 워크트리 | `~/.local/state/tos/measure/wt-cp3-{long,short}-<YYYYMMDD>` · 주식은 `wt-cp3-stock-r1-<YYYYMMDD>` — 다음 거래일 호출이 지운다 |
| 잠금 | `/tmp/cp3-{long,short,stock}-tenant-daily.wrapper.lock` — 래퍼 **안에서** `flock -n`. 10-22 손 설치 줄이 바깥 flock 으로 잡던 `….lock` 과 **다른 경로**다 — 같은 경로면 바깥·안쪽 잠금이 서로 막아 매일 거부된다 |

**설치 (PR 머지 뒤, 운영자).** 먼저 dry-run 으로 diff 를 보고, 같은 명령에 `--apply` 를 붙인다.

```bash
cd /home/deploy/project/kis_unified_sts && git fetch -q origin && git merge --ff-only -q origin/main \
  && tools/tos_cp3/runners/install_tenant_cron.sh            # dry-run: diff 와 복사 계획만
tools/tos_cp3/runners/install_tenant_cron.sh --apply         # 백업(crontab.bak.<ts> · 래퍼 .bak.<sha12>) 뒤 기록
```

- `--apply` 는 셋을 거부한다: 설치기 자신이 `origin/main` 판과 바이트가 다를 때 · 호스트 zone 이
  `+0900` 이 아닐 때(Ubuntu cron 3.0pl1 은 **`CRON_TZ` 를 구현하지 않는다** — 블록의 `CRON_TZ`
  줄은 관례로 두지만 KST 보장은 호스트 zone 이다. 래퍼도 매 호출 같은 검사를 하고 실패면 알린다) ·
  `~/.local/state/tos` 가 없을 때.
- dry-run 도 `--apply` 도 둘을 거부한다: `crontab -l` 이 「`no crontab for`」 아닌 이유로 실패할 때
  (빈 crontab 으로 읽으면 상주·콜드 백업 줄이 통째로 지워진다) · `BEGIN` 표지에 짝 `END` 가 없을 때.
- 순서는 **crontab 먼저, 래퍼 다음**이고, 래퍼 단계가 실패하면 crontab 을 백업으로 되돌리고 래퍼도
  `.bak` 에서 복원한다 — 실패한 설치는 둘 다 원래대로 남는다.
- 블록 밖의 `# cp3-{long,short,stock}-tenant-daily` 꼬리표 줄(10-22 손 설치분)은 지운다 — 한 방향이 두
  번 걸리지 않게. 그 위의 꼬리표 없는 `CRON_TZ=Asia/Seoul` 한 줄은 남는다(무해). 나머지 줄은
  바이트 그대로다(`# run-stock-mock-<날짜>` 같은 1회용 줄도 **남는다** — 꼬리표가 다르다. 설치
  당일에 아직 발화하지 않은 1회용 주식 줄이 있으면 그 줄을 먼저 손으로 지우고 설치한다). 제거는
  `--remove`(dry-run) → `--remove --apply`.
- 시각이 08:45 가 아니라 08:38/08:40 인 이유: 생산자가 CONTINUOUS 08:45 전에 떠 있어야 하고,
  두 생산자가 REAL 조회 키를 함께 쓰는데 KIS 토큰 발급이 분당 1 회다. STOCK 이 08:53 인 이유는
  §7.2-f 의 시작 창 08:52–09:05(주식 CONTINUOUS 개장 09:00 · 첫 행 대기 상한 600 s)이고, 선물
  두 줄과 간격을 둘 필요가 없는 이유는 주식 생산자가 **주식** REAL 키, 주식 런타임이 **모의** 키를
  써서 앱 키 지문이 서로 다르기 때문이다(분당 1회 발급이 겹치지 않는다). **주식 세 줄끼리는**
  08:53·08:55·08:57 로 2분 간격을 둔다 — 세 주식 생산자는 같은 주식 REAL 키를 쓰므로 선물 두
  줄과 같은 이유가 그대로 적용된다(세 생산자는 `token_cache_dir` 도 공유해 캐시된 토큰을
  재사용하지만, 캐시가 비어 있는 그날의 첫 세션에서는 간격이 유일한 보호다).

**`@reboot` catch-up 세 줄 (#1038).** 2026-11-06 호스트가 03:56 에 멈추고 09:00:53 에 재부팅됐고,
이 cron(Ubuntu 3.0pl1)은 **놓친 줄을 다시 돌리지 않는다** — 08:38·08:40·08:53 이 전부 미발화했고
그날 세션은 09:09–09:13 에 손으로 살렸다(래퍼는 늦은 시작을 받는다). 그래서 설치기가 같은 블록에
방향별 `@reboot` 줄을 하나씩 더 쓴다 — `sleep 90`(LONG) · `240`(SHORT) · `390`(STOCK) 뒤에
`run-cp3-tenant-daily.sh <DIR> --catch-up HH:MM`, **HH:MM 은 정규 줄과 같은 스케줄 상수에서
만든다**(설치기의 `hhmm`, 두 번 타이핑하지 않는다). sleep 은 부팅이 끝날 시간(시계·네트워크·래퍼의
fetch)이고 LONG·SHORT 사이를 150 s 벌린 것은 정규 줄이 2분 벌어진 것과 같은 이유다(두 생산자가
REAL 조회 키를 공유 · KIS 토큰 발급 분당 1회). `@reboot` 에는 요일 필드가 없다 — 거래일 판정은
래퍼의 달력 단계가 그대로 한다. 줄에 `%` 를 쓰지 않는다(이 cron 은 명령 필드의 `%` 를 줄바꿈으로
읽는다 — 필요하면 `\%`). 제거는 정규 줄과 같다(`--remove` 가 블록째 지운다).

`--catch-up HH:MM` 은 **넷이 모두 참일 때만** 평소 실행 경로로 들어가고, 아니면 이유 한 줄
(`CATCH-UP SKIP …`)을 로그하고 **rc 0 · 알림 없이** 끝난다.
① 오늘이 거래일 — 새 판정이 아니다. 그대로 위의 휴장 판정을 타고 휴장일은 기존 조용한 SKIP 이다.
② 지금(KST) ≥ HH:MM — 부팅이 그 분보다 이르면 정규 줄이 아직 발화하므로 아무것도 하지 않는다.
③ 지금 < 그날 stop_at — 실행 경로와 **같은** 도출이라 개장 지연일(#924)에는 이 상한도 함께 늘어난다.
④ 오늘 세션 디렉터리가 없다 — 장중 재부팅으로 끊긴 세션은 **자동 재기동하지 않는다**(두 번째 세션은
운영자의 RUN=2 결정 · §7.2-f). 돌고 있는 세션은 디렉터리를 갖고 있으므로 `lock busy` 실패로
알리지 않고 여기서 조용히 끝난다. 넷이 통과하면 텔레그램에 `재부팅 catch-up 기동` 한 줄을 보낸 뒤
정규 줄과 **똑같이** 돈다(같은 잠금 · 같은 단계 · STOCK 은 `render ok` 뒤 상시 승인까지).

catch-up 에서 **잠금이 이미 잡혀 있는 것도 조용한 SKIP** 이다(rc 0 · `CATCH-UP SKIP — lock held
by the regular run`). 겹치는 창이 실제로 있다: 호스트가 08:36:30–08:37 에 부팅하면 LONG 의
`sleep 90` 이 08:38 호출 **안**에 떨어지고, 08:46:30–08:47 이면 STOCK 의 `sleep 390` 이 08:53
호출 안에 떨어진다 — 그 호출은 아직 세션 디렉터리를 만들지 않았으므로 ④ 가 보지 못한다. 그 줄이
이미 오늘 세션을 시작하고 있으니 `lock busy` 알림은 거짓 경보다(정규 줄은 그대로 rc 75 + 알림).
`--catch-up HH:MM` 뒤에 **인자를 더 주면 rc 2** 로 거부한다 — cron 줄의 오타를 반만 해석해서
세션을 띄우지 않는다.

⚠ 상주 paper 세션(`tos-paper-session.sh`, 저장소 밖 · 08:45 줄)은 이 블록이 아니다 — 그 `@reboot`
줄은 운영자가 손으로 단다(#1038 범위 밖).

**한 호출이 하는 일.** 잠금 → 같은 날 세션 디렉터리가 있으면 거부 → durable set 부모
(§7.2-b)가 없으면 거부(첫 genesis 는 운영자 몫) → 그 방향의 어제 워크트리 제거(`--force` 없이)
→ fetch → **(STOCK) 운영 전송 설정 키 대조** → `origin/main` 분리 워크트리 → **개장 판정**(아래)
→ `run_tenant_session.sh`(정지 = 그날 종료 + `CP3_DAILY_STOP_AFTER_CLOSE_MIN`:
선물 +5분 = 평일 15:50, 주식 +10분 = 평일 15:40 · 개장 지연일은 §7.2-g) → **(STOCK) `render ok` 뒤 상시 승인 작성**.

**개장 판정 (#1143 · 운영자 2026-11-20 「캘린더 관리가 리스크가 안 되어도 돼」).**
`tools/tos_cp3/ops/market_open.py` 가 **그 트리의** 달력과 브로커로 순서대로 판정한다 —
① 주말 ② `CP3_DAILY_EXTRA_CLOSED`(기본 빈 값) ③ 그 트리 달력의 `holidays`(= 「알려진 휴일」,
KRX 연말 `2026-12-31` 포함) ④ KIS **국내휴장일조회**(`CTCA0903R` GET · 실전 키 · 개장일여부
`opnd_yn`) ⑤ KIS 를 못 읽으면 **달력에 없는 평일은 거래일**. ①~③ 이 닫는 날은 브로커를 아예
묻지 않는다(런타임 달력 게이트와 같은 판정이고, KIS 가 요청하는 「가급적 1일 1회 호출」도 아낀다).
그날의 답은 `$ST/market-open/<YYYYMMDD>.json` 에 캐시되고 다섯 tenant 의 cron 줄이 `flock` 으로
그 하나를 공유한다 — 호스트당 하루 한 번만 KIS 를 부른다(토큰 캐시도 같은 디렉터리).
`--preflight` 는 `--cache-only` 로 돈다: 캐시된 답과 달력만 읽고, 토큰도 캐시 파일도 만들지 않는다.
⚠ **「달력에 그 해 휴장일이 없다」는 거부는 없어졌다** — 달력이 2026 만 담고 있으므로 그 거부는
2027-01-01 에 모든 tenant 를 세웠다. 이제 그 해는 ④ 가 판정한다.

**달력에 없는 휴장(④ 가 `opnd_yn=N`)만 안내 한 줄을 보낸다.** ①~③ 이 닫는 날은 조용하다(운영자가
이미 아는 날이다). ④ 가 닫으면 세션은 똑같이 조용한 SKIP(rc 0, 실패 아님)이지만 **호스트 전체에
하루 한 줄** 텔레그램이 간다 — 그 날짜를 각 tenant 달력의 `holidays` 에 넣게 만드는 유일한 신호다.
중복 방지는 `$ST/market-open/<YYYYMMDD>.notified` 를 `noclobber`(O_EXCL)로 **만드는 쪽**이 이기는
것이라, 다섯 줄이 같은 초에 떨어져도 하나만 보낸다. `--preflight` 는 읽기 전용이라 보내지 않는다.
- **그래도 그날 세션을 돌려야 하면:** `$ST/market-open/<YYYYMMDD>.json` 의 `opnd_yn` 을 `Y` 로 고친
  뒤 그 tenant 의 `--catch-up <정규분>` 을 다시 돌린다(캐시된 답이 그대로 판정이 된다).
- **KIS 에 다시 묻고 싶으면:** 그 `.json` 을 지우고 다시 돌린다 — 답이 같으면 또 SKIP 이다. 안내를
  한 번 더 받고 싶으면 `.notified` 도 같이 지운다.

**STOCK 만의 세 단계.** 셋 다 §7.2-f 를 손으로 돌릴 때와 같은 일을 래퍼가 하는 것이고, 앞의
둘은 **휴장 판정 뒤·러너 전**에 돈다(휴장일은 운영 파일이 어떻든 조용히 SKIP 해야 한다).
- **운영 전송 설정 키 대조** — `$ST/cp3-setup-d-stock-ops/kis_mock_transport.yaml` 의 최상위 키를
  `origin/main:tools/tos_cp3/runners/setup_stock_mock_once.sh` 의 정본 블록과 비교한다. 다르면
  rc 2 로 거부하고(워크트리는 되돌린다) 알린다. 그 상태로 부팅하면 `KisMockTransportConfigError`
  로 거부돼 송신 0 이다 — 실제 사례 10-30 r1, §7.2-f. 값이 아니라 **키 이름만** 본다.
- **어제 승인 치우기** — 승인 파일 경로는 **고정**이다(`approvals/standing-session.yaml` =
  `tos_runtime.authority.standing.STANDING_APPROVAL_RELPATH`). 그래서 매일 돌리면 두 가지가 겹친다:
  ① 작성기는 파일이 있으면 `--replace` 없이는 거부하므로 **둘째 날부터 쓰기가 rc 1** 이고 신호가
  4단계에서 멎는다, ② `--replace` 만으로도 모자라다 — 런타임의 `bind_at_boot()` 이 **부팅 시점에
  그 경로에 있던 것**의 digest 를 결속하고, 그 뒤에 쓰인 파일은 그 프로세스가 사는 동안
  `digest_changed_since_bound` 로 거부된다. 그래서 **러너 전에** 다른 날짜 파일을
  `$ST/cp3-setup-d-stock-custody/approvals-archive/standing-session.<그날짜>.yaml` 로 **옮긴다**
  (지우지 않는다 — 그날 권한의 기록이다 · 이름이 겹치면 `.1`·`.2` 를 붙이고 **절대 덮어쓰지 않는다** ·
  `approvals/` **밖**에 두는 이유는 그 디렉터리가 제안별 승인 파일 자리이기 때문이다). 파일이 이미
  **오늘 날짜**면 그대로 두고 아래 쓰기를 **건너뛴다**(재작성은 운영자의 `--replace`). 파일을 읽을 수
  없으면(날짜 형식이 다름 · YAML 아님) **추측하지 않고** rc 2 로 거부하고 알린다 — 송신 0.
- **상시 승인(#955)** — `session.log` 의 `render ok` 를 기다린 뒤(상한 20분) 그날짜 승인을
  `--replace` 없이 쓴다. 이것이 11-03 위임 절차의 마지막 단계였고, 승인이 없으면 신호가 와도
  4단계에서 멎어 송신 0 이다. 세션이 render 전에 끝났으면 **쓰지 않는다**(묶을 렌더본이 없다).
  쓰기 rc 는 cron 로그에 `write-standing-approval rc=N` 으로 남고 출력은 `approval.out` 에 있다.
  실패는 알리지만 세션을 죽이지 않는다 — 종료 줄은 러너 rc 를 그대로 싣는다.

`--preflight` 는 셋 다 **읽기 전용으로** 보고한다(키 일치 여부 · 승인 슬롯이 비었나 · 오늘 것인가 ·
다른 날짜면 어디로 옮겨질 것인가). 옮기지 않는다.

⚠ 어제 워크트리 제거의 주식 쪽 glob 은 `wt-cp3-stock-r*-2*` 라서 **지난 날짜의 손 r2 워크트리도
함께 지운다**(그날의 `r1`·`r2` 는 둘 다 지난 날짜다). 세션 아티팩트(`cp3-sessions/…`)는 건드리지
않으므로 로그·증거는 남는다 — 그 안에서 조사할 것이 있으면 워크트리가 아니라 세션 디렉터리를 본다.

**텔레그램 (briefing 채널 · 자격증명은 상주 래퍼와 같은 `$MAIN/.env` 두 줄).** 본문은 rc ·
방향 · 날짜 · 경로뿐이다 — `runner.out` 은 옮기지 않는다(좌표 규율).

| 결말 | 텔레그램 | 래퍼 rc |
| --- | --- | --- |
| 정상 (러너 0 · 143) | `일일 세션 종료 … — 정상` 한 줄 | 러너 rc |
| 러너 실패 (3 · 4 · 5 · 129/130 · 그 밖) | `일일 세션 실패 … rc=N` + 뜻 한 줄 | 러너 rc |
| 잠금 점유 (앞선 호출이 아직 돈다) | 실패 한 줄 — **단 `--catch-up` 은 조용한 SKIP** | 75 (catch-up 0) |
| 세션 디렉터리 이미 있음 · 부모 없음 · 호스트 zone ≠ +0900 | 실패 한 줄 | 2 |
| (STOCK) 운영 전송 설정 키가 정본과 다름 · 그 파일이 없음 | 실패 한 줄 + diff(키 이름) | 2 |
| (STOCK) 승인 파일을 읽을 수 없음 · 치우지 못함 | 실패 한 줄 — **옮기지 않았다**(추측하지 않는다) | 2 |
| (STOCK) 상시 승인 쓰기 실패 · `render ok` 가 20분 안에 오지 않음 | `상시 승인 쓰기 실패` / `상시 승인 못 씀` 한 줄 — 세션은 계속 돈다 | 러너 rc (승인 실패가 rc 를 바꾸지 않는다) |
| 개장 판정 자체가 실패(달력 못 읽음 · 날짜 오류 · `yaml` import 실패 등) | 실패 한 줄 — **SKIP 으로 읽지 않는다**(판정 모듈의 «휴장» 은 종료코드 10 하나뿐) | 2 |
| KIS 국내휴장일조회를 못 읽음(타임아웃 · `rt_cd≠0` · 자격증명 없음) | **없음** — cron 로그에 `calendar fallback` 한 줄, 달력에 없는 평일은 그대로 기동 | 0 |
| fetch · 워크트리 실패 | 실패 한 줄 | 1 |
| 휴장(달력) · 주말 · 연말 | **없음** — cron 로그 `market closed … (source=calendar …) — SKIP` 한 줄 | 0 |
| 달력에 없는 휴장(`opnd_yn=N`) | **안내 한 줄** (실패 아님) — 호스트 전체에 하루 한 번, `.notified` 로 중복 방지 | 0 |

그래서 **거래일 09:00 까지 방향마다 줄이 하나도 없으면** 그 자체가 소견이다 — cron 이 돌지
않았거나(`cron.log` 에 그날 줄 없음) 텔레그램 전송이 실패했다(`telegram notify FAILED` — HTTP 4xx·5xx 도 실패로 센다(`curl --fail`), 자격증명이 없으면 무엇이 없는지 그 줄에 적힌다). 정상
줄은 15:50(주식 15:40) 정지 뒤에 오므로, 낮 동안의 확인은 `cp3-sessions/<dir>-<날짜>/session.log` 를 본다.

**11-11(수) 롤 dry-run — 11-12 첫 실롤 전날.** mini 11월물(`A05611`) 만기는 11-12(목)이고
`get_front_month_code` 는 만기 **당일까지** 11월물을 준다 — 그래서 12월물 잎(`A05612`)의 첫
세션(= genesis)은 **11-13(금)** 이다. 11-11 장 마감 뒤 방향마다 읽기 전용 preflight 를 돌린다
(잠금·fetch·워크트리·텔레그램 없음, 쓰는 것 없음 — 먼저 `git -C $MAIN fetch -q origin`):

```bash
for d in 2026-11-12 2026-11-13; do for dir in LONG SHORT; do
  ~/.config/kis-probes/run-cp3-tenant-daily.sh $dir --preflight $d; done; done
```

기대: 11-12 는 `market=OPEN instrument=A05611 … present (continues)`, 11-13 은
`instrument=A05612 … absent (first session genesis)`, 넷 다 `session dir … free` 와 `worktree … free`.
다르면(예: 11-13 잎이 이미 있다 · `MISSING` 부모) 11-12 전에 운영자가 판단한다. cron 쪽에는 롤
손잡이가 없다 — 러너가 그날 월물을 한 번 계산해 잎·렌더·생산자에 같이 준다(§7.2-d 러너 6단계).
교차 시드(#900)가 실제로 접합했는지는 11-13 세션 뒤 `producer/market/stitch.json` 으로 본다(매
세션 쓰인다). 11-13 저녁에는
`cold-backup-cp3-{long,short}.log` 에 새 잎이 함께 올라갔는지 본다(§7.7 — 래퍼는 `A0####` 잎을 순회).

#### 7.2-f CP-3 주식 MOCK 세션 (M2) — 첫 세션 2026-10-26(월) · **매 거래일 무인 cron 08:53** (운영자 2026-11-05)

005930 · 1주 · Setup D LONG · 09:00–15:30 · **모의 계좌만**. 수용(rescope §3 M2) = 체결 1건 이상 + 사슬 연결.

**⚙ 매 거래일 자동 (운영자 결정 2026-11-05 — 「주식 트리 매일 cron 등록 진행해」).** 11-03 의
위임받은 1회 절차(`run-stock-mock-20261103.sh`)가 **매 거래일**로 확장됐다. cron 줄은 선물과 같은
래퍼의 세 번째 방향이고, 설치·제거·멱등성·텔레그램은 **§7.2-e** 가 정본이다.

| 무엇 | 값 |
| --- | --- |
| cron 줄 | `53 8 * * 1-5 /bin/bash ~/.config/kis-probes/run-cp3-tenant-daily.sh STOCK >> ~/.local/state/tos/cp3-stock-tenant-daily.cron.log 2>&1 # cp3-stock-tenant-daily` |
| 설치 | `tools/tos_cp3/runners/install_tenant_cron.sh`(dry-run → `--apply`) — LONG·SHORT 줄과 같은 블록, 멱등 |
| 세션 자리 | `$ST/cp3-sessions/stock-r1-<YYYYMMDD>` (cron 은 항상 `r1`) · 워크트리 `$ST/measure/wt-cp3-stock-r1-<YYYYMMDD>` |
| 정지 | 그날 `krx-stock` CONTINUOUS 종료 + 10분 = 평일 **15:40** (달력에서 날마다 읽는다 — 개장 지연일은 §7.2-g) |
| 자동 상시 승인 | `render ok` 뒤 래퍼가 그날짜 승인을 쓴다 — 아래 «상시 승인» 의 명령 그대로, rc 는 cron 로그 `write-standing-approval rc=N` · 출력은 `approval.out` |
| 어제 승인 파일 | 러너 전에 `$C/approvals-archive/standing-session.<그날짜>.yaml` 로 **옮긴다**(지우지 않는다 · 겹치면 `.1` · 덮어쓰지 않는다). 승인 경로가 고정이라 치우지 않으면 **둘째 날부터 송신 0** 이다 — 아래 «상시 승인» |
| 사전 점검 | 아래 «세션 전날 점검» 의 키 대조를 래퍼가 매 호출 한다 — 다르면 거부(송신 0)하고 알린다 |
| 끄기 (하루) | 그날 cron 줄을 주석 처리한다(`crontab -e`) |
| 끄기 (영구) | `install_tenant_cron.sh --remove --apply` 는 블록의 모든 tenant 를 뗀다. 한 줄만 떼려면 그 줄을 손으로 지운다 |
| 송신만 막기 | `$ST/cp3-setup-d-stock-custody/kis_mock.app_*` 를 지운다 — 부팅은 되고 첫 토큰 사용이 거부돼 송신 0 (아래 «되돌림») |

##### 종목당 tenant 하나 (운영자 지시 2026-11-19)

「유동성이 큰 대형주들로 최종 모의투자에서 매수/매도가 잘 동작하게 완료해」. 운영자 결정:
**종목당 열린 포지션 1개**(커널의 no-pyramiding 그대로) · **슬롯 3개 이상은 종목 3개 이상에서**
나온다 · 1주 고정 그대로. 그래서 위 절차가 **종목마다 한 벌**이다.

| 종목 | 래퍼 인자 | cron | 세션 자리 | custody · ops |
| --- | --- | --- | --- | --- |
| 005930 | `STOCK` (= `STOCK:005930`) | 08:53 | `stock-r1-<날짜>` | `cp3-setup-d-stock-{custody,ops}` |
| 000660 | `STOCK:000660` | 08:55 | `stock-000660-r1-<날짜>` | `cp3-setup-d-stock-000660-{custody,ops}` |
| 005380 | `STOCK:005380` | 08:57 | `stock-005380-r1-<날짜>` | `cp3-setup-d-stock-005380-{custody,ops}` |

- **왜 custody 를 나누는가.** 상시 승인 산출물 경로는 custody 루트 기준 **고정**이고 승인 문서는
  그 tenant 의 «렌더된» 설정에 묶인다. 공유하면 한 tenant 의 부팅이 다른 tenant 의 승인을
  바인드하고 그 뒤로는 `digest_changed_since_bound` 다 — 둘 다 송신 0.
- **1회 준비는 종목마다.** `setup_stock_mock_once.sh <종목>`(dry-run → `--apply`). 005930 만
  호스트 경로에 종목이 없다(2026-11-06 에 태어난 배포 그대로) — 스크립트가 그 예외를 안다.
- **공유되는 것은 계좌와 앱 키다.** 증인은 이미 종목으로 좁혀져 있어(주식일별주문체결조회를
  `PDNO=<자기 종목>` 으로 질의 · 잔고도 같은 종목으로 거른다) 다른 tenant 의 주문이 이
  tenant 의 읽기에 들어오지 않는다 — 그래서 `ORPHAN_BROKER_ORDER` 로 해제가 멎지 않는다.
  **종목이 겹치면 그 보장이 깨진다**: 한 종목에 두 tenant 를 두지 말 것.
- **요청률은 더해진다.** `KisAppKeyPacer` 는 프로세스마다 하나다 — 그래서 #1125 부터
  `shared_pacer_path` 가 앱 키 하나의 **합산** 대기열을 맡는다(`shared_max_rps: 2.0`,
  어떤 두 요청도 0.5 s 안에 붙지 않는다). 아래 수치는 그 게이트가 없을 때의 산술이다.
  그래서 세 트리의
  `fill_observer.yaml` 관찰 주기가 단일 tenant 값의 3 배다(그 파일 머리 «TENANT COUNT»).
  하드 상한은 1.5 req/s(3 × `min_send_interval_ms` 2000), 셋 다 미결을 쥔 구간이 ~1.33 req/s,
  보유만 하면 0.33 req/s 다 — 실측 조이기 지점 2.0 아래. 조여진 응답(HTTP 500 · EGW00201)은
  fail-closed — `WitnessUnavailable` 로 기록되고 다시 읽는다.
- **부팅은 서로 엇갈려야 한다.** cron 줄을 2분 벌린 것은 **생산자**의 REAL 키 토큰만 지킨다:
  생산자의 첫 행은 어느 분에 시작했든 **개장**에 오므로 세 세션이 09:01 근처에서 같이 렌더하고
  같이 부팅한다. KIS 는 앱 키당 분당 토큰 1장만 내주므로, 저마다 발급하면 둘째·셋째가
  `TokenResponseError` 뒤 쿨다운(`token_reissue_min_interval_s`)을 기다린다 — 2026-11-20 에
  005930 이 그렇게 하루를 잃었다(모든 시도 실패 → 브로커 사실 `None` → `SEND_REFUSED`).
  **고침은 토큰을 공유하는 것이다**: `token_cache_path` 가 가리키는 한 파일을 세 tenant 가
  `flock` 아래에서 함께 쓰고, 먼저 온 프로세스만 발급한다(#1125 · `tos-kis-mock-transport.md` §4).
  `TENANT_BOOT_DELAY_S` 는 그대로 둔다 — 캐시가 비어 있는 첫 부팅과 생산자 쪽 요청률을 아직 벌려 준다 —
  `cp3_tenant_daily.sh` 가 `STOCK_SYMBOLS` 안 **순번 × 70 s** 로 정한다(005930 은 0).
  손으로 시작할 때는 위 블록의 `SYM_BOOT_DELAY` 가 같은 자리다.
- **상태판.** `sts tos status` 는 세션 디렉터리를 글롭하므로 새 tenant 가 자동으로 나온다.
  깨끗한 날 누적(`config/tos_status_board.yaml::clean_streak.trees`)은 LONG 만 센다 — 바뀌지 않았다.

손으로 시작하는 것은 이제 **재기동용**이다(같은 날 두 번째 세션 = `RUN=2`, 아래 «08:55 시작» 블록).
cron 이 이미 `r1` 을 만들었으므로 래퍼를 다시 불러도 「세션 디렉터리 이미 있음」으로 거부된다.

✅ 2026-10-24 오프라인 드라이런이 찾은 막힘 다섯은 **모두 main 에 해소**됐다(main `957507b9` 로 리허설 — 부팅 수용 · 접속 0) —
B1 세션 안 승인 불가 → 세션 한정 상시 승인 #955 · B2 렌더본 `instance_path` · B3 OCP `wire_codec` → #956 · B4 활성 기록 빈 승인 id → #959 ·
B5 개장 때 권한 증인 소멸 → #957(패스마다 heartbeat + 주식 트리만 `containment_bound_ms: 90000`). 다시 보이면 아래 «볼 것» 질의가 잡는다.

**1회 준비(운영자).** `ST=~/.local/state/tos MAIN=/home/deploy/project/kis_unified_sts` · 정본은 `tools/tos_cp3/runners/setup_stock_mock_once.sh`
(시험 `tests/tools/test_setup_stock_mock_once.py` — 홑·겹 따옴표 둘 다 벗긴다 · 700/600 · 재실행은 덮어쓰기 거부). origin/main 판을 그대로 돌린다:
```bash
git -C $MAIN fetch -q origin; bash <(git -C $MAIN show origin/main:tools/tos_cp3/runners/setup_stock_mock_once.sh)          # 점검만 — 무엇을 만들지 보인다
bash <(git -C $MAIN show origin/main:tools/tos_cp3/runners/setup_stock_mock_once.sh) --apply  # data 부모 · ops · custody(+approvals) · manifest · transport
```
- `kis-mock-order-paper` = 트리 `MOCK_STOCK_ORDER.principal` 의 `{environment_label}` 치환값(custody 는 치환하지 않는다 — `tos-kis-mock-transport.md` §5).
- 스크립트가 쓰는 `$ST/cp3-setup-d-stock-ops/kis_mock_transport.yaml`(0600) = `tos-kis-mock-transport.md` §4 값 + `mode: live` · `endpoint_rest_base: "https://openapivts.koreainvestment.com:29443"`
  · `price_scale: 100` · `request_timeout_s: 10` · `min_send_interval_ms: 2000` · `app_key_request_wait_budget_ms: 4000` · `token_reissue_min_interval_s: 65` · `allow_plaintext_for_tests: false`
  · `token_cache_path: "$ST/kis-mock-token/stock-mock.json"` + `token_cache_refresh_margin_s: 600` · `shared_pacer_path: "$ST/kis-mock-token/stock-mock.pace"` + `shared_max_rps: 2.0`
    (#1125 — 앱 키를 공유하는 tenant 전부가 **같은** 네 값. 토큰 한 장과 요청 대기열 하나를 함께 쓴다. 스크립트가 그 디렉터리를 700 으로 만든다)
  · `ACNT_PRDT_CD` = **계좌 뒤 2자리**(다르면 코덱이 송신 거부). §4 표의 「`mode: live` 무조건 거부」는 옛 문장 — 지금은 compose 가 `codec_bound=True` 를 준다.
  · ⚠ **이 파일은 준비 때 한 번 쓰이고 그 뒤 갱신되지 않는다.** 준비 뒤 main 에 새 필수 키가 생기면 부팅이 `KisMockTransportConfigError: … missing entry '<키>'` 로 거부한다(송신 0).
    실제 사례 2026-10-30 첫 세션: 10-26 준비본에 #979(10-28)의 `app_key_request_wait_budget_ms` 가 없어 r1 부팅 거부. 고침은 그 키 한 줄을
    스크립트 정본(`setup_stock_mock_once.sh` 의 같은 줄)과 **같은 값**으로 운영 파일에 추가 — 덮어쓰기 재실행은 거부되므로 손으로 넣는다.
    세션 전날 점검: `diff <(grep -oE '^[a-z_A-Z]+:' $ST/cp3-setup-d-stock-ops/kis_mock_transport.yaml | sort) <(git -C $MAIN show origin/main:tools/tos_cp3/runners/setup_stock_mock_once.sh | sed -n '/^mode: live/,/^allow_plaintext/p' | grep -oE '^[a-z_A-Z]+:' | sort)` — 출력이 없어야 한다.
    **cron 래퍼가 매 호출 같은 대조를 한다**(§7.2-e «STOCK 만의 두 단계») — 다르면 그날 세션을 시작하지 않고 알린다. `run-cp3-tenant-daily.sh STOCK --preflight <날짜>` 로도 같은 줄을 읽기 전용으로 볼 수 있다.
- **상시 승인(그날 · #955)** — 파일 `$ST/cp3-setup-d-stock-custody/approvals/standing-session.yaml`(0600). **cron 세션에서는 래퍼가 쓴다**(`render ok` 뒤 · 첫 진입 전 · 운영자 결정 2026-11-05 이 11-03 의 위임 절차를 매 거래일로 확장). 손으로 쓰는 때(재기동 `RUN=2` 등)는 아래 «볼 것» 의 `render ok` 줄 뒤 · 첫 진입 전(런타임이 이미 떠 있어도 된다 — 첫 사용 때 결속).
  승인 없이는 신호가 와도 4단계에서 멎는다(송신 0). MOCK 트리가 아니면 rc 1 로 아무것도 쓰지 않는다 · 덮어쓰기는 `--replace` 뿐.
  **재작성**(예: `max_uses` 를 올림)은 운영자 권한이고 **재기동 뒤에** 적용된다 — 슬롯이 거래일로 키잉돼 이미 쓴 횟수는 그대로 센다.
  액션당 횟수는 트리의 `authority.yaml::standing_approval_max_uses_per_action` 이 정한다(주식 모의 트리 **390** = 정규장 1분봉 수 · 운영자 지시 2026-11-18 「하루 1회 승인은 모의계좌에서는 불필요해」).
  `--max-uses-per-action` 을 명시하면 그 값이 이기고, 키가 없는 트리(paper · LONG · SHORT)는 1 이다.
  ⚠ **경로가 고정이므로 슬롯은 하루에 하나다.** 작성기는 파일이 있으면 `--replace` 없이 거부하고(→ rc 1), 런타임의 `bind_at_boot()` 은
  **부팅 시점에 그 경로에 있던 것**을 결속해 그 뒤에 쓰인 파일을 `digest_changed_since_bound` 로 거부한다 — 즉 `--replace` 로도 못 고친다.
  그래서 cron 래퍼는 **러너를 띄우기 전에** 다른 날짜 파일을 `$C/approvals-archive/standing-session.<그날짜>.yaml` 로 옮긴다
  (지우지 않는다 · 이름이 겹치면 `.1` · 덮어쓰지 않는다 · `approvals/` 밖 — 그 디렉터리는 제안별 승인 파일 자리다). 이미 **오늘 날짜**면
  그대로 두고 쓰기를 건너뛴다. 손으로 재기동(`RUN=2`)할 때도 같다 — 어제 파일이 `approvals/` 에 남아 있으면 **그 세션은 송신 0** 이므로,
  cron 을 끈 날 손으로 돌릴 때는 먼저 그 파일을 같은 이름 규칙으로 `approvals-archive/` 로 옮긴다.
  **청산(10-26)**: 이 승인은 1주 진입 BUY 하나만 허락하고 청산은 승인되지 않는다(#960: CLOSE 명령이 BUY 로 만들어진다). 세션 뒤 모의 계좌에
  1주 롱이 남는다 — 평탄하게 하려면 모의투자 HTS 에서 손으로 판다. ⛔ 청산을 제안별 승인 파일로 **절대** 승인하지 않는다(두 번째 1주를 **산다**).
- **genesis** = 빈 잎 `$ST/cp3-setup-d-stock-005930-data/005930` 에 대한 첫 `run`(러너가 잎을 만든다 · 되돌릴 수 없다 · 승인 행위는 없다). 다음 날부터는 같은 잎을 잇는다.

##### 7.2-f-1 결정 계약을 바꾼 날 — 새 잎을 열기 전날 (장 마감 뒤)

`config/tos_runtime/decision_generations.yaml` 의 그 tenant `generation` 이 올라간 PR 을
머지했으면, **다음 부팅 전에** 이 절을 돌린다. 안 돌리면 그 잎은 못 올라온다 —
부팅이 inbox 의 지난 이벤트를 **오늘의** 전략으로 다시 도출해 기록과 대조하고
(`tos_runtime/compose/_boot_integrity.py::verify_engine_replay_or_halt`), 규칙이 바뀐 날은
전부 어긋나 `EngineReplayDiverged` 로 거부되며 그 거부가 영구 `REPLAY_DIVERGED` 행을 쓴다
(복구 장벽은 그 수가 0 이어야 한다 — 2026-11-12 `stock-r1-20261112`, 1075/1075).

⚠ **래퍼는 잎을 치워 주지 않는다.** `cp3_tenant_daily.sh` 는 잎이 있으면
`PREFLIGHT leaf … present (continues)` 를 적고 그 잎을 **잇는다**(같은 파일 680-683행;
`decision_generations.yaml` 를 읽지도 않는다 — 그 파일은 CI 의 핀이다). generation 을
올리는 것은 **누군가 이 절을 돌려야 한다고 소리 내어 말하는 행위**일 뿐이고, 잎을 옮기는
것이 실제 일이다.

**① 그 종목이 모의 계좌에서 비었는지 본다 (GET 전용 · 아무것도 보내지 않는다).**
새 잎의 증거는 비어 있어서, 전날 주식이 남아 있어도 `side` 는 FLAT 으로 읽힌다 — 진입
규칙이 발화하고 **남은 주식의 손절은 영영 발화하지 않는다**(계획 §3 · §11 결정 4).

```bash
cd $MAIN && PYTHONPATH=$MAIN CP3_EXPECT_ACCOUNT_FP=<모의 주식 계좌 지문 12hex> \
  TOS_ENV_MOCK=$MAIN/.env.mock \
  .venv/bin/python -m tools.tos_cp3.ops.mock_flat_check <종목> \
  --transport-yaml $ST/cp3-setup-d-stock-<종목>-ops/kis_mock_transport.yaml; echo "rc=$?"
# rc 0 = `<종목> flat (no holding, no order working)` — 보유도 미체결 주문도 없다. 진행.
# rc 3 = 보유가 있거나 그 종목에 미체결 주문이 걸려 있다(출력이 `holdings {...}` 또는
#        `<종목> open orders [...]` 로 어느 쪽인지 말한다) → ②
# rc 1 = 잔고/주문 조회를 못 읽었다(토큰·전송) → 다시. 추측으로 진행하지 않는다.
# rc 2 = 사전조건 거부(계좌 지문 없음 · .env.mock 없음) — 계좌를 추정하지 않는다.
# 지문은 §7.2-f 의 「계좌 지문은 필수다」 블록으로 한 번 구해 둔다(비밀값 아님).
```

**② 남아 있으면 모의 주문으로 정리한다 (MOCK 전용 · 시장가 전량 매도).**

```bash
cd $MAIN && PYTHONPATH=$MAIN CP3_EXPECT_ACCOUNT_FP=<같은 지문> \
  TOS_ENV_MOCK=$MAIN/.env.mock \
  .venv/bin/python -m tools.tos_cp3.ops.mock_flatten <종목> \
  --transport-yaml $ST/cp3-setup-d-stock-<종목>-ops/kis_mock_transport.yaml; echo "rc=$?"
# rc 0 = `<종목> flat` — 매도가 체결되고 잔고가 0 이 됐다(또는 애초에 0 이었다).
# rc 1 = 브로커가 그 매도를 거부했다(`sell http … rt_cd …`) — 사유를 보고 다시.
# rc 3 = 보냈지만 10×3 s 안에 0 이 되지 않았다 — 체결을 기다렸다가 ① 로 재확인한다.
# rc 2 = 사전조건 거부. 보낸 것은 없다.
# ⛔ 이 도구는 **모의 계좌 전용**이고 계좌 지문이 맞지 않으면 아무것도 보내지 않는다.
```

**③ 잎을 보관한다.** 지우지 않는다 — append-only 증거다.

```bash
LEAF=$ST/cp3-setup-d-stock-<종목>-data/<종목>
mkdir -p $(dirname $LEAF)/archive && mv -n $LEAF $(dirname $LEAF)/archive/<종목>.gen<이전>.$(TZ=Asia/Seoul date +%Y%m%d)
```

**④ 다음 아침 preflight 가 `absent (first session genesis)` 라고 말하는지 본다**(§7.2-f 의
`--preflight`). `present (continues)` 면 ③ 이 안 된 것이고, 그 세션은 거부된다.

**손으로 시작 — 재기동(`RUN=2`), 또는 cron 줄을 끈 날.** 창 08:52–09:05: 첫 행은 09:01:0x 에 오고 첫 행 대기 상한이 600 s. cron 의 `r1` 이 08:53/08:55/08:57 에 이 블록과 같은 일을 한다. LONG 08:38·SHORT 08:40 는 **선물** REAL 키, 주식 세션은 **주식** REAL 키(생산자·band)와 모의 키(런타임) — 지문이 서로 달라 선물과는 분당 1회 토큰 발급이 겹치지 않는다. 주식끼리는 겹치므로 `SYM_BOOT_DELAY` 를 둔다(아래).

블록은 **종목 인자 하나**로 움직인다. 맨 앞 세 줄만 고치면 어느 주식 tenant 든 시작한다 —
`SYM` 은 `STOCK_SYMBOLS` 안의 종목, `SYM_SUFFIX` 는 005930 만 빈 문자열(그 배포의 호스트
경로에는 종목이 없다), `SYM_BOOT_DELAY` 는 지금 다른 주식 tenant 가 같이 부팅 중일 때만 ≥70.

```bash
SYM=005930; case $SYM in 005930) SYM_SUFFIX= ;; *) SYM_SUFFIX=-$SYM ;; esac; SYM_BOOT_DELAY=${SYM_BOOT_DELAY:-0}
D=$(TZ=Asia/Seoul date +%Y%m%d) RUN=${RUN:-1}; LC=stock$SYM_SUFFIX; WT=$ST/measure/wt-cp3-$LC-r$RUN-$D   # 같은 날 재기동은 RUN=2 로 이 블록을 다시
git -C $MAIN fetch -q origin && git -C $MAIN worktree add -q --detach $WT origin/main && export TOS_REPO=$WT TOS_PYTHON=$MAIN/.venv/bin/python \
  TOS_STOCK_SYMBOL=$SYM TOS_STOCK_BOOT_DELAY_S=$SYM_BOOT_DELAY \
  TOS_STOCK_SESSION_ROOT=$ST/cp3-sessions/$LC-r$RUN-$D TOS_STOCK_DATA_PARENT=$ST/cp3-setup-d-stock-$SYM-data TOS_STOCK_ENV_MOCK=$MAIN/.env.mock \
  TOS_STOCK_CUSTODY_ROOT=$ST/cp3-setup-d-stock$SYM_SUFFIX-custody TOS_STOCK_KIS_MOCK_TRANSPORT_CONFIG=$ST/cp3-setup-d-stock$SYM_SUFFIX-ops/kis_mock_transport.yaml TOS_STOCK_STOP_AT=15:40 \
  && mkdir -m 700 $TOS_STOCK_SESSION_ROOT && cd $WT && set -a && . tools/tos_cp3/runners/stock-mock-session.env.example && set +a \
  && { nohup bash tools/tos_cp3/runners/run_tenant_session.sh >$TOS_STOCK_SESSION_ROOT/runner.out 2>&1 & echo $! >$TOS_STOCK_SESSION_ROOT/runner.pid; }   # 한 고리가 실패하면 아무것도 뜨지 않는다
```

> 더 간단한 길: `bash $MAIN/tools/tos_cp3/runners/cp3_tenant_daily.sh STOCK:<종목>` 이 위를 전부
> 한다(워크트리 · 승인 · 전송 키 대조 · 텔레그램 포함). 다만 **그날 세션 디렉터리가 이미 있으면
> 거부한다** — 같은 날 두 번째 세션(`RUN=2`)은 그래서 위 블록이다.
```bash
cd $WT && PYTHONPATH=tos/runtime/src:tos/src $MAIN/.venv/bin/python -c "import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))" \
  write-standing-approval --config-dir "$TOS_STOCK_SESSION_ROOT/render" --custody-root "$TOS_STOCK_CUSTODY_ROOT" --environment-label paper --trading-date $(TZ=Asia/Seoul date +%F)
# ⚠ `python -m tos_runtime.compose.cli …` 는 아무것도 하지 않고 rc 0 으로 끝난다(cli.py 에 __main__ 없음) — 위 `-c` 꼴만 쓴다. 실제 출력(리허설 10-24):
#   write-standing-approval: wrote …/approvals/standing-session.yaml (artifact_digest=…, trading_date=20261026, actions=OPEN-LONG-BUY,CLOSE-SHORT-SELL)
#   write-standing-approval: exit row cannot match until #960 (CLOSE commands are built as BUY)
```
**볼 것.** `session.log`: `credential separation ok` → `transport=kis-mock` → `first real row seen`(≈09:01 — `quote_initial_cursor: "153000"`(#922 미실측)이 장중 봉을 준다는 첫 증거. 600 s 안에 없으면 러너가 ABORT 하고 그날은 실측 결과로 남긴다) → `band line ok`(없으면 `BAND ABSENT` = 송신 0) → `=== BOOT`. `sts tos status` 는 `cp3-sessions/stock-<날짜>` 를 읽는다.
```bash
L=$ST/cp3-setup-d-stock-005930-data/005930; sqlite3 -readonly $L/evidence.sqlite3 "SELECT kind,COUNT(*) FROM entries WHERE kind IN ('BROKER_FACTS_OBSERVED','APPROVAL_STANDING_BOUND','APPROVAL_STANDING_CONSUMED','APPROVAL_STANDING_NOT_COVERED','APPROVAL_STANDING_REFUSED','SEND_SEALED','TRANSPORT_SEND','TRANSPORT_DRY_RUN','AUTHORITY_WITNESS_LOST','EGRESS_RESULT_CONSUMED','FILL_OBSERVED','POSTTRADE_FINALITY_PROOF','ENGINE_PROJECTION_RELEASED','MARKETFEED_PASS_OVERRUN') OR kind LIKE 'FILL_OBSERVER_%' GROUP BY 1"
sqlite3 -readonly $L/evidence.sqlite3 "SELECT json_extract(payload_json,'\$.payload.step'),COUNT(*) FROM entries WHERE kind='FLOW_HALTED' GROUP BY 1"   # 어디서 멎나 — INDEPENDENT_APPROVAL 이면 승인 없음
sqlite3 -readonly $L/evidence.sqlite3 "SELECT json_extract(payload_json,'\$.payload.reason'),COUNT(*) FROM entries WHERE kind='APPROVAL_STANDING_NOT_COVERED' GROUP BY 1"   # 승인 범위 밖인 이유
sqlite3 -readonly $L/evidence.sqlite3 "SELECT kind,json_extract(payload_json,'\$.payload.halt_reason'),COUNT(*) FROM entries WHERE kind IN ('EVENT_CONSUMED','COORDINATOR_MESH_HELD','SEND_REFUSED') GROUP BY 1,2"   # B4: LIVE_SCOPE_NOT_AUTHORIZED · mesh activation_atomic(FLOW_HALTED 없음) · B5: SEND_REFUSED
```
**정지 · 킬스위치.** 새 셸이면 먼저 `ST=~/.local/state/tos D=<YYYYMMDD> RUN=<n> SYM=<종목>; case $SYM in 005930) LC=stock ;; *) LC=stock-$SYM ;; esac; TOS_STOCK_SESSION_ROOT=$ST/cp3-sessions/$LC-r$RUN-$D`. 정상: `TENANT_STOP_AT` 에 러너가 스스로 멎는다(rc 0/143). 손 정지 = `kill -TERM $(cat $TOS_STOCK_SESSION_ROOT/runner.pid)`(러너가 런타임 → 생산자 순으로 멈춘다).
러너가 죽었는데 런타임이 남았으면 `pkill -TERM -f "$LC-r$RUN-$D/render"`. `AUTHORITY_WITNESS_LOST` 는 그 프로세스에서 영구다 — 회복은 재기동(시작 블록을 `RUN=2` 로)뿐. ⛔ **이미 나간 모의 주문의 취소는 런타임에 없다(#948) — KIS 모의투자 HTS 에서 손으로.**

##### 장중 모의 tenant 재시작 (운영자 상시 승인 2026-11-20)

**언제.** 그날 한 tenant 가 못 쓰게 됐을 때 — 토큰 발급 실패로 `SEND_REFUSED` 가 계속되거나,
부팅이 `EngineReplayDiverged` 로 거부되거나, 머지된 고침을 그날 안에 태워야 할 때. 모의 tenant 는
장중에 묻지 않고 고친다(커널 코드 변경만 15:40 뒤). 선물·상주 세션에는 쓰지 않는다.

```bash
MAIN=/home/deploy/project/kis_unified_sts
# 계좌 지문은 필수다. 한 번 구해 두고 재사용한다 (계좌번호의 sha256 앞 12자 · 비밀값 아님):
# PYTHONPATH=$MAIN 이 필요하다 — `python -c` 는 **그때의 cwd** 를 sys.path 에 넣으므로, 저장소
# 밖에서 돌리면 `tools.broker_probes` import 가 ModuleNotFoundError 로 죽는다(cd $MAIN 도 같다).
export CP3_EXPECT_ACCOUNT_FP=$(set -a; . $MAIN/.env.mock; set +a; PYTHONPATH=$MAIN $MAIN/.venv/bin/python -c \
  "import os;from tools.broker_probes.common import account_fingerprint;print(account_fingerprint(os.environ['KIS_STOCK_ACCOUNT_NO']))")
bash $MAIN/tools/tos_cp3/ops/restart_stock_tenant.sh <종목> [태그]   # 정지 → 평탄 확인 → 잎 보관 → origin/main 새 run
```

- **잎은 평탄할 때만 보관한다.** 스크립트는 보관 전에 `tools/tos_cp3/ops/mock_flat_check.py`
  (GET 전용)로 **둘 다** 읽는다 — 그 종목 보유(주식잔고조회 `VTTC8434R`)와 **그날 아직 책에
  남아 있는 주문**(주식일별주문체결조회 `VTTC0081R` · `CCLD_DVSN=00` 전체). 둘 다 **끝까지 걷고**,
  끝은 **`tr_cont` 응답 헤더**가 정한다(`M`·`F` 면 더 있다) — 모의는 마지막 페이지에도
  `ctx_area_*` 커서를 실어 보내므로(P-BAL 2026-08-05: `tr_cont='D'` + 커서 채움) 커서만 보면
  끝을 알 수 없다. 헤더가 아예 없으면 「끝」이 아니라 **모름**으로 친다. 주문 행은 잔량을
  읽을 수 있을 때만 「닫힘」이다 — `rmn_qty` 가 비었거나 없거나 숫자가 아니면 **열린 것으로
  센다**(`ord_qty - tot_ccld_qty` 가 읽히면 그것으로 센다 · 런타임 `_fill_state` 와 같은 규칙).
  하나라도 있거나 어느 쪽이든 못 읽으면 **rc 2 로 멈추고 잎을 그대로 둔다**. 보유가 아니라 **미체결 주문**도 막는 이유: ACK 만 받고 체결되지 않은 지정가
  진입이 있으면 보유는 0 이라 옛 검사는 「평탄」이라 답했고, 잎을 보관한 뒤 그 주문이 체결되면
  그 포지션은 어느 증거 사슬의 것도 아니게 된다. 청산은 런타임이 못 하고(승인은 1주 진입 BUY 만 ·
  #960) 취소는 아예 없다(#948) — 보유는 `mock_flatten.py <종목>`(모의 전용 시장가 전량 매도)로,
  미체결 주문은 **모의투자 HTS 에서 손으로** 치운 뒤 다시 돌린다.
- **승인은 시작 «전에» 치우고 `render ok` «뒤에» 쓴다.** 런타임은 부팅 시점에 그 경로에 있던
  승인을 결속하므로(`bind_at_boot`), 나중에 쓴 파일은 `digest_changed_since_bound` 로 거부되고
  그 세션은 송신 0 이다 — 그래서 스크립트는 러너를 띄우기 전에 옛 파일을 `approvals-archive/`
  로 옮긴다. 그리고 승인은 **렌더된 설정의 코드 digest** 에 묶이므로 머지 뒤의 어제·오늘 승인은
  `code_digest_mismatch` 다 — 그래서 재시작마다 `render ok` 를 기다려 다시 쓴다(rc 는
  `$SESSION/approval.out`). 둘 중 하나를 건너뛰면 세션은 떠 있는데 송신이 0 이다.
- **정지 시각은 그 트리의 달력에서 읽는다**(`session_day stop-at` · 개장 지연일 #924 포함).
  강제하려면 `CP3_DAILY_STOP_AT=HH:MM`. 경로 손잡이는 러너와 같은 이름이다
  (`CP3_DAILY_MAIN` · `CP3_DAILY_STATE` · `TOS_ENV_MOCK`).
- **평탄 확인은 공용 앱 키로 토큰을 한 장 발급한다.** 그 시점에 이 tenant 는 이미 멈춰 있지만
  다른 주식 tenant 는 돌고 있으니, 분당 1회 한도에 걸려 새 세션의 첫 발급이 쿨다운
  (`token_reissue_min_interval_s`)만큼 늦어질 수 있다 — 캐시 토큰이 유효하면 그대로 쓴다(#1125).
- rc: 0 시작됨 · 1 실패(정지 안 됨 · fetch · 워크트리 · 승인 쓰기) · 2 거부(지문·종목·평탄 아님) ·
  4 `render ok` 전에 끝났다(승인 없음 = 송신 0). **rc 4 와 승인 쓰기 실패는 손으로 쓸
  `write-standing-approval` 한 줄을 그대로 찍는다** — 그 줄만 돌리면 그 세션은 살아난다(쓰다 만
  파일이 있으면 `--replace`). 시험 `tests/tools/test_cp3_ops_restart.py` ·
  `tests/tools/test_cp3_ops_mock_tools.py`.
- **정지는 pid 신원을 확인하고 보낸다.** `runner.pid` 의 번호를 다른 프로세스가 재사용하고 있을 수
  있으므로 `/proc/<pid>/cmdline` 부터 본다. 러너가 **아니면** 남의 pid 로 보고 죽이지 않고
  건너뛴다. 러너가 **맞는데** `environ` 의 `TOS_STOCK_SESSION_ROOT`(realpath 비교)가 그 자리가
  아니면 **rc 2 로 거부한다** — 그건 남의 프로세스가 아니라 이 tenant 의 러너가 내 가정과 다른
  자리에서 살아 있다는 뜻이고, 그대로 진행하면 돌고 있는 세션 옆에서 잎을 보관하게 된다. 기다리는
  상한은 러너의 정지 상수 합(`SIGKILL_AFTER_S` + 생산자·밴드·대기자 유예 = 140s)을
  `run_tenant_session.sh` 에서 **읽어서** 쓴다 — 여기에 숫자를 또 적지 않는다.

**장 마감 뒤 수용.** 같은 attempt 하나에 아래가 모두 있으면 M2 수용 — 승인(`APPROVAL_STANDING_CONSUMED` 의 `rcl_command_id` = RCL `ConsumeApprovalDecision` `iap-consumption:standing-approval:<YYYYMMDD>:…`) · `CommitReservation` · VERIFY_ITEM 17 · `SEND_SEALED`/`TRANSPORT_SEND` · `ACK` · `FILL_OBSERVED` + `FULL_FILL|PARTIAL_FILL` · `POSTTRADE_FINALITY_PROOF`(`broker-fqp-proof:<attempt>`) · RCL `release-<attempt>` · `ENGINE_PROJECTION_RELEASED`. 질의는 종류·개수·id 접두만 찍는다(예약 id·payload 에는 계좌가 있다 — 옮겨 적지 않는다).
```bash
sqlite3 -readonly $L/evidence.sqlite3 "SELECT COALESCE(json_extract(payload_json,'\$.payload.attempt_id'),replace(json_extract(payload_json,'\$.payload.idempotency_key'),'broker-fqp-proof:','')) a,kind,COUNT(*),group_concat(DISTINCT json_extract(payload_json,'\$.payload.egress_result_kind')) FROM entries WHERE kind IN ('VERIFY_ITEM','SEND_SEALED','TRANSPORT_SEND','EGRESS_RESULT_CONSUMED','FILL_OBSERVED','POSTTRADE_FINALITY_PROOF','ENGINE_PROJECTION_RELEASED') GROUP BY a,kind ORDER BY a,MIN(seq)"
sqlite3 -readonly $L/evidence.sqlite3 "SELECT json_extract(payload_json,'\$.payload.action'),json_extract(payload_json,'\$.payload.rcl_command_id') FROM entries WHERE kind='APPROVAL_STANDING_CONSUMED'"
sqlite3 -readonly $L/rcl.sqlite3 "SELECT seq,kind,substr(command_id,1,64) FROM entries WHERE kind IN ('ConsumeApprovalDecision','CommitReservation','ReleaseReservation') ORDER BY seq"
```
- **신호가 없으면**(`SEND_SEALED` 0 · `FLOW_HALTED` 가 `INDEPENDENT_APPROVAL` 이전에서만 · `COORDINATOR_MESH_HELD` 0) 코드 실패가 아니다 — 수용은 다음 거래일로 넘어간다(새 세션 디렉터리 · 같은 잎).
- **⛔ 세션일에는 같은 모의 계좌·005930 으로 취소 프로브(P-SC, `kis-capability-probes.md` §5.10)를 돌리지 않는다.** 그날 그 종목에 FILLED 가 아닌 주문이 한 건이라도 있으면 보유 증명(`_quantity_for_snapshot`)이 None 이 되어 그날 CLOSE 가 모두 UNKNOWN 이다(fail-closed · 송신 0 · 포지션은 다음 날로 넘어간다 — review-1007 L4, #1012).
  **2026-11-05 cron 등록 뒤에는 모든 거래일이 세션일이다.** 그래서 005930 으로 P-SC 를 돌리려면 **그날 `# cp3-stock-tenant-daily` cron 줄을 먼저 주석 처리**하고(그리고 그날 세션이 이미 떠 있지 않은지 `cp3-sessions/stock-r1-<날짜>` 로 확인하고) 돌린 뒤 되살린다. 주말·휴장일은 애초에 세션이 없으므로 그냥 돌려도 된다.
- **되돌림.** cron 줄을 떼면(§7.2-f 머리의 «끄기») 다음 거래일부터 세션이 없다 — LONG·SHORT·상주는 이 트리와 경로·키·잎을 공유하지 않는다. 송신만 막으려면 `$ST/cp3-setup-d-stock-custody/kis_mock.app_*` 를 지운다 — 부팅은 되지만 첫 토큰 사용(브로커 사실 GET·송신)이 거부돼 송신 0 (cron 줄은 그대로여도 된다). 잎은 append-only 증거라 지우지 않는다.

#### 7.2-g 개장 지연일(날짜별 세션 예외) — 수능일 등 (#924)

KRX 가 어떤 날의 개장·종료를 옮기면(수능일: 주식·지수선물 각각 지연, 시장마다 다르게) 그
날짜를 **캘린더 한 곳**에 적는다 — 각 tenant 트리의 `calendar.yaml` 의 `session_overrides`
(형식은 파일 안 주석). 이 한 항목을 런타임 세션 게이트(`tos_runtime.calendar`)·생산자 첫
봉/종료 커서·주식 첫 페이지 커서(`quote_initial_cursor: session_end`)·러너 첫 줄 대기
(지연분만큼 늘어남)·밴드 기동 시각·cron 래퍼 정지 시각
(`그날 종료 + CP3_DAILY_STOP_AFTER_CLOSE_MIN`)·**cron 래퍼의 (STOCK) 상시 승인 `render ok`
대기**(기본 1200s + 그날 개장 지연 — `render ok` 는 개장을 따라오므로, 고정 대기는 지연일에
먼저 만료되고 그날 송신이 0 이 된다)가 모두 읽는다. 다른 곳에 시각을 다시 적지 않는다.

**항목을 더하거나 고칠 때 (순서가 전부다).**

1. **출처는 KRX 공지값이다 — 선례값이 아니다.** 공지의 세부 시각이 첨부파일이라 안정
   permalink 가 없으면, 같은 날 보도 두 건을 함께 적어 둔다.
2. `calendar_version` 을 올린다(예: `krx-2026.11` → `krx-2026.11.1`). 네 트리의
   `time.yaml::trading_calendar_version` 도 **같은 커밋**에 — 불일치는
   `SessionCalendarMismatch` 부팅 거부다.
3. 해당 tenant 트리의 `calendar.yaml` 바이트 동일 규율을 유지한다(`md5sum`).
4. **그날 가장 이른 cron(LONG 08:38) 전까지 `origin/main` 에 머지돼 있어야 한다.** 래퍼들은
   매 세션 `origin/main` 에서 새 워크트리를 떠서 부팅하므로 재시작은 필요 없다 — 그 시각에
   `origin/main` 에 있기만 하면 된다. 넘기면 그날 그 세션은 정규 시각으로 이미 떠 있다.
5. ⚠ **래퍼(`tools/tos_cp3/runners/cp3_tenant_daily.sh`)를 바꾼 PR 이라면 머지 뒤
   `bash tools/tos_cp3/runners/install_tenant_cron.sh --apply` 를 한 번 돌린다.** 설치본
   `~/.config/kis-probes/run-cp3-tenant-daily.sh` 는 **복사본**이고 `origin/main` 에서
   복사된다(작업 트리에서 복사하지 않는다). 재설치하지 않으면 그날 STOCK 세션이 옛 대기를
   돌려 승인을 못 쓰고 송신이 0 이 된다.

**머지 뒤, 그날 전 dry-run (읽기 전용, 운영자):**

```bash
git -C $MAIN fetch -q origin
for dir in LONG SHORT STOCK; do ~/.config/kis-probes/run-cp3-tenant-daily.sh $dir --preflight <YYYY-MM-DD>; done
# 지연일 기대: "PREFLIGHT session krx-index-futures CONTINUOUS <날짜> 09:45-16:45 OVERRIDE · stop_at=16:50"
#   평일은   "08:45-15:45 regular · stop_at=15:50"
#   STOCK 지연일은 "krx-stock CONTINUOUS <날짜> 10:00-16:30 OVERRIDE · stop_at=16:40"
#   평일은   "09:00-15:30 regular · stop_at=15:40"
# 손으로 시작하는 주식 세션(재기동)의 정지 시각은 같은 리더로 구한다 — TOS_STOCK_STOP_AT 에 그대로 넣는다
# (--after-close-min 10 = cron 래퍼의 STOCK 기본값):
.venv/bin/python -P -m tools.tos_cp3.session_day stop-at \
  --producer-config config/tos_probes/cp3-live-producer-stock-005930.yaml \
  --repo-root . --date <YYYY-MM-DD> --after-close-min 10
```

정지 시각은 코드에 박혀 있지 않다 — 래퍼는 `session_day stop-at` 으로 그날 캘린더에서
도출한다(`cp3_tenant_daily.sh` 의 `STOP_AT=${CP3_DAILY_STOP_AT:-}` 가 비어 있고 뒤에서
채워진다). 테넌트별 기본 여유분만 상수다(LONG/SHORT 5 분 · STOCK 10 분). 재설치 뒤 같은지
한 줄로 확인한다:

```bash
sha256sum ~/.config/kis-probes/run-cp3-tenant-daily.sh \
  <(git -C $MAIN show origin/main:tools/tos_cp3/runners/cp3_tenant_daily.sh)
# 두 줄의 해시가 같아야 한다. 다르면 `tools/tos_cp3/runners/install_tenant_cron.sh --apply`
```

⛔ **상주 paper 세션은 지연일의 마지막 시간을 받지 못한다 (알려진 손실).** 상주 래퍼
`~/.config/kis-probes/tos-paper-session.sh` 는 **이 저장소 밖**이고 정지 시각이 캘린더가
아니라 래퍼 상수와 crontab 에 박혀 있다 — `STOP_HHMM=${TOS_PAPER_STOP_HHMM:-15:45}` 와
crontab 의 `45 15 * * 1-5 … stop`. **다만 세션 게이트는 override 를 읽으므로** 그날 개장도,
정지까지의 창도 올바르다 — override 가 아예 없을 때보다 나쁘지 않다(없으면 정규 개장으로
잡아 첫 줄 대기부터 실패한다). 상주는 synthetic 이라 이 손실을 그냥 받아들이는 것이 기본이고,
하루만 늘리려면 **두 줄을 다 손봐야 한다**(start 가 `STOP_HHMM` 으로 안전 데드라인을 잡고,
stop cron 이 그와 별개로 끝낸다 — 한쪽만 바꾸면 효과가 없다):

```bash
# 전날까지 crontab 두 줄을 그날용으로 바꾸고, 다음 날 아침에 되돌린다.
#   45 8  * * 1-5 … TOS_PAPER_STOP_HHMM=16:45 /bin/bash …/tos-paper-session.sh start …
#   45 16 * * 1-5 … /bin/bash …/tos-paper-session.sh stop …
# 되돌리는 것을 잊으면 그 뒤로 매일 한 시간씩 길어진다 — 그냥 받아들이는 쪽이 기본인 이유다.
```

주식 수동 세션(`TOS_STOCK_STOP_AT`)은 위 dry-run 이 찍는 값을 그대로 넣는다 — 이쪽은 상주
래퍼와 무관하게 캘린더에서 읽은 값이다.

#### 7.2-h synthetic venue 원장 (#1011) — 켜기 · 볼 것 · 되돌림

계획 `docs/plans/2026-10-31-tos-synthetic-venue-ledger-plan.md`(운영자 승인 10-31) · 코드 #1017·#1018. **켜짐** — synthetic 트리 셋(paper · cp3-setup-d-long/short)에 #1053 으로 켰다(**11-13 이후 첫 거래일**, 운영자 결정 10-31). 그 전 기본은 OFF 였고, 주식 트리는 계속 키가 없다.
- **왜**: 키가 없으면 synthetic 트리(paper · cp3-setup-d-long/short)의 증인이 증거 저장소를 다시 읽어(`WITNESS_NOT_INDEPENDENT`) 체결이 `POSITION_CONSUMED` 에 가지 못하고, **첫 진입 뒤 scope 가 월물까지 봉인**된다(CLOSE·OPEN 모두 DENY).
- **켜기**: 트리의 `config/tos_runtime/<tree>/finality.yaml` 에 `witness: synthetic_venue_ledger` 한 줄(synthetic 트리 셋만). 아침 러너가 origin/main 새 워크트리로 부팅하므로 **머지한 다음 세션부터 적용**된다. digest 재도출은 필요 없다 — `release.yaml::expected_code_digest` 는 `tos/src`·`tos/runtime/src` 의 `*.py` 만 접고, 부팅 무결성 해시도 `finality.yaml` 을 담지 않는다(#1053 에서 `tos_redigest.py --check` 무변경 확인). 주식 트리(kis-mock)에 넣으면 부팅이 거부된다(의도된 동작).
- **파일**: 잎 안 `venue_ledger.sqlite3`(0600 · append-only). `evidence.sqlite3`·`rcl.sqlite3` 와 다른 파일이다. 콜드 백업은 이 파일을 **선택 멤버**로 담는다(코드 `operations/backup_set.py`). 옛 manifest 는 이 파일 없이 복원된다.
- **볼 것**(켠 뒤 첫 체결): `sqlite3 -readonly $L/venue_ledger.sqlite3 "SELECT result_kind,COUNT(*) FROM venue_results GROUP BY 1"`(행은 체결 결과당 하나 · 같은 `broker_execution_id` 재송신은 행을 늘리지 않는다). 진입 체결 뒤 RCL 에 `POSITION_CONSUMED` 가 있어야 하고, 청산 체결 뒤 두 예약이 모두 `RELEASED` 여야 한다. HOLD 사유가 `WITNESS_NOT_INDEPENDENT` 이면 키가 안 먹은 것(옛 증인)이고, `NOT_CORROBORATED` 이면 진짜 불일치(orphan 또는 수량 충돌)다 — 손으로 풀지 말고 보고한다.
- **되돌림**: 키 줄을 지우는 PR. 배포 가드 `test_venue_ledger_wiring.py::_SHIPPED_TREE_WITNESS` 와 `test_deploy_approved_values.py` 의 고정값도 같이 고친다. 다음 부팅부터 옛 증인으로 돌아가 다시 봉인 쪽(fail-closed)이 된다. 원장 파일은 지우지 않는다(증거다).
- **세션일 금지**: 같은 잎에서 키를 켠 채 원장 파일을 지우거나 옮기지 않는다 — 원장 없는 체결 증거는 증인 부재로 HOLD 된다(fail-closed지만 그 scope 는 다시 봉인된다).

### 7.4 상주 paper cron (설치됨)

설치된 줄은 이것이다(`crontab -l`, 2026-11-20 실측):

```cron
# TOS paper 상주 세션 (운영자 결정 2026-10-03 · 첫 세션 2026-10-06 · 런북 tos-paper-boot.md §7.4; 크론 끝에 둔다 — CRON_TZ 는 아래 줄에만 적용)
CRON_TZ=Asia/Seoul
45 8  * * 1-5 /bin/bash /home/deploy/.config/kis-probes/tos-paper-session.sh start >> /home/deploy/.local/state/tos/paper-logs/cron.log 2>&1 # tos-paper-session
45 15 * * 1-5 /bin/bash /home/deploy/.config/kis-probes/tos-paper-session.sh stop  >> /home/deploy/.local/state/tos/paper-logs/cron.log 2>&1 # tos-paper-session
@reboot sleep 150; [ "$(date +\%u)" -le 5 ] && [ "$(date +\%H\%M)" -ge 0845 ] && [ "$(date +\%H\%M)" -lt 1545 ] && ! ls -d /home/deploy/.local/state/tos/paper-sessions/$(date +\%F)-* >/dev/null 2>&1 && /bin/bash /home/deploy/.config/kis-probes/tos-paper-session.sh start >> /home/deploy/.local/state/tos/paper-logs/cron.log 2>&1 # tos-paper-session-catchup
```

- `@reboot` 줄은 **장중 재부팅 복구**다 — 평일 08:45~15:45 사이에 뜨면서 오늘 세션
  디렉터리가 아직 없을 때만 기동한다. CP-3 tenant 쪽에도 같은 모양의 catch-up 줄이 있다
  (§7.2-e).

- 시각은 `calendar.yaml` 의 `krx-index-futures` **CONTINUOUS 08:45–15:45 KST MON–FRI** 에
  맞췄다(§5 ④). 런타임은 **마감에 스스로 멎지 않는다** — 세션이 닫히면 틱이
  `SKIPPED_SESSION_CLOSED` 가 될 뿐 `run_forever` 는 계속 돈다. 그래서 정지는 밖에서 온다.
- `1-5` 는 주말을 거르지만 **휴장일은 거르지 못한다.** 휴장 판정은 래퍼가 달력 파일로
  한다(§7.3 4) — cron 줄에 날짜를 적지 않는 이유다.

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

절차 정본은 `docs/runbooks/tos-evidence-cold-backup.md` 다 — 대상은 같은 부모
`~/.local/state/tos/paper-data`, **18:00 KST** 평일, 래퍼가 `A0####` 잎을 순회한다
(설치 이력 · 판본 sha256 은 이력 §7.7).

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

**2. `report.json`** — `~/.local/state/tos/paper-sessions/<날짜>-*/report.json`:

- `boot_proof_ok: true` · `verdict: "ok"` · `exit_code: 0`
- `stop_reason` 은 **셋**이다: `signal`(정상 — 정지 크론) · `deadline`(**정지 크론이 안 돌았다**) ·
  `child_exited`(**`run` 이 스스로 죽었다** — `run_log_tail` 을 본다).

#### held 런타임 — 부팅은 OK 인데 틱이 하나도 처리되지 않는다

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

### 7.11 분봉 수집 — 세션이 쥔 분봉을 과거 저장소로 (운영자 결정 2026-11-28)

**무엇을 하나.** tenant 세션은 저마다 `producer/market` 에 과거 저장소와 **같은 모양**의
Parquet 트리를 쥔다(그날의 봉 + 앞선 시드 날들). 아무도 그것을 과거 저장소
(`config/storage.yaml::market_data.parquet.root` = `data/market`)로 옮기지 않아서
`sts tos replay --data-root data/market` 이 읽을 수 있는 날이 2026-10-08 에서 멈춰 있었다.
`sts tos ingest-bars` 가 그 사본들을 모아 하루 단위로 올린다.

- 같은 코드·날의 사본은 여러 세션에 있다(LONG·SHORT 가 같은 월물, 주식은 `r1…`, 재실행).
  **봉이 가장 많은 사본, 같으면 세션 날짜가 가장 늦은 사본**을 고른다 — 당일 사본은 15:19
  봉에서 끝나고 종가 단일가 봉은 **다음 날** 세션의 시드 사본에만 있다.
- **사본끼리 어긋나도 거부하지 않는다.** 브로커가 분봉을 정정하므로 같은 분의 값이 세션마다
  한 틱씩 다를 수 있다 — 위 규칙(= 가장 나중 브로커 fetch)을 그대로 쓰고, **고른 사본이 다른
  사본과 어긋나는 분 수**를 줄마다 `사본차`(JSON `copy_disagree`)로 적는다. 평소엔 0 이다.
- 저장소가 이미 쥔 하루는 **후보가 그 하루를 담고 있을 때만** 덮는다: 기존 분이 **전부** 후보에
  있고(결손 0) 겹치는 분의 OHLCV 가 **전부 같아야**(어긋 0) 한다. 그 위에서 후보가 더 길면
  `write`, 분 집합이 같으면 `same`, 기존이 더 긴 상위집합이면 `kept_existing` 이다.
  둘 중 하나라도 어기면 `refused:existing_disagrees`(종료코드 2)로 **그 날을 건드리지 않고**
  결손·어긋 분 수를 줄에 적는다 — `replace_minute_day` 가 그 날 디렉터리를 먼저 지우므로,
  봉 수만 보고 쓰면 다른 출처의 더 긴 사본이 **어디에도 없는** 기존 분과 종가 봉을 지운다
  (2026-11-28 독립 리뷰가 실제 저장소의 2026-10-08 선물 두 날에서 그 입력을 찾았다:
  후보가 16 분을 빼먹고 겹치는 모든 칸이 어긋났는데 봉 수만으로 `write` 였다).
  겹치는 값은 **정확 일치**로 본다 — 양쪽 다 저장소 리더의 같은 정규화(OHLC `float64` ·
  거래량 `int64`)를 거친 값이고, 허용오차를 두면 정정된 봉이 「같다」로 통과해 조용히 덮인다.
- 같은 분이 두 번 있으면서 OHLCV 가 어긋나는 사본은 그 날을 **거부**한다
  (`refused:duplicate_timestamps`, 종료코드 2). 세션에 없는 코드·날은 건드리지 않는다.
- **Parquet 를 읽지 못하면 거부다.** 깨진 part 파일을 「그 날은 없다」로 보면
  `replace_minute_day` 가 그 날 디렉터리를 지우고 멀쩡한 봉까지 덮는다. 기존 저장소 쪽이
  읽히지 않으면 그 코드의 칸을 `refused:read_error` 로 적고 **남은 칸은 계속 쓴다**. 세션
  사본 쪽이 읽히지 않으면 그 경로를 이름 불러 실행 전체를 거부한다(둘 다 종료코드 2).
- **도는 생산자의 세션은 건너뛴다.** 생산자는 사는 동안 `<session>/producer/market/.session.lock`
  의 배타 `flock` 을 쥔다(`tools/tos_cp3/live_producer/sinks.py::acquire_session_lock`). 수집은
  그것을 **막지 않고** 한 번 떠보고, 쥐어져 있으면 그 세션의 사본을 전부 버리고 세션을
  `skipped:live` 로 적는다 — 자라는 중인 세션으로 결정하면 반쯤 쓰인 하루가 굳는다.
  떠보는 것은 **오늘(KST) 날짜의 세션뿐**이다: 떠보는 쪽의 공유 `flock` 이 그 순간 부팅하는
  생산자의 배타 `flock` 을 막아 생산자가 자기 세션을 거부해 버리고, 지난 날짜의 세션은 애초에
  살아 있을 수 없다. 잠금 파일이 **있는데 열리지 않으면**(권한·I/O) 생산자가 도는지 알 수
  없으므로 「안 돈다」가 아니라 `skipped:live` 다.
- 끝에 리플레이의 밀도 게이트(330 봉) 아래로 남는 날을 따로 적는다 — 그 날은 모아도
  리플레이가 버린다.
- **잠금 둘, 경로 둘.** `--write` 실행은 `<data-root>/.ingest-bars.lock` 의 배타 `flock` 을
  **기다리지 않고** 잡는다(dry-run 은 잡지 않고, 그 파일을 만들지도 않는다). 아래 cron 줄은
  그 **바깥에서** `/usr/bin/flock -n /tmp/tos-ingest-bars.cron.lock` 으로 한 번 더 막는다 —
  §7.2-e 의 함정대로 **경로가 달라야** 바깥·안쪽 잠금이 서로 막지 않는다. 안쪽 잠금이 따로
  있는 이유는 손으로 돌리는 `sts tos ingest-bars --write` 는 cron 잠금 밖이라는 것이다
  (겹친 두 쓰기 실행은 같은 날 디렉터리를 지우는 사이에 서로의 part 파일을 지운다).

**손으로 돌릴 때.** 기본 동작은 dry-run 이다. 쓰려면 `--write` 가 필요하다.

```bash
cd $MAIN
sts tos ingest-bars                      # 계획만 (dry-run)
sts tos ingest-bars --write              # 실제로 올린다
sts tos ingest-bars --since 2026-11-01 --json
```

**제안 crontab 줄 (운영자가 설치한다 — 이 저장소의 스크립트는 crontab 을 건드리지 않는다).**
빈 평일 슬롯은 16:30 이다(15:45 paper stop · 18:00/18:20/18:40 콜드 백업 · 19:00/19:05/19:10
주식 콜드 백업 사이). `CRON_TZ=Asia/Seoul` 은 crontab 머리에 이미 있다.

```cron
30 16 * * 1-5 /usr/bin/flock -n /tmp/tos-ingest-bars.cron.lock /bin/bash -c 'cd /home/deploy/project/kis_unified_sts && .venv/bin/python -m tools.tos_cp3.ingest_session_bars --write' >> /home/deploy/.local/state/tos/ingest-bars.cron.log 2>&1 # tos-ingest-bars
```

- ⚠ **D 일의 가장 좋은 사본은 D+1 세션의 시드에서야 나타난다.** 16:30 에 돌면 그날치는
  15:19 봉까지의 사본으로 들어가고, **다음 날 같은 작업이 그 날을 종가 단일가 봉까지 있는
  사본으로 다시 올린다**(`write` 한 줄로 또 뜬다). 따로 보정 절차가 없는 이유다 — 매일
  돌기만 하면 어제 날짜가 하루 늦게 완성된다.
- 종료코드 2 는 거부가 있었다는 뜻이다. **칸은 서로 독립이라 한 칸이 거부당해도 남은
  `write` 줄은 계속 쓴다** — 저장소가 거부한 칸만(검증 거부와 디스크·권한 `OSError` 둘 다)
  `refused:store_error` 로 그 줄에 사유까지 적힌다. 그 칸이 **이미 봉을 쥐고 있던 하루**였다면
  `replace_minute_day` 가 쓰기 전에 그 디렉터리를 이미 지웠으므로 그 사실까지 사유에 적힌다 —
  그 줄은 다시 돌려야 복구된다. `cron.log` 의 그날 `refused:` 줄을 보고 그 코드·날을 손으로
  가른다.
- **쓰기 도중에 죽으면.** `replace_minute_day` 는 그 날 디렉터리를 지우고 다시 쓴다. 쓰는
  칸은 (위 규칙상) 기존 하루를 전부 담고 값이 같은 사본임이 이미 증명된 칸이므로, 지우기와
  쓰기 사이에서 죽어도 잃는 것은 **그 세션 사본이 아직 쥐고 있는 봉**뿐이다 — 세션
  디렉터리가 남아 있는 동안 같은 명령을 다시 돌리면 복구된다. (`--write` 는 저장소 잠금을
  쥐므로 겹친 두 실행이 서로의 중간 상태를 지우는 일은 없다.)

### digest 재도출 (런타임 코드를 바꾼 PR)

`tos/src` · `tos/runtime/src` 를 바꾼 PR 은 **같은 PR 에서** 한 명령을 돌린다 — 세 트리
(`config/tos_runtime/{paper,cp3-setup-d-long,cp3-setup-d-short}/release.yaml`)의
`expected_code_digest` 를 함께 다시 쓴다. 이력은 git 이 기록한다(여기에 값을 적지 않는다).

```bash
python tools/tos_redigest.py --write    # 재도출 (세 사본)
python tools/tos_redigest.py --check    # 낡았으면 exit 1 — tos-firewall CI 가 같은 걸 돌린다
```

빠뜨려도 CI 가 잡지만, 그 전에 머지되면: 상주 래퍼가 매일 아침 같은 비교를 하고(이력 §7.3 5)
어긋나면 부팅 전에 ABORT 하며, **tenant 트리는 부팅 레인이 없어** 낡은 핀이 첫 부팅에서 터진다.
(`expected_dependency_set_digest` 는 배포 호스트의 성질이라 이 명령의 범위가 아니다 —
호스트를 바꿨을 때만 `print-digests` 로 직접 전사한다.)
