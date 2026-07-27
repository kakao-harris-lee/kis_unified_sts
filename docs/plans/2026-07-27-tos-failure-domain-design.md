# 설계 문서 #27 — Failure-Domain Isolation and Deployment Safety 계약 (ADR-002-009, EV-L1) (2026-07-27, v1.1)

> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며
> 스펙 텍스트(RFC/ADR/템플릿/프로파일)를 **변경하지 않는다.** 본 문서는 ADR-002-009를 그린필드
> `tos/src/tos/` 신규 패키지의 Phase 1(EV-L1) **순수·비전송 predicate substrate**로 실현하는
> 계약이다. 코드·git 커밋은 본 문서 범위 밖이다.
>
> **비준 상태**: **2026-07-27 운영자 위임 자동 비준(v1.1) — 효력 발생**(표준지시 2026-07-25 + 본 세션 운영자
> "FD 사이클까지 이어서 끝까지" 지시). 경위: v1.0 저작(스톨 1회 복구) → 오케스트레이터 1차 심사 통과 →
> 독립 비평 리뷰 **REJECT(CRITICAL 3·MAJOR 8·MINOR 9·Gap 8** — 시리즈 첫 설계 REJECT[#8 이후]; 결함은 저작
> 품질이 아니라 **부재 주장 3건의 검증 비대칭**[신규 defect class **anti-phantom**]에 집중; 코드 인용 40건
> 무결점·카운트 15종 전수 일치는 시리즈 최고 평가) → v1.1 전건 반영(API 오류 1회 복구·재검증 후 적용): C1 VP
> 키 2건 실재 정정·C2 §4.4 rcl 이연으로 "3종" 참化+`IsolationKind` 추가·C3 §10.1 item별 재귀속(무주인 2항
> Phase-0 등재)·M1 RFC-002 §24.1 하한 반영(22종)·M4 음극성 재설계·§0.5 anti-phantom 규율 명문화(부재 주장
> 19곳 negative-grep 병기) + **리뷰어 인용 1건 실측 반론**(VER §382=추적성 매트릭스 — 오케스트레이터 원문
> 판정으로 저작자 반론 인용) → 오케스트레이터 강화 스팟체크 통과. **§9.3 판단 지점 전건 승인** — 핵심:
> `tos.failuredomain`·§4 3종(음극성 재설계 포함)·plain FrozenModel·이연 판정 테스트(§0.4e). 효력:
> `tos/src/tos/failuredomain/` Phase 1(EV-L1) predicate substrate 착수 승인. 본 문서는 어떤 FD-EV·ADR
> acceptance·restricted-live·production도 승인하지 않는다.
>
> **이 사이클의 특수성 — 시리즈 최박(最薄) 패키지·"0건 완결(zero-closure)"**: **register 실측
> 결과 FD-EV-001..012 12행 전부 최소 레벨 하한이 `EV-L3`이며 어떤 행도 L1 슬라이스를 갖지
> 않는다**(§1). TIME("TIME-EV 0건")·post-trade("닫는 PTF-EV 0건") 선례의 동형이되 **하한이 더
> 높다**(TIME은 L2, post-trade 5행은 staged `EV-L1/2/3`의 L1 부분 저작). **FD는 어떤 FD-EV도
> EV-L1 증거로 닫지 않으며**(VER-002-001:175 "A lower level cannot substitute for a required
> higher level"), **FD-EV의 L1-decidable 내용은 대부분 형제 소유**이되 **FD-EV-004(cache)·
> FD-EV-011(blast-radius) 2행에 한해 FD 술어·좌표가 L1 층에 기여**한다(§3.5·§4 — M3 정정). ADR-002-009는 "Depends On: ADR-002-001
> through ADR-002-008"이며 §6.4/§10/§15가 ADR-002-013/014/017/029로 명시 이연하는 **통합·
> 소유권-분할 레이어**다. 따라서 본 계약은 **좌표 어휘 + 얇은 도메인-불가지 순수 술어 substrate
> 만 저작하고 어떤 FD-EV도 닫지 않는다.** 얇음은 결함이 아니라 정답이며 사과하지 않는다 —
> **§3.5 소유권 분할표가 본 문서의 노른자**다. 분량은 규범(~1,000줄)보다 짧다(설계 의도).
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   모든 모델은 설계 #1 §2.4 레이아웃에 놓이고 §3.2 허용목록 안에서만 의존한다(§0.3).
> - [설계 #4 — Evidence Store + append-only ledger 계약 (v1.1, 비준·구현됨)](2026-07-20-tos-evidence-store-design.md)
>   + 코드 `tos/src/tos/canonical/`. **canonical `FrozenModel`만 REUSE**한다(Q1 확정 — 문서-레벨
>   frozen·digest 소비자 부재로 `DigestBoundArtifact`/`IndependentIdArtifact` 미채택; §0.3·§3.1).
> - **형제 소유 경계의 규범 원천**(재저작 금지, §3.5): [설계 #17 sbr(ADR-002-017)](2026-07-26-tos-startup-recovery-design.md)·
>   [egress(ADR-002-013)](2026-07-26-tos-egress-commit-proof-design.md)·[cur(ADR-002-024)](2026-07-26-tos-currentness-fencing-design.md)·
>   authority(ADR-002-003/007)·liveauth(ADR-002-007)·rcl(ADR-002-002)·[time(ADR-002-008)](2026-07-21-tos-trustworthy-time-design.md)·
>   spg(ADR-002-014)·brokercap·[afg(ADR-002-022)](2026-07-26-tos-action-flow-budgeting-design.md)·orthostate. 인용은
>   전부 **committed 코드 실측 signature+라인**이다(untracked 코드 인용 금지 — 비준 설계 문서는 인용 가능).
>
> **규범 원천**: `ADR-002-009` (Failure-Domain Isolation and Deployment Safety, Status:
> Proposed). ADR §22 line 513 "Authorship of this ADR does not satisfy these conditions and
> does not authorize restricted-live or production operation." 본 계약도 마찬가지다.
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): failure domain·common-mode·
> safety-cell·isolation-claim·blast-radius 어휘·술어는 전부 broker-agnostic이다. broker session/
> account/rate-limit 공유는 §9·FD-EV-010에서 **capability class**로만 표현하며 KIS 등 특정 broker
> 사실은 등장하지 않는다(브로커 능력은 brokercap 주입).
>
> **리뷰 이력**: v1.0 초안 → **v1.1**. 독립 비평 리뷰 **REJECT**(CRITICAL 3·MAJOR 8·MINOR 9·
> Gap 8): 코드 인용 40건 무결점·카운트 15종 전수 일치였으나 결함이 **"부재 주장" 3건**에 집중.
> **신규 defect class `anti-phantom`**: *존재는 grep했으나 부재는 grep하지 않은 검증 비대칭* —
> "FD 전용 VP 키 없음"(C1: `B_failure_domain_detect`/`_contain` 실재)·"egress §10.1 정확 소유"
> (C3: SEND_STARTED는 orthostate/rcl 소유)·"≤3종 술어"(C2: 실제 4종 — cell-partitioning은 rcl
> 이연)가 전부 미검증 부재/과대 주장이었다. **v1.1 규율: 부재 주장도 반드시 grep**(§0.5). C1~C3·
> M1~M8·MINOR 9·Gap 8·Open Q 처분을 전건 반영(§9.1 로그). 품질 파이프라인(저작→1차 심사→독립
> 비평 리뷰→개정→구현→적대적 코드 리뷰→게이트)은 유지. 수용 서명은 IMPLEMENTATION-PLAN-002 §3
> (Independent-Safety-Reviewer는 본 문서의 저자/통합자여서는 안 됨)을 따른다.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것

1. ADR-002-009 조항별 **EV-L1 도달성 경계**와 **FD-EV 0건 완결** 사실(§1) — register 실측
   (FD-EV-001..012 전부 하한 `EV-L3`, L1 슬라이스 부재) + **FD-AC-001..012 12/12 개별 대응**(§1.1).
2. **소유권 분할표(§3.5, 노른자)**: ADR-002-009의 각 isolation 명제를 **이미 비준·구현된 형제
   술어**에 코드 실측(signature+라인)으로 귀속하고, **명칭 유사 ≠ 명제 동일** 함정을 seam으로
   봉합한다. **재저작 금지** 경계 확정.
3. **FD 고유 소유분(극소·§3.4·§4)**: 형제가 소유하지 않는 것만 — (a) **isolation-domain 좌표
   어휘**(`FailureDomainKind`(22)·`FailureBehaviorKind`·`IsolationClaimStatus`·`IsolationKind`[M2]),
   (b) **Failure-Domain Allocation Matrix·Isolation Claim 레코드 shape**(§5, 문서-레벨 plain frozen),
   (c) **도메인-불가지 순수 술어 정확히 3종**: `unproven_isolation_is_common_mode`·`new_risk_blocked_
   by_unproven_isolation`(M4)·`decision_sole_sourced_from_volatile`(M5)(§4).
4. **firewall·REUSE·명명·sibling-edge-0 결정**(§0.3·§0.4·§3.1) — canonical만 import, sibling
   edge 0.
5. **FD 전용 VP-002 키 2건 실재·신규 저작 0건 실측**(§7 — C1 정정): FD의 numeric containment
   bound는 `B_failure_domain_detect`(VP-002:611, "APPROVE per concrete Failure-Domain Allocation
   Matrix" — §5 산출물 직접 지목)·`B_failure_domain_contain`(:618)로 **이미 존재**하며(둘 다
   ADR-002-009 rationale·VER-002-001:204–205 최소 집합 등재), FD-EV-010 broker-session은
   `B_rate_limit_recovery`(:605) 소유. ⇒ **FD는 신규 VP 키를 저작하지 않고**, 기존 2키의 **값
   승인**을 Phase-0 이관하며, **미키잉 2항(blast-radius 상한·cell-HALT→global-HALT 에스컬레이션)**
   만 신설 후보로 플래그(ADR §21 OQ6).
6. **property-test 하네스 타깃 + import-closure allowlist**(§6) 및 형제 좌표 token drift-lock.
7. **Phase-0 인간 게이트 이관 항목**(§8)과 **판단 지점·독립 리뷰어 공격 지점**(§9.3·§9.4).

### 0.2 하지 않는 것 (경계·NO 목록)

- **ADR/스펙 비준·acceptance·restricted-live·production 어느 것도 승인하지 않는다.** ADR §22는
  10개 게이트 조건 전부 완료 전까지 **Proposed** 유지를 요구한다. ADR acceptance는 오직 *실행된*
  evidence로만 온다(project memory `tos-spec-rfc-authoring-track`).
- **어떤 FD-EV도 완결하지 않는다(§1).** register 최소 레벨이 **전부 `EV-L3` 이상**(6행 `+Security`·
  1행 `EV-L3/5`)이므로 Phase 1은 **FD-EV 0건**을 닫는다. "EV-L1-complete 주장 금지." 모든 substrate
  주장에 규율 태그를 붙인다: **"EV-L1 predicate substrate only; FD-EV-### remains NOT_IMPLEMENTED
  pending EV-L3(+Security) fault injection; the L1-decidable content is sibling-owned."**
- **Failure-Domain Allocation Matrix를 런타임으로 구현하지 않는다.** §5 매트릭스는 **문서-레벨
  frozen 레코드 shape**만이다 — allocation·common-mode 분석·enforcement point 배선·containment
  측정은 배포 프로파일 승인(ADR §22-1)과 런타임 소관이다.
- **어떤 isolation을 강제(enforce)하지 않는다.** ADR §1 line 15 "Separate processes, services,
  containers, nodes, or names do not by themselves prove isolation." 본 계약의 술어는 *분류·fail-
  closed*만 하고, 실제 fence·partition·credential 격리 **메커니즘**은 형제(egress/rcl/authority/
  spg/sbr)와 런타임이 소유한다(§3.5).
- **egress/전송·authority 부여·capacity mutation을 구현하지 않는다.** 설계 #1 §4대로 tos는
  정의상 non-transmitting이다. FD 좌표에 authority-effect가 있으면 전부 **false 상수**이며
  "isolation 좌표가 authority로 쓰이면 거부" 술어를 둔다(§4, 설계 #4 §4.6 `_all_authority_false`
  정신 REUSE).
- **hard fence 메커니즘을 저작하지 않는다.** ADR §4.5 line 100–102 "Process convention, leader
  belief, a dashboard flag, or cooperative shutdown is not a hard fence"의 실제 fence는 형제가
  **injected positive-proof**(`X_hard_fenced: bool|None`, fail-closed)로 이미 소유한다(§3.5).
- **신규 VP-002 키를 저작하지 않는다.** numeric bound 승인·신설은 Phase-0 Bounds-Approver 게이트다.
- **수치 하드코딩 0.** blast-radius·broker-session·partition bound는 전부 주입/이연이며 어떤
  숫자도 모델에 넣지 않는다(CLAUDE.md 설정 기반).

### 0.3 firewall 준수 선언 (설계 #1 §3.2에 대한 본 계약의 준수)

신규 FD 패키지 모델은 다음만 import한다:

- 서드파티: `pydantic`(frozen 모델), `pytest`·`hypothesis`(테스트만). **`numpy`/`pandas`/`pyyaml`도
  import하지 않는다** — FD 결정 규칙은 StrEnum·boolean·집합/구조 논리뿐이고 모든 bound·limit은
  주입 파라미터이며 YAML 파싱은 하네스(설계 #3) 소관이다(closure 최소화 — #5–#24 §0.3 동형).
- tos 자기 자신: **`tos.canonical`**(`FrozenModel`만 — **Q1 확정**: 매트릭스·claim은 문서-레벨
  frozen이고 digest 소비자가 없어 `DigestBoundArtifact`/`IndependentIdArtifact`를 **미채택**,
  §3.1), 자기 자신 모듈. **canonical 외 모든 현재·미래 tos 형제를 import하지
  않는다**(default-deny). 형제 좌표는 **주입 token**(bare string / StrEnum value)으로만 참조하고
  형제 클래스·술어를 import하지 않는다(§3.4/§3.5). **`tos.ordering` 미import**: FD 레코드는 causal
  append-only 순서가 불필요하다(matrix/claim은 순서 비교 대상이 아님 — §3.1). **PROMOTE 0건.
  sibling edge 0건.**
- **`shared.config` 절대 금지**(설계 #1 §6.1, `.importlinter`): `shared.config.__init__`이
  `shared.config.secrets`(→ `os.environ`)를 무조건 전이 import한다. FD 패키지는 어떤 `shared.*`도
  필요로 하지 않는 순수 커널이다.
- **금지(직접·전이 모두)**: `shared.execution`·`shared.kis`·`shared.streaming`·`shared.llm`·
  `shared.storage`·`shared.backtest`·`services.*`·`cli.*`(`.importlinter` forbidden set).
- **firewall 구조 확인(실측 — #21/#24 §0.3 상속)**: `.importlinter`는 `[importlinter:contract:
  tos-operational-firewall]` type=forbidden·source_modules=`tos` 단일 계약이며 intra-tos
  sibling→sibling edge를 구조적으로 금지하지 않는다 — 설계 #1 §3.2 "자기 자신 `tos.*`" 허용
  조항이 커버한다. **신규 FD 패키지는 firewall 도구 무수정 자동 포섭**된다. 본 문서는 그럼에도
  **sibling edge 0건**을 **설계 규율**로 유지한다(§0.4·§3.1).
- 이 배제를 능동 강제하는 것이 §6.1 import-closure 검증 테스트다(**allowlist 형식** — `import` 후
  `sys.modules`의 top-level `tos.*` ⊆ {`tos.canonical`, 자기 자신} assert + `shared.config`·
  `os.environ`·numpy/pandas/yaml 부재 assert).

### 0.4 REUSE / 경계 / 명명 결정 요지 (핵심 아키텍처)

**(a) 중심 판정 — FD는 거의 아무것도 소유하지 않으며 그것이 정답이다.** ADR-002-009는 authority·
capacity·egress·time·deployment·recovery 각 축에 이미 존재하는 형제 ADR(002-001..008/013/014/017)
**위에** 얹힌 통합·소유권-분할 레이어다("Depends On: ADR-002-001 through ADR-002-008"). 따라서
FD의 L1-decidable 내용은 대부분 **정의상 형제가 이미 소유**한다. 본 계약은 이를 **부정하거나
중복 저작하지 않고**(DRY, CLAUDE.md), §3.5에서 코드 실측으로 귀속한 뒤 **형제가 소유하지 않는
극소분만** 저작한다(§3.4·§4). 이 판정이 문서의 성격을 결정한다 — 시리즈 최박 패키지.

**(b) canonical `FrozenModel`만 REUSE, ordering·sibling edge 0 (Q1 확정).** matrix/claim 레코드는
**문서-레벨 plain `FrozenModel`**이다 — 런타임 digest 소비자·위조-탐지 경로가 Phase-1에 없어
`DigestBoundArtifact`/`IndependentIdArtifact`를 **미채택**(매트릭스 identity·digest-binding·registry는
배포 프로파일·evidence 레이어 이연; §3.1). `id=f(digest)`(capsule content-addressed)도 미채택.
**ordering 미import**: FD는 causal 순서 비교가 없다.

**(c) 패키지 위치·명명 = `tos/src/tos/failuredomain/`(권고) 또는 `tos/src/tos/fd/`(차점).**
register domain "Failure Domain"·prefix `FD`(`FD-EV`/`FD-AC`)·ADR 변별 토큰 "Failure-Domain"을
명명 근거로 삼는다. 대안 비교(#18/#21/#24 §0.4a 형식):

- **`tos.fd`(register prefix 직결·차점)**: `FD-EV`/`FD-AC` prefix와 직접 일치하고 대부분 형제가
  register 두문자다(rcl/spg/are/afg/ioc/iap/sbr/hag/cur). 그러나 "fd"는 **cryptic**(file
  descriptor / forward declaration 충돌)하다 — #18 `pr`·#21 `nt`·#24 `ptf`가 정확히 "cryptic"
  이유로 차점 처리된 선례. 단 "FD"는 ADR-title-anchored 2-letter로 `ptf`보다 강하다.
- **선택 `tos.failuredomain`**: ADR 변별 토큰 "Failure-Domain" 직접 명명, non-cryptic, 명사형.
  #21 `Non-Trade→nontrade`·#24 `Post-Trade→posttrade`와 **동형 연접**(`Failure-Domain→
  failuredomain`)으로 최인접 형제 명명 일관성이 강하다. orthostate/brokercap/liveauth/replacement/
  nontrade/posttrade 선례로 수용 가능. **naming은 load-bearing이 아니다**(설계 #1 line 164) —
  운영자가 `tos.fd`로 치환 가능(§9.3-1 판단 지점). 내부 module(`vocabulary.py`·`records.py`·
  `predicates.py`)은 형제 선례 동형. (이하 본문은 `tos.failuredomain`으로 지칭.)

**(d) 앵커 규약 — FD-EV/FD-AC/§-clause/SAFE 앵커, 새 시리즈 창작 금지.** **실측**: ADR-002-009는
**자체 `FD-INV-###` 시리즈가 없다** — §6.1–6.7은 **제목만 붙은 산문 조항**(Strategy-to-Safety
Isolation … Evidence Independence)이며 번호 불변식이 아니다. `FD-AC-001..012`(§17)는 존재하며
`FD-EV-001..012`(register 12행)와 1:1 대응(동일 제목). ⇒ 본 계약은 모델 구성-불변식·술어를
**`FD-EV-###` / `FD-AC-###` / §6.x 조항 / §-clause / `SAFE-###`(§20)**에 앵커하고 **새 INV/AC/EV
시리즈를 창작하지 않는다**. **post-trade의 PTF-INV-001..018 전수 실현 표(§4.0)에 해당하는
INV-실현 표는 FD에 없다**(INV 시리즈 부재) — 이 구조적 차이가 문서를 더 얇게 만든다.

**(e) 명시적 이연 판정 테스트 (M8 — 균일 적용).** 각 ADR 명제에 대해 단일 판정: **"형제가
명제-동일 술어를 committed 코드로 보유하는가?"** — **YES ⇒ 형제 이연**(§3.5 귀속) / **NO ⇒ FD
저작 또는 Phase-0 무주인 등재.** **무주인을 형제 소유로 잘못 기록하면 아무도 저작하지 않는 구조적
fail-open**(C3 item4 교훈 — 이 문서의 유일한 fail-open 클래스). §3.5 전행에 균일 적용하며 판정이
비자명한 3건을 사유와 함께 명시한다:
- (a) **§8.4:228 partition 3-boolean 분류**(FD-AC-003 그 자체 — broker reachable ∧ revocation/
  capacity currentness 상실): 형제에 이 정확한 3-boolean 술어 부재(negative-grep) ⇒ **FD 저작
  후보**(§4.5 신설).
- (b) **§7:188 rule 5 자기-증언 배제**("the path that observes a restrictive state cannot be the
  only unverified source asserting delivery of that restriction"): 소유자 지명 필요 ⇒ authority/cur
  이연(§3.5 §7 행).
- (c) **§13:311–318 6-field cell 선언 + §14:335 step 6 cell→global 에스컬레이션**: 형제 미소유
  (negative-grep) ⇒ **Phase-0 무주인 등재**(§8.2). §4.4 IsolationClaim(도메인-불가지 claim 구조,
  FD 저작 정당)과의 **비대칭 근거**: cell 6-field·에스컬레이션 조건은 배포 프로파일·미승인 수치
  bound에 종속되어 Phase-0 인간 게이트가 옳다.

### 0.5 anti-phantom 규율 (v1.1 신규 — 부재 주장도 grep)

**시리즈 교훈(신규 defect class `anti-phantom`)**: 존재 인용은 grep했으나 **부재 주장**("형제
미소유"·"VP 키 없음"·"tos 전역 무주인")은 grep하지 않은 **검증 비대칭**이 v1.0 REJECT의 유일
결함군(C1~C3)이었다. v1.1은 **모든 부재/무주인/유일-소유 주장에 negative-grep 근거**를 병기한다:
(i) `git grep -l <name> ⇒ 빈 결과` 명시(예: `IsolationKind` 부재·egress `SEND_STARTED` 부재),
(ii) "유일 소유"는 대안 소유자 전수 배제 grep, (iii) "무주인"은 tos 전역 grep 0 + Phase-0
등재(§8.2)로 fail-open 차단. 이 규율을 §3.5·§7·§8.2 전반에 적용한다.

---

## 1. 범위 매핑 — ADR-002-009 조항별 EV-L1 도달성 (닫는 FD-EV 0건)

**EV-level 정의**(VER-002-001 "EV-L1 — Model and Property Verification"; L2 = Component Fault
Test; L3 = Integrated/Adversarial). **결정적 실측**(`EVIDENCE-REGISTER-002.csv` line 101–112):
FD-EV-001..012는 **전부 `Critical`·`NOT_IMPLEMENTED`이고 최소 레벨 하한이 `EV-L3`**이다 — **L1
최소를 가진 행이 하나도 없다.** 따라서 **Phase 1은 어떤 FD-EV도 닫지 않는다.**

**register 실측 (verbatim, 사전 지도와 일치 — 정정 없음)**:

| FD-EV | 제목 | 최소 레벨(csv line) | L1-decidable 소유 |
|---|---|---|---|
| -001 | Strategy-to-Safety Isolation | `EV-L3+Security` (101) | authority(§6.1 grant·control-plane) |
| -002 | Stale Deployment and Duplicate Active Generation | `EV-L3+Security` (102) | authority `GenerationVector`·spg activation·sbr |
| -003 | Control-Plane-to-Egress Partition | `EV-L3+Security` (103) | authority `control_plane_verifiable`·egress |
| -004 | Cache Failure Cannot Create Permission | `EV-L3` (104) | cur `ProofResult`/`CurrentnessAdmission` (+ FD volatile-domain 술어 §4) |
| -005 | Restrictive Event Distribution Failure | `EV-L3` (105) | cur·authority(allow-event≠authority) |
| -006 | Live and Non-Live Environment Isolation | `EV-L3+Security` (106) | authority(cross-env §18.4)·egress(route/env)·liveauth |
| -007 | Risk Capacity Ledger Failover Fence | `EV-L3+Security` (107) | rcl `writer_fenced`·`credible_union_capacity` |
| -008 | Shared Time Common Mode | `EV-L3` (108) | time `common_mode_group`·`independent_reference_count` |
| -009 | Partial Deployment and Configuration Rollback | `EV-L3+Security` (109) | spg `activation_atomic`·`rollback_requires_new_generation`·`rollback_revives_nothing` |
| -010 | Shared Broker Resource Exhaustion | `EV-L3/5` (110) | brokercap(capability class)·FD common-mode 선언 |
| -011 | Safety-Cell Blast-Radius Containment | `EV-L3` (111) | rcl(aggregate serialization) + **FD 좌표**(§4) |
| -012 | Region and Datastore Recovery | `EV-L3` (112) | sbr `restore_worst_credible_union`·`recovery_generation_monotone` |

레벨 분포 **전수 계수**(12/12): `EV-L3` **5행**(004·005·008·011·012) · `EV-L3+Security` **6행**
(001·002·003·006·007·009) · `EV-L3/5` **1행**(010). **L1 슬라이스 = 0행.** ⇒ **닫는 FD-EV = 0건.**

> **완결 주장 규율(설계 #2 §7·#4 §7·TIME §1 상속)**: Phase 1은 *좌표 어휘 + 얇은 순수 술어 저작*
> 까지다. **어떤 항목도 "EV-L1-complete"로 주장하지 않는다**(**VER-002-001:175** "A lower level
> cannot substitute for a required higher level" — 12행 전부 하한 L3+라 EV-L1로 닫히지 않음).
> FD-EV의 L1-decidable 내용은 **대부분 §3.5대로 형제 소유**이며, **FD-EV-004·FD-EV-011 2행에
> 한해 FD 술어·좌표가 L1 층에 기여**한다(§4, M3 정정 — "전부 형제 소유" 과대주장 폐기). §22 게이트
> 조건 8("required EV-L1, EV-L2, and EV-L3 fault evidence is executed")의 EV-L1 레이어는 **형제
> EV-L1 substrate + FD 좌표/술어 substrate**가 공동 제공하나, **FD-EV 행 자체는 EV-L3 도달 전까지
> NOT_IMPLEMENTED**다.

**ADR-002-009 조항 → 분류 (normative 문장 단위, 전수)**. 분류: **core(L1 슬라이스 저작 — FD에는
없음) / substrate(FD 좌표·술어 저작·EV 미주장) / not-Phase-1(형제 소유 또는 런타임 이연)**.

| ADR §-clause (normative) | 분류 | FD-EV / 앵커 | Phase-1 저작 대상 (형제 소유는 §3.5) |
|---|---|---|---|
| §1 Decision (line 15–35: **8항 매트릭스**(§1:19–26)·no-single-failure-both·final-egress·RCL-sole·unproven⇒common-mode·no-auto-rearm) | substrate + 경계 | 전 FD-EV | **§4 도메인-불가지 술어**(unproven⇒common-mode·not-converted-to-permission) + §3.5 귀속 |
| §2 Context (10 unsafe common mode, line 42–53) | 무저작(맥락) | — | **무소유 0건** — 10 common mode는 §3.5 형제 술어가 개별 커버 |
| §3 Decision Drivers (8, line 61–70) | 무저작(맥락) | — | 무소유 0건 |
| §4 Definitions (4.1–4.6, 6 def) | substrate | 어휘 앵커 | **§2 좌표 어휘**(`FailureDomainKind`(22)·`FailureBehaviorKind`·`IsolationClaimStatus`·`IsolationKind`·`SafetyCellScope`·`IsolationClaim` shape). **§4.5 hard-fence·§4.6 blast-radius는 술어 미저작**(m8) — hard-fence=형제 6종 소유(§3.5), blast 수치술어=rcl 이연(C2) |
| §5 Failure-Domain Allocation Matrix (11 field·line 116–132) | substrate | — | **§5 레코드 shape**(`FailureDomainAllocationEntry`) — 문서-레벨 frozen; unknown⇒common-mode |
| §6.1 Strategy-to-Safety Isolation | not-Phase-1 | FD-EV-001 | **authority** 소유(§3.5) — grant·capacity·epoch·egress 거부 |
| §6.2 Capacity Serialization Isolation | not-Phase-1 | FD-EV-007 | **rcl** 소유 — `writer_fenced`·silence≠release |
| §6.3 Final Egress Isolation | not-Phase-1 | FD-EV-003 | **egress** 소유 — `credential_route_authority_disjoint` |
| §6.4 Restrictive-Path Dominance | not-Phase-1 | FD-EV-005 | **authority/cur/egress** — `B_revocation_to_egress`·`B_halt_to_egress`(ADR-002-007 §§9.1–9.5 이연) |
| §6.5 Environment Isolation | not-Phase-1 | FD-EV-006 | **authority(cross-env)/egress/liveauth** |
| §6.6 Recovery Isolation | not-Phase-1 | FD-EV-012 | **sbr** 소유 — `restore_worst_credible_union`·no-independent-grant |
| §6.7 Evidence Independence | not-Phase-1 | — | **evidence(ADR-002-016)** — audit ≠ preventive fence |
| §7 Control/Data-Plane Placement (7 rule, line 184–192) | not-Phase-1 | FD-EV-001/003 | **authority `control_plane_verifiable`**(rule 6)·rcl(rule 3)·egress(rule 4) |
| §8.1 Authoritative Data (no backward generation) | not-Phase-1 | FD-EV-002 | **authority/sbr `GenerationVector`** monotone(RFC-002 §28 OD1 이연) |
| §8.2 Event Infrastructure (allow≠authority·absence≠permission) | not-Phase-1 | FD-EV-005 | **cur/authority** — `CurrentnessAdmission` |
| §8.3 Cache Infrastructure (fail-closed) | substrate | FD-EV-004 | **cur** 소유 + **§4 volatile-domain-sole-source⇒fail-closed** 도메인-불가지 술어 |
| §8.4 Network Partitions (7 partition, line 218–228) | not-Phase-1 | FD-EV-003 | **authority `B_authority_partition_detect`**·전 형제 |
| §9 Identity/Credential/Broker-Session (line 234–246) | not-Phase-1 | FD-EV-006/010 | **egress**(credential/route)·**brokercap**(broker session common-mode)·authority(rotation⇒generation) |
| §10 Deployment/Rollback (line 252–272) | not-Phase-1 | FD-EV-002/009 | **spg** 소유 + authority(no-auto-rearm) + ADR-002-029(deployment provenance 이연) |
| §10.1 Greenfield Egress/Credential Boundary (6, line 276–285) | not-Phase-1 + 무주인 1 | FD-EV-006 | **item별 재귀속(C3 — "정확 소유" 폐기)**: item1(per-cell 존재·유일성)=**미소유**·FD `SafetyCellScope` 후보/Phase-0; item2=egress `credential_route_authority_disjoint`(4-field inventory·safety_cell 없음) **부분**+상류 principal 분류; item3=**orthostate `SEND_STARTED`+rcl `CapabilityClaim`**(egress SEND_STARTED grep 0); item4(market-data 비주문 credential 분리)=**tos 무주인⇒§8.2 Phase-0 등재**; item5=cur monotonic restrictive input; item6=rcl/cur |
| §11 Shared Libraries/Configuration | not-Phase-1 | FD-EV-002 | **spg**(config atomicity·mixed-version) |
| §12 Time Failure Domains | not-Phase-1 | FD-EV-008 | **time `common_mode_group`·`independent_reference_count`** |
| §13 Safety-Cell Blast-Radius (line 311–322) | substrate(좌표만) | FD-EV-011 | **FD `SafetyCellScope` 좌표만**(§2). 수치 non-expansion 술어는 **rcl `credible_union_capacity`:739 이연**(C2 — 유일 수치술어·승인 bound 부재·§13:322 "Aggregate capacity remains serialized by the RCL"); cell 6-field·cell→global 에스컬레이션=Phase-0 무주인(§8.2) |
| §14 Failure Response (7, line 328–338) | not-Phase-1 | 전 FD-EV | **전 형제**(deny/preserve/fence/retain-UNKNOWN=orthostate) |
| §15 Startup/Failover/Recovery (line 344–360) | not-Phase-1 | FD-EV-012 | **sbr(ADR-002-017)** — `restricted_isolation_proven`·`competing_owner_fenced` |
| §16 Observability/Evidence (line 366–388) | not-Phase-1 | — | **evidence(ADR-002-016)** |
| §17 FD-AC-001..012 (12) | 경계·비-acceptance | — | §1.1 (전부 이연) |
| §18 Rejected Alternatives (7) / §19 Consequences | substrate(구조) | — | **§4 술어가 §18.2/18.6/18.7을 구조적 실현**(redundancy/priority/dashboard ≠ permission) |
| §20 Traceability (SAFE) / §21 Open Q (8) / §22 Gate (10) | 경계 | SAFE-### | §7·§8·§9.2 |

**substrate = §1/§4/§5/§8.3/§13/§18** · **not-Phase-1(형제 소유) = §6.1–6.7/§7/§8.1/§8.2/§8.4/
§9/§10/§10.1/§11/§12/§14/§15/§16** · **core(L1 슬라이스) = 0건.** **닫는 FD-EV = 0건.**

### 1.1 FD-AC-001..012 커버리지 표 (12/12 개별 대응 — 전부 이연·0 closure)

> ADR §17(line 398–409)은 `FD-AC-001..012`를 정의하며 `FD-AC-n`은 `FD-EV-n`과 1:1 대응(동일
> 제목). 아래 표가 **12개 전수 개별 대응**을 고정한다. **닫는 AC = 0건**(written case는 요구
> demonstration만 정의·완결 evidence 아님 — §17 line 394 "Registration is not execution").
> **FD가 저작하는 core L1 슬라이스는 없다** — 각 AC의 L1-decidable 요소는 §3.5 형제 소유.

| FD-AC | 요구 demonstration (§17) | Phase-1 대응 | 소유·이연 |
|---|---|---|---|
| AC-001 | Strategy-runtime 붕괴 ↛ authority/capacity/egress | not-Phase-1 | **authority** — `EV-L3+Security` 이연 |
| AC-002 | 구/신 배포 동시 → 단일 writer·단일 egress generation | not-Phase-1 | **spg**(activation)·authority(`GenerationVector`) — `EV-L3+Security` |
| AC-003 | control-plane→egress partition → new-risk 차단(broker reachable) | not-Phase-1 | **authority `control_plane_verifiable`**·egress — `EV-L3+Security` |
| AC-004 | cache loss/eviction/stale/restart ↛ permission/release | not-Phase-1 | **cur** + FD volatile-domain 술어(§4) — `EV-L3` |
| AC-005 | event lag/loss/dup/reorder/replay ↛ revoked authority 보존 | not-Phase-1 | **cur/authority** — `EV-L3` |
| AC-006 | live/non-live credential/route/account/identity 교차 불가 | not-Phase-1 | **egress `credential_route_authority_disjoint`**·authority — `EV-L3+Security` |
| AC-007 | RCL failover가 stale writer fence·conservative commit 보존 | not-Phase-1 | **rcl `writer_fenced`** — `EV-L3+Security` |
| AC-008 | shared time/sync 실패 → 영향 egress 전부 authority 감소 | not-Phase-1 | **time `common_mode_group`** — `EV-L3` |
| AC-009 | partial deployment/mixed config/rollback → denied-live·new-auth 요구 | not-Phase-1 | **spg `rollback_requires_new_generation`·`rollback_revives_nothing`** — `EV-L3+Security` |
| AC-010 | broker-session/limit/rate 고갈 → protective common mode 노출(reserved 미주장) | not-Phase-1 | **brokercap**(capability class) — `EV-L3/5` |
| AC-011 | Safety-Cell 실패 → 선언 blast-radius 내 봉쇄 또는 상위 HALT 에스컬레이션 | not-Phase-1 | **rcl**(aggregate `credible_union_capacity`) + FD `SafetyCellScope` 좌표(§2) — `EV-L3` |
| AC-012 | region/datastore recovery ↛ stale authority revive·UNKNOWN erase·auto re-arm | not-Phase-1 | **sbr `restore_worst_credible_union`**·authority(no-auto-rearm) — `EV-L3` |

**12/12 개별 대응·무저작 0.** **L1 core = 0** — 전 12행 not-Phase-1(형제 소유·EV-L3+ 이연).

---

## 2. 데이터 모델 계약 (좌표 어휘 — 얇음)

**핵심 난제**: FD의 고유 저작은 **형제가 소유하지 않는 좌표 어휘**뿐이다. **실측**: `safety_cell`은
**이미 형제 좌표**(capsule `safety_cell: str|None`(`capsule.py:57`·`snapshot.py:52`)·afg/are
`SAFETY_CELL` enum member(`afg/vocabulary.py:150`·`are/vocabulary.py:81`))이고, `failure_domain`도
**이미 형제 좌표**(afg `failure_domain_separated: bool|None`(`afg/records.py:151`)·capsule common-
mode collapse "failure-domain … not counted"(`capsule/predicates.py:375`))다. **git grep으로
`blast_radius`·`isolation_domain`·`allocation_matrix`만 tos 전역에서 미소유**임을 확인했다. ⇒ FD가
저작하는 어휘는 이 미소유분 + ADR §4 정의를 1:1 전사한 taxonomy enum이며, 기존 형제 좌표는
**참조**한다(재정의 금지 — §3.4 seam).

**표현 원칙**: 모든 레코드는 pydantic v2 frozen(`ConfigDict(frozen=True, extra="forbid")`,
`tos.canonical.FrozenModel` REUSE). update/delete 연산 부재(설계 #4 §2.0 규율 상속).

### 2.1 좌표 어휘 (ADR §4·§5 전사)

**(A) `FailureDomainKind(StrEnum)` (규범 하한 = RFC-002 §24.1, `RFC-002-Architecture.md:1888` —
§5:132 "The matrix SHALL cover at minimum the failure-domain categories listed in RFC-002 §24.1")**
— ADR §4.1:80 18-domain(process·runtime·node·zone·region·datastore·event_infrastructure·cache·
network_path·broker_session·account·credential·workload_identity·deployment_pipeline·clock·
configuration_distribution·parser·shared_risk_library) **+ RFC-002 §24.1 supply-chain 4종
(M1 — ADR §4.1 미열거이나 규범 하한 필수)**: `source_repository`("source-code repository and review
workflow")·`build_toolchain`("isolated build runner and dependency/toolchain resolver")·
`artifact_signing`("artifact signer, key custody, and transparency or admission service")·
`artifact_registry`("content-addressed artifact registry and restore path"). **총 22종(18+4)**.
deployment provenance/supply-chain **거버넌스는 ADR-002-029 소유·FD는 좌표만 소유**(§10:270 —
충돌 없음). **plain, closed StrEnum**(m5 — rlp `vocabulary.py:161–176` "plain, closed StrEnum"
선례; 확장은 Phase-0 프로파일 개정이되 enum 자체는 closed — v1.0 "closed set 아님" 자기모순 정정).
broker-agnostic.

**(B) `FailureBehaviorKind(StrEnum)` (§5 line 122, 전수 전사)** — crash·omission·delay·duplication·
corruption·partition·stale_survival·byzantine_input·exhaustion. matrix 레코드의 "Failure behavior"
필드 값.

**(C) `IsolationClaimStatus(StrEnum)` (§1 line 32·§4.4)** — `ESTABLISHED`(positively 확립)·
`COMMON_MODE`(미확립 ⇒ 보수)·`UNKNOWN`. **극성 규율**: 오직 §4.4 전 필드 positively present일 때만
`ESTABLISHED`; 그 외 전부 `COMMON_MODE`(§4 술어). unknown/untested/undocumented ⇒ `COMMON_MODE`
(§5 line 130 "SHALL NOT be recorded as independent with an explanatory footnote").

**(D) `SafetyCellScope(FrozenModel)` (§4.3 line 92)** — `account`·`portfolio`·`broker`·
`environment`·`authority_epoch`·`writer_epoch`·`egress_scope`(전부 opaque 주입 str|None). **이는
capsule `safety_cell: str` 스칼라 좌표의 구조적 전개**이며 capsule 좌표와 **정렬**한다(capsule을
import하지 않음 — 설계 #4 §3.1 동형 스칼라 참조). "A cell boundary is not proven merely by labels
or namespaces"(§4.3) — 필드 present ≠ isolation 증명(§3.5 sbr `restricted_isolation_proven`이
증명 소유). **Q3 근거(FrozenModel 채택)**: rlp `ScopeDimension`(닫힌 member 카탈로그,
`vocabulary.py:161`)은 scope 차원을 *열거*하나, FD `SafetyCellScope`는 §4.3 7-field를 *구조적으로
담는* 좌표 레코드이므로 enum이 아닌 FrozenModel이 정합적이다 — rlp 레코드(`records.py:151`
`scope_dimensions: frozenset[ScopeDimension]`)가 차원 집합을 담는 것과 동형(§6.4 anchor-drift
property가 7-field↔§4.3 대응을 고정).

**(E) `IsolationKind(StrEnum){PHYSICAL, LOGICAL, COMMON_MODE}` (M2 — 진성 FD 소유분)**: RFC-002
§24.1(`RFC-002-Architecture.md:1911` "the matrix SHALL identify … **physical/logical/common-mode
classification**")·ADR §7:192("Logical separation … SHALL be described as logical separation, not
physical independence")가 규범 필수 분류 필드로 지정한다. `FailureDomainAllocationEntry.isolation_
kind: IsolationKind|None`(§5) — **None⇒`COMMON_MODE` fail-closed**(미분류를 physical/logical로
간주 금지). **negative-grep 확증(anti-phantom §0.5)**: `git grep -l IsolationKind tos/src/tos ⇒
빈 결과`(형제 미소유·진성 FD 신설). **plain, closed StrEnum**(m5). broker-agnostic.

### 2.2 authority-absence 불변식 (§0.2 강제)

FD 좌표는 authority를 부여하지 않는다. `IsolationClaim`·`FailureDomainAllocationEntry`가 authority-
effect 플래그를 담으면 전부 **false 상수**이며(true면 구성 실패 — 설계 #4 §4.6 `_all_authority_
false` 정신), "isolation 좌표가 authority/permission으로 쓰이면 거부" 술어를 §4에 둔다(§1 line 32
"SHALL NOT be converted into permission"의 모델-레벨 실현).

---

## 3. 소유권 분할 (canonical REUSE · sibling-edge-0 · 명제-동일성 · §3.5 노른자)

### 3.1 canonical REUSE + sibling edge 0 (설계 #4 §3.1 동형)

FD는 `tos.canonical`의 **`FrozenModel`만** import한다. **Q1 확정 — plain `FrozenModel`(digest-bound
아님)**: `FailureDomainAllocationEntry`·`IsolationClaim`은 **문서-레벨 frozen 레코드 shape**이고
런타임 digest 소비자·위조-탐지 경로가 Phase-1에 없다(§0.2 매트릭스 비-런타임) — 따라서
`DigestBoundArtifact`/`IndependentIdArtifact`를 **미채택**(매트릭스 identity·digest-binding·registry는
배포 프로파일 승인·evidence 레이어 이연). `IdDerivedArtifact`도 미채택. **ordering 미import**(causal
순서 불요). **PROMOTE 0·sibling edge 0.**

### 3.2 sibling 좌표 주입 seam (edge 0 — 코드 실측)

FD는 형제 술어를 **호출하지 않고**, §5 매트릭스 레코드가 형제 좌표를 **주입 token**(bare string /
StrEnum value)으로 담아 "이 domain의 isolation은 형제 X가 소유"를 **문서화**한다. §6 seam test가
형제를 **test에서만** import해 token이 live member와 일치함을 drift-lock한다(#24 §3.4 선례). token은
`==` 비교; `is` identity는 FD 자신 enum에만.

### 3.3 명제-동일성 함정 개요 (defect-class #3 — 최대 함정)

ADR-002-009는 authority·capacity·egress·time·deployment·recovery의 **isolation 명제**를 서술하나,
그 명제는 **이미 형제가 자기 도메인 축에서 소유**한다. **명칭이 겹치되 명제가 다른** 함정을 §3.5
"명제 동일성" 열이 코드 실측으로 봉합한다. 특히:

- FD "isolation"(§4.4 general isolation claim) **≠** sbr `restricted_isolation_proven`(§17 recovery-
  readiness 8-axis) **≠** authority cross-env isolation(§18.4). **grain·scope 상이.**
- FD "hard fence"(§4.5 정의: 무엇이 fence가 **아닌가**) **≠** authority `hard_fence_proven`·rcl
  `writer_fenced`·afg `stale_writer_hard_fenced`·sbr `competing_owner_fenced`·cur `fence_advances_
  floor`·ioc `mutation_fence_holds`(각 도메인 fence **메커니즘 injected proof**).
- FD "common-mode"(§4.2 general) **≠** time `common_mode_group`(time-source 축)·capsule common-mode
  collapse(input independence 축)·recon per-field independence(evidence 축).

### 3.4 FD 고유 소유분 (핵심 판정 — 무엇이 남았나)

§3.5 전수 귀속 후 **형제가 소유하지 않는 것**만 FD가 저작한다:

1. **좌표 어휘 4 enum + 1 좌표 레코드**(§2): `FailureDomainKind`(22, §4.1+RFC §24.1)·
   `FailureBehaviorKind`(9, §5)·`IsolationClaimStatus`(3)·**`IsolationKind`(3, M2 — tos grep 0)** +
   `SafetyCellScope` 좌표 레코드(§4.3 7-field). (`safety_cell`·`failure_domain` **스칼라/enum-member
   좌표는 이미 형제 소유** — FD는 taxonomy·구조·분류 enum만 신규.)
2. **매트릭스 레코드 shape 2**(§5): `FailureDomainAllocationEntry`(§5 11-field + `isolation_kind`)·
   `IsolationClaim`(ADR §4.4 5-field). **문서-레벨 plain frozen shape만**(Q1) — allocation·
   enforcement·containment은 배포 프로파일·런타임.
3. **도메인-불가지 순수 술어 정확히 3종**(§4 — C2 정정: cell-partitioning 수치술어는 rcl 이연):
   `unproven_isolation_is_common_mode`(§4.1)·`new_risk_blocked_by_unproven_isolation`(§4.2·M4)·
   `decision_sole_sourced_from_volatile`(§4.3·M5). 이 3종은 어떤 형제의 도메인-특수 인스턴스로도
   **일반화되지 않는** §1 core 원칙이다. (§8.4:228 partition 3-boolean은 FD 저작 후보이나 3종 유지
   위해 판단 지점 §9.3-4로 이연 — 과잉 저작 회피.)

**그 외 전부 형제 소유(재저작 금지)** — 이것이 §3.5다.

### 3.5 소유권 분할표 (본 문서 최대 함정 지대·노른자 — 코드 실측 signature+라인)

> **소유권 분할 명시(#8 C1·#24 M4 교훈)**: ADR-002-009는 **failure-domain taxonomy(22)·isolation-
> kind 분류(`IsolationKind`)·common-mode 기본값 원칙·safety-cell 좌표**만 신규 소유하며(blast
> 수치술어는 rcl 이연 — C2), authority grant·capacity serialization·final
> egress·time common-mode·deployment/rollback fencing·recovery readiness·evidence custody를
> **소유하지 않는다**. 아래 표의 "형제 소유(재저작 금지)"·"seam·명제 동일성" 열이 각 경계를 고정한다.
> 인용은 전부 **committed 코드 실측**이다(§0.3 untracked 인용 금지).

| ADR 조항/개념 | FD 소유 (Phase 1) | 형제 소유 (재저작 금지·실측) | seam·명제 동일성 |
|---|---|---|---|
| §6.1 Strategy-to-Safety (FD-EV-001) | (미소유) 좌표만 | **authority** `control_plane_verifiable`→denied(`predicates.py:714–733`)·grant 술어·cross-env(`:222/:271`, §18.4) | authority가 "strategy/UI/operator identity ↛ grant/capacity/epoch/egress" 소유. FD는 domain taxonomy만 |
| §6.2 Capacity Serialization (FD-EV-007) | (미소유) | **rcl** `writer_fenced`(`predicates.py:507`)·`credible_union_capacity`(`predicates.py:739`, empty-fail-closed·no-last-write-wins) | rcl-only mutation(§1 line 30). silence/lease-expiry/missing-ACK/process-death ↛ release는 rcl 소유 |
| §6.3 / §10.1 Final Egress·Credential Boundary (FD-EV-003/006) | item1 좌표 후보·item4 무주인(§8.2) | **egress** `credential_route_authority_disjoint`(`predicates.py:405`, 4-field inventory·**safety_cell 필드 없음**)·`CredentialRouteInventoryEntry`; **orthostate `SEND_STARTED`+rcl `CapabilityClaim`**(`rcl/state.py:133`) | **§10.1 item별 재귀속(C3 — "정확 소유" 폐기)**: item2=egress disjointness **부분**(per-cell/safety_cell 아님)+상류 principal 분류; item3=orthostate/rcl(**egress `SEND_STARTED` grep 0**·negative-grep §0.5); item1(per-cell 유일성)=FD `SafetyCellScope` 후보/Phase-0; item4(market-data 분리)=tos 무주인⇒§8.2; item5=cur; item6=rcl/cur |
| §6.4 Restrictive-Path Dominance (FD-EV-005) | (미소유) | **authority/cur/egress** — `B_revocation_to_egress`·`B_halt_to_egress`·`B_egress_hard_fence`(VP-002); ADR-002-007 §§9.1–9.5 fenced single-use protocol(§6.4 line 160 명시 이연) | restrictive state가 egress에서 authoritative 되는 bound는 형제 VP·egress 소유. FD numeric 0 |
| §6.5 Environment Isolation (FD-EV-006) | (미소유) | **ioc `ConformanceAxis.LIVE_NONLIVE`**(`vocabulary.py:93`)·**brokercap `ConformanceClass.CLASS_D_NON_LIVE`**(`vocabulary.py:146`)·`environment_binding_ok`(`predicates.py:644`)·authority cross-env(`:271`, §18.4)·hag `ApprovalScope.environments`(`state.py:119`) | **M7 정정**: live/non-live **축은 ioc `LIVE_NONLIVE`·brokercap `CLASS_D_NON_LIVE` 소유**·환경 좌표 필드는 다수 패키지 보유 — **닫힌 값 enum만 미소유**이며 **ioc §28 q3 선례대로 Phase-0 INSTANCE 이연**(FD 신설 불필요; §9.4-2 해소) |
| §6.6 / §15 Recovery Isolation (FD-EV-012) | (미소유) | **sbr** `restricted_isolation_proven`(`predicates.py:407`, `IsolationFacts.all_proven()` 8-axis, §17 line 447 "labels/tickets/instances do not prove isolation")·`restore_worst_credible_union`(`:741`)·`competing_owner_fenced`(`:604`)·`recovery_generation_monotone`(`state.py:161`) | **명제 유사·scope 상이(핵심 seam)**: sbr = recovery-readiness isolation(ADR-002-017); FD §4.4 = general cross-domain isolation claim. **sbr `IsolationFacts` 재저작 금지** |
| §6.7 / §16 Evidence Independence | (미소유) | **evidence(ADR-002-016)** replay/store·"audit ↛ preventive fence"(§6.7) | evidence 레이어 소유. FD는 evidence를 permission으로 쓰지 않음(§4 not-converted 술어가 정신 공유) |
| §7 Control/Data-Plane (7 rule) | (미소유) | **authority** `control_plane_verifiable`(rule 6 line 189)·**rcl** stale-writer(rule 3)·**egress** front-end-allow-불충분(rule 4) | rule별 형제 소유. FD는 §5 매트릭스가 "logical ≠ physical"(§7 line 192)을 레코드 shape로 문서화만 |
| §8.1 Authoritative Data (no backward gen) | (미소유) | **authority/sbr** `GenerationVector`(`authority/state.py:29`·`sbr/state.py`)·monotone; RFC-002 §28 OD1(split-brain storage) 이연 | generation 후진 금지는 authority/sbr 소유. FD 미저작 |
| §8.2 Event Infra (allow≠auth·absence≠perm) | (미소유) | **cur** `CurrentnessAdmission`(ADMIT/DENY, `vocabulary.py:113–114`)·`ProofResult`(CURRENT/RESTRICTED/UNKNOWN, `:96–98`)·**authority** | "receipt of allow event is not continuing authority"(§8.2)는 cur/authority 소유 |
| §8.3 Cache Infra (fail-closed) | **§4 volatile-domain 술어** | **cur** `ProofResult.UNKNOWN`⇒non-admit·`fence_advances_floor`(`predicates.py:415`) | **명제 상이**: cur = 런타임 currentness proof/latch; FD = 도메인-불가지 "volatile domain(cache/absence) sole-source ⇒ fail-closed" 구조 술어(§4). cur이 실제 mechanism 소유 |
| §8.4 Network Partitions (7 partition) | `FailureBehaviorKind.partition` 좌표 + **§8.4:228 3-boolean 저작 후보**(M8a·§9.3-4) | **authority** `B_authority_partition_detect`(VP-002:121, **ADR-002-003** — m6 정정, rationale:125)·전 형제 partition 분석 | 7 partition(§8.4:218–228)은 형제 축별 소유. **§8.4:228 FD-AC-003 3-boolean**(broker reachable ∧ revocation/capacity currentness 상실 ⇒ high-severity)은 형제 미소유(negative-grep §0.5)⇒**FD 저작 후보이나 3종 유지 위해 이연**(§9.3-4) |
| §9 Identity/Credential/Broker-Session (FD-EV-006/010) | (미소유) common-mode 선언·**identity inventory 무주인 등재**(§8.2) | **egress**(credential/route 4-field)·**brokercap** `CapabilityStatus`(broker session/limit/rate)·**authority**(rotation⇒generation) | **Gap 정정**: §9:238–242 **identity inventory 5종**(live-tx·SCP-mutation·RCL-writer·epoch/config-change·shared broker-session/limit/rate/cancel)은 **egress 4-field inventory로 커버 불가**(egress는 credential+route disjointness만; 5-종 열거는 배포 프로파일 §8.2). "priority ↛ reserved capacity"(§9:246)=brokercap |
| §10 / §11 Deployment·Config·Rollback (FD-EV-002/009) | (미소유) | **spg** `activation_atomic`(`predicates.py:505`)·`activation_serializable`(`:548`)·`envelope_incompatible`(`:316`)·`rollback_requires_new_generation`(`:702`)·`rollback_revives_nothing`(`:728`)·`compatibility_manifest_matches`(`:774`)·`hard_and_runtime_versions_match`(`:883`); **authority** `automatic_rearm_denied=True` unconditional(`predicates.py:721/740`)·`rearm_gate`(`:749`); ADR-002-029(deployment provenance 이연, §10 line 270) | **spg가 deployment/mixed-version/rollback fencing 전면 소유.** "rollback is a new deployment generation"(§10 line 268) = spg `rollback_requires_new_generation`. "SHALL NOT automatically re-arm"(§10/§15) = authority `automatic_rearm_denied`. **재저작 금지** |
| §12 Time Failure Domains (FD-EV-008) | (미소유) | **time** `common_mode_group`(`elements.py:134`)·`independent_reference_count`(`predicates.py:682`, common-mode collapse §7 line 184)·`source_disagreement_within_bound`·`freshness_verdict` | "two time sources using one upstream are not independent"(§12 line 303) = time `common_mode_group` collapse. **재저작 금지** |
| §13 Safety-Cell Blast-Radius (FD-EV-011) | **`SafetyCellScope` 좌표만**(§2) | **rcl** `credible_union_capacity`(`predicates.py:739`, aggregate serialization)·`CapacityState` | **C2 정정**: "distributing reservations among cells ↛ exceed aggregate"(§13:321) 수치 non-expansion 술어를 **rcl 이연**(§13:322 "Aggregate capacity remains serialized by the RCL" — rcl가 유일 aggregate 권위·승인 bound 부재). cell 6-field·cell→global 에스컬레이션=Phase-0 무주인(§8.2·§0.4e-c) |
| §14 Failure Response (7 step) | (미소유) | **전 형제** — deny(authority)·preserve capacity(rcl)·fence(형제)·retain UNKNOWN(**orthostate** `KnowledgeState`) | "missing ACK ≠ non-acceptance·cancel ACK ≠ FQP·lease expiry ≠ economic expiry"(§14 line 338)는 orthostate/rcl 소유 |
| §15 Startup/Failover/Recovery | (미소유) | **sbr(ADR-002-017)** — §15 line 360 "ADR-002-017 governs the closed Recovery Barrier … cannot substitute" 명시 이연 | sbr 전면 소유. FD 미저작 |
| §16 Observability/Evidence | (미소유) | **evidence(ADR-002-016)** — "documentation/written tests are not completed evidence"(§16 line 388, VER-002-001) | evidence 소유 |
| §13/§4.1 좌표 (rlp 교차·M6) | `SafetyCellScope`·`FailureDomainKind`(구조 좌표) | **rlp `ScopeDimension.SAFETY_CELL`(`vocabulary.py:179`)·`FAILURE_DOMAIN`(`:196`)** | **명제 상이**: rlp = **trial-plan scope 차원 카탈로그**(어느 축으로 trial scope를 좁히나 — 닫힌 member 열거); FD = **cell/failure-domain 구조 좌표**(§4.3 7-field·§4.1 22-taxonomy). 토큰 겹치나 enum(rlp)↔record/taxonomy(FD)로 별개 |
| §6.5/§15 human-approval env (hag·M6) | (미소유) | **hag `ApprovalScope.environments`(`state.py:119`)** | human approval scope의 environment 집합은 hag 소유. FD는 §6.5 environment isolation을 ioc/brokercap/hag로 귀속(FD 미저작) |
| §6.4/§7 gate authority 분리 (venue·M6) | (미소유) | **venue `gate_authority_separated`(`predicates.py:723`)** | venue = "gate authority ≠ execution authority" defense-in-depth 분리. FD control/data-plane 분리(§7)의 venue-축 인스턴스 — FD 미저작 |

> **핵심 소유권 판정 4건(명제-동일성 함정 봉합)**:
> 1. **sbr ↔ FD 분할(isolation 명제 — 최대 경계)**: sbr `restricted_isolation_proven`(`predicates.py:407`)이
>    **recovery-readiness의 8-axis positive isolation proof**(ADR-002-017 §17)를 소유하고, §17 line
>    447 verbatim "Logical strategy separation, different UI labels, separate recovery tickets,
>    distinct process instances, or unused nominal capacity do not prove isolation"·SBR-INV-008이
>    이미 "common failure domains"를 8 axis 중 하나로 열거한다. FD §4.4 Isolation Claim은 **general
>    cross-domain 구조**(assumptions/excluded-common-modes/enforcement/verification/residual)이며
>    scope가 다르다(sbr=recovery / FD=general matrix). **sbr `IsolationFacts` 재저작 절대 금지** —
>    FD는 general shape·status enum만, 실제 8-axis proof는 sbr 소유. **Q2 처분**: FD `IsolationClaim.
>    verification_cases`는 sbr `IsolationFacts.all_proven()`(`records.py:153`) 결과를 **참조 token**
>    으로 담는 구조로 정합(§9.4-1). (참조는 §3.2 seam token — sbr import 아님.)
> 2. **spg ↔ FD 분할(deployment — 전면 형제)**: §10/§11의 immutable artifact·mixed-version·config
>    atomicity·rollback fencing이 **전부 spg 술어**(activation_atomic·rollback_requires_new_
>    generation·rollback_revives_nothing·compatibility_manifest_matches·hard_and_runtime_versions_
>    match)로 이미 존재한다. FD §10은 **무저작**이며 spg로 귀속. ADR §10 line 270이 provenance를
>    ADR-002-029(미패키지 governance ADR)로 별도 이연.
> 3. **hard-fence 편재 소유(§4.5 정의 vs 메커니즘 — m7 정밀화)**: "hard fence"는 단일 "패턴"이
>    아니라 **6개 형제가 각기 다른 signature·명제로 소유**한다: authority `hard_fence_proven`
>    (`predicates.py:485–500`, `is True or lease_expiry_fence_elapsed is True` — stale authority)·
>    rcl `writer_fenced`(`:507` — RCL writer)·afg `stale_writer_hard_fenced`(`:1047`, `is True`,
>    §20:429 — action-flow writer)·sbr `competing_owner_fenced`(`:604` — recovery competing owner)·
>    cur `fence_advances_floor`(`:415` — currentness floor)·ioc `mutation_fence_holds`(`:492` —
>    mutation). fence **메커니즘은 runtime+broker 이연**(authority §5.8 "The hard fence itself is
>    runtime + broker"). FD §4.5는 **"무엇이 fence가 아닌가"의 정의**(process convention/leader
>    belief/dashboard flag/cooperative shutdown ≠ fence)이며 §4.2 `common_mode_not_converted_to_
>    permission`가 정신을 실현하되 **형제 fence 6종을 재저작하지 않는다.**
> 4. **egress ↔ FD 분할(§10.1 — C3 "정확 소유" 폐기·item별 재귀속)**: §10.1 6 item은 단일 소유자가
>    아니다. **item2**(egress identity가 usable credential+route 보유·나머지 미보유)만 egress
>    `credential_route_authority_disjoint`(`predicates.py:405`) 소유이되 **4-field inventory·safety_
>    cell 없음**이라 per-cell 유일성(item1)을 증명 못 한다. **item3**(broker op이 fenced capability+
>    `SEND_STARTED` 뒤)=**orthostate `SEND_STARTED`+rcl `CapabilityClaim`**(**egress `SEND_STARTED`
>    grep 0** — negative-grep §0.5). **item1**(per-cell 존재·유일성)=FD `SafetyCellScope` 후보/
>    Phase-0. **item4**(market-data 비주문 credential 분리)=**tos 전역 무주인**(negative-grep)⇒**§8.2
>    Phase-0 등재**(무주인을 형제 소유로 기록하면 아무도 저작하지 않는 fail-open — 이 문서 유일
>    구조적 fail-open 클래스, §0.4e). item5=cur monotonic restrictive input·item6=rcl/cur.

---

## 4. FD 고유 순수 술어 substrate (도메인-불가지 정확히 3종 — 얇음)

**앵커는 §1:32/ADR §4.4/§5:130/§8.3/§18·SAFE-###**이며 **새 시리즈를 창작하지 않는다**(§0.4d).
**정확히 3종**(C2 정정 — cell-partitioning 수치술어는 rcl 이연, §3.5 §13)이며 어떤 형제 도메인-특수
인스턴스로도 일반화되지 않는 §1 core 원칙이다. **모든 술어는 authority/permission을 부여하지 않고
block/classify만 한다**(§2.2 — 부여는 형제 소유). **fail-closed discipline**: 미증명/미확립/absent/
None은 **절대 vacuous permissive가 되지 않으며**, 음극성 판정만 하고(양성 permission은 형제 소유),
각 가드에 **both-ways canary**(가드가 실제 발화 ∧ 정당한 통과를 막지 않음)를 붙인다. **소절 제목 =
함수명**(m3).

### 4.1 `unproven_isolation_is_common_mode` (§1:32·ADR §4.4·§5:130)

`unproven_isolation_is_common_mode(claim: IsolationClaim | None) -> bool`: **True(=common-mode)**
when ADR §4.4가 요구하는 5-field(assumptions·excluded_common_modes·enforcement_mechanisms·
verification_cases·residual_risk) 중 **하나라도 부재/미열거**이거나 `claim is None`; **False(=
established)**는 5-field 전부 positively present일 때만. 내부 helper `_isolation_claim_status`가
`IsolationClaimStatus`(§2.1C)를 산출.
- **∅-공허 양방향**: `excluded_common_modes` **빈 집합**은 "미분석"과 "positively 제외 없음"을
  **구별**한다 — §5:130 "Unknown, untested, or undocumented sharing SHALL be recorded as common-
  mode"에 따라 **미분석(sentinel None)⇒common-mode(True)**; positively-declared-empty
  (`ExplicitlyAnalyzedEmpty` 마커·§6 카운트 포함)는 나머지 4-field present 시 established(False)
  허용(설계 #24 §4.8 ∅ 양방향 상속). vacuous permissive 금지·정당 established 차단 금지.
- **극성**: 음극성은 `is None`/미열거; established는 5-field **양성 identity conjunction**으로만
  (truthy-sentinel 금지 — memory 교훈). [SAFE-030, SAFE-031]

### 4.2 `new_risk_blocked_by_unproven_isolation` (§1:32·§18.2/18.6/18.7 구조적 실현·M4 재설계)

**M4 최우선 fail-open 정정** — v1.0 `common_mode_permits_new_risk(status, redundancy_count,
operator_confident, dashboard_healthy, replay_available, audit_present)`는 permission-함의 이름 +
5 permissive 인자로 fail-open 위험이었다. **재설계**: `new_risk_blocked_by_unproven_isolation(
status: IsolationClaimStatus | None) -> bool`, 본문 **`return status is not IsolationClaimStatus.
ESTABLISHED`**(None⇒`True`=blocked). **5 permissive 인자를 시그니처에서 완전 제거**(redundancy/
confidence/dashboard/replay/audit는 **test-only 입력**으로만). §1:32 verbatim "It SHALL NOT be
converted into permission by redundancy count, operator confidence, a healthy dashboard, replay
capability, or an audit trail"·§18.2/18.6/18.7 기각을 **구조적 실현**(그 5 요소가 signature에 없어
caller 위조 불가).
- **both-ways canary**: (a) `COMMON_MODE`/`UNKNOWN`/None ⇒ `True`(blocked, 가드 발화); (b)
  `ESTABLISHED` ⇒ `False`(not-blocked) — 단 **not-blocked ≠ permission**(실제 authority 부여는
  authority/liveauth 소유·§2.2·§3.5). test-only 5 인자는 "결과를 바꾸지 못함"을 property로 검증
  (전 조합 결과 불변). [SAFE-041, SAFE-051] (**m2 정정**: SAFE-045[live/non-live·§6.5]→**SAFE-051**
  — §4.2는 evidence/redundancy-non-substitution[SAFE-051/052] 명제이지 환경격리가 아님.)

### 4.3 `decision_sole_sourced_from_volatile` (§8.2·§8.3·§10.1 item 5·M5 주입화)

**M5 주입화**: `decision_sole_sourced_from_volatile(support_domains: frozenset[FailureDomainKind],
volatile_domains: frozenset[FailureDomainKind] | None) -> bool | None`: support가 `volatile_
domains` **단독**이면 `True`(⇒소비자 fail-closed); **`volatile_domains is None`(미확립) ⇒ `None`
(UNKNOWN, fail-closed)** — v1.0의 하드코딩 `{cache, event_infrastructure}`를 **주입 제거**(broker/
deployment별 volatile 집합은 프로파일 소관·집합 하드코딩 0). §8.3 "cache SHALL NOT be the sole
source … fail closed"·§8.2 "absence of a deny event is not proof of permission"·§10.1 item5
"absence, deletion, expiry, or recovery never establishes current permission."
- **명제 상이(§3.5 §8.3 seam)**: **cur이 런타임 currentness proof/latch mechanism 소유** — FD는
  도메인-불가지 "support ⊆ volatile ⇒ permission 근거 불가"의 **구조적 분류**만. cur `ProofResult.
  UNKNOWN`⇒non-admit가 실제 집행.
- **∅ 양방향**: `support_domains` 빈 집합 ⇒ support 전무 ⇒ `True`(최악); `volatile_domains` 빈
  집합(주입됨) ⇒ non-volatile support면 `False`(정당 통과). [SAFE-030, SAFE-048]

**(§4.4 cell-partitioning 술어는 v1.0에서 삭제 — C2**: rcl `credible_union_capacity`:739 이연,
§3.5 §13·§8.2; blast-radius SAFE-003/004/013은 rcl/배포 프로파일로 이관.**)**

---

## 5. Failure-Domain Allocation Matrix 레코드 shape (§5 — 문서-레벨 frozen)

§5(line 116–132)의 11-field 매트릭스를 **frozen 레코드 shape**로 1:1 저작한다. **런타임 아님** —
allocation·common-mode 분석·enforcement 배선·containment 측정은 배포 프로파일 승인(§22-1)·런타임.

`FailureDomainAllocationEntry(FrozenModel)`(Q1 — plain frozen·digest-bound 아님) — **11 필드(§5 표
전사) + `isolation_kind`(M2)**: `authority_or_state`·`safety_cell: SafetyCellScope`·`failure_
domains: frozenset[FailureDomainKind]`·`shared_dependencies`·`failure_behavior: FailureBehaviorKind`·
`unsafe_consequence`·`prevention`(non-bypassable enforcement point·주입 형제 owner token)·
`detection_and_containment`(observable signal·approved bound = 주입, VP)·`recovery`(reconciliation·
epoch·re-arm barrier — 형제 owner token)·`evidence`(acceptance case·registered evidence id)·
`residual_risk`(remaining common mode·approved owner) **+ `isolation_kind: IsolationKind | None`**
(RFC-002 §24.1:1911 필수 physical/logical/common-mode 분류; **None⇒`COMMON_MODE` fail-closed**, §2.1E).
- **`shared_dependencies` common-mode 배경 7종(ADR §4.2:86 전사·m8)**: 서로 다른 endpoint/replica/
  name이 **하나의 administrator·credential·database·network·clock·library·broker resource**(7종)를
  공유하면 그 dependency는 common-mode다 — `shared_dependencies`가 이 7-배경 축을 담아 §4.1 판정
  입력이 된다(time `common_mode_group`이 time-축 인스턴스인 것과 동형·§3.5 §12).
- **불변식(§5 line 130)**: unknown/untested/undocumented sharing ⇒ `shared_dependencies`에 기록되고
  entry isolation status는 §4.1로 common-mode. "SHALL NOT be recorded as independent with an
  explanatory footnote" — **footnote-형 independent 주장 표현 불가**(구조적: independent 마킹은
  §4.1 `unproven_isolation_is_common_mode(claim) is False` 요구).
- `IsolationClaim(FrozenModel)` — **ADR §4.4 5-field**. `FailureDomainAllocationEntry`가 참조.
- **prevention/recovery/owner 필드는 형제 owner token**(예: `"egress.credential_route_authority_
  disjoint"`·`"spg.rollback_requires_new_generation"`·`"rcl.writer_fenced"`) — §3.2 seam으로
  drift-lock(§6). FD는 owner를 **가리키기만** 하고 enforcement를 저작하지 않는다.

---

## 6. property-test 하네스 타깃

§1 분류에 정렬. **닫는 FD-EV = 0건** — 어떤 test-target도 FD-EV closure·acceptance를 주장하지
않는다(규율 태그 부착). 각 술어에 **both-ways canary**·**fixture clean-vs-illegal 정합**(#8 교훈).
**hypothesis 전략은 ∅/None/forgery/common-mode-default 케이스를 명시 포함**한다.

- **§4 도메인-불가지 술어 3종(전 substrate)**: `unproven_isolation_is_common_mode`(5-field 전부-
  present만 False=established·미분석-∅⇒True·declared-empty-∅⇒established 허용, 양방향); **`new_risk_
  blocked_by_unproven_isolation`(M4 — status만; test-only 5 인자[redundancy/confidence/dashboard/
  replay/audit] 각 축 조합에서 결과 불변 property·caller 위조 불가)**; `decision_sole_sourced_from_
  volatile`(volatile-only⇒True·support-∅⇒True·`volatile_domains` None⇒None·혼합⇒False). **(cell_
  partitioning 술어 property는 삭제 — C2 rcl 이연.)**
- **§2 enum per-member 바인딩**: `FailureDomainKind`(**22** — 18+supply-chain 4)·`FailureBehaviorKind`
  (9)·`IsolationClaimStatus`(3)·**`IsolationKind`(3)** 각 member를 §4.1/§5/§1/RFC §24.1 라인에
  **개별 계수 property**로 바인딩(누락 0 강제 — #21 MINOR-1 "N개 중 1개 누락" 교훈). **plain closed
  StrEnum**(m5 — 미등록 값은 구성 거부; "closed set 아님" 자기모순 제거) property.
- **§5 레코드 불변식(Q1 — plain frozen)**: `FailureDomainAllocationEntry`/`IsolationClaim`을 무작위
  생성해 (i) frozen immutability(update/delete 부재)·(ii) authority-effect 전부 false(§2.2 위반 시
  구성 실패)·(iii) **`isolation_kind is None`⇒common-mode**(§2.1E)·(iv) unknown-sharing⇒`shared_
  dependencies` 기록·§4.1 common-mode property. (digest same-id/diff-bytes forgery property는 Q1
  plain-frozen 채택으로 **미적용** — digest-bound 미채택.)
- **규율 태그**: 전 타깃에 "EV-L1 predicate substrate only; closes no FD-EV; L1-decidable content
  is sibling-owned per §3.5" 부착.

### 6.1 import-closure 검증 테스트 (C1 강제 — 설계 #4 §7.1·#24 §7.1 상속)

서브프로세스에서 `import tos.failuredomain`만 한 뒤 `sys.modules` 검사(**allowlist 형식**): top-
level `tos.*` ⊆ {`tos.canonical`, 자기 자신} assert; `shared.config`·`shared.config.secrets`·
`os.environ`/`os.getenv`·`numpy`·`pandas`·`yaml`·**`tos.ordering` 및 모든 형제 패키지 부재** assert.
required check(`tos-firewall`, `tools/tos_firewall_check.py` + `.importlinter`)와 함께 green이어야
§0.3 선언이 능동 성립. **sibling edge 0 회귀 고정.**

### 6.2 sibling token drift-lock (§3.2·§5 owner 필드)

§5 owner 필드·§1.1·§3.5 형제 귀속에 등장하는 **전 형제 token**을 **test-only 모듈**이 형제를 import해
live member와 대조(drift-lock — #24 §3.4 선례; **Gap 정정 — §3.5 전체와 동기화·13종 추가**). 대상
token(전수 계수 = §3.5 인용 전체): egress `credential_route_authority_disjoint`·rcl `writer_fenced`·
`credible_union_capacity`·**`CapabilityClaim`**·spg `activation_atomic`·**`activation_serializable`·
`envelope_incompatible`·`hard_and_runtime_versions_match`**·`rollback_requires_new_generation`·
`rollback_revives_nothing`·`compatibility_manifest_matches`·authority `GenerationVector`·`control_
plane_verifiable`·`automatic_rearm_denied`·**`hard_fence_proven`·`rearm_gate`**·sbr `restricted_
isolation_proven`·`restore_worst_credible_union`·**`competing_owner_fenced`·`recovery_generation_
monotone`**·time `common_mode_group`·`independent_reference_count`·cur `CurrentnessAdmission`·
`ProofResult`·**`fence_advances_floor`**·orthostate `KnowledgeState`·**`SEND_STARTED`**·brokercap
`CapabilityStatus`·**`CLASS_D_NON_LIVE`·`environment_binding_ok`**·**ioc `ConformanceAxis.LIVE_
NONLIVE`·`mutation_fence_holds`**·**afg `stale_writer_hard_fenced`**·**hag `ApprovalScope.
environments`**·**venue `gate_authority_separated`**·**rlp `ScopeDimension.SAFETY_CELL`·`FAILURE_
DOMAIN`**. 각 token은 `vocabulary.py` 로컬 상수로 고정하고 seam test가 실 member와 `==` 대조(test
import는 §6.1 closure 불계상). **누락 0 강제.** **negative-token(§0.5)**: egress `SEND_STARTED`·
`IsolationKind`(tos 전역)는 **부재 assert**로 회귀 고정.

### 6.3 run manifest 정렬 (VER-002-001 §3 immutable baseline)

FD 전용 run manifest 템플릿은 없다 — 설계 #1 §5.1 REUSE. **Gap 정정**: VER-002-001 §3(:84 "Every
evidence run SHALL bind to an immutable baseline")에 정합시킨다 — git commit digest·`tos` 버전·**test
harness version(VER:106)**·**fault-injection schedule + seed(VER:107·append-only VER:350)**·baseline
manifest digest·산출 sha256. (v1.0 "인터프리터+고정 의존성" 문구는 VER §3 baseline 어휘에 대응이
없어 harness-version·fault-schedule로 교체.) FD-EV 행을 **닫지 않으므로** baseline은 substrate
property run에만 적용된다.

### 6.4 anchor-drift property (`SafetyCellScope` ↔ ADR §4.3 — Gap·rlp §7.2 선례)

`SafetyCellScope` 7-field(account·portfolio·broker·environment·authority_epoch·writer_epoch·egress_
scope)가 **ADR §4.3:92 열거와 1:1 대응**함을 property로 고정한다(rlp §7.2 `ScopeDimension`↔
`TrialScope` anchor-drift 선례 — 스펙 좌표와 코드 좌표가 drift하면 실패). 필드 추가/삭제/개명 시
ADR §4.3 재확인 강제 — "스펙 용어 = 코드 용어"(설계 #1 §2.4)의 회귀 잠금.

---

## 7. bounds — FD 전용 VP-002 키 2건 실재·신규 저작 0건 (C1 정정) + Phase-0

**C1 정정(anti-phantom §0.5)** — v1.0 "FD 전용 bound 키가 없다"는 **부재 미검증 거짓**이었다.
negative-grep이 아니라 실측한 결과 **FD 전용 키 2건이 실재**한다:

| FD 전용 bound (VP-002) | line | 근거·상태 |
|---|---|---|
| `B_failure_domain_detect` | **611** | "APPROVE **per concrete Failure-Domain Allocation Matrix**"(§5 산출물 직접 지목)·"isolation-assumption breach to authoritative detection for the affected Safety Cell (ADR-002-009)"·`STOP_NEW_RISK`·**VER-002-001:204 최소 집합 등재** |
| `B_failure_domain_contain` | **618** | "authoritative failure-domain detection to completed denial or broader HALT at every affected final egress (ADR-002-009)"·`HALT`·**VER-002-001:205 등재** |
| `B_rate_limit_recovery` | 605 | FD-EV-010 broker-session/rate 공유(§9)·"protective/reconciliation traffic budget must survive"(ADR-002-001 §7.5)·**충분성 Phase-0 open(Q4)** |

**추가 형제-소유 bound**(FD 매트릭스가 owner token으로 참조·재저작 아님): `B_authority_partition_
detect`(121, **ADR-002-003** — m6)·`B_revocation_to_egress`(135, -007)·`B_halt_to_egress`(142,
-007/015)·`B_time_health_to_egress`(156, -008)·`B_egress_hard_fence`(170, -013)·`B_stale_epoch_
reject`(177, -002/003)·`B_recovery_barrier_to_egress`(212, -017).

⇒ **FD는 신규 VP-002 키를 0건 저작한다**(실재 2키 재사용·신규 0). **기존 2키(`B_failure_domain_
detect`/`_contain`)의 값 승인**을 Phase-0 Bounds-Approver로 이관(현재 `null`·"APPROVE per concrete
matrix/profile"). 모델은 `FailureDomainAllocationEntry.detection_and_containment`를 **주입 슬롯**
으로만 선언하고 어떤 숫자도 하드코딩하지 않는다.

**미키잉 신설 후보 2항(Phase-0)**: 실재 2키가 detect/contain 총량을 덮으나 ADR §21 OQ6 대비 **전용
키가 아직 없는** 2항 — (a) **blast-radius 상한**(§13 aggregate — rcl `credible_union_capacity`가
직렬화하나 cell-blast 전용 bound 부재)·(b) **safety-cell HALT→global HALT 에스컬레이션 조건**
(§13:318·§14:335) — 만 신설 후보로 플래그(Live-Armer 분리). broker-session exhaustion은
`B_rate_limit_recovery`가 부분 커버(Q4 충분성 open).

---

## 8. 후속 작업 · Phase-0 인간 게이트 이관 항목

### 8.1 후속 구현 작업 (본 계약 위에서)

- `tos/src/tos/failuredomain/` 어휘·레코드 shape·§4 술어·§6 property·import-closure·drift-lock·
  anchor-drift 테스트 저작(설계 #3 EV-L1 하네스가 실행). `tos.canonical` 단일 의존.
- **EV-L1 저작 근거(Gap)**: VER-002-001 §"EV-L1 — Model and Property Verification"(:142)가 EV-L1을
  *model + property 검증*으로 정의하고 추적성 매트릭스(:378–384)가 각 acceptance criterion →
  implementation component → test case → evidence package 대응을 요구한다 — FD의 model+property
  저작이 그 EV-L1 층이다. **anti-phantom 주기(§0.5)**: 리뷰 지목 "VER §382 step 4"는 verbatim
  "failure-domain model/property 의무"를 담지 않으므로(:378–384는 일반 추적성 매트릭스) 근거는
  **§EV-L1-정의(:142)+추적성(:378–384)**으로 명시한다. FD-EV/FD-AC 행 자체는 L3 도달 전까지 미완결.
- **의존 방향**: failuredomain ⟸ `tos.canonical`. 형제는 **주입 token**으로만 참조(import 0).

### 8.2 Phase-0 인간 게이트로 넘기는 항목 (본 계약이 결정하지 않음)

1. **배포 프로파일 + Failure-Domain Allocation Matrix 인스턴스 승인**(ADR §22-1) — §5 shape는 빈
   매트릭스 틀이며 실 allocation·common-mode 분석·`isolation_kind` 분류·residual-risk owner는 인간 승인.
2. **실재 VP-002 키 값 승인 + 미키잉 2항 신설**(§7 — C1 정정): `B_failure_domain_detect`(:611)·
   `B_failure_domain_contain`(:618) **값 승인**(현재 null) + blast-radius 상한·cell-HALT→global-HALT
   에스컬레이션 **전용 키 신설 후보**(ADR §21 OQ6; Bounds-Approver, Live-Armer 분리). `B_rate_limit_
   recovery` 충분성(Q4).
3. **§10.1 무주인 2항 소유자 지명(C3 — fail-open 차단)**: **item1**(per-cell egress-identity 존재·
   유일성)·**item4**(market-data 비주문 credential 분리)은 tos 전역 무주인(negative-grep §0.5) ⇒ FD
   `SafetyCellScope` 좌표 후보(item1) / 배포 프로파일(item4)로 Phase-0 지명. 무주인을 형제 소유로
   기록하면 아무도 저작하지 않는 fail-open(§0.4e).
4. **§9:238–242 identity inventory 5종 + §13:311–318 cell 6-field + §14:335 에스컬레이션 지명**
   (Gap·M8c): egress 4-field로 커버 불가·형제 미소유 ⇒ **배포 프로파일 소관**으로 Phase-0 지명
   (수치/조건은 미승인 VP·§0.4e-c).
5. **general isolation-claim ↔ recovery isolation(sbr) 좌표 거버넌스**(§3.5-1·§9.4-1): FD
   `IsolationClaim`(general 5-field)·sbr `IsolationFacts.all_proven()`(recovery 8-axis)의 **참조-token
   구조(Q2)** 확정 — 상류 FAILURE-DOMAIN-ALLOCATION-MATRIX 템플릿 승격 검토 포함.
6. **environment class INSTANCE 이연(M7 — §9.4-2 해소)**: live/non-live **축은 ioc `LIVE_NONLIVE`·
   brokercap `CLASS_D_NON_LIVE` 소유**·닫힌 값 enum만 미소유 ⇒ **ioc §28 q3 선례대로 Phase-0
   INSTANCE 이연**(FD 신설 불필요).
7. **패키지 명 확정**(§0.4c·§9.3-1): `tos.failuredomain`(권고) vs `tos.fd`(terse) — non-load-bearing.
8. **Independent-Safety-Reviewer 지정** 및 §6 EV-L1 evidence 수용 서명(저자/통합자 배제 —
   IMPLEMENTATION-PLAN §3). ADR §22 게이트 조건 2–10은 전부 형제 evidence·배포 프로파일·독립
   리뷰로만 충족(authorship 불충분 — §22 line 513).

---

## 9. 개정 로그 + 비준 체크리스트 + 판단 지점

### 9.1 개정 로그

- 2026-07-27: **v1.0 초안 최초 작성.** ADR-002-009 EV-L1 실현 계약. **시리즈 최박 패키지·0건
  완결**. register 실측(FD-EV 12행 전부 하한 `EV-L3`·L1 슬라이스 0 — 사전 지도와 일치, 정정
  없음). 핵심 판정: **FD는 통합·소유권-분할 레이어이며 L1-decidable 내용 대부분이 이미 형제
  소유**(§3.5) — canonical만 import, sibling edge 0, FD 고유 소유분 극소(좌표 어휘 3 enum +
  레코드 shape 2 + 도메인-불가지 술어 3). FD-INV 시리즈 부재(§6.1–6.7 산문) ⇒ INV-실현 표 무저작.
  명제-동일성 함정 4건 봉합(sbr isolation·spg deployment·hard-fence 편재·egress §10.1).
- 2026-07-27: **v1.1 — 독립 비평 리뷰 REJECT(CRITICAL 3·MAJOR 8·MINOR 9·Gap 8) 전건 반영.** 신규
  defect class **`anti-phantom`**(부재 주장도 grep — §0.5). **CRITICAL**: (C1) "FD 전용 VP 키 없음"
  거짓 정정 — `B_failure_domain_detect`:611·`B_failure_domain_contain`:618 실재·VER:204–205 등재;
  신규 저작 0·값 승인 Phase-0(§7·§8.2-2). (C2) "≤3종" 실제 4종 → §4.4 cell-partitioning을 rcl
  `credible_union_capacity`:739 이연·**정확히 3종**·그 자리에 `IsolationKind`(§2.1E) 추가. (C3)
  egress §10.1 "정확 소유" 3/4 불성립 → item별 재귀속(item3=orthostate `SEND_STARTED`+rcl
  `CapabilityClaim`·egress grep 0; item1/item4 무주인⇒§8.2). **MAJOR**: (M1) RFC-002 §24.1 17범주
  하한+supply-chain 4(22종); (M2) `IsolationKind` 신설(RFC §24.1:1911·§7:192); (M3) "전부 형제 소유"
  과대주장→FD-EV-004/011 L1 기여(VER:175); (M4) §4.2 fail-open 재설계(`new_risk_blocked_by_unproven_
  isolation(status)`·5 permissive 인자 제거·음극성); (M5) §4.3 volatile 주입화; (M6) rlp/hag/venue
  행; (M7) environment=ioc `LIVE_NONLIVE`/brokercap `CLASS_D_NON_LIVE` 소유·Phase-0 INSTANCE 이연;
  (M8) 명시적 이연 판정 테스트(§0.4e)+3 비자명 사유. **MINOR/Gap**: §13:322·SAFE-045→051·소절제목=
  함수명·plain closed StrEnum(rlp 선례)·partition owner ADR-002-003·hard-fence 6 signature·drift-
  lock 13종 동기화·run manifest VER §3 baseline·anchor-drift(§6.4)·§4.2:86 7-배경. **Open Q**:
  Q1=plain FrozenModel·Q2=참조-token·Q3=rlp 선례·Q4=`B_rate_limit_recovery` open. 코드 인용 40건
  무결점·카운트 전수 일치는 v1.1 재확인(22 domain·9 behavior·3 status·3 isolation-kind).

### 9.2 비준 체크리스트 (운영자 · 독립 리뷰어 확인 사항)

- [ ] §0.2 NO 목록(FD-EV 0건·런타임 매트릭스·isolation enforce·egress/authority·hard-fence
      메커니즘·신규 VP 키 0[실재 2키 재사용·C1])과 §0.3 firewall(canonical `FrozenModel`만·ordering·
      형제 import 0)·**§0.5 anti-phantom(부재 주장도 grep)**에 동의.
- [ ] §1 조항별 EV-L1 도달성 + **닫는 FD-EV 0건**(register line 101–112 전부 `EV-L3`+) +
      §1.1 FD-AC 12/12 전부 not-Phase-1 대응에 동의.
- [ ] **§3.5 소유권 분할표(노른자)**: authority/rcl/egress/spg/sbr/time/cur/brokercap/orthostate/
      evidence 귀속과 **재저작 금지** 경계, 4건 명제-동일성 seam(sbr isolation·spg deployment·
      hard-fence·egress §10.1)에 동의.
- [ ] §3.4 FD 고유 소유분(좌표 4 enum[`IsolationKind` 포함]·레코드 shape 2·도메인-불가지 술어
      **정확히 3**·C2)이 **형제 미소유분에 한정**됨(`safety_cell`/`failure_domain` 스칼라 좌표는
      형제 소유 실측)에 동의.
- [ ] §4 술어 정확히 3종(`unproven_isolation_is_common_mode`·**`new_risk_blocked_by_unproven_
      isolation`**[M4 음극성·status만·5 permissive 인자 제거]·`decision_sole_sourced_from_volatile`
      [M5 주입])의 ∅ 양방향·truthy 극성·both-ways canary에 동의.
- [ ] §6 하네스(전부 predicate substrate·closes-no-EV 태그)·§6.1 import-closure allowlist·§6.2
      형제 token drift-lock(누락 0)에 동의.
- [ ] §7 **FD 전용 VP 키 2건 실재**(`B_failure_domain_detect`:611/`_contain`:618·C1 정정)·신규
      저작 0·값 승인 Phase-0 + 미키잉 2항(blast/cell-escalation) 신설 후보(ADR §21 OQ6)에 동의.
- [ ] §8.2 Phase-0 8항목(배포 매트릭스·실재 VP 키 값승인+2 신설후보·§10.1 무주인 2·identity
      inventory/cell·isolation 거버넌스·environment INSTANCE·명명·리뷰어)을 별도 게이트로 유지함에 동의.
- [ ] 명명 규약(§0.4d): FD-EV/FD-AC/§6.x/§-clause/SAFE 앵커·**새 INV/AC/EV 시리즈 미창작**·
      INV-실현 표 부재(FD-INV 시리즈 없음)에 동의.

### 9.3 운영자 판단 지점 (요약)

1. **패키지 명**(§0.4c): `tos.failuredomain`(권고·semantic·nontrade/posttrade 동형) vs `tos.fd`
   (terse·FD-EV prefix 직결·단 file-descriptor cryptic). load-bearing 아님.
2. **FD 고유 술어 3종 채택 vs 추가 이연**(§4): 3종조차 §1 core 원칙의 얇은 실현이다 — 운영자가
   "FD는 좌표 어휘·레코드 shape만 저작하고 §4 술어도 형제/런타임 이연"을 택할 수 있다(더 얇게).
   본 계약 권고: 3종은 **어떤 형제로도 일반화 안 되는 §1 도메인-불가지 원칙**이므로 FD 저작이
   정당(재저작 아님). 그러나 이는 최소 필요분이며 확장 금지.
3. **레코드 shape = plain `FrozenModel`**(§3.1·**Q1 확정**): 매트릭스는 문서-레벨이고 런타임 digest
   소비자가 없어 `IndependentIdArtifact`(digest-bound) 미채택·plain frozen 확정(재검토 시 위조 탐지
   필요하면 승격 가능하나 Phase-1 불요).
4. **§8.4:228 partition 3-boolean FD 저작 여부**(§0.4e-a·§3.5 §8.4): FD-AC-003 3-boolean(broker
   reachable ∧ revocation/capacity currentness 상실)은 형제 미소유(negative-grep)라 FD 저작 후보이나,
   **정확히 3종 유지·과잉 저작 회피**를 위해 Phase-1 미저작·이연 권고. 운영자가 4번째 술어로 채택 가능.

### 9.4 독립 리뷰어 공격 지점 (open questions)

1. **general ↔ recovery isolation 정합(Q2 처분)**(§3.5-1): FD `IsolationClaim.verification_cases`는
   sbr `IsolationFacts.all_proven()`(`records.py:153`) 결과를 **참조 token**으로 담는 구조로
   정합한다(§3.5 판정1·§8.2-5) — general claim이 recovery 8-axis proof를 *참조*하되 재저작하지
   않는다. **잔여 공격**: general 5-field ↔ recovery 8-axis 좌표 대응을 Phase-0 거버넌스가 명시하지
   않으면 drift 가능 — 독립 리뷰어 재확인.
2. **environment-class(M7 해소)**: v1.0 "tos 전역 미소유"는 **부재 미검증**(anti-phantom)이었다 —
   실측 결과 live/non-live **축은 ioc `ConformanceAxis.LIVE_NONLIVE`(:93)·brokercap `CLASS_D_NON_
   LIVE`(:146)/`environment_binding_ok`(:644) 소유**이고 환경 좌표 필드도 다수 패키지 보유. **닫힌
   값 enum만 미소유** ⇒ ioc §28 q3 선례대로 **Phase-0 INSTANCE 이연**(FD 신설 불필요·§8.2-6). 해소.
3. **§4.2 `new_risk_blocked_by_unproven_isolation` 재저작 우려**: FD 음극성 술어가 authority
   `hard_fence_proven`·§18.2 기각과 **겹칠** 위험. 본 계약은 "FD는 status→blocked 구조 판정만·
   authority가 실제 fence proof 소유"로 분리(§3.5-3·hard-fence 6 signature)했으나 독립 리뷰어 재확인.
4. **§4 술어 3종이 과잉 저작인가**(§9.3-2): 과잉 저작이 최대 함정이므로 3종조차 이연 가능한지 적대
   검토 — 특히 `decision_sole_sourced_from_volatile`이 cur `ProofResult.UNKNOWN`⇒non-admit와 명제
   동일이면 cur 귀속이 옳다(§3.5 §8.3 seam이 도메인-불가지 vs 런타임 currentness로 분리했으나 재확인).

**본 계약이 승인하는 것**: `tos/src/tos/failuredomain/` Phase 1(EV-L1) 좌표 어휘(4 enum +
`SafetyCellScope`) + 매트릭스 레코드 shape 2 + 도메인-불가지 술어 **정확히 3** + property/import-
closure/drift-lock/anchor-drift 테스트 **작성 착수**. **FD-EV 0건 완결**(L1-decidable 대부분 형제
소유·FD-EV-004/011만 L1 기여·EV-L3+ 이연); §8.2 Phase-0 8항목·독립 리뷰어 지정·배포 매트릭스 승인·
실재 VP 키(`B_failure_domain_detect`/`_contain`) 값 승인은 별도 게이트. ADR-002-009는 **Proposed**
유지(§22 10 조건 미충족·authorship 불충분).
