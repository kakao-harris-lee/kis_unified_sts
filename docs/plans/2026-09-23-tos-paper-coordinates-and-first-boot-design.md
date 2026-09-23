# TOS paper 배포 좌표 주입 + 첫 부팅 구성 — 설계 (2026-09-23)

- 작성: 2026-09-23 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 측정 시점 main **`e812804f`** + PR #794 브랜치 `d5075188`
- 상위: `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` W-A **A-5**(§7.8, §7.8.2 좌표 주입 서베이)
- 운영자 결정(2026-09-23, 이 문서의 입력):
  1. 「이 장비가 운영 장비다. 여기 있는 `.env`·`.env.mock` 을 그대로 활용」 → **호스트 생성 스크립트 방식** 선택
  2. `currentness.yaml::required_dimensions` — 제안대로 floor 사용(PR #794 가 반영)
  3. 미확정 값은 추천값이 있으면 사용 · `finality.yaml::value_date` = **`T+1`**(선물 일일정산)
  4. PR #794 이탈 1~4 확인
- 성격: **설계 하나 · 구현 PR 하나(§4)** · 운영자 결정 1건(§3).

## 0. 한 줄 요약

`run` 은 배포 좌표(계좌·종목)가 없어 부팅하지 못한다. tos 코드는 `os.environ` 을 읽을 수 없고(방화벽 TOS-FW-C)
좌표는 커밋하지 않는다(파일 헤더 규율). 그래서 **`tos/` 밖의 호스트 스크립트가 `.env.mock` 을 읽어 커밋된 paper 설정을
복사하고 좌표 칸만 채운 **저장소 밖** 디렉터리(`~/.config/tos/paper-config/`)를 만든 뒤, `run --config-dir <그 디렉터리>` 로 부팅한다.** tos 코드·방화벽
변경은 0 이다. 좌표를 넣어도 부팅은 **첫 부팅 구성**(§3 — 전략 파일·방향·수량 기준)이 정해져야 끝까지 간다.

## 1. 좌표 칸 — 무엇을 어디서 채우나 (PR #794 `d5075188` 기준)

| 파일 | 키 | 채울 값 | 원천 |
|---|---|---|---|
| `venue_constraint_policy.yaml` | `scope.accounts` | `[<선물 계좌>]` | `.env.mock::KIS_FUTURES_ACCOUNT_NO` |
| 〃 | `scope.instruments` | `[<mini 근월물>]` | `shared.instruments.futures.get_front_month_code(product="mini")`, 실행 당일 |
| `order_construction_policy.yaml` | `scope.accounts` · `scope.instruments` | 같음 | 같음 |
| `aggregate_risk_policy.yaml` | `account_scope` · `instrument_scope` | 같음 | 같음 |
| `action_flow_policy.yaml` | `account_scope` | 같음 | 같음 |
| `construction.yaml` **(PR #794 에 없음 — 구현 PR 이 §3 픽스처로 신설)** | `account` · `instrument` | 같음 | 같음 |
| `strategies/*.yaml` | 조건의 `account` · `instrument` | 같음 | 같음(§3 에서 전략 파일이 정해진 뒤) |

- **계좌는 모의 선물 계좌**다. 채택 스코프가 `SYNTHETIC_FUTURES_ORDER`(브로커 미도달)라 합성 경로에서 계좌번호는 **좌표
  일치 검사에만** 쓰이지만, 다음 단계(모의 서버 핸드오버)가 같은 계좌를 쓰므로 지금부터 같은 값으로 맞춘다. `.env`(paper
  런타임 파일)의 선물 계좌는 **실전 계좌**라 쓰지 않는다(비협상 규칙 — 실전 선물 계좌 미펀딩, 주문 경로 금지).
- **종목은 파일에 고정하지 않는다.** 근월물은 만기(`A05610` = 2026-10-08)마다 바뀐다. 스크립트가 실행 당일 뽑는다.

## 2. 생성 스크립트 설계

**위치**: `scripts/tos/render_paper_config.py`(저장소 루트 `scripts/` — `tos/` 밖이라 TOS-FW-C 대상 아님, `shared.*` import
가능). 출력 기본값 **`~/.config/tos/paper-config/`**(저장소 밖 · 권한 700). 저장소 안 경로를 쓰지 않는 이유: gitignore 누락
하나로 계좌번호가 커밋될 수 있다.

**동작**:

1. `--source config/tos_runtime/paper`(커밋된 승인값) 전체를 출력 디렉터리로 **바이트 복사**.
2. `--env-file .env.mock`(기본)에서 `KIS_FUTURES_ACCOUNT_NO` **한 키만** 파싱(값 출력 금지, 로그에는 `account_fingerprint`
   만). `os.environ` 을 오염시키지 않도록 파일을 직접 파싱한다.
3. 근월물 계산(`--instrument` 로 수동 지정 가능).
4. §1 표의 **named-TBD 좌표 칸만** 치환한다. 치환은 **텍스트 단위**(YAML 재직렬화 금지 — 헤더 주석과 출처가 날아간다, review-794
   방법론 지적). 규칙은 파일마다 **키로 앵커된 정확한 원문 줄**(예: `scope:` 블록 안의 `  accounts: ["TBD"]`)이고, 각 규칙은
   **정확히 한 번** 매칭돼야 하며 아니면 거부한다. 파일 안의 다른 `TBD`(예: `order_construction_policy.yaml` 의 `canonical_digest`·
   `activation_record_id` 등 7곳)는 규칙이 아니므로 건드리지 않는다.
5. **호스트 사실로 도출되는 두 칸도 같은 방식으로 채운다**(review-795 HIGH-1):
   - `finality.yaml::source_revision` = 원본 체크아웃의 `git rev-parse HEAD`(2026-09-12 값 제안 §5 가 적은 산출 *방법* 「배포 git SHA」.
     커밋 파일에 넣으면 자기참조라 렌더 시점에만 채울 수 있다).
   - `finality.yaml::proof_recipe_id` = 추천값이 없다(ADR-002-030 §29 Q3 미결 · 09-12 §5 등급 M). 운영자 선택 (가)의 **부팅 증명 픽스처
     규율**로 불투명 토큰 `tos-paper-proof-recipe-bootproof-g1` 을 **커밋 파일에** 넣고 헤더에 「부팅 증명 픽스처 — 승인된 recipe 아님」.
   - `finality.yaml::value_date` = `T+1` 을 **커밋 파일에** 직접 기입(운영자 결정 3 — 좌표가 아니라 정책).
6. **`safety_activation.yaml::members` 도출**(review-795 HIGH-2): 좌표 치환 뒤 렌더 디렉터리에 대고
   `print-policy-digests --config-dir <출력>` 를 실행하고, 그 출력 4-튜플을 렌더된 `safety_activation.yaml::members` 에 기입한다
   (손으로 적지 않는다 — 채택 계획 §2 결정 3). 좌표가 digest 에 들어가므로 이 값은 **호스트마다 다르고 커밋될 수 없다** — 렌더 산출물이다.
7. 출력 디렉터리에 `RENDERED.json`(원본 커밋 SHA · 치환한 칸 목록 · 계좌 지문 · 종목 · `print-policy-digests` 출력 · 생성 시각 KST) 기록.
8. `--check` 모드: 출력 디렉터리와 원본을 비교해 **규칙이 지목한 칸 외 차이 0** 이면 0, 아니면 1.

**가드 — 「이것이 실패하는 구체적 입력」**:

| 가드 | 실패하는 입력 |
|---|---|
| 좌표 칸만 바뀐다 | 원본에 없는 키를 바꾸는 치환 규칙을 추가 → `--check` 와 단위 테스트 RED |
| 칸마다 정확히 1회 매칭 | 원본 파일에 `accounts: ["TBD"]` 가 두 번 있거나 없음 → 스크립트 거부 |
| 계좌 원천이 모의 파일 | `--env-file .env` 또는 `.env.real` 지정 → 거부. CLI 는 파일 이름이 정확히 `.env.mock` 인 경로만 받는다 — **테스트용 우회 플래그는 두지 않는다**(review-795 MEDIUM-4). 테스트는 CLI 가 아니라 내부 함수 `render(source, out, *, account, instrument, revision)` 을 직접 부르고, 그 함수는 env 파일을 읽지 않는다. 핀: `main(["--env-file", "<tmp>/.env"])` → 종료코드 2 |
| 계좌 형식 | 하이픈을 뺀 숫자가 10자리가 아니면 거부(`.env.mock` 선물 계좌는 하이픈 포함 형태 — 원형 그대로 치환하지 않고 로더가 받는 형태로 정규화, 구현 PR 이 로더 입력 형식을 실측해 정한다) |
| 출력이 저장소 밖 | 출력 경로가 저장소 작업트리 안이면 거부 |
| 렌더가 저장소에 아무것도 남기지 않는다 | (review-795 HIGH-3 — 이전 문구가 인용한 「저장소 전체 비밀값 grep 가드」는 **존재하지 않았다**.) 테스트가 저장소 사본(임시 디렉터리 `git clone`) 안에서 스크립트를 실제 CLI 로 실행한 뒤 `git status --porcelain --ignored` 가 **실행 전과 같음**을 단정한다. 출력 경로 검사를 지우거나 출력을 저장소 안 경로로 바꾸는 뮤테이션 → 새 파일이 생겨 RED. 테스트의 계좌는 가짜 값 `9999999999` 뿐 |

**부팅 명령**(런북에 기록):

```bash
python scripts/tos/render_paper_config.py --out ~/.config/tos/paper-config
python -c 'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' run \
  --config-dir ~/.config/tos/paper-config --data-dir <데이터> --custody-root <custody> --environment-label non-live-test
```

**기각한 대안**: 좌표 오버레이 파일을 tos 로더가 직접 읽기(정책 문서 digest 범위 재설계 필요) · custody 확장(계좌는 자격증명이
아니라는 review F2 결정을 뒤집음) · `os.environ` 직접 읽기(TOS-FW-C 개정 = 경계 설계 변경). 셋 다 PR #794 §7.8.2 에 비용 기록.

## 3. 운영자 결정 — 첫 부팅 구성 (좌표만으로는 부팅이 끝나지 않는다)

좌표를 채워도 다음 TBD 가 남는다. 전부 **하나의 구성 결정**에 묶여 있고, 저장소 어디에도 추천값이 없다(PR #794 B3 서베이 ·
`2026-09-16-tos-ocp-sizing-values-proposal.md` §2 ② 「전략 파일 확정 후」).

| TBD | 묶여 있는 것 |
|---|---|
| `strategies/*.yaml`(DSL 10 리프 — `direction`·`quantity_basis` 포함) | 무엇을 거래하는가 |
| `order_construction_policy.yaml::admitted_quantity_bases` | 전략의 `quantity_basis` 와 같아야 함 |
| `order_construction_policy.yaml::axes[DIRECTION]` | **배포 전체에 방향 하나** — 현 설계는 구성 단위 고정값(`tos/runtime/src/tos_runtime/venue/construction_rules.py` `ActionClassShape` 독스트링) |
| `construction.yaml::action_class` · `outbound_side` · `instrument_class` | 방향과 일치해야 함 |
| `construction.yaml::price_field_key` · `shape_price_field_key` | `critical_input_policy.yaml` 과 함께(없으면 price=None 경로) |

**핵심 충돌**: 현 설계에서 `DIRECTION` 은 배포 전체에 하나만 줄 수 있다. 비협상 규칙은 선물의 **롱/숏 대칭**이다.
`order_construction_policy.yaml:185-194` 주석이 이미 이 충돌을 적고 「전략 제안 경로가 착지하면 시도별 조회가 된다」고 한다.

선택지:

- **(가) 부팅 증명용 고정 구성 — 추천.** SYNTHETIC 스코프(브로커 미도달)에서 **부팅이 틱을 소비하는지** 만 증명하는 최소
  구성: 방향 하나(`LONG`) · `NEW_LONG`/`BUY` · 수량 기준 `RISK`(현 픽스처 토큰) · 1계약. 모든 파일 머리에 「부팅 증명 픽스처 —
  거래 전략 아님 · 대칭은 전략 제안 경로 착지 후」를 박고, 같은 구성을 `SHORT` 로도 한 번 부팅해 **양방향 모두 부팅됨**을
  증거로 남긴다(대칭을 좁히지 않았다는 증명). 실주문 0 · 브로커 호출 0.
- (나) 전략 제안 경로(시도별 방향 조회)를 먼저 구현하고 부팅한다. 대칭 문제를 설계로 푼다. 커널·런타임 변경 — 별도 계획 필요.
- (다) A-5 를 「좌표 주입까지」로 닫고 첫 부팅 구성은 전략 아크로 넘긴다. `run` 은 계속 부팅하지 않는다.

**운영자 선택(2026-09-23): (가) 부팅 증명 픽스처.** 대칭을 좁히지 않았다는 증거로 LONG·SHORT 두 구성 모두 부팅시킨다.

## 4. 구현 PR (결정 뒤) 모양

1. `scripts/tos/render_paper_config.py` + 단위 테스트(`tests/unit/scripts/` 신설 — 레거시 `test` 워크플로 게이트, 가짜 env 파일) · `--check`.
2. 커밋 파일: `finality.yaml::value_date: "T+1"` · `proof_recipe_id: "tos-paper-proof-recipe-bootproof-g1"`(픽스처 헤더) + 핀 갱신
   (PR #794 의 `_VALUE_PINS`). `source_revision`(렌더 시 git SHA)과 `safety_activation.yaml::members`(렌더 시 `print-policy-digests`)는
   렌더 산출물이라 커밋 파일에서는 named-TBD 를 유지한다 — §2 5·6항.
3. §3 이 (가)면: 부팅 증명 전략 파일·construction·OCP 두 칸을 **부팅 증명 픽스처 헤더**와 함께 커밋, LONG/SHORT 두 번 부팅 증거.
4. 런북 `docs/runbooks/tos-paper-boot.md` — 생성 → 부팅 → 정지 → 확인.
5. 종료조건: 호스트에서 `run` 이 **거부 없이 틱을 관측**(저널 틱 원천 채택이 필요하면 그것도 이 PR — `marketfeed.yaml` +
   `critical_input_policy.yaml` 은 추천값이 없으므로 **§3 과 같은 부팅 증명 픽스처 규율**로)하거나, 남은 거부를 이름으로 지목.

## 5. 착지 기록

(비어 있음)
