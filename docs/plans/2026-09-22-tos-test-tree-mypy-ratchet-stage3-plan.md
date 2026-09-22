# tos 테스트 트리 mypy 래칫 3단계 — `arg-type` 773 계획

- 작성: 2026-09-22 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · fact-check 1라운드 반영(§7.0)
- 상위 계획: `docs/plans/2026-09-18-tos-test-tree-mypy-ratchet-plan.md` §3.3(성격 규정) ·
  §6 처분 ④(「2단계가 끝난 뒤 별도 계획을 쓴다」) · §7.5(3단계 입력 수치와 **「분류기를 먼저
  검증해라」** 지시)
- 측정 시점: main `29f39fe6` (PR #770 머지 직후) · mypy **2.3.1**(CI 핀과 동일) · 두 트리 별도
  실행(합치면 `Duplicate module` — 상위 §7.1 함정)
- 대상: CI `tos-firewall` 의 두 스텝 `mypy (tos kernel tests)` · `mypy (tos runtime tests)` 에
  남은 유예 3종(`arg-type` · `no-untyped-def` · `unused-ignore`) 중 **`arg-type` 하나**.
  `no-untyped-def` 는 상위 §6 ①로 **하지 않는다**. `unused-ignore` 는 상위 §3.4 대로
  **이 단계가 끝난 뒤** 잰다.

## 0. 분류기를 먼저 검증했다 — 이 계획의 축

상위 §7.5 는 3단계 계획에 두 가지를 못박았다: 「이 숫자를 그대로 인용하지 말고 목적에 맞는
분할을 다시 정의해라」 · 「분류기를 먼저 검증해라 — 저자가 여기서 그러지 않아 틀렸다」. 2단계
착지 기록의 저자 오류 14건 중 14번(§7.6)이 정확히 그 부류였다 — 분류기가 리터럴 `"None"` 만
잡아 유니온을 통째로 놓쳤고, 그 한계를 「데이터에 형상이 없다」로 읽었다.

그래서 이 계획은 분류기를 **먼저** 만들고 검증한 뒤 수치를 읽었다. 그리고 **그 검증도 두 번
틀렸다** — 저자가 잡은 결함 2건에 더해 fact-check 가 **2건을 더** 잡았다(§0.1 표의 아래 두
행). 「분류기를 검증했다」는 문장 자체가 검증 대상이었다.

### 0.1 분류기 검증 — 결함 4건 (저자 2 · 리뷰 2)

| 결함 | 누가 | 실측 |
|---|---|---|
| 초판 정규식이 **피호출자가 없는 형상**(`Argument N has incompatible type ...`, positional 호출에 mypy 가 callee 를 안 붙임)을 못 읽음 | 저자 | **27건** 미파싱 → 고친 뒤 773/773 |
| 더블을 **이름 패턴**(`_Stub*`/`_Fake*`/`_Mutable*`)으로 판정 — 상위 계획의 26건 | 저자 | **「실제 타입에 등장하는 이름이 테스트 트리에 `class` 로 정의돼 있는가」** 로 바꾸니 87. `_Request`·`_FixedKeyProvider`·`_TrustedTimeService`·`_NullEvidence` 가 빠져 있었다. 상위 계획의 「더블 3%」는 **분류기 결함이지 데이터 성질이 아니었다** |
| 그 `class` 정의 grep 이 **`^class` 로 줄 시작에 앵커**돼 있어 함수 안에 들여쓰기로 정의된 더블을 놓침 | **review-775 HIGH** | `tos/runtime/tests/recovery/test_reconciliation.py:285` 의 `    class _FakeRclReader:` 등 **3건**이 Z 로 오분류. `^\s*class` 로 넓히니 D **87 → 90**, Z **44 → 41** |
| 같은 grep 이 산문의 `class of bug` 도 잡아 허구 식별자 `of` 가 클래스 집합에 섞임 | **review-775 MEDIUM** | 이번 773 건엔 영향 0(실제 타입에 `of` 토큰 없음). 패턴 끝에 `\s*[:(]` 를 붙여 닫음 — `of` 없음. 집합 크기는 **불변식이 아니라 관측치**다(저자 실행 206 · 재심의 깨끗한 체크아웃 204 · `sed` 방언에 따라 207) — 부록 A 는 크기를 단언하지 않고 출력만 한다 |
| 부록 A 전사에서 **따옴표 제거 줄이 빠짐** — 문서의 코드를 그대로 돌리면 773 중 686 이 Z 로 떨어진다 | **review-775 HIGH** | 저자 스크립트엔 있었고 **문서에 옮길 때 빠졌다.** 부록 A 에 복원 |

파서와 규칙은 부록 A 에 있다. 누구든 같은 명령으로 같은 수치를 얻어야 하고, 얻지 못하면 이
계획이 아니라 분류기가 틀린 것이다 — **fact-check 가 그 기준을 실제로 적용했고 부록 A 가 그
기준에 미달했었다.**

### 0.2 라벨 실측 (겹침 허용, 773건 · 결함 4건 수리 후)

| 라벨 | 규칙 | 건수 |
|---|---|---:|
| **A** kwargs 언패킹 | 실제 타입이 `**` 로 시작 | **443** |
| **B** 실제형이 옵셔널 | 실제 타입에 `None` 항이 있고 기대 타입에는 없다 | 107 (그중 리터럴 `None` 29) |
| **C** 기대형만 옵셔널 | 기대 타입에 `None` 항이 있고 실제 타입에는 없다 | 253 |
| **D** 더블 | 실제 타입의 식별자 중 하나가 테스트 트리에 정의된 클래스 | **90** |
| **E** `object` | 실제 타입이 정확히 `object` | 66 |
| **Z** 그 밖 | 위 어느 것도 아님 | **41** |

**C 253 중 193 은 A 와 겹친다** — `**dict[str, object]` 를 `X | None` 파라미터에 스플랫한
것이라 A 의 처방으로 닫힌다. 상위 §7.5 의 「기대 타입만 옵셔널 51건」은 이 겹침을 A 에 우선
배정한 뒤의 잔여였다. **C 는 독립 부류가 아니라 대부분 A 의 그림자다.**

### 0.3 배타 분할 — 처방이 같은 것끼리

분할 축은 **처방**이다. 같은 처방으로 닫히는 것을 한 부류로 묶고, 겹치면 **더 근본적인
처방 쪽**에 둔다(A 는 빌더 관용구를 바꾸면 C 도 사라지므로 A 가 우선). 우선순위는
A > D > B > E > C′ > Z 이고 부록 A 의 `bucket()` 이 그대로다.

| 부류 | 배타 건수 | 비율 | 처방(§1) |
|---|---:|---:|---|
| **A** kwargs 언패킹 (C 겹침 193 포함) | **443** | 57% | 빌더 관용구 교체 — §1.1 |
| **B** 실제형 옵셔널 미좁힘 | 107 | 14% | 2단계 처방(좁히기·ISSUED 접근자) — §1.2 |
| **D** 더블 계약 미충족 (C 겹침 12 포함) | **90** | 12% | 더블을 계약에 맞춘다 — §1.3 |
| **E** `object` 산출자 (C 겹침 22 포함) | 66 | 9% | 산출자 애노테이션 교정 — §1.4 |
| **C′** 기대형만 옵셔널, 실제형이 다른 구체 타입 | 26 | 3% | 개별 판단 — §1.5 |
| **Z** 그 밖 | **41** | 5% | dict 불변성 21 + 개별 — §1.5 |
| 합 | **773** | 100% | |

상위 §7.5 의 분할(446 · 110 · 51 · 140 · 26)과 A·B 는 근사 일치하고, **D 가 26 → 90 로
3.5배**, 「단일 형상 없음」 140 이 **41 로 준다.** 잔여가 준 것은 형상이 생겨서가 아니라
**더블 판정 기준을 바꿨기 때문**이다 — 이번에도 분류기가 수치를 바꿨고, **한 번 더 바뀌었다**
(87 → 90, 리뷰의 앵커 지적).

### 0.4 집중도 — 근본은 몇 곳인가

2단계의 교훈(상위 §7.7 ①)대로 **피호출자로 묶어** 봤다. A 443 건의 피호출자 정의 위치를
전수 조회한 결과(부록 A `definition_of`):

| A 의 피호출자 | 건 | 정의 |
|---|---:|---|
| `CapabilityTuple` | 70 | `tos/src/tos/brokercap/routing.py:175` — `FrozenModel` |
| `degraded_lease_invalidated` | 56 | `tos/src/tos/authority/predicates.py:626` — 키워드 전용 파라미터 함수 |
| `endpoint_binding_from_profile_ok` | 28 | `tos/src/tos/brokercap/routing.py:429` — 함수 |
| `issue` of `DigestBoundArtifact` | 22 | `tos/src/tos/canonical/_base.py:226,301` — `(cls, *, scheme, status=ISSUED, **content: Any)` |
| `model_construct` of `BaseModel` | 20 | pydantic — `(_fields_set=None, **values: Any)` |
| `clean_request` | 18 | 테스트 헬퍼 3벌(`_wdr_strategies.py:118` · `_egress_strategies.py:138` · `_hag_strategies.py:157`) |
| `compute_replay_result` | 14 | `tos/src/tos/evidence/replay.py:60` — 함수 |
| `CompositeState` | 14 | `tos/src/tos/orthostate/records.py:39` — `IndependentIdArtifact` |
| `risk_decision` | 13 | `tos/src/tos/are/predicates.py:647` — 함수 |
| `EgressResultPayload` | 10 | `tos/src/tos/engine/records.py:214` — `FrozenModel` |
| `cancellation_admissible` · `partition_lease_admissible` | 18 | `tos/src/tos/protective/predicates.py:523,460` — 함수 |
| 나머지 55 피호출자 | 160 | pydantic 모델 39종 · 런타임 dataclass 8종 · 테스트 헬퍼 8종 |

**한 파일이 96건**(`tos/tests/brokercap/test_brokercap_routing.py` — `CapabilityTuple` 65 +
`endpoint_binding_from_profile_ok` 28 + 3 · **96 전건이 A**). 상위 12 피호출자가 **283건
(64%)** 이다.

A 의 뿌리 관용구는 하나다:

```python
# tos/tests/sir/_sir_strategies.py:82 — 같은 모양이 테스트 트리 전반에 있다
def clean_signal(**overrides: object) -> SafetySignal:
    kwargs: dict[str, object] = {"signal_id": "sig-1", ...}
    kwargs.update(overrides)
    return SafetySignal(**kwargs)          # ← arg-type: **dict[str, object] 는 어떤 파라미터에도 안 맞는다
```

`tos/tests/brokercap/test_brokercap_routing.py:103` 의 `_base_kwargs(**overrides: object) ->
dict[str, object]` 도 같은 모양이고, `:134` 의 `CapabilityTuple(**_base_kwargs(**{axis: None}))`
처럼 **불법 값을 일부러 넣어 seal 을 발화시키는** 용법이 함께 있다(그 호출은 이미
`pytest.raises(pydantic.ValidationError)` 안에 있다 — `:126-134`). 이 용법이 처방을 제약한다 —
**빌더는 불법 입력을 통과시킬 수 있어야 한다**(테스트가 검증 실패를 관측하는 것이 목적).

## 1. 처방 — 부류별

세 가지를 먼저 못박는다(상위 §3.3 의 세 항을 승계하고 하나를 더한다).

- **Protocol · 커널 시그니처를 넓히지 않는다.** `**kwargs: Any` 로 파라미터를 지우거나
  `X | None` 을 `object` 로 바꿔 green 을 얻지 않는다. 프로덕션 타입 안전성을 테스트 편의로
  파는 것이다.
- **`dict[str, Any]` 일괄 치환은 처방이 아니다.** 스플랫 지점마다 `Any` 를 박으면 773 이
  0 이 되지만 mypy 가 그 호출을 **영원히 안 본다** — 유예를 코드 안으로 옮긴 것이다.
  `Any` 는 「이 값은 검증기(pydantic)가 받는다」처럼 **의미가 있는 자리에만** 쓴다(§1.1 A-pyd).
- **`# type: ignore[arg-type]` 를 새로 추가하지 않는다.** 래칫이 거꾸로 돈다.
- **한 PR 로 하지 않는다**(§2).

### 1.1 A — kwargs 언패킹 443

피호출자 종류가 처방을 가른다. **인스턴스(호출부)가 아니라 빌더(산출자)를 고친다** — 빌더
하나가 호출부 수십을 닫는다(2단계 ②의 `Self` 3줄과 같은 부류).

**A-pyd — pydantic 모델 생성자 (`CapabilityTuple` 70 · `CompositeState` 14 ·
`EgressResultPayload` 10 · sir/wdr/rlp/failuredomain `state.py`·`records.py` 모델 39종 …
≈ 210건).** 빌더가 dict 를 스플랫하는 대신 **`Model.model_validate({**base, **overrides})`**
로 만든다. `model_validate(obj: Any)` 라 mypy 가 통과하고, **검증을 그대로 탄다** — 불법
override 로 seal 을 발화시키는 테스트 의도가 보존된다. `model_copy(update=)` 는 **검증을
건너뛰므로 금지**(불법 값이 조용히 들어간다 — 정확히 테스트가 잡으려는 것을 못 잡게 된다).
빌더의 반환형은 그대로 모델이고, 호출부는 한 줄도 안 바뀐다. (fact-check 가 pydantic
2.12.5 에서 셋 다 실측했다: `model_validate` 는 `ValidationError` 를 낸다 · `model_copy(
update=)` 는 잘못된 타입을 조용히 넣는다 · `dict[str, object]` 입력의 `model_validate` 는
mypy 를 통과한다.)

`model_construct` 20건은 별개다 — `model_construct(_fields_set: set[str] | None = None,
**values: Any)` 의 **첫 파라미터에 dict 값이 바인딩될 수 있다**는 지적이다. 이것은 「검증을
건너뛰고 만든다」는 의도가 이미 명시된 자리라, `model_construct(**typed)` 로 만드는 대신
**표본 1건으로 먼저 처방을 확정**한다(§3 ③). 후보: 값 dict 를 `dict[str, Any]` 로 두는 것
(이 자리의 `Any` 는 「검증 없이 받는다」는 의미가 있다).

**A-fn — 커널 술어 함수 (`degraded_lease_invalidated` 56 · `endpoint_binding_from_profile_ok`
28 · `compute_replay_result` 14 · `risk_decision` 13 · `cancellation_admissible` 9 ·
`partition_lease_admissible` 9 · `analyze_candidate` 8 = 137건).** 키워드 전용 파라미터가
**명시된** 함수에 `dict[str, object]` 를 스플랫한다. 처방은 **테스트 측 `TypedDict` 하나**
(`total=True`, 함수 시그니처와 1:1) 를 헬퍼 옆에 두고, `valid_lease_kwargs()` 같은 빌더가
그 TypedDict 를 반환하게 한다 — `**TypedDict` 는 mypy 가 **키·타입을 정밀 검사**한다(누락
키·타입 불일치 둘 다 `[typeddict-item]` — fact-check 실측). 즉 유예를 걷는 것을 넘어 **빌더와
시그니처의 드리프트를 mypy 가 잡게 된다**(지금은 아무도 안 잡는다).

TypedDict 로 표현 못 하는 케이스가 둘 있고, 둘 다 **스플랫을 버리고 명시 호출**로 푼다:

1. **불법 값 주입**(`{axis: None}` 처럼 시그니처 밖의 타입) — 그 케이스만 키워드를 직접
   써서 호출한다. 그 호출은 이미 `pytest.raises` 안에 있으므로(`test_brokercap_routing.py:
   126-134`) 새로 필요한 것은 불법 값에 **`cast`** 를 붙여 「이 줄은 타입을 어긴다」를 코드에
   남기는 것뿐이다. `# type: ignore[arg-type]` 가 아니다.
2. **부분 override**(TypedDict 의 일부 키만 바꾸는 헬퍼) — `TypedDict` 는 `total=False`
   보조 타입 + `{**base, **partial}` 로 표현 가능하다. 그래도 안 되면 그 헬퍼만 명시 키워드.

**A-issue — `issue(**content: Any)` 22건.** `**content` 가 `Any` 인데 걸리는 이유는 dict 에
**`scheme`·`status` 가 섞여 들어가** 그 두 파라미터에 `object` 가 바인딩되기 때문이다. 처방:
빌더에서 `scheme=SCHEME` 를 **dict 밖으로 빼서 명시 키워드**로 넘긴다. 한 줄 이동이 22건.

**A-rt — 런타임 dataclass/클래스 (`FileCustody` 6 · `KisMockTransportConfig` 6 ·
`OperatorProjection` 4 · `TrustworthyTimeConfig` 4 · `ConstructionConfig` 4 ·
`WitnessOrder` 3 · `EgressReceiptObservation` 4 …) 와 테스트 헬퍼 (`clean_request` 18 ·
`build_core` · `ocp_yaml` 4 · `clean_policy` 2 …).** A-fn 과 같은 TypedDict 처방. 헬퍼 3벌
(`clean_request`)은 **그대로 3벌**로 둔다 — 이 단계는 에러 코드 하나를 닫는 것이고, 중복
제거는 다른 단계다(2단계 `_import_closure.py` 37벌과 같은 처분).

### 1.2 B — 실제형 옵셔널 미좁힘 107

| 형상 | 건 | 어디서 오나 |
|---|---:|---|
| `int | None → int` | 41 | `receipt.seq`·`tip().seq`·`generation` 계열이 Optional — `expected_seq` 인자(`append_cas` 6 · `apply_reservation_transition` 7 · `mark_handling_started` 12 · `mark_consumed` 6) |
| `None → StageRequest` | 23 | `tos/runtime/tests/compose/test_rcl_tip_generation_provider.py:58` 등 — `provider(None)` : 「provider 는 request 를 읽지 않는다」를 **`None` 을 넘겨서** 증명 |
| `str | None → str` | 17 | `snapshot_consumer_binding_ok` 11 · `write_approval_file` 2 · `clean_attestation` 2 · `FinalityProofRef` 1 · `derive_id` 1 |
| `Path | None → Path` | 7 | `load_instance_document` 7 (`tos/runtime/tests/brokercap/test_derive.py` 5 · `test_exit_conditions.py` 2) |
| `DimensionKey | None` 8 · 그 밖 11 | 19 | 개별 |

(초판은 `load_instance_document` 7 을 `str | None` 행에 넣어 7+11=18≠17 이 됐다 — review-775
HIGH. 실제는 `Path | None` 이다.)

처방은 2단계 그대로다: **실제로 좁힌다.** `assert x is not None` 은 **「타입 체계가 허용하는
입력으로 도달 가능」할 때만** 넣고(상위 §7.7 ②), 도달 불가면 2단계 `issued_result` 처럼
**산출자 쪽에 non-Optional 접근자**를 둔다. `receipt.seq` 는 「성공한 append 는 None 을 안
돌려준다」가 코드 주석에 이미 있으므로(`test_rcl_tip_generation_provider.py:47`) 후자 후보다.

`None → StageRequest` 23건은 **타입에 대한 거짓말**이다. `Callable[[StageRequest], int]` 에
`None` 을 넘겨 「안 읽는다」를 증명하는 것은 런타임엔 참이지만 타입엔 거짓이다. 처방: **최소
`StageRequest` 픽스처 하나**를 만들어 넘기고(`StageRequest` 는 `tos/src/tos/engine/
records.py:548` 의 `FrozenModel` — 그냥 만들 수 있다), 「provider 가 request 를 읽지 않는다」는
**별도 테스트 하나**가 센티널 인스턴스로 증명한다. `cast(StageRequest, None)` 는 금지 — 거짓을
타입 체계에 서명하는 것이다.

### 1.3 D — 더블 계약 미충족 90

여기가 **3단계에서 유일하게 설계 판단이 필요한 곳**이다. 기대 타입이 **Protocol 인 것과 구체
클래스인 것**이 갈리고, 후자가 더 많다(Protocol 25 · 구체 65):

| 기대 타입 | 건 | 종류 |
|---|---:|---|
| `TrustworthyTimeService` | **21** | 구체 클래스 `tos/runtime/src/tos_runtime/time/service.py:95` — 더블이 **5종**(`FakeTimeService` 9 · `_TrustedTimeService` 6 · `_NeverStartedTimeService` 4 · `_NotStartedTimeService` 1 · `_BrokenTimeService` 1; 9 중 1 은 `... | None` 자리) |
| `StageRequest` | 13 | 구체 `FrozenModel` (`engine/records.py:548`) — 더블 `_Request` |
| `EvidenceAppendPort` | 8 | **Protocol** (`evidence/ports.py:34`) |
| `KeyProvider` | 7 | **Protocol** (`custody/ports.py:106` · `evidence/store.py:234` 두 벌) |
| `ReservationProjectionReader` | 6 | **Protocol** (`rcl/projection.py:48`) — 더블 4종(`_MinimalRclReader` 3 · `_MutableStateProjection` · `_FixedStateProjection` · `_FakeRclReader`) |
| `SessionFactsOwner` | 6 | 구체 (`calendar/owner.py:124`) |
| `FinalityReleaseConsumer` | 6 | 구체 (`posttrade/release_consumer.py:316`) |
| `SyntheticFinalityProducer` | 5 | 구체 (`posttrade/finality.py:139`) |
| `OrderConstructionStage` | 5 | 구체 (`tos/src/tos/egressgw/construction.py:948`) |
| `RecordingAggregateRiskService` 3 · `SqliteEvidenceStore` 2 · `VenueConstraintService` 2 · `SqliteCommitLog` 1 · `SqliteEventInbox` 1 | 9 | 구체 |
| `CredentialCustody` 2 · `list[ReferenceSourceReader]` 2 | 4 | **Protocol** (`custody/ports.py:124` · `time/sources.py:94`) |

규칙:

1. **기대가 Protocol 이면**(25건) 더블을 계약에 맞춘다 — 빠진 멤버를 더하고 시그니처를
   맞춘다. **Protocol 을 넓히지 않는다**(상위 §3.3).
2. **기대가 구체 클래스인데 그 클래스가 그냥 만들 수 있는 값 객체면**(`StageRequest` 13)
   더블을 버리고 **실제 클래스를 픽스처로 만든다.** `_Request` 는 존재 이유가 없다.
3. **기대가 구체 서비스 클래스면**(`TrustworthyTimeService` 21 · `SessionFactsOwner` 6 ·
   `FinalityReleaseConsumer` 6 · `SyntheticFinalityProducer` 5 · `OrderConstructionStage` 5 ·
   그 밖 9 = **52건**) 선택지가 둘이고 **어느 쪽인지는 피호출자가 정한다**:
   - 피호출자가 그 서비스의 **좁은 표면만** 쓰면(예: 시간 서비스의 `now()` 하나) — 런타임
     소스에 **Protocol 포트를 도입**하고 파라미터 타입을 그 포트로 바꾼다. **소스 변경**이므로
     별도 커밋 + 한 줄 사유 + 리뷰 지점(§3 ⑤). `TrustworthyTimeService` 에 더블이 **5종**이나
     있다는 것 자체가 포트가 필요하다는 신호다 — 다섯 테스트가 각각 다른 「시간 서비스가 아닌
     것」을 만들어 넣고 있다.
   - 피호출자가 넓은 표면을 쓰면 — 더블이 **구체 클래스를 상속**한다(`class _Broken(
     TrustworthyTimeService)`). 상속하면 계약이 mypy 에 보인다.
   - **하지 않는 것**: 파라미터를 `object`/`Any` 로 넓히기.

   포트 도입은 **운영자 확인 ①**(§5)이다 — 런타임 소스 시그니처를 건드리는 유일한 처방이다.

### 1.4 E — `object` 산출자 66

2단계 ③(`_decide() -> object` 한 줄이 21건)과 같은 부류다. 산출자별:

| 피호출자 | 건 | 산출자(레인이 확정) |
|---|---:|---|
| `netting_requires_positive_proof` | 20 | `tos/tests/posttrade/test_posttrade_no_favorable_default.py` — `ObligationLeg | None` 자리 20건 전부 |
| `EgressResultPayload` | 14 | `tos/tests/engine/test_engine_finality_release.py` |
| `_outstanding` 8 · `ProvisionalReservationLedger.*` 11 (`outstanding` 3 · `bind_attempt` 3 · `admits_new_exposure` 2 · `commit_unbound` 2 · `mark_potentially_live` 1) | 19 | 같은 파일 — `ledger`/`key` 인자가 `object` 로 만들어지는 픽스처 |
| 그 밖 | 13 | `test_venue_wiring.py` 6 · `test_spg_dominance.py` 2 · `test_witness_kis.py` 2 · `test_release_consumer.py` 2 · `time/test_service.py` 1 |

처방: **산출자의 애노테이션을 실제 타입으로 교정**한다. `cast` 는 산출자를 못 고칠 때만
(외부 라이브러리 반환 등) 쓰고 그 사유를 그 줄에 적는다. `test_engine_finality_release.py`
**한 파일이 33건**(14 + 19)이라 산출자는 몇 개 안 될 것이다 — 파일별로 고치기 전에 **`got`
타입으로 묶어** 근본을 찾는다(상위 §7.7 ①).

### 1.5 C′ 26 · Z 41 — 개별

- **dict 불변성 21건**(Z): `dict[CommitmentStep, Stage] → dict[CommitmentStep, object]` 14 ·
  `list[dict[str, str]] → list[dict[str, object]]` 4 · `dict[ConformanceAxis, str] | ... →
  dict[ConformanceAxis, str | None]` 3. `dict`/`list` 는 값 타입에 **불변**이라 `Stage` 를
  `object` 자리에 못 넣는다. 피호출자 `_driver`(`tos/runtime/tests/engine/test_replay_stage.py`)
  는 **테스트 헬퍼**라 파라미터를 `Mapping[CommitmentStep, Stage]` 로 고친다 — 읽기만 하면
  `Mapping` 이 맞는 타입이다. **커널/런타임 소스 파라미터가 `dict[..., object]` 인 경우는 소스
  변경**이므로 §1.3 ③과 같은 절차(별도 커밋·사유·리뷰 지점).
- **`str → Enum`** 4건(`FillSide`·`AppendRefusalReason`·`EdgeType`·`EgressResultKind`):
  테스트가 문자열을 넘긴다. Enum 멤버로 바꾼다 — 문자열이 **의도적 불법 입력**이면 §1.1 ①
  처방(`pytest.raises` + `cast`).
- **C′ 26**: `int → Decimal | None` 9 · `dict[ConformanceAxis, str] → ... | None` 5 ·
  `dict[str, str | bool | None] → dict[str, object] | None` 4 · `NonBrokerTransportNature →
  TransportNatureLike | None` 3 · 그 밖 5. 개별로 본다 — 진짜 타입 불일치일 가능성이 있다
  (커널 결함 후보). 레인이 첫 표본에서 **진짜 결함이 나오면 멈추고 보고**한다(운영자 ④).
- 나머지 Z 16: 개별.

## 2. 분할 — PR 5개

**한 파일은 한 PR 에만 산다.** 부류로 나누되 파일이 두 부류에 걸치면 **가장 큰 부류의 PR**
로 몰아 넣고, 동률이면 순서상 앞선 PR 로 간다(공유 워크트리 인덱스 경합·병합 충돌을 피하는
규칙 — 메모리 `shared-worktree-git-index-race`).

| PR | 부류 | 건(근사) | 왜 이 순서인가 |
|---|---|---:|---|
| **3-a** | **E + B** | 173 | 2단계와 **같은 처방**이라 위험이 가장 낮다. 먼저 끝내 레인이 손을 푼다. `None → StageRequest` 23 의 픽스처가 여기서 생긴다 |
| **3-b** | **A — `test_brokercap_routing.py` 한 파일** | 96 | 한 파일에 A-pyd(65)와 A-fn(28)이 **둘 다** 있어 두 처방을 한 곳에서 검증한다. 여기서 확정한 TypedDict·`model_validate` 모양이 3-c/3-d 의 본이 된다. 96 전건 A — 다른 부류 잔여 0 |
| **3-c** | **A-fn + A-issue** (brokercap 제외) | 131 | TypedDict 도입. `degraded_lease_invalidated` 56 이 3파일(`test_authority_lease.py` 32 + spg/protective `test_seam_authority.py` 12+12)에 걸쳐 있어 TypedDict **하나를 어디 둘지**(각 파일 vs 공유 `_authority_strategies.py`)를 첫 표본에서 정한다 |
| **3-d** | **A-pyd + A-rt + 헬퍼** (brokercap 제외) | 216 | `model_validate` 교체가 대부분 — 빌더 한 줄씩. `_sir_strategies.py` 39 · `_wdr_strategies.py` 24 · `_rlp_strategies.py` 12 · `_failuredomain_strategies.py` 12 · `_fixtures.py` 15 |
| **3-e** | **D + C′ + Z** + **게이트 켜기** | 157 | D 의 포트 도입(운영자 ①)이 여기 있다. 마지막 PR 이 `tos-firewall.yml` 두 스텝에서 `--disable-error-code=arg-type` 를 지우고 스텝 주석에 3단계 문단을 더한다(2단계 2b 와 같은 모양) |

부류 합은 173 + 96 + 131 + 216 + 157 = 773 이다. 다만 **파일이 부류에 걸치는 경우가 18개**
있어(부록 A `files spanning >1 bucket`) 위 규칙으로 옮기면 PR 별 건수는 ±20 움직인다.
걸침의 실체는 대부분 런타임 `compose/`·`recovery/` 테스트에서 **B 와 D 가 한 파일에 같이
있는 것**(`test_currentness_wiring.py` B6/D8 · `test_transport_wiring.py` D10/B2 ·
`test_reconciliation.py` B4/D4 …)이고, 커널 쪽은 `test_engine_finality_release.py`(E33/A2)
하나다. **각 PR 은 착수 시점에 자기 몫을 다시 재고 본문에 적는다.** 합은 773 에서 **줄기만**
해야 한다(§3 ①).

3-b 가 3-c/3-d 의 **본**이므로 순서는 3-a → 3-b → (3-c ∥ 3-d) → 3-e 다. 3-c 와 3-d 는
파일이 겹치지 않으면 병렬.

## 3. 종료조건 · 뮤테이션 · 게이트

각 PR 은 다음을 **본문에 수치로** 적는다. 2단계 착지 기록(상위 §7.5~7.7)의 형식을 따른다.

1. **`arg-type` 실측 전후** — 두 트리 각각, `--disable-error-code=arg-type` 를 **뺀** 명령으로.
   착수 시점 773(499 커널 + 274 런타임). 감소분이 PR 이 주장하는 건수와 **같아야** 하고
   다르면 사유를 적는다(2단계 ⑥ 「파일 증가 +21/+18 — 실제 +43/+48」 부류의 오류를 막는다).
2. **전 트리 zero-disable 실행** — 유예 3종을 전부 뺀 `mypy tos/tests` / `mypy tos/runtime/
   tests` 로 **다른 코드가 새로 드러나지 않았는지**(상위 §7.7 ④ — 소스 수정은 켜진 코드에서도
   red 를 낸다). `no-untyped-def`·`unused-ignore` 수치의 **변화량**도 적는다 — 3단계가 그
   둘을 어떻게 움직였는지가 `unused-ignore` 마지막 단계의 입력이다.
3. **표본 1건 먼저** — 각 처방(TypedDict · `model_validate` · `model_construct` · 포트 도입)은
   **첫 1건을 고치고 mypy 를 돌려 그 처방이 실제로 닫는지 본 뒤** 나머지에 적용한다. 2단계
   ①(「잠복 버그가 드러났다」— 실은 발화 불가)과 ⑬(「면역」— 거짓)은 전부 **처방을 검증 없이
   확장**한 데서 왔다.
4. **뮤테이션** — 처방마다 하나, **RED 를 실제로 본 뒤** 원복(`cp -p` 백업 · `cmp` 확인 ·
   `.mypy_cache` 와 `__pycache__` **둘 다** 삭제 — 상위 §7.6 ⑬):
   - TypedDict: 필수 키 하나 제거 → `typeddict-item` RED
   - `model_validate` 빌더: 불법 override 를 넣는 **기존 테스트가 여전히 실패를 관측**하는가
     (`pytest` 로 — 이건 뮤테이션이 아니라 **행동 보존 확인**이다. `model_copy` 로 바꿔 보면
     그 테스트가 **깨져야** 한다 — 이것이 뮤테이션)
   - 더블: 맞춘 멤버 하나 제거 → RED
   - 포트: 포트 멤버 하나 제거 → 실 서비스 쪽이 아니라 **호출부**가 RED 인지(포트가 실제로
     좁혀졌다는 증거)
5. **리뷰 지점** — 리뷰 레인에 **반드시** 넘기는 것: ① 소스 변경 커밋 전부(§1.3 ③ 포트 ·
   §1.5 `Mapping`) — 시그니처 변경이 커널/런타임 호출부를 넓히지 않았는가 ② `cast` 전부 —
   각각 사유가 그 줄에 있는가, 불법 입력 표시 외의 용도로 쓰이지 않았는가 ③ `assert ... is
   not None` 전부 — 도달 가능한가(상위 §7.7 ② 기준) ④ 새 `# type: ignore` **0건**.
6. **게이트 목록** — 상위 §5 8·9 를 그대로 승계한다: `python tools/tos_completion_status.py
   --check` 를 **반드시** 돌리고, diff 가 테스트 파일의 줄 수를 바꾸면 그 파일의 계약 앵커를
   **각각 다시 유도**한다(일괄 오프셋 금지 · GREEN 은 앵커가 옳다는 뜻이 아니다). 3-b 의
   `test_brokercap_routing.py` 와 3-d 의 `_*_strategies.py` 는 앵커 밀도가 높다 — 상위 §5.1 의
   실측표에서 3단계가 건드리는 앵커는 **14파일 170행**이다.
7. **테스트 수 불변** — `tos/tests` · `tos/runtime/tests` 수집 건수를 전후로 잰다. `None →
   StageRequest` 의 「안 읽는다」 테스트 1건 추가 외에는 **불변**이어야 한다.
8. `ruff` · `black --check` · `tools/tos_firewall_check.py` — 새 import(`TypedDict`·`Mapping`·
   `cast`)는 stdlib 이라 firewall 무관하지만 **실측으로** 확인한다.

## 4. 기각 대안

| 대안 | 왜 아닌가 |
|---|---|
| 스플랫 지점마다 `dict[str, Any]` | 773 → 0 이지만 mypy 가 그 호출을 영원히 안 본다. 유예를 플래그에서 코드로 옮긴 것 |
| `**kwargs: Any` 로 커널 술어 시그니처 넓히기 | 프로덕션 타입을 테스트 편의로 판다. 상위 §3.3 이 이미 기각 |
| Protocol 넓히기(더블이 안 주는 멤버를 Optional 로) | 같은 이유 |
| `# type: ignore[arg-type]` 추가 | 래칫 역행 · `unused-ignore` 마지막 단계의 입력을 오염 |
| 파일별 유예(`per-module` `disable_error_code`) | 상위 §0 이 버린 것 — 파일 목록은 썩고 새 파일이 조용히 빠진다 |
| `model_copy(update=overrides)` 빌더 | 검증을 건너뛴다 — 불법 override 를 잡는 테스트가 **아무것도 안 잡게** 된다(pydantic 2.12.5 실측) |
| 한 PR | 773건 단일 diff 는 리뷰가 형식이 된다(상위 §3.3) |
| 더블 90건을 「이름이 `_Fake`/`_Stub` 인 것」으로 한정 | §0.1 — 그 기준이 64건을 놓쳤다 |

## 5. 운영자 확인

| # | 항목 | 추천 |
|---|---|---|
| ① | §1.3 ③ — 런타임 소스에 **Protocol 포트 도입**을 허용할 것인가(`TrustworthyTimeService` 21건이 최대 수혜, 시그니처 변경은 `tos/runtime/src` 안에서만) | **허용하되 별도 커밋·리뷰 지점.** 대안(상속)은 더블 5종을 실 서비스에 묶어 시간 서비스 내부 변경마다 테스트 5개가 흔들린다 |
| ② | §2 PR 5개 분할과 순서 | **채택.** 3-b 를 본으로 먼저 |
| ③ | §1.1 ① — 불법 입력 표시를 `cast` 로 할 것인가, `# type: ignore[arg-type]` 를 그 줄에만 허용할 것인가 | **`cast`.** ignore 는 `unused-ignore` 단계에서 다시 세어야 하고, 부류가 섞인다 |
| ④ | C′ 26 에서 **커널 결함**이 나오면 이 단계 안에서 고칠 것인가 | **아니다.** 보고하고 별도 PR. 이 단계는 테스트 트리 타입 게이트다 |

## 6. 하지 않는 것

- `no-untyped-def` 621 — 상위 §6 ① 그대로.
- `unused-ignore` 187 — 3단계 뒤에 잰다. 이 단계에서 `# type: ignore[arg-type]` 가 「사용 중」
  으로 바뀌는 것이 있다면 그것은 **정상**이고, 죽은 것은 마지막 단계에서 치운다.
- 테스트 헬퍼 중복 제거(`clean_request` 3벌 · `build_core` 3벌 · `_outstanding` 3벌).
- 새 검증 하네스·분류기 도구화. 부록 A 의 스크립트는 **이 계획의 재현용**이고 `tools/` 에
  넣지 않는다(리뷰 레인 규약 §5).

## 7. 착지 기록

PR 마다 번호·main SHA·실측 전후를 덧붙인다. 원 계획 문언은 지우지 않는다.

### 7.0 계획 자체의 fact-check — review-775 (2026-09-22, PR #775)

계획 문서가 코드 변경 없이 PR 로 올라갔고 리뷰 레인(sonnet, 저자와 다른 패스)이 **수치·
`파일:줄`·툴 동작을 전부 재현**했다. 판정 **HIGH 3 · MEDIUM 2 · LOW 1 — 머지 불가** → 조치
후 재심. 재현된 것: 773(499+274) · 24개 `파일:줄` 전부 · 피호출자 카운트 전부 · pydantic 세
동작 · `**TypedDict` 정밀 검사 · Protocol/구체 분류 전부.

| # | 지적 | 조치 |
|---|---|---|
| HIGH 1 | 부록 A 코드를 그대로 돌리면 686건이 Z 로 떨어진다 — **따옴표 제거 줄이 전사에서 빠짐** | 복원. 「누구든 같은 수치를 얻어야 한다」는 문장을 쓴 문서가 자기 기준에 미달했다 |
| HIGH 2 | §1.2 `str \| None` 행에 `load_instance_document` 7 을 넣었으나 실제는 `Path \| None` — 7+11=18≠17 | 행 교체. `str` 행의 실제 분포 = `snapshot_consumer_binding_ok` 11 · `write_approval_file` 2 · `clean_attestation` 2 · `FinalityProofRef` 1 · `derive_id` 1 |
| HIGH 3 | 더블 판정 grep 이 `^class` 앵커라 **들여쓰기 클래스**를 놓침(`test_reconciliation.py:285 _FakeRclReader`) | `^\s*class` 로 넓혀 전수 재분류: **D 87 → 90 · Z 44 → 41**. §0.2·§0.3·§1.3·§1.5·§2 전부 갱신 |
| MEDIUM 1 | 같은 grep 이 산문 `class of bug` 를 잡아 `of` 가 클래스 집합에 섞임 | 패턴 끝에 `\s*[:(]` — `of` 없음 확인 |

**재심(review-775b) 이 HIGH 1 조치 안에서 새 결함을 잡았다** — 조치로 심은 `assert len(TEST_CLASSES)
== 206` 이 깨끗한 체크아웃에서는 **204** 라 `AssertionError` 로 죽는다(저자 환경의 206 은
`__pycache__`/방언 등 환경 의존). 집합 크기는 불변식이 아니라서 단언을 빼고 출력만 남겼다. 같이
잡힌 MEDIUM: INDEX 행의 `Protocol(23)/구체 서비스(51)` 이 D=87 시절 값 그대로였다 → 25/52 로 정정.
**조치가 새 결함을 심는 부류**(상위 §7.2 「지적이 매번 조치 안에서 나왔다」)가 이 문서에서도 반복됐다.
| MEDIUM 2 | §1.4 `_outstanding` + `ProvisionalReservationLedger.*` 18 — 실제 19(`mark_potentially_live` 1 누락) | 19 로 정정, 메서드별 내역 명기 |
| LOW | §1.1 ① 이 `pytest.raises` 를 새 조치처럼 서술 — 이미 감싸져 있다(`:126-134`) | 「새로 필요한 것은 `cast` 뿐」으로 문언 정정 |

**저자가 「분류기를 검증했다」고 쓴 절에서 분류기 결함 2건이 더 나왔다.** 2단계 §7.6 ⑭와 같은
부류이고, 같은 문서 안에서 반복됐다. 검증 주장은 검증을 면제하지 않는다.

## 부록 A — 분류기 (재현용)

측정 명령 (repo 루트, 루트 venv, mypy 2.3.1):

```bash
rm -rf .mypy_cache
.venv/bin/python -m mypy tos/tests --ignore-missing-imports \
  --disable-error-code=no-untyped-def --disable-error-code=unused-ignore > /tmp/k.txt
.venv/bin/python -m mypy tos/runtime/tests --ignore-missing-imports \
  --disable-error-code=no-untyped-def --disable-error-code=unused-ignore > /tmp/r.txt
grep -h "\[arg-type\]" /tmp/k.txt /tmp/r.txt > /tmp/argtype_all.txt   # 773
```

분류 규칙 (라벨은 겹침 허용, §0.3 의 배타 분할은 `bucket()`):

```python
import re, subprocess, collections

pat = re.compile(
    r'^(?P<file>[^:]+):(?P<line>\d+): error: Argument (?P<arg>"[^"]+"|\d+)(?: to '
    r'(?P<callee>"[^"]+"(?: of "[^"]+")?))? has incompatible type (?P<actual>".*?"); '
    r'expected (?P<expected>".*?")  \[arg-type\]$'
)  # `(?: to ...)?` — 피호출자 없는 positional 형상 27건을 초판이 놓쳤다 (§0.1)

rows = []
for line in open("/tmp/argtype_all.txt"):
    m = pat.match(line.rstrip("\n"))
    assert m, line                       # 미파싱 0 이어야 한다
    d = m.groupdict()
    d["actual"] = d["actual"].strip('"')     # ← 이 두 줄이 초판 전사에서 빠졌다 (review-775 HIGH 1)
    d["expected"] = d["expected"].strip('"')
    rows.append(d)

# 테스트 더블 = 테스트 트리에 정의된 클래스. `^\s*class` — 들여쓰기 정의도 센다 (HIGH 3);
# 끝의 `\s*[:(]` — 산문 "a class of bug" 를 거른다 (MEDIUM 1).
_defs = subprocess.run(
    ["grep", "-rhoE", r"^\s*class [A-Za-z_][A-Za-z0-9_]*\s*[:(]", "tos/tests", "tos/runtime/tests"],
    capture_output=True, text=True,
).stdout.split("\n")
TEST_CLASSES = {re.sub(r"\s*[:(]$", "", x.strip().split(None, 1)[1]) for x in _defs if x.strip()}
assert "of" not in TEST_CLASSES          # 크기는 단언하지 않는다 — 환경 의존 관측치(204~207, §7.0)
print("TEST_CLASSES", len(TEST_CLASSES))

def has_none(t):  # `None` 이 유니온의 항으로 있는가 — 리터럴 완전일치가 아니다 (상위 §7.6 ⑭)
    return bool(re.search(r"(^|\| )None($| \|)", t))

def labels(a, e):
    L = []
    if a.startswith("**"):                                   L.append("A_kwargs_unpack")
    if has_none(a) and not has_none(e):                      L.append("B_actual_optional")
    if a == "None" and not has_none(e):                      L.append("B0_literal_none")
    if has_none(e) and not has_none(a):                      L.append("C_expected_optional_only")
    if set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", a)) & TEST_CLASSES:
                                                             L.append("D_double")
    if a == "object":                                        L.append("E_object")
    return L or ["Z_other"]

def bucket(L):  # §0.3 배타 분할 — 처방이 더 근본적인 쪽이 먼저
    for tag, name in (("A_kwargs_unpack", "A"), ("D_double", "D"), ("B_actual_optional", "B"),
                      ("B0_literal_none", "B"), ("E_object", "E"), ("C_expected_optional_only", "C'")):
        if tag in L:
            return name
    return "Z"

for d in rows:
    d["labels"] = labels(d["actual"], d["expected"]); d["bucket"] = bucket(d["labels"])
print(collections.Counter(x for d in rows for x in d["labels"]))
print(collections.Counter(d["bucket"] for d in rows))
```

피호출자 정의 위치(§0.4 표)는 `grep -rnE "^\s*(class|def) <name>\b" tos/src tos/runtime/src
tos/tests tos/runtime/tests` 로 얻었다.

실측 결과(main `29f39fe6`, 결함 4건 수리 후): 파싱 773/773 · 라벨 A 443 · B 107(B0 29) ·
C 253 · D 90 · E 66 · Z 41 · 배타 조합 = A 250 · A+C 193 · B 78 · B+B0 29 · D 78 · C+D 12 ·
E 44 · C+E 22 · C 26 · Z 41 · **`bucket()` = A 443 · B 107 · D 90 · E 66 · C′ 26 · Z 41 = 773**.
부류에 걸치는 파일 18개(`files spanning >1 bucket`)는 §2 의 규칙으로 배정한다.
