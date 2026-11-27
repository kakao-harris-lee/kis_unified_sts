# TOS 리플레이(P3) — `sts tos replay` 와 CI 결정 정답 (2026-11-27)

로드맵 `2026-11-11-tos-platform-roadmap.md` §P3 의 실행 계획이다. 앞선 단계(P1 관찰 · P2 선언형
필드 · 두 번째 전략 · 성과 최소판 · `/tos` 가독성)는 끝났다.

## 1. 문제

tenant YAML(전략 · 바인딩 · `fields.yaml`)이나 지표 카탈로그를 바꾼 PR 이 **결정을 어떻게 바꾸는지**
머지 전에 볼 길이 없다. 지금은 다음 날 아침 세션이 돌아야 안다. 000660 · 005380 에서 전략 실험을
시작했으므로(활용 계획 §4.1) 이 공백이 실험 속도를 정한다.

## 2. 목표와 완료 기준

1. `sts tos replay --tree <tree> --from D --to D` 가 과거 분봉 위에서 그 tenant 의 봉별 결정과
   가상 손익을 낸다(호스트의 `data/market` 사용).
2. CI 잡 하나가 출하 트리 다섯(`cp3-setup-d-{long,short}` · `cp3-setup-d-stock-{005930,000660,005380}`)
   을 고정 구간에서 리플레이해 커밋된 정답과 비교한다. 경로 게이팅 없이 모든 PR 에서 돈다.
3. tenant YAML 한 줄을 바꾼 PR 에서 그 잡이 빨갛게 되고, 실패 출력이 **어느 봉의 결정이 무엇에서
   무엇으로 바뀌었는지**를 보인다. 의도한 변경이면 `--update-golden` 으로 정답을 갱신해 같은 PR 에
   싣는다(정답 diff 가 곧 리뷰 대상).

측정: 005380 의 `rsi` 임계 const 를 30→35 로 바꾼 가지에서 잡이 실패하고 diff 가 나온다 / 되돌리면
통과한다. 이 왕복을 PR 본문에 적는다.

## 3. 사실 관계 (2026-11-27 실측)

- **봉 → 필드**는 이미 순수 함수다: `tools/tos_cp3/produce_fields.py::produce_bars_declarative(df,
  symbol=, document=, emit_days=)`. 라이브 생산자(`live_producer/line.py`)가 매 분 같은 함수를 부른다.
- **필드 → 결정**도 이미 있다: `tos/runtime/cp3/inspect_session.py` 는 journal 한 벌과 전략 · 바인딩
  파일만으로 봉마다 규칙을 다시 평가한다(`evaluate_policy` — 엔진의 `run_decision_pipeline` 이 부르는
  그 함수). 증거 DB 없이 돌면 `journal_only` 이고, 그 봉들은 `counted` 다.
- 방화벽 때문에 `tools/` 는 `tos` 를 import 하지 못한다. `sts tos inspect` 는 `python -P -m
  cp3.inspect_session … --json` 을 하위 프로세스로 부른다(`tools/tos_cp3/inspect_session.py::build_argv`).
- **출하 트리는 그대로는 로드되지 않는다.** 전략 파일의 `account` · `instrument` 가 `"TBD"` 이고
  로더가 거부한다. `scripts/tos/render_paper_config.py::render()` 가 채운다(환경 파일을 읽지 않는
  함수, 테스트는 가짜 계좌로 부른다).
- **가상 손익**은 `tools/tos_cp3/hypothetical_pnl.py::build_hypothetical_pnl` 이 inspect 의 `bars[]`
  에서 계산한다(진입 판단 봉 종가 → 다음 청산 판단 봉 종가, 수수료 · 슬리피지 없음).
- **분봉 데이터는 호스트에만 있다.** `data/` 는 gitignore, 커밋된 Parquet 은 0건. 호스트 저장소는
  2026-10-08 에서 끝난다(주식 3종목 135~146 거래일, 미니선물 월물별 17~117 거래일). 그 뒤 날짜는
  기록된 세션 journal 로만 볼 수 있고, 그건 `sts tos inspect` 가 이미 한다.
- **이 저장소는 공개다**(`gh repo view --json visibility` → PUBLIC). `data/` 가 gitignore 인 것은
  사고가 아니라 그 때문이고, 따라서 **실제 분봉은 고정본으로 커밋할 수 없다** — CI 가 읽을 입력은
  지어낸 것이어야 한다(§4.3). 실제 분봉 리플레이는 호스트에서 `--data-root data/market` 으로만 돈다.
- **호스트의 미니선물 분봉은 대부분 장 막판 부분 백필이다**(구현 중 실측): 월물별 중앙값 102 봉/일
  (13:54~15:45 구간), 밀도 게이트 330 봉을 넘는 세션은 `A05610` 에서 셋뿐이다. 호스트 측 선물
  리플레이를 두껍게 하려면 full 세션 분봉을 먼저 쌓아야 한다 — 이 계획의 범위 밖이고, 정답은 합성
  분봉을 쓰므로 영향이 없다.
- 커널 `tos.backtest` 의 `BacktestDriver` 는 테스트 밖에서 아무도 조립하지 않는다. 그 결과
  (`trace_document`)에는 결정 종류도 규칙 id 도 없고 다이제스트만 있다.

## 4. 설계

```
분봉(호스트 Parquet 또는 합성 CSV 고정본) ─ produce_bars_declarative ─▶ journal.jsonl (as_of_ms = 봉의 분)
출하 트리 ─ render(가짜 계좌, 종목) ─▶ 전략 · 바인딩 파일
        └──────── 하위 프로세스: cp3.inspect_session --json ────────▶ 봉별 결정
                                              ├─▶ 결정 구간표(정답 형식)
                                              └─▶ build_hypothetical_pnl ─▶ 가상 손익
```

새 코드는 `tools/tos_cp3/replay.py` 하나와 CLI 등록, 테스트, CI 잡이다. 지표 · DSL 평가 · 손익 계산
· 렌더는 전부 기존 함수를 부른다. 커널과 런타임은 건드리지 않는다.

### 4.1 `tools/tos_cp3/replay.py`

- `replay(tree, *, symbol, bars, emit_days) -> ReplayResult` — 순수(임시 디렉터리만 씀).
  1. `fields.yaml` 로드 → `produce_bars_declarative` → journal 행(`raw_event_id · source_id ·
     instrument · as_of_ms · fields`). `source_id` 는 `tos-cp3-replay/<버전>`.
  2. 트리를 임시 디렉터리에 `render()` — 계좌는 고정 가짜 값, 종목은 인자, 방향은 트리 선언대로.
  3. `inspect_session.run(...)` 의 기존 하위 프로세스 경로로 `--json` 을 받는다.
  4. 결과: 봉별 `(raw_event_id, decision_kind, rule_id)` 열, 생략된 봉과 사유, 가상 손익.
- 분봉 원천 둘: `--data-root`(호스트 Parquet 저장소, 기존 `load_bars` 와 밀도 게이트 그대로 —
  실제 분봉은 여기서만 읽는다) 또는 `--bars-csv`(커밋된 합성 고정본,
  `timestamp,open,high,low,close,volume`). CSV 는 CI 가 저장소 계층과 pyarrow 를 지지 않게 하고,
  공개 저장소에 시세 데이터를 두지 않게 한다. 출처는 출력과 정답 머리에 `bars` 로 실린다.
- 종목 기본값: 주식 트리는 트리 이름의 종목, 선물 트리는 `--symbol` 필수(월물이 날짜에 따라 다르다).

### 4.2 `sts tos replay`

`cli/commands/tos_status.py` 에 등록. 출력은 읽는 사람 기준 세 덩이:

1. 머리 — 트리 · 종목 · 구간 · 봉 수 · 생략 봉 수 · «리플레이는 신호만 본다(§6)».
2. 날짜별 한 줄 — 봉 수, 규칙별 발화 봉 수, 그날 가상 손익.
3. 가상 거래 목록과 합계. 표기는 항상 «가상 손익(체결 가정)».

`--json` 은 같은 내용을 기계용으로, `--runs` 는 결정 구간표를 그대로.

### 4.3 정답

- 입력 고정본: `tests/fixtures/tos/replay/bars/<symbol>.csv.gz` — 종목 넷(주식 셋 + 미니선물 한
  월물 코드), 각 14 거래일(2026-09-01 ~ 09-18), 종목당 42~58 KB. **가격은 합성이다.** §3 의 이유로
  실제 분봉은 커밋할 수 없으므로, `tools/tos_cp3/synthetic_bars.py` 가 표준 라이브러리
  `random.Random(seed)` 로 만든다(numpy RNG 를 쓰지 않는 것은 판이 바뀌어도 같은 바이트가 나오게
  하려는 것이다). 명세 전부 — 씨앗 · 세션 수 · 세션 창 · 기준가 · 호가단위 · 변동성 — 는
  `config/tos_replay_golden.yaml::synthetic` 에 있고, 종목 코드는 공개 식별자라 실제 코드를 쓴다.
  재생성은 `python -m tools.tos_cp3.replay --write-synthetic-bars` 다.
- 과정: 느린 anchor + AR(1) 편차 + 변동성 burst + 세션별 변동성 배수. 편차가 오래 남으므로 세션
  VWAP 에서 멀어진 뒤 되돌아오고, 그 왕복이 Setup D 의 z 극단 · 되돌림 확인과 RSI/%R 의 과매도 ·
  회복을 **둘 다** 만든다. 세션 창은 KIS 분봉 피드가 실제로 주는 범위(주식 09:00~15:19 380 봉,
  선물 08:45~15:34 410 봉)이므로 밀도 게이트를 넘고, 가격은 그 종목 호가단위의 정수배다.
- 정답: `tests/fixtures/tos/replay/golden/<tree>.decisions.tsv`. 머리(트리 · 종목 · **분봉 출처** ·
  구간 · 봉 수 · 생략 수)와 **결정이 바뀐 지점만** 적는 구간표:
  `첫 봉 시각 · 끝 봉 시각 · 봉 수 · decision_kind · rule_id`. 무손실이고, diff 가 «09:41 부터
  3봉이 NO_ACTION 에서 R1 진입으로» 같은 모양으로 읽힌다. 머리의 `# bars  synthetic seed=<n>` 이
  그 아래 가상 손익을 시장 역사로 읽지 않게 하는 표시다.
- `python -m tools.tos_cp3.replay --golden check|update` 가 다섯 트리를 한 번에 돈다. `check` 실패
  출력은 unified diff 다.
- 커밋된 고정본이 그 명세의 출력과 **바이트 동일**한지 정답 테스트가 본다 — 누가 실제 분봉을 그
  디렉터리에 떨어뜨리면 거기서 빨갛게 된다. 막았을 실제 사고: 이 작업의 첫 판이 호스트의 실제
  분봉을 커밋했고(저장소는 공개다) 푸시 직전에 멈췄다.
- 필드 값 자체의 다이제스트는 넣지 않는다. 결정이 같으면 통과다(로드맵 문장 그대로). 부동소수
  끝자리로 CI 가 흔들리는 것을 피한다 — 결정이 흔들리면 그건 봐야 할 일이다.

### 4.4 CI

- 테스트 `tests/tools/test_cp3_replay.py`(합성 봉으로 단위: journal 모양, 생략 봉, 구간표 왕복,
  TBD 트리 렌더)와 `tests/tools/test_cp3_replay_golden.py`(다섯 트리 정답 비교).
- 잡 `tos-replay-golden` 을 `tos-firewall.yml` 에 더하고 집계 잡의 `needs` 에 넣는다. 이 워크플로는
  경로 게이팅이 없어 커널 · DSL · 카탈로그 · tenant YAML 어느 변경에서도 돈다. 설치는 `test.yml` 의
  shard 와 같은 방식(루트 `.[dev]` + `PYTHONPATH` 로 tos · runtime) — 생산자가 `shared.*` 를 읽기
  때문이다. 정답 테스트 파일 하나만 돌린다.
- `test_cp3_*` 이름이라 `test.yml` 에서도 돈다(그쪽은 tos 전용 PR 에서 건너뛴다 — 그래서 위 잡이
  따로 필요하다).

## 5. 기각한 안

| 안 | 이유 |
| --- | --- |
| 커널 `BacktestDriver` + `EngineCore` 로 돌리기(로드맵 초안의 문장) | 조립 루트 전체(단계 · 승인 · venue · 증거 싱크)를 오프라인용으로 다시 세워야 하고, 결과에는 결정이 아니라 다이제스트만 나온다. 이번 목표(결정 diff)는 엔진이 부르는 것과 같은 `evaluate_policy` 로 충족된다. 체결 모델이 필요해지는 P4(손절·목표) 때 다시 본다. |
| **실제 분봉을 고정본으로 커밋** | 공개 저장소에 시세 데이터를 재배포하게 된다(§3). `data/` 가 gitignore 인 것이 그 결정이고, 고정본은 그 결정을 우회하는 자리가 아니다. 합성 분봉이 같은 일을 한다 — 정답이 지키는 것은 「같은 입력에 같은 결정」이고, 그 입력이 시장의 것이어야 할 이유는 없다. |
| 정답을 봉마다 한 줄로 | 다섯 트리 ≈ 2만 5천 줄. 구간표가 같은 정보를 2,854줄로 담는다(005380 의 수준형 청산 규칙이 구간을 자주 끊는다). |
| 설치 판 차이를 미리 맞추기 | 정답은 호스트(Python 3.12)에서 뽑았고 CI 는 3.11 이다. 임계에 맞닿은 봉이 달라지면 첫 CI 가 그 봉을 보여 준다 — 그때 고친다. |
| CI 에 Parquet 고정본 | 잡이 저장소 계층과 pyarrow 를 끌고 온다. CSV 로 같은 프레임이 된다. |
| 기록된 세션 journal 을 정답 입력으로 | 필드가 이미 계산돼 있어 카탈로그 · 생산자 변경을 못 잡는다. 입력은 분봉이어야 한다. |
| 리플레이 전용 필드 계산 루프 | `produce_bars_declarative` 의 생략 게이트를 두 벌로 만든다. |

## 6. 리플레이가 말하지 않는 것

화면과 문서에 그대로 적는다.

- **신호만 본다.** 승인 · 예약 · venue 한도 · 시간 인정 같은 커널 단계는 지나지 않는다. «신호가
  났다» 이지 «주문이 나갔다» 가 아니다. 단계 회귀는 hermetic 테스트와 복구 drill 이 잡는다.
- **포지션을 모른다.** 청산 규칙은 보유 여부와 무관하게 발화한다(라이브도 같다 — 보유가 없으면
  커널이 보내지 않는다). 가상 손익이 진입-청산을 짝짓는다.
- **라이브와 필드가 같다는 증명이 아니다.** 라이브는 시드 + 자라는 프레임으로 매 분 다시 계산한다.
  그 동등성은 `fields_equivalence.py --mode session` 의 일이다.
- 가상 손익은 성과 약속이 아니다(로드맵 §5 위험표).

## 7. 순서

PR 하나(등급 B — 읽기 전용 도구와 CI, 독립 리뷰 1회).

1. `replay.py` + 단위 테스트.
2. `sts tos replay` 등록, 호스트 데이터로 다섯 트리 실행해 출력 확인(호스트에서만 하는 일).
3. 합성 고정본 · 정답 생성, 정답 테스트(바이트 동일 · 규칙 발화), CI 잡.
4. §2 의 왕복 측정(임계 한 줄 변경 → 빨강 + diff → 되돌림 → 초록)을 PR 본문에.
5. 로드맵 §P3 · `docs/plans/INDEX.md` · `PROJECT_STATUS.md` · 루트 `CLAUDE.md` 명령 목록에 한 줄씩.

## 8. 제약

- 증인 동결(`shared/decision/setups/vwap_reversion.py`)과 수입 방화벽은 건드리지 않는다.
  `tos/` · `tos/runtime/` 변경 0 이 기본이다 — 필요해지면 멈추고 그 이유를 적는다.
- 가짜 계좌 값은 테스트 fixture 가 이미 쓰는 것을 쓴다. 실제 계좌 · 환경 파일을 읽지 않는다.
- **고정본은 합성 분봉이다. 시세 값을 커밋하지 않는다** — 이 저장소는 공개이고 `data/` 는 그 때문에
  gitignore 다(§3 · §4.3). 종목 코드는 공개 식별자라 그대로 쓰고, 가격만 지어낸다. 정답의 가상
  손익은 시장 역사가 아니므로 머리에 `# bars  synthetic seed=<n>` 이 적힌다.
- 새 검사(R5)의 근거가 된 실제 사고: 2026-11-12 주식 잎 `EngineReplayDiverged` — 규칙을 바꾼 PR 이
  다음 날 아침에야 드러났다. 결정 정답이 있었다면 그 PR 에서 «결정이 바뀐다»가 먼저 보였다.
