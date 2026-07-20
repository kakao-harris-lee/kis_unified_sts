# 설계 문서 #4 — Evidence Store + append-only ledger 계약 (2026-07-20, v1.1)

> **비준 기록**: **2026-07-20 운영자 비준 (v1.1)**. 효력 발생 — IMPLEMENTATION-PLAN-002
> §4 Phase 1(EV-L1)의 ADR-002-016 부분을 그린필드 `tos/src/tos/evidence/`에 순수·비전송
> 데이터 모델 + property test로 작성 착수 승인. **canonicalization PROMOTE 결정 승인**:
> digest-binding substrate를 `tos/canonical/`로 승격해 capsule·evidence가 공유하며,
> 이는 비준·커밋된 capsule 코드(`76546c6f`)의 소량 리팩터(DigestBoundArtifact base/subclass
> 분할 + re-export shim + 에러 alias, §9.1)를 구현 단계 후속 작업으로 유발한다. evidence는
> `id=f(digest)` 미채택(§12 same-id/diff-bytes 충돌 탐지 전제). §9.2 Phase-0 이관 항목
> (bounds 승인·독립 리뷰어·프로덕션 anchor/canonicalization·누락 프로파일 키·record_class
> taxonomy·id 배치 확정)은 별도 게이트로 유지. (독립 비평 리뷰 ACCEPT-WITH-MINOR → MINOR-1~5
> 정정 후 비준.) 운영자 비준 시 효력 —
> [IMPLEMENTATION-PLAN-002](../../tos-spec/src/part-1-foundation/verification/IMPLEMENTATION-PLAN-002.md)
> §4 Phase 1(EV-L1)의 ADR-002-016 부분(§165, line 177–178: "record/receipt identity,
> causal graph, durability class, continuity, gap, integrity-anchor, retention,
> redaction, Replay Capsule, divergence, and non-revival **models**")을 그린필드
> `tos/src/tos/evidence/`에 **순수·비전송 데이터 모델 + property test**로 실현하는
> 프로젝트 측 설계 계약을 확정한다. §9.2 Phase-0 이관 항목(bounds 승인·독립 리뷰어
> 지정·프로덕션 anchor/canonicalization 선택·누락 프로파일 키 신설)은 별도 게이트로
> 유지한다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해
> **non-normative**이며 스펙 텍스트(RFC/ADR/템플릿)를 변경하지 않는다. broker-agnostic
> 원칙(project memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커 사실은 프로젝트 측
> 예시로만 등장하며 규범 주장이 아니다. evidence 레코드 클래스·불변식은 모두
> broker-agnostic이다.
>
> **선행 문서(의존)**:
> - [설계 문서 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 설계 #1 §2.4 레이아웃(`tos/src/tos/evidence/`)에 놓이고 §3.2
>   import 허용목록 안에서만 의존한다(§0.3). **`shared.config`는 허용목록에서
>   제거됨**(전이 secrets 유입 — 설계 #1 §6.1 2026-07-20 항목); evidence 모델은
>   pydantic + stdlib + `tos.*`만 import하고 numpy/pandas·shared.config를 쓰지 않는다.
> - [설계 문서 #2 — Decision Context Capsule + Snapshot 계약 (v2, 운영자 비준·구현됨)](2026-07-20-tos-decision-context-capsule-snapshot-design.md)
>   + 코드 `tos/src/tos/capsule/`. **canonicalization/digest 계약을 REUSE한다(재정의
>   금지)** — 상세는 §3, REUSE-vs-PROMOTE 결정은 §0.4·§3.1.
>
> **규범 원천**: `ADR-002-016` (Safety Evidence, Audit, and Deterministic Replay
> Integrity, Status: Proposed). 필드 구조 SoT: `verification/`의
> `SAFETY-EVIDENCE-ENVELOPE-template.yaml`, `EVIDENCE-COMMIT-RECEIPT-template.yaml`,
> `EVIDENCE-GAP-RECORD-template.yaml`, `EVIDENCE-INTEGRITY-POLICY-template.yaml`,
> `EVIDENCE-RUN-MANIFEST-template.yaml`, `REPLAY-CAPSULE-template.yaml`.
>
> **리뷰 이력**: v1 초안 → **v1.1**. 독립 비평 리뷰 **ACCEPT-WITH-MINOR**(CRITICAL 0,
> MAJOR 0) — 핵심 결정(canonicalization PROMOTE + evidence `id=f(digest)` 미채택)은 옳다고
> 확인·유지, MINOR-1~5 정정(§10.1). 수용 서명 게이트는 IMPLEMENTATION-PLAN-002 §3 line
> 153/157 하드 배제(Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)를 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-016 조항별로 **Phase 1(EV-L1)에서 모델·property로 도달 가능한 것과 이연할
   것의 경계**(§1).
2. Safety Evidence Envelope / Evidence Commit Receipt / Evidence Gap Record /
   Evidence Integrity Policy / Replay Capsule의 **데이터 모델 계약**과, 템플릿이 빈
   배열로 남긴 **element 스키마 저작**(§2, gap 1) — ADR §5/§8/§9/§13/§14/§15 prose에서.
3. **append-only ledger 모델**: segment/anchor 표현, tombstone-appended deletion,
   gap-state-as-appended-chain(§2.7, gap 4) — 모델이 레코드를 절대 변경/삭제하지 않는다.
4. **canonicalization + digest 계약의 REUSE + PROMOTE 결정**(§3, gap 6·7): 설계 #2의
   canonicalization/digest-binding substrate를 tos 코어(`tos/canonical/`)로 승격하고,
   evidence는 digest-verification을 REUSE하되 **레코드 identity는 digest에서 파생하지
   않는다**(§12 same-id/diff-bytes 탐지 가능성 보존).
5. **integrity-anchor 추상 Protocol**(§3.4, gap 2): chain·Merkle 둘 다 수용하는
   segment-commitment 계약 + 비프로덕션 잠정 verify 구현(주입 digest, sha256).
6. **append-only·무결성 불변식**(§4): ERI-INV-005/006/007/009/011, §12
   same-id/diff-bytes, ERI-INV-001/014(evidence ≠ authority)를 frozen 모델 불변식/술어로.
7. **gap 탐지·완전성 모델**(§5): §14 상태 기계 전이 술어(gap 9), 완전성 인덱스, causal
   closure.
8. **replay 결정성 모델**(§6, gap 3): divergence 술어(ERI-INV-009), isolation flag
   불변식, EV-L1/predicate 경계.
9. **property-test 하네스 타깃**(§7)과 import-closure 검증 확장(§7.1), run manifest 정렬.
10. **bounds 주입 계약과 누락 프로파일 키의 Phase-0 게이트 플래그**(§8, gap 8).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.**
  ARCHITECTURE-GATE-STATUS의 NO 3종은 그대로다. ADR acceptance는 오직 *실행된*
  evidence로만 온다(project memory `tos-spec-rfc-authoring-track`).
- **런타임 Evidence Store를 구현하지 않는다.** ADR-002-016 §7 표(line 207)는 evidence
  custody 소유자를 "Evidence Store under Evidence Integrity Policy"로 두지만, Phase 1은
  그 store가 산출·보관할 **아티팩트의 순수 데이터 모델과 불변식**만 저작한다. 실제 append,
  durable commit, ingress 수신, projection, index 빌드의 런타임 경로는 비-scope다.
- **durable commit / 실제 durability를 구현하지 않는다.** 따라서 Evidence Commit
  Receipt는 **순수 데이터로만 완결**되고 `status: UNVERIFIED`(RECEIPT line 2)를 벗어날 수
  없다 — durable acceptance 증명은 out-of-scope durable store + anchor service가 있어야
  가능한 L2+이다(§2.3·gap 5). Receipt binding·substitution-rejection 술어만 EV-L1이다.
- **real integrity anchor service를 구현하지 않는다.** §13(line 335) "anchor outside the
  failure domain of the primary evidence store"의 **failure-domain 분리는 런타임 속성**
  이며 순수 모델이 증명할 수 없다. §3.4는 anchor의 *binding 필드 + verify 술어*만 모델링
  하고, real anchor service·common-mode(§13 line 346)·prefix-truncation의 실제 store
  탐지는 EV-L2/L3+Security로 이연한다(ERI-EV-005).
- **egress 런타임을 구현하지 않는다.** 설계 #1 §4대로 tos는 정의상 non-transmitting이다
  (자격증명·라우트·주문구성 부재 + egress 코드 firewall 차단). §10.2의 pre-effect
  receipt→first-byte 순서(ERI-EV-002)는 Phase 1에서 **receipt binding 술어**만 저작한다.
- **authority(ERI-INV-001/014)를 부여하지 않는다.** 모든 아티팩트의 `authority_effect.*`
  / `creates_authority` / `may_mutate_live_state` / `may_release_capacity` / `may_rearm`은
  `false` 상수이며 모델이 이를 강제한다(§4.6). "권한/broker route 경로가 어디에도 없다"의
  전수 증명은 EV-L2/L3(ERI-EV-011)이다; Phase 1은 flag 불변식 + "record/receipt가 authority
  로 쓰이면 거부"(§21 line 511) 술어만이다.

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

evidence 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만), `pyyaml`(정책·
  템플릿 YAML 로드 — 유일 수단). **`numpy`/`pandas`는 import하지 않는다** — evidence는
  구조·해시·순서 모델이지 수치 계산이 없으므로 closure를 최소화한다(설계 #1 §4 잔여
  리스크 최소화).
- tos 자기 자신: `tos.canonical`(§3.1 승격 후 canonicalization/digest substrate),
  `tos.evidence.*`. **`tos.capsule`을 import하지 않는다** — evidence가 capsule을 참조할
  때는 오직 `decision_context_capsule_id`/`_digest`(ENVELOPE subjects line 52, REPLAY
  line 44)의 **스칼라 참조**로만 담고, capsule 모델 클래스를 import하지 않는다(§3.1
  layering 근거).
- **`shared.config` 절대 금지**(설계 #1 §6.1, 설계 #2 §0.3 C1 — 코드 실증): `shared/config/
  __init__.py`가 `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. 정책·
  템플릿 YAML 로딩은 `pyyaml`만으로 수행한다. `shared.{models,indicators,resilience,utils,
  exceptions}`는 firewall 허용이나 evidence 순수 모델은 이들에 대한 필요가 없어 **의존하지
  않는다**(closure 최소화 — 설계 #2 §0.3와 동일 규율).
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`,
  `shared.llm`, `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.evidence`
  closure에 금지·shared.config 부재 assert).

### 0.4 canonicalization REUSE/PROMOTE 결정 요지 (gap 6 — 핵심 아키텍처)

**결정**: (a) 설계 #2 `tos/src/tos/capsule/`의 `canonicalization.py`(CanonicalizationScheme
Protocol·EVL1ProvisionalCanonicalizer·registry·주입 digest_factory)와 `_base.py`의
generic 부분(`FrozenModel`·`ArtifactStatus`·`DigestBoundArtifact`·`derive_id`·
`CapsuleIntegrityError`)을 **tos 코어 모듈 `tos/canonical/`로 승격(PROMOTE)**한다. capsule과
evidence 양쪽이 `tos.canonical`을 import하고, **capsule ↔ evidence 간 직접 import은
없다**. (b) evidence 아티팩트는 **digest-verification 계약을 REUSE**한다
(`canonical_payload_digest`/`canonical_record_digest`/`content_digest ==
H_ver(canonicalize(covered))`). (c) 그러나 evidence 레코드/영수증/정책 **identity는
digest에서 파생하지 않는다**(`id = f(digest)` **미채택**) — §12(line 321·323)이 요구하는
"same identity + different canonical bytes = Critical integrity conflict"를 append-only
ledger가 **표현·탐지 가능**하려면 identity와 content-digest가 분리 가능해야 하기 때문이다.

근거·상세는 §3.1. 이 결정에서 **코드는 옮기지 않는다** — 승격은 후속 구현 작업(§9.1)이며,
설계 #1 §3.4가 `shared/determinism` 추출에 쓴 것과 동일하게 **re-export shim**으로 기존
capsule 코드·property test를 green 유지한다.

---

## 1. 범위 매핑 — ADR-002-016 조항별 EV-L1 도달성

EV-level 정의(VER-002-001 line 142–152): **EV-L1 = Model and Property Verification**
(state-machine exploration, model checking, property-based testing, deterministic
simulation). **EV-L2 = Component Fault Test**(controlled failure injection +
authoritative state inspection). Phase 1은 EV-L1만이다. 아래 표는 ADR-002-016 §25의
`ERI-EV-001..012`(acceptance 1:1)와 EVIDENCE-REGISTER-002의 Minimum Level을 기준으로 한다.

| ERI-EV | 요지 | Phase 1(EV-L1) | 근거 |
|---|---|---|---|
| **-004** Duplicate/Reorder/Conflict/Continuity | **EV-L1 core** | idempotency·**same-id/diff-bytes conflict**(§12 line 323)·continuity-reset(§11 315)·child-before-parent 불완전(§12 326)·competing-exclusive(§12 324) 순수 술어 |
| **-006** Causal Ordering & Time Ambiguity | **EV-L1 core** | ordering priority(§11 306–311)·no cross-continuity subtract(§11 313)·overlapping-uncertainty ⇒ ambiguous-not-sorted(§11 313) 순수 술어 |
| **-008** Historical Baseline & Schema Replay | **EV-L1 core** | exact-baseline binding + UNSUPPORTED_BASELINE/INCONCLUSIVE(§15 404) + current-rule = distinct named result(§15 409) 상태 술어 |
| **-007** Isolated Replay & Divergence | **EV-L1 core(predicate) + Security tail 이연** | divergence 술어(ERI-INV-009 line 170) + isolation flag 불변식(§6, gap 3)이 L1; "no live path" 전수(§15 380)는 L2+/Security |
| **-010** Retention/Compaction/Supersession/Deletion | **EV-L1 core(predicate) + Security tail 이연** | supersession-lineage closure·economic-horizon dominates·compaction-preserves-reconstructability·tombstone(§17)이 L1; 실제 deletion + single-admin dual-control은 L2+ |
| -001 Complete Immutable Causal Chain | **predicate-only** | causal-closure + gap-on-omission 술어만(§5); owning-boundary 실제 capture(§9 240)는 런타임 ⇒ L2+ |
| -005 Mutation/Deletion/Fork/Anchor/Restore Detection | **predicate-only** | chain/Merkle verify 술어(§3.4)가 L1; insider·infra·real-restore·common-mode(§13 346)는 L2+/Security |
| -009 Redaction/Export/Secret/Custody | **predicate-only** | redaction-preserves-digest/field-presence(ERI-INV-010 line 174)이 L1; unauthorized-access·secret-injection(§16 426)은 L2+/Security |
| -012 Recovery Non-Revival & Reconstruction | **predicate-only** | non-revival(ERI-INV-012 line 182) + branch-preservation(§18 456) 술어만; real failover/restore·incident 조립(§19)은 L2+ |
| -002 Pre-Effect Durability & Receipt Binding | **not Phase-1** (receipt-binding 술어만 파생) | first-byte vs persistence race(§10.2 282)는 fault injection ⇒ L2+. "receipt가 exact request/scope/policy/continuity digest에 bind" 술어는 모델에서 파생되나 durability 증명은 아님(§2.3, gap 5) |
| -003 Outage & Emergency Path Confinement | **not Phase-1** | §10.3 emergency journal·§18 outage는 fault injection ⇒ L2+ |
| -011 Broker/External/Non-Trade Conservatism | **not Phase-1** (+Broker) | "missing ≠ non-effect"·"cancel-ACK ≠ FQP"(§1 25, §20 493)는 outcome enum이 구조적으로 지지하나 항목 evidence는 +Broker ⇒ L2+ |

**Phase-1 EV-L1 property 타깃(core)**: `-004, -006, -008`(+`-007, -010`의 core, Security
tail 이연). **predicate-only(EV-L1-complete 주장 금지, gap 6 discipline)**: `-001, -005,
-009, -012`. **not Phase-1**: `-002, -003, -011`(002·011은 모델에서 파생되는 순수 술어를
가지되 EV 항목 evidence로 주장하지 않는다).

> **Phase 1 완결 주장 규율(설계 #2 §7 상속)**: Phase 1은 *모델 + property test 저작*
> 까지다. EV-L1 core 항목조차 **evidence acceptance가 아니다** — VER register의 Owner/
> Reviewer는 TBD이고 수용은 Independent-Safety-Reviewer(저자 아님)의 별도 서명 게이트
> (IMPLEMENTATION-PLAN §3 line 153/157)다. 어떤 항목도 "EV-L1-complete"로 주장하지 않는다.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True,
extra="forbid")`, 설계 #2 `tos.canonical.FrozenModel` REUSE)로 저작한다. 모든 필드는
canonical 템플릿의 필드명을 그대로 쓴다(스펙 용어 = 코드 용어, 설계 #1 §2.4). frozen은
ERI-INV-005(line 154–156, "Raw Evidence Is Append-Only")의 레코드 수준 실현이다 — 어떤
필드도 사후 변경 불가하며, **모델에는 update/delete 연산이 존재하지 않는다**(§2.7).

### 2.0 append-only ledger 골격 (모델의 중심)

ledger는 **불변 레코드의 append-only 시퀀스**다. lifecycle 변화(correction·supersession·
deletion·gap-state 전이)는 **원본을 변경하지 않고 새 레코드를 append**하여 표현한다. 이것이
gap 4(retention/deletion vs append-only 긴장)의 해소 기반이다:

- **supersession**: 새 envelope의 `supersedes_record_id`(ENVELOPE line 100, **covered**)가
  전방 참조. 원본은 불변으로 남고 둘 다 보존된다(§17 line 443 "Superseded and failed
  records remain linked").
- **correction 역참조는 저장하지 않는다(파생)**: `corrected_by_record_id`(ENVELOPE line
  101)를 원본에 사후 기입하면 append-only 위반이다. 따라서 이 필드는 **파생 back-reference**
  (완전성 인덱스 §12 line 329가 전방 스캔으로 계산)로 취급하고 canonical digest preimage
  에서 제외한다(§3.3). 권위 있는 correction 링크는 새 레코드의 `supersedes_record_id` +
  CausalLink(edge_type=`CORRECTION`)다. (설계 #2 §2.5의 `cut_compatible` 파생-술어 기법과
  동형: 템플릿 바이트 정렬 유지 + 불변성 보존.)
- **deletion = tombstone-appended record**(§2.6): 실제 삭제 대신 Tombstone 레코드를 append.
- **gap-state 전이 = appended chain**(§2.7): status 필드 mutate 대신 새 GAP-RECORD를 append.

### 2.1 Safety Evidence Envelope (§8, template SoT 정렬)

`SAFETY-EVIDENCE-ENVELOPE-template.yaml`(111 line) 구조를 1:1 모델링한다. 필드를 **3레이어**
로 분류한다(§3.3 digest 커버리지에 사용):

- **Layer-0 (identity/meta outputs, self-excluded)**: `evidence_record_id`,
  `idempotency_id`, `status`(=`record_outcome`가 아니라 lifecycle 마커; 템플릿 line 2
  `status: DRAFT`), `canonicalization_version`(모델이 담되 §3.3에서 제외). — §3.3.
  **identity는 digest에서 파생하지 않는다**(§3.1).
- **Layer-1 (covered — economic effect·decision을 바꿀 수 있는 모든 필드)**: `record_class`,
  `record_outcome`, `schema_id/version`, `evidence_integrity_policy_id/_generation/_digest`,
  전체 `source`, 전체 `scope`, 전체 `subjects`, `causality`(causal_links 포함, §2.5),
  `payload`(raw/canonical digest·content_type·byte_length·confidentiality/redaction class),
  `time_evidence`, `lifecycle.durability_class`/`retention_class`/`legal_hold_ids`/
  `supersedes_record_id`, `authority_effect.*`(전부 false 상수, §4.6). — ADR §8 line 216–232.
- **Layer-2 (파생/역참조, self-excluded)**: `lifecycle.corrected_by_record_id`(§2.0 파생),
  `integrity.evidence_commit_receipt_id`(receipt는 record 발행 *이후* 산출되므로 record
  digest preimage에 넣을 수 없음 — §2.2 순서). — §3.3.

> **integrity 블록의 위치(§2.4)**: `integrity.{source_signature_or_mac, integrity_key_id,
> predecessor_commitment, segment_id}`는 ledger 배치 시 결정되는 값이다.
> `predecessor_commitment`·`segment_id`는 **레코드가 어느 segment의 어느 위치에 놓이는가**
> 로 정해지므로(§2.4 anchor 모델), payload digest preimage와 분리한다 — envelope의
> `canonical_payload_digest`는 payload에 대한 것이고, ledger membership 무결성은 segment
> commitment(§2.4)가 별도로 담당한다(§13 line 335 "content-addressed" = 레코드, "chained
> OR Merkle" = segment 두 층 분리).

**identity 필드 계약(gap 1의 일부 + §12 실현)**:
- `evidence_record_id`: **globally unique**(§8 line 218). 한 번 생성되어 retry/replication/
  export/replay 전반에 안정(§12 line 321). digest에서 파생하지 **않는다**.
- `idempotency_id`: **stable idempotency identity**(§8 line 218). 같은 논리적 emission의
  재시도에 걸쳐 동일. same idempotency_id + same `canonical_payload_digest` ⇒ idempotent
  dup(§12 line 322).
- **왜 digest-파생 id를 쓰지 않는가**(§3.1 핵심): §12 line 323 "same identity + different
  canonical bytes = Critical integrity conflict"와 §22 line 523 "Same record ID carries
  different bytes ⇒ contain and preserve both"를 **모델이 표현·탐지**하려면
  evidence_record_id ⊥ canonical_payload_digest여야 한다. id=f(digest)면 same-id는 곧
  same-bytes를 함의하여 §12-323이 vacuous가 되고 ERI-EV-004의 conflict 술어가 검증 대상을
  잃는다.

### 2.2 Evidence Commit Receipt (§5.4/§10.2, template SoT 정렬)

`EVIDENCE-COMMIT-RECEIPT-template.yaml`(33 line, 전 scalar) 1:1 모델링. digest-bound
아티팩트(§3.2: `canonical_record_digest`가 대상 레코드의 digest에 bind). **Phase 1 순수
데이터로 완결되나 아무 durability도 증명하지 못한다**(gap 5):

- `status: UNVERIFIED`(line 2)는 Phase 1에서 **유일한 정직한 상태**다. "durably accepted"
  (§5.4 line 106–108)를 증명하려면 out-of-scope durable store + anchor service가 있어야
  하므로, 모델만으로는 UNVERIFIED를 벗어날 수 없다. 이는 결함이 아니라 scope 경계다
  (ERI-EV-002 = not Phase-1, §1).
- **EV-L1 술어(파생, 항목 주장 아님)**: (a) **binding** — receipt는 정확히 하나의 record
  digest(`canonical_record_digest`) + 하나의 `evidence_integrity_policy_generation` + 하나
  `store_continuity_id`에 bind하고, `valid_for_request_digest`/`valid_for_scope_digest`/
  `valid_for_egress_generation`을 담는다(§10.2 line 284). (b) **substitution-rejection** —
  다른 request의 receipt(`valid_for_request_digest` 불일치), stale/mismatch/obsolete
  policy·continuity의 receipt는 거부(§10.2 line 286, §22 line 522). 이 두 술어는 순수
  함수로 property 가능하나, "durable acceptance" 자체는 증명하지 않는다.
- `creates_authority`/`creates_capacity`/`permits_broker_transmission`/`may_rearm` = false
  (line 25–28, §4.6). "A valid Commit Receipt proves only durable acceptance, not
  correctness/authorization"(§1 line 17); receipt-as-authorization은 §23.5(line 554) 기각.

### 2.3 Evidence Gap Record (§14, template SoT 정렬 + 상태 기계 gap 9)

`EVIDENCE-GAP-RECORD-template.yaml`(55 line) 1:1 모델링. **template에 `content_digest`
필드가 없음**(실측 확인)에 유의 — gap 레코드의 무결성은 self-digest가 아니라 **ledger
membership + segment commitment**(§2.4)에서 온다. gap 레코드는 evidence다(ERI-INV-004
line 150, 실패·denial·gap은 first-class).

- 헤더: `gap_id`(logical gap identity, 안정), `status`(§2.7 상태 기계), `detected_by`,
  `detected_at_time_snapshot_id`, EIP id/gen.
- `affected_scope`(line 8–20): 12개 id-list. `gap.{gap_type, expected_record_classes,
  missing_or_conflicting_ids, expected_sequence_start/end, observed_branches(§2.5),
  affected_causal_roots, economic_effect_unknown:true}`.
- `response.{new_risk_blocked:true, containment_generation, capacity_treatment:
  CONSERVATIVE_UNKNOWN, existing_protection_preserved:true, escalation_id}`.
- `repair.{recovered_record_ids, recovery_sources(§2.5), repair_method, remaining_
  uncertainty:UNKNOWN, independently_reviewed:false}`.
- `authority_effect.{closes_unknown, releases_capacity, creates_live_authorization,
  may_rearm}` = **전부 false**(line 46–50, §4.6) — gap 레코드는 어떤 상태에서도 UNKNOWN을
  닫거나 capacity를 풀거나 re-arm하지 못한다(§1 line 25).

### 2.4 append-only ledger: segment / integrity anchor 모델 (§13, gap 2 데이터 면)

§13(line 335)의 두 층을 별개로 모델링한다(§2.1 주석):

1. **record content-addressing**: 각 envelope의 `canonical_payload_digest`(§3.2 REUSE).
2. **segment commitment + integrity anchor**: 순서 있는 레코드 segment에 대한 인증된
   commitment. 모델 요소:
   - `EvidenceSegment`: `segment_id`, 순서 있는 `record_ids[]`(+각 위치), `store_continuity_id`
     (§11 line 315 restart/restore/reset ⇒ 새 continuity), `store_generation`,
     `policy_generation`, `key_generation`, `segment_commitment`(§3.4 scheme 산출),
     `predecessor_commitment`.
   - `IntegrityAnchor`(§5.7 line 118–120): `anchor_id`, `segment_commitment`(대상),
     `store_continuity_id`, `policy_generation`, `key_generation`, **`predecessor_anchor`**
     (anchor 체인), `anchor_cadence_ms`(주입 bound — §8/gap 8). "detects mutation; does not
     validate the safety decision"(§5.7 line 120)를 모델 주석·불변식으로 명시.
   - RECEIPT의 `durable_segment_id`/`durable_position`/`integrity_anchor_predecessor`/
     `store_continuity_id`/`store_generation`(line 10–14)가 이 segment/anchor에 대한 receipt
     측 참조.
- **failure-domain 분리(§13 line 335)는 모델링하지 않는다**(런타임, §0.2) — anchor의 binding
  필드와 verify 술어만 L1이다. real "anchor outside failure domain"·common-mode(§13 346)는
  L2+(ERI-EV-005 predicate-only, §1).

### 2.5 미해결 element 스키마 저작 (gap 1)

템플릿이 빈 배열로 남긴 원소 스키마를 ADR prose에서 저작한다(설계 #2 gap-1 저작과 동형).
각 원소는 frozen 모델이며, 인용은 필드 근거다.

**(A) ENVELOPE `causal_links[]`(line 69)** — Causal Link(§5.5 line 110–112):

| 필드 | 값 | 근거 |
|---|---|---|
| `edge_type` | enum{`INTENT, APPROVAL, AUTHORITY, CAPACITY_COMMIT, CAPABILITY_CLAIM, PROFILE_ACTIVATION, TRANSMISSION_ATTEMPT, BROKER_EVENT, CORRECTION, HALT, RECOVERY`} — **현재 잠정 11종** | §5.5 line 112 |
| `target_id` | predecessor의 immutable identity | §12 line 325 |
| `target_digest` | predecessor의 immutable digest | §12 line 325 |

- **불변식**: `target_id`·`target_digest` 둘 다 필수·non-null(mutable URL/filename/dashboard
  row/"latest" alias는 표현 불가 ⇒ 구성 실패, §12 line 325). **timestamp-only link 금지**
  (§5.5 line 112) — time은 `time_evidence`에만 있고 causal edge가 아니다. child가 parent보다
  먼저 도착하면 incomplete chain(§12 line 326)이며 parent 존재/유효를 증명하지 않는다.
- **edge_type은 closed set이 아니다(MINOR-1)**: ADR §5.5 line 112는 "such as"(예시적·비배타)
  이므로 위 11종은 **잠정**이며 Phase-0(§9.2 item 5 record-class matrix/causal-parent rules)
  에서 확장 가능하다. 등록되지 않은 미지 edge_type은 **fail-closed**(구성 불가)이고 확장은
  정책 승인으로만 열린다.

**(B) EIP element 5종** — Evidence Integrity Policy(§5.3):

- `durability.record_class_rules[]`(line 21) — `{record_class, durability_class∈{PRE_EFFECT_
  DURABLE, POST_EFFECT_BOUNDED, EMERGENCY_DURABLE, DERIVED_REBUILDABLE}(§10.1 273–278),
  required_replication:int|null(주입), acknowledgement_rule}`. 규칙 없는 클래스 ⇒
  `DENY_IF_UNSPECIFIED`(EIP line 20) ⇒ new risk 차단.
- `completeness.required_causal_parent_rules[]`(line 40) — `{record_class,
  required_parent_edge_types:[CausalLink.edge_type]}`. 요구 parent 누락 ⇒ incomplete chain
  ⇒ gap(§12 line 326, §14). (record-class matrix + causal-parent rules = §27 Q5·§28 gate 2.)
- `completeness.source_sequence_rules[]`(line 41) — `{source_class,
  requires_monotonic_local_sequence:bool, continuity_reset_creates_new_identity:bool,
  gap_or_dup_across_continuity_reconcilable_not_hideable:bool}`. §11 line 309·315.
- `retention.record_class_rules[]`(line 47) — `{record_class, horizons:[{BROKER_CORRECTION_
  LATE_FILL, IDEMPOTENCY_REPLAY, ECONOMIC_EFFECT, SAFETY_REVIEW, INCIDENT_LEGAL_HOLD,
  VERIFICATION_ACCEPTANCE}](§17 434–439), effective_horizon="longest applicable"(§17 432),
  min_retention_ms:int|null(주입, dossier §6 MIN_evidence_retention_ms)}`.
  `economic_effect_dominates_retention`(EIP line 51)와 결합(§4.5, gap 4).
- `access_and_redaction.redaction_profiles[]`(line 59) — Redaction View(§5.10, §16):
  `{profile_id, removed_fields:[str], tokenized_fields:[str], preserves_canonical_digest:
  true, preserves_field_presence:true(§16 423 reviewer가 redaction을 탐지 가능),
  preserves:[ORDERING, QUANTITIES, ECONOMIC_EFFECT, IDENTITIES, SCOPE, OUTCOME](§16 422)}`.
  ordering/quantity/authority/effect/independence 필드를 제거하는 profile은 INVALID
  (ERI-INV-010 line 174, §22 line 528).

**(C) GAP `observed_branches[]`(line 28) / `recovery_sources[]`(line 41)**:

- `ObservedBranch` — `{branch_id, segment_id, head_commitment, store_continuity_id,
  store_generation, record_ids_in_branch:[str]}`. fork/conflicting-restore(§13 341) 시 모든
  branch 보존, **last-write-wins merge 금지**(§18 line 456, §22 line 523).
- `RecoverySource` — `{source_ref, custodian, acquisition_method, acquisition_time_snapshot_id,
  transfer_history:[str], remaining_uncertainty:enum}`. §14 line 372(repair는 source/method/
  uncertainty/custody와 함께 **append**) + §19 line 474(custody 필드). repair는 interval을
  rewrite하지 않고 former strength를 복원하지 않는다(§14 372) — §2.7·gap 5.

**(D) REPLAY element 4종** — Replay Capsule(§15):

- `normalized_view_versions[]`(line 32) — `{view_id, transform_identity, transform_version,
  raw_record_digests:[str]}`. raw digest·transform identity 참조, raw를 덮어쓰지 않음
  (§5.9 line 126–128, ERI-INV-005).
- `source_continuity_vectors[]`(line 40) — `{source_continuity_id, workload_identity,
  first_local_sequence, last_local_sequence, committed_prefix_position}`. cross-continuity
  monotonic는 subtract 금지(§11 313); reset ⇒ 새 identity(§11 315).
- `documented_nondeterministic_boundaries[]`(line 56) — `{boundary_id, description,
  bounded:bool, seed_ref}`. `bounded=false`(unbounded) ⇒ 결과 ∈ {INCONCLUSIVE, DIVERGED},
  never MATCH(ERI-INV-009 line 170).
- `tolerances[]`(line 58) — `{field_ref, tolerance_kind∈{EXACT, ABSOLUTE, RELATIVE},
  tolerance_value:주입|null}`. safety-relevant 필드는 EXACT 요구(§15 line 407); tolerance가
  DIVERGED를 MATCH로 바꿀 수 없다(§6, gap 3).

### 2.6 Tombstone 레코드 (gap 4 — deletion을 append로)

§17(line 443)의 compaction/destructive deletion을 **모델이 레코드를 삭제·변경하지 않고**
표현한다. Tombstone은 하나의 appended envelope(record_class=`TOMBSTONE`)이며:

- 대상 레코드(들)의 `canonical_payload_digest`·`segment_commitment`(§17 line 443 "retained
  commitments, tombstones, causal indexes, source continuity, and raw material") 보존 참조.
- `deletion_approval_ref`: approved policy + effective-human **dual control** + scope proof +
  expired-holds + **economic-lifetime-ended proof**(§17 line 443). Tombstone은 그 자체가
  `authority_effect.*` false — "Deletion approval creates no authority"(§17 line 443).
- **불변식(gap 4 핵심)**: open order·potentially-live attempt·UNKNOWN·open position·unreleased
  capacity·unresolved external·active incident·accepted evidence·live scope를 지지하는 레코드
  에 대한 Tombstone은 **거부**(§17 line 441, ERI-INV-011 line 178). ⇒ "compaction preserves
  reconstructability"가 property로 검증 가능하다: Tombstone append 후에도 (i) segment
  commitment가 여전히 verify되고 (ii) causal index가 여전히 close된다(§5.3). 모델은 raw
  payload 저장 회수를 표현하지 않고 **commitment 보존**만 표현하므로, reconstructability가
  결코 손상되지 않음을 순수 술어로 보인다.
- **caveat(MINOR-3, tautology 방지)**: 이는 **모델의 tombstone 표현이 commitment 참조를
  보존한다는 construction-invariant**일 뿐이다(모델이 아무것도 실제로 버리지 않으므로). 실제
  저장 compaction이 reconstructability를 보존함(ADR §17 line 443 "independently verified
  snapshot")의 검증은 real store·snapshot 검증을 요하는 **L2+ 이연**이며 Phase 1은 주장하지
  않는다.

### 2.7 Gap 상태 기계 = appended chain (gap 9 + gap 4)

§14(line 369) 상태 전이 `SUSPECTED → CONFIRMED → CONTAINED → REPAIRED →
INDEPENDENTLY_REVIEWED`를 **status 필드 mutate가 아니라 appended chain**으로 모델링한다.
한 `gap_id`에 대한 상태 전이는 각각 **새 immutable GAP-RECORD를 append**(같은 gap_id, 새
status)하며, "현재 상태" = 그 chain의 fold(파생 head). template의 scalar `status`(line 2)는 그
instance의 상태다(append-only 보존). **상태 전이 순서(MINOR-2)**: EVIDENCE-GAP-RECORD-template
에는 prior-state 링크 필드가 **없으므로**(실측: header + `affected_causal_roots[]`뿐), 전이
순서는 **같은 `gap_id` + ledger segment 위치(§2.4 segment commitment)**로만 성립하며
**GAP-RECORD에 신규 링크 필드를 추가하지 않는다**(§2.3 template 1:1 규율 유지).

**전이 술어(property 대상, ERI-EV-004/012)**:

- **전진만, regression·skip 금지**: `SUSPECTED→REPAIRED`(CONTAINED 건너뜀) 불법;
  `REPAIRED→SUSPECTED` 불법.
- **상태별 precondition**: `CONFIRMED`는 detection 근거 필요; `CONTAINED`는
  `new_risk_blocked=true` + `containment_generation` 설정; `REPAIRED`는 `recovered_record_ids`
  + `recovery_sources`(§2.5 C)가 append되어 있고 `remaining_uncertainty` 보존(§14 372 "does
  not restore former evidence strength"); `INDEPENDENTLY_REVIEWED`는 `independently_reviewed
  =true` + reviewer ≠ repairer(§19 독립성; IMPLEMENTATION-PLAN §3 line 153).
- **fail-closed 불변식(§14 372, §1 25)**: pre-effect/capacity/egress/fills/UNKNOWN/external/
  recovery에 영향하는 gap은 **REPAIRED까지도 `new_risk_blocked=true` 유지**; 오직
  INDEPENDENTLY_REVIEWED + governed re-arm(out-of-scope)만이 lift할 수 있고, 그조차 former
  strength를 복원하거나 authority를 revive하지 않는다(ERI-INV-012 line 182).
- **authority_effect 항상 false**: 모든 상태에서 `closes_unknown=false`(gap 레코드는 UNKNOWN
  을 절대 닫지 못함, §1 line 25)·`releases_capacity=false`·`may_rearm=false`(§4.6).
- **§14 line 374 부정 목록**: flat portfolio / omitted query / operator memory / convenient
  replay는 gap을 닫지 못한다 — 모델은 gap closure를 위 전이·appended recovery 이외의 어떤
  입력으로도 표현할 수 없게 한다(closure는 evidence-linked recovery로만).

---

## 3. canonicalization + digest REUSE 계약 + integrity anchor Protocol

### 3.1 REUSE-vs-PROMOTE 결정 (gap 6 — 핵심 아키텍처)

**(a) PROMOTE 결정과 근거.** 설계 #2의 canonicalization/digest-binding substrate를 tos 코어
`tos/canonical/`로 승격하고 capsule·evidence가 공유한다. capsule ↔ evidence 직접 import은
없다.

*근거 1 — layering/의존 방향*: Evidence Store는 무결성 substrate(ERI-INV-005 append-only,
§13 anchoring)로 스펙에서 가장 foundational한 축이다. Decision Context Capsule(ADR-002-018)은
**input-boundary** 관심사이며 evidence를 *산출*하는 subject일 뿐이다(ENVELOPE.subjects.
`decision_context_capsule_id` line 52). `tos.evidence → tos.capsule` import은 무결성
substrate가 leaf input-boundary 패키지에 의존하게 만드는 **layering 역전**이다. evidence가
capsule을 참조할 때는 id+digest 스칼라(§0.3)만 필요하므로 capsule 클래스 import이 애초에
불필요하다. 공유가 필요한 것은 오직 canonicalization + digest-binding **기계**이며, 그것을
core로 올리면 capsule·evidence 모두 한 방향으로 core에 의존하고 서로 독립한다.

*근거 2 — 커먼즈 승격 원칙의 fractal 적용*: 설계 #1 §1.1 "양쪽에 필요하면 cross-import가
아니라 승격"을 tos **내부**에 적용한다(shared/ 커먼즈 아님 — tos 내부 core). canonicalization/
digest substrate는 tos 커널에서 가장 많이 재사용될 조각이며(향후 IMPLEMENTATION-PLAN Phase 1
의 ~28개 ADR 아티팩트 계열이 전부 digest-bound), 소비자가 정확히 2개(capsule·evidence)인
지금이 올바른 home을 확정하는 가장 싼 시점이다. 미루면 매 계열이 `tos.capsule.
canonicalization`을 import해 잘못된 layering을 고착하거나, 나중에 30개 호출부를 옮겨야 한다.

*비용/리스크*: 승격은 코드 이동(후속 구현, §9.1)이며 **이 문서에서 코드는 옮기지 않는다**.
설계 #1 §3.4가 `shared/determinism` 추출에 쓴 것과 동일하게 **re-export shim**(`tos.capsule.
canonicalization` → `tos.canonical.canonicalization` 재노출)으로 기존 capsule 코드·property
test를 green 유지한다. 이동 대상: `canonicalization.py` 전체; `_base.py`의 generic 부분
(`FrozenModel`·`ArtifactStatus`·`DigestBoundArtifact`·`derive_id`·`CapsuleIntegrityError`
→ 승격 시 `ArtifactIntegrityError`로 일반화, `CapsuleIntegrityError`는 alias). 잔류(capsule
로컬): `SnapshotAuthority`·`CapsuleAuthority`·`PolicyRef`(capsule 고유). 모듈명 `tos/canonical/`
은 권고이며 운영자가 `tos/_core/`로 치환 가능하다 — **naming은 load-bearing이 아니고
layering이 load-bearing이다**. docstring의 §3.4/CII-INV-003/ORDER-CONFORMANCE-PROOF 인용은
승격 시 설계 #2 §3·설계 #4 §3, ADR-002-016 §13/§12 병기로 일반화한다.

**(b) evidence는 digest-verification을 REUSE, identity 파생은 미채택.** evidence 아티팩트
(ENVELOPE·RECEIPT·EIP·REPLAY)는 `DigestBoundArtifact`의 **digest 검증**(`<digest_field> ==
H_ver(canonicalize(covered))`, `_base.py` line 217–223)을 REUSE한다. 그러나 **`id =
f(digest)` 파생(`derive_id`, `_ID_FIELD == derive_id(prefix, digest)` 검증, `_base.py` line
224–229)은 채택하지 않는다.** 이유는 §2.1에 상술: append-only ledger가 §12(line 323)
same-id/diff-bytes Critical conflict를 **표현·탐지**하려면 identity ⊥ content-digest여야
한다. capsule은 immutable content-addressed 아티팩트라 `id=f(digest)`가 옳지만(설계 #2 §4.1,
same-id/diff-bytes를 unconstructable로), evidence 레코드는 conflict를 *탐지 대상*으로 삼는
ledger 시민이므로 정반대다. ⇒ 승격된 substrate는 "digest 검증"과 "id 파생"을 분리해야 한다:
digest 검증은 공통 base, id 파생은 capsule이 opt-in하는 mixin/flag로, evidence는 digest
검증만 쓰고 identity는 독립 필드(자체 검증: idempotency_id + digest pairing 술어, §4.4).

**(c) cross-scheme id-collision caveat와 §12의 조화(Phase-0 이관).** `canonicalization.py`
line 23–31의 caveat(canonicalization_version이 digest preimage·파생 id에서 제외되어 다중
scheme 공존 시 cross-scheme id 충돌 가능)는 **id=f(digest)를 쓰는 capsule에 대한 것**이다.
evidence는 id를 파생하지 않으므로 그 충돌 경로가 직접 적용되지 않는다. 다만 evidence의
**digest 비교**(예: envelope의 EIP digest 일치, receipt의 record digest 일치)는 여전히
scheme-relative이므로, 다중 scheme 공존 시 "같은 covered가 다른 scheme에서 같은 digest"를
방지하려면 `canonicalization_version`을 digest 비교 문맥에 bind해야 한다. 이 전체 해소
(version을 preimage/식별에 접거나 namespace)는 프로덕션 canonicalization + id 정책의 몫으로
**Phase-0로 이관**한다(설계 #2 §9.2 items 1/6과 동일 게이트). Phase 1 단일 잠정 scheme에서는
무해하다.

### 3.2 evidence digest-bound 아티팩트 매핑

| 아티팩트 | digest 필드 | id 필드(독립) | covered = ? |
|---|---|---|---|
| Safety Evidence Envelope | `canonical_payload_digest`(+`raw_payload_digest`) | `evidence_record_id`, `idempotency_id` | Layer-1(§2.1) |
| Evidence Commit Receipt | `canonical_record_digest`(대상 레코드에 bind) | `receipt_id` | receipt 발행 필드(§2.2) |
| Evidence Integrity Policy | `content_digest` | `policy_id`(+`generation`) | policy 본문(§3.5) |
| Replay Capsule | `content_digest` | `replay_capsule_id` | baseline+inputs+determinism+expected |
| Evidence Gap Record | (없음 — §2.3) | `gap_id` | — (ledger membership로 무결성) |

`raw_payload_digest`(raw)와 `canonical_payload_digest`(canonical)의 분리는 §5.9 normalized
view / §16 redaction이 raw를 덮어쓰지 않고 canonical 위에서 파생됨을 지지한다(ERI-INV-005/010).

### 3.3 digest 커버리지 + 자기제외 (설계 #2 §3.2/§3.3 상속)

`covered = Layer-1`(§2.1). preimage에서 제외되는 집합(설계 #2 §3.2 규율 상속):
identity/meta outputs(`evidence_record_id`·`idempotency_id`·`canonical_payload_digest`·
`raw_payload_digest`·`canonicalization_version`), `status`(lifecycle 마커 — 발행 전반에서
digest 안정성 유지, 설계 #2 §3.2 item 2·§9.2 item 2 status attestation은 서명 레이어 이관),
서명 필드, Layer-2 파생·역참조(`corrected_by_record_id`·`evidence_commit_receipt_id`).
**TBD/null이 covered에 하나라도 있으면 pre-issuance(status=DRAFT), digest 불가**(설계 #2 §3.2;
`_base.py` line 201–210 DRAFT는 digest/id null 강제).

### 3.4 integrity-anchor 추상 Protocol + 잠정 verify (gap 2)

§13(line 335)은 segment를 "chained **OR** Merkle-equivalent"로 두고, §27 Q2/Q3·§28 gate 1/5는
프로덕션 알고리즘·anchor service를 미승인으로 둔다. 따라서 설계 #2 §3.1 canonicalization
파라미터화와 동형으로:

- **추상 `SegmentCommitmentScheme` Protocol**(chain·Merkle 둘 다 수용) — `CanonicalizationScheme`
  과 병렬:
  - `version: str`
  - `commit(ordered_record_digests) -> commitment`
  - `verify_membership(record_digest, position, commitment, proof) -> bool` (Merkle:
    inclusion proof / chain: 위치까지의 running hash)
  - `verify_append(prev_commitment, appended_digests) -> new_commitment` (append-only /
    prefix 보존)
  - `link_anchor(commitment, store_continuity_id, policy_generation, key_generation,
    predecessor_anchor) -> IntegrityAnchor`
- **잠정 비프로덕션 구현 = hash-chain**(`ev-l1-provisional-chain-0`): `c_i =
  H(c_{i-1} ‖ record_digest_i)`. **레코드 digest·chain hash 모두 설계 #2의 주입
  digest_factory(default `hashlib.sha256`, 비프로덕션)를 REUSE**한다. chain은
  `predecessor_commitment`(ENVELOPE line 92)에 직접 대응하고 prefix 보존(append-only)이
  자명하여 property에 적합. **Protocol이 Merkle을 수용하므로 프로덕션이 chain·Merkle 중
  무엇을 골라도 모델 재작업이 없다**(§27 Q3, Phase-0). anchor cadence의 *timing*은 주입
  bound(§8, gap 8) — 누락 프로파일 키.

**이 Protocol이 EV-L1에서 지지하는 §13 detection 술어(ERI-EV-005 predicate-only, §1)**:
mutation/substitution(레코드 covered 변경 ⇒ 재계산 commitment 불일치)·deletion/prefix-
truncation/suffix-loss(membership/append verify 실패)·fork/conflicting-restore(같은 position에
다른 predecessor_commitment/continuity ⇒ §2.5 observed_branches, no merge)·anchor-rollback/
skipped-interval(predecessor_anchor 불연속)·schema-substitution/canonicalization-disagreement
(선언 version으로 재계산한 digest ≠ 저장 digest)·key-rollback(key_generation 역행)·**§12
same-id/diff-bytes**(§2.1, 중앙 술어).

**정직한 scope 경계**: (i) `source_signature_or_mac`(ENVELOPE line 90)의 **암호학적 검증은
Phase 1 대상이 아니다** — 키 자료가 없고, §13 line 348 "signature verification alone does not
prove completeness/correctness"가 경고하듯 서명은 completeness를 증명하지 않는다. 모델은 이
필드의 *존재·구조*만 담고 MAC 검증은 L2+(키 custody)로 이연한다. (ii) common-mode
(primary+replica) corruption(§13 346)·real "anchor outside failure domain"은 런타임 ⇒ L2+.

### 3.5 EIP는 DigestBoundArtifact인가 (gap 7)

**YES — digest-verified DigestBoundArtifact이되 id=f(digest)는 미채택**(§3.1 (b) 패턴과 동일).
EIP는 `content_digest`(line 5) + `canonicalization_version`(line 6) + `generation`(line 3) +
`status`(line 4)를 갖는다:

- `content_digest == H_ver(canonicalize(covered_policy_content))`. covered = 정책 본문
  (scope·durability·integrity·completeness·retention·access_and_redaction·replay·
  authority_effect). 제외 = `policy_id`·`content_digest`·`canonicalization_version`·`status`.
- `policy_id`는 **generation에 걸쳐 안정**하고 `content_digest`는 generation마다 바뀐다 ⇒
  `policy_id`는 digest에서 파생하지 않는다(evidence 레코드와 동일 "digest-bound, independent
  id" 패턴). `(policy_id, generation, content_digest)`가 특정 버전을 식별.
- **self-describing 정규화**: EIP 자신의 `content_digest`는 자신의 `canonicalization_version`
  scheme으로 계산한다(version은 preimage에서 제외되므로 순환 없음 — `canonicalization.py`
  line 24). ENVELOPE는 `evidence_integrity_policy_id/_generation/_digest`(line 8–10)로
  캡처된 정확한 정책 generation+digest를 bind하고, 이 digest가 알려진 EIP의 content_digest와
  불일치하면 policy-substitution/generation-drift(§21 line 505)로 탐지(EV-L1 술어).

---

## 4. append-only·무결성 불변식

모두 frozen 모델 불변식(구성 실패) 또는 순수 술어(property)로 실현한다.

### 4.1 ERI-INV-005 — Raw Evidence Is Append-Only (line 154–156)

모델에 **update/delete 연산 부재**(§2.0). correction/normalization/redaction/supersession/
migration은 전부 linked 새 레코드/뷰(§2.6 tombstone, §2.7 gap chain, §2.5 normalized view).
property: 임의의 lifecycle 변화 시나리오에서 기존 레코드의 어떤 covered 필드도 불변; 변화는
오직 append로만 관측된다.

### 4.2 §12 same-id/diff-bytes = Critical integrity conflict (line 323) — 중앙 ledger 술어

`evidence_record_id` ⊥ `canonical_payload_digest`(§2.1·§3.1). property(ERI-EV-004 core):
- 같은 `evidence_record_id` + 다른 `canonical_payload_digest`인 두 레코드 ⇒ **Critical
  integrity conflict**, contain + 두 관측 모두 보존(§22 line 523). merge/last-write-wins 금지.
- 같은 `idempotency_id` + 같은 `canonical_payload_digest` ⇒ idempotent dup(§12 line 322,
  dedup).
- 같은 `idempotency_id` + 다른 `canonical_payload_digest` ⇒ conflict(같은 논리 emission이
  발산 content). 
- 다른 identity가 같은 exclusive transition/consumption/effect 주장 ⇒ semantic conflict,
  containment(§12 line 324).

### 4.3 ERI-INV-006 — Causality Is Explicit (line 158–160) / ERI-INV-007 — Forks/Gaps Fail Closed (line 162–164)

- **INV-006 / ERI-EV-006**: ordering은 §11 line 306–311 우선순위(quorum commit index →
  egress journal seq → source-native seq → component continuity+local monotonic → typed
  Causal Links → trustworthy-time interval)로만; cross-host wall-clock alone은 순서를 만들지
  않는다(§11 line 304). cross-continuity monotonic subtract 금지(§11 line 313). overlapping
  uncertainty ⇒ **ambiguous, represented not sorted**(§11 line 313). property: 임의 시각·
  continuity에서 "편한 순서로 정렬"이 표현 불가; 모호는 모호로 남는다.
- **INV-007 / ERI-EV-004·005**: unknown/conflicting/rolled-back/truncated/forked history ⇒
  new risk 차단(§2.7 gap fail-closed, §2.5 observed_branches). property: fork ⇒ ≥2 branch
  보존 + `new_risk_blocked=true` + no merge.

### 4.4 identity 안정성·idempotency (§12 line 321–322)

property: identity는 한 번 생성 후 안정(retry/replication/index/export/replay 불변);
idempotency 술어는 §4.2. (id=f(digest) 미채택이므로 identity 안정성은 "생성 후 불변" frozen
불변식 + ledger 유일성 술어로 강제; digest 파생이 아님.)

### 4.5 ERI-INV-011 — Retention Does Not Define Economic Lifetime (line 178–180)

property(ERI-EV-010 core): retention/expiry/compaction/archival/deletion-approval/legal-hold-
release는 order·attempt·exposure·UNKNOWN·commitment 등 economic effect를 만료시키지 않는다.
`economic_effect_dominates_retention`(EIP line 51) + §2.6 tombstone 거부 불변식. economic
effect 상태는 context/retention lifecycle과 **직교**(설계 #2 §4.5 CII-INV-009와 동형).

### 4.6 ERI-INV-001/014 — Evidence Is Not Authority (line 138–140 / 190–192)

모든 아티팩트의 `authority_effect.*`/`creates_authority`/`may_mutate_live_state`/
`may_transmit_to_broker`/`may_release_capacity`/`may_rearm` = **false 상수**(값이 true면 구성
실패 — 설계 #2 `SnapshotAuthority._all_authority_false` 패턴 REUSE). ENVELOPE line 103–108,
RECEIPT line 25–28, GAP line 46–50, EIP line 72–77, REPLAY line 78–80과 정합. §7 authority
표(line 198–210) + §23.5(receipt-as-auth 기각 554)+ §23.10(audit substitute for prevention
기각 574)을 flag 불변식 + "record/receipt가 capacity/reconciliation/approval/broker
authority로 쓰이면 거부"(§21 line 511) 술어로. **"권한 경로 전무" 전수 증명은 L2/L3
(ERI-EV-011), Phase 1은 flag 불변식 + 거부 술어만**(§0.2).

### 4.7 ERI-INV-003 / ERI-INV-013 (MINOR-5)

- **ERI-INV-003 — Missing Evidence Is Conservative (line 146–148)**: gap fail-closed(§2.7
  `new_risk_blocked=true`) + `capacity_treatment: CONSERVATIVE_UNKNOWN`(GAP line 35)로 실현.
  absence/lag/query-omission/expired-retention/broken-chain은 non-acceptance·cancellation·
  zero-remaining·capacity-release·no-exposure를 증명하지 않는다(§14 line 374 부정 목록과 결합).
- **ERI-INV-013 — Secret Safety (line 186–188)**: payload가 `raw_payload_digest`/
  `canonical_payload_digest`/`encrypted_location` 참조만 담고 **raw credential/key/token을
  저장하지 않는다**(§2.1, §16 line 426)는 **구조적 실현**(§0.3 firewall가 secret 소스 접근도
  차단). secret-injection 탐지 + leaked-secret 대응(§16 line 426)은 L2+/Security 이연.

---

## 5. gap 탐지·완전성 모델 (§14)

### 5.1 gap 탐지 controls (§14 line 354–364) — 순수 술어로 modelable한 부분

§14의 9개 independent control 중 **데이터·순수 술어로 modelable**: source-local sequence+
continuity(§2.5 source_sequence_rules)·authoritative-log revision 대사(ENVELOPE previous/
resulting_authoritative_revision)·intent/attempt/order/fill/position/capacity causal-graph
closure(§5.3)·anchor cadence+segment cardinality(§2.4, cadence bound는 §8)·producer/ingress
receipt 대사(§2.2 binding 술어). **런타임 필요(L2+)**: egress-vs-broker 대사·broker page/
cursor·external/non-trade 비교·periodic independent inventory+replay(§14 line 358–364,
ERI-EV-011 +Broker).

### 5.2 gap 상태 기계 (§14 line 369) — gap 9

§2.7에 상술(appended chain, 전이 술어, fail-closed, authority-false). ERI-EV-004/012 property.

### 5.3 완전성 인덱스 + causal closure (§12 line 329)

Evidence Store가 산출하는 완전성 인덱스(account·Safety Cell·Capacity Domain·authority gen·
profile gen·egress gen·source continuity·intent·attempt·order·EIP gen)를 **파생 인덱스 모델**
로 표현(저장 mutate 아님, §2.0 corrected_by 파생과 동형). causal closure 술어: 한 causal root
(예: intent)에 대해 required_causal_parent_rules(§2.5 B)가 요구하는 모든 edge가 존재하고 모든
child가 parent를 immutable id+digest로 참조하면 chain complete; 하나라도 누락/child-before-
parent(§12 line 326) ⇒ Evidence Gap(§2.3). ERI-EV-001 predicate. **owning-boundary에서의
실제 capture(§9 line 240)는 런타임 ⇒ L2+** — Phase 1은 closure 술어만(ERI-EV-001 = predicate-
only, §1).

### 5.4 §4.3 Phase B downstream 체인 재구성 (설계 #2 §9.1 인계)

설계 #2 §4.3은 capsule의 Layer-2(venue/adm/bindings)를 Phase 1에서 null로 두고 "전체 체인은
downstream 아티팩트 + Evidence Store(#4)에서 재구성"한다고 인계했다. 본 계약이 그 재구성을
소유: capsule `{id, digest}`를 참조하는 downstream(proposal·venue snapshot·order
admissibility·HUMAN-APPROVAL-SET)이 append하는 envelope들의 causal_links(edge_type=`APPROVAL`
등)와 subjects(`decision_context_capsule_id`/`context_generation` line 52–53)를 §5.3 완전성
인덱스로 엮어 §12(line 329) completeness index + §19(line 477–478) lineage로 재구성한다.
capsule 모델 자체는 import하지 않고 id+digest 스칼라로만 참조(§0.3·§3.1). 설계 #2 §4.5
correction lineage(CII-INV-008/009)의 custody = 본 계약의 append-only ledger(§2.0·§2.6).

---

## 6. replay 결정성 모델 (§15, gap 3)

### 6.1 divergence 술어 (ERI-INV-009 line 170–172) — EV-L1

Replay Capsule의 선언 필드에 대한 **순수 함수**로 결과 enum(§15 line 399–405)을 계산:
`compute_result(expected, actual, input_completeness, nondeterminism_bounded, schema_compat,
digest_match, baseline_supported) -> {MATCH, DIVERGED, INCONCLUSIVE, CORRUPT_INPUT,
UNSUPPORTED_BASELINE}`. **불변식(property)**: 다음 중 하나라도 성립하면 결과 ≠ MATCH —
missing input / unbounded nondeterminism(§2.5 D `bounded=false`) / schema incompatibility /
digest mismatch / different safety-relevant result(§15 line 170). ERI-EV-007 core(predicate).

### 6.2 baseline binding + UNSUPPORTED_BASELINE (§15 line 382–395, 404) — EV-L1

Replay Capsule은 baseline(repo/build/deployment·정책 digest·`schema_and_migration_digests`·
`workload_identity_and_key_generations`)과 inputs(raw record ids+digests·integrity anchor
ids·§2.5 D elements·design-#2 digest vectors line 41–45)를 **exact bind**한다. 술어(ERI-EV-008
core): baseline이 지원되지 않거나 변경되면 `UNSUPPORTED_BASELINE`, 절대 PASS 불가(§15 line
407). **current-rule 재평가는 distinct named result이며 historical 결과를 덮어쓰지 않는다**
(§15 line 409, §23.7 line 562 기각) — 상태 술어로 강제(별도 result 레코드, supersede 아님).

### 6.3 isolation flag 불변식 (§15 line 380, ERI-INV-008 line 166) — L1 flag / L2+ 증명

REPLAY.isolation(`live_credentials_present`·`live_broker_route_reachable`·`production_mutation_
endpoint_reachable`·`live_approval_or_authorization_consumable` = false, line 62–65)을 false
상수 불변식으로(§4.6 패턴). **경계(gap 3 line)**: `007 core`(divergence 술어 + isolation
flag 불변식)는 EV-L1; **`007 +Security tail`(no live path 전수 증명 — 실제 topology에서 replay
principal이 live route에 도달 불가)은 L2+**(§0.2). `tolerances`(§2.5 D)가 safety-relevant
divergence를 MATCH로 바꿀 수 없음(§15 line 407)도 L1 술어. `result.{creates_authority,
may_mutate_live_state, may_rearm}` = false(REPLAY line 78–80): "MATCH establishes
reproducibility, not adequacy"(§15 line 407) 주석 불변식.

---

## 7. property-test 하네스 타깃

§1의 EV-L1 도달성에 정렬. 6개 predicate family:

| family | Phase 1 타깃 | 근거 |
|---|---|---|
| envelope canonicalization + digest 검증 | **REUSE 설계 #2 §3.4 (A) must-pass suite** | `tos.canonical` 승격분(§3.1); evidence covered로 재적용 |
| hash-chain/Merkle segment verify | **§3.4 Protocol + 잠정 chain** | ERI-EV-005 predicate; §13 detection 술어(§3.4) |
| idempotency / same-id-diff-bytes / causal-completeness | **core** | ERI-EV-004(§4.2)·ERI-EV-001 predicate(§5.3) |
| gap 탐지 + 상태 기계 | **core(전이)** + predicate(탐지) | ERI-EV-004/012(§2.7·§5) |
| replay divergence / baseline | **core** | ERI-EV-007/008(§6) |
| supersession/tombstone/retention lineage | **core(predicate)** | ERI-EV-010(§2.6·§4.5) |

- **core property**: ERI-EV-004, -006, -008, -007(core), -010(core).
- **predicate-only(EV-L1-complete 주장 금지)**: -001, -005, -009, -012.
- **not Phase-1**: -002(receipt-binding 술어만 파생, §2.2), -003, -011.
- **bound 처리(설계 #2 §7 상속)**: property는 bound를 hypothesis 생성 주입값으로 다뤄 "임의
  유효 bound 하에서 술어가 보수적으로 성립"을 검증한다(특정 값 비의존). 어떤 숫자도
  하드코딩하지 않는다(§8, CLAUDE.md 설정 기반).

### 7.1 import-closure 검증 테스트 (C1 강제 — 설계 #2 §7.1 확장)

설계 #2 §7.1과 동형으로, 서브프로세스에서 `import tos.evidence`(및 `tos.canonical`)만 한 뒤
`sys.modules`를 검사하여 assert: (1) 설계 #1 §2.3 금지 패키지 부재, (2) **`shared.config`·
`shared.config.secrets` 부재**(전이 유입 런타임 포착), (3) `os.environ`/`os.getenv` 미참조,
(4) **`tos.capsule` 부재**(§3.1 layering — evidence closure에 capsule이 없어야 한다). required
check(`tos-firewall`)와 함께 green이어야 §0.3 firewall 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

evidence를 산출하는 모든 property-test run은 `EVIDENCE-RUN-MANIFEST-template.yaml`(설계 #1
§5.1 선례)에 — (1) git commit digest + `tos` 버전, (2) 인터프리터 + 고정 의존성 버전
(pydantic/hypothesis), (3) 실행 환경, (4) 하네스 git digest, (5) **property-test seed**
(hypothesis seed/derandomize, append-only), (6) 소비 설정 아티팩트 digest(EIP + bound 프로파일
+ `canonicalization_version` + `SegmentCommitmentScheme.version`), (7) 산출 아티팩트 sha256 —
을 기록한다. RUN-MANIFEST의 ERI artifacts 배열(line 93–99: safety_evidence_envelopes·
evidence_commit_receipts·evidence_integrity_anchors·evidence_gap_records·access_redaction_
exports·replay_capsules_and_results·chain_of_custody)이 산출물의 SoT 목록이다.

---

## 8. bounds 주입 + 누락 anchor-cadence 키 Phase-0 (gap 8)

`VERIFICATION-PROFILE-002.yaml`은 `status: PROPOSED`(banner: "unapproved or placeholder bound
is not an approved bound"). ADR-002-016 §4(line 87)·§27 Q12(line 656)는 durability/detection/
recovery/retention/replay bound를 approved Verification Profile + EIP 소관으로 못박는다.

- **결정**: 모든 bound(`B_evidence_persist`·`B_evidence_gap_detect`·`B_evidence_gap_contain`·
  `MIN_evidence_retention_ms`·`MAX_replay_start_delay_ms`·anchor cadence·record_class별
  durability/retention)는 **주입 policy 파라미터**로만 모델에 들어온다. 어떤 숫자도
  하드코딩하지 않는다(CLAUDE.md). 값 누락 ⇒ `UNKNOWN` ⇒ fail-closed(new risk 차단).
- **실측 확인(evidence-based)**: VERIFICATION-PROFILE-002.yaml에 존재 —
  `B_evidence_persist`(line 674)·`B_evidence_gap_detect`(681)·`B_evidence_gap_contain`(688)·
  `MIN_evidence_retention_ms`(706)·`MAX_replay_start_delay_ms`(707), 모두 `value_ms: null`/
  MEASURE|APPROVE. EIP는 `segment_commitment`(line 32)·`external_anchor`(33)·`anchor_cadence_
  ms`(34)를 선언.
- **누락 distinct key (Phase-0 게이트 플래그)**: `anchor_cadence_ms`(EIP line 34)·§5.7·§13
  (line 335)·§27 Q3에도 불구하고 **VERIFICATION-PROFILE-002.yaml에 `MAX_anchor_cadence_ms`/
  `B_evidence_anchor`에 해당하는 distinct 프로파일 bound가 없다**(직접 grep 확인: 해당 키
  0건). 이는 설계 #2 §8의 누락 키 발견과 counterpart다. 본 계약은 이 **누락 키를 Phase-0
  인간 게이트(Bounds-Approver, Live-Armer와 분리)의 프로파일 보강 항목으로 플래그**한다 —
  모델은 anchor cadence를 주입 슬롯으로 **선언**하되(누락 시 UNKNOWN fail-closed, anchor-
  cadence gap 탐지 §14 line 361을 충족 주장 불가), 값·키 승인은 Bounds-Approver로 넘긴다.
- 또한 `evidence_integrity_policy` id/gen/digest(dossier §6, profile TBD)·`evidence_location`
  (§ review)도 Phase-0 미승인으로 남는다.

---

## 9. 후속 설계 문서 의존 + Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **`tos/canonical/` 승격(§3.1)**: `tos/capsule/canonicalization.py` 전체 + `_base.py`의
  generic 부분(`FrozenModel`·`ArtifactStatus`·`DigestBoundArtifact`·`derive_id`·
  `CapsuleIntegrityError`→`ArtifactIntegrityError`)을 `tos/canonical/`로 이동, capsule에
  re-export shim(설계 #1 §3.4 precedent), docstring 일반화. **리팩터 범위 명시(MINOR-4)**:
  re-export shim은 **import 경로만** 보존한다 — 실제 작업은 (i) `DigestBoundArtifact.
  _verify_digest_identity`(`tos/src/tos/capsule/_base.py`의 단일 `model_validator`)를
  **base(digest 검증만) / subclass(`id=f(digest)` opt-in)로 분할**하는 클래스 리팩터,
  (ii) `CapsuleIntegrityError`→`ArtifactIntegrityError` alias 시 **에러 메시지 텍스트
  ("CII-INV-003"/"§4.1" 등)에 assert하는 기존 property 테스트가 있으면 그 assertion을 점검·조정**
  (§9.2 item 9 연계)을 포함한다. 기존 capsule property test green 유지. **이 문서에서 코드는
  옮기지 않는다.**
- **설계 #3(EV-L1 하네스)와의 관계**: §7 property 타깃·§7.1 import-closure·§7.2 run manifest는
  설계 #3 하네스가 **실행**한다. `shared.determinism`(추출됨)은 하네스용이지 evidence 순수
  모델 의존이 아니다(설계 #2 §0.3와 동일).
- **의존 방향**: #4(본 문서) ⟸ 설계 #2(canonicalization REUSE·capsule 참조) ⟸ 설계 #1. #3는
  #2·#4의 모델을 실행.

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **프로덕션 integrity-anchor 알고리즘 + chain-vs-Merkle 선택**(§27 Q2/Q3, §28 gate 1/5;
   §3.4). 잠정 chain은 프로덕션 승인을 대체하지 않는다.
2. **프로덕션 canonical serialization + digest/signing 알고리즘 선택**(§27 Q2; 설계 #2 §9.2
   item 1과 공유). `ev-l1-provisional-*`·sha256은 비프로덕션.
3. **cross-scheme id-collision + digest-version binding 해소**(§3.1 (c); 설계 #2 §9.2 items
   1/6과 공유 게이트).
4. **VERIFICATION-PROFILE-002 bounds 승인 + 누락 `MAX_anchor_cadence_ms`/`B_evidence_anchor`
   키 신설**(§8; Bounds-Approver ≠ Live-Armer).
5. **record-class matrix + causal-parent rules 완성**(§27 Q5, §28 gate 2; §2.5 B는 스키마만
   저작, 실제 매트릭스 값은 정책 승인).
6. **retention/compaction/tombstone/deletion 기간 승인**(§27 Q9, §28 gate 7; §2.6 tombstone은
   구조만, 기간·dual-control 정책은 승인).
7. **status attestation 경로**(status가 digest·서명 preimage에서 제외되므로 서명/evidence
   레이어가 lifecycle을 attest — 설계 #2 §9.2 item 2가 본 문서로 인계한 잔여 리스크; 서명 키
   custody는 L2+).
8. Independent-Safety-Reviewer 지정 및 §7 EV-L1 evidence 수용 서명(저자 배제, IMPLEMENTATION-
   PLAN §3 line 153/157).
9. **[열린 질문 / PROMOTE 착수 전 확인]** capsule property 테스트 중 `CapsuleIntegrityError`의
   **메시지 텍스트**(예외 type이 아니라 문자열)에 assert하는 케이스 존재 여부를 §3.1 PROMOTE
   구현 착수 시 확인(MINOR-4 (ii) 연계) — 존재하면 `ArtifactIntegrityError` alias 전환 시
   assertion 조정 필요.

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-20: **v1 초안 최초 작성.** ADR-002-016 EV-L1 실현 계약. 9개 결정 의제(gap 1–9)
  전부 결정 또는 Phase-0 이관 명시. 설계 #1(경계·firewall)·설계 #2(canonicalization REUSE)
  및 canonical 템플릿 6종에 정렬. 핵심 결정: (gap 6) canonicalization/digest substrate를
  `tos/canonical/`로 **PROMOTE**, evidence는 digest-verification REUSE하되 **identity는
  digest-파생 미채택**(§12 same-id/diff-bytes 탐지 가능성 보존); (gap 2) integrity-anchor
  추상 Protocol(chain·Merkle 수용) + 잠정 chain; (gap 4) deletion=tombstone-append + gap-
  state=appended chain; (gap 8) 누락 `MAX_anchor_cadence_ms` 프로파일 키 실측 확인 후 Phase-0
  플래그. 이후 독립 비평 리뷰 대기.
- 2026-07-20: **v1.1 — 독립 비평 리뷰 ACCEPT-WITH-MINOR(CRITICAL 0, MAJOR 0); MINOR-1~5
  정정.** 핵심 결정(canonicalization PROMOTE + evidence `id=f(digest)` 미채택)은 확인·유지
  (구조 변경 없음). MINOR-1 edge_type closed→잠정 11종·Phase-0 확장 가능·미지 fail-closed
  (§2.5 A); MINOR-2 gap-state 전이 순서를 gap_id + ledger segment 위치로 한정(신규 링크 필드
  미추가, template 1:1 유지, §2.7); MINOR-3 compaction reconstructability는 construction-
  invariant이며 실제 store compaction은 L2+ 이연 caveat(§2.6); MINOR-4 shim은 import 경로만
  보존 — validator 분할 리팩터 + 에러 메시지 assert 테스트 점검 명시(§9.1); MINOR-5
  ERI-INV-003/013 번호 배정(§4.7). §9.2 item 9 열린 질문(CapsuleIntegrityError 메시지 assert
  테스트 확인) 추가.
- 2026-07-20: **v1.1 운영자 비준.** canonicalization PROMOTE(`tos/canonical/`) 결정 승인 —
  capsule 코드(`76546c6f`) base/subclass 분할 리팩터를 구현 단계 후속 작업으로 인가. 효력:
  Phase 1(EV-L1) `tos/src/tos/evidence/` 모델+property test + PROMOTE 리팩터 착수. §9.2
  Phase-0 항목·record_class taxonomy·id 배치는 별도 게이트로 유지.

### 10.2 비준 체크리스트 (운영자·독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(런타임 store·durable commit·real anchor service·egress·authority 미구현)과
      §0.3 firewall 준수 선언(numpy/pandas·shared.config·tos.capsule 부재)에 동의.
- [ ] §0.4/§3.1 **canonicalization PROMOTE + evidence identity 비파생 결정**(핵심 아키텍처)과
      그 근거(layering·§12 same-id/diff-bytes 탐지 가능성)에 동의.
- [ ] §1 조항별 EV-L1 도달성 매핑에 동의(특히 -002/-003/-011 not-Phase-1, -001/-005/-009/-012
      predicate-only).
- [ ] §2.5 element 스키마 저작(causal_links·EIP 5종·gap 2종·replay 4종)이 ADR §5/§9/§13/§14/
      §15 prose에 충실함을 확인(gap 1).
- [ ] §2.6 tombstone-append·§2.7 gap-state appended chain이 append-only(ERI-INV-005)를 보존
      하며 reconstructability를 property化함에 동의(gap 4·9).
- [ ] §2.2 Receipt가 Phase 1에서 UNVERIFIED를 벗어날 수 없음(durable store 부재) + binding/
      substitution-rejection 술어만 EV-L1임에 동의(gap 5).
- [ ] §3.4 integrity-anchor 추상 Protocol + 잠정 chain(비프로덕션)과 signature 검증·common-
      mode·failure-domain 분리의 L2+ 이연에 동의(gap 2).
- [ ] §3.5 EIP가 DigestBoundArtifact(digest-verified, independent id)임에 동의(gap 7).
- [ ] §4 append-only·무결성 불변식(§12 same-id/diff-bytes 중앙 술어 포함)과 §4.6 evidence ≠
      authority flag 불변식에 동의.
- [ ] §6 replay divergence 술어·isolation flag(L1) vs no-live-path 전수(L2+) 경계에 동의(gap 3).
- [ ] §7 하네스 타깃 core/predicate 구분과 "EV-L1-complete 주장 금지" 규율, §7.1 import-closure
      확장(tos.capsule 부재 포함)에 동의.
- [ ] §8 bounds 주입 + 누락 `MAX_anchor_cadence_ms`/`B_evidence_anchor` 키 Phase-0 플래그에
      동의(gap 8).
- [ ] §9.2 Phase-0 이관 8항목을 별도 게이트로 유지함에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 ADR-002-016 부분을 `tos/src/tos/evidence/`
에 순수 모델 + property test로 작성 착수 승인(+ §3.1 `tos/canonical/` 승격 후속 작업). §9.2
Phase-0 8항목과 bounds 승인·독립 리뷰어 지정은 별도 게이트로 남는다.
