# TOS 커널 라운드 #2 계획 — egressgw mesh 분리 · deferred 6 입력 · ⓔ step 필수화 · item 6/12 문언 · SendSeal docstring

- **상위**: Phase 5 계획(`2026-09-10-tos-phase5-recovery-governance-plan.md`) §2 결정 5 · §8 처분 5(«커널 라운드 #2 로 묶어 승인 · W1 착지 후 시작, W3 착수 전 선행») · §10(W2-K 후보 · 운영자 확인 6) · Phase 3 계획 §7.11 이월 ⓔ/ⓖ · KIS MOCK transport 계획 §9 잔여 ② · 커널 라운드 #1 계획 §0 공통 규율(커널 편집은 레인 K 한 곳 · 판정은 커널 술어만 · stash/checkout/reset 금지).
- **저작**: 세션 모델 단독 · 서베이 실측(2026-09-11 · main `ba908a80`) 기반 · 권한 부여 0 · EV 상태 변경 0.

## 0. 서베이 실측 (요지)

| 항목 | 실측 |
|---|---|
| `gateway.py` 2007행 | `resolve_broker_applicability`(393–484) + `_deferred_item_verdict`(520–556) ≈ 129행이 최소 분리 단위 · 둘 다 `_verdict`(486–513 · 호출 50곳)·`_positive`(515–518 · 8곳)에 의존 · `_deferred_item_verdict` 는 **context 인자가 없다**(입력 = applicability 뿐) · 호출 지점 `verify_send_boundary` 580–581 |
| 모듈 레이아웃 핀 | `test_egressgw_import_closure.py` `_SUBMODULES`/`_LOADED_SUBMODULES`/명시 import(51–57 · 204–222 · 589–599) — 새 모듈은 세 곳 갱신 전 red · `test_egressgw_package.py:58-64` 모듈 docstring «five are non-authoritative provisional stand-ins» 핀 · M-K1 AST 핀은 `__call__`/`_seal_and_claim` 만 |
| `SendBoundaryContext` | `records.py:690-793` · 팩토리 `send_boundary_context` 817–1000(84 kwargs · 등재 211행) · 런타임 호출 1곳 `compose/context.py:698-762` · deferred 사유 문자열 verbatim 핀 0 · 분할 6/5/6 핀 `test_egressgw_verify_list.py:70-108` |
| ⓔ `step` | `records.py:616` `CommitmentStep \| None = None` · 검증기 조기 반환 678–679 · 프로덕션 4곳 전부 `step=` 전달 · 테스트 39곳 미전달(`test_sinks` 15 · `test_obligation` 9 · `test_transport_wiring` 5 · `test_compose_root` 2 · `test_egressgw_preserved_capacity` 3 · `test_egressgw_evidence_record_seal_fields` 5) · 선택성 핀 0 |
| item 6/12 문언 | `gateway.py` 772·820·828·836(item 6) · 918·927·935·942(item 12) «⚠ provisional stand-in» — 파생(`tos_runtime/brokercap/derive.py:115`)이 착지한 뒤 stale · verbatim 핀 0 |
| SendSeal docstring | `seal.py:150-151` + `gateway.py:1613-1614` «request_bytes_digest 는 account+instrument 단위» — T2 이후 compose 의 digest source 에 따라 attempt 단위(KIS codec) 또는 account+instrument(캡슐 stand-in) · 핀 0 |
| 크기 예산 | `gateway.py` 2007·`records.py` 1027 등재(드리프트 양방향 red) · 1000행 미만 신설 모듈은 무등재 · `tos_contract_check.py` 는 코드 앵커 0(분리 무영향) · 계약 문서 764행의 `gateway.py:939` 인용은 byte-frozen — 드리프트 기록만 |
| W2-K · ⓖ | 커널 테스트 3건이 `RELEASED` 부재·release 메서드 부재를 직접 핀 · ⓖ 는 dedup 서명 `engine/state.py:658-663` · **운영자 확인 6 전 미착수** |

## 1. 범위

| 포함 (레인 K · 커널 + 그 테스트 · 런타임 테스트의 `step` 갱신) | 제외 |
|---|---|
| K-1 `egressgw/mesh.py` 신설(applicability 게이트 + deferred 판정) · `_verdict`/`_positive` → `_base.py` 공유 · `__init__` 재수출 · 레이아웃 핀 3곳 갱신 · `gateway.py` 하향 재등재 · K-2 `SendBoundaryContext` deferred 6 입력 + 주입 분기 · K-3 ⓔ `step` 필수 · K-4 item 6/12 문언·모듈 docstring 정직 재계수 · K-5 SendSeal docstring(2곳) | W2-K(`PROJECTION_ORDER` `RELEASED`·release 메서드) · ⓖ(dedup 해소 세대) — 운영자 확인 6 대기 · 런타임 소스 변경(W3 이 6 입력을 공급 · 이 라운드는 커널 표면만 · `compose/context.py` 무접촉) · 계약 문서 |

## 2. 결정

1. **mesh.py 인터페이스**: `resolve_broker_applicability(nature, context)` 와 `deferred_item_verdict(item, applicability, context)`(공개명 · 언더스코어 제거)를 `mesh.py` 로 이동 · `_verdict`·`_positive` 는 `_base.py` 로 이동해 `gateway.py`·`mesh.py` 가 import(중복 정의 0) · `gateway.py` 는 `from tos.egressgw.mesh import ...` · `__init__.py` 의 `resolve_broker_applicability` 재수출 원천을 `mesh` 로 · `mesh.py` 는 `tos.engine`(TransportNatureLike 등)·`tos.egress`·`tos.brokercap`·`._base`·`.records`·`.vocabulary` 만 import(`gateway` 를 import 하지 않음 — 순환 금지 · import-closure 테스트가 이를 핀).
2. **deferred 6 주입 분기**(Phase 5 결정 5): `SendBoundaryContext` 에 `safety_authority_epoch_current`·`live_scope_valid`·`safety_profile_current`·`deviation_clear`·`incident_clear`·`monitoring_clear: bool | None = None` · 팩토리 kwargs 6개(기본 None) · `deferred_item_verdict`: `NON_BROKER_SYNTHETIC` ⇒ NOT_APPLICABLE(불변) · 그 외: 해당 필드 `is True` ⇒ SATISFIED(사유: «positively supplied by the owning runtime service») · `is False` ⇒ **DENIED**(명시적 음성은 UNKNOWN 이 아니라 거부 — 정직) · `None` ⇒ UNKNOWN(기존 문언 유지 «owning runtime has not landed»). 항목↔필드 사상: 4 `CURRENT_SAFETY_AUTHORITY_EPOCH`↔`safety_authority_epoch_current` · 5 `VALID_LIVE_SCOPE`↔`live_scope_valid` · 7 `HARD_SAFETY_ENVELOPE_VERSIONS`↔`safety_profile_current` · 8 `SAFETY_DEVIATION`↔`deviation_clear` · 9 `SAFETY_INCIDENT`↔`incident_clear` · 10 `SAFETY_MONITORING`↔`monitoring_clear`(닫힌 표 · 표 밖 항목 ⇒ 구조 오류). 런타임은 이 라운드에서 아무것도 공급하지 않으므로 composed 동작 불변(T3 e2e 의 UNKNOWN 집합 {4,5,7,8,9,10} 그대로 green 이어야 한다).
3. **ⓔ**: `GatewayEvidenceRecord.step: CommitmentStep`(필수 · 기본값 없음) · 검증기의 `None` 조기 반환 삭제 · 테스트 39곳에 실제 step 기입(`SEND_REFUSED` 는 그 테스트가 모사하는 정지 단계 · 나머지는 `FIXED_KIND_STEPS`) · 핀: step 부재 구성 ⇒ ValidationError.
4. **K-4 문언**: item 6/12 사유에서 «⚠ provisional stand-in» 제거 · 정직 문언 = «입력은 호출자(런타임 compose)가 스코프 표+INSTANCE 에서 파생해 공급한다(Phase 4 계획 §2 결정 4) — 커널은 공급된 flag 의 양성 여부만 판정» · 모듈 docstring 의 «five are non-authoritative provisional stand-ins» 는 **실제 남은 attestation 수**(item 12 `venue_session_account_facts_current` · item 16 `restrictive_latch_state`·`worst_credible_capacity` + 있으면 추가 — 실측 후 기입)로 재계수하고 `test_egressgw_package.py:62` 핀을 같이 갱신.
5. **K-5**: `seal.py:150-151`·`gateway.py:1613-1614` — «`request_bytes_digest` 의 단위는 compose root 의 digest source 가 정한다: KIS codec 결속(T2) 시 attempt 단위(수량·가격 포함), 캡슐 stand-in 시 account+instrument 단위 — 두 identity 가 다른 값인 것은 여전히 설계» 로 정정.
6. **크기 예산**: `gateway.py` 하향 재등재(분리 후 실측) · `records.py`·`send_boundary_context` 상향 재등재(6 필드/kwargs) · `mesh.py` 는 1000행 미만 ⇒ 무등재 · 계약 문서의 `gateway.py:939` 인용 드리프트는 §7 에 기록만.

## 3. 기각 대안

- `_verdict` 를 mesh 와 gateway 에 중복 정의 → DRY 위반 · `_base.py` 공유.
- `False` 를 UNKNOWN 으로 접기 → 명시적 음성 신호를 잃는다(운영 서비스가 «deviation 있음» 이라 했는데 «모름» 으로 기록).
- 이 라운드에서 W2-K/ⓖ 동시 착지 → 운영자 확인 6 미도착 · 별도 처분.
- 런타임 `context.py` 에서 6 필드를 attestation 으로 공급 → W3 owner 원칙(1차원=1owner) 위반.

## 4. 레인 · 테스트 순서 (라운드 #1 §1.5 규율 · red first)

단일 레인 K(커널 편집 한 곳). 순서: (1) import-closure 3곳에 `mesh` 추가 + `mesh.py` 뼈대 → red→green (2) K-2 필드·사상표 핀(6 셀 극성표: True/False/None × 대표 항목 2) → 주입 분기 (3) K-3 step 필수 핀 → 39곳 갱신 (4) K-4/K-5 문언 + docstring 핀 재계수 (5) 전체 `tos/tests`·`tos/runtime/tests` → mypy/ruff/black → firewall → budget 재등재 → contract/completion/spec `--check`.

## 5. 종료 조건

- `tos/tests`·`tos/runtime/tests` green(«N passed» 줄 인용) · 커널 diff 는 레인 K 커밋에만 · 런타임 **소스** diff 0(테스트만) · mypy/ruff/black 0 · firewall PASS · lint-imports KEPT · budget 0 violations(재등재 포함) · contract/completion/spec `--check` GREEN(bound 문서 무접촉).
- 뮤테이션 각각 red: M1 `False` ⇒ SATISFIED · M2 `None` ⇒ SATISFIED(T3 e2e + 커널 핀) · M3 NON_BROKER_SYNTHETIC 분기 제거(슬라이스 e2e) · M4 `step` 기본값 복원(핀) · M5 `mesh.py` 가 `gateway` 를 import(import-closure) · M6 사상표에서 한 항목 제거(구조 오류 핀).
- 독립 리뷰(Claude 측 `code-reviewer`, 저작자와 분리) approve · 권한 부여 0 · EV 상태 변경 0.

## 6. 운영자 확인 지점

1. (Phase 5 §10 확인 6) W2-K 를 이 라운드 후속 커밋으로 붙일지 — 미확인 시 미착수.
2. `False` ⇒ DENIED 극성(결정 2) — Phase 5 결정 5 문언은 True/None 만 언급.

## 7. 실행 결과 — 라운드 #2 착지 (2026-09-11 · 브랜치 `feat/tos-kernel-round-2` · main `ba908a80` 기점)

| 레인 | 커밋 | 내용 |
|---|---|---|
| K-1/K-2 | `1f36dfe4` | `egressgw/mesh.py` 신설(`resolve_broker_applicability` · `deferred_item_verdict` 공개) · `SendBoundaryContext` deferred 6 필드 + 팩토리 kwargs · 닫힌 항목↔필드 표(표 밖 = `ArtifactIntegrityError`) · `True`⇒SATISFIED · `False`⇒DENIED · `None`⇒UNKNOWN(문언 불변) · `vocabulary→_base` 순환 엣지 제거(`ArtifactIntegrityError` 를 `tos.canonical` 에서) |
| K-3 | `6eeecbe0` | `GatewayEvidenceRecord.step: CommitmentStep` 필수 · 검증기 None 조기 반환 삭제 · 커널 5 + 런타임 테스트 32곳 step 기입 |
| K-4/5/6 | `c8a037ab` | item 6/12 사유 «⚠ provisional stand-in» 제거 · SendSeal docstring 2곳(단위는 compose 의 digest source 가 정함) · 예산 재등재 |
| 테스트 | `44f9f3ee`·`867f6af4`·`a0465f27` | 극성표 18케이스 + M6 구조 오류 · step 필수 핀(M4) · mesh→gateway 무import AST 핀(M5) |
| 처분 | `10205c69` | MEDIUM 3(상대 import 핀 누락 · 사유 문언이 «호출자가 파생했다» 단언 → «파생 책임» · item 12 SATISFIED 의 attestation 표기 복원) + LOW 4(`_verdict` → `records.py` 로 이동해 함수 내부 import 제거 · `_closure_child` · 런타임 attestation 집합 ↔ 커널 docstring 재계수 링크 테스트 · synthetic+`False` ⇒ NOT_APPLICABLE ×6) |
| 잔여 | `c321c89a` | LOW-8 상대 import 해석기(level ≥ 2 포함) · LOW-9 예산 노트 정정 |

- **게이트**: `tos/tests` **9433 passed** · `tos/runtime/tests` **1183 passed** · ruff/black/mypy 0 · firewall PASS · lint-imports 3/0 · budget 0 violations(`gateway.py` 2007→**1849** · `records.py` 1027→**1113** · `send_boundary_context` 211→236 · `mesh.py` 246 무등재) · contract/completion/spec GREEN · 런타임 **소스** diff 0 · bound 문서 무접촉.
- **독립 리뷰**: 1차 needs-attention(MEDIUM 3 · LOW 7 · 동작 결함 0 · M5d 상대 import 생존) → 처분 → 재심 **approve** · 뮤테이션 M1~M7 + M5a~d + M10(synthetic 분기 순서) 전부 red · M8(truthiness) 은 pydantic 경계 정규화로 등가 뮤턴트(수용).
- **K-4 재계수 실측**: 남은 운영자 attestation 은 **3**(item 12 `venue_session_account_facts_current` · item 16 `restrictive_latch_state`·`worst_credible_capacity`) — 커널 정적 분할표 «5 provisional (3,6,12,14,15)» 은 그대로 참이라 유지하고 재계수를 병기 · 런타임 `EgressAttestations` 필드 집합과 링크 테스트로 결속.
- **composed 동작 불변**: T3 e2e(`test_kis_mock_e2e_honesty.py`) UNKNOWN 집합 {4,5,7,8,9,10} green · monkeypatch 대상만 `deferred_item_verdict` 3인자로 기계적 갱신(런타임 테스트 1파일 · 계획 «step 만» 범위 밖 — 사유: 이름·시그니처 변경의 필연적 파급).
- **이월**: 런타임 `load_egress_attestations` docstring «five» (런타임 소스 diff 0 원칙으로 이번 라운드 미수정 → W3 attestation 제거 시 함께) · 계약 문서 764행 `gateway.py:939` 인용 드리프트(byte-frozen · 기록만) · **운영자 확인 ⑵ `False ⇒ DENIED` 극성**(한 분기 · 되돌리기 저비용 — 리뷰어 확인) · **운영자 확인 ⑴ W2-K/ⓖ** 미착수.
