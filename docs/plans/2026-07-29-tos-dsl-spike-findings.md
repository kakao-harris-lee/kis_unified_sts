# 작업 메모 — tos.dsl 실전략 de-risking 스파이크 실측 결과 (2026-07-29)

> **문서 성격 (규범성 선언)**: 본 문서는 **비규범 작업 메모**다. **비준 대상이 아니며**, GOV-001의 세
> 거버넌스 행위(비준 / ADR acceptance / live authorization) 중 어느 것도 수행하지 않는다. ADR·RFC·VER·
> register의 어떤 상태도 변경하지 않고, 어떤 EV 항목도 이동시키지 않는다. 유일한 산출은 **수직 슬라이스
> 스코핑 서베이(`2026-07-29-tos-engine-vertical-slice-scoping-survey.md`) §0 판정 3이 권고한 D-E1 착수 직전
> 스파이크의 실측 기록**이다. 스파이크는 repo를 일절 수정하지 않았고(스크립트는 세션 스크래치패드 휘발성),
> 판정 근거는 전부 repo file:line 인용으로 본 메모에 보존한다. 여기의 갭 소유 제안은 D-E1~D-E4 설계
> 문서의 입력물일 뿐 규범 판정이 아니다.

- **수행**: 2026-07-29, 세션 C 위임 스파이크 에이전트. `PYTHONPATH=tos/src .venv/bin/python`, exit 0.
- **베이스라인**: `pytest tos/tests/dsl -q` → 99 passed. repo 무수정(`git status --porcelain -- tos/src/tos/dsl
  tos/tests/dsl tos/src/tos/capsule` 공집합 확인).
- **저작 대상**: 단일 심볼 분봉 종가 밴드-리버전 전략 — `close < lower_band AND session == REGULAR →
  LONG/OPEN`; `close > upper_band → Explicit Flat`; else No-Action. 합성 5-bar 시퀀스 평가.

---

## 0. 표제 판정 — 서베이 전제 정정

**`tos.dsl`은 AST-only 패키지가 아니다. 작동하는 순수 evaluator가 이미 탑재되어 있고, 첫 시도에
end-to-end로 실제 아티팩트를 emit했다.** 갭은 algebra나 emit 경로가 아니라 전부 **경계**(시장 데이터가
evaluator에 도달하는 방법, 전략 admission)에 있다.

| 단계 | 결과 |
|---|---|
| 1. 실전략 저작 | **PASS** — `AuthoredStrategy` 발행 (`astrat-f1c1bd9c…c049`) |
| 2. Proposal emit | **PASS** — ACTION `prop-6f839fe4…6cc1` · FLAT `prop-8ad6cec5…99ea` · No-Action outcome |
| 3. evaluator 존재 판정 | **존재** (§1) |
| 4. escape-checker | **수제 미러에서 PASS** — `ADMISSIBLE`, 17 nodes; 저작 AST로부터의 직접 경로는 부재(G11) |
| 5. ADR-DEV-007 출력 의미론 | **전부 실재·전부 구조적** (§4) |

평가 outcome 시퀀스는 저작 의도와 정확히 일치: `[NoAction, Proposal(ACTION), NoAction, Proposal(FLAT),
NoAction]` — 하단 밴드를 뚫었지만 PRE_OPEN인 bar가 올바르게 억제됨.

## 1. evaluator 실재 (부재 아님 — negative-grep으로 반전 확인)

- `tos.dsl.vocabulary.evaluate_policy(policy, env) -> Decision` — vocabulary.py:384
- `tos.dsl.determinism.evaluate(strategy, capsule, config, *, scheme, enforcement_mechanism_version) ->
  EvaluationResult` — determinism.py:238
- `build_environment(capsule, config)` — determinism.py:88; 반환은 정확히 `{"capsule": …, "config": …}`
  (determinism.py:105-108)
- Decision→아티팩트 매핑 `_decision_to_outcome` — determinism.py:178
- **재현성 실증**: 동일 `(strategy, capsule, config)` → byte-identical Proposal(content-addressed).

**⇒ D-E1은 evaluator를 만들 필요가 없다. evaluator 주변의 오케스트레이션을 만들어야 한다.**

## 2. 갭 15건 (그룹·소유 제안)

### 그룹 A — 시장 데이터가 evaluator에 정당하게 도달할 수 없음 (D-E1/D-E2 최우선 입력)

| # | 갭 | 근거 |
|---|---|---|
| G6 | Capsule에 **수치 leaf 0개**. 가격 명칭 슬롯은 `price_and_order_constraints: tuple[str,…]`뿐이고 UNKNOWN으로 해소 | capsule.py:79; vocabulary.py:338-340 |
| G8 | Critical Input `Observation`은 **값을 싣지 않는다** — `raw.payload_digest` 포인터만. `FieldEvaluation`도 `worst_credible_bound: str \| None`뿐 | observation.py:70-74; field_evaluation.py:60 |
| G9 | Capsule은 `SnapshotRef`(id+digest)만 내장, snapshot body 미내장 → 실제 snapshot이 있어도 `capsule.critical_input_snapshot.observations`는 UNKNOWN | capsule.py:41-51; determinism.py:105-108 |
| G10 | 유일하게 작동하는 채널 = `config.bindings: dict[str, ScalarValue]` — **시장 데이터를 '설정'으로 재라벨링** | determinism.py:60 |
| G7 | 그 결과 `config_version`이 매 bar 바뀌어야 하고 replay signature가 오염됨 | determinism.py:59, 281 |

**규범 정합 문제이지 단순 배관 문제가 아니다**: RFC-008 §10:327-331 — "Any market datum … is Critical
Input… The DSL SHALL NOT let a strategy relabel a value as a 'feature,' 'signal,' or 'override' to escape
that governance." 스파이크 전략은 표현 가능했지만 **§10-conformant하지 않다** — 작동하는 유일한 채널이
§10이 금지하는 바로 그 재라벨링이다. **소유: 수정은 D-E2, 단 seam 계약(`build_environment`가 무엇을
소비하는가)은 D-E1이 먼저 확정해야 D-E2가 설계 가능.**

### 그룹 B — algebra 표현력 (낮춰야 했던 것)

| # | 갭 | 소유 제안 |
|---|---|---|
| G1 | 산술/집계 노드 부재. `ADMISSIBLE_KINDS` = const·context_ref·compare·rule·policy·target·propose_action·propose_flat·propose_vector·no_action (vocabulary.py:70-83). **이동평균·밴드 등 파생 지표를 DSL 내부에서 계산 불가** — 스파이크는 사전계산 밴드를 주입 | D-E2 (지표는 상류 Critical Input) |
| G3 | list/tuple leaf는 UNKNOWN으로 해소 — **bar 이력 접근 불가**, 사전-축약 스칼라만 (vocabulary.py:338-340) | D-E2 |
| G2 | `Rule`은 `all_of`(conjunction)만; OR/NOT 노드 부재. disjunction=순서 규칙 분리, negation=연산자 수동 반전 | 저작 관례; 확장 시 RFC-008 §14 |
| G4 | `TargetSpec` 전 필드가 리터럴 `str`, Operand 아님 (vocabulary.py:193-211). **AuthoredStrategy 1개 = 하드코딩 (account, instrument) 1쌍** — N심볼 유니버스에 N개의 content-addressed 전략 필요 | **D-E1** (이벤트 코어의 전략 디스패치 형태를 직접 결정) |
| G5 | `Proposal`에 **수치 필드 전무** — `quantity_basis: str \| None`(proposal.py:128), 수량·지정가 없음("evidence, never capacity", proposal.py:74-76) | D-E4 (Order Construction) |

### 그룹 C — 전략 admission / escape-checking

| # | 갭 | 근거 |
|---|---|---|
| G11 | `DecisionPolicy`/`AuthoredStrategy` → `CandidateProgram` 변환 함수가 **tos.dsl 어디에도 없음**(전 10모듈 반환 어노테이션 runtime negative-grep = NONE). 둘 다 `analyze()`에 넣으면 `AttributeError: no attribute 'nodes'`. checker 입력 도메인(candidate.py:110-150)과 저작 algebra(vocabulary.py:157-308)가 분리 | admissibility.py:108 |
| G12 | `AdmissibilityResult`는 `CandidateProgram`을 내장(evidence.py:95)하지만 **strategy_id/digest 바인딩 필드 부재** — 동일 policy의 퇴화 1-node `const` 미러도 ADMISSIBLE 반환됨을 실증(판정이 실평가 아티팩트에 귀속 불가) | evidence.py:95 |

**정직한 프레임**: 이는 결함이 아니라 설계다 — typed algebra는 구성상 admissible(candidate.py:1-20
"cannot express an escape attempt")이고, checker는 타입 시스템 **밖에서** 오는 후보용이다. 귀결은 **D-E1
스코핑 분기**: (i) 전략을 in-process typed `DecisionPolicy` 객체로만 수용 → checker 불요, G11/G12 무의미;
(ii) **직렬화/설정-저작 데이터**로 수용(repo의 설정 주도 원칙이 시사) → 파싱·candidate lowering·전략↔판정
바인딩(G12 부재분)을 D-E1이 소유. 설계 브리프에 이 분기를 명시할 것.

### 그룹 D — identity·replay·degraded 평가

| # | 갭 | 소유 제안 |
|---|---|---|
| G13 | per-bar 결정 identity가 **전적으로 Capsule digest 차이에 의존**. capsule에 필수 시간 필드 없음(`_REQUIRED_COVERED`가 `validity.issued_at` 미포함) → 같은 Snapshot digest를 공유하는 두 bar가 하나의 `proposal_id`로 붕괴 | D-E2(distinct digest 보장) + D-E1 |
| G14 | `bounds.select_outcome`은 호출자가 `on_exhaustion: Callable[[], NoActionOutcome]`을 공급해야 함(bounds.py:86) — DSL은 degraded outcome을 스스로 만들지 않음. **`evaluate()`는 bound 기계를 호출하지 않는다**(determinism.py에 resolve_bound/select_outcome/BoundState negative-grep, exit 1). bound→평가 배선 무주인 | **D-E1** |
| G15 | `DecisionKind` 4멤버(NO_ACTION·ACTION·FLAT·VECTOR)뿐 — WITHHOLD/DEGRADED/ERROR 부재. 호출자가 degradation을 NO_ACTION으로 접고 기록해야 함 | **D-E1** |

소소: `policy=None` 전략에 `evaluate()` 호출 시 bare `AttributeError`(determinism.py:268, `type: ignore`
경유) — fail-closed지만 비정형(패키지의 다른 가드는 `ArtifactIntegrityError`).

## 3. escape-checker·출력 의미론 실측

수제 미러(17 nodes): `verdict=ADMISSIBLE, reasons=()`. 사용한 `context_ref` 소스(`config`)는
`ADMISSIBLE_CONTEXT_SOURCES`(vocabulary.py:88) 소속. wildcard 스코프 미발동(`instrument="005930"`).

## 4. ADR-DEV-007 출력 의미론 — 전부 실재·구조적

| 개념 | 위치 |
|---|---|
| No-Action 일급 outcome | `DecisionKind.NO_ACTION` vocabulary.py:140; `NoActionOutcome` outcome.py:54 |
| Explicit Flat = *Proposal* | `DecisionKind.FLAT` vocabulary.py:142; `TargetKind.FLAT` vocabulary.py:134; `build_flat` proposal.py:244 |
| Flat ≠ No-Action 구조 분리 | `NoActionOutcome`은 `Proposal` 서브클래스 아님(runtime 확인); `FLAT_QUANTITY_BASIS = "ZERO_POSITION"` proposal.py:49 |
| Flat/action 강제(라벨 주장 아님) | proposal.py:157-175 — `FLAT` Proposal에 `quantity_basis="RISK"` 구성 시도가 runtime 거부됨 |
| Atomic Unit | `VectorInterdependence{ATOMIC, INDEPENDENT}` vocabulary.py:146; `resolve_vector_realization` outcome.py:238 |

## 5. D-E1 설계 브리프 지시 사항 (본 스파이크의 귀결)

1. **evaluator를 스코프하지 말 것.** 이미 출하되어 작동한다. 그 주변 오케스트레이션을 스코프하라.
2. **env-구성 계약이 D-E1의 첫 결정이고 D-E2를 블록한다.** 현재 `build_environment`는 Capsule+flat config
   dict를 읽고, Capsule은 시장 수치를 실을 수 없음이 실증됐다. `evaluate`의 환경 소스를 넓힐지 / D-E2가
   Capsule/Snapshot에 값 표면을 추가할지는 D-E1에서 확정해야 한다 — 아니면 D-E2가 RFC-008 §10 위반 seam에
   대고 설계하게 된다.
3. **G4가 디스패치 결정을 조기 강제한다.** 전략 1개 = 하드코딩 instrument 1개. 심볼별 전략 인스턴스화 vs
   instrument-키 레지스트리는 이벤트 코어 인터페이스 질문이지 후순위 세부가 아니다.
4. **G14/G15는 순수 D-E1 배관** — bounded-evaluation degrade 경로는 존재하되 전부 미배선.
5. **G11/G12는 조건부** — 전략이 직렬화 데이터로 도착할 때만 실작업이 된다. 분기를 설계 브리프에 명시.
