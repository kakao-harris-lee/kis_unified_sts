# CP-3 ④ tenant 부팅 경로 재설계: 렌더 일반화 · 슬롯 단일화 · 저널 원천 분리 (2026-10-09)

- **상위**: `docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md` §5 3 ④(「렌더의 전략 파일 상수 · 다섯 digest 재도출 ·
  `safety_activation.yaml::members` 갱신」) — PR #884 작성 레인의 실측이 「상수 한 줄 교체로는 안 된다」를 보였다.
- **운영자 지시 2026-10-09 (대화)**: 「다시 설계」.
- **범위**: 렌더러(`scripts/tos/render_paper_config.py`, 레거시 쪽 · `tos` import 불가)와 tenant 트리 파일과 tenant
  세션 실행 절차. **커널·런타임 패키지 변경 0**이 목표다(§7 에서 확인).
- **v2 (2026-10-09, 독립 리뷰 PR #885 처분 — 9건 전건 수용, 기각 0)**: H1 declared 모드의 방향 검증(§2.3) · H2 스크래치
  전용 규칙의 기계적 강제(§2.5) · M1 치환 템플릿 규칙과 키 집합 핀(§2.1) · M2 `--check` 와 `RENDER.yaml`(§7) · M3 상주
  동일성 증명 강화(§4.1) · L1~L4.
- **v3 (같은 날, 재리뷰 3건 전건 수용)**: H2 의 둘째 거부는 가려진 절 → 삭제, 모든 행 · `resolve()` 비교 · 레드 증명 셋 ·
  M1 핀을 키 이름이 아니라 슬롯 튜플 전체로 · 템플릿 규칙 ④ 에 YAML 앵커 토큰 하나 허용(바이트 동일 조건).
- **범위 밖**: ③ 실시간 필드 생산자(별도 설계) · band 원천 웨이브(`2026-10-08-tos-cp3-band-source-wave-plan.md`) · 상주
  paper 의 거동 변경(이 계획 전체에서 상주 렌더 산출은 **바이트 동일**이어야 한다, §4.1).

## 0. 한 줄 요약

렌더러의 하드코딩된 규칙 표(상주 트리 전용)를 **트리마다 커밋되는 렌더 매니페스트**로 옮기고, 「앵커는 정확히 1회」
규칙은 **그대로 둔 채** tenant 전략 파일의 반복 좌표를 **YAML 앵커/별칭**으로 한 줄에 모은다. 방향은 tenant 에서
**치환하지 않고 검증**하고(트리가 방향별로 커밋돼 있다), 관측 저널은 상주의 합성 저널과 tenant 의 **외부 원천(③)** 으로
나눈다. ③ 이전의 부팅 증명은 스크래치 data dir 에서만, 합성 표지를 단 채로 한다.

## 1. 지금 무엇이 막히나 (실측, main `78272d8b`)

| 막힘 | 자리 |
|---|---|
| 규칙 표가 **상주 트리 상수**다 — 파일 이름(`strategies/bootproof_band.strategy.yaml`), 앵커 줄, `policy.rules[0]` 만 | `scripts/tos/render_paper_config.py:150` (`_STRATEGY_FILE`) · `:210-232` (`COORDINATE_RULE_KEYS`) · `:235-371` (`_coordinate_rules`) |
| 앵커는 파일 안에서 **정확히 1회**여야 한다 — tenant 전략 파일은 규칙이 셋이라 `account: "TBD"` · `instrument: "TBD"` 가 각 3회 | `render_paper_config.py:553-569` (`_apply_rules`) · `config/tos_runtime/cp3-setup-d-long/strategies/setup_d_long.strategy.yaml:109-111,145-149,169-170` |
| 방향을 **치환**한다 — tenant 전략은 규칙마다 방향이 다르다(R1 진입 LONG, R2·R3 는 롱을 닫는 SHORT) | `render_paper_config.py:139-147,274-279,311-358` |
| 렌더가 **합성 저널**을 쓴다(close 4,499,000 등) — tenant 에 쓰면 15 필드가 없어 아무것도 안 돌거나, 지어낸 값으로 돈다 | `render_paper_config.py:117,152-163,847` (`_write_journal`) |
| `--check` 는 등록된 앵커 줄만 바뀌었는지 본다 — 규칙 표가 바뀌면 같이 바뀌어야 한다 | `render_paper_config.py:1167-` (`check`) |
| tenant 트리의 `release.yaml` 은 상주의 **바이트 사본**이다 — 런타임 코드 PR 이 `paper/release.yaml` 만 재도출하면 tenant 사본이 낡아 tenant 부팅이 ABORT 한다(지금은 검출 테스트 없음 → tenant 완성 PR 에 드리프트 가드 추가 중) | `config/tos_runtime/cp3-setup-d-long/release.yaml` · `config/tos_runtime/paper/release.yaml` |
| 활성화 기록은 **방향을 결속하지 않는다** — LONG/SHORT 렌더의 다섯 digest 가 바이트 동일 | `render_paper_config.py:632-638` (docstring, review-797 LOW-6) |

## 2. 설계

### 2.1 렌더 매니페스트 (`<tree>/RENDER.yaml`, 트리마다 커밋)

규칙 표를 코드 상수에서 **데이터**로 옮긴다. 매니페스트는 그 트리의 슬롯과 모드를 선언하고, 렌더러는 그것만 실행한다.

```yaml
tree_id: "cp3-setup-d-long"
direction:
  mode: "declared"          # 상주는 "substitute"(오늘 거동), tenant 는 "declared"(치환 안 함 · --direction 과 대조)
  value: "LONG"
journal:
  mode: "external"          # 상주는 "synthetic_bootproof"(오늘 거동), tenant 는 "external"(렌더러가 쓰지 않음)
slots:                      # 각 항목 = 오늘의 Rule 하나: 파일 · 키 이름 · 정확한 원문 앵커 줄 · 값 원천
  - file: "venue_constraint_policy.yaml"
    key: "scope.accounts"
    anchor: '  accounts: ["TBD"]'
    value: "account"        # 닫힌 집합: account | instrument | revision | journal_path | direction_action_class | direction_side | direction
  # …
```

- **값 원천은 닫힌 집합**이다. 매니페스트가 리터럴 값을 실을 수 없다 — 「승인되지 않은 값을 쓰는 규칙」을 막던 오늘의
  `COORDINATE_RULE_KEYS` 핀의 성질을 유지한다.
- **치환 템플릿(리뷰 M1).** 오늘의 치환문은 균일하지 않다 — `"TBD"` → 값, `"LONG"` → 방향, `source_revision: null` →
  `source_revision: "<rev>"`(따옴표가 생긴다), `NEW_LONG`/`BUY` → 토큰(`render_paper_config.py:235-371`). 그래서 슬롯은
  `replacement` 템플릿 필드를 갖되 그 모양을 렌더러가 검증한다: ① `{value}` 자리표시가 **정확히 하나** ② 그 밖에 `{`/`}` 없음
  ③ 템플릿에서 `{value}` 와 그 양옆의 따옴표를 뺀 **키 접두**(첫 `:` 까지)가 앵커의 키 접두와 같음 ④ 자리표시 밖의 나머지
  문자는 따옴표·대괄호·공백뿐 — **단 하나의 예외**: 키 접두 바로 뒤의 YAML 앵커 토큰 하나(`&[A-Za-z_][A-Za-z0-9_]*`)는
  허용하되 앵커 줄과 템플릿에서 **바이트 동일**해야 한다(§2.2 의 `          account: &account "TBD"` 슬롯이 이 규칙을
  통과해야 하므로 — 재리뷰 MEDIUM). 그래서 템플릿이 리터럴 값을 실어 나를 수 없다. 레드 증명 둘: 템플릿에 `"A05610"` 리터럴 →
  거부 · 템플릿의 앵커 이름이 앵커 줄과 다름(`&acct` vs `&account`) → 거부.
- **키 집합 핀(리뷰 M1).** 슬롯 목록이 데이터로 옮겨 가면 렌더러 자신의 자기 검사(`:1097-1101`, `rendered_keys` vs
  `COORDINATE_RULE_KEYS`)는 매니페스트를 자기 자신과 비교하게 된다 — 슬롯을 하나 더해도 아무것도 red 가 되지 않는다.
  그래서 **트리마다 기대 슬롯을 테스트의 리터럴로 커밋**한다 — 키 이름 집합이 아니라 `(file, key, anchor, replacement)`
  **튜플 전체**(재리뷰 LOW: 키 이름만 핀하면 `construction.yaml::account` 키를 `  tick_size: 5` 줄에 다시 겨눠도 통과한다).
  상주 = 오늘의 `_coordinate_rules` **20개**와 같은 튜플(정정 2026-10-09, PR #888 실측: `_coordinate_rules` 는 20 이고
  `COORDINATE_RULE_KEYS` 가 21 이다 — 21번째 `safety_activation.yaml::members` 는 아래 행대로 매니페스트에 **없고**
  늘 도출되므로 이 리터럴에도 들어가지 않는다). 슬롯 추가·변경은 테스트 수정을 요구한다. 레드 증명: 키는
  `construction.yaml::account` 그대로 두고 앵커 `  tick_size: 5` 와 템플릿 `  tick_size: {value}` 를 **함께** 바꾼 매니페스트
  → red. (앵커만 바꾸면 템플릿의 키 접두가 앵커와 달라 규칙 ③ 이 먼저 거부하므로 핀의 기여를 보이지 못한다 — 3차 리뷰
  LOW, #838. 함께 바꾼 입력은 ①~④ 를 모두 통과하고 핀만이 잡는다.)
- 렌더러는 매니페스트를 읽어 `Rule` 을 만들고 **`_apply_rules` 는 그대로** 쓴다(정확히 1회 규칙 불변).
- `members` 슬롯은 매니페스트에 넣지 않는다 — 오늘처럼 렌더러가 `print-policy-digests` 로 **항상** 도출한다
  (`render_paper_config.py:374-386,1090-1094`). 손으로 쓰는 경로를 만들지 않는다.
- `--check` 는 같은 매니페스트에서 앵커 집합을 얻는다.

### 2.2 반복 좌표의 단일화 — YAML 앵커/별칭

tenant 전략 파일에서 첫 규칙의 좌표 줄만 앵커를 달고 나머지는 별칭으로 참조한다:

```yaml
# R1
          account: &account "TBD"
          instrument: &instrument "TBD"
# R2, R3
          account: *account
          instrument: *instrument
```

- 원문에 `account: &account "TBD"` 줄은 **한 번**만 있으므로 오늘의 「정확히 1회」 규칙이 그대로 성립한다.
- 런타임 로더는 `yaml.safe_load` 다(`tos/runtime/src/tos_runtime/strategy/loader.py:216`) — 별칭은 파싱 시 해석되고,
  그 뒤의 `first_null_leaf` · `first_named_tbd_leaf` 검사(`:224-237`)가 해석된 값 전체를 훑는다. 그래서 별칭 하나를
  빠뜨리면(렌더 뒤 `"TBD"` 가 남으면) **로더가 이름을 밝혀 거부한다** — 새 가드를 만들 필요가 없다.
- `loader.py:210` 의 sha256 은 렌더된 **원문 바이트**에 대한 것이라 별칭 표기도 그대로 증거에 들어간다.
- 방향은 별칭으로 묶지 **않는다** — 규칙마다 값이 다르고(§1), tenant 에서는 치환하지 않는다(§2.3).

**구체적 실패 입력과 레드 증명**: R3 의 `account: *account` 를 `account: "TBD"` 로 되돌린 파일 → 렌더는 R1 앵커만 채우고
성공하지만, 로더가 `policy.rules[2]…account` 의 `'TBD'` 로 거부해야 한다. 이 테스트가 그 거부를 단언한다.
같은 테스트가 「별칭 버전을 채워 파싱한 값 == 세 번 다 리터럴로 적은 버전을 파싱한 값」도 단언한다(별칭이 의미를 바꾸지
않는다는 증명).

### 2.3 방향 — tenant 는 치환하지 않고 검증

- 상주(`mode: substitute`): 오늘과 같다. `--direction SHORT` 가 네 자리를 함께 바꾼다(런북 §7.10 3).
- tenant(`mode: declared`): 트리가 방향별로 커밋돼 있다(`cp3-setup-d-long`·`cp3-setup-d-short`). 렌더러는 `--direction`
  이 매니페스트 `direction.value` 와 **같지 않으면 거부**한다.
- ⚠ **그것만으로는 방향 검사가 사라진다(리뷰 H1).** 오늘 LONG 렌더의 방향 규칙은 줄을 **자기 자신으로** 바꾸는데, 앵커가
  정확히 1회 맞아야 하므로 LONG 이 아닌 트리는 렌더를 거부한다(`render_paper_config.py:244-247` docstring). 활성화는 방향을
  결속하지 않고(`:632-638`), 런북 §⑤(`docs/runbooks/tos-paper-boot.md:794-801`)는 방향 일관성을 「렌더가 네 자리를 함께
  바꾼다」와 paper 트리 전용 핀에 기댄다. 매니페스트끼리만 비교하면 이 검사가 **없어진다**. 구체적 실패 입력:
  `cp3-setup-d-short` 트리에 LONG 의 `RENDER.yaml`(`value: "LONG"`)을 복사했거나 `construction.yaml` 이 아직
  `NEW_LONG`/`BUY` 인 상태로 `--direction LONG` 렌더 → 렌더 성공 · 다섯 digest 동일 · 활성화 통과 · 아무것도 거부하지 않음.
- **처분**: declared 모드에서도 방향 슬롯을 **검증 전용 규칙**(치환문 == 앵커, 선언된 방향의 토큰으로 만든 줄, 정확히 1회
  매칭)으로 남긴다 — `construction.yaml::action_class`·`outbound_side` · OCP `DIRECTION` 축 · `marketfeed.yaml::direction` ·
  전략 파일 **진입 규칙**의 `direction`. 그래서 위 입력은 「**매니페스트 순서상 첫 방향 슬롯**(오늘은 OCP `DIRECTION`
  축)의 앵커 0회 매칭」으로 거부된다(정정 2026-10-10 PR-B 실측 — v3 는 `action_class` 를 지목했는데 그 슬롯은 더 뒤에
  있어 먼저 발화하지 않는다. `action_class` 앵커도 0회인 것은 참이고, 테스트가 그것을 따로 센다). 트리마다
  방향 일관성 테스트를 둔다(레드 증명 = 위 입력 그대로).
- 왜 치환을 버리나: tenant 전략은 규칙마다 방향이 다르고 SHORT 진입 비교도 다르다(`z_x1000 >= +1800`) — 치환으로는
  만들 수 없고, 그래서 SHORT 트리를 따로 커밋했다(kickoff §5 3). 치환과 커밋이 둘 다 있으면 두 원천이 된다.
- 활성화가 방향을 결속하지 않는 문제(§1 끝 행)는 그대로 남는다. tenant 는 트리 자체가 방향별이고 **data dir 도
  방향별**(지정은 tenant 완성 PR)이라 섞일 경로가 상주보다 좁다. `RENDERED.json` 에 `tree_id` 를 더한다(`direction` 은 이미
  있다 — 런북 `tos-paper-boot.md:196`).

### 2.4 저널 — 합성과 외부 원천의 분리

- 상주(`mode: synthetic_bootproof`): 오늘과 같다(`_write_journal`).
- tenant(`mode: external`): 렌더러는 저널을 **쓰지 않는다**. `--journal-path` 인자가 **필수**이고 없으면 거부한다.
  그 경로는 ③ 생산자의 출력이다.
  ⚠ **정정 2026-10-10 (PR-B 리뷰 L1, 실측).** v3 는 여기에 「③ 이 없으면 tenant 는 렌더되지 않는다(fail-closed)」라고
  적었는데 **과대진술이다**. 렌더러가 거부하는 것은 **인자 부재**와 **존재하지 않는 파일** 둘뿐이고, 존재하는 파일이면
  무엇이든 통과한다 — 리뷰어가 **빈 파일**로 렌더를 성공시켰다. 바로 아래 행이 말하듯 내용은 읽지 않으므로 그래야
  맞고(두 문장이 서로 모순이었다), **합성 저널이 지정 data dir 에 닿는 것을 막는 것은 렌더러가 아니라 §2.5 의
  스크래치 루트 거부(PR-C)**다. fail-closed 인 것은 「③ 의 출력 경로를 **대지 않으면** 렌더가 안 된다」까지다.
- `journal_path` 슬롯 값은 인자에서 온다. 렌더러는 그 파일의 존재만 확인하고 내용은 읽지 않는다(생산자 계약은 ③ 의 일).
- ⛔ **그 ③ 계약에는 2026-10-09 운영자 결정이 붙인 구속 요구가 하나 있다 — `as_of_ms` 는 저널에 append 하는 시각이어야
  한다.** tenant 트리의 `critical_input_policy.yaml::fields[].max_age_ms` 는 **800**(= 커널 시간 예산
  `MAX_time_conservative_freshness_age_ms` 1000 − Σ지연 200)이고, `max_age_ms` 와 커널 시간 경로는 **같은 양**
  (`now_ms - as_of_ms`)을 잰다. B1a 처럼 봉의 **라벨(OPEN)** 로 찍으면 관측의 최소 나이가 60,000 ms 라 열다섯 필드가
  전부 `(UNKNOWN, "stale")` 이고, 한도를 올려서 고칠 수 없다(올리면 커널이 같은 양으로 재서 거부한다). 근거는 그 트리의
  `critical_input_policy.yaml` 헤더와 kickoff §5 3 ② 다. 이 계획은 ③ 을 설계하지 않지만, 이 요구는 ③ 설계의 입력이다.

### 2.5 ③ 이전의 부팅 증명 — 스크래치 전용

배선(렌더 → 활성화 → 로더 → 15 필드 → 결정 → 거부)을 ③ 없이 증명하려면 저널이 필요하다. ⚠ 「15 필드 **소비**」라고
적었던 v3 의 표현은 2026-10-09 운영자 결정(`max_age_ms` 800) 뒤로 **과장**이다 — 아래 둘째 항목의 이유로 그 한 행은
신선도 창을 놓칠 공산이 크다. 그래서:

- 별도 도구 `tools/tos_cp3/bootproof_journal.py`(레거시 쪽 · `tos` import 없음): 15 필드를 가진 **한 행**을 **현재 시각**
  `as_of_ms` 로 쓴다. 값은 B1a 실측 창(`~/.local/state/tos/measure/cp3-b1a-run1/`)의 한 봉을 그대로 빌리고 `source_id` 에
  `cp3-bootproof-synthetic` 표지를 단다.
- ⚠ **그 한 행도 `max_age_ms` = 800 을 만족하지 못할 공산이 크다(2026-10-09 운영자 결정의 결과).** 쓰기 시각에 찍어도
  쓰기와 부팅 사이가 800 ms 를 넘으면 `_derive_field_state` 가 `(UNKNOWN, "stale")` 를 돌려준다 — 상주 렌더의 부팅 증명
  관측이 `_JOURNAL_AGE_MS` 1000 > 800 때문에 **언제나** STALE 인 것과 같은 모양이다(런북 `tos-paper-boot.md`
  §「렌더가 만든 부팅 증명 관측은 부팅 시점에 이미 STALE 이다」). 그러므로 이 도구가 증명하는 것은 **배선**(렌더 → 활성화
  → 로더 → 15 필드 **선언** → 결정 경로)이지 **필드 소비**가 아니다. 소비까지 보려면 부팅 **뒤에** 행을 덧붙이거나(원자적
  전체 파일 교체 — `marketfeed/journal.py`) ③ 을 기다린다. PR-C 는 어느 쪽을 택했는지 실측과 함께 적는다.
- 이 저널로 하는 부팅은 런북 §3 의 1회성 절차 그대로, **스크래치 data dir** 에서만 한다. 지정된 tenant data dir
  (`~/.local/state/tos/cp3-setup-d-*-data`)에는 **절대 쓰지 않는다** — 첫 실제 genesis 는 ③ 의 실데이터로 한다.
- ⚠ **산문만으로는 이 규칙이 지켜지지 않는다(리뷰 H2).** 렌더러는 저널을 읽지 않고 data dir 을 모르며, 실행 템플릿은 data
  부모를 env 로 받는다. 구체적 실패 입력: `run_tenant_session.sh` 에 data 부모 `~/.local/state/tos` + 부팅 증명 저널 → 지정된
  `cp3-setup-d-*-data` 저장소에 합성 데이터로 genesis. 저장소는 append-only 라 **되돌릴 수 없다**.
  **처분 — 실행 템플릿의 거부 하나**(레드 증명 = 위 입력 그대로): 저널의 **어느 행이든** `source_id` 가
  `cp3-bootproof-synthetic` 접두를 달고 있으면, data dir 의 `Path.resolve()` 가 스크래치 루트(`~/.local/state/tos/scratch/`)의
  `Path.resolve()` 아래에 있고 **새로 만든 빈 디렉터리**일 때만 진행한다. 부팅 증명 도구 쪽에도 같은 검사를 둔다(두 진입점
  어느 쪽에서도 막히게). v2 에 있던 둘째 거부(「지정 패턴 + 합성 → 거부」)는 첫째가 이미 덮어 혼자서는 발화할 수 없는 가려진
  절이라 **삭제**했다(재리뷰 LOW, #838). 해석(`resolve`)이 있으므로 스크래치 루트 아래의 심볼릭 링크가 지정 dir 을 가리키는
  경우도 거부된다 — 이것을 둘째 레드 증명으로 둔다(스크래치 루트 안 심볼릭 링크 → 지정 dir, 합성 저널 → 거부). 첫 행만이 아니라
  모든 행을 보는 레드 증명: 첫 행은 실데이터 표지, 셋째 행이 합성 표지 → 거부.
- B1a 값을 쓰는 이유: 지어낸 값이 아니고, B1b 실행이 같은 값으로 이미 결정을 냈으므로 부팅 증명 결과를 B1b 트레이스와
  대조할 수 있다. ⚠ **단 그 봉은 full 계약 `101S6000` 의 것이다(리뷰 L1)** — `cp3-b1a-run1` 의 lineage 가 그렇고(세션
  2025-12-08, 가격대 ~583), 부팅 증명 행은 소비되려면 렌더된 **mini** 종목 코드를 달아야 한다. 즉 full 값을 mini 로 **재표지**
  하는 것이다(10-08 v1 의 full→mini 오독과 같은 모양이므로 숨기지 않는다). 그래서 `source_id` 에
  `cp3-bootproof-synthetic:101S6000:<원 raw_event_id>` 로 원 계약과 원 행을 남기고, 결과를 시장 사실로 읽지 않는다 — 이 부팅은
  **배선**을 증명할 뿐이다.

### 2.6 tenant 세션 실행

- 상주 래퍼(`~/.config/kis-probes/tos-paper-session.sh`, 호스트 · 비커밋)는 **건드리지 않는다**.
- tenant 는 추적되는 실행 템플릿을 둔다 — 선례 `tools/broker_probes/runners/run_p_ca.sh`(PR #825: 분리 워크트리 · clean ·
  `origin/main` 조상 가드 · 인스턴스 값은 전부 env 필수, 기본값 0개). 위치 제안: `tools/tos_cp3/runners/run_tenant_session.sh`.
- 템플릿이 받는 값: 트리 id · 방향 · 렌더 출력 dir · data 부모 dir(잎 `<종목>` 은 상주처럼 근월물 코드) · 저널 경로 · 정지
  시각. 기본값을 두지 않는다. 지정된 경로(tenant 완성 PR 의 data dir 지정)는 런북에만 적고 템플릿에는 하드코딩하지 않는다.
- cron 등록은 이 계획에 없다 — 첫 실제 세션은 ③ 뒤의 운영자 결정이다.

## 3. 기각한 대안

| 대안 | 이유 |
|---|---|
| 「앵커 N 회 매칭」 규칙(횟수 선언) | 위치를 **열거하는** 가드다 — 메모의 반복 결함(가드를 문장 종류·위치의 열거로 쓰면 거의 틀린다). 횟수가 맞아도 엉뚱한 줄일 수 있어 YAML 경로 재검증이 추가로 필요해진다. 별칭은 「1회」 불변을 유지하고 누락은 기존 로더 검사가 잡는다 |
| YAML 왕복(load → 수정 → dump) | 렌더러가 의도적으로 금지한다 — 헤더 주석과 출처 인용이 사라진다(`render_paper_config.py:191-194`) |
| tenant 전용 렌더 스크립트를 새로 | 오프-레포 출력 거부 · 계좌 원천 검사 · 스테이징 스왑 · 활성화 재검증이 이미 있다(`:534` · `:394` `parse_account_from_env_file` · `:933` · `:814`). 복제는 두 번째 구현 |
| tenant 에서도 방향 치환 | §2.3 — 규칙마다 방향이 다르고 SHORT 비교가 달라 치환으로 못 만든다 |
| tenant 트리를 상주 트리에 대한 **상속**(차이 파일만 커밋, 나머지는 렌더 시 상주에서 복사) | DRY 이고 `release.yaml` 드리프트(§1)를 구조적으로 없앤다. 다만 커밋된 트리만으로 로더 테스트를 돌릴 수 없게 되고 리뷰 단위가 흐려진다. **이번엔 사본 + 드리프트 가드**(tenant 완성 PR)로 가고, 상속은 tenant 트리가 셋 이상이 되면 다시 본다 |

## 4. 불변식과 테스트

### 4.1 상주 렌더는 바이트 동일

상주 트리의 매니페스트는 오늘의 `_coordinate_rules` 와 **같은 규칙 집합**이어야 한다. 테스트 둘:

1. 매니페스트에서 만든 `Rule` 튜플 == 오늘의 하드코딩 튜플(이행 PR 에서만 둘 다 존재 — 이행 뒤 하드코딩 쪽 삭제). 이행 뒤에는
   §2.1 의 트리별 기대 키 집합 리터럴이 그 역할을 잇는다.
2. 같은 입력(가짜 계좌 · 고정 `now_ms` · 같은 리비전)으로 이행 전후 렌더 산출이 **바이트 동일** — **LONG 과 SHORT 둘 다**
   (리뷰 M3 a: substitute 모드에서 방향 치환은 SHORT 에서만 바이트를 바꾸고, 이 PR 이 그 네 치환을 데이터로 옮기므로 런북
   §7.10 3 의 「네 자리가 바뀌면 그 PR 에서 SHORT 를 돌린다」에 해당한다). `RENDERED.json` 은 키를 **더하는 것**만 허용하고,
   호스트 드라이버가 읽는 다섯 키 — `instrument` · `journal_path`(`~/.config/kis-probes/tos_paper_session.py:331-333`) ·
   `activation_check` · `source_revision` · `rendered_at_kst`(`:366-370`) — 는 **값이 같아야** 한다(리뷰 M3 b). 래퍼가 매일
   `origin/main` 에서 다시 만들므로(런북 §7.10 6) PR-A 는 머지 다음 08:45 에 바로 운영에 들어간다.
3. 상주 세션의 08:45 경로에 인자 변경이 필요 없어야 한다 — 드라이버는 `--out --env-file --instrument --direction` 만 넘기고
   기본 `--source` 에 기댄다. 그래서 `paper/RENDER.yaml` 은 렌더러 변경과 **같은 PR** 에 들어가야 한다.

### 4.2 tenant

- 매니페스트 로드 거부: 닫힌 집합 밖의 `value` · `direction.mode`/`journal.mode` 가 둘 중 하나가 아님 · 슬롯 파일 부재.
- `declared` 모드에서 `--direction` 불일치 → 거부. `external` 모드에서 `--journal-path` 부재 → 거부. `external` 에서
  렌더러가 저널 파일을 쓰지 않음(산출 dir 에 `bootproof_journal.jsonl` 없음).
- §2.2 별칭 누락 → 로더 거부(레드 증명) · 별칭 == 리터럴 파싱 동치. ⚠ 그 레드 증명은 R3 를 `"TBD"` 로 되돌린 경우만 잡고,
  R2/R3 에 **다른 리터럴 값**을 적은 경우는 통과한다(리뷰 L4) → 파싱 뒤 **모든 규칙 target 의 account·instrument 가 서로
  같다**는 단언을 더한다(레드 증명: R2 에 `"A05611"` 리터럴).
- §2.3 방향 일관성: 트리마다, 검증 전용 방향 규칙이 그 트리의 선언 방향 토큰으로 정확히 1회씩 맞는다(레드 증명: SHORT 트리 +
  LONG 매니페스트 · SHORT 트리 + `NEW_LONG` construction).
- §2.5 스크래치 강제: 실행 템플릿과 부팅 증명 도구가 스크래치 루트 밖 + 합성 저널을 거부(레드 증명 셋: 위 H2 입력 · 스크래치
  루트 안 심볼릭 링크 → 지정 dir · 셋째 행에만 합성 표지).
- 매니페스트 템플릿 검증(§2.1): 리터럴을 실은 템플릿 거부.
- 렌더된 tenant 트리가 `print-policy-digests` 다섯 줄(CRITICAL_INPUT_POLICY 포함)을 내고 활성화 재검증을 통과.
- `--check` 가 tenant 렌더에서 등록 슬롯 밖 변경을 잡고, external 모드에서 `bootproof_journal.jsonl` 부재를 문제로 보지
  않는다(§7).

## 5. 순서

1. **PR-A (렌더러 일반화)**: 매니페스트 로더 + 상주 `RENDER.yaml` + §4.1 세 테스트. 상주 산출 바이트 동일이 머지 조건.
   `scripts/` 변경이라 `expected_code_digest` 와 무관(설치 패키지 루트 밖) — PR 에서 실측으로 확인.
2. ✅ **PR-B (tenant 매니페스트 + 별칭) — 2026-10-10 완료**: LONG·SHORT 트리에 `RENDER.yaml` · 전략 파일 별칭화 · §4.2 테스트. tenant 완성
   PR(값·SHORT·data dir·드리프트 가드)이 머지된 뒤에. 같은 PR 에서 tenant 전략 파일 헤더의 낡은 주장 둘을 고친다(리뷰
   L2 — 9행 「B1b 사본과 좌표 두 칸만 다르다」는 별칭화로 거짓이 되고, 36행의 행 번호 100·101·136·137·160·161 은 이미
   109·110·145·146·169·170 이다). tenant 완성 PR 에 B1b ↔ 배포 전략 드리프트 가드가 있으면 별칭 표기를 그 가드가 허용하도록
   함께 맞춘다.

   **실측 처분**:
   - 두 트리의 매니페스트는 **각 20 슬롯**(상주와 같은 20 개를 tenant 파일 이름과 방향 토큰으로 옮긴 것)이고
     `direction.mode: declared` + `journal.mode: external` 이다. 검증 전용 방향 슬롯은 **다섯**이다 —
     `construction.yaml::action_class`/`outbound_side` · OCP `DIRECTION` 축 · `marketfeed.yaml::direction` ·
     전략 **진입 규칙**의 `direction` — §2.3 의 처분 목록 그대로다. ⚠ 로더의 declared 필수 검사는 **값 원천
     세 종류**(`direction` · `direction_action_class` · `direction_side`)를 요구하고 그 셋이 이 다섯 슬롯에 걸쳐
     있으므로, **슬롯 하나를 지워도 그 검사는 통과할 수 있다**(예: `marketfeed.yaml::direction` 만 지우면 세 원천이
     모두 남는다). 다섯이 다 있다는 것을 고정하는 것은 로더가 아니라 PR-B 의 트리별 기대 슬롯 리터럴과
     `test_every_direction_slot_is_verify_only_and_matches_the_committed_tree` 다.
   - `finality.yaml::source_revision` 슬롯은 tenant 트리에도 **있다**(그 파일이 상주 바이트 사본이다).
   - **B1b ↔ 배포 드리프트 가드는 수정이 필요 없었다.** `tos/runtime/cp3/tests/test_cp3_short_strategy_content.py::
     test_b1b_copy_equals_the_deployed_tenant_strategy_after_normalising_coordinates` 는 `yaml.safe_load` **뒤**를
     대조하고(`normalise_coordinates` 가 파싱된 문서를 받는다) 별칭은 파싱 시 해석되므로, 별칭 표기가 그대로 통과한다.
     바이트 대조가 아니라는 것은 그 테스트 자신의 docstring 이 적고 있던 사실이다. 그래서 「텍스트로 비교하면 정직하게
     고치고 기록한다」 조항은 발동하지 않았다 — 실측으로 확인했다(23 tests pass, 변경 0).
   - 전략 파일 헤더의 낡은 주장은 **둘이 아니라 셋**이었다: 9행 · 36행의 행 번호 **그리고** 「⛔ 렌더는 아직 이 파일을
     채우지 못한다」 블록 — 그 블록은 이 PR 이 바로 거짓으로 만드는 것이므로 함께 고쳤다. 행 번호는 다시 적지 않고
     **표기에 대한 진술**로 바꿨다(헤더가 길어지면 또 어긋난다).
   - 드리프트 가드 `tos/runtime/tests/compose/test_tenant_tree_copies.py` 의 `RENDER.yaml` 은 `_RESIDENT_ONLY` 에서
     `_DIFFERS_FROM_RESIDENT` 로 옮겼다(사본이 아니다 — 매니페스트는 자기 트리를 적는다).
     `test_tenant_tree_short.py` 에서는 `_DIFFERS_FROM_LONG` 에 `{tree_id, direction.value, slots}` 로 등재하고,
     `slots` 가 리스트라 **한 잎으로 접히므로** `_FOLDED_PREFIXES` 에 넣고 좁히기 테스트를 함께 달았다.
   - 두 트리 파일 수 **31 → 32**, README 의 계수 문장 셋을 함께 갱신했다(그 문장들을 **파싱하는** 테스트가 있다).

   **독립 리뷰 처분 2026-10-10 (HIGH 0 · MEDIUM 0 · LOW 2 — 전건 수용, 기각 0)**. 리뷰어가 실측으로 재현한 것:
   두 트리 tmp 렌더 · 다섯 digest 와 활성화 · `check()` 빈 리스트 · 운영 로더가 target 을 바르게 해석 ·
   LONG/SHORT 차이가 기대 자리에만 · 레드 증명 R1·R2·R5·R6·R8 재현. 다섯 슬롯 전수성이 로더가 아니라 **트리별
   리터럴**에 걸려 있는 것은 **수용 가능**으로 판정됐다(로더로 옮기지 말 것 — 로더는 값 원천 셋만 알면 되고,
   「이 트리가 몇 자리에서 방향을 말하는가」는 트리의 사실이지 렌더러의 사실이 아니다).
   - **L1 — 문서가 external 모드의 fail-closed 를 과대진술했다.** §2.4 본문 · 두 tenant README · kickoff 셋이
     「③ 이 없으면 tenant 는 렌더되지 않는다」고 적었는데, 렌더러는 **인자 부재**와 **없는 파일**만 거부하고 내용은
     읽지 않는다 — 리뷰어가 **빈 파일**로 렌더를 성공시켰다. 네 자리 모두 「무엇을 거부하고 무엇을 거부하지 않는가」로
     고쳤고, 합성 저널 차단의 실제 소유자가 **§2.5 스크래치 루트 거부(PR-C)** 임을 같이 적었다.
   - **L2 — tenant README 의 `--check` 안내에 명령줄이 없었다.** 런북 꼴 그대로 치면 `--source` 기본값인 **상주
     `config/tos_runtime/paper`** 와 대조해 **거짓 차이 + rc 1** 이 난다. 두 README 에 `--source` 를 명시한 전체
     명령줄을 `.venv/bin/python` 으로 넣었다(렌더 예시도 같은 인터프리터로 통일).

   **두 LOW 는 재진술이 아니라 재측정했다(2026-10-10)**: ① 0 바이트 저널 파일로 `render(cp3-setup-d-long, …)` 이
   **성공**한다 — 거부 0. ② LONG tenant 산출에 대해 `--check --out <dir>` 를 `--source` 없이 돌리면 **rc 1 ·
   문제 177줄**(`unexpected file: README.md` · `missing: strategies/bootproof_band.strategy.yaml` 등 상주 트리와의
   대조)이고, `--source config/tos_runtime/cp3-setup-d-long` 을 더하면 **rc 0 · `matches`** 다.
   - 선택 항목: §2.3 의 「`action_class` 0회 매칭」을 「매니페스트 순서상 첫 방향 슬롯(오늘은 OCP `DIRECTION` 축)」로
     정정했다 — PR-B 실측과 테스트가 단언하는 쪽이다.
3. **PR-C (부팅 증명 도구 + 실행 템플릿)**: §2.5 · §2.6. 첫 부팅 증명 실행은 스크래치 data dir 에서 1 세션, 기록은 런북
   §7.9 형식.
4. **실제 genesis**: ③ 생산자가 생긴 뒤 운영자 결정. 이 계획에서 하지 않는다.

## 6. 운영자 결정이 필요한 것

없다(설계 범위 안). 결정이 필요한 것은 모두 이 계획 밖이다: ③ 생산자 방식 · 첫 실제 genesis 시점 · tenant 의 cron 등록 ·
tenant data dir 을 콜드 백업 대상에 넣을지.

## 7. 커널·런타임 변경 0 확인

- 매니페스트는 렌더러(레거시 쪽 `scripts/`)만 읽는다. `RENDER.yaml` 은 `shutil.copytree`(`render_paper_config.py:1064`)가
  산출 dir 로 **그대로 복사하게 둔다**(리뷰 M2). v1 은 복사 뒤 지우자고 했는데, 그러면 `check()` 의 「원천에 있는데 산출에
  없는 파일」 검사에 걸린다(v1 이 이름 붙인 「추가 파일」 검사가 아니라). 런타임은 이 파일을 보지 않는다 — `_boot_integrity`
  는 이름 붙은 파일만 digest 하고, 로더의 stray-file 규칙은 `strategies/` 에만 걸리며, tenant 트리 루트에는 이미
  `README.md`·`strategy_bindings.yaml` 이 있다.
- `check()` 의 필수 생성 파일 목록(`_GENERATED_NAMES`, `:124`)은 지금 `bootproof_journal.jsonl` 을 포함해서 external 모드
  렌더마다 「render artifact missing」 을 낸다(리뷰 M2) → 필수 생성 파일을 매니페스트의 `journal.mode` 에서 정한다
  (synthetic = 저널 + `RENDERED.json`, external = `RENDERED.json` 만).
- YAML 별칭은 `yaml.safe_load` 가 이미 해석한다 — 로더 변경 없음.
- 따라서 `tos/src/tos/`·`tos/runtime/src/tos_runtime/` 0 바이트, `expected_code_digest` 재도출 없음. PR 마다 실측으로 확인한다.
