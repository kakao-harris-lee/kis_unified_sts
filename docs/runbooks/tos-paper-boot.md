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

**세션 뒤 — §3.6 대조** 명령 여섯 줄과 수용 기준(M5 · M6 · B3)은 이력 §7.2-d 에 있다.

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
