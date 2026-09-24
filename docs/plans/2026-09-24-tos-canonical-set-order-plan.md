# tos 정본 직렬화 — 집합 순서 결정성 복원 (2026-09-24)

- 작성: 2026-09-24 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 측정 시점 main **`b5bb5eb5`**
- 발견: PR #797(첫 부팅) 구현 레인 — 렌더 종료 검사가 **새 프로세스에서** 정책을 재로드해 digest 를 대조하다 잡았다.
- 운영자 결정(2026-09-23): 「커널 수정 계획 → 별도 PR」 · (2026-09-24) `canonicalization_version` **유지**(§2.4).
- 개정 이력: 초판 `f50886b4` → 2판 `6ae0fc1f`(review-798 1차 반영) → **3판(이 문서, review-798 2차 반영)**. 차이는 §6.
- 성격: **소형 계획 하나 · 구현 PR 하나(PR #797 머지 뒤 — §4)**. 계약 문서·tos-spec 은 건드리지 않는다.

## 0. 한 줄 요약

커널·런타임은 `FrozenModel.model_dump(mode="json")` 결과를 여러 경로로 digest 한다. JSON 모드는 `set`/`frozenset` 을 순회
순서(문자열 해시 시드 의존) 그대로 리스트로 내고, 정본 인코더는 리스트를 순서 유의미로 해시한다 → **같은 내용이 프로세스마다
다른 digest**(설계 #2 §3.4 must-pass **(A)-1 결정성** 위반). 처분: **`FrozenModel` 에 JSON 모드 직렬화 훅 하나**를 달아 모든
집합을 `sorted()` 리스트로 낸다. 이미 모델별로 `sorted()` 정렬하던 8종과 키가 같아 **비트 호환**이고, `covered_content()`·
`event_identity()`·런타임 `compute_digest(x.model_dump(mode="json"))` 등 **모든 호출 형태가 한 번에 닫힌다**.

## 1. 실측 (main `b5bb5eb5`, review-798 1·2차 재현 포함)

### 1.1 메커니즘

- `tos/src/tos/canonical/_base.py:73` `class FrozenModel(BaseModel)` — 커널 기록 모델의 공통 베이스. `DigestBoundArtifact`(`:109`)도 그 하위.
- `_base.py:187` `covered_content()` = `self.model_dump(mode="json", include=set(self._COVERED_FIELDS))`.
- `tos/src/tos/canonical/canonicalization.py` `_encode` — 매핑은 키 정렬, 시퀀스는 「order-significant」.
- 집합 원소의 순회 순서는 `PYTHONHASHSEED` 를 따른다. `tos`·`tos_runtime` 의 집합 선언 **89 필드의 원소는 `str` 70 · `StrEnum` 19 뿐**
  (review-798 2차 전수) — 모두 해시 무작위화 대상이고, 서로 비교 가능해 `sorted()` 가 `TypeError` 를 낼 곳이 없다.

### 1.2 `covered_content()` 경로 — 19종 중 결함 **11종**, 이미 정렬 **8종**

`DigestBoundArtifact` 하위 중 `_COVERED_FIELDS` 보유 **120종**, 그중 covered 필드(중첩 재귀)에 집합이 있는 **19종**. 시드 8개 측정:
결함 11종은 8종의 digest, 이미 정렬하는 8종은 1종의 digest.

| 상태 | 모델 | 정렬 수단 |
|---|---|---|
| **이미 결정적 (8)** | `CurrentnessPolicy` · `RestrictiveFenceRecord`(`tos.cur`) · `SafetyDeviationPolicy`(`tos.wdr`) · `SafetyIncidentPolicy`(`tos.sir`) · `TrialEvidencePackage` · `TrialPolicy`(`tos.rlp`) | 모델별 `covered_content` 재정의 / `_sorted_set_fields` — `sorted()` |
| 〃 | `LiveAuthorization` · `ReArmApprovalRecord`(`tos.liveauth`) | `tos/src/tos/liveauth/state.py:54` `field_serializer` — `sorted()` |
| **결함 (11)** | `BrokerCapabilityProfile` · `HumanApprovalRequest` · `HumanAuthorityPolicy` · `HumanDelegationRecord` · `HumanHaltCommand` · `StatementCoverageManifest` · `RecoveryInventoryCut` · `RecoveryObligation` · `RecoveryReadinessDecision` · `OrderAdmissibilityDecision` · **`VenueConstraintPolicy`** ⚠ 배포 채택(09-16) | 없음 |

`CurrentnessPolicy` 는 결함이 아니다(`tos/src/tos/cur/records.py:44-49`). 이 배포가 당장 막히는 것은 `VenueConstraintPolicy` 하나다.

### 1.3 `covered_content()` 를 거치지 않는 digest — 호출 형태 다섯

- 커널: `tos/src/tos/engine/records.py:454` `event_identity()` 가 `EngineEvent.model_dump(mode="json")` 을 직접 digest —
  `CORPORATE_ACTION` 의 집합 필드 때문에 시드 0~5 에서 event id 6종.
- 런타임(**`tos/runtime/src/tos_runtime/engine/`** — 2판이 `tos/src` 로 잘못 적었다): `driver.py:536`
  `self._scheme.compute_digest(event.model_dump(mode="json"))` · `driver.py:803` · `inbox.py:353` · `finality_projection.py:145,150` ·
  `orthostate_projection.py:310,344,425` 등.
- review-798 2차가 센 호출 형태: 직접 중첩 · 변수 경유 · dict 에 담아 반환 · `json.dumps` 후 해시 · `evidence_store.append` 내부.
  **호출부를 하나씩 고치거나 AST 로 잡는 방식은 형태 하나를 놓치면 재발한다** — 그래서 3판은 직렬화 자체를 고친다(§2.1).

### 1.4 영속 digest

- 19종 digest 를 값으로 담은 영속 파일 **0**(`config/tos_runtime/paper/*` 는 `canonical_digest: TBD`, 64-hex 리터럴 전수 grep 0).
- **예외 하나: `config/tos_runtime/paper/release.yaml::expected_code_digest`** — `tos/src`·`tos/runtime/src` 의 모든 `*.py` 바이트를 접는다.
  이 PR 이 커널 코드를 바꾸므로 **반드시 변한다**(프로토타입 `0876c3e0…` → `510b282b…`, review-798 H-1). §2.5.

## 2. 처분

### 2.1 `FrozenModel` JSON 직렬화 훅 — 한 곳

새 모듈 `tos/src/tos/canonical/_canonical_json.py` 에 pydantic **`@model_serializer(mode="wrap")`** 를 가진 믹스인
`CanonicalJsonMixin` 을 두고, `FrozenModel` 이 그것을 상속한다. 훅은 **`info.mode == "json"` 일 때만** 기본 직렬화 결과 트리에서
원래 `set`/`frozenset` 이던 값을 `sorted()` 리스트로 바꾼다(파이썬 모드 `model_dump()` 는 집합을 집합으로 그대로 돌려준다 —
동작 변화 없음). `model_dump(mode="json")` 과 `model_dump_json()` 이 모두 이 훅을 탄다. 중첩 모델은 각자의 훅을 탄다.

- **정렬 키 = `sorted()`**(원소의 파이썬 값 — `str`/`StrEnum` 은 문자열 순). 이미 정렬하는 8종이 쓰는 키와 같아 그 8종의 digest 는
  **비트 단위로 그대로**다(review-798 2차 프로토타입: 원소 길이를 섞어도 main 과 동일).
- **비교 불가 원소는 거부**: `sorted()` 가 `TypeError` 를 내면 훅은 대체 키로 조용히 넘어가지 않고 그대로 올린다. 오늘 커널에는
  그런 집합이 없다(§1.1).
- **원래 값을 순회한다**(review-798 3차 M-2): wrap serializer 가 JSON 모드에서 받는 트리는 **이미 리스트화된** 값이다. 그래서 훅은
  `getattr(self, 필드)` 로 원래 값을 결과와 나란히 순회해, 원래 `set`/`frozenset` 이던 자리만 정렬한다(프로토타입이 이 방식으로
  `model_dump_json()`·`include`/`exclude`·`exclude_none`/`exclude_defaults`·`round_trip`·`SerializeAsAny`·판별 유니온·중첩 컨테이너 전부에서
  정렬을 확인했다). 필드 자체 serializer 는 훅이 덮어쓴다.
- **정렬이 조용히 빠지는 세 경우**(오늘 커널 0건): 집합 필드에 별칭을 두고 `by_alias=True` 로 덤프할 때 · `FrozenModel` 이 아닌
  `BaseModel` 이 중첩될 때 · 필드 serializer 가 집합이 아닌 값을 낼 때. 셋 다 §3 의 핀으로 막는다.
- **비용과 조건부 부착**(M-3): 무조건 부착하면 **모든** `FrozenModel` 직렬화가 파이썬 콜백을 탄다 — 프로토타입 실측 `EngineEvent`
  `model_dump(mode="json")` 39→267~287 µs, 파이썬 모드 `model_dump()` 30→180~190 µs, 아티팩트 생성(검증+digest) +25~30%.
  그래서 요구사항은 **집합 필드가 필드 트리에 있는 클래스에만 훅을 붙이는 것**(`__pydantic_init_subclass__` 등에서 클래스별로
  판정하고 집합 필드 이름을 미리 계산 — 프로토타입에서 JSON 모드 267→143 µs)이다. 종료조건: 집합이 없는 클래스는 파이썬·JSON 모드
  모두 **도입 전과 비용 동일**(±측정 잡음), 집합 있는 클래스는 비용을 측정해 착지 기록에 적는다. 조건부 부착이 pydantic 에서
  불가능하면 구현 레인이 멈추고 수치와 함께 보고한다(무조건 부착을 조용히 택하지 않는다).
- 요구사항 요약: 「JSON 모드 출력에서 집합이 `sorted()` 순이고, 그 밖의 출력은 바이트 동일」(§3 핀).

### 2.2 `_base.py` 의 인용된 줄을 움직이지 않는다

`tos/tests/orthostate/test_orthostate_l2_fault.py` 가 `_base.py:187/205/209/211` 를 줄 단위로 고정하고(**ST-05·06·07·09·12**),
`tos-spec/src/part-1-foundation/verification/ADVERSE-SCENARIO-SET-002-EVL2-PILOT.yaml` 이 `_base.py:205/211` 를 `normative_anchor`
로 인용한다(운영자 게이트 결정 `53980b64` 로 들어온 spec — 이 PR 은 편집하지 않는다). 그래서 **`_base.py` 의 변경은 `:73`
`class FrozenModel(BaseModel):` 한 줄을 같은 줄에서 `class FrozenModel(CanonicalJsonMixin, BaseModel):` 로 바꾸는 것과, 그 이름을
들이는 import 뿐**이어야 한다. 기존 import 줄에 이름을 더하는 방식은 **불가능**하다(믹스인이 다른 모듈이고, 합쳐도 `black` 이 그 줄을
펼친다 — review-798 3차 M-1). 그래서 **새 import 한 줄을 넣고 `_base.py` 모듈 docstring 한 줄을 지워** 그 아래 줄 번호를 유지한다
(프로토타입에서 줄 고정 전부 유지 · L2 테스트·black·ruff·mypy 통과 · import 순환 없음 확인). 고정된 줄은 `:87`(`tos/tests/spg`
**SPG-05·06**) · `:187/205/209/211`(orthostate ST-05·06·07·09·12)이다 — 2판·3판 초고가 SPG-05·06 을 빠뜨렸다. `covered_content()`(`:187`)는
**바꾸지 않는다** — 훅이 그 아래에서 일한다.

### 2.3 이미 정렬하는 8종의 개별 수단

`covered_content` 재정의·`_sorted_set_fields`·`liveauth` `field_serializer` 는 훅과 같은 결과를 내므로 **삭제한다**(모델별 수단이 여럿인
상태가 11종을 남긴 원인). 삭제 전후 digest 동일을 핀으로 증명한다(§3). 삭제로 그 파일들의 줄이 밀려 산문 인용
(`liveauth/state.py:135~208` 등)이 낡는다 — 구현 레인이 `tos/`·`docs/plans/`(활성 문서) 의 인용을 **내용으로 재유도**한다.
`tos-spec/`·`tos-evidence/` 의 인용이 걸리면 그 파일은 편집하지 말고 그 수단은 **삭제하지 않고 남긴다**(범위 축소가 동결 편집보다 낫다).

### 2.4 `canonicalization_version` 유지 (운영자 확인 2026-09-24)

`ev-l1-provisional-0` 은 비프로덕션 잠정 canonicalizer(설계 #2 §3.4). 결함 경로의 digest 는 내용의 함수가 아니었으므로 보존할
안정값이 없고, 이미 결정적이던 8종은 비트 호환이다. D5 결정 기록 §1.3-2 의 「digest 값이 바뀌면 `ALGORITHM_ID` 범프」는
`tools/bcp_digest.py`(:31-33, stdlib+yaml 만 쓰는 BCP digest 도구)의 규율이다 — 문자열 `ev-l1-provisional-0` 만 겹치고 코드는 공유하지
않는다. 이 PR 은 그 도구를 건드리지 않는다.

### 2.5 `expected_code_digest` 재도출 — 운영자 확인 대상이 아니다

`release.yaml::expected_code_digest` 는 제안표 §0.1.2 의 **(라) 배포 환경 실측값** — 운영자 판단이 아니라 `print-digests` 로
**도출**하는 값이다(`release.yaml` 헤더 「`tos/src/**.py` 또는 `tos/runtime/src/**.py` 가 한 바이트라도 바뀌면 갱신 · 두 곳을 함께」).
구현 PR 의 **마지막 커밋**에서 `print-digests` 를 다시 돌려 `release.yaml` 과 `test_deploy_approved_values.py::_VALUE_PINS` 를 함께
갱신하고, 명령·출력을 커밋 메시지에 남긴다. **머지 순서**: `tos/src`·`tos/runtime/src` 를 건드리는 다른 PR(현재 #799 달력)이 먼저
머지되면 rebase 뒤 다시 도출한다.

## 3. 핀 — 「이 가드가 실패하는 구체적 입력」

| 핀 | 실패하는 입력 |
|---|---|
| **프로세스 간 결정성 — `covered_content`**: 19종 각각 대표 인스턴스(집합 원소 **≥ 6, 서로 길이가 다른 문자열**)를 `PYTHONHASHSEED` 가 다른 서브프로세스 **≥ 5** 개에서 만들어 digest 동일 | 훅을 빼면 → 결함 11종이 시드마다 갈려 RED |
| **프로세스 간 결정성 — 비-`covered_content` 경로**: `CORPORATE_ACTION` `event_identity()` + 런타임 `driver.py:536` 형태 1건 이상 | 훅을 빼면 → RED |
| **비트 호환 — 기존 8종**: 훅 도입 전 digest 를 **길이가 다른 원소**로 만든 골든 값으로 고정 · `_NonTruthyStrEnum`(`ObligationResult`) 같은 `str` 하위 Enum 원소 포함 | 정렬 키를 `sorted()` 외(예 `_encode` 토큰 — 길이 우선)로 바꾸면 → RED. (같은 길이 원소만 쓰면 이 뮤테이션이 헛돈다 — review-798 M-3) |
| **파이썬 모드 불변**: `model_dump()`(파이썬 모드)가 집합을 집합으로 돌려줌. 단 `LiveAuthorization`·`ReArmApprovalRecord` 는 삭제될 `field_serializer(when_used="always")` 때문에 오늘 파이썬 모드에서 정렬 리스트를 내므로 **이 두 모델은 「frozenset 으로 바뀜」을 명시 기대값**으로 적는다(`tos/src`·`tos/runtime/src` 의 파이썬 모드 호출 0 — review-798 3차 L-1) | 훅이 모드를 가리지 않으면 → RED |
| **별칭 금지**: 집합 필드(트리 전체)에 `alias`/`serialization_alias` 가 없음을 단정 | 집합 필드에 별칭을 달면 → RED(`by_alias=True` 덤프에서 정렬이 조용히 빠지는 경우를 차단) |
| **트리 기준 폐쇄**: 필드 트리에 집합이 있는 pydantic 모델(오늘 558개 중 59개)의 **트리 안 모든 모델**이 `FrozenModel` 하위 | 집합을 가진 `BaseModel` 을 `FrozenModel` 안에 중첩하면 → RED |
| **비용**: 집합이 없는 대표 모델 3종(예 `EngineEvent` 가 집합 없는 형태로 쓰이는 경우 포함)의 파이썬·JSON 덤프가 도입 전과 같은 비용 — 상대 비율 단정(절대 시간 아님, 러너 편차 흡수) | 훅을 무조건 부착하면 → 비율 초과로 RED |
| **목록 폐쇄**: 테스트가 `tos`·`tos_runtime` 하위 모듈을 **전부 명시적으로 import** 한 뒤, 집합 필드를 가진 pydantic 모델 전부가 `FrozenModel` 하위이거나 명시 허용목록(사유 한 줄)에 있음을 단정 · 발견 수 **하한** 단정 | `BaseModel` 을 직접 상속하는 새 모델에 집합 필드를 추가하면 → RED · import 누락으로 0 이 나오면 하한에서 RED |
| **비교 불가 원소 거부**: 합성 모델 `frozenset[str | None]`(해시 가능·비교 불가) → 훅이 `TypeError` 를 올림 | 훅에 `key=str` 폴백을 넣으면 → RED. (중첩 모델 집합은 해시 불가라 폴백 이전에 죽어 헛돈다 — review-798 M-3) |
| **줄 고정 무회귀**: `test_orthostate_l2_fault.py`·`tos/tests/spg` 무변경 통과 · `_base.py:87/187/205/209/211` 내용 불변 | `_base.py` 줄 이동 → ST-05·06·07·09·12 · SPG-05·06 RED |
| **(A) suite 무회귀** | 기존 must-pass 5종 |

## 4. 순서와 삭제

- 구현 PR 은 **PR #797 머지 뒤**. #797 의 결함 고정 테스트 `test_venue_policy_canonical_digest_is_not_reproducible_across_processes`
  와 `pinned_hash_seed` 픽스처, 렌더 `_subprocess_env()` 의 `PYTHONHASHSEED` 통과를 **이 PR 에서 삭제**한다.
- 종료조건: 런북(`docs/runbooks/tos-paper-boot.md`) 절차를 **시드 고정 없이** 이 호스트에서 다시 돌려 렌더 R0 가 통과하고, 갱신된
  `expected_code_digest` 로 `run` 이 `ReleaseAdmissionRefused` 없이 부팅함.

## 5. 운영자 확인

| # | 항목 | 추천 | 실제 |
|---|---|---|---|
| ① | `canonicalization_version` 유지(§2.4) | 유지 | **유지** — 2026-09-24 |

`expected_code_digest` 갱신은 도출값이라 확인 대상이 아니다(§2.5).

## 6. 개정 차이

| 판 | 무엇이 틀렸나 | 3판 |
|---|---|---|
| 초판 | 결함 19종 · 정렬 키 `_encode` · 초크포인트 하나 · 파급 오지목 · 핀 약함 | 2판에서 교정(review-798 1차 HIGH 3 · MEDIUM 3) |
| 2판 | 경로 ② 파일 경로를 `tos/src` 로 오기 · AST 폐쇄 핀이 호출 형태 5종 중 일부만 잡음 | **직렬화 훅 하나**로 호출 형태 무관하게 닫음(M-1) |
| 2판 | 「지역 import 로 줄 수 유지」 — `black` 이 빈 줄을 강제해 불가 · `-> Any` 는 `no-any-return` | `covered_content()` 를 **안 건드린다** · `:73` 한 줄 + 기존 import 줄 확장(M-2) |
| 2판 | ST 목록 누락(ST-12) | ST-05·06·07·09·12 |
| 2판 | 골든이 같은 길이면 키 뮤테이션 헛돎 · 중첩 모델 예시는 폴백 전에 죽음 | 길이 다른 원소 · `frozenset[str | None]`(M-3) |
| 2판 | `expected_code_digest` 파급 누락 | §1.4 예외 · §2.5 재도출 · 머지 순서(H-1) |

## 7. 착지 기록

**착지 2026-09-24 · 브랜치 `fix/tos-canonical-set-order` · 기준 main `153c8fd0`(#797 포함).**

### 7.1 무엇이 들어갔나

| 커밋 | 내용 |
|---|---|
| `fix(tos)` | 새 모듈 `tos/src/tos/canonical/_canonical_json.py` (`CanonicalJsonMixin`) · `_base.py` 는 import 한 줄 추가 + 모듈 docstring 한 줄 삭제 + `:73` 한 줄 |
| `refactor(tos)` | 모델별 정렬 8종 삭제(`cur` 2 · `wdr` 1+헬퍼 · `sir` 1+헬퍼 · `rlp` 2+헬퍼 · `liveauth` field_serializer) · 산문 인용 5곳 재유도 |
| `test(tos)` | `tos/tests/canonical/{_set_order_builders,_set_order_worker,test_canonical_json_set_order}.py` · `tos/runtime/tests/canonical/test_canonical_json_closure.py` · `tests/tools/test_tos_canonical_set_order.py` |
| `fix(scripts)` | #797 결함 핀 3종 + `pinned_hash_seed` 픽스처 + `_subprocess_env()` 의 `PYTHONHASHSEED` 통과 삭제 |
| `docs` | 이 절 · `docs/plans/INDEX.md` 1행 · `docs/runbooks/tos-paper-boot.md` §5 ① 해소 |
| `chore(tos)` | `expected_code_digest` 재도출(마지막 커밋, §2.5) |

### 7.2 조건부 부착 — 어떻게 구현했나

`@model_serializer(mode="wrap")` 데코레이터는 클래스 정의 시점에 무조건 붙으므로 쓰지
않았다. 대신 믹스인이 **`__get_pydantic_core_schema__`** 를 정의해, `handler(source)` 가
만든 코어 스키마를 훑어 **그 클래스 자신의 필드 스키마에 `set`/`frozenset` 노드가 있을
때만**(중첩 `model`/`dataclass`/`definition-ref` 는 건너뛴다 — 중첩 모델은 각자의 훅을
탄다) `schema["serialization"]` 에 래핑 직렬화기를 얹는다. 집합 필드 이름은 그때
`__canonical_set_fields__` 로 미리 계산한다. 집합이 없는 클래스는 스키마가 손대지지
않으므로 pydantic-core 네이티브 직렬화기를 그대로 쓴다.

부수 효과 하나: 같은 클래스가 유니온 멤버로 두 번 스키마 생성에 들어오면 pydantic 이
**캐시된 스키마**를 돌려주므로, 훅은 자기 자신의 앞선 부착을 알아보고 멱등하게 넘어간다
(`_is_this_hook`). 다른 `@model_serializer` 가 이미 있는 집합 보유 클래스는 `TypeError`
로 **요란하게** 거부한다 — 조용히 덮어쓰면 정렬이나 그 직렬화기 중 하나가 사라진다.

### 7.3 비용 실측 (µs/op · best-of-5 × 2000회 · 같은 호스트)

| 측정 | main `153c8fd0` | 이 브랜치 |
|---|---|---|
| 집합 **없는** `FrozenModel` / 같은 모양 순수 `BaseModel` (python·json) | — | 아래 표 |
| 집합 **있는** `FrozenModel` / 같은 모양 순수 `BaseModel` (python·json) | — | 아래 표 |
| `EngineEvent.model_dump()` | 65.6 | 89.5 |
| `EngineEvent.model_dump(mode="json")` | 61.1 | 102.2 |
| `EngineEvent.model_dump_json()` | 49.6 | 97.7 |
| `VenueConstraintPolicy.covered_content()` | 7.3 | 33.2 |
| `VenueConstraintPolicy` 검증+digest 전체 | 99.5 | 130.7 |

**비율 재측정 (review-802 M-1).** 처음 적은 0.92~1.07 은 **단발 관측**이었고, 실제
분산을 과소 진술한 것이 맞다. 같은 호스트에서 60회 반복한 실측:

| 측정기 | control(순수 대 동일한 순수) | 집합 **없는** `FrozenModel` | 집합 **있는** `FrozenModel` |
|---|---|---|---|
| 기존 (각 변을 끝까지 재고 최소값끼리 나눔, best-of-5 × 2000) · python | 0.683–1.625 | 0.511–1.903 | — |
| 〃 · json | 0.415–2.620 | 0.251–2.854 | — |
| 현재 (쌍측정 · 라운드별 비율의 median, 21 × 500) · python | 0.925–1.073 | 0.895–1.097 | 1.683–2.030 |
| 〃 · json | 0.910–1.070 | 0.923–1.061 | 2.403–2.683 |

**control 은 훅이 양쪽에 없어 참값이 1.00 인데도 기존 측정기에서는 0.42~2.62 로 퍼졌고
1.6 을 60회 중 1~2회 넘었다** — 즉 옛 경계는 훅이 아니라 스케줄러를 재고 있었다. 새
측정기에서 세 열이 서로 겹치지 않으므로, 종료조건 「집합 없는 클래스의 비용은 도입 전과
같다」는 이제 실제로 측정된다. 비용은 집합을 가진 클래스에만 붙는다. `EngineEvent` 의
파이썬 모드가 느려진 것은 그 이벤트가 집합을 가진 `CorporateActionPayload` 를 중첩하기
때문이고, 그 중첩 모델이 훅을 단 결과다(훅은 파이썬 모드에서 즉시 반환하지만 콜백 자체는
탄다).

### 7.4 삭제한 정렬 수단과 동결 인용

8종 전부 삭제했다 — 계획 §2.3 의 「동결 파일 인용이 밀리면 남긴다」 조건은 **발동하지
않았다**. `tos-spec/src/verification/EVIDENCE-SURFACE-MAP.csv` 가 이 파일들을 인용하는
줄은 `cur/records.py:15`·`rlp/records.py:14`·`wdr/records.py:15`(모듈 docstring)뿐이고
삭제 시작 줄(`cur:120`·`rlp:102`·`wdr:107`)보다 위라 밀리지 않는다. `sir/records.py`·
`liveauth/state.py` 를 인용하는 동결 파일은 없다.

`tos/` 안의 산문 인용 5곳(`cur`·`wdr`·`sir`·`rlp`·`stm` 모듈 docstring 의
「`covered_content` 가 정렬한다」)은 내용으로 재유도했다 — 이제 공용 훅을 가리킨다.

### 7.5 핀과 뮤테이션

| 핀 | 어디 | 뮤테이션 → 결과 |
|---|---|---|
| 프로세스 간 결정성(19종 + `event_identity` + 런타임 `driver.py` 형태), 시드 6개 서브프로세스 | `tests/tools/test_tos_canonical_set_order.py` | 훅 제거 → **RED, 21키 전부** |
| 음성 대조군(모델을 거치지 않은 raw frozenset 순서)이 시드마다 **달라야** 한다 | 〃 | (시드가 안 닿으면 나머지가 공허해지는 것을 막는 가드) |
| 비트 호환 골든 8종(길이 섞인 원소 + `ObligationResult` 계열 str-Enum) | `tos/tests/canonical/test_canonical_json_set_order.py` | 정렬 키를 길이 우선 토큰으로 → **RED, 8종 전부** |
| 조건부 부착 · 비용 비율 | 〃 | 무조건 부착 → **RED**(집합 없는 모델 1.96x · 부착 핀도 RED) |
| 별칭 금지 | 〃 + 폐쇄 테스트 | 집합 필드에 `alias` 추가 → **RED** |
| 트리 폐쇄(집합 보유 pydantic 모델 전부 `FrozenModel` 하위 · 하한 59/41/19 · 전 모듈 명시 import) | `tos/runtime/tests/canonical/test_canonical_json_closure.py` | 집합 가진 `BaseModel` 추가 → **RED** |
| 비교 불가 원소 거부(`frozenset[str | None]`) · 파이썬 모드 불변(liveauth 2종은 명시 기대 변화) · 줄 고정 무회귀 | `tos/tests/canonical/...` + 기존 L2 가드 | — |
| **집합 안의 집합 금지**(review-802 M-2) | `tos/runtime/tests/canonical/test_canonical_json_closure.py` | `frozenset[frozenset[str]]` 필드 추가 → **RED** (`_MutationSetInSet: ['outer']`) |
| **stdlib dataclass / NamedTuple / TypedDict 금지**(〃) | 〃 | 세 가지 각각 필드 추가 → **RED 3/3** |
| **조건부 부착 구조 단정 + 잡음 바닥 상대 비용 경계**(review-802 M-1) | `tos/tests/canonical/test_canonical_json_set_order.py` | 무조건 부착 → 구조 단정 **RED**, 구조 단정을 무력화해도 비용 단정 **RED**(1.69x·2.04x 대 1.35x 경계, 잡음 바닥 1.00x) |
| **명시 import 목록이 스스로 도달하는지**(review-802 L-3) | `tos/runtime/tests/canonical/test_canonical_json_closure.py` | 목록 밖 새 서브패키지를 conftest 에서만 import → 첫 단정 **RED**(`sys.modules` 단정은 green — 강도 차이를 그대로 보여 줌) |
| **훅 스키마 노드의 클래스별 사본 · 유니온 재진입 멱등**(review-802 L-5) | `tos/tests/canonical/test_canonical_json_set_order.py` | 두 클래스의 `serialization` 노드가 서로 다른 객체이면서 같은 함수를 들고, 유니온 홀더 정의가 `TypeError` 없이 통과 |

기준선: main `153c8fd0` 에서 같은 워커를 시드 6개로 돌리면 digest 맵이 **6종 전부
상이**. 이 브랜치에서는 **1종**.

### 7.6 종료조건 — 시드 고정 없는 런북 완주 (이 호스트, 2026-09-24)

`PYTHONHASHSEED` 미설정, 산출물은 저장소 밖 임시 디렉터리, 실 `.env.mock` 사용.

```text
LONG  render → activation: ACTIVATED 5 (re-derived in a fresh process)   # R0 통과
LONG  --check → matches config/tos_runtime/paper
LONG  run --environment-label paper → (SIGTERM) run: stopped (signal received).  exit=0
SHORT render → activation: ACTIVATED 5 (re-derived in a fresh process)
SHORT run → (SIGTERM) run: stopped (signal received).  exit=0
세션 시계 주입 2026-09-28T10:00:00+09:00 (unix_ms=1790557200000):
  phase='CONTINUOUS' is_open=True trading_calendar_version='krx-2026.09.1'
  TICK OUTCOME: TICKED   (LONG·SHORT 양쪽 · marketfeed.sqlite3 snapshots=1)
```

갱신 전 `expected_code_digest` 로 부팅하면 Stage A 가 `ReleaseAdmissionRefused` 로
거부한다 — 이 재측정에서 실제로 한 번 겪었고(가드가 산다는 증거), 갱신 후 통과했다.

### 7.7 `expected_code_digest` 재도출 (§2.5)

```text
$ PYTHONPATH=tos/src:tos/runtime/src .venv/bin/python \
    -c 'import sys;from tos_runtime.compose.cli import main;sys.exit(main(sys.argv[1:]))' print-digests
expected_code_digest: b96213f5e64beff7b69af3146fa403d48c517b0c4f68f6531e4519a291564662
expected_dependency_set_digest: 20559763a1132fc75f71f3d83e99512f4b0d9cdde9e0df61b54b9d2459f98d8b
python_version: 3.12.12
sqlite_version: 3.45.1
```

이 브랜치에서 두 번 도출했다: 3차 `1600de4c…9cb110`(커널 훅 착지 시점, 이전 값은
`b9eda9bd…d33571` = main `153c8fd0`), **4차 `b96213f5…564662`**(review-802 조치가
`_canonical_json.py` 를 또 바꿔서). 매번
`config/tos_runtime/paper/release.yaml`(값 + 헤더 주석 이력)과
`tos/runtime/tests/compose/test_deploy_approved_values.py::_VALUE_PINS` 를 같은 커밋에서
갱신했다. `expected_dependency_set_digest` 는 네 번 모두 변하지 않았다(같은 루트
`.venv`). 이 절 뒤의 문서 전용 커밋은 접기 대상(`tos/src`·`tos/runtime/src` 의 `*.py`)
밖이라 값을 움직이지 않는다 — 문서 커밋 뒤 명령을 다시 돌려 동일함을 확인했다.

### 7.8 검증

| 검사 | 결과 |
|---|---|
| `pytest tos/tests` | PASS (9500+ · exit 0) |
| `pytest tos/runtime/tests` | PASS (exit 0) |
| `pytest tests/unit/scripts` (병렬·serial 2패스) | PASS — **`pinned_hash_seed` 없이** |
| `pytest tests/tools/test_tos_*.py tests/tos_l3` | PASS |
| `black --check` (tos-firewall 스텝과 동일 범위) · `ruff check` | PASS |
| mypy 4종(`tos/src`·`tos/runtime/src`·`tos/tests`·`tos/runtime/tests`, CI 플래그) | PASS |
| `tools/tos_firewall_check.py` · `tos_contract_check[--self-test]` · `tos_completion_status --check` · `tos_spec_status --check` · `tos_size_budget --check` | PASS |

`lint-imports`(레이어 ②)는 이 워크트리에서 실행 불가 — `tos_runtime` 이 공용 venv 에
editable 설치돼 있지 않고 venv 는 읽기 전용이다. CI 의 `tos-firewall` 잡이 설치 후
실행한다. 레이어 ①(AST 게이트)은 통과했고, 이 PR 은 import 를 한 줄만 늘린다
(`tos.canonical._base` → `tos.canonical._canonical_json`, 둘 다 커널 내부).

### 7.9 기존 영속 상태는 이월하지 않는다

이 커밋 **이전**에 쓰인 durable 상태는 이월 대상이 아니다 — paper DB 는 빈 상태에서
시작한다. 구체적으로 `tos_runtime/engine/inbox.py:400,481` 이 durable inbox 행을
`EngineEvent.model_validate(...)` 로 재수화하는데, 이전 프로세스가 쓴 행을 지금 다시
접으면 다른 `event_identity()` 가 나온다. **회귀는 아니다**: 그 id 는 이 PR 이전에도
프로세스마다 달랐다(그게 이 계획이 닫는 결함이다). 다만 첫 부팅 아크가 곧 상태를 쓰기
시작하므로, 「이 커밋 전 상태 + 이 커밋 후 코드」 조합은 만들지 않는다는 것을 여기에
적어 둔다. (review-802 LOW-7)

### 7.10 review-802 조치

| 지적 | 조치 |
|---|---|
| M-1 비용 비율 CI flaky (`ratio < 1.6`, 로컬 25회 중 1회 실패, 최대 1.747) | 게이트를 **구조 단정**으로(집합 없는 클래스의 `__pydantic_core_schema__["serialization"] is None`), 비용은 **쌍측정 + 라운드별 비율의 median**(21×500) 으로 바꾸고 **잡음 바닥 상대 경계**(`1.35 × max(1.0, control)`) 로 재진술. control=순수 `BaseModel` 대 동일한 두 번째 순수 `BaseModel`. 60회 반복 실패 0 |
| M-2 집합 안의 집합이 문서에도 핀에도 없음 | 모듈 docstring 의 silent-miss 목록에 **실측 2시드 출력과 함께** 추가 · 폐쇄 테스트에 금지 핀 `test_no_set_is_nested_inside_a_set` · 같은 자리에 `test_no_model_field_tree_holds_a_stdlib_aggregate`(dataclass/NamedTuple/TypedDict). 4종 전부 뮤테이션 RED 확인 |
| L-3 `test_every_module_is_imported` 가 `sys.modules` 를 봄 | **명시 목록이 스스로 도달하는 집합**(각 모듈의 속성 그래프를 따라감)과 먼저 비교하고 `sys.modules` 는 두 번째 단정으로. 두 배포 루트를 시드로 넣으면 가드가 비어 버린다는 것을 뮤테이션으로 확인해 루트는 제외. 그 과정에서 `tos_runtime.evidence.backup`(동명 함수 re-export 에 가려진 모듈)을 실제로 찾아냄 |
| L-4 렌더 증인이 원래 안 깨지던 모델을 고름 | `venue_constraint_policy.yaml` 추가(파라미터화). 소스는 named-TBD 라 **렌더 산출물**에 대해 돌린다 |
| L-5 모듈 레벨 가변 dict 공유 | `dict(_SORTED_SET_SERIALIZATION)` per-class 사본 + 공유 금지 핀 + 유니온 재진입 멱등 핀 |
| L-6 `_with_sorted_sets` 분기 지역변수 명명 역전 | `original_child`/`dumped_child` 로 통일 |
| L-7 기존 영속 상태 한 줄 | §7.9 |
