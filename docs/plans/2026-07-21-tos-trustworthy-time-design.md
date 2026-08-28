# 설계 문서 — tos Trustworthy Time 모델 계약 (ADR-002-008, EV-L1) (2026-07-21, v1.1)

> **비준 기록**: **2026-07-21 운영자 비준 (v1.1)**. 효력 발생 — 이 슬라이스의 모델 +
> property test 작성 착수 승인. **ordering PROMOTE 승인**: `OrderingEvent`/`compare_order`
> (비준·구현된 evidence 코드 `86d8fa4e`)를 전용 `tos.ordering` core 모듈로 승격해
> evidence·time이 공유하며, `tos.evidence.predicates`는 re-export shim으로 ERI-EV-006
> green 유지(설계 #4 §3.1/§4.3/§7 교차-주석은 §9.1 후속). Phase-1은 **TIME-EV를 0건
> 완결**(전 항목 EV-L2+; predicate substrate만). Phase-0 잔존: bounds 승인 + 누락 distinct
> 키 6~7종·독립 리뷰어·ReasonCode/quality 거버넌스·snapshot 스키마 독립 검토.
> (독립 비평 리뷰 ACCEPT-WITH-RESERVATIONS → MAJOR-1 좌표계 봉합 + MINOR-1~5 정정 후 비준.)
> 본 문서는
> IMPLEMENTATION-PLAN-002 §4 Phase 1(EV-L1)의 **ADR-002-008 부분**(§4 line 165–168:
> "the **capacity state machine** … and **authority epoch/lease**, **Time
> Health/continuity**, and **Live Authorization/revocation** models
> (ADR-002-003/007/008) **as pure, non-transmitting models**")을 그린필드
> `tos/src/tos/time/`에 **순수·비전송 데이터 모델 + property test**로 실현하는
> 프로젝트 측 설계 계약이다. 비준 시 효력은 이 슬라이스의 **모델+property test 작성
> 착수 승인**에 한한다. **트랙 A의 첫 §2 코어**(ADR-002-003/007/008 묶음) 중 하나다.
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해
> **non-normative**이며 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.**
> broker-agnostic 원칙(project memory `tos-spec-broker-agnostic`): KIS 등 특정 브로커
> 사실은 프로젝트 측 예시로만 등장하며 규범 주장이 아니다. 시간 domain·health 상태·
> 불변식은 전부 broker-agnostic이다(§4.7 session/tz 포함).
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   본 계약의 모든 모델은 설계 #1 §2.4 레이아웃에 놓이고 §3.2 허용목록 안에서만
>   의존한다(§0.3). **`shared.config` 제거됨**(전이 secrets 유입 — 설계 #1 §6.1
>   2026-07-20 항목); time 모델은 **numpy/pandas도 import하지 않는다**(순수 구조·비교·
>   구간 모델이라 수치 백엔드 불필요 — 설계 #1 §4 잔여 리스크 최소화, 설계 #4 §0.3 규율).
> - [설계 #2 — Decision Context Capsule + Snapshot 계약 (v2, 비준·구현됨)](2026-07-20-tos-decision-context-capsule-snapshot-design.md)
>   + 코드 `tos/src/tos/capsule/`. **`Freshness{within_bound: bool|None}` fail-closed
>   패턴을 REUSE**(§4).
> - [설계 #4 — Evidence Store + append-only ledger 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/evidence/`, `tos/src/tos/canonical/`. **canonicalization/
>   digest-binding substrate(`tos.canonical`)와 ordering primitive를 REUSE한다(재정의
>   금지)** — REUSE-vs-PROMOTE 상세는 §0.4·§5.
>
> **규범 원천**: `ADR-002-008` (Trustworthy Time Architecture, Status: Proposed).
> ADR §8은 **전용 TIME-HEALTH-SNAPSHOT 템플릿을 두지 않는다**(prose-only) — 따라서 본
> 계약은 Time Health Snapshot 스키마를 **§8 prose에서 저작**한다(§2.1, gap 1). 시간
> 표면이 인라인으로 등장하는 SoT 템플릿: `CRITICAL-INPUT-SNAPSHOT-template.yaml`
> (`trustworthy_time` 33–37), `SAFETY-EVIDENCE-ENVELOPE-template.yaml`(`time_evidence`
> 82–87), `DECISION-CONTEXT-CAPSULE-template.yaml`(`time_health_generation` 47),
> `EVIDENCE-COMMIT-RECEIPT-template.yaml`(17–18), `RECOVERY-EVIDENCE-PACKAGE-
> template.yaml`(25–26).
>
> **리뷰 이력**: v1 초안 → **v1.1**. 독립 비평 리뷰 **ACCEPT-WITH-RESERVATIONS**(CRITICAL
> 0, MAJOR 1, MINOR 5): MAJOR-1(§2.6/§5 좌표계 혼동 — `UncertaintyInterval`을
> `local_monotonic_value`와 동일 좌표라 한 것이 `compare_order`의 un-guarded interval 분기
> 안전 전제를 뒤집어 교차-continuity 순서를 야기, §8 line 212 non-subtraction 위반)와
> MINOR-1~5를 정정(§10.1). ordering-PROMOTE 거버넌스 우려는 설계 #4 canonicalization PROMOTE
> 선례(operator+독립리뷰 게이트·이연·shim)대로 **기각**되어 방향 유지. 수용 서명 게이트는
> IMPLEMENTATION-PLAN-002 §3(line 153/157) 하드 배제(Independent-Safety-Reviewer는 본 문서의
> 저자/통합자여서는 안 됨)를 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-008 조항별 **EV-L1 도달성 경계**와 **TIME-EV 0건 완결** 사실(§1).
2. **Time Health Snapshot 데이터 모델 계약**: ADR §8 prose에서 저작한 아티팩트 스키마 +
   빈-배열 element 스키마(`reference_sources[]`·`reason_codes[]`) 저작(§2, gap 1).
3. **runtime clock 없는 monotonic-continuity 모델**과 **교차 continuity 뺄셈 금지 술어**
   (§3, gap 2).
4. **uncertainty interval 표현**(two-sided `[lo, hi]`), UNKNOWN≠0 fail-closed, negative-
   age 미클램프·future-beyond-tolerance 규칙(§3·§4, gap 3).
5. **freshness/uncertainty 모델**: ADR §9 8종 delay class를 주입 슬롯으로 선언(§4, gap 5).
6. **ordering 술어**: ADR §10 우선순위 + overlap⇒AMBIGUOUS를 **이미 배포된 ordering
   primitive REUSE(PROMOTE)** 로 실현(§5, gap 6).
7. **health FSM 전이 보수성**: §6.4 새 generation·non-revival 술어(§6).
8. **REUSE-vs-new substrate 결정**: Time Health Snapshot = `DigestBoundArtifact`(base) +
   service-assigned 독립 `snapshot_id`(`IdDerivedArtifact` 아님); ordering primitive
   PROMOTE; `shared.determinism` 미import; 패키지 위치 `tos/src/tos/time/`(§0.4·§5, gap 6).
9. **불변식 명명 규약**: TIME-INV register 부재 ⇒ 모델 불변식을 **TIME-AC-001..010 /
   SAFE-030..052**에 따라 명명(§0.4, gap 7).
10. **property-test 하네스 타깃**과 import-closure 검증 확장(§7), **bounds 주입 계약 +
    누락 프로파일 키 Phase-0 게이트 플래그**(§8, gap 5).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR-
  002-008 §23(line 528)은 "authorizes design and non-live implementation-planning work
  only"다. ADR acceptance는 오직 *실행된* evidence로만 온다(project memory
  `tos-spec-rfc-authoring-track`).
- **런타임 Trustworthy Time Service를 구현하지 않는다.** ADR §14.1(line 346–348)은 snapshot
  생성·상태 전이의 소유자를 TTS로 두지만, Phase 1은 그 서비스가 산출할 **아티팩트의 순수
  데이터 모델과 불변식·술어**만 저작한다. 실제 상태 전이 엔진·health 평가 루프는 비-scope.
- **실제 clock을 읽지 않는다.** 모델 어디에도 `time.monotonic()`·`time.time()`·
  `datetime.now()` 등 clock read가 없다. `monotonic_continuity_id`·`local_monotonic_value`·
  `wall_clock_observation`은 전부 **opaque 주입값**이다(§3). 이것이 hermetic·결정론 property
  테스트(설계 #1 §2.4)의 전제다. clock 소스·suspension/boot identity 증거는 ADR §22 OQ2
  대로 플랫폼 미정 — 런타임(L2+).
- **egress/전송을 구현하지 않는다.** 설계 #1 §4대로 tos는 정의상 non-transmitting이다.
  §14.6 Egress Gateway 최종 강제(line 366–368)·§8 line 222 egress generation propagation은
  Phase 1에서 **모델·술어**로만 저작하고 실제 전송·전파 메커니즘은 이연한다(ADR §22 OQ6).
- **authority를 부여하지 않는다.** §14.1(line 348) "It SHALL NOT issue live authority or
  classify economic risk." Time Health Snapshot의 authority-effect 플래그는 전부 `false`
  상수이며 모델이 이를 강제한다(§6, 설계 #4 §4.6 `_all_authority_false` 패턴 REUSE). "권한
  경로 전무" 전수 증명은 L2/L3(§0.1과 별개) — Phase 1은 flag 불변식 + "snapshot이 authority로
  쓰이면 거부" 술어만이다.
- **어떤 TIME-EV 항목도 완결하지 않는다(§1, gap 4).** register 최소 레벨이 **전부 EV-L2 이상**
  이므로(EVIDENCE-REGISTER-002.csv line 69–78) Phase 1은 **TIME-EV 0건**을 닫는다. "EV-L1-
  complete 주장 금지"(설계 #2 §7·설계 #4 §7 규율 상속).
- **numeric bounds를 승인하지 않는다.** VERIFICATION-PROFILE-002 bounds 승인·독립 리뷰어
  지정은 Phase-0 인간 게이트(§8·§9).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

time 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만), `pyyaml`(bounds 프로
  파일 YAML 로드가 필요할 때 — 유일 수단). **`numpy`/`pandas`는 import하지 않는다**(순수
  구조·정수/`Decimal` 구간 산술만; 수치 백엔드 불필요 — closure 최소화, 설계 #4 §0.3와 동일
  규율).
- tos 자기 자신: `tos.canonical`(digest-binding substrate), **`tos.ordering`**(PROMOTE될 전용
  ordering core 모듈 — `tos.canonical` 서브모듈 아님, §0.4b·§5·MINOR-2), `tos.time.*`.
  **`tos.capsule`·`tos.evidence`를 import하지 않는다** — capsule/
  evidence가 시간 스냅샷을 참조할 때는 오직 `trustworthy_time_snapshot_id`/`generation`/
  `monotonic_continuity_id`/`local_monotonic_value`/`uncertainty_ms`의 **스칼라 참조**로만
  담고(§2.0), time 모델 클래스를 import하지 않는다. 역으로 time도 그들을 import하지 않는다
  (§5 layering 근거 — 세 패키지는 `tos.canonical`에만 한 방향 의존하는 형제다).
- **`shared.config` 절대 금지**(설계 #1 §6.1): `shared/config/__init__.py`가
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. bounds 프로파일 로딩은
  `pyyaml`만으로 수행한다.
- **`shared.determinism` 미import**(gap 6 결정): 설계 #1 §3.4로 추출된 `shared/determinism`은
  firewall 허용이나 (i) `replay.py`가 `pandas`를 물고(§0.3 numpy/pandas 배제 위반), (ii)
  `lookahead_guard.py`는 backtest look-ahead 탐지이지 **clock-health 프리미티브가 아니다.**
  ⇒ time은 자체 순수 시간 프리미티브를 정의하고(주입 `monotonic_continuity_id`+
  `local_monotonic_value`, clock read 없음, §3) `shared.determinism`에 의존하지 않는다.
  `shared.{models,indicators,resilience,utils,exceptions}`도 time 순수 모델은 필요가 없어
  의존하지 않는다(closure 최소화).
- **금지(직접·전이 모두)**: `shared.execution`, `shared.kis`, `shared.streaming`,
  `shared.llm`, `shared.storage`, `shared.backtest`, `services.*`, `cli.*`(설계 #1 §2.3).
- 이 배제를 능동 강제하는 것이 §7.1 import-closure 검증 테스트다(`import tos.time` closure에
  금지·shared.config·shared.determinism·numpy/pandas·tos.capsule·tos.evidence 부재 assert).

### 0.4 REUSE·substrate·명명 결정 요지 (gap 6·7 — 핵심 아키텍처)

**(a) Time Health Snapshot = `DigestBoundArtifact`(base) + service-assigned 독립
`snapshot_id`, `IdDerivedArtifact` 아님**(gap 6, §2.1 상술). ADR §8(line 194)·§14.1(line
346–348)은 snapshot identity와 TTS `generation`을 **서비스가 할당**한다고 규정한다 —
content-address가 아니다. §8(line 208)은 "wrong … generation … or whose issuer continuity
identity is inconsistent with the declared issuer and signed snapshot provenance"인 snapshot을
소비자가 **거부**하도록 요구한다. 즉 *선언된 identity/generation이 내용과 불일치하는* snapshot이
**표현 가능**해야 탐지·거부가 성립한다. `id=f(digest)`면 same-generation/different-bytes가 표현
불가(same bytes ⟹ same id)이고 §8-208 provenance 불일치 탐지가 vacuous가 된다 — 이는 설계 #4
§2.1/§3.1이 evidence `evidence_record_id ⊥ canonical_digest`로 §12 same-id/diff-bytes conflict를
보존한 것과 **동형**이다. ⇒ Time Health Snapshot은 evidence 아티팩트와 같은 "digest-bound,
independent service-assigned id" 패턴이다(설계 #4 §3.2). `IdDerivedArtifact`(capsule 전용,
immutable content-addressed)는 채택하지 않는다.

**(b) ordering primitive는 REUSE하되 `tos.evidence` → shared core로 PROMOTE**(gap 6, §5 상술).
이미 배포된 `tos/src/tos/evidence/predicates.py`의 `Ordering{BEFORE,AFTER,AMBIGUOUS}`(133–138)·
`OrderingEvent(FrozenModel)`(141–159)·`compare_order`(171–224)는 ADR-002-016 §11 인과 순서를
구현하며, 그 필드·규칙은 ADR-002-008 §10과 **동일 순서 법칙**이다(same-continuity monotonic만
비교, 교차 continuity 뺄셈 금지, `time_lo`/`time_hi` 구간 disjoint만 정렬·overlap⇒AMBIGUOUS).
**time→evidence import edge는 layering 역전**이다(evidence 레코드가 시간 스냅샷을 *참조*하므로
evidence가 time의 소비자다 — SAFETY-EVIDENCE-ENVELOPE `time_evidence` 82–87; 반대 방향 edge는
개념적 순환). ⇒ 설계 #4 §3.1 canonicalization PROMOTE와 동형으로 ordering primitive를 **전용
ordering core 모듈(`tos.ordering` 권고 — MINOR-2)** 로 **승격**하고, `tos.evidence.predicates`는
re-export shim으로 남겨 ERI-EV-006 property suite를 green 유지한다. **`tos.canonical`의 서브모듈로
접지 않는다**: `tos.canonical`은 "digest-binding substrate"로 문서화됐고 promoted `OrderingEvent`는
evidence/egress 필드(`quorum_commit_index`·`egress_journal_sequence` — ADR-002-016/012 개념)를 담아
causal-ordering을 digest core에 접으면 관심사 혼합이기 때문(단 `OrderingEvent(FrozenModel)`은
`tos.canonical.FrozenModel`을 필요로 하므로 `tos.ordering → tos.canonical` 단방향 core-내부 edge는
허용). time·evidence·(그리고 `tos.ordering` 자신) 모두 core에 한 방향 의존. **중복 저작 금지**(DRY,
CLAUDE.md). 코드 이동은 후속 구현(§9.1)이며 본 문서는 옮기지 않는다. 대안·리스크·fallback은 §5.

**(c) `shared.determinism` 미import**(§0.3). **(d) 패키지 위치 = 전용 `tos/src/tos/time/`**:
설계 #1 §2.4(line 157)는 예시적으로 "time health"를 `models/` 아래 열거했으나, 실제 구현은
capsule/·evidence/를 **전용 top-level 패키지**로 두었고 §2.4(line 164)가 "subpackage는 RFC-002
§10 컴포넌트 분해를 따른다(스펙 용어 = 코드 용어)"고 위임했다. RFC-002 §10의 "Trustworthy Time
Service"는 first-class 컴포넌트이므로 **전용 `tos/src/tos/time/`** 가 선례에 부합한다. naming은
load-bearing이 아니다(설계 #4 §3.1) — 운영자가 치환 가능. `models/`는 같은 Phase-1 bullet의
다른 모델(capacity·authority epoch/lease)에 남을 수 있다.

**(e) 불변식 명명 규약**(gap 7): ADR-002-008에는 **`TIME-INV-###` register가 없다**(불변식은
prose SHALL/SHALL NOT + §19 TIME-AC-001..010 + §21 SAFE-###로만 존재). 따라서 본 계약은 **새
INV 시리즈를 창작하지 않고** 모델 불변식·술어를 **TIME-AC-001..010**(§19 line 447–464)과
**SAFE-030/031/035/044/048/050/051/052**(§21 line 482–489)에 인라인 매핑한다. (capsule이
ADR-002-018의 CII-INV register를 상속한 것과 달리, 여기는 INV register가 없어 TIME-AC/SAFE에만
앵커한다.)

---

## 1. 범위 매핑 — ADR-002-008 조항별 EV-L1 도달성 (TIME-EV 0건 완결)

EV-level 정의(VER-002-001 line 142 "EV-L1 — Model and Property Verification"; L2 = Component
Fault Test). **결정적 사실**: `EVIDENCE-REGISTER-002.csv`(line 69–78)의 TIME-EV-001..010은
**전부 `Critical`·`NOT_IMPLEMENTED`이고 최소 레벨이 EV-L2 이상**이다 — EV-L1 최소를 가진 항목이
**하나도 없다**(최저가 006/007 = `EV-L2/3`; 나머지 = `EV-L3`; 010 = `EV-L3+Security`). ⇒
**Phase 1은 어떤 TIME-EV도 닫지 않는다.** 모델은 각 항목의 **L1-decidable 술어 substrate**만
주장한다.

| TIME-EV | 제목 | register 최소(csv line) | Phase-1 EV-L1 substrate (닫지 않음) | ADR 근거 |
|---|---|---|---|---|
| -001 | Wall Rollback/Jump | EV-L3 (69) | `wall_clock_observation`은 audit 전용·expiry/freshness/ordering 결정에서 **구조적 제외**(§4.2) — rollback이 어떤 술어도 못 읽음 | §4.2 (85), §13 (329) |
| -002 | Clock Freeze | EV-L3 (70) | expiry/freshness는 monotonic 경과 + 보수 상한으로만; frozen wall이 expiry를 못 막음 | §9 (228), §11.2 (283–292) |
| -003 | Reference Disagreement | EV-L3 (71) | disagreement가 uncertainty를 보수적으로 넓힘 + common-mode는 독립으로 세지 않음(§7 184) 술어 | §7 (184), §13 (331) |
| **-004** | Monotonic Discontinuity | EV-L3 (72) | **continuity-id 변화 / non-monotone value / discontinuity ⇒ anchor+lease+cached-snapshot 무효**(§3 non-subtraction·invalidation) | §5 (124), §11.2 (277), §13 (333) |
| -005 | Restart/Suspension | EV-L3 (73) | suspension > `MAX_process_suspension_ms` 또는 unknown ⇒ 무효; boot-id 변화 ⇒ 새 continuity | §5 (124), §11.2 (277), §13 (334–335) |
| **-006** | Holdover Boundary | EV-L2/3 (74) | **보수적 usable-lifetime 산술(§11.2 285–292): 임의 unknown 항 또는 ≤0 ⇒ invalid — 순수** | §11.2 (283–294), §6.2 (151–155) |
| **-007** | Freshness/Ordering Ambiguity | EV-L2/3 (75) | **negative-age 미클램프, missing/future ⇒ STALE/UNKNOWN/CONFLICTED, overlap ⇒ AMBIGUOUS**(shipped `compare_order`+capsule `Freshness` 선례) | §9 (241–243), §10 (259–261) |
| -008 | Session-Boundary Uncertainty | EV-L3 (76) | uncertainty window가 session 경계를 가로지르면 deny(§12 319) 술어 | §12 (319) |
| **-009** | Time Recovery Generation | EV-L3 (77) | **새 generation이 무효화된 lease/authority를 revive하지 않음**(§6.4·§16 non-revival) | §6.4 (163–165), §16 (399–409) |
| -010 | Egress Time Currentness | EV-L3+Security (78) | receipt-anchor + transport로 교차-host age, **직접 monotonic 뺄셈 없음**(§3 cross-continuity 5단계) | §8 (212–222), §14.6 (366–368) |

**Phase-1 EV-L1 술어 substrate 강도**: 가장 직접적으로 선례가 있는 것은 **-007**(shipped
`tos.evidence.compare_order`의 overlap⇒AMBIGUOUS + capsule `Freshness.within_bound=None`⇒UNKNOWN
선례)와 **-004**(shipped `compare_order`의 same-continuity 가드 일반화)다. **-006/-009**는 순수
산술·상태 술어다. 나머지(001/002/003/005/008/010)는 술어 substrate만.

> **완결 주장 규율(설계 #2 §7·설계 #4 §7 상속)**: Phase 1은 *모델 + property test 저작*까지다.
> **어떤 항목도 "EV-L1-complete"로 주장하지 않는다** — TIME-EV는 최소 레벨이 전부 EV-L2 이상
> 이라 애초에 EV-L1으로 닫을 수 없다. 모든 주장에 규율 태그를 붙인다: **"EV-L1 predicate
> substrate only; TIME-EV-### remains NOT_IMPLEMENTED pending EV-L2/L3 (010은 +Security)
> fault injection."** VER register의 Owner/Reviewer는 TBD이고 수용은 Independent-Safety-
> Reviewer(저자 아님)의 별도 서명(IMPLEMENTATION-PLAN §3 line 153/157)이다.

**ADR-002-008 조항 → 모델 산출물 매핑**: §4 domains → §2.3; §5 continuity identity → §2.2;
§6 FSM → §2.4·§6; §7 establish-TRUSTED checks → §2.5·§7(술어); §8 snapshot → §2.1 + §3
cross-continuity; §9 freshness → §4; §10 ordering → §5; §11.2 holdover → §3(lifetime); §12
session → §6(술어); §16 recovery → §6(non-revival); §19 TIME-AC → 전 절 불변식 라벨.

---

## 2. 데이터 모델 계약

**표현 원칙**: 모든 아티팩트는 **pydantic v2 frozen 모델**(`ConfigDict(frozen=True,
extra="forbid")`, `tos.canonical.FrozenModel` REUSE — `_base.py` 66–69)로 저작한다. 필드명은
가능한 한 인라인 SoT 템플릿(§0 규범 원천)의 시간 필드명과 정렬한다(스펙 용어 = 코드 용어, 설계
#1 §2.4). frozen은 snapshot immutability(§8 "immutable, versioned")의 레코드 수준 실현이며,
모델에는 **update/delete 연산이 존재하지 않는다**(설계 #4 §2.0 규율 상속).

### 2.0 소유권 골격 — snapshot은 time이 소유, capsule/evidence는 참조 블록만

Time 모델이 **Time Health Snapshot 아티팩트를 소유**한다. capsule/evidence는 이를 **스칼라
참조 블록**으로만 담는다(§0.3 layering):

- `CRITICAL-INPUT-SNAPSHOT.trustworthy_time`(33–37): `{snapshot_id, generation,
  consumer_receipt_anchor, maximum_age_ms}` — capsule 측 투영.
- `SAFETY-EVIDENCE-ENVELOPE.time_evidence`(82–87): `{trustworthy_time_snapshot_id,
  source_wall_time, local_monotonic_value, monotonic_continuity_id, uncertainty_ms}` —
  evidence 측 투영.
- `DECISION-CONTEXT-CAPSULE.generation_vector.time_health_generation`(47).
- `EVIDENCE-COMMIT-RECEIPT.{committed_at_monotonic_continuity_id, committed_at_local_
  monotonic_value}`(17–18); `RECOVERY-EVIDENCE-PACKAGE.{trustworthy_time_generation,
  source_continuity_ids}`(25–26).

⇒ time 모델이 소유하는 스냅샷 필드는 이 인라인 블록 필드명과 **정렬**하여, 소유 아티팩트가
투영으로 깔끔히 내려가게 한다(예: `snapshot_id` ↔ `trustworthy_time_snapshot_id`,
`generation` ↔ `time_health_generation`, `wall_clock_observation` ↔ `source_wall_time`,
`maximum_consumer_age_ms` ↔ `maximum_age_ms`). **capsule·evidence는 tos.time을 import하지
않는다**(설계 #4 §3.1이 evidence가 capsule id+digest 스칼라만 담고 capsule 클래스를 import하지
않은 것과 동형).

### 2.1 Time Health Snapshot = `DigestBoundArtifact` (gap 1 + gap 6a)

ADR §8(line 190–206) prose에서 아티팩트를 1:1 저작한다(**전용 템플릿 부재** — 이 스키마는
프로젝트 측 신규 저작이며 독립 리뷰 대상, 상류 TIME-HEALTH-SNAPSHOT-template 후보로 §9.2 플래그).
`DigestBoundArtifact`(`_base.py` 91–246)를 **상속**하되(digest 검증 REUSE), `snapshot_id`·
`generation`은 **독립 주입 필드**다(§0.4a). 필드를 3레이어로 분류(§3.3 상속):

| 레이어 | 필드 | 처리 |
|---|---|---|
| **Layer-0 (identity/meta, digest 자기제외)** | `snapshot_id`(service-assigned, 독립), `generation`(TTS 단조 카운터, 독립), `status`(`ArtifactStatus` lifecycle 마커 REUSE), `canonicalization_version`, `canonical_digest`, `integrity.source_signature_or_mac`/`integrity_key_id` | digest preimage 제외. `generation`은 evidence EIP와 동형으로 **제외**(설계 #4 §3.5 MINOR-2): digest 일치만으로 generation을 증명 못 하게 하여 소비자 binding `(snapshot_id, generation, digest)`가 generation-drift를 탐지 |
| **Layer-1 (covered — health 결정 내용)** | `health_state`(§2.4), `time_continuity_identity`(§2.2), `evaluated_monotonic_anchor`(`{monotonic_anchor_id, monotonic_anchor_value}`), `wall_clock_observation`(audit 전용), `reference_sources[]`(§2.5), `bounds`(§2.6 offset/drift/uncertainty/source_disagreement), `suspension_status`·`discontinuity_status`, `tz_db_version`·`trading_calendar_version`, `issuer_continuity_id`·`issue_monotonic_value`·`maximum_consumer_age_ms`, `verification_profile_version`·`safety_profile_version`, `reason_codes[]`(§2.5), `authority_effect`(전부 false 상수, §6) | digest preimage 포함 (ADR §8 194–206) |

- **`wall_clock_observation`은 Layer-1 covered이되 "결정 입력 금지"가 불변식**: audit 무결성을
  위해 digest에 포함하나(변조 시 digest 불일치), **어떤 술어도 expiry/freshness/ordering에서
  이를 읽지 않는다**(§4.2 line 85). [TIME-AC-001; SAFE-035]. (제외하면 변조가 digest를 안
  바꾸므로 covered에 둔다 — 설계 #4 §2.1 integrity-block 논거와 반대 방향의 동일 정신.)
- **`_REQUIRED_COVERED`(ISSUED에서 concrete 필수, TBD/null이면 DRAFT — `_base.py` 135–155/
  199–205) 결정**: **구조적 continuity·상태·provenance·버전 필드**로 한정한다 — `health_state`,
  `time_continuity_identity`의 코어(host/boot/process/monotonic_anchor/generation), `evaluated_
  monotonic_anchor`, `issuer_continuity_id`, `issue_monotonic_value`, `tz_db_version`,
  `trading_calendar_version`, `verification_profile_version`, `safety_profile_version`. (§7
  "If any required check is missing … the state is not TRUSTED" line 186; §8 194–204 "at least".)
- **numeric bound 필드는 optional(null 허용) covered**: `maximum_consumer_age_ms`·`bounds.*`는
  `_REQUIRED_COVERED`에 **넣지 않는다.** 근거: 프로파일의 모든 시간 bound가 Phase-1에서
  null/PROPOSED이므로(§8), 이를 required로 하면 **모든 Phase-1 snapshot이 DRAFT로 떨어져 모델이
  검증 불가**가 된다. 대신 bound는 **주입 슬롯**이고 null이면 **소비 술어에서 UNKNOWN⇒fail-
  closed**로 처리한다(§4·§8; 설계 #2 §2.4 `Freshness.within_bound=None`⇒UNKNOWN, 설계 #4 §8
  동형). 특히 `maximum_consumer_age_ms`가 null이면 소비자는 max-age를 확립할 수 없어 **snapshot을
  permissive 용도로 거부**(§8 line 210) — 이는 정확히 요구되는 fail-closed 거동이다. [SAFE-050]
- `issue()`(`_base.py` 207–246): base classmethod가 주입 id(`snapshot_id`)를 그대로 두고 digest만
  계산 — evidence와 동일 경로(설계 #4 §3.2). canonicalization은 `tos.canonical` registry +
  `EVL1ProvisionalCanonicalizer`(`ev-l1-provisional-0`) **REUSE**, 신규 canonicalizer 없음
  (프로덕션 canonical form은 Phase-0, 설계 #4 §9.2 item 1과 동일 게이트).

### 2.2 Time Continuity Identity (§5 line 111–126)

`FrozenModel` 서브구조. ADR §5(line 113–122)의 최소 바인딩을 1:1 저작(전부 opaque 주입값):
`host_or_runtime_id`, `boot_id`, `process_id`, `monotonic_anchor_id`, `monotonic_anchor_value`,
`tts_generation`, `active_reference_source_set`(source_id 집합)·`reference_path_id`,
`tz_db_version`, `trading_calendar_version`, `verification_profile_version`.

- **불변식(§5 124)**: process restart / host reboot / monotonic reset / discontinuity /
  unbounded suspension / identity change ⇒ 그 event를 가로질러 continuous임을 증명 못 하는 모든
  local anchor를 **무효화**(§3 술어). [TIME-AC-004, TIME-AC-005; SAFE-048]
- **불변식(§5 126)**: **wall time에서 monotonic anchor를 재구성하지 않는다** — 모델에
  `monotonic_anchor_value`를 `wall_clock_observation`으로부터 계산하는 생성 경로가 **존재하지
  않는다**(anchor는 필수 주입 필드). [TIME-AC-001; SAFE-035]

### 2.3 시간 domain 구분 (§4 line 71–107)

ADR §4의 7 domain을 **붕괴시키지 않는다**(§4 107 "SHALL NOT be collapsed into one timestamp").
모델은 서로 다른 domain 값을 **별개 필드/타입**으로 담아 disagreement를 evidence로 보존한다:

| domain | 모델 표현 | 규율 |
|---|---|---|
| 4.1 Local Monotonic (75–79) | `local_monotonic_value` + `monotonic_continuity_id` | 한 continuity 내에서만 경과 측정; 교차 process/host 비교 금지(§3) |
| 4.2 Local Wall (81–85) | `wall_clock_observation` | audit 전용; expiry/freshness/ordering 단독 근거 금지(§2.1 불변식) |
| 4.3 Reference (87–89) | `reference_sources[]`(§2.5) | source·path·quality·common-mode 기록 필수 |
| 4.4 Source Event Time (91–93) | freshness 술어의 `source_time`(§4) | source identity/sequence/precision/uncertainty 유지 |
| 4.5 Broker/Venue (95–97) | (별도 privileged 필드 **없음**) | Broker Capability Profile 제한; attribution/ordering/expiry/FQP에 자동 부적합 — broker sequence는 Profile 승인 시에만 source sequence로 매핑(broker-agnostic, §5) |
| 4.6 Authorization Validity (99–101) | holdover lease 술어의 주입 lifetime(§3) | — |
| 4.7 Trading Session (103–105) | session context 주입 필드(tz id/version, calendar version, phase, boundary 좌표) | **broker-agnostic**; 시장 시간 하드코딩 금지(§6 session 술어) |

### 2.4 Health State FSM (§6 line 130–166) — 5 상태 / 7 전이

> **증거 기반 정정**: ADR §6(line 134–145)은 **5개 상태**(`UNINITIALIZED`, `SYNCHRONIZING`,
> `TRUSTED`, `DEGRADED_HOLDOVER`, `UNTRUSTED`)와 **7개 방향 전이**를 정의한다. 브리핑의
> "7-state"는 7개 **전이**를 가리킨 것으로 판단한다. 모델은 5 상태 + 7 전이를 §6 그대로 저작하며
> **추가 상태를 창작하지 않는다.**

`HealthState(StrEnum)` = `{UNINITIALIZED, SYNCHRONIZING, TRUSTED, DEGRADED_HOLDOVER,
UNTRUSTED}`. 허용 전이(§6 134–145):
`UNINITIALIZED→SYNCHRONIZING`, `SYNCHRONIZING→TRUSTED`, `TRUSTED→DEGRADED_HOLDOVER`,
`TRUSTED→UNTRUSTED`, `DEGRADED_HOLDOVER→UNTRUSTED`, `DEGRADED_HOLDOVER→SYNCHRONIZING`,
`UNTRUSTED→SYNCHRONIZING`. 상태 의미(§6.1–6.3): `TRUSTED`=전 check in-bound(149);
`DEGRADED_HOLDOVER`=online ref 상실·monotonic anchor는 holdover budget 내 연속, **새 normal
risk 불가·pre-issued degraded protective lease만**(151–155); `UNTRUSTED`=증명 불가·새 permissive
action 불가(157–161). 전이 보수성(§6.4)은 §6에서 술어로 실현.

### 2.5 미해결 element 스키마 저작 (gap 1)

ADR §8이 빈 배열/미명세로 남긴 원소 스키마를 §8/§4.3/§7/§13/§17 prose에서 저작한다(설계 #2
gap-1·설계 #4 §2.5 저작과 동형). 각 원소는 `FrozenModel`.

**(A) `reference_sources[]` (§8 199–200; §4.3 89; §7 176/184; §15 380)** — `ReferenceSource`:

| 필드 | 값 | 근거 |
|---|---|---|
| `source_id` | opaque source identity | §4.3 (89), §8 (199) |
| `path_id` | synchronization path identity | §4.3 (89), §7 (179 "synchronization path and source identity") |
| `common_mode_group` | 같은 clock/network/hypervisor/sync-daemon을 공유하는 그룹 id (nullable) | §7 (184), §15 (380–393) |
| `quality` | opaque quality 지표(주입 등급; 하드코딩 임계 금지) | §4.3 (89), §8 (199) |
| `reachable`·`healthy` | reachability·health 플래그 | §7 (176) |
| `offset_bound_ms`·`drift_bound_ppm`·`uncertainty_bound_ms` | per-source 주입 bound (int\|None) | §8 (200), §7 (176) |

- **불변식(§7 184)**: 같은 `common_mode_group`의 소스들은 **독립으로 세지 않는다** — 하나의
  독립 기여로 붕괴(§4 disagreement/independence 술어; 설계 #2 §5.2 CII-INV-004 common-mode
  붕괴와 동형). "Multiple names served by one clock/path/hypervisor/daemon SHALL NOT be
  claimed as independent." [TIME-AC-003; SAFE-031, SAFE-035]
- **quality/등급은 closed set이 아니다**(설계 #4 §2.5 MINOR-1 규율): broker/deployment별 소스
  등급은 Phase-0 프로파일 확장 대상(§8, §9.2). 미등록 값은 fail-closed.

**(B) `reason_codes[]` (§8 205; §13 표 327–338; §17 417)** — `ReasonCode(StrEnum)`,
degradation/denial 사유. §13 실패표 + §6 상태에서 도출한 **잠정** 집합(예:
`WALL_ROLLBACK, WALL_JUMP, CLOCK_FREEZE, SOURCE_UNAVAILABLE, SOURCE_DISAGREEMENT_OUT_OF_BOUND,
DRIFT_EXCEEDED, MONOTONIC_DISCONTINUITY, RESTART, SUSPENSION_EXCEEDED_OR_UNKNOWN,
BROKER_TIME_CONFLICT, CALENDAR_OR_TZ_UNAVAILABLE, STALE_SNAPSHOT, UNESTABLISHABLE_GENERATION,
HOLDOVER_LIFETIME_NONPOSITIVE`). §13은 표(예시적)이므로 이 집합은 **잠정**이며 Phase-0에서
확장 가능(§9.2); 미등록 코드는 fail-closed. broker-agnostic(KIS 전용 코드 없음).

### 2.6 uncertainty interval + bounds bundle (gap 3)

**결정**: uncertainty의 1차 표현은 **two-sided `UncertaintyInterval{lo: int|None, hi: int|None}`**
이다(단일 스칼라 아님). 근거: ADR §10(259)·§13(331) ordering이 **overlap⇒AMBIGUOUS**를 요구하며
overlap은 구간 개념이고, 이미 배포된 `OrderingEvent.time_lo/time_hi`(predicates.py 158–159)가
정확히 이 구간이다(§5 REUSE). 한쪽이라도 `None`이면 그 쪽 **unbounded = UNKNOWN**(fail-closed).

> **좌표계 규율(MAJOR-1 정정 — 안전-critical)**: `lo`/`hi`는 **reference/trustworthy-time
> frame** 값이다 — ADR §10 **priority-4 "corroborated source event time within its
> uncertainty"**(251–256)로, reference time에 앵커되어 **교차-continuity 비교가 유의미**하다.
> 이는 `local_monotonic_value`(§10 **priority-3**, §4.1 line 75–79 "SHALL NOT be compared
> across process or host identities" — per-continuity)와 **별개 좌표계**다. 실측(`predicates.py`):
> `compare_order`의 `local_monotonic_value` 비교는 `if same_continuity:` 가드 **안**(197–212)
> 이지만 `time_lo`/`time_hi` 구간 분기(218–223)는 가드 **밖**이다 — 이 분기가 안전한 것은
> **오직 lo/hi가 reference-frame이기 때문**이다. 따라서 monotonic-frame 값을 이 구간에 넣으면
> 가드 없는 교차-continuity 순서가 생겨 §8(212) non-subtraction을 조용히 위반한다
> (overlap⇒AMBIGUOUS도 못 막음: 교차-continuity disjoint monotonic 구간은 여전히 순서가 남는다).
> **`UncertaintyInterval`은 reference-frame 불확실성 구간이며, monotonic 좌표는 여기에 절대
> 넣지 않는다**(§5 규율·property). [TIME-AC-004, TIME-AC-007; SAFE-031, SAFE-035]

- **UNKNOWN ≠ 0**(§9 241/243; §18 line 443 "Clamp negative age to zero. Rejected"): 미확립
  bound는 `None`(UNKNOWN)이고 fail-closed다 — **0/fresh로 강제 금지.** (설계 #2 §2.4
  `Freshness.within_bound=None`⇒UNKNOWN 패턴 REUSE.) [TIME-AC-007; SAFE-030]
- **단일 스칼라 `uncertainty_ms`는 lossy 투영일 뿐**: SoT 인라인 블록(`time_evidence.
  uncertainty_ms` 87)과의 바이트 정렬을 위해 스냅샷이 담을 수 있으나, 모델은 **안전 결정에
  스칼라를 쓰지 않는다**(스칼라는 비대칭·한쪽-unknown을 표현 못 해 §10 overlap·§9 future-
  tolerance를 지원 못 함). 안전 결정은 interval/`bounds`로만.
- 스냅샷의 `bounds`(§8 200)는 **magnitude bundle**: `offset_bound_ms`, `drift_bound_ppm`,
  `uncertainty_bound_ms`, `source_disagreement_bound_ms` — 각 int\|None(주입). freshness/
  ordering 술어가 이들 + §9 delay-class bound를 **보수적으로 합산**해 AgeBound(단측, §4) 또는
  `UncertaintyInterval`(양측, §5)을 도출; 적용 가능한 항 중 하나라도 None이면 결과 UNKNOWN.

---

## 3. monotonic-continuity · 교차 continuity 뺄셈 금지 술어 (gap 2)

핵심 난제: **실제 clock을 읽지 않고** 경과·연속성을 모델링. `monotonic_continuity_id`·
`local_monotonic_value`는 **opaque 주입값**이며 술어는 이들을 좌표로만 다룬다(shipped
`OrderingEvent`의 동명 필드와 동일 성격 — predicates.py 155–156).

> **좌표계 분리 규율(MAJOR-1 — §2.6·§5와 공유)**: `local_monotonic_value`는 **priority-3
> per-continuity** 좌표다. **교차-continuity age·ordering은 오직 아래 (4)의 5-step
> receipt-anchor 경로로만 성립하며, monotonic 좌표를 raw `compare_order`의 interval
> 분기(reference-frame 전용, 가드 없음)에 절대 넣지 않는다.** 교차 continuity에서 monotonic은
> 비교·뺄셈 대상이 아니라 receipt-anchor를 통한 소비자-local 재-앵커 대상이다(§8 212–220).

**(1) 교차 continuity 뺄셈 금지(§8 212 + §10 259; 안전 코어)** — `elapsed_within_continuity(a,
b) -> int | None`: `a.monotonic_continuity_id == b.monotonic_continuity_id`일 때만 `b.value -
a.value`를 반환; 다르면 **`None`(뺄셈 자체를 수행하지 않음)**. 이는 shipped `compare_order`의
`same_continuity` 가드(predicates.py 197–212)를 age 산술로 일반화한 것이다. [TIME-AC-004,
TIME-AC-010; SAFE-031, SAFE-035] (§8 교차-continuity는 §21 482–489상 provenance/trustworthy-time
basis = SAFE-031/035이며 holdover SAFE-048이 아니다 — MINOR-5 정정.)

**(2) anchor 무효화(§5 124; §13 333–335; §11.2 277)** — `anchor_valid(continuity_now, anchor,
suspension_ms, max_suspension_ms) -> bool`: 다음 중 하나라도 성립하면 **False(무효, "덜 신선"이
아님)** — continuity-id 변화 / 같은 claimed continuity 내 non-monotone `local_monotonic_value`
(discontinuity) / `boot_id`·`process_id` 변화(restart) / `suspension_ms > max_suspension_ms`
또는 `suspension_ms is None`(unbounded/unknown). 무효 시 anchor·lease·cached-snapshot 전부
새 permissive 사용 불가. [TIME-AC-004, TIME-AC-005; SAFE-048]

**(3) 보수적 usable lifetime(§11.2 283–294; TIME-EV-006 substrate)** — `conservative_usable_
lifetime(issued_lifetime, elapsed_monotonic, source_transport_unc, max_drift_error,
suspension_unc, safety_margin) -> int | None`: §11.2 공식 그대로
`issued − elapsed − source_transport_unc − max_drift_error − suspension_unc − safety_margin`.
**임의 항이 `None`(unknown)이면 `None`; 결과 ≤ 0이면 invalid**(§11.2 294 "If any term is
unknown or the result is non-positive, the lease is invalid for new transmission"). property:
각 uncertainty 항에 대해 **단조 감소**(더 큰 불확실성 ⇒ 더 짧은 lifetime), 결코 음수-클램프
안 함. holdover는 `health_state == DEGRADED_HOLDOVER` + §11.2 전제(anchor가 TRUSTED에서 설정 +
같은 continuity + progression/suspension in-bound + online-authority 상실 전 발행 + exclusive
owner/capacity 증명 + positive lifetime)에서만. [TIME-AC-006; SAFE-048]

**(4) 교차 continuity snapshot age(§8 212–220; TIME-EV-010 substrate)** — `effective_snapshot_
age_bound(snapshot, consumer_receipt_anchor, injected_bounds) -> int | None`. 소비자와 issuer의
continuity가 **다르면** ADR §8의 5단계로만: (i) issuer 서명 age+uncertainty 검증; (ii) 소비자
자신의 monotonic+continuity로 receipt 기록(`ConsumerReceiptAnchor{consumer_monotonic_
continuity_id, consumer_local_monotonic_value_at_receipt}`); (iii) 주입 transport/queue/
clock-domain-conversion bound 가산; (iv) receipt 이후 **소비자-local** 경과 가산(소비자 자신의
continuity 내 뺄셈 — 허용); (v) 임의 bound missing/stale/contradictory 또는 max 초과면 거부.
**issuer monotonic을 소비자 clock에서 빼지 않는다**(§8 220 "not a cross-host timestamp"). 교차
continuity + transport/queue/conversion bound 중 하나라도 None이거나 consumer receipt anchor가
무효(소비자 restart/discontinuity, §8 220)면 **UNKNOWN**; `> maximum_consumer_age_ms`면 거부.
[TIME-AC-010; SAFE-031, SAFE-035, SAFE-030, SAFE-050]

---

## 4. freshness / uncertainty 모델 (gap 3·5)

ADR §9(226–245)는 freshness를 **보수적 상한**으로 평가한다(raw wall 뺄셈 금지). 8종 delay class
(§9 230–239)를 각각 **주입 슬롯**으로 선언한다(§8 bounds 계약). `freshness_verdict(source_time,
receipt_anchor, now_anchor, delay_bounds, future_tolerance) -> FreshnessVerdict`,
`FreshnessVerdict(StrEnum) = {FRESH, STALE, UNKNOWN, CONFLICTED}` (§19 TIME-AC-007 "STALE,
UNKNOWN, or CONFLICTED").

**규칙(§9 241–243)**:
- 적용 가능한 8 delay 항 중 상한을 **확립 못 하면** ⇒ `STALE`/`UNKNOWN`(241). 미확립 = 주입
  bound `None` (설계 #2 §2.4 fail-closed 패턴).
- **negative-age 미클램프**(243; §18 443): 계산 age가 음수면 `0`으로 클램프하지 않고
  `CONFLICTED`.
- **future-beyond-tolerance**(243): source_time이 `future_tolerance`(주입, 누락 키 — §8)를
  넘어 미래면 `CONFLICTED` (fresh 아님).
- **missing source time / unbounded transport**(243) ⇒ `UNKNOWN`/`STALE`, fresh 강제 금지.
- 임계값은 프로파일(245) — 모델은 **주입값**만 소비, 하드코딩 없음. property: **임의 유효
  bound 하에서 술어가 보수적으로 성립**(hypothesis 생성 bound; §8).

[TIME-AC-002, TIME-AC-007; SAFE-030]

8 delay class(§9 232–239)와 주입 슬롯: source precision/uncertainty(232) · source→receipt
transport(233) · local receive monotonic(234) · current monotonic elapsed(235) · drift+holdover
uncertainty(236) · queue/buffer/replay/batch(237) · source sequence gaps(238) · clock-domain
conversion(239). 각 슬롯의 프로파일 키 존재 여부는 §8 표.

---

## 5. ordering 술어 (§10) — ordering primitive REUSE(PROMOTE) 결정 (gap 6b)

ADR §10(249–261) 우선순위: (1) authoritative source/broker sequence; (2) durable local
send/receive sequence; (3) local monotonic within one continuity; (4) corroborated source event
time within uncertainty; (5) wall for audit only. **wall은 uncertainty interval이 overlap하면
교차-process 전순서를 만들지 못한다**(259). 모호는 Knowledge/Evidence 차원에 남아 **순서 해소가
필요한 안전 전이를 차단**(261).

**이 법칙은 이미 배포된 `tos.evidence.predicates`에 구현되어 있다**: `compare_order`(171–224)가
priority(quorum/egress sequence → same-continuity source_native_sequence → same-continuity
local_monotonic → typed causal links → disjoint time interval)를 구현하고, **overlap⇒AMBIGUOUS**
(219–223), **교차 continuity 뺄셈 금지**(197–212)를 이미 강제한다. ADR-002-008 §10과 ADR-002-016
§11은 **동일 순서 법칙**이다.

**결정: ordering primitive를 `tos.evidence` → shared core(`tos.canonical`)로 PROMOTE하고 time·
evidence가 공유한다**(§0.4b). 대안 비교:

- **대안 A — `tos.time`이 `tos.evidence`를 import**: 기각. evidence 레코드가 시간 스냅샷을
  *참조*하므로(`time_evidence` 82–87) evidence가 time의 소비자다 — 반대 방향 edge는 개념적
  순환이며 설계 #4 §3.1이 기각한 "foundational substrate가 leaf consumer에 의존" 역전과 동형.
- **대안 C — time이 자체 ordering 술어를 신규 저작**: 기각. 안전-critical 순서 술어를 **중복**
  하면 drift 위험(DRY 위반, CLAUDE.md). PROMOTE가 정확히 이를 방지.
- **선택 B — PROMOTE(전용 `tos.ordering` core 모듈)**: `Ordering`·`OrderingEvent`·`compare_order`
  (+`_cmp`)를 **전용 ordering core 모듈 `tos.ordering`**(권고; `tos.canonical` 서브모듈 아님 —
  MINOR-2)로 이동, `tos.evidence.predicates`는 re-export shim(설계 #4 §3.1 canonicalization
  PROMOTE와 동형). 근거(MINOR-2): promoted `OrderingEvent`는 evidence/egress 필드
  (`quorum_commit_index`·`egress_journal_sequence` — ADR-002-016/012 개념)를 담아 time 순수
  모델엔 무의미하고, `tos.canonical`은 "digest-binding substrate"로 문서화됐으므로 causal-ordering을
  거기 접으면 관심사 혼합이다. time·evidence 둘 다 `tos.ordering`에 **한 방향** 의존, 서로 독립.
  `OrderingEvent(FrozenModel)`은 `tos.canonical.FrozenModel`을 필요로 하므로 `tos.ordering →
  tos.canonical` 단방향 core-내부 edge만 둔다.

**time 측 사용**: time의 ordering 산출물은 **신규 비교 로직이 아니라** Time Health Snapshot의
좌표로 `OrderingEvent`를 구성해 promoted `compare_order`를 호출하는 것이다. **좌표 매핑은
좌표계별로 엄격히 분리한다(MAJOR-1)**:
- `local_monotonic_value`(+`monotonic_continuity_id`) → `OrderingEvent.local_monotonic_value`/
  `source_continuity_id` (§10 priority-3; `compare_order`의 `same_continuity` 가드 안에서만 비교).
- `UncertaintyInterval{lo, hi}`(reference-frame, §2.6) → `OrderingEvent.time_lo`/`time_hi`
  (§10 priority-4; 가드 없는 구간 분기는 reference-frame 전용). 닫힌 구간 관례(`a.time_hi <
  b.time_lo`만 정렬, 접점은 AMBIGUOUS — predicates.py 220–223)를 **그대로 보존**(재정의 금지).
- **monotonic 좌표를 `time_lo`/`time_hi`에 넣지 않는다** — 넣으면 가드 없는 교차-continuity
  순서가 생겨 §8(212) non-subtraction 위반(§2.6·§3 규율).

broker sequence(§4.5)는 별도 privileged 필드로 두지 않는다 — Broker Capability Profile 승인
시에만 source sequence로 매핑(broker-agnostic). [TIME-AC-004, TIME-AC-007; SAFE-031, SAFE-035]

**property(MAJOR-1 신규)**: monotonic 좌표만 지닌(reference-frame 구간 부재, `time_lo`/`time_hi`
= None) 두 **교차-continuity** 이벤트는 `compare_order` 결과가 반드시 **`AMBIGUOUS`** 여야 한다
(가드 밖 구간 분기가 None을 만나 정렬 불가). 이는 shipped `compare_order`의 현 거동을 명세로
고정하고, time이 monotonic을 구간으로 밀어넣지 않음을 회귀 검증한다.

**리스크·제약(정직 기록)**: PROMOTE는 **이미 비준·구현된 evidence 코드를 이동**하는 유일한
결정이다. **executor 의존성(MINOR-3)**: 본 §5 ordering 산출물은 **PROMOTE 실행(operator-gated
§9.1)에 종속**된다 — PROMOTE 전에는 time이 참조할 core ordering 모듈이 없으므로 §5는 미확정이다.
제약: (i) 코드 이동은 후속 구현(§9.1), 본 문서는 옮기지 않음; (ii) ERI-EV-006 property suite는
`tos.evidence.predicates` 경로(shim)로 계속 import되어 **불변 regress**해야 함; (iii) module 명은
load-bearing 아님 — 권고는 전용 `tos.ordering`(MINOR-2)이나 운영자가 확정, **load-bearing은
layering(time·evidence 모두 core에 한 방향, 중복 없음)** 이다; (iv) PROMOTE 실행 시 설계 #4
§3.1/§4.3/§7이 ordering을 evidence-local로 서술한 부분이 stale되므로 교차-주석 필요(MINOR-4,
§9.1). **Fallback**: PROMOTE를 지금 과하다고 판단하면, 최소 요구는 "time→evidence edge 금지 +
비교 로직 중복 금지"이며 정확한 home은 Phase-0/운영자로 이연(단, 그때까지 time의 §5 산출물은 미확정).

---

## 6. health FSM 전이 보수성 · non-revival (§6.4)

ADR §6.4(163–165): **덜-신뢰 방향 전이는 즉시** 적용 가능; **`TRUSTED`로의 복귀는 새 health
generation + 완전 재확립을 요구**하고 **untrusted 구간의 action/evidence를 소급 검증하지
않는다.**

- `health_transition_allowed(from_state, to_state) -> bool`: §6(134–145) 7 전이만 허용(그 외
  구성/전이 불가). [§6 FSM]
- `transition_to_trusted_requires_new_generation(from_gen, to_gen) -> bool`: `to_state ==
  TRUSTED`인 전이는 `to_gen > from_gen`(엄격 증가)일 때만 유효(§6.4·§16 401 "a new Trustworthy
  Time Service generation"). [TIME-AC-009; SAFE-044]
- **non-revival 술어(§6.4 165; §16 406; TIME-EV-009 substrate)** — `recovery_generation_
  revives_nothing(invalidated_under_gen, new_gen, ...) -> bool`: generation N에서 무효화된
  lease/authority는 N+1(이후 임의 generation)에서도 **revive되지 않는다**(항상 True). 모델은
  "generation 증가"를 lease/authority 유효성 복원으로 매핑하는 연산을 **제공하지 않는다.**
  §16(409) "establishes time readiness only … does not open the Recovery Barrier, issue Live
  Authorization, or re-arm." [TIME-AC-009; SAFE-044]
- **authority-absence 불변식**: Time Health Snapshot의 `authority_effect.{creates_authority,
  may_mutate_live_state, may_release_capacity, may_rearm}` = **false 상수**(true면 구성 실패 —
  설계 #4 §4.6 `_all_authority_false` REUSE). §14.1(348) "SHALL NOT issue live authority or
  classify economic risk." "snapshot이 authority로 쓰이면 거부" 술어. [SAFE-044]
- **session 경계 술어(§12 319; TIME-EV-008 substrate)** — `session_open_positively(session_ctx,
  uncertainty_interval) -> bool`: ambiguous local time / missing calendar / unknown phase /
  tz-version conflict / **경계가 uncertainty interval 내부**면 **deny**(positively-open만
  허용). session context(tz id/version, calendar version, phase, boundary 좌표)는 주입 —
  **시장 시간 하드코딩 금지, broker-agnostic**(§4.7). [TIME-AC-008; SAFE-050]

---

## 7. property-test 하네스 타깃

§1의 EV-L1 substrate에 정렬. **전부 predicate substrate이며 어떤 TIME-EV도 닫지 않는다**(§1
규율). property는 bound를 **hypothesis 생성 주입값**으로 다뤄 "임의 유효 bound 하 보수적 성립"을
검증(특정 값 비의존, 하드코딩 없음 — §8).

| family | Phase-1 타깃 | substrate / 근거 |
|---|---|---|
| snapshot canonicalization + digest 검증 | **REUSE 설계 #2 §3.4 (A) must-pass suite** (`tos.canonical`) | snapshot covered로 재적용; frozen digest 일관성(`_base.py` 171–205) |
| **snapshot 소비자 binding / wrong-generation 거부** (MINOR-1) | **core 술어** | 소비자가 `(snapshot_id, generation, digest)` 바인딩 검증 + **wrong/null-generation·wrong-environment·wrong-scope·config-version** snapshot 거부(§8 208); 단 issuer≠consumer continuity는 mismatch가 아니라 §3(4) 활성화. evidence `eip_binding_ok`(predicates.py 564–595, null-generation fail-closed) 미러. §0.4a/§2.1의 주 근거 property |
| continuity / non-subtraction | **core 술어** | `elapsed_within_continuity`(교차⇒None) · `anchor_valid`(무효화). TIME-EV-004/005 substrate (§3) |
| conservative usable lifetime | **core 술어** | §11.2 공식; unknown 항/≤0⇒invalid; 각 항 단조. TIME-EV-006 substrate (§3.3) |
| freshness verdict | **core 술어(가장 선례 강함)** | negative 미클램프·missing/future⇒STALE/UNKNOWN/CONFLICTED·UNKNOWN≠0. TIME-EV-007 substrate (§4); capsule `Freshness` 선례 |
| ordering | **REUSE promoted `compare_order`** (`tos.ordering`) | overlap⇒AMBIGUOUS·교차 continuity 뺄셈 금지; **교차-continuity monotonic-only ⇒ AMBIGUOUS**(MAJOR-1); monotonic 좌표를 reference-frame 구간 분기에 미투입. TIME-EV-007 substrate (§5); shipped evidence ordering 선례 |
| health FSM + non-revival | **core 술어** | §6 전이만·→TRUSTED는 gen 엄격증가·revive 연산 부재. TIME-EV-009 substrate + §6.4 (§6) |
| cross-continuity snapshot age | **core 술어** | §8 5단계; issuer monotonic 뺄셈 없음; missing bound/anchor 무효⇒UNKNOWN. TIME-EV-010 substrate (§3.4) |
| source independence / common-mode | **술어** | common_mode_group 이중계상 금지; disagreement > tolerance⇒not-TRUSTED. TIME-EV-003 substrate (§2.5A) |
| authority-absence | **flag 불변식 + 거부 술어** | authority_effect 전부 false; snapshot-as-authority 거부. SAFE-044 (§6) |

- **core(술어) 강도**: -007·-004가 shipped 선례로 가장 강함; -006·-009는 순수 산술·상태. **전부
  predicate substrate — "EV-L1-complete 주장 금지"**(§1).

### 7.1 import-closure 검증 테스트 (C1 강제 — 설계 #4 §7.1 확장, §7.x 커버)

서브프로세스에서 `import tos.time`(및 `tos.canonical`·`tos.ordering`)만 한 뒤 `sys.modules`를 검사해 assert:
(1) 설계 #1 §2.3 금지 패키지 부재; (2) **`shared.config`·`shared.config.secrets` 부재**(전이
유입 런타임 포착); (3) `os.environ`/`os.getenv` 미참조; (4) **`shared.determinism` 부재**(gap 6
결정 — pandas 유입/무관 프리미티브 차단); (5) **`numpy`·`pandas` 부재**(§0.3); (6) **`tos.capsule`·
`tos.evidence` 부재**(§5 layering — time closure에 형제 패키지가 없어야 하며, ordering은 PROMOTE된
전용 **`tos.ordering`** core 모듈에서만 온다). 이 테스트가 **`tos.time` 패키지의 import closure를 커버**한다.
required check(`tos-firewall`)와 함께 green이어야 §0.3 준수 선언이 능동 성립한다.

### 7.2 run manifest 정렬 (설계 #1 §5.1 7항목)

TIME 전용 run manifest 템플릿은 없다 — 설계 #1 §5.1 run-manifest 규율을 REUSE한다. evidence를
산출하는 모든 property-test run은 다음을 기록: (1) git commit digest + `tos` 버전; (2) 인터프리터
+ 고정 의존성 버전(pydantic/hypothesis); (3) 실행 환경; (4) 하네스 git digest; (5) **property-
test seed**(hypothesis seed/derandomize, append-only); (6) **소비 설정 아티팩트 digest**(주입
time bounds 프로파일 + `canonicalization_version` + promoted ordering primitive 버전); (7) 산출
아티팩트 sha256. (VER-002-001 §2.3 재현성·§3 baseline·§9.1 seed·§9.2 digest의 EV-L1 부분집합.)

---

## 8. bounds 주입 + 누락 프로파일 키 Phase-0 (gap 5)

`VERIFICATION-PROFILE-002.yaml`은 전체 `status: PROPOSED`·`approved_by: []`·`effective_from:
null`이다(배너: "unapproved or placeholder bound is not an approved bound"). ADR §9(245)·§11.2·
§8은 모든 time 임계값을 승인 프로파일에 둔다. **결정**: 모든 임계값은 **주입 policy 파라미터**로만
모델에 들어오고, **어떤 숫자도 하드코딩하지 않는다**(CLAUDE.md 설정 기반). 누락 주입값 ⇒ UNKNOWN
fail-closed(§4·§3). property는 bound를 hypothesis 생성 주입값으로 다룬다(§7).

**존재하는 distinct 키(실측)**:

| 키 | line | value / status | ADR 항 |
|---|---|---|---|
| `MAX_time_health_snapshot_age_ms` | 698 | `null` / APPROVE ("including transport uncertainty") | §8 (210), §9 |
| `MAX_degraded_lease_holdover_ms` | 699 | `5000` / PROPOSED | §11.2 |
| `MAX_clock_drift_ppm` | 700 | `200` / PROPOSED (drift) | §7 (176), §9 (236) |
| `MAX_process_suspension_ms` | 701 | `2000` / PROPOSED | §5 (124), §11.2 |
| `B_time_health_to_egress` | 156–161 | `null` / MEASURE, hard_maximum | §8 (222), §14.6 |

**누락/folded distinct 키 (Phase-0 Bounds-Approver 플래그 — 6~7종)**: ADR §9(230–239) 8종 delay
+ §11.2(283–292) lifetime 항 + §8(216) cross-continuity 항을 실측 대조한 결과, 다음은 **전용 키가
없다**:

1. **transport-and-queue uncertainty**(§9 233/237, §8 216) — `MAX_time_health_snapshot_age_ms`
   주석에 "including transport uncertainty"로 **folded**만, transport/queue/buffer/replay/batch
   전용 키 없음.
2. **clock-domain-conversion uncertainty**(§9 239, §8 216) — 키 전무.
3. **source-disagreement tolerance**(§7 184, §13 331, TIME-AC-003) — 키 전무(drift ppm은
   있으나 disagreement 초과 시 deny하는 tolerance는 없음).
4. **offset bound**(§8 200, §7 176 "offset and drift") — drift(ppm)만 존재, **offset 전용 키
   부재.**
5. **stabilization interval**(§16 403 "the approved stabilization interval") — 키 전무.
6. **future-timestamp tolerance**(§9 243) — 키 전무.
7. **holdover safety margin**(§11.2 291 "approved safety margin") — `MAX_degraded_lease_
   holdover_ms`(총 예산)에 **folded**, margin 항 전용 키 부재. (추가로 source precision §9 232·
   source-sequence-gap §9 238도 전용 키 없음.)

본 계약은 이 누락/folded 키를 **Phase-0 프로파일 보강 항목으로 플래그**한다(설계 #4 §8 4/8
under-report 정정과 동형). 모델은 §9 8종 delay + §11.2 항 + §8 cross-continuity 항 각각을 **주입
슬롯으로 선언**하되(누락 시 UNKNOWN fail-closed), 값·키 승인은 **Bounds-Approver 게이트**로 넘긴다
(Live-Armer와 분리 — IMPLEMENTATION-PLAN §3). [SAFE-050]

---

## 9. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 9.1 후속 구현 작업 (본 계약 위에서)

- **ordering primitive PROMOTE**(§5·§0.4b): `Ordering`·`OrderingEvent`·`compare_order`를
  **전용 `tos.ordering` core 모듈**(MINOR-2)로 이동 + `tos.evidence.predicates` re-export shim;
  ERI-EV-006 suite 불변 green 확인. (설계 #4 §3.1 canonicalization PROMOTE 후속과 동형 절차.)
- **설계 #4 교차-주석 갱신**(MINOR-4): PROMOTE 실행 시 설계 #4 §3.1(canonicalization PROMOTE)·
  §4.3(ERI-EV-006 ordering)·§7(하네스 ordering family)이 ordering을 **evidence-local**로 서술한
  부분이 stale된다 — primitive 재배치 시 "ordering은 `tos.ordering`으로 승격됨" 교차-주석을 그
  절들에 남긴다(shim으로 동작은 불변).
- **`tos/src/tos/time/` 모델·술어·property·import-closure 테스트 저작**(§2–§7): 설계 #3(EV-L1
  하네스)이 property suite를 실행. `tos.canonical`(digest) + `tos.ordering`(ordering) 의존.
- **의존 방향**: time ⟸ `tos.canonical`·`tos.ordering` ⟸ (설계 #4 substrate); `tos.ordering ⟸
  tos.canonical`. time은 capsule/evidence를 import하지 않음(형제).

### 9.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. VERIFICATION-PROFILE-002 **bounds 승인** + **누락/folded 키 6~7종 신설**(§8; Bounds-Approver,
   Live-Armer와 분리).
2. **프로덕션 canonical serialization·digest 알고리즘 선택**(설계 #4 §9.2 item 1과 동일 게이트) —
   §2.1 잠정 `ev-l1-provisional-0`는 프로덕션 승인을 대체하지 않는다.
3. **TIME-HEALTH-SNAPSHOT 스키마의 독립 리뷰** — 전용 템플릿이 없어 §2.1은 **프로젝트 측 신규
   저작**이다. 상류 tos-spec에 TIME-HEALTH-SNAPSHOT-template로 승격할지, `reference_sources[]`·
   `reason_codes[]` element 집합·`ReasonCode`/`quality` 등급의 확장을 어떻게 거버넌스할지 결정.
4. **ordering PROMOTE의 module home 확정**(§5·MINOR-2): 권고는 **전용 `tos.ordering` core
   모듈**(`tos.canonical` 서브모듈 아님 — 관심사 분리); naming은 비-load-bearing이나 운영자 확정 필요.
5. **`integrity.source_signature_or_mac`의 암호학적 검증**(§2.1): 키 자료·custody가 없어 Phase 1은
   필드 *존재·구조*만 담고 MAC 검증은 L2+ 이연(설계 #4 §3.4 (i)와 동형). status/signature가
   lifecycle을 bind하는 attestation 경로도 서명/evidence 레이어로 이관.
6. Independent-Safety-Reviewer 지정 및 §7 EV-L1 evidence 수용 서명(저자 배제 —
   IMPLEMENTATION-PLAN §3 line 153/157).
7. **런타임 continuity/suspension/boot identity 증거 플랫폼**(ADR §22 OQ2) 및 **Time Health
   generation 분배·소비자 receipt-anchor 메커니즘**(ADR §22 OQ6, `B_time_health_to_egress`) —
   전부 L2+ 런타임.

---

## 10. 개정 로그 + 비준 체크리스트

### 10.1 개정 로그

- 2026-07-21: **v1 초안 최초 작성.** ADR-002-008 EV-L1 실현 계약. 7개 결정 의제(gap 1–7) 전부
  결정 또는 Phase-0 이관 명시. 설계 #1(경계·firewall)·#2(capsule)·#4(evidence, canonical
  substrate)에 정렬. 주요 결정: (gap 1) Time Health Snapshot을 §8 prose에서 저작 +
  `reference_sources[]`/`reason_codes[]` element 스키마 + covered/`_REQUIRED_COVERED` 분류;
  (gap 2) opaque 주입 monotonic + 교차 continuity 뺄셈 금지 + anchor 무효화; (gap 3) two-sided
  `UncertaintyInterval` + UNKNOWN≠0 + negative 미클램프/future⇒CONFLICTED; (gap 4) **TIME-EV
  0건 완결** + "EV-L1-complete 주장 금지"; (gap 5) 8종 delay 주입 슬롯 + 누락 키 6~7종 Phase-0
  플래그; (gap 6) `DigestBoundArtifact`+독립 `snapshot_id`·ordering **PROMOTE**·`shared.
  determinism` 미import·패키지 `tos/src/tos/time/`; (gap 7) TIME-AC/SAFE 명명(새 INV 금지).
  증거 기반 정정 2건: FSM은 **5 상태 / 7 전이**(§6 134–145; 브리핑 "7-state"=7 전이); ordering은
  이미 배포된 evidence primitive라 신규 저작 아닌 **PROMOTE+REUSE**.
- 2026-07-21: **v1.1 — 독립 비평 리뷰 ACCEPT-WITH-RESERVATIONS(CRITICAL 0, MAJOR 1, MINOR 5)
  반영.** **MAJOR-1(좌표계 혼동)**: §2.6에서 `UncertaintyInterval` lo/hi가 **reference/trustworthy-
  time frame(§10 priority-4)** 이며 `local_monotonic_value`(priority-3, per-continuity)와 **별개
  좌표계**임을 명시("동일 좌표계" 문구 제거); §3·§5에 "교차-continuity age·ordering은 5-step
  receipt-anchor로만, monotonic을 raw `compare_order` 구간 분기에 미투입" 규율 명문화; §5·§7에
  **"교차-continuity monotonic-only ⇒ AMBIGUOUS"** property 추가. **MINOR-1**: §7에 snapshot 소비자
  binding/wrong-generation 거부 property 추가(evidence `eip_binding_ok` 미러). **MINOR-2**: ordering
  home을 `tos.canonical` 서브모듈이 아닌 **전용 `tos.ordering` core 모듈**로 재권고, §0.3/§0.4b/§7.1
  firewall 선언 정정. **MINOR-3**: §5 산출물의 PROMOTE 실행(§9.1) 종속을 executor 의존성으로 강조.
  **MINOR-4**: §9.1에 "PROMOTE 시 설계 #4 §3.1/§4.3/§7 교차-주석" 추가. **MINOR-5**: §3(1) SAFE
  태그를 SAFE-048→**SAFE-031/035**로 정정(§8 교차-continuity는 §21상 provenance/trustworthy-time
  basis). ordering-PROMOTE 거버넌스 우려는 선례대로 기각되어 방향 유지.
- 2026-07-21: **v1.1 운영자 비준.** ordering PROMOTE(전용 `tos.ordering` core 모듈; evidence
  코드 이동 + shim) 승인. 효력: `tos/src/tos/time/` Phase 1(EV-L1) 모델 + property test 착수.
  TIME-EV 0건 완결(predicate substrate만); Phase-0 잔존(bounds·독립 리뷰어·snapshot 스키마 검토).

### 10.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(런타임 TTS·실제 clock·egress·authority·TIME-EV 0건·bounds 미승인)과 §0.3
      firewall 준수(numpy/pandas·shared.config·shared.determinism·tos.capsule/evidence 배제)에 동의.
- [ ] §1 조항별 EV-L1 도달성 + **TIME-EV 0건 완결** + "EV-L1-complete 주장 금지" 규율에 동의
      (register line 69–78 최소 레벨 전부 EV-L2+).
- [ ] §2.1 Time Health Snapshot = **`DigestBoundArtifact` + 독립 service-assigned `snapshot_id`**
      (gap 6a) + §8 prose 저작(전용 템플릿 부재) + covered/`_REQUIRED_COVERED`/bound-optional 분류
      (gap 1)에 동의.
- [ ] §2.5 element 스키마(`reference_sources[]` common-mode 붕괴·`reason_codes[]`)와 §2.6
      two-sided uncertainty interval(gap 1·3)에 동의.
- [ ] §3 교차 continuity 뺄셈 금지·anchor 무효화·보수적 lifetime·§8 cross-continuity 5단계(gap 2)에 동의.
- [ ] **MAJOR-1 좌표계 분리**(§2.6·§3·§5): `UncertaintyInterval` lo/hi = reference-frame(§10
      priority-4), `local_monotonic_value` = per-continuity(priority-3); monotonic을 `compare_order`
      구간 분기에 미투입; **교차-continuity monotonic-only ⇒ AMBIGUOUS** property에 동의.
- [ ] §4 freshness verdict(negative 미클램프·future⇒CONFLICTED·UNKNOWN≠0)와 §8 8종 delay 주입 +
      누락 키 6~7종 Phase-0 플래그(gap 5)에 동의.
- [ ] **§5 ordering primitive PROMOTE**(gap 6b — 유일하게 비준·구현된 evidence 코드 이동; shim으로
      ERI-EV-006 불변 regress; time→evidence edge 금지)와 fallback에 동의.
- [ ] §6 FSM 전이 보수성·non-revival·authority-absence·session 술어(§6.4·§12)에 동의.
- [ ] §7 하네스 타깃(전부 predicate substrate; snapshot 소비자 binding property 포함 — MINOR-1)과
      **§7.1 import-closure 테스트(tos.time 커버)**에 동의.
- [ ] §9.2 Phase-0 이관 7항목(bounds·프로덕션 canon·snapshot 스키마 독립 리뷰·ordering home·MAC·
      리뷰어·런타임 플랫폼)을 별도 게이트로 유지함에 동의.
- [ ] 명명 규약(gap 7): 모델 불변식을 **TIME-AC-001..010 / SAFE-030..052**에 매핑하고 새 INV 시리즈를
      창작하지 않음에 동의.

비준 시 효력: IMPLEMENTATION-PLAN-002 §4 Phase 1의 **ADR-002-008 부분**(line 165–168)을
`tos/src/tos/time/`에 순수·비전송 모델 + property test로 작성 착수 승인. §9.2 Phase-0 7항목과
bounds 승인·독립 리뷰어 지정은 별도 게이트로 남는다.
