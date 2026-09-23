# TOS paper 첫 부팅 런북 — 렌더 → 부팅 → 정지 → 확인

- 대상: `tos_runtime` `run` 을 이 호스트의 배포 좌표로 부팅한다.
- 설계: `docs/plans/2026-09-23-tos-paper-coordinates-and-first-boot-design.md`
  (운영자 결정 1·3 · 운영자 선택 (가), 2026-09-23) · 상위 계획
  `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` §7.8.
- 실측 시점: 2026-09-23, main `b5bb5eb5` 기준 브랜치 `feat/tos-paper-render-and-first-boot`.

> ## ⛔ 이 런북은 아직 **끝까지 가지 못한다**
>
> 아래 §5 가 실측 차단 3건을 이름으로 적는다. **①은 이 절차 자체를 무효화하는 결함이고,
> ②③은 값/승인 문제다.** §2~§4 의 명령은 정확하고 재현 가능하지만, ① 때문에 §3 의
> 렌더는 **정상적으로 거부된다.** 그 거부를 우회하는 방법을 이 런북은 제공하지 않는다 —
> 그것이 정직한 상태다.

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
  `account_fingerprint`(`tools/broker_probes/common.py` 와 같은 salt-free SHA-256 상위 12자)만.
- 저널(`bootproof_journal.jsonl`)은 **렌더 시점에 생성**되고 관측 시각이 그때로 고정된다.
  → **부팅 직전에 렌더한다.** 오래된 렌더로 부팅하면 신선도 한도를 넘겨 값이 UNKNOWN 이 된다.

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
| `tos/src/tos/venue/records.py:424` · `:165-168` | 그 둘이 `frozenset[ConstraintClass]` · `allowed_order_types`/`allowed_tifs`/`allowed_sides`/`allowed_position_effects` (전부 frozenset) |
| `tos/src/tos/canonical/_base.py:187` | `covered_content()` = `model_dump(mode="json", …)` → frozenset 이 **집합 순회 순서 그대로의 리스트**가 된다 |
| `tos/src/tos/canonical/canonicalization.py:148-149,174-176` | `_encode` 는 시퀀스를 **순서 유의미**로 취급한다("sequence order is preserved (vectors are order-significant)") |
| `tos/src/tos/venue/vocabulary.py:169` | `ConstraintClass` 는 `StrEnum` → 순회 순서가 프로세스별 문자열 해시 시드를 따른다 |

즉 **「`print-policy-digests` 를 돌려 digest 를 `members` 에 옮겨 적는다」는 문서화된 운영자
절차가 이 한 종류에서는 성립하지 않는다.** 나머지 네 종류(OCP/ARE/AFG/CIP)는 covered
필드에 집합이 없어 안정적이다. 기존 테스트가 전부 **한 프로세스 안에서** 계산·검증해서
드러나지 않았다(`tests/compose/test_deploy_policies.py::_install_real_policies` 주석:
"the `print-policy-digests` step, done **in-process**").

**처분: 이 아크의 설계 범위 밖이다.** 정본 직렬화의 의미를 바꾸는 것은 구현이 아니라
설계 PR 이다. `tests/unit/scripts/test_render_paper_config.py::
test_venue_policy_canonical_digest_is_not_reproducible_across_processes` 가 이 사실을
**결정적으로** 고정한다(해시 시드 두 값이 서로 다른 digest 를 낸다). 고쳐지면 그 테스트가
RED 가 되고, 그때 같은 파일의 `pinned_hash_seed` 픽스처를 지우는 것이 수용 기준이다.
`PYTHONHASHSEED` 를 맞춰 통과시키는 것은 **진단이지 절차가 아니다.**

### ② `scope.environments: ["paper"]` vs `--environment-label non-live-test`

```text
run: refused — compose_paper_runtime raised VenuePolicyScopeMismatch:
venue policy scope.environment 'paper' != this compose root's environment_label 'non-live-test'
```

- 파일: `config/tos_runtime/paper/venue_constraint_policy.yaml:55` (`environments: ["paper"]`)
  · 대조: `tos_runtime/compose/_venue_wiring.py` `_cross_check_scope`.
- 설계 §2 의 부팅 예시가 쓰는 라벨은 `non-live-test` 인데, 채택된 정책 문서가 선언한
  환경은 `paper` 다. 위 §1·§3 이 `LABEL=paper` 를 쓰는 이유다.
- ⚠ 다만 `paper` 는 `tos_runtime/compose/cli.py:215` 의 `_LIVE_ENVIRONMENT_LABELS`
  (`{"paper","restricted-live","production"}`)에 들어 있다 — `restore-drill` 은 그 라벨을
  거부한다(`cli.py:816`). `run` 에는 그 검사가 걸려 있지 않지만, **어느 라벨로 부팅할지는
  운영자 결정 사항**이다. 이 런북은 둘 중 하나를 고르지 않고 불일치를 지목한다.

### ③ `safety_envelope.yaml::governed_dimensions: []`

```text
run: refused — compose_paper_runtime raised RiskPolicyScopeMismatch: aggregate risk policy
governs dimension id(s) ['INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL'] that the Hard Safety
Envelope's own governed_dimensions [] does not declare — every ARE-governed dimension must
have a real envelope ceiling
```

- 파일: `config/tos_runtime/paper/safety_envelope.yaml` (`governed_dimensions: []`) ·
  요구: `config/tos_runtime/paper/aggregate_risk_policy.yaml:74`
  ("HSE must govern INSTRUMENT::LONG_SHORT_DELTA_DIRECTIONAL with envelope_max ≥ 1").
- **의도된 상태다.** 그 봉투 파일 자신의 헤더가 「그 차원의 구체적 한도는 제안표에 행이
  없다(승인 대상이 아니라 **별도 안전 승인 사안**) … 그래서 그 경로는 보수적으로 막힌다」
  라고 적는다. 안전 한도이므로 **이 아크에서 채우지 않는다.**

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

## 6. 정리

- 렌더 산출물(`~/.config/tos/paper-config*`)과 커스터디 루트는 **계좌 좌표/자격증명**을
  담는다. 저장소 밖에 두고, 공유하지 않는다.
- 렌더는 저장소에 아무것도 남기지 않는다 —
  `tests/unit/scripts/test_render_paper_config.py::test_guard_render_leaves_the_repository_byte_identical`
  이 임시 `git clone` 안에서 실제 CLI 를 돌려 `git status --porcelain --ignored` 불변을 단정한다.
