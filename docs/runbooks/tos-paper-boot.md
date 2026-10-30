# TOS paper 운영 런북 — 상주 세션 · CP-3 tenant 세션 · 콜드 백업

- 이 파일은 **오늘 운영자가 돌리는 절차**만 담는다. 명령 · 경로 · 결말 표 · 분류 질의.
- 과거 실측 · 수용 기록 · 드라이런 · 설계 이력은
  [`tos-paper-boot-history.md`](tos-paper-boot-history.md) 로 **그대로 옮겼다**(한 줄도 고치지
  않았다). 절 번호는 **양쪽에서 같다** — 다른 문서의 `§4-A` 는 이력 파일의 `§4-A` 다.
- ⛔ 이 런북은 호스트를 바꾸지 않는다. cron · 설정 파일 · 모드 변경은 전부 운영자 결정이다.

| 이력으로 옮긴 절 | 무엇 |
| --- | --- |
| §0 | 이 배포가 무엇이고 무엇이 아닌가 (전문) |
| §1 · §2 · §3 · §4 · §6 | 1회성 부팅 — 커스터디 루트 · 렌더 · 부팅 · 정지 확인 · 정리 (분기 1회 SHORT 부팅증명이 이 절차를 쓴다) |
| §4-A · §4-A-1 · §4-B | `migrate` v1 → v2 와 그 실행 기록 · 대화형 `backup-set --archive-dir` |
| §5 ①–⑤ | 2026-09-24 실측 차단 이력(정본 digest · 부팅 라벨 · HSE · 세션 게이트 · 방향 결속) |
| §7.1 · §7.2 좌표 규율 · §7.2-a | 상주 결정의 배경 · 0700 패치 실측 |
| §7.2-b (배경) · §7.2-c | tenant 경로 지정의 근거 · ③ 이전의 손 부팅 증명 절차 |
| §7.2-d (해설) | 러너가 무엇을 바꿨나 · §3.6 대조 명령과 수용 기준 M5/M6/B3 · band 설계 |
| §7.3 | 래퍼 `start` 가 하는 일(순서) · 드라이버 출처 |
| §7.9 · §7.9-leaf · §7.9-held(증상) · §7.10 | 드라이런 기록 · 닫힌/열린 질문 · 종목 롤 측정 |

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

**세션 뒤 — §3.6 대조는 러너가 자동으로 돌린다**(step 14, 2026-10-29). 손으로 돌릴
여섯 줄과 수용 기준(M5 · M6 · B3)은 이력 §7.2-d 에 그대로 있고, 자동 단계는 그 여섯
줄을 **서브프로세스로 그대로** 돌린다(`tools/tos_cp3/post_session_b3.py` ·
설정 `config/tos_cp3_b3.yaml`). 읽을 것 둘:

- `<session>/b3/report/summary.json` — **무엇을 봤나**. `unresolved.count` 와
  `live_comparison.divergent` 가 §2-1 의 두 판정 수다. 이 파일을 쓰는 것은
  `diff_decisions.py` 하나뿐이다.
  - `summary_schema_version` **3 부터** `divergent` 가 「설명 안 되는 divergence」다
    (2026-10-29). 선언된 차이는 `live_comparison.declared_difference_counts` 에
    선언 id 별로, 대조에서 빼 둔 봉은 `live_comparison.excluded_bar_counts` 에
    사유별로 따로 나온다 — 다섯 수(`identical` · `kind_only_matches` ·
    선언 · `divergent` · `excluded_from_comparison`)의 합이 `bars_in_scope` 다.
    v2 의 `divergent` 는 선언된 차이를 섞어 세므로 그 수로 §2-1 을 읽지 않는다.
- `<session>/b3/status.json` — **돌았나**. 첫 단계 **전에** `verdict: running` 으로
  쓰이고 끝에 원자적으로 교체되므로, `running` 이 남아 있으면 **끝내지 못한 것**이다
  (예산 초과 · SIGKILL). `failed` 는 사유와 멈춘 단계(`stage`)를 싣고, `skipped` 는
  설정이나 시장 때문에 돌리지 않은 것이다. 단계 로그는 `<session>/b3/logs/`.

**실측 2026-10-29 (long-20261028 세션 · 잎은 그 세션 뒤의 콜드 백업 gen9).** 여섯 단계
25.9 s, `summary.json` 409 봉 · **unresolved 0**.

처음 그 실측의 `live_comparison.divergent` 는 **26/409** 였고, 그 26 건은 전부 이미
기계가 읽을 수 있는 곳에 선언돼 있는데 대조가 그 곳을 읽지 않은 것이었다. 두 집합을
읽게 한 뒤(2026-10-29) 세 세션 실측:

| 세션 | 봉 | identical | 선언 B1b-D1 | 대조 제외 pre_boot | **divergent** |
| --- | --- | --- | --- | --- | --- |
| long-20261028 | 409 | 383 | 25 | 1 | **0** |
| long-20261029 | 409 | 353 | 55 | 1 | **0** |
| short-20261029 | 409 | 369 | 39 | 1 | **0** |

- **B1b-D1** — 오프라인만 `capacity_denied` 이고 실시간은 아닌 봉. `tos.backtest` 는
  한 scope 당 주문 하나를 run 내내 들고 있고(예약 투영에 release 경로가 없다) 첫 발사
  뒤는 전부 정확한 capacity 거부라서 생기는 차이이고, B1b 가 자기 `lineage.json`
  (`declared_differences`)에 그렇게 선언한다. **한 방향만**이다 — 실시간이 거부하고
  오프라인이 아닌 경우는 이 차이가 아니고 divergent 로 남는다. 결정 종류까지 어긋나면
  역시 divergent 다. lineage 가 그 id 를 선언하지 않으면 아무것도 재분류하지 않는다.
  - ⚠ **선언된 한계**: 실시간의 **진짜 capacity 누수**(자기 예약을 들고 있는데 두 번째
    노출을 허용)는 B3 에서 이 차이와 **구분되지 않는다** — `live.jsonl` 에 노출 상태가
    없어 「release 돼서 거부 안 됨」과 「거부돼야 했는데 안 됨」을 가를 수 없다. B3 의
    oracle 은 kickoff §3 B4(「체결 비교 포기」)대로 결정/의도 수준이고, 누수는 엔진 자신의
    at-most-one-exposure 불변식이 잡는다.
- **08:45 봉** — 부팅 시점에 이미 생산자 journal 에 있던 줄이라 설계상 boot 에서 stale
  이고 엔진은 보류밖에 할 수 없다(`DECISION_WITHHELD` / `TIME_NOT_ADMITTED`). 러너의
  `boot-journal-snapshot.json::pre_boot_raw_event_ids` 가 **id 로** 지목하는 봉만
  빼고, 그 id 는 `consumed-ids.json` 이 실어 온다. 시각이나 순서로 빼지 않는다 —
  **post-boot 의 `TIME_NOT_ADMITTED` 는 M5 ① stale 신호이고 그대로 센다**.
  - **조건은 둘**: id 가 지목되고 **그 봉의 실시간 레코드가 보류 모양**
    (`outcome_kind: NO_OUTCOME`)이어야 한다. 지목된 봉인데 실시간이 실제로 결정을 냈으면
    그대로 대조하고 `live_comparison.pre_boot_bars_not_held_out` 에 id 를 남긴다.

오프라인 분류(`bars` · `buckets` · `unresolved`)는 빼 둔 봉까지 409 봉 그대로다. 빠진
것은 그 한 봉의 **실시간 대조**뿐이다.

⚠ 그 실측이 처음에는 거부로 끝났고, 그것이 **왜 여태 summary 가 없었는지**다:
`live-decisions` 가 누적 잎 전체(6 일 2,348 건)를 담아 B3 가
「live decision(s) name bars that are not compared」로 거부했다. 2026-10-22 의 세션 날짜
범위 고정이 consumed-ids 문서에만 적용돼 있었다 — 이제 두 문서가 같은 boot 스냅샷으로
같은 날에 묶인다(`session_inputs.LiveScope`).

`sts tos status` 는 이 둘을 그 순서로 읽는다 — 돌지 않은 세션은 수를 보여 주지 않고
사유를 보여 준다. ⛔ **B3 의 rc 는 세션의 종료 코드를 바꾸지 않는다**(위 「종료 코드」가
그대로다): 세션의 판정은 런타임과 생산자에 대한 것이고, 돌지 못한 대조는 그 둘에 대해
아무 말도 하지 않는다. 러너 로그의 `=== END B3 rc=…` 줄이 그 rc 를 적는다.

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

#### 7.2-e CP-3 tenant 세션 — 매 거래일 무인 cron (재범위 M1 · 운영자 2026-10-22)

§7.2-d 를 거래일마다 LONG·SHORT 한 번씩 무인으로 돌린다. 2026-10-22 에 손으로 넣은 두 줄
(비커밋 `~/.config/kis-probes/run-cp3-tenant-daily.sh`)을 저장소가 소유하는 형태로 바꾼 것이다.

| 무엇 | 어디 |
| --- | --- |
| 래퍼 원본(추적) | `tools/tos_cp3/runners/cp3_tenant_daily.sh` |
| 래퍼 설치본 | `~/.config/kis-probes/run-cp3-tenant-daily.sh` (mode 700 · 설치기가 **`origin/main` 에서** 복사) |
| 설치기 | `tools/tos_cp3/runners/install_tenant_cron.sh` — **기본 dry-run** · `--apply` · `--remove` · 멱등 |
| cron 블록 | `# BEGIN CP3_TENANT_DAILY` … `# END CP3_TENANT_DAILY` — LONG `38 8 * * 1-5` · SHORT `40 8 * * 1-5` |
| cron stdout | `~/.local/state/tos/cp3-{long,short}-tenant-daily.cron.log` (⚠ 로테이션 없음) |
| 세션 아티팩트 | `~/.local/state/tos/cp3-sessions/{long,short}-<YYYYMMDD>/` (`runner.out` · `session.log` · `producer/` · `config/`) |
| 그날의 워크트리 | `~/.local/state/tos/measure/wt-cp3-{long,short}-<YYYYMMDD>` — 다음 거래일 호출이 지운다 |
| 잠금 | `/tmp/cp3-{long,short}-tenant-daily.wrapper.lock` — 래퍼 **안에서** `flock -n`. 10-22 손 설치 줄이 바깥 flock 으로 잡던 `….lock` 과 **다른 경로**다 — 같은 경로면 바깥·안쪽 잠금이 서로 막아 매일 거부된다 |

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
- 블록 밖의 `# cp3-{long,short}-tenant-daily` 꼬리표 줄(10-22 손 설치분)은 지운다 — 한 방향이 두
  번 걸리지 않게. 그 위의 꼬리표 없는 `CRON_TZ=Asia/Seoul` 한 줄은 남는다(무해). 나머지 줄은
  바이트 그대로다. 제거는 `--remove`(dry-run) → `--remove --apply`.
- 시각이 08:45 가 아니라 08:38/08:40 인 이유: 생산자가 CONTINUOUS 08:45 전에 떠 있어야 하고,
  두 생산자가 REAL 조회 키를 함께 쓰는데 KIS 토큰 발급이 분당 1 회다.

**한 호출이 하는 일.** 잠금 → 같은 날 세션 디렉터리가 있으면 거부 → durable set 부모
(§7.2-b)가 없으면 거부(첫 genesis 는 운영자 몫) → 그 방향의 어제 워크트리 제거(`--force` 없이)
→ fetch → `origin/main` 분리 워크트리 → **그 트리의** tenant 달력으로 휴장·주말 판정(+ `CP3_DAILY_EXTRA_CLOSED`
— 기본 빈 값, KRX 연말 `2026-12-31` 은 달력에 있음) → `run_tenant_session.sh`(정지 = 그날 종료 + 5분, 평일 15:50 · 개장 지연일은 §7.2-g).

**텔레그램 (briefing 채널 · 자격증명은 상주 래퍼와 같은 `$MAIN/.env` 두 줄).** 본문은 rc ·
방향 · 날짜 · 경로뿐이다 — `runner.out` 은 옮기지 않는다(좌표 규율).

| 결말 | 텔레그램 | 래퍼 rc |
| --- | --- | --- |
| 정상 (러너 0 · 143) | `일일 세션 종료 … — 정상` 한 줄 | 러너 rc |
| 러너 실패 (3 · 4 · 5 · 129/130 · 그 밖) | `일일 세션 실패 … rc=N` + 뜻 한 줄 | 러너 rc |
| 잠금 점유 (앞선 호출이 아직 돈다) | 실패 한 줄 | 75 |
| 세션 디렉터리 이미 있음 · 부모 없음 · 호스트 zone ≠ +0900 | 실패 한 줄 | 2 |
| 휴장 판정 자체가 실패(달력 못 읽음 · 날짜 오류 · `yaml` import 실패 등) | 실패 한 줄 — **SKIP 으로 읽지 않는다**(판정 스크립트의 «휴장» 은 종료코드 10 하나뿐) | 2 |
| 달력에 그 해 휴장일이 하나도 없다(달력이 해를 넘기지 못함) | 실패 한 줄 | 2 |
| fetch · 워크트리 실패 | 실패 한 줄 | 1 |
| 휴장 · 주말 · 연말 | **없음** — cron 로그 `SKIP` 한 줄 | 0 |

그래서 **거래일 09:00 까지 방향마다 줄이 하나도 없으면** 그 자체가 소견이다 — cron 이 돌지
않았거나(`cron.log` 에 그날 줄 없음) 텔레그램 전송이 실패했다(`telegram notify FAILED` — HTTP 4xx·5xx 도 실패로 센다(`curl --fail`), 자격증명이 없으면 무엇이 없는지 그 줄에 적힌다). 정상
줄은 15:50 정지 뒤에 오므로, 낮 동안의 확인은 `cp3-sessions/<dir>-<날짜>/session.log` 를 본다.

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

#### 7.2-f CP-3 주식 MOCK 세션 (M2) — 첫 세션 2026-10-26(월) · 손으로 한 번 · cron 없음

005930 · 1주 · Setup D LONG · 09:00–15:30 · **모의 계좌만**. 수용(rescope §3 M2) = 체결 1건 이상 + 사슬 연결.
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
  · `price_scale: 100` · `request_timeout_s: 10` · `min_send_interval_ms: 2000` · `app_key_request_wait_budget_ms: 4000` · `token_reissue_min_interval_s: 60` · `allow_plaintext_for_tests: false`
  · `ACNT_PRDT_CD` = **계좌 뒤 2자리**(다르면 코덱이 송신 거부). §4 표의 「`mode: live` 무조건 거부」는 옛 문장 — 지금은 compose 가 `codec_bound=True` 를 준다.
  · ⚠ **이 파일은 준비 때 한 번 쓰이고 그 뒤 갱신되지 않는다.** 준비 뒤 main 에 새 필수 키가 생기면 부팅이 `KisMockTransportConfigError: … missing entry '<키>'` 로 거부한다(송신 0).
    실제 사례 2026-10-30 첫 세션: 10-26 준비본에 #979(10-28)의 `app_key_request_wait_budget_ms` 가 없어 r1 부팅 거부. 고침은 그 키 한 줄을
    스크립트 정본(`setup_stock_mock_once.sh` 의 같은 줄)과 **같은 값**으로 운영 파일에 추가 — 덮어쓰기 재실행은 거부되므로 손으로 넣는다.
    세션 전날 점검: `diff <(grep -oE '^[a-z_A-Z]+:' $ST/cp3-setup-d-stock-ops/kis_mock_transport.yaml | sort) <(git -C $MAIN show origin/main:tools/tos_cp3/runners/setup_stock_mock_once.sh | sed -n '/^mode: live/,/^allow_plaintext/p' | grep -oE '^[a-z_A-Z]+:' | sort)` — 출력이 없어야 한다.
- **상시 승인(그날, 운영자 · #955)** — 파일 `$ST/cp3-setup-d-stock-custody/approvals/standing-session.yaml`(0600). 쓰는 때는 아래 «볼 것» 의 `render ok` 줄 뒤 · 첫 진입 전(런타임이 이미 떠 있어도 된다 — 첫 사용 때 결속).
  승인 없이는 신호가 와도 4단계에서 멎는다(송신 0). MOCK 트리가 아니면 rc 1 로 아무것도 쓰지 않는다 · 덮어쓰기는 `--replace` 뿐.
  **재작성**(예: `max_uses` 를 올림)은 운영자 권한이고 **재기동 뒤에** 적용된다 — 슬롯이 거래일로 키잉돼 이미 쓴 횟수는 그대로 센다.
  **청산(10-26)**: 이 승인은 1주 진입 BUY 하나만 허락하고 청산은 승인되지 않는다(#960: CLOSE 명령이 BUY 로 만들어진다). 세션 뒤 모의 계좌에
  1주 롱이 남는다 — 평탄하게 하려면 모의투자 HTS 에서 손으로 판다. ⛔ 청산을 제안별 승인 파일로 **절대** 승인하지 않는다(두 번째 1주를 **산다**).
- **genesis** = 빈 잎 `$ST/cp3-setup-d-stock-005930-data/005930` 에 대한 첫 `run`(러너가 잎을 만든다 · 되돌릴 수 없다 · 승인 행위는 없다). 다음 날부터는 같은 잎을 잇는다.

**08:55 시작(창 08:52–09:05: 첫 행은 09:01:0x 에 오고 첫 행 대기 상한이 600 s).** LONG 08:38·SHORT 08:40 는 **선물** REAL 키, 이 세션은 **주식** REAL 키(생산자·band)와 모의 키(런타임) — 지문이 서로 달라 분당 1회 토큰 발급이 겹치지 않는다.
```bash
D=$(TZ=Asia/Seoul date +%Y%m%d) RUN=${RUN:-1}; WT=$ST/measure/wt-cp3-stock-r$RUN-$D   # 같은 날 재기동은 RUN=2 로 이 블록을 다시
git -C $MAIN fetch -q origin && git -C $MAIN worktree add -q --detach $WT origin/main && export TOS_REPO=$WT TOS_PYTHON=$MAIN/.venv/bin/python \
  TOS_STOCK_SESSION_ROOT=$ST/cp3-sessions/stock-r$RUN-$D TOS_STOCK_DATA_PARENT=$ST/cp3-setup-d-stock-005930-data TOS_STOCK_ENV_MOCK=$MAIN/.env.mock \
  TOS_STOCK_CUSTODY_ROOT=$ST/cp3-setup-d-stock-custody TOS_STOCK_KIS_MOCK_TRANSPORT_CONFIG=$ST/cp3-setup-d-stock-ops/kis_mock_transport.yaml TOS_STOCK_STOP_AT=15:40 \
  && mkdir -m 700 $TOS_STOCK_SESSION_ROOT && cd $WT && set -a && . tools/tos_cp3/runners/stock-mock-session.env.example && set +a \
  && { nohup bash tools/tos_cp3/runners/run_tenant_session.sh >$TOS_STOCK_SESSION_ROOT/runner.out 2>&1 & echo $! >$TOS_STOCK_SESSION_ROOT/runner.pid; }   # 한 고리가 실패하면 아무것도 뜨지 않는다
```
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
**정지 · 킬스위치.** 새 셸이면 먼저 `ST=~/.local/state/tos D=<YYYYMMDD> RUN=<n>; TOS_STOCK_SESSION_ROOT=$ST/cp3-sessions/stock-r$RUN-$D`. 정상: `TENANT_STOP_AT` 에 러너가 스스로 멎는다(rc 0/143). 손 정지 = `kill -TERM $(cat $TOS_STOCK_SESSION_ROOT/runner.pid)`(러너가 런타임 → 생산자 순으로 멈춘다).
러너가 죽었는데 런타임이 남았으면 `pkill -TERM -f "stock-r$RUN-$D/render"`. `AUTHORITY_WITNESS_LOST` 는 그 프로세스에서 영구다 — 회복은 재기동(시작 블록을 `RUN=2` 로)뿐. ⛔ **이미 나간 모의 주문의 취소는 런타임에 없다(#948) — KIS 모의투자 HTS 에서 손으로.**

**장 마감 뒤 수용.** 같은 attempt 하나에 아래가 모두 있으면 M2 수용 — 승인(`APPROVAL_STANDING_CONSUMED` 의 `rcl_command_id` = RCL `ConsumeApprovalDecision` `iap-consumption:standing-approval:<YYYYMMDD>:…`) · `CommitReservation` · VERIFY_ITEM 17 · `SEND_SEALED`/`TRANSPORT_SEND` · `ACK` · `FILL_OBSERVED` + `FULL_FILL|PARTIAL_FILL` · `POSTTRADE_FINALITY_PROOF`(`broker-fqp-proof:<attempt>`) · RCL `release-<attempt>` · `ENGINE_PROJECTION_RELEASED`. 질의는 종류·개수·id 접두만 찍는다(예약 id·payload 에는 계좌가 있다 — 옮겨 적지 않는다).
```bash
sqlite3 -readonly $L/evidence.sqlite3 "SELECT COALESCE(json_extract(payload_json,'\$.payload.attempt_id'),replace(json_extract(payload_json,'\$.payload.idempotency_key'),'broker-fqp-proof:','')) a,kind,COUNT(*),group_concat(DISTINCT json_extract(payload_json,'\$.payload.egress_result_kind')) FROM entries WHERE kind IN ('VERIFY_ITEM','SEND_SEALED','TRANSPORT_SEND','EGRESS_RESULT_CONSUMED','FILL_OBSERVED','POSTTRADE_FINALITY_PROOF','ENGINE_PROJECTION_RELEASED') GROUP BY a,kind ORDER BY a,MIN(seq)"
sqlite3 -readonly $L/evidence.sqlite3 "SELECT json_extract(payload_json,'\$.payload.action'),json_extract(payload_json,'\$.payload.rcl_command_id') FROM entries WHERE kind='APPROVAL_STANDING_CONSUMED'"
sqlite3 -readonly $L/rcl.sqlite3 "SELECT seq,kind,substr(command_id,1,64) FROM entries WHERE kind IN ('ConsumeApprovalDecision','CommitReservation','ReleaseReservation') ORDER BY seq"
```
- **신호가 없으면**(`SEND_SEALED` 0 · `FLOW_HALTED` 가 `INDEPENDENT_APPROVAL` 이전에서만 · `COORDINATOR_MESH_HELD` 0) 코드 실패가 아니다 — 수용은 다음 거래일로 넘어간다(새 세션 디렉터리 · 같은 잎).
- **⛔ 세션일에는 같은 모의 계좌·005930 으로 취소 프로브(P-SC, `kis-capability-probes.md` §5.10)를 돌리지 않는다.** 그날 그 종목에 FILLED 가 아닌 주문이 한 건이라도 있으면 보유 증명(`_quantity_for_snapshot`)이 None 이 되어 그날 CLOSE 가 모두 UNKNOWN 이다(fail-closed · 송신 0 · 포지션은 다음 날로 넘어간다 — review-1007 L4, #1012). 프로브는 세션이 없는 날에 돌린다.
- **되돌림.** 세션을 시작하지 않으면 끝이다 — LONG·SHORT·상주는 이 트리와 경로·키·잎을 공유하지 않는다. 송신을 막으려면 `$ST/cp3-setup-d-stock-custody/kis_mock.app_*` 를 지운다 — 부팅은 되지만 첫 토큰 사용(브로커 사실 GET·송신)이 거부돼 송신 0. 잎은 append-only 증거라 지우지 않는다.

#### 7.2-g 개장 지연일(날짜별 세션 예외) — 수능일 등 (#924)

KRX 가 어떤 날의 개장·종료를 옮기면(수능일: 주식·지수선물 각각 지연, 시장마다 다르게) 그 날짜를
**캘린더 한 곳**에 적는다 — `config/tos_runtime/{paper,cp3-setup-d-long,cp3-setup-d-short,cp3-setup-d-stock-005930}/calendar.yaml`
의 `session_overrides` (네 파일은 바이트 동일 유지 · 형식은 파일 안 주석). 이 한 항목을 런타임 세션
게이트(`tos_runtime.calendar`)·생산자 첫 봉/종료 커서·주식 첫 페이지 커서(`quote_initial_cursor: session_end`)·
러너 첫 줄 대기(지연분만큼 늘어남)·밴드 기동 시각·cron 래퍼 정지 시각(`그날 종료 + CP3_DAILY_STOP_AFTER_CLOSE_MIN`)이
모두 읽는다. 다른 곳에 시각을 다시 적지 않는다.

**2026-11-19(2027학년도 수능) — 아직 비어 있다.** 2026-10-24 기준 KRX 공지가 없다(작년 공지 10-30).
공지가 나오면: ① 공지 URL·시각으로 네 파일에 같은 항목 추가 ② `calendar_version` 과 각 트리
`time.yaml::trading_calendar_version` 을 같은 커밋에서 올린다 ③ PR. 선례(2025-11-13): 주식
10:00–16:30, KOSPI200·미니 선물 개장·종료 각 +1h — **선례는 참고일 뿐, 공지 확인 전 입력 금지.**

**머지 뒤, 11-19 전 dry-run (읽기 전용, 운영자):**

```bash
git -C $MAIN fetch -q origin
for dir in LONG SHORT; do ~/.config/kis-probes/run-cp3-tenant-daily.sh $dir --preflight 2026-11-19; done
# 기대: "PREFLIGHT session krx-index-futures CONTINUOUS 2026-11-19 <공지 개장>-<공지 종료> OVERRIDE · stop_at=<종료+5분>"
#        (18일 등 평일은 "08:45-15:45 regular · stop_at=15:50")
# 주식(수동 세션)의 정지 시각은 같은 리더로 구한다 — TOS_STOCK_STOP_AT 에 그대로 넣는다:
.venv/bin/python -P -m tools.tos_cp3.session_day stop-at \
  --producer-config config/tos_probes/cp3-live-producer-stock-005930.yaml \
  --repo-root . --date 2026-11-19 --after-close-min 5
```

래퍼는 cron 이 설치한 사본이므로 이 PR 머지 뒤 `install_tenant_cron.sh --apply` 로 사본을 한 번
갱신해야 새 정지 시각 도출을 쓴다(그 전 사본은 `15:50` 고정). 상주 paper 세션 래퍼(`~/.config/kis-probes/tos-paper-session.sh`)
는 이 저장소 밖이라 이 PR 이 건드리지 않는다 — 그날 정지 시각을 운영자가 확인한다.

### 7.4 cron 두 줄 — ✅ **설치됐다 (운영자 2026-10-03 15:43 KST)**

설치된 줄은 이것이다(설치된 블록 그대로 — 주석 머리 한 줄 포함):

```cron
# TOS paper 상주 세션 (운영자 결정 2026-10-03 · 첫 세션 2026-10-06 · 런북 tos-paper-boot.md §7.4; 크론 끝에 둔다 — CRON_TZ 는 아래 줄에만 적용)
CRON_TZ=Asia/Seoul
45 8  * * 1-5 /bin/bash /home/deploy/.config/kis-probes/tos-paper-session.sh start >> /home/deploy/.local/state/tos/paper-logs/cron.log 2>&1 # tos-paper-session
45 15 * * 1-5 /bin/bash /home/deploy/.config/kis-probes/tos-paper-session.sh stop  >> /home/deploy/.local/state/tos/paper-logs/cron.log 2>&1 # tos-paper-session
```

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
