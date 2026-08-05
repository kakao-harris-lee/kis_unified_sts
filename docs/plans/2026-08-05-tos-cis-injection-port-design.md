# 설계 문서 #38 — Context Integrity Service 산출물 주입 포트 확정 계약 (D-E2 `tos.marketfeed`, 이연 ②(a) closure, provisional·닫는 EV 0건) (2026-08-05, v1.2)

> **v1.2 개정(2026-08-06·비준 전 이월지시 등재)**: 델타 재검증 **ACCEPT-WITH-MINOR(MAJOR 0·MINOR
> 3·NIT 3)** — v1.1의 실측 반박 3건(value.py :42-45/:38-41·records.py :165) 전부 확정(비평자가 자기
> 정정값 철회 — sed 렌더 수동 계수의 2행 전위 오프셋이 원인). 비준 전 소액 반영: **§12에 구현자
> 이월 지시 3건 등재**(①P3 whitespace 정규화·②P1.3 token-wise 매칭·③P1.4 `get_type_hints`)·
> **Open Q 2건 확정**(④§4-P3 대상에 `SnapshotStore`/`ValueCandidateSource` docstring 포함·§5.2 착지
> 후 기준·⑤§4.2 parity=구조-3형태 고정)·**NIT 3건**(P3 in-scope 예시·N2 "이 계층 입력만으로는"
> 한정·마침표 분할의 `.py:` 보호). **착지 정밀도만·설계 판정 불변.** §15 처분표 1행 추가.

> **v1.1 개정(2026-08-06)**: 독립 적대적 비평 REVISE(MAJOR 4·MINOR 10) 전건 반영. **MAJOR-1**
> §11-1(ii)의 전칭 주장("셋 다 오늘 단언되지 않는다")을 **정확한 델타**로 재작성 — fake-CIS
> 구동·exclusivity 거동·G1-G4·N1은 이미 committed(`_slice_fixtures.py:335-408`
> `BandBarBook`·`test_slice_conformant_path.py:233-257`)이며 진짜 신규는 ①생성자 required-주입
> inspect 잠금(marketfeed 테스트 inspect 사용 **0건** 실측)·②게이트-레벨 단언의 포트 경계 승격·
> ③Protocol 자체 잠금 셋뿐. **MAJOR-2** D-E4 동형 Protocol 잠금(`test_brokeradapter_transport.py:69-96`)
> 결손을 §4에 신설(§4-P1) — `session_token=`을 `SnapshotStore.__call__`에 추가해도 K3/K13/K4가
> 안 터지는 실측 반증을 봉인. **MAJOR-3** "K1 GREEN=(b) 밀수 0 증거"의 무감도 정정 — (b) 미밀수
> 증거를 **K7·K8·K15**(`test_marketfeed_namespace_and_env.py:192-200` — census 누락분·신규 등재)로
> 교체, K1 GREEN은 발명금지 (f) 준수 증거로 축소. **MAJOR-4** over-claim seal 산출물 신설(§4-P3)
> — 존재-검사 + **부재 방향 co-occurrence 규칙**(과잉거부 방지 분할 포함). MINOR 10·갭 3건 전건
> 반영(§15 처분표). **오케스트레이터 승인 등재**: 서베이 :409 "확장" 대비 "정식화만" 스코프 축소
> 승인(§0.6).

> **비준 대상 배너.** 본 문서는 **저작(authoring) 산출물**이다. 파이프라인: 저작 → 1차 심사 →
> 독립 적대적 비평 → **개정(v1.1·본 산출)** → (운영자 위임 자동 비준·ADR-002 Part-2/3 연장 지시) →
> 구현 → 적대적 코드 리뷰. 본 산출은 **provisional**이며 **닫는 EV/AC 0건**이다. acceptance는 비준
> 설계(#31~#35)의 후속 게이트와 동일 소관(P0-1 bounds·P0-3 독립 리뷰어·독립 서명)이다.
>
> **성격: 이연 closure 계약 (재분해된 하위 조각 (a)).** 본 계약은 신규 패키지·신규 런타임 타입·
> 신규 src 심볼을 만들지 않는다. 수직 슬라이스 #1 완결 시점에 정직 이연으로 기록된 **② D-E2
> Context Integrity Service**(#32 §0.2-4·§2.3 trust seam·#35 §10-4)를, 스코핑 서베이
> (`docs/plans/2026-08-05-tos-deferral-closure-scoping-survey.md` §E 3편)가 실측 판정한 대로
> **(a) 주입 포트 확정** 과 **(b) env-주입 재검증**으로 재분해한 뒤 **(a)만** 착수한다. (b)는 K7
> 시그니처 잠금 정합 선행 판정이 필요한 정직 이연으로 잔존한다(§0.3·§10-1).
>
> **저작 provenance(anti-phantom).** 본 문서 file:line 인용 중 다음은 **2026-08-05~06 본 세션 직접
> read 실측**이다: `tos/src/tos/marketfeed/*`(6모듈)·`tos/tests/marketfeed/*`(package·resolver·
> import_closure·distinctness·namespace_and_env·lineage·fixtures)·`tos/tests/slice/_slice_fixtures.py`·
> `tos/tests/slice/test_slice_conformant_path.py`·`tos/tests/brokeradapter/test_brokeradapter_transport.py`·
> `tools/tos_firewall_check.py`·`tos/tests/dsl/test_dsl_context_value.py`·설계 #35 전문·#34 §0/§5/§8·
> #32 §0.2/§1.1/§2.3/§9/§12.5·설계 #2 §0.2. 그 외 인접 설계(#31/#33)·engine 잠금 테스트 일부는
> **서베이(binding 실측 입력)에서 상속** — 구현 시점 REGREP 게이트(§12)가 전건 재실측을 의무화한다.

---

## 0. 전제·규율

### 0.1 착수-불가 판정 (구속·원문 인용) — "CIS 런타임 구현"이라는 형태로는 열 수 없다

서베이(§E 3편, `2026-08-05-tos-deferral-closure-scoping-survey.md:404-414`)의 실측 판정을 계승한다:
**실 Context Integrity Service 런타임(관측 수집·조립·발행)은 현 방화벽 하에서 tos/ 안에도 밖에도
놓을 수 없다.**

- **안(tos/ 내부) 불가** — CIS 런타임은 네트워크/상태를 요구하나 `tools/tos_firewall_check.py`가 이를
  구조 금지: **TOS-FW-B**(`:19`, `:69-83` — socket/ssl/http/urllib.request/subprocess/ctypes)·
  **TOS-FW-C**(`:20-22`, `:213-251` — os.environ/getenv)·**TOS-FW-D**(`:22-23`, `:252-272` —
  importlib.import_module/exec/eval/compile).
- **밖(tos/ 외부) 불가** — **TOS-FW-R**(`:24-26`, `check_reverse_imports` :306-366):
  > (e) TOS-FW-R  no file OUTSIDE ``tos/`` may ``import tos`` (R-reverse — §3.2):
  >               the operational system must never depend on the unverified kernel.
  ⇒ tos/ 밖 런타임은 `import tos`를 못 하므로 D-E2 타입을 이름으로 참조해 산출물을 만들 수 없다.

**⇒ 유일한 정합 경로 = 주입 Protocol 경계**(서베이 :408) — D-E4 `Transport` 선례(#34 §5.1)와 **구조
동형.** "CIS 구현"이 아니라 **"CIS 산출물의 주입 포트 확정"** 이라는 더 작은 계약이다.

**원문 인용(구속 근거)**:

- **#35 §10-4**(`docs/plans/2026-07-29-tos-slice-gap-closing-design.md:558-559`):
  > 4. **값⟺digest 상류 완전 enforcement** — Context Integrity Service(#32 §0.2-4·§2.3 trust seam).
  >    투영은 생산-시점 검증을 신뢰·재검증 안 함(**over-claim 금지**).
- **#32 §0.2-4**(`docs/plans/2026-07-29-tos-marketfeed-design.md:125-126`):
  > 4. **실 Context Integrity Service 런타임 미구현.** 관측 수집·조립·snapshot 발행의 런타임 경로는
  >    비-scope(설계 #2 §0.2). D-E2는 그 산출물(admitted snapshot)을 **소비·해소(resolve)**하는
  >    계약과 값 표면만.
- **설계 #2 §0.2**(`docs/plans/2026-07-20-tos-decision-context-capsule-snapshot-design.md:74-77`):
  > - **런타임 Context Integrity Service를 구현하지 않는다.** … Phase 1은 그 서비스가 산출할
  >   **아티팩트의 순수 데이터 모델**과 그 불변식만 저작한다. 관측 수집·조립·발행의 런타임 경로는
  >   비-scope다.
- **D-E4 §5.1 선례**(`2026-07-29-tos-egressgw-brokeradapter-design.md:558-566`): Transport Protocol만
  tos/ 안에 정의·실 구현은 tos/ 밖 주입. #38은 그 **입력 방향(ingress)** 동형이며 둘 다 **닫는 EV 0.**

### 0.2 본 계약의 범위·비범위

- **범위**: (1) 어느 주입 표면이 CIS-산출물 포트인가 실측 판정(§2)·(2) 포트의 계약적 의무(보장/
  비-보장) 명문화(§3)·(3) fake-CIS 구동 계약 테스트를 **committed 슬라이스 표면에 대한 additive
  델타로** 설계(§4)·(4) K2-safe·over-claim-safe docstring 개정(§5)·(5) canary 전수 census + 신규
  canary 명세(§6).
- **비범위(명시 이연·§10)**: ②(b) env-주입 재검증·실 CIS 런타임·capsule 모델 변경·
  `TimeCoordinateProjection`(시간 권위·§2.3)·estimator/window·다심볼(#37)·정식 EV-L2 PASS.
- **커널·계층 잠식 금지**: capsule 모델 무변경·발행 게이트 4-게이트 로직 무변경·engine→marketfeed
  edge 0.

### 0.3 ②(b)와의 경계선 + (b)-미밀수 증거의 정정 (MAJOR-3·구속)

**②(b) env-주입 재검증은 이번 아크에서 착수하지 않는다**(서베이 판정 1·`:457-458`). 근거:
`build_environment`/`evaluate_resolved`가 발행된 `ContextValueView`의 값⟺digest를 재검증하는 계약
(#32 §2.3 :314-320·§9-6 :660)인데, 재검증에 필요한 `scheme`/검증자를 진입점에 실으면 **K7 정확-집합
잠금**(evaluate 5-param·evaluate_resolved 정확 +1·ambient 배제·`test_dsl_context_value.py:316-368`)을
깨거나 ambient smuggle이 된다. ⇒ (b)는 **K7 정합 선행 판정이 필요한 별개 이연**으로 잔존(§10-1).

**⚠ v1.1 정정(MAJOR-3 — K1의 (b)-무감도)**: v1.0은 "K1 GREEN = (b) 밀수 0 증거"라 주장했으나 이는
**거짓**이다. K1(`test_marketfeed_distinctness.py:236-247`)은 발행 게이트에 두 관측을 직접 먹여
붕괴를 보일 뿐 **env-주입 경로를 건드리지 않으므로**, (b)를 전량 밀수해도 K1은 GREEN이다. 두
관심사를 정확히 분리한다(§3.4 자기 표와도 정합):

- **K1 GREEN → 발명금지 (f) 준수 증거로만**: 게이트에 as-of 재사용 거부를 **넣지 않았음**(=N1
  as-of를 상류 CIS 소관으로 유지·§0.4 (f)).
- **(b) 미밀수 증거 → K7·K8·K15**: dsl 진입점 시그니처 무변경(K7·K8) + **value-free env가
  byte-identical**(K15 = `test_marketfeed_namespace_and_env.py:192-200` —
  `build_environment(capsule, config) == legacy` — env-주입 경로에 재검증이 착지하면 거동/시그니처
  중 하나가 반드시 변함). 이 셋이 (b) 경로를 실측으로 봉인.
- **MAJOR-2 Protocol 잠금은 (b) 밀수 아님**: §4-P1의 Protocol 잠금은 **소비측 marketfeed 표면**
  (`SnapshotStore.__call__`)만 잠그고 **dsl 진입점(build_environment/evaluate_resolved) 무저촉·발행
  게이트 무변경**이다 — env-주입 재검증과 무관.

### 0.4 발명 금지 (서베이 §E 3편 (a)-(f) 전건 전사·구속)

`2026-08-05-tos-deferral-closure-scoping-survey.md:416-420` 원문 전사. 본 계약·구현은 아래를 **하지
않는다**:

- **(a)** capsule 모델 필드 추가/변경 — #32 §0.2-1(`marketfeed-design.md:117-120`) "어떤 capsule
  모델 필드도 추가/변경/제거하지 않는다 … 불가피 시 **설계 말고 미결 보고**".
- **(b)** `evaluate`/`evaluate_resolved` 시그니처 확대 — K7.
- **(c)** marketfeed 레코드에 transport/credential 이름 필드 — K3 seal이 **생성 시점**에 터짐
  (`_base.py:108-127`·`records.py:162-165` `seal_fetch_surface(...)` 호출).
- **(d)** 엔진→marketfeed edge — K6 양방향 canary.
- **(e)** 발행 게이트가 **"완전 강제"** 를 주장하는 문구로 docstring 개정 — §10-4 over-claim 금지
  (#32 §2.3 :319-320 "over-claim 금지").
- **(f)** as-of 재사용 거부를 게이트에 넣으며 K1을 조용히 갱신 — FLIP이면 FLIP으로 등재. (본 계약은
  넣지 않으므로 K1 GREEN·§0.3.)

### 0.5 anti-phantom 규율 (부재·존재 양방향 grep·MINOR-1 정정)

- **부재 주장(정정된 형태)**:
  1. `grep -rn "Context Integrity Service" tos/src/` → **1행**(`marketfeed/__init__.py:55`) — tos/에
     CIS 런타임 구현 부재. 포트 확정 후에도 그 1행은 **참으로 유지**(§5·K2).
  2. **⚠ v1.1 정정(MINOR-1)**: v1.0의 "`grep 'socket|urllib|os.environ|import_module'
     tos/src/tos/marketfeed/*.py` → 0"은 **거짓**이다 — 실측 **9 hits**(전부 `FETCH_SURFACE_TOKENS`
     리터럴·docstring의 단어 "socket"/"websocket"이며 **import 0건**). network/escape 부재는 raw
     substring이 아니라 **K4 AST canary**(`test_marketfeed_import_closure.py:555-562`, planted-escape
     대조 canary 포함)로 봉인된다 — 그것을 근거로 인용한다.
  3. `MarketFeedContextResolver.__init__`의 `snapshot_store`/`candidate_source`에 default **부재**
     (resolver.py:137-138) → "CIS-산출물 소스 없이 resolver 생성 불가"의 구조 사실.
- **존재 확인**: `SnapshotStore`(resolver.py:56)·`ValueCandidateSource`(resolver.py:75)·
  `TimeCoordinateProjection`(resolver.py:91)·`MarketFeedContextResolver`(resolver.py:123) 전부
  `tos.marketfeed.__all__` 노출(`__init__.py:150-155`). committed fake-CIS 구동체 `BandBarBook`
  (`_slice_fixtures.py:335-408`)·`build_resolver`(`:411-422`) 실존.
- **committed canary 전수-grep(#35 MAJOR-1 교훈)**: 서베이 K1-K12 시작점에 본 세션 직접 재-grep으로
  **K13(authority-symbol 스윕)·K14(phantom-`__all__`)·K15(value-free env byte-identical — MAJOR-3)**
  3건을 추가 적발. 시작점이지 완결 아님·REGREP(§12)이 전건 재실측 의무화.

### 0.6 오케스트레이터 승인 등재 (서베이 문언 대비 스코프 축소·2026-08-06)

서베이 :409는 "(a) = SnapshotStore/ValueCandidateSource **확장** + 포트 선언"으로 서술했으나, 본
계약은 **"확장 0·정식화만"** 으로 축소한다. 근거: umbrella Protocol/생성자 변경은 committed 생성
지점 **3곳**(`test_marketfeed_resolver.py:54`·`_slice_fixtures.py:418`·`test_slice_conformant_path.py:245`)
을 파괴한다(§2.2 (A)). **오케스트레이터가 이 축소를 2026-08-06 승인**한다(비평 Open Question 판정) —
본 §0.6에 등재.

---

## 1. 이연 ② → 뿌리 지도 (§별 원문·실측)

| 뿌리(설계 §·원문) | 실측 코드 증거(2026-08-06) |
|---|---|
| **#32 §0.2-4**(`:125-126`) "D-E2는 그 산출물(admitted snapshot)을 소비·해소하는 계약과 값 표면만" | `MarketFeedContextResolver.resolve`(resolver.py:158-198) — 주입 store/source 소비 |
| **#32 §1.1-3**(`:210-212`) "슬라이스는 admitted snapshot을 소비해 값을 §10-conformant로 노출하는 계약을 실증" | 발행 4-게이트(value.py:11-31) |
| **#32 §2.3 신뢰 seam**(`:314-320`) "env-주입 지점은 값⟺digest를 재검증하지 않고 신뢰 … **over-claim 금지**" | resolver.py:24-26·value.py:35-45·`__init__.py:59-63` 3중 자기-선언 |
| **#32 §9-6**(`:660`) "**env-주입 재검증**(dishonest producer·신뢰 seam) — 상류 정직" | **②(b)** — 본 계약 밖(§0.3·§10-1) |
| **#32 §12.5**(`:766`) "\| snapshot 조립·발행 런타임 \| — \| Context Integrity Service \|" | CIS 런타임 = 상류·D-E2 = 소비 계약 |
| **#35 §10-4**(`:558-559`) "재검증 안 함(over-claim 금지)" | 포트 **비-보장** 원문(§3.3) |
| **K1**(`test_marketfeed_distinctness.py:236-247`) "Complete enforcement is upstream (the CIS)" | 코퍼스 유일 "the Context Integrity Service" 명명 executable |

**핵심 관찰**: 코드는 이미 "admitted snapshot을 소비한다"를 **하고**, fake-CIS로 그것을 **구동하는
테스트도 committed**이다(`BandBarBook`). 없는 것은 그 소비 경계가 **명명된 포트인가** + 그 포트의
**Protocol 표면과 생성자 형상이 잠겼는가** — 이 둘뿐이다(§2·§11-1 정확한 델타).

---

## 2. 판정: 포트는 이미 씨앗으로 출하됨 — 정식화(formalization)만·신규 타입 0

### 2.1 판정: `SnapshotStore` + `ValueCandidateSource` = admitted-snapshot 주입 포트(씨앗·확정)

- **`SnapshotStore`**(resolver.py:56-71): `(*, snapshot_id, canonical_digest) -> CriticalInputSnapshot |
  None`. `SnapshotRef`(capsule.py:41)로 content-addressed된 **CIS-발행 snapshot body** 조회. `None`은
  1급 답·부재를 다른 body로 대체 금지(:64). ⇒ CIS 산출물이 들어오는 seam.
- **`ValueCandidateSource`**(resolver.py:75-87): `(snapshot, *, instrument_key) -> Sequence[AdmittedValue]`.
  후보 값(claim)만 공급·발행 게이트가 검증하므로 **부정직 소스의 최대치는 rejection record**(:80).
- **판정**: 포트 = 이 **두 required 주입 표면의 쌍**(resolver.py:137-138·default 부재). 이미 씨앗이며
  아래 정식화만 필요.
- **committed 구동체(선행 기출하·MAJOR-1 증거)**: `BandBarBook`(`_slice_fixtures.py:335-408`)이 이
  두 역할을 자기선언 수행(`snapshot_store` :383-399는 stale-body 재검사까지 구현)하고 `build_resolver`
  (`:411-422`)가 **실 resolver**를 이 두 주입으로 생성한다. 즉 fake-CIS 구동은 이미 committed다.

### 2.2 판정: 신규 Protocol/타입 0·생성자 무변경 — "확장" 아닌 "정식화"

**검토·기각**:

- **(A) umbrella Protocol 신설** — **기각(하위호환 파괴).** 두 표면을 단일 `__call__`로 묶으면 생성자
  시그니처가 바뀌어 committed 생성 지점 **3곳**(`test_marketfeed_resolver.py:54`
  `MarketFeedContextResolver(snapshot_store=…, candidate_source=…)`·`_slice_fixtures.py:418`
  `build_resolver`·`test_slice_conformant_path.py:245` `starving` resolver)을 파괴한다. methodless
  마커 Protocol은 phantom. ⇒ 신규 타입 발명 부정직.
- **(B) 두 Protocol에 검증 메서드 추가** — **기각.** 재검증은 (b) 소관·K7 충돌(§0.3).
- **(C) 정식화만**(신규 타입 0·생성자 무변경) — **채택.** 실물 3가지: ①생성자 required-주입 inspect
  잠금(§4-P2·marketfeed 테스트 inspect **0건** 실측 → 유일 신규 구조 잠금)·②Protocol 자체 잠금
  (§4-P1·D-E4 동형)·③기존 게이트-레벨 단언의 포트 경계(resolver 경유) 승격(§4-P4).

**⇒ 최종: 씨앗 확정·정식화만·신규 src `.py` 0·신규 런타임 타입 0·신규 src 심볼 0·생성자 무변경.**
src 변경 = `resolver.py`·`__init__.py` **docstring 개정만**. 테스트 = 신규 파일
`tos/tests/marketfeed/test_marketfeed_cis_port.py` 1건(`test_marketfeed_package.py` 무편집). D-E4가
**신규** 패키지에 **신규** `Transport`를 만든 것과 달리, 여기 seam은 **이미 출하**돼 있어 동형성은
"신규 Protocol 창설"이 아니라 **"주입 Protocol 경계 + Protocol 잠금 + 생성자 잠금 + fake 구동"** 이라는
구조 수준에 있다(§11-1).

### 2.3 `TimeCoordinateProjection`은 포트에서 제외 (정직 경계·침묵 드롭 금지)

세 번째 주입 표면 `TimeCoordinateProjection`(resolver.py:91-101)은 **CIS-산출물 포트가 아니다.**
docstring(:92-97) "a 'now' reading, if the deployment has one" — 배포의 **시간 권위**(→engine
`TimeAdmissionInputs`)이지 admitted snapshot이 아니다. as-of **앵커 값**은 admitted values에서 오나
(resolver.py:186) 시간 좌표 **투영**은 별개 권위(trustworthy-time 소관). committed 증거:
`build_resolver`(`_slice_fixtures.py:414-416`)가 `time_projection`을 의도적으로 생략하고 D-E3의
`BarTimeProjection`이 converter에서 적용(converter.py:119-127). ⇒ 흡수 시 scope creep. 명시 제외
(이연도 (b)도 아닌 **타 설계 소관**)로 기록.

---

## 3. 주입 포트 계약 — 정체성·의무 표면(보장/비-보장)

### 3.1 포트 정체성 (명명·구속)

**admitted-snapshot 주입 포트** ≔ `MarketFeedContextResolver`에 주입되는 두 표면의 쌍: `SnapshotStore`
(CIS-발행 snapshot body) + `ValueCandidateSource`(attributed candidate values). 상류는 "주입 경계
너머의 무엇이든"(task) — D-E3 히스토리·D-E4 라이브·§4 fake-CIS·committed `BandBarBook`. resolver는
셋을 **구별하지 못한다**(resolver.py:16-18 parity claim). 이 소스-무관 parity가 포트가 특정 상류를
전제하지 않는 이유다.

### 3.2 포트가 **보장하는 것** (구조적 admission — 소비 시점)

발행 게이트 `publish_context_value_view`(value.py:562) 4-게이트로 **소비 시점** 집행:

1. **binding integrity** — body id/digest ↔ `SnapshotRef` 정확 일치·불일치는 `BINDING_MISMATCH`
   (value.py:594·ADR-002-018 §15:386).
2. **값 ⟺ covered digest** — 후보 preimage가 observation `payload_digest`로 digest(value.py:508-517·
   `DIGEST_MISMATCH`).
3. **VALID 게이트** — 미평가 필드 explicit UNKNOWN floor(value.py:223-225).
4. **lineage** — 재현성 + 기록된 look-ahead(value.py:332-334).

**추가 구조 보장(포트 형상)**: **exclusivity** — snapshot body/값은 오직 주입 표면으로만 진입·resolver
자체 생성 0(resolver.py:14)·fallback 0(:24-26)·required 주입(:137-138). ambient fetch는 K4/K3가
봉인. **∅ 양방향** — `SNAPSHOT_UNRESOLVED`/`BINDING_MISMATCH`/`EXPLICIT_EMPTY` 별개 recorded member.

### 3.3 포트가 **보장하지 않는 것** (생산자 정직 — over-claim 금지·구속)

**포트는 상류 CIS의 정직을 보장하지 못한다**(신뢰 seam·#32 §2.3 :319-320). 비-보장 명문화:

- **N1 as-of distinctness 비-보장** — 같은 as-of 두 bar → digest 붕괴·게이트 **탐지 불가**
  (value.py:42-45 "A producer that stamps two different bars with the same as-of collapses it, and
  that is a producer-honesty problem this layer cannot close"). K1이 이 한계를 executable로 단언·
  **완전 강제는 상류 CIS**.
- **N2 fabricated-but-plausible lineage 비-보장** — 그럴듯한 부모 위조는 게이트가 못 잡음
  (value.py:38-41 "a producer that fabricates a plausible-looking parent set is not [caught]. Runtime
  look-ahead enforcement over a real replay is D-E3's"). **구조적으로 반증 불가**(§4.2 N2) — 위조된
  자기정합 lineage는 참 lineage와 byte-무구별이라 판별 테스트가 원리적으로 존재하지 않는다.
- **N3 env-주입 재검증 비-보장** — 값⟺digest는 발행 시점·env-주입 재검증 안 함(resolver.py:24-26).
  **②(b)** 소관(§0.3·§10-1).
- **탐지 vs 강제** — `__init__.py:62` "this layer **detects rather than enforces**". 포트 계약이 이
  문장을 executable seal로 승격(§4-P3).

**over-claim 금지(구속)**: 포트 계약·docstring·테스트 어느 것도 "생산자 정직 보장"/"완전 강제"를
주장하지 않는다.

### 3.4 의무 표면 요약표 + (b)/CIS 소유 정합 (MAJOR-3 정합)

| # | 항목 | 포트 | 소유 | (b)-미밀수 증거 매핑 |
|---|---|---|---|---|
| G1 | binding integrity | **보장** | D-E2 게이트 | — |
| G2 | 값⟺covered digest | **보장** | D-E2 게이트 | — |
| G3 | VALID 게이트 | **보장** | D-E2 게이트 | — |
| G4 | lineage 재현성·기록된 look-ahead | **보장** | D-E2 게이트 | — |
| G5 | exclusivity(주입 유일 통로·fallback 0) | **보장**(구조) | 본 계약(§4-P2/P5) | — |
| G6 | ∅ 양방향 | **보장** | D-E2 vocabulary | — |
| N1 | as-of distinctness | **비-보장** | **상류 CIS** | K1 GREEN = 발명금지 (f) 준수(≠(b)) |
| N2 | fabricated-plausible lineage | **비-보장** | 상류 CIS / D-E3 replay | (반증 불가·§4.2) |
| N3 | env-주입 재검증 | **비-보장** | **②(b)** | **K7·K8·K15 GREEN** |

**정합 주석**: N1(상류 CIS)과 N3((b))는 **다른 소유**다. 따라서 K1(N1 증거)을 (b)(N3) 미밀수 증거로
쓰면 모순이었다(v1.0 결함·MAJOR-3). v1.1은 K1을 N1/발명금지(f)에만, (b) 미밀수를 N3의 K7/K8/K15에만
결속한다.

---

## 4. fake-CIS 구동 계약 테스트 — committed 표면에 대한 additive 델타 (MAJOR-1 재작성)

**전제(MAJOR-1·구속): 다수가 이미 committed다.** fake-CIS 구동·exclusivity 거동·G1-G4·N1은 슬라이스
표면에 기출하:

| 이미 committed | 위치 | 본 계약과의 관계 |
|---|---|---|
| fake CIS가 실 resolver 구동 | `_slice_fixtures.py:335-422`(`BandBarBook`·`build_resolver`) | **선행 증거로 인용**·재저작 0 |
| exclusivity 거동(store만 바꿔 SNAPSHOT_UNRESOLVED vs healthy) | `test_slice_conformant_path.py:233-257`("so the difference is the store.") | **선행 증거로 인용** |
| G1(binding) 거부 | `test_marketfeed_resolver.py:93-102`(K11) | 포트 framing 재사용 |
| G2/G3/G4 거부·over-realization | `test_marketfeed_resolver.py:254-269`·`test_marketfeed_lineage.py`·`test_marketfeed_valid_gate.py` | 선행 |
| N1 as-of 붕괴 | `test_marketfeed_distinctness.py:236-247`(K1) | 선행·포트 비-보장 명명 |

**⇒ 신규 테스트는 위를 재저작하지 않고, 오직 아래 델타(P1-P5)만 additive로 신설한다.** 배치: 신규
파일 `tos/tests/marketfeed/test_marketfeed_cis_port.py`(test 파일엔 submodule-drift canary 없음 —
import_closure는 `_MARKETFEED_SRC` glob으로 src만 스캔·§6-K5 실측).

### 4.1 신규 델타 (P1-P5·구현 완료 판정)

- **P1 — Protocol 자체 잠금 (MAJOR-2·D-E4 `test_brokeradapter_transport.py:69-96` 동형·핵심 신규)**.
  실측 반증: `SnapshotStore.__call__`에 `session_token=`을 추가해도 K3(pydantic `model_fields`)·
  K13(고정 8이름 vars 스윕)·K4(AST import) **무엇도 안 터진다** — Protocol 파라미터는 그 어느
  canary의 대상이 아니다. 따라서 신설:
  1. **call-only 단일 표면**: `[n for n in vars(SnapshotStore) if not n.startswith("_")] == []` 및
     `ValueCandidateSource` 동일 — 이름 붙은 side 메서드(`fetch`/`subscribe`) smuggle 차단(D-E4
     `vars(Transport)==["send_once"]` 동형의 call-only 형태).
  2. **정확-파라미터 집합**: `set(inspect.signature(SnapshotStore.__call__).parameters) ==
     {"self","snapshot_id","canonical_digest"}`; `ValueCandidateSource.__call__ ==
     {"self","snapshot","instrument_key"}`(resolver.py:67-71·:83-87 실측).
  3. **ambient/transport 이름 배제**(K7 동형·`_base.py` token-wise·구현자 이월 ②): 두 `__call__`
     파라미터명을 `split("_")`+whole-name(과잉거부 방지)으로 토큰화해 `fetch/fetcher/session/token/
     credential/url/socket/host/port/subscribe/clock/now` 부재 — **exact-name이면 헤드라인 예시
     `session_token`(=`{session, token}`)을 놓치므로 token-wise 필수**(주 봉인은 P1.2·이는 광고대로의
     중복 방어).
  4. **CIS 주입 표면 폐포 = 정확히 2**(구현자 이월 ③): `resolver.py:33`의 `from __future__ import
     annotations`로 어노테이션이 **문자열**이라 identity 비교 불가 — **`typing.get_type_hints(
     MarketFeedContextResolver.__init__)`로 해소**한 뒤 타입이 `SnapshotStore`/`ValueCandidateSource`인
     주입이 **정확히 2개**·`TimeCoordinateProjection`은 별개 optional(§2.3)임을 단언.
- **P2 — 생성자 required-주입 잠금 (유일 신규 구조 잠금·§2.2 (C)①)**: `inspect.signature(
  MarketFeedContextResolver.__init__)`에서 `snapshot_store`·`candidate_source`가 **default 없는
  keyword-only**(default is `Parameter.empty`), `time_projection`만 default None. ⇒ CIS-산출물 소스
  없이 resolver 생성 불가.
- **P3 — over-claim seal (MAJOR-4·존재+부재 양방향)**. 대상 = marketfeed **6 submodule 전부의**
  module/공개 class/func `__doc__`(test docstring 제외) — **`SnapshotStore`/`ValueCandidateSource`
  docstring 포함**(Open Q ④: §5.2가 편집하는 그 문자열도 over-claim 금지 대상). **P3 pin은 §5.2
  docstring 착지 후 상태 기준**(순서: §5.2 편집 → P3 단언). **⚠ 전 substring 단언은
  `" ".join(doc.split())` 화이트스페이스 정규화 후 검사**(구현자 이월 ①·§12) — `__init__.py:62-63`의
  "none of\nthem" 개행 걸침으로 raw 검사가 착지 시 FAIL(선례 `test_egressgw_package.py:43`).
  1. **존재(positive pin)**: 정규화 후 `"detects rather than enforces"`(`__init__.py:62`)·
     `"cannot close"`(value.py:44)·`"none of them is claimed as closed"`(`__init__.py:62-63` 걸침)
     존재 단언(K2 확장).
  2. **부재(negative·co-occurrence·과잉거부 방지)**: over-claim stem `{"complete enforcement",
     "fully enforc","completely enforc","re-verif","guarantees producer","guarantee producer
     honesty"}`가 등장하면 **같은 문장 안에** upstream/부정 anchor `{"upstream","cannot","does not",
     "not …"}` 공기 필수. **문장 분할은 `.py:`·dotted 토큰 보호**(마침표 raw 분할 금지 — `". "`
     공백 동반 또는 `\.\w` 비분할·구현자 이월 NIT-3). 정직 문구("complete enforcement is upstream")
     PASS·"this layer fully enforces distinctness" FAIL.
  3. **과잉거부 guard(#26 WDR·`_base.py` 규율)**: 이식 test(NIT-1 in-scope 예시) — (i) over-claim
     stem+anchor 공기 in-scope 형 PASS 예시 = `"complete enforcement is upstream (the CIS)"`(정직)
     PASS·(ii) planted anchor-없는 `"this layer fully enforces distinctness"` FAIL. **co-occurrence
     규칙 자체**를 실증(단순 substring 아님).
- **P4 — 게이트-레벨 단언의 포트 경계 승격**: 기존 게이트-직접 단언(G1-G4)을 **resolver 경유**(포트
  경계)로 한 번 더 실증 — fake-CIS store/source가 (a)mismatched body→`BINDING_MISMATCH`·(b)digest
  불일치 후보→`DIGEST_MISMATCH`·(c)look-ahead lineage→`LINEAGE_LOOKAHEAD`·(d)미평가 필드→
  `FIELD_STATE_NOT_VALID`. "부정직 소스의 최대치는 rejection record"(resolver.py:80) 실증. (게이트
  단독 단언은 기출하이나 **포트 경계 승격은 신규**·MAJOR-1 델타 ②.)
- **P5 — exclusivity 뮤테이션(확장·gap 처리)**: (a) 주입 표면을 `__init__` 밖(모듈 전역/클래스 속성)
  으로 옮기는 뮤테이션 → P2 잠금 FAIL·(b) `snapshot_store`를 keyword-only→positional 전환 → P2 FAIL·
  (c) `snapshot_store`에 default 부여(ambient no-op 소스) → P2 FAIL. 셋 다 KILLED로 포트 우회 차단.

### 4.2 비-보장의 정직 실증 (over-claim 금지 방향·MINOR-6/7 반영)

- **N1(as-of)**: fake CIS가 두 bar에 같은 as-of → 둘 다 admit·digest 붕괴를 **"잡힌다"고 단언하지
  않는다**. 붕괴를 단언하고 상류 CIS 소관 명명(K1 동형). as-of 거부 삽입은 (b) 스코프임을 주석 표기.
- **N2(fabricated lineage)**: **테스트로 신설하지 않는다**(MINOR-6). 위조 자기정합 lineage는 참
  lineage(`test_marketfeed_lineage.py:102-107` `test_a_reproducible_derived_value_publishes`)와
  byte-무구별이라 **이 계층의 입력만으로는**(NIT-2 한정) 판별자가 없다 — 실 replay 대조는 D-E3
  소관(value.py:38-41 "Runtime look-ahead enforcement over a real replay is D-E3's"). 이 **입력-한정
  반증 불가성** 자체가 N2 비-보장의 정직한 근거다. P3 over-claim seal이 "포트가 이를 강제한다"는
  문구를 금지함으로써 N2를 문서 차원에서 봉인.
- **source parity(MINOR-7·비-동어반복·⑤ 착지 형태 고정=구조-3형태)**: 동일 body를 **구조적으로
  다른 3형태**로 주입 — (i) 평범한 함수, (ii) 인스턴스 bound method(`BandBarBook.snapshot_store`
  형태), (iii) `functools.partial`/callable 클래스 인스턴스 — 해도 resolver view digest **동일**.
  **KILL 뮤테이션 명기**: store가 자기 종류를 peek해(`type(self)` 분기) 다르게 행동하면 parity 단언
  FAIL → resolver가 상류 종류를 구별하지 않음을 반증 가능하게 실증. **(구현자 재량 제거: 슬라이스
  인용 대체 옵션 철회 — 구조-3형태로 고정.)**

**property/mutation 규율**: P1-P5·P4 rejection 뒤집기 → KILLED. fake CIS는 fetch/clock/rng 0
(fixtures 규율·`_marketfeed_fixtures.py:2-9` 상속).

---

## 5. docstring 개정 범위 (K2-safe·over-claim-safe·정직 승격)

### 5.1 `tos/src/tos/marketfeed/__init__.py` (:52-63)

- **:52-57 (c) 문장**: "…only **consumes** its output" 뒤에 **포트 명명 1구 additive** — "…only
  consumes its output — **through the admitted-snapshot injection port** (`SnapshotStore` +
  `ValueCandidateSource`), the D-E2 consumption boundary of that upstream output (design #38)."
  **"not the Context Integrity Service runtime"·"only consumes"·"out of scope" 무변경.**
- **"closes no EV"·"Provisional" 무변경** → **K2**(`test_marketfeed_package.py:232-236`은 이 두
  substring만 단언·실측) GREEN.
- **:59-63 honest-limit 무변경**(특히 `:62` "detects rather than enforces"·`:63` "none … claimed as
  closed") → P3 positive pin의 대상.

### 5.2 `tos/src/tos/marketfeed/resolver.py` (:14-31, :55-101)

- **:14-21 블록**에 포트 명명 additive(두 injected 표면 = "the admitted-snapshot injection port").
  "cannot tell them apart, which is the parity claim"(:16-18)·"invents nothing"(:14) 무변경.
- **:24-26 trust seam 무변경**((b)·N3 계승).
- `SnapshotStore`(:56-71)·`ValueCandidateSource`(:75-87) docstring에 "one half of the admitted-snapshot
  injection port (design #38)" 1구 additive. **시그니처·`__call__` 형상 무변경**(P1 잠금 대상이므로
  변경 시 P1 FAIL — 자기 봉인).

### 5.3 개정이 승격하는 것 (docstring→canary·내부-정합)

marketfeed 자신의 규율("A docstring promising that is a self-report … instead every marketfeed record
runs its own field names through this check"·`_base.py:11-13`)과 정합하도록, 포트 확정은 **구조/거동
으로** 봉인된다: exclusivity=P2 시그니처 read·Protocol 표면=P1 inspect·의무=P4 fake-CIS 구동·
over-claim=P3 co-occurrence. docstring canary(P3 positive·K2)는 **honesty-scope 선언**에만 국한 —
이는 marketfeed가 **이미** honesty-scope를 docstring text로 canary하는 방식(`test_marketfeed_package.py:232`·K2)과
동일 패턴이다(§11-4).

---

## 6. canary census + 판정

### 6A. committed canary 전수 census (기존·GREEN/FLIP/REGREP)

**본 계약은 신규 src `.py` 0·신규 런타임 타입 0·신규 src 심볼 0·생성자·게이트 로직 무변경 → FLIP·
WIDEN 0.**

| # | canary(file:line) | 잠그는 것 | 본 계약 영향 | 판정 |
|---|---|---|---|---|
| **K1** | `test_marketfeed_distinctness.py:236-247` | as-of 재사용 붕괴(한계·"CIS is upstream") | 게이트 as-of **무변경**·§4.2 동형 | **GREEN**(발명금지 (f) 증거·≠(b)·§0.3) |
| **K2** | `test_marketfeed_package.py:232-236` | docstring `"closes no EV"`·`"Provisional"` | 두 substring 무변경·(c)는 additive | **GREEN** |
| **K3** | `test_marketfeed_package.py:91-100`; `_base.py:108-127` | 레코드 필드 transport/credential 토큰 금지 | 신규 레코드/필드 0 | **GREEN** |
| **K4** | `test_marketfeed_import_closure.py:291-334`·`:555-562`·`:617-624` | closure⊆allowlist·network/clock/rng/escape 부재(AST) | 신규 import 0 | **GREEN** |
| **K5** | `test_marketfeed_import_closure.py:627-641`·`:644-648` | src submodule drift(신규 `.py` 금지) | 신규 src `.py` 0 | **GREEN** |
| **K6** | `test_marketfeed_import_closure.py:374-380`·`:425-448` | engine allowlist=14·engine→marketfeed 무 edge | edge 0 | **GREEN** |
| **K7** | `test_dsl_context_value.py:316-368` | evaluate 5-param·evaluate_resolved +1·ambient 배제 | dsl 진입점 무변경 | **GREEN**((b) 미밀수 증거·§0.3) |
| **K8** | `test_dsl_context_value.py:263-267` | `build_environment.resolved_context` keyword-only | 무변경 | **GREEN**((b) 미밀수) |
| **K9** | `test_dsl_context_value.py:394-443` | 서명 append 뮤테이션 | 무변경 | **GREEN** |
| **K10** | `test_engine_value_view.py:148-158`(서베이 상속) | `DecisionTickPayload.model_fields` | payload 필드 0 | **GREEN** |
| **K11** | `test_marketfeed_resolver.py:93-102` | 다른 body 대체 불가 | §4-P4가 포트 framing 재사용 | **GREEN** |
| **K12** | `tos_firewall_check.py` A/B/C/D/R | tos/ 방화벽(§0.1 근본 제약) | 위반 0 | **GREEN** |
| **K13**† | `test_marketfeed_import_closure.py:651-676` | vars 스윕 8이름(`send_once` 등) 부재 | 신규 심볼 0 | **GREEN** |
| **K14**† | `test_marketfeed_package.py:249-253` | phantom `__all__` 부재 | 신규 `__all__` 0 | **GREEN** |
| **K15**† | `test_marketfeed_namespace_and_env.py:192-200` | **value-free env byte-identical**(build_environment==legacy) | env-주입 경로 무변경 | **GREEN**((b) 미밀수 핵심 증거·MAJOR-3) |

† K13·K14·K15는 서베이 K1-K12 밖 본 세션 재-grep 적발(#35 MAJOR-1 규율). **K15는 MAJOR-3의 (b)
미밀수 실측 증거** — census 누락분을 신규 등재. (모든 file:line은 REGREP 총괄 게이트(§12) 재실측
대상 — 이중 표기 대신 §12로 일원화.)

**추가 GREEN 확인**: `test_the_pure_layer_statically_imports_no_engine`(`test_marketfeed_import_closure.py:468-482`)·
`test_the_adapter_layer_really_holds_the_engine_edge`(`:485-490`)·
`test_the_resolver_claims_no_causal_ordering_coordinate`(`test_marketfeed_resolver.py:272-278`).

### 6B. 본 계약이 **설치하는 신규 canary** (P1-P5·additive·기존 canary 아님)

| id | 신규 canary | 무엇을 새로 봉인하나 | 근거 |
|---|---|---|---|
| **P1** | Protocol call-only·정확 param·ambient 배제·폐포=2 | `SnapshotStore.__call__`에 `session_token=` 추가가 오늘 무저촉 → 봉인(MAJOR-2) | D-E4 `test_brokeradapter_transport.py:69-96` 동형 |
| **P2** | 생성자 required-주입 inspect 잠금 | marketfeed 테스트 inspect **0건** → 유일 신규 구조 잠금 | §2.2 (C)① |
| **P3** | over-claim seal(존재+부재 co-occurrence) | "완전 강제" 삽입을 원리적으로 못 잡던 공백 봉인(MAJOR-4) | `_base.py` token 규율·#26 WDR |
| **P4** | 게이트 단언의 포트 경계 승격 | resolver 경유 G1-G4 | resolver.py:80 |
| **P5** | exclusivity 뮤테이션(위치·positional·default) | 포트 우회 3경로 KILL | §4-P5 |

**FLIP 0·WIDEN 0.** 모든 변경은 docstring additive 또는 신규 테스트 파일 additive다.

---

## 7. 완료 판정 (구현의 "done" 계약)

1. **신규 canary P1-P5 GREEN**(§6B) — 특히 P1 Protocol 잠금·P2 생성자 잠금.
2. **fake-CIS 델타 GREEN**(§4) — committed 슬라이스 표면 재저작 0·additive만.
3. **docstring 개정 착지**(§5) — 포트 명명 additive·"not the CIS runtime"/"closes no EV"/"Provisional"/
   "detects rather than enforces" 무변경.
4. **K1-K15 전건 GREEN**(§6A) — K1 GREEN(발명금지 (f))·**K7·K8·K15 GREEN((b) 미밀수)**.
5. **`docs/plans/INDEX.md` 등재**(MINOR-10) — #38 행 추가.
6. **`tools/tos_firewall_check.py` 게이트 PASS**(MINOR-10) — 신규 테스트 파일도 TOS-FW-A 대상;
   `inspect`는 stdlib(허용·실측)·`functools`도 stdlib. network/escape 0.
7. **REGREP 게이트 이행**(§12) — 인용 line 전건 재실측.
8. **닫는 EV 0 유지**(§9).

---

## 8. fail-closed·극성 규율 (시리즈 상속)

- **양성 identity**: admit 판정 = `disposition in ADMITTING_DISPOSITIONS`(vocabulary.py:54-56).
- **∅ 양방향**: `SNAPSHOT_UNRESOLVED`/`BINDING_MISMATCH`/`EXPLICIT_EMPTY` 별개 member(vocabulary.py:32-46).
- **UNKNOWN-restrictive**: 포트 비-해소 → `value_view=None` → 전 operand UNKNOWN·fallback 0.
- **구조 파생 > 자기신고**: 값=preimage·as-of/digest=observation 파생(records.py:12-18).
- **탐지 vs 강제(over-claim 금지)**: "detects rather than enforces"(`__init__.py:62`) 계승·P3 봉인.

---

## 9. property test 타깃 (저작 증거·acceptance 아님·닫는 EV 0)

1. **P1 Protocol 잠금**: `session_token=`/side-method 삽입 뮤테이션 → KILLED.
2. **P2 생성자 잠금**: required→default/positional/`__init__`-외부-이동 뮤테이션 → KILLED(§4-P5).
3. **P3 over-claim seal**: planted "fully enforces" → FAIL·정직 문구 → PASS(과잉거부 guard).
4. **P4 G1-G4 포트 경계**: 4종 rejection·admit 0(뒤집기 뮤테이션 → KILLED).
5. **N1 비-보장**: same-as-of 붕괴 실증·상류 명명(**as-of 거부 삽입은 (b)·뮤테이션 아님**).
6. **source parity**: 구조-3형태 동일 digest·peek-분기 뮤테이션 → FAIL.
7. **additive 회귀**: 출하 marketfeed/dsl/engine/slice 테스트 전수 GREEN·**K1·K7·K8·K15 GREEN**.

---

## 10. not-this-contract / 명시 이연

1. **②(b) env-주입 재검증**(#32 §9-6) — **K7 정합 선행 판정 필요**(§0.3). **소유·산출물 지정(갭
   반영)**: (b) 착수 전, **오케스트레이터가** "재검증을 시그니처 확대 없이 K7·K8·K15와 정합시킬
   경로가 있는가"를 판정하고, 그 판정을 **서베이-형식 스코핑 노트 또는 (b) 계약 §0 判定 아티팩트**로
   기록한다 — 그 아티팩트 부재 시 (b) 저작 착수 금지.
2. **실 CIS 런타임**(수집·조립·발행) — 방화벽상 tos/ 안팎 불가(§0.1)·상류 소관.
3. **capsule 모델 변경** — #32 §0.2-1·발명금지 (a).
4. **`TimeCoordinateProjection`(시간 권위)** — 포트 아님(§2.3).
5. **estimator/window** — #32 §0.2-3.
6. **다심볼** — #37 소관·resolver 파라미터 무변경(resolver.py:159).
7. **정식 EV-L2 PASS**(설계 #2 §7 CII-EV-002) — P0-1/P0-3 선결.

---

## 11. 리뷰어 공격 지점 (선제 반론)

1. **"포트만 확정하는 계약이 무엇을 닫는가"(공허성·최대 공격면).** — 반론: (i) **정직 인정**: 닫는
   EV 0·신규 타입 0·거동 변경 0(메커니즘 기출하). 이는 정확한 스코프다(서베이 §E 3편: CIS 런타임은
   방화벽상 구현 불가). (ii) **정확한 델타(MAJOR-1 반영)**: v1.0의 "셋 다 오늘 단언 안 됨"은 **거짓**
   이었다 — fake-CIS 구동(`_slice_fixtures.py:335-422`)·exclusivity 거동(`test_slice_conformant_path.py:233-257`)·
   G1-G4·N1은 committed다. **진짜 신규는 셋뿐**: ① **P2 생성자 required-주입 inspect 잠금**(marketfeed
   테스트 inspect **0건** 실측 — 유일한 신규 구조 잠금), ② **P1 Protocol 자체 잠금**(D-E4
   `test_brokeradapter_transport.py:69-96` 동형·`session_token=` 삽입이 오늘 K3/K13/K4 무저촉인 공백
   봉인), ③ **P3 over-claim seal**(부재 방향 co-occurrence). 기존 게이트 단언의 **포트 경계 승격**
   (P4)은 재저작이 아니라 경계 이동이다. (iii) **동형성**: D-E4 §5.1(실 브로커 미구현)이 비준됐듯,
   #38은 그 ingress 동형이다 — #38 공허 = D-E4 §5.1 공허(모순).
2. **"두 Protocol은 이미 존재·테스트됨. 중복 아닌가."** — 반론: 기존은 resolver **소비**를 단언하나
   **Protocol 표면 자체(파라미터·call-only)** 는 아무 canary도 잠그지 않는다(P1 반증: `session_token=`
   무저촉). P2·P1·P3은 committed 표면에 additive이며 전건 GREEN 유지(K11 재사용·강화).
3. **"(b) 경계 침범 아닌가."** — 반론(MAJOR-3 정정): 발행 게이트 as-of **무변경**·env-주입 재검증
   **미도입**. **(b) 미밀수 증거는 K7·K8·K15**(value-free env byte-identical). K1 GREEN은 **N1/발명금지
   (f)** 증거일 뿐((b) 무감도였던 v1.0 주장 철회). P1 Protocol 잠금은 소비측만·dsl 진입점 무저촉.
4. **"docstring 개정은 self-report — marketfeed 자기 규율(`_base.py:11`) 위반."** — 반론(내부-정합):
   구조 속성(exclusivity·Protocol 표면·transport 어휘 부재)은 **구조로**(P1/P2·K3/K4/K13), 거동 의무는
   **fake-CIS 구동으로**(P4), over-claim은 **co-occurrence로**(P3) 봉인한다. docstring canary(P3
   positive·K2)는 **honesty-scope 선언**에만 국한 — marketfeed가 이미 쓰는 패턴
   (`test_marketfeed_package.py:232`).
5. **"`TimeCoordinateProjection` 제외는 자의적."** — 반론(실측): resolver.py:92-97이 "a 'now' reading"
   으로 명명(시간 권위)·`build_resolver`가 이를 생략하고 D-E3 `BarTimeProjection`이 converter에서
   적용(`_slice_fixtures.py:414-416`·converter.py:119-127). 흡수 시 scope creep. 명시 제외(§2.3).
6. **"CIS 부재 neg-grep 1행은 약하다."** — 반론: 1행(docstring)의 구조 뒷받침은 K12(TOS-FW-B/R)·
   K4(network 부재·AST)·K13(transport 어휘 부재)·P1(Protocol 표면). 부재는 방화벽+closure+Protocol
   잠금으로 봉인.

---

## 12. 미결·리스크 (구현 게이트)

- **REGREP 게이트(#35 §12 규율)**: 인용은 2026-08-05~06 실측이나 세션-직접분과 서베이-상속분(K10
  engine 잠금·#31/#33)이 혼재. **구현 시점 전건 재grep 필수.** **REGREP 실패(드리프트 발견) 처리
  경로(갭 반영)**: 드리프트 발견 시 → **구현 즉시 중단 → 오케스트레이터 보고 → 에라타 여부 판정**
  (인용 갱신이 additive면 진행·canary 정확-집합 충돌이면 시리즈 선례["구현이 더 충실하면 설계-정합"]
  판정). 임의 진행 금지.
- **⚠ 인용-불일치 정직 보고(v1.1)**: 비평 MINOR-2가 제안한 `value.py:40-41→:42-43`·`:42-45→:45-46`·
  `records.py:165→:166`은 본 세션 재-read와 **불일치**한다. 실측(2026-08-06): value.py 한계-블록
  :33-45, **N1(as-of)=:42-45**(비평 제안 :45-46은 :46 공백·오측)·**N2(fabricated-lineage)=:38-41**
  (비평 제안 :42-43은 as-of 블록·전위); records.py `seal_fetch_surface(...)` 호출=**:165**(비평 제안
  :166은 `for` 루프·off-by-one). ⇒ MINOR-2의 **취지(드리프트 제거)** 를 이행하되 **측정-정확 line**을
  적용했다(`records.py`는 모호 회피 위해 :162-165 범위). 비평의 나머지 MINOR-2(`__init__.py:60→:62`·
  TOS-FW-D `:23→:22-23`·#32 §2.3 `:319-320`)는 실측 일치·반영. 델타 재검증이 이 3건을 재대조하도록
  명시.
- **MINOR-4 정정**: v1.0 §12 "K3·K13이 터진다"는 **거짓**(실측: `session_token=`을 Protocol
  `__call__`에 넣어도 K3/K13/K4 무저촉). 이 공백이 곧 **P1 신설 근거**이며, P1 착지 후엔 그런
  파라미터가 P1 inspect canary에서 FAIL한다.
- **P3 over-claim seal 형태**: 반드시 **co-occurrence 규칙 + 과잉거부 guard**로 구현(단순 substring
  존재-검사는 "완전 강제" 삽입을 못 잡음·MAJOR-4). "enforces"·"enforcement" 단어의 정직 사용을
  삼키지 말 것.
- **P1 폐포=2 착지**: `TimeCoordinateProjection`을 CIS 표면으로 오분류하지 말 것(§2.3).

**구현자 이월 지시 register (델타 재검증·비평자 실행 검증·전부 즉시-탐지·1행 수정·fail-safe 방향)**:

- **① P3 whitespace 정규화**: §4-P3 전 substring 단언에 `" ".join(doc.split())` 적용 —
  `__init__.py:62-63` "none of\nthem" 개행 걸침으로 raw 검사가 착지 시 FAIL. 선례(델타 재검증
  제공): `test_egressgw_package.py:43`·`test_brokeradapter_import_closure.py:432`·
  `tos/tests/sci/test_seam_sir.py:123`.
- **② P1.3 token-wise 매칭**: ambient 배제를 `_base.py` `fetch_surface_offenders`식 `split("_")`+
  whole-name(과잉거부 방지)으로 — exact-name이면 헤드라인 예시 `session_token`을 놓침(주 봉인은
  P1.2·이는 중복 방어를 광고대로 실행).
- **③ P1.4 어노테이션 방식 고정**: `resolver.py:33` `from __future__ import annotations`로 어노테이션이
  문자열 — identity 비교 불가. **`typing.get_type_hints`로 해소**해 비교(문자열 비교도 가능하나
  get_type_hints가 formatting-robust). §4-P1.4 반영.

---

## 13. 명명·번호

- **문서 번호 #38** — 이연 ②(a) CIS 산출물 주입 포트 확정. 서베이 3-편(#36=①·#37=③·#38=②(a))의
  세 번째. 비준 #32(D-E2)에 대한 이연-closure 계약.
- **신규 src 심볼 0·신규 런타임 타입 0·신규 패키지 0·신규 src `.py` 0.** 변경 = `resolver.py`·
  `__init__.py` docstring additive + 신규 테스트 파일 `test_marketfeed_cis_port.py`(신규 canary
  P1-P5). P1-P3은 기존 표면/docstring을 **읽는** 테스트이므로 src 심볼을 더하지 않는다.

---

## 14. 확인하지 못한 것 (정직 보고)

- **비평 MINOR-2 line 3건과의 불일치**: §12 상세. 측정-정확 line을 적용했고 델타 재검증 대조 지점을
  명시했다.
- **서베이 상속 인용의 현재성**: `test_engine_value_view.py:148-170`(K6/K10)·#31/#33 인용은 직접
  재-read 안 함·REGREP(§12) 소관.
- **전체 스위트 GREEN**: 본 계약은 저작·테스트 미실행. 신규 P1-P5 통과는 구현·적대적 코드 리뷰 소관.
- **(b)의 실제 착수 가능성**: env-주입 재검증이 K7·K8·K15와 정합 가능한지는 (b) 별개 이연의 선결
  질문(§10-1)·본 계약 미판정.
- **상류 CIS의 미래 형태**: 주입 경계 너머 상류의 구체 형태는 스코프 밖(parity·§3.1).

---

## 15. 개정 로그 (v1.1 — 2026-08-06 독립 적대적 비평 REVISE 반영)

| finding | 처분 | 변경 위치 |
|---|---|---|
| **MAJOR-1** (§11-1(ii) 전칭 붕괴) | **채택** | §1·§2.1·§4(전제표·committed 인용)·§11-1(ii) 정확 델타(P1/P2/P4) |
| **MAJOR-2** (Protocol 자체 잠금 결손) | **채택** | §4-P1 신설(D-E4 :69-96 동형)·§6B·§0.3 "(b) 밀수 아님" |
| **MAJOR-3** (K1의 (b)-무감도·§3.4 모순) | **채택** | §0.3·§3.4 정합표·§6A K15 등재·§7·§11-3 — (b) 증거=K7/K8/K15, K1=발명금지(f) |
| **MAJOR-4** (over-claim seal 산출물 0·형태 결함) | **채택** | §4-P3 신설(존재+부재 co-occurrence+과잉거부 guard)·§5.3·§9 |
| **MINOR-1** (§0.5 neg-grep #2 오기) | 채택 | §0.5 #2 — 9 hits 실토·K4 인용 대체 |
| **MINOR-2** (인용 드리프트) | **부분 채택+실측 정정** | `__init__.py:62`·TOS-FW-D `:22-23`·#32 §2.3 `:319-320` 반영; value.py/records.py는 측정-정확 line 적용·§12·§14 불일치 정직 보고 |
| **MINOR-3** (파일명 오기) | 채택 | `test_marketfeed_resolver.py`·`test_marketfeed_package.py`로 전정 |
| **MINOR-4** (§12 "K3·K13 터진다" 거짓) | 채택 | §12 정정·P1 근거로 전환 |
| **MINOR-5** (§2.2 (A) blast-radius) | 채택 | §2.2 (A)·§0.6 — 생성 지점 3곳(:54·:418·:245) |
| **MINOR-6** (§4-4b 반증 불가) | 채택 | §4.2 N2 — 테스트 미신설·반증불가성이 근거·`lineage.py:102-107` 인용 |
| **MINOR-7** (parity 동어반복) | 채택 | §4.2 — 구조-3형태 + peek-분기 KILL 뮤테이션 |
| **MINOR-8** ("선택적 canary" 재량) | 채택 | §2.2 (C)·§4 — 전 신규 canary는 `test_marketfeed_cis_port.py`·`test_marketfeed_package.py` 무편집 |
| **MINOR-9** (K10 이중 표기) | 채택 | §6A K10 = **GREEN**(REGREP는 §12 총괄 게이트) |
| **MINOR-10** (§7 완료 기준) | 채택 | §7-5·7-6 — INDEX.md 등재·firewall 게이트(inspect/functools stdlib 실측) |
| **갭** (exclusivity 뮤테이션 확장) | 채택 | §4-P5(위치·positional·default 3경로) |
| **갭** ((b) 소유·산출물) | 채택 | §10-1 — 오케스트레이터 판정·아티팩트 부재 시 착수 금지 |
| **갭** (REGREP 실패 경로) | 채택 | §12 — 중단→보고→에라타 판정 |
| **오케스트레이터 Open Q 판정** | 등재 | §0.6 — 스코프 축소 승인(2026-08-06) |
| **델타 재검증 ACCEPT-WITH-MINOR(MAJOR 0·MINOR 3·NIT 3)** | **이월지시 등재**(v1.2) | v1.1 실측 반박 3건 확정(비평자 자기 정정값 철회·sed 2행 전위); §12 ①②③·§4-P1.3/P1.4/P3·§4.2 N2/parity·NIT 3 반영 |

- **v1.2 (2026-08-06)**: 델타 재검증 ACCEPT-WITH-MINOR 반영 — 구현자 이월 3건 등재(§12)·Open Q 2건
  확정(§4-P3 대상·§4.2 parity)·NIT 3건. **착지 정밀도만·설계 판정 불변.**
- **v1.1 (2026-08-06)**: 독립 적대적 비평 REVISE(MAJOR 4·MINOR 10) 전건 반영(위 표).
- **v1.0-draft (2026-08-05)**: 최초 저작. 독립 적대적 비평 대기.

<!-- 저작 증거·닫는 EV 0. 비준 전 파이프라인: 독립 적대적 비평(v1.0 완료) → 개정(v1.1·본 산출) →
운영자 위임 자동 비준(ADR-002 Part-2/3 연장) → 구현 → 적대적 코드 리뷰. -->
