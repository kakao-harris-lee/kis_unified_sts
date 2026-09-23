# tos 정본 직렬화 — 집합 순서 결정성 복원 (2026-09-24)

- 작성: 2026-09-24 · 세션 모델 단독 저작(운영자 지시 2026-09-04) · 측정 시점 main **`b5bb5eb5`**
- 발견: PR #797(첫 부팅) 구현 레인 — 렌더 종료 검사가 **새 프로세스에서** 정책을 재로드해 digest 를 대조하다 잡았다.
  review-797 가 재현(해시 시드 10개 → digest 9종)하고 범위를 넓혔다(MEDIUM-3).
- 운영자 결정(2026-09-23): 「커널 수정 계획 → 별도 PR」.
- 성격: **소형 계획 하나 · 구현 PR 하나.** 계약 문서(Phase-0 완료 계약)는 건드리지 않는다.

## 0. 한 줄 요약

커널 정본 모델 **120종 중 19종**이 covered 필드에 `set`/`frozenset` 을 갖는다. `covered_content()` 가
`model_dump(mode="json")` 으로 그것을 **순회 순서 그대로의 리스트**로 바꾸고, 정본 인코더는 리스트를 순서 유의미로
해시한다. 문자열·`StrEnum` 원소의 순회 순서는 프로세스마다 다른 해시 시드를 따르므로, **같은 내용이 프로세스마다 다른
digest 를 낸다.** 이것은 설계 #2 §3.4 must-pass 불변식 **(A)-1 「결정성: 같은 covered 콘텐츠 ⟹ 같은 digest」 위반**이다.
처분은 **`covered_content()` 한 곳에서 집합을 정본 순서로 정렬**하고, 19종 전부에 대해 **프로세스 간** 결정성 핀을 건다.

## 1. 실측 (main `b5bb5eb5`)

**메커니즘**(인용은 main 기준):

- `tos/src/tos/canonical/_base.py:187` — `covered_content()` = `self.model_dump(mode="json", include=set(self._COVERED_FIELDS))`.
  pydantic 의 JSON 모드는 `frozenset` 을 **순회 순서대로** 리스트로 낸다.
- `tos/src/tos/canonical/canonicalization.py` `_encode` — 매핑은 키 정렬(§3.4 (A)-2), 시퀀스는 「vectors are order-significant」로
  순서 보존. 집합이 여기 도착할 때는 이미 리스트라 구별할 수 없다.
- 순회 순서: 문자열(과 `StrEnum`)의 해시는 `PYTHONHASHSEED` 로 무작위화된다 → 프로세스마다 다름. 정수는 안정적이지만 정렬해도
  무해하다.

**왜 지금까지 안 잡혔나**: (A) suite 와 모든 기존 테스트가 digest 를 **한 프로세스 안에서** 계산·검증한다. 같은 프로세스
안에서는 순회 순서가 일정하다. `print-policy-digests`(프로세스 1) → YAML 전사 → 부팅(프로세스 2)이라는 운영 절차가
처음으로 **두 프로세스 사이**를 건넜다.

**영향 모델 19종**(세션 모델 독립 스캔 — `DigestBoundArtifact` 하위 클래스 중 `_COVERED_FIELDS` 가 있는 120종에서, covered
필드의 애노테이션을 중첩 모델까지 재귀해 `set`/`frozenset` 이 나오는 것):

| 모듈 | 모델 | 집합 covered 필드 |
|---|---|---|
| `tos.brokercap.records` | `BrokerCapabilityProfile` | `final_quantity_proof_rules` |
| `tos.cur.records` | `CurrentnessPolicy` ⚠ 배포 채택(#794) | `required_dimensions` |
| 〃 | `RestrictiveFenceRecord` | `affected_scope` |
| `tos.hag.records` | `HumanApprovalRequest` · `HumanDelegationRecord` · `HumanHaltCommand` | `scope` |
| 〃 | `HumanAuthorityPolicy` | `declared_conflict_roles` |
| `tos.liveauth.records` | `LiveAuthorization` · `ReArmApprovalRecord` | `live_authorization_scope` · `requested_scope` |
| `tos.posttrade.records` | `StatementCoverageManifest` | 11개(`expected_*`·`received_*`·`shared_dependencies`) |
| `tos.rlp.records` | `TrialEvidencePackage` · `TrialPolicy` | 1 · 4 |
| `tos.sbr.records` | `RecoveryInventoryCut` · `RecoveryObligation` · `RecoveryReadinessDecision` | 3 · 2 · 1 |
| `tos.sir.records` | `SafetyIncidentPolicy` | `authoritative_signal_classes` |
| `tos.venue.records` | `OrderAdmissibilityDecision` | `bound_instrument_route` |
| 〃 | `VenueConstraintPolicy` ⚠ 배포 채택(09-16) | `shape_constraints` · `dependency_closure` · `required_constraint_classes` · `admitting_phase_rules` |
| `tos.wdr.records` | `SafetyDeviationPolicy` | 5 |

## 2. 처분

### 2.1 한 곳에서 고친다 — `covered_content()`

`covered_content()` 가 JSON 덤프 **전에** covered 값 트리를 한 번 훑어, `set`/`frozenset` 을 **원소의 정본 토큰 순서로 정렬한
리스트**로 바꾼다. 정렬 키는 원소를 JSON-네이티브로 바꾼 뒤의 `_encode(...)` 토큰 — 문자열·`StrEnum`·정수·중첩 모델이 섞여도
전순서가 서고, 인코더와 같은 규칙이라 「정렬 뒤 인코딩」이 단사성(§3.4 (A)-5)을 깨지 않는다.

기각한 대안:

| 대안 | 기각 이유 |
|---|---|
| 필드마다 `CanonicalFrozenSet` 애노테이션 별칭(`CanonicalDecimal` 선례) | 19종·33필드에 흩어지고, **새 집합 필드 하나가 별칭을 빠뜨리면 조용히 재발**한다 — 이 저장소의 반복 결함 형태(「가드가 자기가 막는다고 말한 것을 허용한다」). 초크포인트 하나가 부류를 닫는다 |
| `_encode` 가 집합을 받게 하기 | 집합은 `_encode` 에 도착하기 전 `model_dump` 에서 이미 리스트가 된다 |
| 테스트·운영 절차에서 `PYTHONHASHSEED` 고정 | 증상 은폐. 커널 불변식 위반은 그대로 |
| 스키마를 `tuple`(순서 있는)로 바꾸기 | 의미 변경(순서가 의미 없는 집합을 순서 있게 만든다) + 19종 API 변경 |

### 2.2 `canonicalization_version` 은 올리지 않는다

`ev-l1-provisional-0` 은 **비프로덕션 잠정 canonicalizer**(설계 #2 §3.4)이고, 집합을 담은 19종의 digest 는 **지금까지 내용의
함수가 아니었다**(시드의 함수였다). 보존할 안정 digest 가 존재한 적이 없으므로 버전 경계를 긋는 것이 오히려 「이전 버전은
결정적이었다」는 거짓 주장이 된다. 원소가 1개 이하인 집합의 digest 는 바뀌지 않는다. 이 판단은 계획 §4 운영자 확인 대상이다.

### 2.3 파급 — 구현 PR 이 **실측**한다

- 저장소 안에 이 19종 digest 를 **값으로** 담은 곳(골든 테스트, `tos-evidence/`·`tos-spec/` 픽스처, `config/tos_runtime/paper/`
  의 `canonical_digest`·`members`) — 구현 레인이 grep·실행으로 찾아 목록화. 원소 ≥2 집합을 가진 인스턴스만 값이 바뀐다.
- `config/tos_runtime/paper/*` 의 `canonical_digest` 는 `"TBD"` 로 두는 것이 정상 형태(채택 계획 §0.1.1)라 파급 없음이 예상된다.
- `completion_status` 앵커(`파일:줄`)가 `_base.py` 를 가리키면 줄 이동을 **내용으로** 재유도한다.

## 3. 핀 — 「이 가드가 실패하는 구체적 입력」

| 핀 | 실패하는 입력 |
|---|---|
| **프로세스 간 결정성**(19종 전부): 각 모델의 대표 인스턴스(집합 필드 원소 ≥3)를 `PYTHONHASHSEED` 가 다른 서브프로세스 3개에서 만들어 digest 가 모두 같음 | 2.1 정렬을 되돌리면 → digest 가 시드마다 갈려 RED |
| **목록 폐쇄**: 테스트가 위 스캔을 런타임에 재실행해 집합 필드를 가진 모델 집합을 구하고, 그 전부가 결정성 핀의 매개변수에 있어야 함 | 새 모델에 집합 covered 필드를 추가하고 핀 매개변수에 안 넣으면 → RED |
| **정렬 뒤 단사성**: 원소가 다른 두 집합 → 다른 digest; 순서만 다른 두 집합 → 같은 digest | 정렬 키를 `str()` 등 충돌 가능한 것으로 바꾸면(예 `1` 과 `"1"`) → RED |
| **(A) suite 무회귀** | 기존 must-pass 5종 전건 통과 |

PR #797 의 `test_venue_policy_canonical_digest_is_not_reproducible_across_processes`(결함 고정 테스트)와 `pinned_hash_seed`
픽스처·렌더 `_subprocess_env()` 의 시드 통과는 **이 PR 에서 삭제**한다 — 그 테스트 자신이 「고쳐지면 RED · 삭제가 수용 기준」이라고
적었다.

## 4. 운영자 확인

| # | 항목 | 추천 |
|---|---|---|
| ① | `canonicalization_version` 유지(§2.2) | **유지** |

## 5. 착지 기록

(비어 있음)
