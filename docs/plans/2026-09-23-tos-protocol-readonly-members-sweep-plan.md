# tos Protocol 평범한 속성 → 읽기전용 멤버 스윕 (2026-09-23)

- 작성: 2026-09-23 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 측정 시점 main **`3d2ae6d3`**(PR #788 머지) ·
  mypy **2.3.1**(CI 핀) · 모의투자 운용 서버 루트 venv
- 상위: 핸드오프 `docs/runbooks/2026-09-23-tos-session-handoff-paper-server.md` §4.4 「커널 위생 부류 후속 후보」 ·
  3단계 계획 `docs/plans/2026-09-22-tos-test-tree-mypy-ratchet-stage3-plan.md` §7.2(#785 결함 1)·§7.3(CI 사각지대)
- 성격: **소형 스윕 하나 · PR 하나.** 3단계에서 **다섯 번** 나온 부류 — 「Protocol 의 평범한 속성 선언은 frozen 구현을
  거부한다」 — 를 `tos/src`·`tos/runtime/src` 의 Protocol **전수(75종 / 42파일)** 에 대해 한 번에 재고 처분한다.

## 0. 한 줄 요약

평범한(settable) 속성 멤버를 가진 Protocol 은 **7종 / 멤버 10개**다. 그중 **2종은 지금 구조적으로 깨져 있다** —
`_RecoveryVerdictLike.readiness_verdict` 의 유일 실 구현 `RecoveryVerdict` 가 `@dataclass(frozen=True)` 라서
`ComposedRuntime` 이 `_ComposedForDrill` 을 만족하지 못한다(#785 결함 1 과 같은 메커니즘). CI 가 조용한 이유는
`ComposeForDrill` 을 주는 유일한 호출부가 **애노테이션 없는 테스트 헬퍼**(`no-untyped-def` 유예 → 반환이 `Any`)라서다 —
3단계 §7.3 의 사각지대가 그대로 작동한 사례. 처분은 **열 멤버 전부 읽기전용 `@property`** 로(3-e 포트와 #785 의 하우스
스타일) + **두 갈래 핀 테스트**(mypy 적합성 함수 + 런타임 데이터 디스크립터 검사).

## 1. 실측 (2026-09-23, AST 스캔 + mypy 프로브)

스캔: `tos/src`·`tos/runtime/src` 의 `class X(Protocol)` 본문에서 `ClassVar` 가 아닌 `name: T` 애노테이션(= settable 멤버).

| # | Protocol | 파일:줄 | 평범한 멤버 | 실 구현 | 구조 적합 |
|---|---|---|---|---|---|
| 1 | `CanonicalizationScheme` (`@runtime_checkable`) | `tos/src/tos/canonical/canonicalization.py:62` | `version: str` (:70) | `EVL1ProvisionalCanonicalizer`(`self.version = …`, 가변 클래스) | ✓ |
| 2 | `SegmentCommitmentScheme` (`@runtime_checkable`) | `tos/src/tos/evidence/ledger.py:82` | `version: str` (:90) | `ProvisionalHashChainScheme` · `Sha256HmacChainScheme`(가변 클래스) | ✓ |
| 3 | `_AggregateRiskDecisionReader` | `tos/runtime/src/tos_runtime/compose/_dimension_readers.py:386` | `last_decision` (:392) | `RecordingAggregateRiskService`(가변) | ✓ |
| 4 | `_ConstructionStageReader` | `…/compose/_dimension_readers.py:440` | `construction` (:446) | `OrderConstructionStage`(가변, `self.construction = None`) | ✓ |
| 5 | `_ConstructionStageReader` | `…/compose/_venue_wiring.py:519` | `construction` (:528) | 같음 | ✓ |
| 6 | `_RecoveryVerdictLike` | `…/operations/backup_set.py:585` | `readiness_verdict` (:586) | **`RecoveryVerdict` — `@dataclass(frozen=True)`**(`recovery/barrier.py:206`) | **✗** |
| 7 | `_ComposedForDrill` | `…/operations/backup_set.py:589` | `evidence_store`·`inbox`·`emergency_log`·`recovery` (:594-597) | `ComposedRuntime`(`compose/_types.py:230`, 가변 dataclass) | **✗** — `recovery: RecoveryVerdict \| None` ≠ settable `_RecoveryVerdictLike \| None`(settable 멤버는 불변 일치를 요구) |

mypy 프로브(스크래치, 저장소 무변경 — `def p(x: <실구현>) -> <Protocol>: return x` 일곱 함수):

```text
probe.py:33: error: Incompatible return value type (got "RecoveryVerdict", expected "_RecoveryVerdictLike")  [return-value]
probe.py:33: note: Protocol member _RecoveryVerdictLike.readiness_verdict expected settable variable, got read-only attribute
probe.py:37: error: Incompatible return value type (got "ComposedRuntime", expected "_ComposedForDrill")  [return-value]
probe.py:37: note:     recovery: expected "_RecoveryVerdictLike | None", got "RecoveryVerdict | None"
Found 2 errors in 1 file
```

나머지 다섯(1~5)은 오늘 적합하지만, **frozen 구현(또는 frozen 테스트 더블)이 하나라도 들어오는 순간 6 과 같은 방식으로
깨진다.** 3단계가 도입한 3-e 포트(`_ContinuityIdentityLike` 등)는 처음부터 읽기전용 property 로 선언돼 이 부류 밖이다.

**열 멤버 중 Protocol 타입을 통해 대입하는 소비자는 0** (`grep -rn '\.(version|last_decision|construction|readiness_verdict|
evidence_store|inbox|emergency_log|recovery)\s*='` — 전부 실 구현의 `self.x = …` 또는 `ComposedRuntime`·서비스 인스턴스에
직접 대입, Protocol 참조를 거치지 않음). 읽기전용화가 컴파일을 깨는 곳은 없다.

**왜 CI 가 6·7 을 못 잡았나.** `restore_drill(compose: ComposeForDrill, …)` 의 유일 호출부는
`tos/runtime/tests/recovery/test_drill.py:555 _restore_drill_helpers` 의 내부 `def _compose_callable(data_dir,
environment_label)` — 애노테이션이 없어 `no-untyped-def` 유예 아래서 반환이 `Any` 다. 프로덕션 호출부는 없다
(`compose/cli.py:112` 문서 — 드릴 callable 은 호출자 공급). 즉 「소스 스텝이 잡는다」(3단계 §7.3)는 여기엔 적용되지
않는다 — `backup_set.py` 소스 스텝은 Protocol **정의**만 보고, 적합성은 **호출부** 타입에서만 검사되는데 그 호출부가 `Any` 다.

## 2. 처분 — 열 멤버 전부 읽기전용 `@property`

```python
class _RecoveryVerdictLike(Protocol):
    @property
    def readiness_verdict(self) -> ReadinessVerdict: ...
```

- 읽기전용 property 멤버는 **가변 속성·dataclass 필드·frozen dataclass 필드·pydantic frozen 필드·property** 전부가 만족한다.
  구현 집합이 넓어지고 소비자는 Protocol 을 통한 대입만 잃는다 — 그런 소비자는 0(§1).
- `@runtime_checkable`(1·2)은 `isinstance` 가 멤버 **존재**만 보므로 property 로 바꿔도 동작 동일. 커널 두 줄은
  #785 와 같은 성격의 **시그니처 축소 없는 위생 변경**이다(3단계 §7.2 「Protocol·커널 시그니처 확장 0」 유지 — 넓히는 게
  아니라 좁힌다).
- `_ComposedForDrill.recovery` 는 `_RecoveryVerdictLike | None` 그대로 — 6 이 property 가 되면 `RecoveryVerdict | None` 이
  공변으로 적합해진다(7 이 따로 고칠 것은 없고, 네 멤버를 property 로 바꾸는 것은 부류 처분).
- 7 종 전부 **독스트링에 「읽기전용 property — frozen 구현 허용, 이 계획」 한 줄**(3-e 포트 `_ContinuityIdentityLike`
  독스트링과 같은 형식).

### 하지 않는 것

- `no-untyped-def` 유예 해제나 `_compose_callable` 애노테이션 추가로 CI 가 잡게 만들기 — 유예는 상위 §6 ① 운영자
  결정이고, 이 계획은 핀 테스트로 같은 효과를 얻는다(§3). 다만 **`_compose_callable` 은 애노테이션을 단다** —
  그 자체가 「테스트 트리 mypy 가 실 적합성을 보게 하는」 가장 짧은 길이고, 3단계 D 레인이 더블에 한 것과 같다.
- Protocol 넓히기(`Optional` 화)·`# type: ignore`·`cast` — 전부 3단계 기각표와 같은 이유.
- 나머지 68 종 Protocol(메서드·property 만 가진 것) 접촉 없음. `pyproject.toml`·워크플로·`tos-gate.yml`·
  `tools/tos_entry_harness.sh` 무변경.

## 3. 핀 — 「이 가드가 실패하는 구체적 입력」

두 갈래. 하나만으로는 부족하다 — mypy 핀은 테스트 트리 mypy 가 꺼진 로컬에서 안 보이고, 런타임 핀은 타입 적합성을
직접 증명하지 못한다.

**(i) mypy 적합성 함수** — 테스트 트리 스텝(`--disable-error-code=no-untyped-def` 만)이 검사한다.

- `tos/runtime/tests/operations/test_protocol_readonly_members.py`(런타임 5·6·7 — 실 구현 + **frozen dataclass 더블** 각 1):
  `def _real(x: ComposedRuntime) -> _ComposedForDrill: return x` · `def _frozen(x: _FrozenDrillDouble) -> _ComposedForDrill: return x` 등.
- `tos/tests/canonical/test_protocol_readonly_members.py`(커널 1·2 — 실 구현 + frozen 더블). 커널 테스트는 `tos_runtime` 을
  import 하지 않는다(방화벽).
- `_compose_callable(data_dir: Path, environment_label: str) -> ComposedRuntime` 애노테이션 — 이제 `restore_drill(compose=…)`
  호출 자체가 적합성 검사 지점이 된다.

**(ii) 런타임 데이터 디스크립터 검사** — 같은 두 파일의 pytest 함수: 일곱 Protocol × 열 멤버에 대해
`inspect.isdatadescriptor(inspect.getattr_static(Proto, name))` 가 참. 평범한 애노테이션으로 되돌리면 클래스에 속성 자체가
없어(`__annotations__` 에만 존재) `AttributeError` → RED.

| 뮤테이션 | 기대 |
|---|---|
| ① `_RecoveryVerdictLike.readiness_verdict` 를 `readiness_verdict: ReadinessVerdict` 로 되돌림 | 테스트 트리 mypy RED **≥2**(`_real`·`_frozen` 둘 다 · `restore_drill(compose=…)` 호출부 포함) · pytest (ii) RED 1 |
| ② `_AggregateRiskDecisionReader.last_decision` 되돌림(오늘 적합한 부류) | mypy RED **1**(`_frozen` 만 — 실 구현은 가변이라 통과) · pytest (ii) RED 1 |
| ③ 커널 `CanonicalizationScheme.version` 되돌림 | 커널 테스트 트리 mypy RED 1(frozen 더블) · pytest (ii) RED 1 · `@runtime_checkable` isinstance 테스트는 **여전히 통과**(존재만 봄 — 이것이 런타임 검사로는 부족한 이유) |
| 대조군 | 처분 상태에서 커널/런타임 테스트 트리 mypy `Success` · 소스 스텝 0/0 · 두 핀 파일 pytest 전건 pass |

종료조건: 위 뮤테이션 ①②③ 전부 재현 + 대조군 + `tos/runtime/tests/recovery/test_drill.py` · `tos/runtime/tests/compose/`
· `tos/tests/canonical` · `tos/tests/evidence` pytest 전건 pass + 거버넌스(firewall · lint-imports · contract+self-test ·
completion · spec · size) 관례대로. 리뷰는 sonnet 레인(저자와 다른 패스) 판정 PR 코멘트 → `mergeStateStatus == CLEAN` → 머지.

## 4. 운영자 확인

없음 — 핸드오프 §4.4 가 후보로 등재한 위생 스윕이고 동작 불변·시그니처 축소 없음. 커널 두 줄(1·2)이 마음에 걸리면
그 두 줄만 빼고 머지할 수 있다(런타임 5 종만으로도 6·7 결함은 닫힌다).

## 5. 착지 기록

### 5.1 착지 — PR #790 (2026-09-23, base main `3d2ae6d3`)

§2 그대로: 7 개 Protocol(커널 2 · 런타임 5)의 평범한 멤버 10개를 읽기전용 `@property` 로 전환 + 각
Protocol 독스트링에 이 계획을 인용하는 한 줄 추가. `_compose_callable`(`tos/runtime/tests/recovery
/test_drill.py`)에 `data_dir: Path, environment_label: str) -> ComposedRuntime` 애노테이션. §3 그대로
핀 테스트 2 파일 신설.

**측정(재검증, `rm -rf .mypy_cache` 후, `PYTHONPATH=tos/src:tos/runtime/src`):**

| 검사 | 기대(계획 저작 시점) | 실측 |
|---|---|---|
| 커널 테스트 트리 | `Success … 580 source files`(579+1) | `Success: no issues found in 581 source files`(579+2 — 새 `tos/tests/canonical/__init__.py` 도 1 파일로 집계돼 예측보다 1 많음, 실코드 파일은 예측대로 1개) |
| 런타임 테스트 트리 | `Success … 222 source files`(221+1) | `Success: no issues found in 222 source files` |
| 커널 소스 스텝(`cd tos && mypy src`) | 0 / 264 | `Success: no issues found in 264 source files` |
| 런타임 소스 스텝(`mypy tos/runtime/src`) | 재현 안 되면 CI 위임 | **재현 안 됨** — 26 errors / 18 files, 전부 `no-any-return`(루트 venv 에 `tos`/`tos_runtime` editable 미설치 → 호출 반환이 `Any`). `git stash` 로 변경 전 트리에서 동일 명령 재실행 → **동일 26/18**(파일·건수·내용 100% 일치) 확인 — 내 변경과 무관한 기존 환경 한계. CI 위임(설치 없이, 지시대로 pip install/uninstall 안 함). |

**§3 뮤테이션(스크래치 카피, 저장소 무변경) — 전부 재현, 대조군 포함:**

| 뮤테이션 | 예측 | 실측 |
|---|---|---|
| ① `_RecoveryVerdictLike.readiness_verdict` 되돌림 | mypy RED ≥2 · pytest RED 1 | **mypy RED 3**(`_real_recovery_verdict`·`_real_composed_for_drill`·`_frozen_recovery_verdict` — 예측이 언급한 「`restore_drill(compose=…)` 호출부 포함」은 실측에서 재현 안 됨, §5.2 참조) · **pytest RED 1**(정확히 예측대로) |
| ② `_AggregateRiskDecisionReader.last_decision` 되돌림 | mypy RED 1(frozen 만) · pytest RED 1 | **정확히 예측대로**(mypy 1, pytest 1) |
| ③ 커널 `CanonicalizationScheme.version` 되돌림 | mypy RED 1 · pytest RED 1 · isinstance 테스트는 통과 | **정확히 예측대로**(mypy 1, pytest 1 failed + 2 passed = isinstance 둘 다 생존) |
| 대조군(처분 상태, 뮤테이션 없음) | 커널/런타임 테스트 트리 mypy `Success` | **확인됨**(위 표) |

### 5.2 계획 예측과 실측이 갈린 지점 2건 (기록용, 코드는 지시대로 최소 변경)

1. **`_compose_callable` 애노테이션만으로는 `restore_drill(compose=…)` 호출부가 실제 적합성 검사 지점이
   되지 않는다.** `_compose`(`test_compose_root.py`)가 자신의 반환 타입을 선언하지 않아 mypy 가 항상
   `Any` 로 본다 — `_compose_callable` 안에서 `runtime: ComposedRuntime = _compose(...)` 로 지역 변수
   애노테이션을 달아 **이 함수 자신의 선언된 반환 타입**(`no-any-return`)만 살렸다(지시된 시그니처·바디
   로직 불변, 한 줄에 타입만 붙임). 더 나아가 `_compose` 자체에 반환 애노테이션을 달아 봤더니
   (스크래치 실험, 커밋 안 함) `tos/runtime/tests` 전체에서 **140 개의 새 에러 / 15 개 파일**이 쏟아졌다
   — 수십 곳이 그동안 `Any` 뒤에 숨어 있던 `Optional` 미좁힘/타입 불일치였다. 이 스윕의 범위를 훨씬
   넘으므로 되돌렸다. 그리고 `_restore_drill_helpers`(바깥 함수) 자신도 무애노테이션이라 그 반환
   튜플이 호출부에서 `Any` 로 접힌다 — 즉 `restore_drill(compose=compose_callable, ...)` 호출 자체는
   여전히 검사되지 않는다. **탐지는 계획이 실제로 의도한 대로 핀 테스트(§3)가 담당**하고(뮤테이션 ①②③
   전부 그쪽에서 재현), `_compose_callable` 애노테이션은 부수적 위생 개선으로 남는다.
2. **`tos/tests/orthostate/test_orthostate_l2_fault.py` 의 `ST-07` 가드 인용 갱신(계획 범위 밖 1줄).**
   `canonicalization.py` 에 독스트링+property 6줄이 늘며 `if version is None or version not in
   _REGISTRY:` 가 255→261 로 밀렸다. 이 파일의 「인용 드리프트 방지」 가드가 정확히 이걸 잡아
   `pytest tos/tests` 전건 실행에서 FAILED 로 드러났다 — 줄 번호 한 곳만 갱신(문구·로직 불변). 같은
   패턴(`_GUARD_SITES`)을 쓰는 다른 두 파일(`test_spg_l2_fault.py`, `conftest.py`)은 이 스윕이 건드린
   5개 파일(`canonicalization.py`·`ledger.py`·`_dimension_readers.py`·`_venue_wiring.py`·
   `backup_set.py`) 중 어느 것도 인용하지 않아 추가 갱신 불필요.

**pytest:**

| 스위트 | 결과 |
|---|---|
| `tos/tests/canonical` + `test_canonicalization.py` + `-k evidence`(kernel) | 357 passed |
| `tos/runtime/tests/{recovery,compose,operations}` | 778 passed |
| `tos/tests`(kernel, 전건) | **9542 passed** |
| `tos/runtime/tests`(runtime, 전건) | **2628 passed**(무관한 기존 픽스처의 벤치나인 `BrokenPipeError` 트레이스백 1건 — `_fake_kis_server.py`, 배경 스레드의 소켓 종료 경합, exit 0·failed 0) |

**거버넌스:** firewall PASS · lint-imports 3 kept/0 broken · contract PASS + self-test PASS(뮤테이션
145종 전부 판별) · completion GREEN(violations=0) · spec PASS · size budget PASS(0 violations, 39
등록 예외). `black --check`/`ruff check` 전 터치 파일 통과.

리뷰는 sonnet 레인(저자와 다른 패스) PR 코멘트 → `mergeStateStatus == CLEAN` 대기 — 머지는 운영자
결정(§4 그대로, 운영자 확인 불필요이나 머지 자체는 명시 지시 시).
