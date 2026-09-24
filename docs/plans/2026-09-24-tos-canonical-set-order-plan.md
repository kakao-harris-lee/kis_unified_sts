# tos 정본 직렬화 — 집합 순서 결정성 복원 (2026-09-24)

- 작성: 2026-09-24 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 측정 시점 main **`b5bb5eb5`**
- 발견: PR #797(첫 부팅) 구현 레인 — 렌더 종료 검사가 **새 프로세스에서** 정책을 재로드해 digest 를 대조하다 잡았다.
- 운영자 결정(2026-09-23): 「커널 수정 계획 → 별도 PR」 · (2026-09-24) `canonicalization_version` **유지**(§2.3).
- 개정: review-798(HIGH 3 · MEDIUM 3 · LOW 5)이 초판의 범위(19종)·정렬 키·단일 초크포인트 주장·파급 서술·핀 강도를 반증했다.
  이 판은 그 실측 위에 다시 쓴 것이다 — 초판과의 차이는 §6.
- 성격: **소형 계획 하나 · 구현 PR 하나(PR #797 머지 뒤 — §4)**. 계약 문서는 건드리지 않는다.

## 0. 한 줄 요약

커널이 digest 를 만드는 **두 경로**가 `set`/`frozenset` 을 `model_dump(mode="json")` 으로 순회 순서(문자열 해시 시드 의존)
그대로 리스트화한 뒤 순서 유의미로 해시한다. 그래서 **같은 내용이 프로세스마다 다른 digest** 를 낸다 — 설계 #2 §3.4
must-pass **(A)-1 결정성** 위반. 경로 ① `DigestBoundArtifact.covered_content()` 에서 **11종**, 경로 ② `event_identity()` 등
`model_dump` 를 직접 해시하는 곳에서 `EngineEvent`(`CORPORATE_ACTION`). 나머지 8종은 **이미 모델별로 `sorted()` 정렬**하고
있다. 처분: 기존 8종과 **같은 키(`sorted()`)** 로 두 경로를 **공유 헬퍼 한 개**에서 정규화하고, 8종의 개별 정렬을 그 헬퍼로
흡수한다(digest 비트 호환).

## 1. 실측 (main `b5bb5eb5`, review-798 재현 포함)

### 1.1 메커니즘

- `tos/src/tos/canonical/_base.py:187` `covered_content()` = `self.model_dump(mode="json", include=set(self._COVERED_FIELDS))` —
  JSON 모드는 `frozenset` 을 순회 순서 리스트로 낸다.
- `tos/src/tos/canonical/canonicalization.py` `_encode` — 매핑은 키 정렬, 시퀀스는 「order-significant」.
- 문자열·`StrEnum` 원소의 순회 순서는 `PYTHONHASHSEED` 를 따른다(정수는 해시가 안정적이지만 순회 순서는 삽입 이력에도
  의존하므로 「항상 안정」은 아니다 — 정렬 대상에서 빼지 않는다).
- 모든 기존 테스트가 digest 를 **한 프로세스 안에서** 계산·검증해 드러나지 않았다.

### 1.2 경로 ① `covered_content()` — 19종 중 **결함 11종**, 이미 정렬 8종

`DigestBoundArtifact` 하위 클래스 중 `_COVERED_FIELDS` 보유 **120종**, 그중 covered 필드(중첩 모델 재귀)에 집합이 있는 **19종**.
review-798 이 시드 8개로 측정: 결함 11종은 8종의 digest, 이미 정렬하는 8종은 1종의 digest.

| 상태 | 모델 | 정렬 수단 |
|---|---|---|
| **이미 결정적 (8)** | `CurrentnessPolicy` · `RestrictiveFenceRecord`(`tos.cur`) · `SafetyDeviationPolicy`(`tos.wdr`) · `SafetyIncidentPolicy`(`tos.sir`) · `TrialEvidencePackage` · `TrialPolicy`(`tos.rlp`) | 모델별 `covered_content` 재정의 / `_sorted_set_fields` — `sorted()` |
| 〃 | `LiveAuthorization` · `ReArmApprovalRecord`(`tos.liveauth`) | `tos/src/tos/liveauth/state.py:54` `field_serializer` — `sorted()` |
| **결함 (11)** | `BrokerCapabilityProfile` · `HumanApprovalRequest` · `HumanAuthorityPolicy` · `HumanDelegationRecord` · `HumanHaltCommand` · `StatementCoverageManifest` · `RecoveryInventoryCut` · `RecoveryObligation` · `RecoveryReadinessDecision` · `OrderAdmissibilityDecision` · **`VenueConstraintPolicy`** ⚠ 배포 채택(09-16) | 없음 |

「⚠ 배포 채택」 중 `CurrentnessPolicy` 는 **결함이 아니다**(초판 오류) — `tos/src/tos/cur/records.py:44-49` 가 이 문제를 이름으로
적고 정렬한다. 이 배포가 당장 막히는 것은 `VenueConstraintPolicy` 하나다.

### 1.3 경로 ② `covered_content()` 를 거치지 않는 digest

`tos/src/tos/engine/records.py:454` `event_identity()` 가 `EngineEvent.model_dump(mode="json")` 을 직접 digest 한다.
`CORPORATE_ACTION` 이벤트의 집합 필드 때문에 시드 0~5 에서 event id 가 6종. 같은 모양: `tos/src/tos/engine/driver.py:536` ·
`:802` · `tos/src/tos/engine/inbox.py:353`. 경로 ①만 보는 스캔·핀은 이 부류를 못 본다.

### 1.4 영속 digest

review-798: 19종 digest 를 값으로 담은 영속 파일 **0** — `config/tos_runtime/paper/*` 는 `canonical_digest: TBD`, 64-hex 리터럴
전수 grep 0. 경로 ② event id 를 담은 영속 픽스처는 구현 레인이 실측한다(§3).

## 2. 처분

### 2.1 공유 헬퍼 하나 — `tos/src/tos/canonical/_canonical_dump.py`(신설)

```python
def canonical_json_dump(model: BaseModel, *, include: set[str] | None = None) -> Any:
    """model_dump(mode="python") → 집합을 sorted() 리스트로 → pydantic_core.to_jsonable_python."""
```

- 순서: `model_dump(mode="python")` → 값 트리에서 `set`/`frozenset` 을 **`sorted()`** 리스트로(원소는 JSON-네이티브화 **전**의
  파이썬 값 — `str`/`StrEnum` 은 문자열 순) → `pydantic_core.to_jsonable_python`. review-798 이 이 경로를 120종 전부에서
  `mode="json"` 과 동일(리스트 정렬 정규화 후 비교)함을 확인했고, 충돌하는 serializer 는 없었다.
- 키가 **`sorted()`** 인 이유: 이미 정렬하는 8종이 쓰는 키와 같아 **그 8종의 digest 가 비트 단위로 그대로**다. 초판의
  `_encode` 토큰 키(길이 우선)는 그 8종의 digest 를 바꿨을 것이다(review-798 HIGH-2).
- 원소가 서로 비교 불가능한 집합(예: 중첩 모델의 집합)이 커널에 있으면 `sorted()` 가 `TypeError` 를 낸다 — 헬퍼는 그 경우
  **조용히 대체 키를 쓰지 않고 거부**하며, 구현 레인이 그런 필드가 있는지 실측해 보고한다(있으면 그 필드만 별도 결정).

### 2.2 두 경로를 헬퍼로 바꾸고, 8종의 개별 정렬을 흡수한다

- 경로 ①: `_base.py:187` 의 한 줄 본문을 `return canonical_json_dump(self, include=set(self._COVERED_FIELDS))` 로 **같은 줄 수로**
  교체한다. **`_base.py` 의 줄 번호가 움직이지 않게** 하는 것이 요구사항이다 — `tos/tests/orthostate/test_orthostate_l2_fault.py`
  가 `_base.py:187/205/209/211` 를 줄 단위로 고정하고(ST-05·06·07·09), `tos-spec/src/part-1-foundation/verification/
  ADVERSE-SCENARIO-SET-002-EVL2-PILOT.yaml` 이 `_base.py:205/211` 를 인용한다. 그 spec 파일이 동결 결속 대상인지 확인하지 않고도
  파급을 0 으로 만든다(review-798 MEDIUM-1). import 한 줄이 필요하면 **함수 안 지역 import** 로 줄 수를 지킨다.
- 경로 ②: `event_identity()`·`driver.py:536/802`·`inbox.py:353` 의 `model_dump(mode="json")` 을 헬퍼로 바꾼다. 이 파일들의 줄 고정
  인용도 구현 레인이 전수 grep 해 **같은 줄 수 교체**를 우선하고, 불가피하면 인용을 내용으로 재유도한다.
- 이미 정렬하는 8종의 `covered_content` 재정의·`_sorted_set_fields`·`field_serializer` 는 **삭제**한다(헬퍼가 같은 키로 같은 결과를
  낸다 — 삭제 전후 digest 동일을 핀으로 증명). 모델별 수단이 여럿인 상태가 이 결함을 11종에 남긴 원인이다.

기각한 대안: 필드별 별칭(새 필드가 빠뜨리면 재발) · `_encode` 확장(집합은 도착 전에 이미 리스트) · `PYTHONHASHSEED` 고정(증상
은폐) · `tuple` 스키마 전환(의미 변경).

### 2.3 `canonicalization_version` 유지 (운영자 확인 2026-09-24)

`ev-l1-provisional-0` 은 비프로덕션 잠정 canonicalizer(설계 #2 §3.4). 결함 11종과 경로 ② 의 digest 는 **내용의 함수가 아니었으므로**
보존할 안정값이 없고, 이미 결정적이던 8종은 비트 호환이다. D5 결정 기록 §1.3-2 의 「digest 값이 바뀌면 `ALGORITHM_ID` 범프」
규율은 **`tools/bcp_digest.py`(BCP digest 도구)의 규율**이지 커널 정본 직렬화의 것이 아니다 — 이 PR 은 `tools/bcp_digest.py` 를
건드리지 않는다.

## 3. 핀 — 「이 가드가 실패하는 구체적 입력」

| 핀 | 실패하는 입력 |
|---|---|
| **프로세스 간 결정성 — 경로 ①**: 19종 각각 대표 인스턴스(집합 필드 원소 **≥ 6**)를 `PYTHONHASHSEED` 가 다른 서브프로세스 **≥ 5** 개에서 만들어 digest 가 모두 같음 | 헬퍼를 `mode="json"` 으로 되돌리면 → 결함 11종이 시드마다 갈려 RED. (원소 6 · 시드 5 에서 우연히 전부 같은 순서일 확률은 무시 가능 — n=2·시드 3 은 25%, review-798 MEDIUM-2) |
| **프로세스 간 결정성 — 경로 ②**: `CORPORATE_ACTION` `EngineEvent` 의 `event_identity()` 를 같은 조건으로 | `event_identity()` 를 되돌리면 → RED |
| **비트 호환 — 기존 8종**: 헬퍼 도입 전 digest(테스트에 골든 값으로 고정)와 도입 후 digest 가 같음 | 정렬 키를 `sorted()` 이외(예 `_encode` 토큰)로 바꾸면 → RED |
| **목록 폐쇄**: 테스트가 `tos` 하위 모듈을 **전부 명시적으로 import** 한 뒤 스캔을 재실행해, 집합 covered 필드를 가진 모델 집합이 결정성 핀 매개변수와 같고 **하한 19 이상**임을 단정 | 새 모델에 집합 필드를 추가하고 핀에 안 넣으면 → RED · import 누락으로 스캔이 0 을 내면 하한에서 RED |
| **경로 ② 폐쇄**: `tos/src` 에서 `model_dump(mode="json"` 결과를 digest 함수에 넘기는 호출부를 AST 로 찾아, 헬퍼 경유가 아닌 곳이 0 | 새 코드가 `compute_digest(x.model_dump(mode="json"))` 를 쓰면 → RED |
| **비교 불가 원소 거부**: 합성 모델(중첩 모델 원소 집합)로 헬퍼가 조용히 대체 키를 쓰지 않고 거부함 | 헬퍼에 `key=str` 폴백을 넣으면 → RED |
| **(A) suite 무회귀** · `test_orthostate_l2_fault.py` 무변경 통과 | `_base.py` 줄 이동 → ST-05~09 RED |

## 4. 순서와 삭제

- 구현 PR 은 **PR #797 머지 뒤**에 연다. #797 이 추가한 결함 고정 테스트
  `tests/unit/scripts/test_render_paper_config.py::test_venue_policy_canonical_digest_is_not_reproducible_across_processes` 와
  `pinned_hash_seed` 픽스처, 렌더 `_subprocess_env()` 의 `PYTHONHASHSEED` 통과를 **이 PR 에서 삭제**한다(그 테스트 자신의 수용 기준).
- 삭제 뒤 런북 절차(`docs/runbooks/tos-paper-boot.md` — 렌더 → 부팅)를 **시드 고정 없이** 이 호스트에서 다시 돌려 R0 가 통과함을
  종료조건으로 한다.

## 5. 운영자 확인

| # | 항목 | 추천 | 실제 |
|---|---|---|---|
| ① | `canonicalization_version` 유지(§2.3) | 유지 | **유지** — 2026-09-24 |

## 6. 초판(커밋 `f50886b4`)과의 차이 — review-798

| 초판 | 이 판 | 근거 |
|---|---|---|
| 결함 19종 · `CurrentnessPolicy` 포함 | 결함 **11종** · 8종은 이미 정렬 | HIGH-1 |
| 정렬 키 `_encode` 토큰 | **`sorted()`** — 기존 8종과 비트 호환 | HIGH-2 |
| 「초크포인트 하나가 부류를 닫는다」 | 경로 **둘**(`covered_content` + `event_identity` 등) · 공유 헬퍼 + AST 폐쇄 핀 | HIGH-3 |
| 파급: 골든 테스트·`completion_status` 앵커 | 파급: 줄 고정 가드 ST-05~09 · spec yaml 인용 → **줄 수 불변 구현**으로 회피 | MEDIUM-1 |
| 원소 ≥3 · 시드 3 | 원소 ≥6 · 시드 ≥5 · 비교 불가 원소는 합성 모델 | MEDIUM-2 |
| 「덤프 전 트리 순회」 | `mode="python"` → 정렬 → `to_jsonable_python`(검증된 경로) | MEDIUM-3 |
| 「33필드」 | 필드 수는 계획에서 뺀다(표는 모델 단위) | LOW |

## 7. 착지 기록

(비어 있음)
