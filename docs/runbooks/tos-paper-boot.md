# TOS paper 첫 부팅 런북 — 렌더 → 부팅 → 정지 → 확인

- 대상: `tos_runtime` `run` 을 이 호스트의 배포 좌표로 부팅한다.
- 설계: `docs/plans/2026-09-23-tos-paper-coordinates-and-first-boot-design.md`
  (운영자 결정 1·3 · 운영자 선택 (가), 2026-09-23) · 상위 계획
  `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` §7.8.
- 실측 시점: 2026-09-23 (1차) · **2026-09-24 재측정/정정 (review-797 조치)**, main
  `b5bb5eb5` 기준 브랜치 `feat/tos-paper-render-and-first-boot`.

> ## ⛔ 이 런북은 아직 **끝까지 가지 못한다**
>
> §5 가 실측 상태를 이름으로 적는다. **②③은 운영자 결정·승인으로 2026-09-23 해소됐다.**
> 남은 것은 **①(정본 digest 가 프로세스마다 다르다)** — 이 절차 자체를 무효화하는 커널
> 결함이고, 그래서 §2 의 렌더는 **정상적으로 거부된다.** 그 거부를 우회하는 방법을 이
> 런북은 제공하지 않는다 — 그것이 정직한 상태다. ①이 닫히면 `run` 은 부팅한다(실측).
> 그 뒤에도 **틱은 ④(캘린더 만기 공백) 때문에 대부분의 날짜에 소비되지 않는다.**

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

```bash
DATA=~/.local/state/tos/paper-data          # 저장소 밖
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

## 5. 실측 차단 — 2026-09-23 현재 (이름으로)

### ① ⛔ `VenueConstraintPolicy.canonical_digest` 가 프로세스마다 다르다 (절차 자체의 결함)

렌더는 `print-policy-digests` 출력을 `safety_activation.yaml::members` 에 전사한 뒤,
**새 프로세스에서** 정책을 다시 로드해 그 digest 로 활성화를 재확인한다(부팅이 하는 일과
동형). 그 재확인이 거부한다:

```text
render_paper_config: refused — activation read-back refused — the rendered members block
is not activated (exit 1):
tos_runtime.venue.activation.PolicyNotActivated: activation refused for
kind=<BundleMemberKind.VENUE_CONSTRAINT_POLICY: 'VENUE_CONSTRAINT_POLICY'>
member_id='vcp-paper-krx-index-futures' generation=1 digest='<A>':
members[0]: digest '<B>' != '<A>'
```

원인(실측):

| 지점 | 사실 |
|---|---|
| `tos/src/tos/venue/records.py:406-416` | `VenueConstraintPolicy._COVERED_FIELDS` 에 `required_constraint_classes`·`shape_constraints` 포함 |
| `tos/src/tos/venue/records.py:425` · `:165-168` | 그 둘이 `frozenset[ConstraintClass]` · `allowed_order_types`/`allowed_tifs`/`allowed_sides`/`allowed_position_effects` (전부 frozenset). (`:424` 는 그 필드가 아니라 바로 위 `#:` 주석 줄이다 — review-797 LOW-2 정정) |
| `tos/src/tos/canonical/_base.py:187` | `covered_content()` = `model_dump(mode="json", …)` → frozenset 이 **집합 순회 순서 그대로의 리스트**가 된다 |
| `tos/src/tos/canonical/canonicalization.py:148-149,174-176` | `_encode` 는 시퀀스를 **순서 유의미**로 취급한다("sequence order is preserved (vectors are order-significant)") |
| `tos/src/tos/venue/vocabulary.py:169` | `ConstraintClass` 는 `StrEnum` → 순회 순서가 프로세스별 문자열 해시 시드를 따른다 |

즉 **「`print-policy-digests` 를 돌려 digest 를 `members` 에 옮겨 적는다」는 문서화된 운영자
절차가 성립하지 않는다.** 기존 테스트가 전부 **한 프로세스 안에서** 계산·검증해서
드러나지 않았다(`tests/compose/test_deploy_policies.py::_install_real_policies` 주석:
"the `print-policy-digests` step, done **in-process**").

**범위 — 이것은 한 모델의 문제가 아니라 부류다**(2026-09-24 실측, review-797 MEDIUM-3):

| 수 | 무엇 |
|---|---|
| **120** | `_COVERED_FIELDS` 를 가진 정본 모델 전체 |
| **19** | covered content 에 `set`/`frozenset` 을 가진 모델(중첩 포함) |
| **6** | 그중 **이미 정렬한다** — `covered_content()` 를 오버라이드한다. `tos/src/tos/cur/records.py:44-49` 가 이유를 그대로 적는다: 「`model_dump(mode="json")` 가 frozenset 을 **순서 없는** 리스트로 만들고 정본화기는 시퀀스 순서를 보존하므로 `covered_content` 가 각 집합 필드를 **정렬**해 프로세스 간 결정적이 되게 한다」(설계 #23 §3.1). `cur`/`wdr`/`sir`/`rlp` 계열 |
| **13** | 정렬하지 않는다 = digest 가 프로세스 의존. `brokercap.BrokerCapabilityProfile` · `hag` 4종 · `liveauth` 2종 · `sbr` 3종 · `posttrade.StatementCoverageManifest` · `venue.OrderAdmissibilityDecision` · **`venue.VenueConstraintPolicy`** |

이 배포가 오늘 digest 를 계산하는 13종은 `VenueConstraintPolicy` 하나뿐이다. 찍히는 나머지
네 종류(OCP/ARE/AFG/CIP)는 covered 필드에 집합이 **아예 없어** 안정적이다 — 그것은 찍히는
다섯 종류에 대한 진술이지 커널 전체에 대한 진술이 아니다.

⚠ **고치는 사람을 위한 주의**: `CurrentnessPolicy.required_dimensions` 는 타입만 보면
영향권처럼 보이고 이 배포도 그 값을 채택했지만(`currentness.yaml`, PR #794), **정렬하는
6종에 속한다** — 해시 시드 6개로 digest 불변을 실측했다. 타입 스캔만으로는 과대 보고된다.
**수정 패턴은 커널에 이미 있다**(위 `cur` 오버라이드).

**처분: 이 아크의 설계 범위 밖이다.** 정본 직렬화의 의미를 바꾸는 것은 구현이 아니라
설계 PR 이다. `tests/unit/scripts/test_render_paper_config.py::
test_venue_policy_canonical_digest_is_not_reproducible_across_processes` 가 이 사실을
**결정적으로** 고정한다(해시 시드 두 값이 서로 다른 digest 를 낸다). 고쳐지면 그 테스트가
RED 가 되고, 그때 같은 파일의 `pinned_hash_seed` 픽스처를 지우는 것이 수용 기준이다.
`PYTHONHASHSEED` 를 맞춰 통과시키는 것은 **진단이지 절차가 아니다.**

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

### ④ 틱은 세션/만기 게이트에 막힌다 (값 문제 아님)

①②③을 진단 목적으로 통과시키면 `run` 은 **부팅하고 `run_forever` 에 들어가 SIGTERM 에
정상 종료(코드 0)** 한다. 그래도 틱은 소비되지 않는다:

```text
session_context: ... phase='EXPIRED' is_open=False ...
TICK OUTCOME: SKIPPED_SESSION_CLOSED
```

- `decide_tick` 1순위 게이트(`marketfeed/scheduler.py` — 세션이 닫혀 있으면
  `SKIPPED_SESSION_CLOSED`).
- `config/tos_runtime/paper/calendar.yaml:36-40` — `krx-index-futures` 는
  CONTINUOUS **08:45–15:45 KST MON–FRI**, 그리고 `futures_expiry` 가 **3/6/9/12월 둘째 목요일
  이후 클래스 전체를 `EXPIRED`** 로 만든다(클래스 단위 규칙 — `venue_constraint_policy.yaml:71`
  이 "class-level, plan §5 이월" 이라고 적는다).
- 2026-09-23 은 9월 만기(09-10) 이후라 **시각과 무관하게 EXPIRED** 다. 같은 렌더 산출물을
  만기 이전 장중 시각으로 구동하면 `TICKED` 되고 스냅샷이 남는다(아래 확인 절차).

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
