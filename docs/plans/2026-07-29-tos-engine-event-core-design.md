# 설계 문서 #31 — tos.engine: 단일 이벤트 코어 + 결정 파이프라인 오케스트레이션 계약 (D-E1, 수직 슬라이스 #1, provisional·닫는 EV 0건) (2026-07-29, v1.1)

> **⚖ 비준 기록**: **2026-07-29 운영자 위임 자동 비준(v1.1)** — 2026-07-29 운영자 지시("Part-2/3 설계 비준도
> 위임 자동비준으로 연장")에 따라, 오케스트레이터가 게이트 조건(독립 비평 리뷰 REVISE → v1.1 전건 처방 반영·
> 실증 반론 0 → 오케스트레이터 재실측 스팟체크 통과[MAJOR 1~3 반영·개정 로그 §15·코드 앵커 일치])을 검증하고
> 기록함. 시리즈 최초 Part-2/3 설계 비준. 품질 파이프라인 잔여 단계(구현 → 적대적 코드 리뷰 → 게이트)는 유지.
> 본 비준은 프로젝트 측 설계 계약 발효이며, ADR acceptance(EV 실행 증거)·live authorization과 무관하다(§1.1).
> 효력: Phase 1 `tos/src/tos/engine/` 구현 착수.

> **v1.1 개정(2026-07-29, 독립 비평 리뷰 REVISE 반영 — CRITICAL 0·MAJOR 3·MINOR 3·Gap 2·NIT 2; 인용 무결성
> 91/92·phantom 0·§0.5 규율 작동 판정)**: 열린 세계 배선 미명세 3건 봉합 — **(MAJOR-1)** 비동기-send 재진입
> 중복노출 창을 provisional RCL stand-in의 at-most-one retention으로 봉인(§4.4·§2.1(iv)·§7.2-9·§8)·**(MAJOR-2)**
> D1↔D4 admission 술어를 DSL AST로 검사 가능한 형태로 재정의("outcome-게이팅 compare는 ≥1 capsule-sourced operand
> 필수"·"Critical-Input-결정 operand" 문구 철회·부분 봉인 정직 명기·§3.2(3)·§3.5·§7.2-8)·**(MAJOR-3)** 결정론
> canary에 random/uuid/secrets 추가 + step-12 attempt-id content-addressed 파생 명세(§7.1·§4.3). Gap/MINOR/NIT
> 전건 반영(개정 로그 §15). **아키텍처 4판정·5 핵심 결정·provisional 스코프는 리뷰 지지로 유지.**
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 스펙 텍스트
> (RFC/ADR/템플릿/프로파일/register)를 **변경하지 않는다.** 본 문서는 Part-2/Part-3 RFC(RFC-003 결정·RFC-005
> 실행·RFC-002 §10.7 아키텍처·RFC-008 DSL)를 그린필드 `tos/src/tos/engine/` 신규 패키지의 **owning runtime**
> — 단일 이벤트 코어 + Execution Coordinator 결정 파이프라인 시퀀서 — 로 실현하는 계약이다. 코드·git 커밋은
> 본 문서 범위 밖이다(비준은 오케스트레이터 소관). **본 문서는 시리즈 최초의 Part-2/3 엔진 층 설계다** — 이제까지의
> 30편(ADR-002 시리즈)이 순수 결정 커널(닫힌 세계)이었다면, 본 문서는 그 커널들을 **배선**하는 열린 세계의
> 첫 설계이며, 시리즈 교훈("fail-open은 술어 내부가 아니라 배선에 산다" — 엔진 완주 경로 평가 §2:45-47)이
> 정확히 겨누는 지점이다.
>
> **⚠ provisional·닫는 EV 0건 (본 문서 최상위 정직 선언 — §1.1)**: 본 슬라이스 산출은 **엔지니어링-통합
> provisional**이며 **어떤 EV-L2+ PASS도 주장하지 않는다.** 이유: (a) G2 프로덕션 canonicalization 미결
> (register §6:132 — `ev-l1-provisional-0`·sha256은 비프로덕션·"EV-L2+ 실행 전 필요"), (b) P0-1 bounds 승인·
> P0-3 독립 리뷰어 지정 미완(register §4:108 — 완료·서명 전 어떤 행도 READY/PASS 불가), (c) 본 설계가 배선하는
> 여러 단계(approval·aggregate-risk·action-flow·**RCL 원자 commit**)는 슬라이스 #1에서 **비권위 provisional
> stand-in**으로만 존재한다(실 linearizable ledger·실 독립 승인자 부재 — §4.4). 따라서 슬라이스는 **배선의
> 기계·패리티 실증**이지 결정/실행/리스크 모델의 acceptance 증거가 아니다. GOV-001의 세 거버넌스 행위(비준 /
> ADR acceptance / live authorization) 중 어느 것도 수행하지 않으며 어떤 EV/AC/acceptance도 선언하지 않는다.
>
> **비준 기록**: 2026-07-29 운영자 위임 자동 비준 대상(v1.0 초안 → v1.1 개정; 수직 슬라이스 스코핑 서베이 §6-3 해소 주석 —
> "Part-2/3 설계 비준도 위임 자동비준으로 연장"). 게이트: 독립 비평 리뷰 통과 + upgrade 조건 충족을 오케스트레이터가
> 검증 후 "운영자 위임 자동 비준(2026-07-29 연장 지시)"으로 기록·집행. 품질 파이프라인[저작→1차 심사→독립 비평→
> 개정→구현→적대적 코드 리뷰→게이트] 전량 유지. **ADR acceptance·live authorization은 위임 밖 별개 게이트로 잔존.**
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): 본 계약의 이벤트·상태·시퀀스 어휘는 전부
> broker-agnostic이다. KIS·KRX 사실은 등장하지 않으며, broker 능력은 brokercap 주입값(비규범 Broker Capability
> Profile INSTANCE·트랙 d)으로만, 세션시각은 venue `SessionPhase` opaque 주입 토큰으로만 표현한다.
>
> **선행 문서(의존)**:
> - [설계 #1 — `tos/` 경계 & import-firewall 계약 (v2, 운영자 비준)](2026-07-20-tos-boundary-and-import-firewall-design.md).
>   모든 모델은 설계 #1 §2.4 레이아웃에 놓이고 §3.2 허용목록 안에서만 의존한다(본 문서 §0.3).
> - [수직 슬라이스 스코핑 서베이 (비규범)](2026-07-29-tos-engine-vertical-slice-scoping-survey.md) — 슬라이스 #1
>   경계·seam 3분류·D-E1~D-E4 분해. **비규범이므로 규범 판정(조항 인용·seam 채택)은 본 설계가 재실측으로 수행.**
> - [tos.dsl 실전략 de-risking 스파이크 (비규범)](2026-07-29-tos-dsl-spike-findings.md) — §5 브리프 지시 5개가
>   본 문서의 핵심 결정(§3~§4)의 실측 근거.
> - [Phase-0 인간 게이트 register (비규범)](2026-07-29-tos-phase0-human-gate-register.md) — provisional 제약 원천.
>
> **규범 원천(전부 2026-07-29 자체 grep 실측·anti-phantom §0.5)**: ADR-002-002 §11(Normal Commitment Flow —
> **본 시퀀서의 규범 척추**)·§10 Capacity State·§5 INV·RFC-002 §9.1 Authority Ownership 매트릭스·§10.7 Execution
> Coordinator·§10.8 Broker Egress Gateway·§12 Orthogonal State·RFC-003 §7 Decision Pipeline·§8 Inputs·§9/§9.1
> Proposal/Outcome·§10 Determinism·RFC-005 §6 Principles·§7 Approved-Intent Path·§11 UNKNOWN·§12 Boundary·
> RFC-008 §10 Consuming Layers.

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것 (7건)

1. **패키지 명명 `tos.engine`** (negative-grep 실측 충돌 0·§10.1). 신규 그린필드 owning-runtime 패키지.
2. **단일 이벤트 코어 계약** — 동기·결정론 이벤트 루프, 닫힌 이벤트 어휘, wall-clock 직접 호출 금지(tos.time 주입
   좌표), 슬라이스-로컬 비권위 core state. 백테스트(D-E3)와 paper(D-E4)가 **같은 코어**를 소비하는 인터페이스(§2).
3. **결정 파이프라인 오케스트레이션** — RFC-003 §7의 4단계 span(Accept context → Interpret → Decide → Bind/emit)을
   기구현 `tos.dsl.determinism.evaluate`(:238)로 구동. evaluator 재작성 금지(§3.1).
4. **Execution Coordinator 시퀀서 계약** — ADR-002-002 §11의 **19-step Normal Commitment Flow**를 순서대로,
   각 단계를 주입 stage 인터페이스로 호출하는 fail-closed 시퀀서. 이것이 본 문서의 **하중 안전 콘텐츠**(§4).
5. **5개 핵심 결정**(스파이크 §5·서베이 §6): env-구성 seam 계약(§3.2)·G4 디스패치(§3.3)·G14/G15 degrade 배선
   (§3.4)·G11/G12 admission 분기(§3.5)·동기/비동기(§2.1). 요지는 §0.4 표.
6. **D-E1/D-E4 import 경계 + provisional stand-in 정책** — 시퀀서가 권위 런타임(approval·ARA·AFG·RCL·send)을
   **주입**으로 결합해 슬라이스 #1에서 비권위 stand-in 또는 D-E2/3/4 구현으로 채운다(§0.4·§4.4·§12).
7. **firewall 준수** — `tos.engine`은 시리즈 최초의 **광폭 import-closure 통합자**(§0.3).

### 0.2 하지 않는 것 (NO 목록·경계)

1. **evaluator 재작성 금지.** `tos.dsl.determinism.evaluate`(:238)는 이미 출하되어 작동(스파이크 §0-§1). 본
   문서는 그 **주변 오케스트레이션**만 만든다.
2. **실 RCL linearizable ledger 미구현.** ADR-002-002 §8(§8.1 Linearizability:403·§8.3 Fencing Epoch:434·
   §8.4 CAS:449)의 상태 있는 유일-writer ledger는 **미래 런타임**(RFC-002 §10.5·§9.1:557 "sole serialization
   and mutation authority"). 슬라이스는 비권위 in-memory reservation projection만(§4.4).
3. **실 독립 승인·Aggregate Risk Authority·Action Flow Governor 런타임 미구현.** iap/are/afg는 술어·모델만
   기구현이고 각 **owning runtime은 미래**(are/__init__:17-18·afg/__init__:28-29). 슬라이스는 provisional
   승인/decision stand-in(§4.4).
4. **Order Construction Service·Broker Egress Gateway·Broker Adapter·brokercap INSTANCE = D-E4.** 실 전송·서명·
   네트워크 I/O는 본 문서 밖(§12).
5. **Market-Data feed·Critical Input 값 표면 = D-E2.** 본 문서는 seam **계약**만 확정하고 값 표면 구현은 이연
   (§3.2 — 첫 결정·D-E2 블록커).
6. **이벤트 백테스트·paper fill 모델·cost-realism·차등 오라클 = D-E3**(서베이 §0 판정 3).
7. **라이브 실주문·비동기 I/O.** GOV-001 제3행위 밖(register §4). 비동기는 D-E4 send 경계로 이연(§2.1).
8. **닫는 EV/AC 0건.** §1.1 — 본 산출은 provisional. acceptance는 §9의 후속 게이트 소관.
9. **통계적 edge 증명·multi-symbol portfolio vector.** 서베이 §1 OUT-4/5.

### 0.3 firewall 준수 선언 (설계 #1 §3.2/§3.3에 대한 본 계약의 준수)

- **`tos.engine`은 시리즈 최초의 광폭 import-closure 통합자다.** 지금까지의 32 패키지는 순수 결정 커널로
  import-closure가 최소({tos, tos.canonical, tos.ordering, self} + 소수 sibling edge)였다(wdr test 실측:
  `tos/tests/wdr/test_wdr_import_closure.py:46` `_ALLOWED_TOS_PACKAGES = {tos, tos.canonical, tos.ordering,
  tos.wdr}`). 엔진은 **정반대** — 커널들을 조립하는 owning runtime이라 closure가 커널들의 **상위집합**이다.
  이것은 결함이 아니라 통합자의 본질이다(§10.2 리뷰어 반론).
- **allowlist(부분집합) 형식 유지**(설계 #1 §3.3:196-204 — ①커스텀 AST 게이트 default-deny·②import-linter
  전이 검출·③required CI check). `tos.engine`의 import-closure는 다음 부분집합이어야 한다:

  ```
  {tos, tos.canonical, tos.ordering, tos.dsl, tos.capsule, tos.time, tos.evidence,
   tos.ioc, tos.venue, tos.rcl, tos.are, tos.afg, tos.cur, tos.engine}
  ```

  근거: **직접 실현 edge 6**(canonical·ordering·dsl·capsule·time·evidence — 결정 파이프라인 + core state +
  provisional sink) + **계약-타이핑 edge**(ioc·venue·rcl·are·afg·cur — 19-step 시퀀서가 참조하는 stage
  verdict **타입**; stage **로직**은 주입). **brokercap·egress는 D-E4 edge**(send 경계 주입 인터페이스 너머 —
  §0.4·§12·§10.2 공격 지점).
- **여전히 금지**: `shared.*` 운영 패키지·`os.environ`/`getenv`·network stdlib·`importlib`/`exec`/`eval`/
  `compile` 동적 escape·`numpy`/`pandas`(설계 #1 §2.3). 엔진은 **주입** clock/feed/egress를 받되 스스로 열지
  않는다 — 이벤트 루프의 wall-clock 금지가 그 구체(§2.3). `shared/backtest`·`shared/determinism/lookahead_guard.py`·
  `shared/kis`는 **차등 오라클·지식 참조**일 뿐 import 아님(서베이 §7-5).

### 0.4 핵심 아키텍처 판정 요지 (5개 핵심 결정 + 경계 + provisional 정책)

| # | 결정 | 판정 | 근거(요지) | 리스크 |
|---|---|---|---|---|
| **D1** | env-구성 seam 계약 (§3.2) | 시장 수치는 **admitted Critical Input observation**으로 Snapshot body를 통해 `"capsule"` 소스로만 흐른다. `config.bindings`(determinism.py:60)는 **저작자-상수만** 싣고 **시장 파생값 금지**. 계약 확정, 값 표면 구현은 **D-E2 이연** | RFC-008 §10:327-331·RFC-003 §8:236-237 재라벨링 금지. 현 유일 작동 채널(config relabel)이 §10 위반(스파이크 G6-G10) | D-E2 미착지 시 슬라이스는 비-conformant 스파이크 채널로만 돌아 §10 위반 seam 노출 → **명시 provisional 봉인**(§3.2) |
| **D2** | G4 디스패치 (§3.3) | **instrument-키 레지스트리**. 키는 `AuthoredStrategy`의 `TargetSpec`(vocabulary.py:193)이 선언한 (account, instrument)에서 **구조 파생**. 이벤트 instrument와 불일치 시 **fail-closed(무평가)** | 전략 1개=하드코딩 instrument 1개(스파이크 G4). 키 자기신고 금지(구조 파생>자기신고) | 다심볼 확장은 레지스트리 N-entry로 인터페이스 무변경 |
| **D3** | G14/G15 degrade 배선 (§3.4) | 코어가 `resolve_bound`(bounds.py:40)→`degrades_to_no_action`(:70)→`select_outcome(on_exhaustion=…)`(:82) 배선. degradation → **NO_ACTION 접기 + 구별된 degradation 증거 기록**. degraded는 commitment flow 진입 금지 | `evaluate()`는 bound 기계 미호출(스파이크 G14 negative-grep). DecisionKind 4멤버뿐·WITHHOLD/DEGRADED 부재(G15) | DCE-INV-007 bound 값 미신설(register §8-1:223) → provisional 값·§8 |
| **D4** | G11/G12 admission 분기 (§3.5) | 슬라이스 #1은 **in-process typed `DecisionPolicy`/`AuthoredStrategy` 객체만** 수용 → escape-checker 불요(typed algebra=admissible-by-construction). **직렬화 입력 경로는 명시 이연**(seam 예약: 파싱+candidate lowering+전략↔verdict 바인딩) | 스파이크 §2 그룹 C 정직 프레임. YAGNI(서베이 OUT) | config-주도 원칙(CLAUDE.md)은 직렬화 경로를 나중 요구 → seam 예약 필수. **admission은 D1 강제도 소유**(Critical Input이 `"config"` 경유 금지 검증 — D1↔D4 결합·§3.5) |
| **D5** | 동기/비동기 (§2.1) | **동기·단일스레드·결정론 코어**. 한 이벤트를 완결까지 처리 후 다음. 비동기 I/O는 **D-E4 send 경계로 격리**·결과는 `EGRESS_RESULT` 이벤트로 재주입 | 결정론(RFC-003 §10)·리플레이·race fail-open 제거. NT "단일 코어" 구조 절도(엔진 §3-2). 분봉 규모 충분 | 실시간 다피드 동시성은 D-E4 경계 설계에서 재검토 |

- **경계·provisional 정책(핵심)**: 시퀀서는 19-step을 **주입 stage 인터페이스**로 결합한다. 각 stage는 (a) 슬라이스
  #1에서 available 순수 술어(ioc·venue·cur·ARE/AFG decision 술어), (b) **비권위 provisional stand-in**(approval·
  RCL 원자 commit·Transmission Capability — 실 런타임 부재), (c) **D-E4 구현**(send 경계)로 채워진다. **(b)류는
  어떤 capacity/approval EV도 닫지 못한다** — 배선만 실증(§4.4). 이 정책이 §1.1 "닫는 EV 0" 의 구조적 이유다.

### 0.5 anti-phantom 규율 (FD #27 §0.5·SIR #28 §0.5 상속 — 부재 주장·존재 주장 양방향 grep)

- 본 문서의 **모든 file:line 인용은 2026-07-29 자체 grep/read 실측값**이다(서베이·스파이크의 인용을 재실측으로
  확인·규범 판정은 본 설계 소유·서베이 §5:110-111). 스펙/코드 개정 시 행 이동 — 재사용 시 재실측.
- **부재 주장은 negative-grep 병기**: (1) `tos.engine` 충돌 부재 — `ls -d tos/src/tos/*/ | grep -iE
  'engine|event|loop|coord|orch|pipeline|runtime'` → 매칭 0(§10.1). (2) `engine`이 firewall 배제 목록에 미예약 —
  `grep -rniE 'tos\.engine|"engine"' */__init__.py` → 0. (3) `evaluate()`가 bound 기계 미호출 — 스파이크 G14
  `determinism.py`에 `resolve_bound`/`select_outcome`/`BoundState` negative-grep exit 1(재확인).
- **존재 주장 실측 확인**(SIR #28 교훈 — 미검증 존재 주장이 대칭 사각): 인용한 심볼은 전부 export 표면 read로 확인
  (dsl/__init__:70-98·capsule/__init__:46-53·ioc/__init__:76-104·venue/__init__:112-141·time/__init__:66-71·
  evidence/__init__:54-99·rcl/__init__:84·bounds.py:40-111·vocabulary.py:88-143·determinism.py:60-284·
  proposal.py:73-128·capsule.py:79-233).

---

## 1. 범위 + provisional 선언 + 조항 하중 지도

### 1.1 provisional 선언 — 왜 슬라이스가 EV를 닫지 못하는가 (정직 스코프)

세 독립 사유가 합류한다:

1. **G2 프로덕션 canonicalization 미결.** tos.capsule/canonical/evidence는 전부 `EVL1ProvisionalCanonicalizer`/
   `EV_L1_PROVISIONAL_*`(capsule/__init__:39-45·evidence/__init__:62 `EV_L1_PROVISIONAL_CHAIN_VERSION`)만 보유.
   register §6:132 — "프로덕션 canonical serialization·digest 승인 … EV-L2+ 실행 전 필요." 슬라이스 산출의 모든
   digest는 비프로덕션.
2. **P0-1 bounds 승인·P0-3 독립 리뷰어 지정 미완.** register §4:108 — "P0-1/P0-3 완료 + 정식 실행·서명 전에는
   어떤 행도 READY/PASS 불가." 본 설계가 소비할 여러 bounds(§8)가 null/미신설.
3. **권위 런타임 부재(구조적).** 본 시퀀서가 순서대로 부르는 approval·aggregate-risk·action-flow·**RCL 원자
   commit** 단계는 슬라이스 #1에서 비권위 provisional stand-in이다(§4.4). 실 linearizable ledger(ADR-002-002 §8)·
   실 독립 승인자가 없으므로 **capacity commitment·approval EV는 원리적으로 닫을 수 없다.**

⇒ 슬라이스 #1의 가치는 **배선(seam)의 기계·패리티 실증**이다(엔진 §3-1a·서베이 §7-3 권고 (a)). 이 문서는
"가설 증거로서의 admissible backtest"를 제시하지 않는다 — 그렇게 하면 ADR-DEV-010 §8로 자기-disqualify(서베이
§7-2). **닫는 EV = 0. 후속 정식 수용은 §9의 게이트 완료 후 재실행.**

### 1.2 조항 하중 지도 (RFC-003/005/002/008 → D-E1 Realize / Defer·자체 실측)

| 원천 | Realize (D-E1 하중) | Defer (명시 이연) |
|---|---|---|
| **RFC-003 §7** 결정 파이프라인 | 199-215 4단계 span(Accept context 201-204·Interpret 205-207·Decide 208-212·Bind/emit 213-215)·217-220 emission 종료 | §12:438 positive-expectancy·§13:470 replaceability(단일 전략) |
| **RFC-003 §8** inputs | 234-237 Critical Input via Capsule only·no relabel(**D1 근거**) | §7(RFC-004) market-state 모델 |
| **RFC-003 §9/§9.1** Proposal/Outcome | 258-264 2 outcome types·292-301 no-action/explicit-flat 구조 분리·320-326 invalid context is not a decision·327-339 atomic unit(per-instrument) | vector as set(다심볼 이연·서베이 OUT-5) |
| **RFC-003 §10** 결정론 | 345-363 reproducible·point-in-time snapshot·version/record | 365-382 replay≠recompute(승인측 SAFE-034 — 슬라이스 소비 아님) |
| **RFC-005 §6** 원칙 | 167-168 approved-Intent-only·170-172 every child order full machinery·173-175 irreversibility·179-181 UNKNOWN restrictive·182-183 model informs not authorizes | — |
| **RFC-005 §7** Approved-Intent Path | 189-192 exact ordering=ADR-002-002 §11·enforced by Execution Coordinator(§10.7)·**SHALL NOT redefine/reorder/abridge**·210-213 no invent/default/normalize/round/repair | §8:217-248 slicing/최적실행(단일 주문 slice 불요) |
| **RFC-005 §11** UNKNOWN | 319-343 SAFE-021·325-327 UNKNOWN≠rejection worst-credible never-silently-retried·335-337 POTENTIALLY_LIVE post-SEND_STARTED crash=possibly-live | §9 TCA(cost-realism만 D-E3) |
| **RFC-005 §12** 경계 | 346-377 11 SHALL NOT(시퀀서 규율 원천·§4.3) | — |
| **RFC-002 §9.1/§10.7** 권위·Coordinator | 545-576 Authority Ownership 매트릭스(551·557·565·566·574)·708-724 Execution Coordinator 책임+2 SHALL NOT | §10.8:728-767 Broker Egress Gateway(=D-E4) |
| **RFC-002 §12** Orthogonal State | 1231 UNKNOWN first-class(core state·§2.4) | 전 orthostate 런타임(forward seam) |
| **RFC-008 §10** consuming | 327-331 Critical Input always·no relabel(**D1**)·347-350 UNKNOWN restrictive | layer 2/3·numeric bounds(dsl/__init__:20-26 미구현) |

### 1.3 Normal Commitment Flow — 규범 19-step 순서 + 슬라이스 #1 도달성 (본 시퀀서의 척추)

**⚠ 재실측 정정(서베이와 어긋남·§14 보고)**: 서베이 §0 판정 1은 "RFC-005 §7:193-199 … **12단계**"로 표현하나,
**RFC-005 §7:193-199는 비규범 요약문(11 phase)이고 규범 척추는 ADR-002-002 §11의 19 numbered step**이다.
RFC-005 §7:192는 명시적으로 "RFC-005 SHALL NOT redefine, **reorder, or abridge** that sequence." ⇒ **D-E1 시퀀서는
ADR-002-002 §11의 19-step을 정본으로 순서 배선하고 RFC-005 요약을 정본으로 삼지 않는다.** (19-step 실측:
§11.1:580-588 step 1-7 · §11.2:590-595 step 8-11 · §11.3:597-601 step 12-14 · §11.4(:603 header) step 15-19(:605-609)·crash note :611.)

| step (ADR-002-002 §11) | 소유 actor | 슬라이스 #1 도달성 |
|---|---|---|
| 1. Decision Service가 immutable Intent proposal 생성 | Decision Service | **REALIZE(D-E1)** — 결정 파이프라인(§3)·`evaluate`→Proposal |
| 2. Order Construction이 non-authorizing candidate command 생성 | Order Construction Service | **주입 stage** — ioc `compile_command`(순수 available)·runtime wrapper=D-E4 |
| 3. Venue Constraint Gate가 candidate 평가·Admissibility Decision | Venue Constraint Gate | **주입 stage** — venue `session_phase_admits`/`order_shape_admissible`(순수 available) |
| 4. Independent Approval이 exact proposal 승인·Intent 등록 | Independent Approval Service | **provisional stand-in(§4.4)** — 실 독립 승인자 부재·비권위 |
| 5. Economic Effect Envelope 도출 | Order Construction (ADR-002-020) | **주입 stage** — ioc `EconomicEffectEnvelope`=rcl `CapacityVector`(순수 available) |
| 6. Aggregate Risk Authority가 Aggregate Risk Decision 발행 | Aggregate Risk Authority | **provisional stand-in** — are 술어 available·Authority 런타임+Snapshot 미래(are/__init__:17-18) |
| 7. Action Flow Governor가 Action Flow Decision 발행 | Action Flow Governor | **provisional stand-in** — afg 술어 available·Governor 런타임 미래(afg/__init__:28-29) |
| 8-10. RCL이 verify + 원자 commit(`COMMITTED_UNBOUND`) + Action Flow Permit | Risk Capacity Ledger | **provisional stand-in(핵심)** — rcl 술어/CapacityVector available·**실 linearizable ledger 미래**(§8.1:403·§9.1:557). 비권위 in-memory reservation |
| 11. Order Conformance Proof 생성 | Order Construction (ADR-002-020) | **주입 stage** — ioc `command_conforms`/`OrderConformanceProof`/`mutation_fence_holds`(순수 available) |
| 12. **Execution Coordinator가 unique attempt request 생성**(bound to proof + Permit) | **Execution Coordinator** | **REALIZE(D-E1)** — Coordinator의 유일 직접 행위(§4.3) |
| 13-14. RCL이 attempt bind·`ATTEMPT_BOUND`·single-use Transmission Capability 발행 | Risk Capacity Ledger | **provisional stand-in** — 실 ledger 미래·비권위 token |
| 15-19. Broker Adapter verify·`SEND_STARTED` durable·`POTENTIALLY_LIVE`·network call·evidence 기록 | Broker Adapter / Egress Gateway | **D-E4** — send 경계·brokercap·egress·cur·network I/O |

**정직 귀결**: D-E1이 코드로 **직접 실현**하는 step은 1·12 두 개뿐이다. D-E1의 진짜 산출은 그 사이를 잇는 **19-step
fail-closed 시퀀서**(§4)와 **결정 파이프라인**(§3)이며, 권위 step(4·6·8-10·13-14)은 비권위 stand-in, send step
(15-19)은 D-E4다. 이 구조가 §1.1 "닫는 EV 0"을 구조적으로 강제한다.

---

## 2. 이벤트 코어 계약 (D5 + 어휘 + time 주입 + core state)

### 2.1 결정 — 동기·단일스레드·결정론 이벤트 루프 (D5)

**판정: 슬라이스 #1의 코어는 동기·단일스레드·결정론이다. 비동기 I/O는 D-E4 send 경계로 격리하고 결과를
`EGRESS_RESULT` 이벤트로 코어에 재주입한다.**

- **근거 1(결정론).** RFC-003 §10:345-348 — "given the exact recorded Decision Context, Decision Policy version,
  and configuration version, an independent re-execution SHALL reconstruct the same outcome." 동기·단일스레드 코어는
  이 재현성을 자명하게 만들고, 비동기 스케줄 비결정(race)이 낳는 배선 fail-open 클래스를 원천 제거한다(엔진 §2:48-49
  "현 파이프라인은 이 규율로 async를 생산해 본 적 없다" — 리스크 회피).
- **근거 2(백/라이브 패리티 — NT 구조 절도).** 엔진 §3-2:63-65 — 백테스트와 라이브가 **단일 이벤트 코어**를 공유.
  코어를 동기·결정론으로 두면 백테스트(D-E3, 역사적 bar 재생 — 본질 동기)와 paper(D-E4)가 **같은 시퀀서**를 돈다.
  차이는 **이벤트 소스와 egress 싱크뿐**(§12). 비동기를 코어 밖 edge에 격리하는 것이 이 패리티의 전제.
- **근거 3(봉투).** 분봉 규모·KIS 단일·KRX(엔진 §1 축·§3-5 YAGNI). 나노초 async 루프 불요.
- **검토·기각 대안**: (A) 코어 내부 asyncio 이벤트 루프 — 기각: 결정론·리플레이·패리티 3중 훼손, 배선 race
  fail-open 도입. (B) 멀티스레드 심볼-병렬 — 기각: 슬라이스 단일 심볼이라 무의미·공유상태 경합. (C) 완전 동기·send도
  블로킹 — 부분 채택하되 **send만 D-E4 경계로 뽑아 주입**(코어는 send 요청을 발행하고 즉시 반환·결과는 후속
  이벤트) — 이로써 코어는 블로킹 network에 매이지 않으면서 결정론 유지.
- **엣지케이스**: (i) send 결과가 영영 안 옴(J1) → `EGRESS_RESULT` 대신 **timeout 이벤트**가 UNKNOWN으로 재주입
  (§4.2·RFC-005 §11:325). (ii) 재주입 순서 역전 → ordering `compare_order`(ordering/__init__)로 인과 순서 강제·
  코어는 단조 소비. (iii) 코어 재기동 → J3 crash-recovery(recon·sbr·orthostate·ioc `recovery_revives_nothing`) —
  슬라이스는 provisional·§9 이연. **(iv·MAJOR-1 봉인) 재진입 중복노출**: send 요청↔`EGRESS_RESULT` 사이에 동일
  instrument의 2차 `DECISION_TICK` 도래 가능(동기 코어라도 **이벤트 간**에는 발생). 이는 §4.4의 provisional RCL
  stand-in이 outstanding POTENTIALLY_LIVE를 retain하고 겹치는 economic-effect 요청을 capacity-stage에서 deny함으로
  봉인한다(SAFE-021 at-most-one의 provisional 미러·RFC-005 §11:319-343·§12 item 7 :364-365).

### 2.2 이벤트 어휘 (닫힌 집합·DecisionKind 4멤버 규율 동형)

코어는 **닫힌 이벤트 kind 집합**만 처리한다(vocabulary `DecisionKind` 4-멤버 닫힘 규율 상속·미지 kind는 silent
drop이 아니라 **fail-closed 오류**). 슬라이스 #1 최소 집합:

| kind | 페이로드 | 의미·트리거 |
|---|---|---|
| `DECISION_TICK` | resolved `DecisionContextCapsule`(+ D-E2 Snapshot value 표면) + reference time 좌표 | admitted Critical Input 갱신 → bound instrument에 대해 결정 파이프라인(§3) 1회 구동 |
| `EGRESS_RESULT` | typed egress 결과(ack / **full-fill / partial-fill(체결수량+잔여수량)** / UNKNOWN / timeout / reject) | D-E4 send 경계에서 재주입 → 코어가 provisional reservation state 전이·증거 기록(권위 소비는 RCL 런타임 이연·§4.4). **partial은 partial로 표현·기체결분 재요청 금지**(RFC-005 §11:338-339·§6:176-178) |

- **닫힘 규율**: 이벤트 kind는 `StrEnum` 닫힌 열거. 디스패처는 **positive membership**(kind ∈ 집합)로만 진행,
  그 외 전부 fail-closed(§6 극성). 확장(cancel·reconciliation·corporate-action 이벤트)은 열거 추가로만·인터페이스 무변경.
- **핵심**: `EGRESS_RESULT`의 존재 이유 = 코어가 RFC-002 §10.7:719 "maintain potentially live order state"를
  이행하려면 send 결과를 소비해 reservation을 전이해야 함. 그 전이의 **권위**는 RCL 런타임(이연)이므로 슬라이스는
  provisional projection만 갱신(§2.4·§4.4).

### 2.3 time 주입 좌표 (wall-clock 직접 호출 금지)

- **규율**: 코어는 `time`/`datetime`/wall-clock을 **직접 호출하지 않는다.** tos.time은 그 자체가 clock-free
  (time/__init__:7-9 — "pure, non-transmitting, authority-free, and clock-free … opaque injected time coordinates
  … never reads time/datetime"). 코어의 시간은 **이벤트가 실어 오는 reference 좌표**다: 백테스트=bar timestamp,
  paper=주입 clock 판독(코어 내부 호출이 아니라 D-E4/D-E2가 이벤트에 실어 주입).
- **소비**: freshness/staleness는 tos.time 술어로 판정 — `freshness_verdict`(time/__init__:66)·
  `snapshot_age_admissible`(:71)·`session_open_positively`(:70)·`HealthState`(:38). 주입 reference 좌표 + snapshot
  관측시각으로 verdict를 얻고, verdict가 positive-admit 아니면 fail-closed(§4.2).
- **근거**: RFC-003 §10:352 "consume a point-in-time context snapshot and record the exact context identity/digest"
  — wall-clock 직접 호출은 point-in-time 재현성을 깬다. 결정론(D5)의 시간 축 구체화.

### 2.4 core state — 슬라이스-로컬 비권위 projection (orthostate forward seam)

- 코어는 bound Intent/Proposal에 대해 **provisional reservation state**를 유지한다: ADR-002-002 §10.1의 capacity
  상태 어휘(`COMMITTED_UNBOUND`:512·`ATTEMPT_BOUND`:518·`POTENTIALLY_LIVE`:524 …)를 **비권위로 projection**.
- **UNKNOWN first-class**: RFC-002 §12.1:1231 — UNKNOWN은 일급 조건. 코어 state는 UNKNOWN을 **명시 멤버**로
  가지며(누락·null이 아님) worst-credible로 소비(ADR-002-002 INV-006:174 "UNKNOWN … conservative upper bound …
  consume capacity"). §6 ∅ 양방향과 정합.
- **⚠ 비권위 선언 + forward seam**: 이 state의 **권위 소유자는 RCL 런타임**(ADR-002-002 §8 유일 writer·미래)과
  **orthostate**(RFC-002 §12 Orthogonal Trading State·`CompositeState`/`DimensionTransitionRecord`
  orthostate/__init__:70). 슬라이스의 core state는 그 권위 상태의 **projection**일 뿐·전이 권위 없음. **orthostate는
  forward seam**(구현 시점 디스크 재실측 — venue/PR 선례·서베이 §6-2 seam 규율): 착지·정합 시 typed-reuse 검토,
  미정합 시 provisional projection·명시 이연.

---

## 3. 결정 파이프라인 오케스트레이션 (RFC-003 §7 4단계 span)

### 3.1 4단계 span 구동 (evaluator 재작성 금지)

`DECISION_TICK` 수신 시 코어는 RFC-003 §7:199-215의 4단계를 **기구현 evaluator로** 구동한다:

1. **Accept context(§7:201-204).** bound `DecisionContextCapsule` 소비. Capsule이 missing/stale/incomplete/
   invalid면 **결정 금지·restrictive no-action**(§7:203-204). ⇒ 코어는 `evaluate` 호출 **전에** Capsule 유효성·
   freshness(§2.3 tos.time verdict)·`_REQUIRED_COVERED`(capsule.py:189-194) 충족을 positive-admit로 확인,
   불충족 시 `evaluate` 미호출·no-action 기록(§6 fail-closed).
2. **Interpret(§7:205-207).** `evaluate(strategy, capsule, config, *, scheme, enforcement_mechanism_version)`
   (determinism.py:238) 호출 — 순수 함수. "no hidden state, default, or out-of-context fetch"(§7:207)는 evaluate
   시그니처가 ambient source·fetch callable을 노출 안 함(determinism.py:250-252)으로 이미 보장.
3. **Decide(§7:208-212).** evaluate가 반환한 `EvaluationResult.outcome`(NO_ACTION / ACTION / FLAT / VECTOR —
   DecisionKind vocabulary.py:137-143·VECTOR :143). 슬라이스는 per-instrument(one Proposal)만(§9.1:327-339·서베이
   OUT-5). **`DecisionKind.VECTOR`(다심볼·:143) outcome 도래 시 fail-closed**(슬라이스 per-instrument 전제 위반 —
   무진행·restrictive no-action·기록; VECTOR 접기 규칙은 후속 다심볼 사이클 소유·MINOR-1).
4. **Bind and emit(§7:213-215).** outcome은 이미 exact Capsule identity+digest에 바인딩(`RecordedInputSignature`
   determinism.py:272-283 — `capsule_id`/`capsule_canonical_digest` 기록). "Binding does not create authority"
   (§7:215). 코어는 emit 후 **종료**(§7:217-220) — approval·commitment·transmission은 downstream(§4 시퀀서).

**evaluator 재저작 금지 재확인**(스파이크 §5-1): evaluate는 재현성 실증(동일 3-tuple → byte-identical
content-addressed Proposal·스파이크 §1). 본 문서는 그 **호출 전후 배선**만 소유.

### 3.2 D1 — env-구성 seam 계약 (첫 결정·D-E2 블록커·RFC-008 §10 재라벨링 금지)

**문제(스파이크 G6-G10 실측)**: `build_environment(capsule, config)`(determinism.py:88)는 정확히 `{"capsule":
capsule-content, "config": dict(config.bindings)}`(:105-108)를 반환. 그런데 **Capsule은 시장 수치 leaf를 실을 수
없다** — `price_and_order_constraints: tuple[str, ...]`(capsule.py:79·문자 명칭뿐)·Observation은 값 없이
`payload_digest` 포인터만(스파이크 G8)·Capsule은 `SnapshotRef`만 내장하고 snapshot body 미내장(capsule.py:233
`critical_input_snapshot: SnapshotRef`·스파이크 G9). ⇒ 유일 작동 채널 = `config.bindings: dict[str, ScalarValue]`
(determinism.py:60). 그러나 이는 **시장 데이터를 '설정'으로 재라벨링**(스파이크 G10)해 RFC-008 §10:327-331·RFC-003
§8:236-237 "SHALL NOT relabel a value as a 'feature,' 'signal,' 'derived field,' or 'override' to avoid Critical
Input governance"를 **위반**한다.

**계약 확정(D-E1 소유·값 표면 구현은 D-E2 이연)**:

1. **시장 파생값은 admitted Critical Input observation으로 `CriticalInputSnapshot` body를 통해 `"capsule"`
   컨텍스트 소스로만 흐른다.** RFC-004 §9:242-244 규범 — "SHALL consume market data only as admitted Critical Input
   with source identity, continuity, and provenance … never by unattributed fetch **or side channel**"(:244). 지표·밴드 등 파생값은 **상류(D-E2)에서 계산·admit**되고 Snapshot에
   observation으로 실린다(스파이크 G1 소유: "지표는 상류 Critical Input").
2. **`config.bindings`는 저작자-상수만 싣는다**(예: 밴드 stddev 배수 k, 기간 period — 저작자가 고른 상수). **시장
   파생값 금지.** determinism.py:53 docstring "the injected thresholds/constants a policy reads" 은 이 축소 해석으로
   봉인.
3. **`ADMISSIBLE_CONTEXT_SOURCES = {"capsule", "config"}`(vocabulary.py:88)는 유지하되**, admission(§3.5·D4)이
   **구조 검사 가능한 술어**로 재라벨링 escape를 부분 봉인한다(v1.1 재정의 — MAJOR-2; "Critical-Input-결정 operand"
   문구 철회·DSL에 그 속성 부재[`grep -rniE 'critical.?input.?determin|is_critical' tos/src/tos/dsl/` = 0]):
   **outcome을 게이팅하는 `Compare`(vocabulary.py:185)는 ≥1개 capsule-sourced `ref` operand를 가져야 하며, 두 operand가
   전부 `const`(literal) 또는 config-sourced `ref`인 compare는 inadmissible**. 이는 engine admission이 typed
   `DecisionPolicy.rules`(vocabulary.py:307)→`Rule.all_of`(:284)→`Compare.left`/`right`(:188/:190)→`Operand`
   (`const`:167 vs `ref` — `resolve_operand`:316-333)를 walk하며 검사(dsl 변경 불요·escape-checker `analyze` 무관).
   **정직 명기(부분 봉인)**: 이는 핵심 case(시장-의존 결정이 전부 config를 경유하는 재라벨링)만 막고, config에 시장값을
   넣으면서 capsule operand도 함께 두는 부정직 저작은 못 막는다 — **완전 enforcement는 D-E2 Snapshot provenance**
   (RFC-004 §9:242-244)가 소유. 이것이 **D1↔D4 결합**(engine admission 부분 봉인 + D-E2 완전 봉인).
4. **D-E2 소유 이연분**: `CriticalInputSnapshot`에 값-싣는 observation 표면 추가(source/continuity/provenance)·
   `SnapshotRef`→body resolver — `build_environment`가 무엇을 소비하는가의 **값 표면**. D-E1은 계약(무엇이 흐르고
   무엇이 금지인가)만 확정.

**⚠ provisional 봉인**: D-E2 미착지 상태에서 슬라이스를 돌리면 numerics는 스파이크의 비-conformant config-relabel
채널로만 흐른다. ⇒ **슬라이스 #1 단독 실행 시 이 채널은 명시 provisional·§10 위반 seam으로 표기**하고, 출하 계약
(shipped contract)에서는 **금지**한다. D-E2 착지가 conformant end-to-end의 전제(서베이 §3-2 소유 D-E2).

- **검토·기각 대안**: (A) `evaluate` 시그니처 확장해 Snapshot body 직접 수용 — 부분 기각: evaluate 재작성 금지
  (§3.1)이나, `build_environment`의 **입력 조립**(capsule의 SnapshotRef를 body로 resolve)은 evaluate 코어 불변인
  주변 배선이라 D-E2 소유로 허용. (B) config에 시장값 허용하되 "provenance 태그" 부착 — 기각: §10 재라벨링 금지의
  정면 위반·태그는 governance 우회의 전형(스파이크 G10 인용). (C) 별도 3rd 컨텍스트 소스 `"market"` 신설 — 기각:
  vocabulary 변경(evaluator 표면 확장)·`"capsule"`이 이미 Critical Input 정도(canonical governance)라 중복.

### 3.3 D2 — G4 디스패치 (instrument-키 레지스트리·구조 파생 키·불일치 fail-closed)

**문제(스파이크 G4)**: `TargetSpec` 전 필드가 리터럴 `str`(vocabulary.py:193·Operand 아님). ⇒ `AuthoredStrategy`
1개 = 하드코딩 (account, instrument) 1쌍. N-심볼 유니버스 = N개 content-addressed 전략.

**판정: instrument-키 레지스트리. 키는 전략의 `TargetSpec`이 선언한 (account, instrument)에서 구조 파생.**

- 코어는 `registry: Mapping[InstrumentKey, tuple[AuthoredStrategy, ...]]`를 받는다. `DECISION_TICK`(instrument X)
  수신 시 `registry[X]`의 전략(들)을 평가.
- **구조 파생 키(자기신고 금지)**: 레지스트리 키는 **각 `AuthoredStrategy`의 선언 instrument에서 계산**하고, 등록
  시 키↔전략-선언 instrument **일치를 강제**(불일치 등록 거부·fail-closed). ⇒ "레지스트리는 X라 하는데 전략은 Y를
  타깃" fail-open 봉인(구조 파생 > 자기신고·시리즈 교훈).
- **None(wildcard) instrument 등록 거부(MINOR-1)**: `TargetSpec.account`/`instrument`는 `str | None`
  (vocabulary.py:204-205). `instrument is None`(wildcard) 전략은 **레지스트리 등록 거부**(fail-closed·키 파생 불가) —
  Proposal wildcard 금지(RFC-003 §9:279-283)의 디스패치 층 미러.
- **이벤트↔전략 instrument 교차 확인**: 평가 직전 event.instrument == strategy 선언 instrument를 positive 확인,
  불일치 시 무평가·기록(§6). Capsule의 bound instrument와도 삼자 일치.
- 슬라이스 #1: 레지스트리 1-entry. 다심볼은 N-entry로 **인터페이스 무변경** 확장.
- **검토·기각 대안**: (A) per-symbol 전략 인스턴스 리스트 순회(키 없음) — 기각: O(N) 스캔·이벤트당 전 전략 평가로
  낭비·잘못된 심볼 평가 위험. (B) 와일드카드 전략(1개가 N심볼) — 기각: `TargetSpec` 구조가 금지(G4 하드코딩)·
  Proposal 와일드카드 금지(RFC-003 §9:279-283 "SHALL NOT use wildcard account, instrument …"). 레지스트리는 이
  구조적 사실의 O(1) 표현일 뿐.

### 3.4 D3 — G14/G15 degrade 배선 (bounded-evaluation → NO_ACTION 접기 + 기록)

**문제(스파이크 G14/G15)**: `bounds.select_outcome`은 호출자가 `on_exhaustion: Callable[[], NoActionOutcome]`을
공급해야 함(bounds.py:82-86). `evaluate()`는 bound 기계를 **호출하지 않는다**(negative-grep·§0.5). `DecisionKind`는
4멤버(NO_ACTION/ACTION/FLAT/VECTOR·vocabulary.py:137-143)뿐 — WITHHOLD/DEGRADED/ERROR 부재.

**판정: 코어가 bounded-evaluation degrade 경로를 배선한다.**

- **배선(⚠ symbolic 예산 회계·런타임 인터럽트 아님·MINOR-2)**: `resolve_bound(*, work_steps, budget_steps)`
  (bounds.py:40)은 **순수 정수 비교**(`work_steps <= budget_steps` → `COMPLETED` else `BOUND_EXHAUSTED`·
  bounds.py:53-67)이며 `evaluate`를 **mid-run 중단하지 않는다**(`evaluate`는 step 수 미보고). ⇒ `work_steps`는 코어가
  `evaluate` **호출 전** `DecisionPolicy` 구조(rules/compares/operands)를 walk해 얻는 **정적 복잡도 계수**이고,
  `budget_steps`는 주입 DCE-INV-007 예산(§8). 즉 **사전(pre) 예산 게이트** — 초과 시 `evaluate` 미호출·
  `degrades_to_no_action(state)`(bounds.py:70)→`select_outcome(…, on_exhaustion=…)`(bounds.py:82)에 **NoActionOutcome
  zero-arg factory** 공급.
- **접기 규율**: degradation → **NO_ACTION(restrictive) 접기 + 구별된 degradation 증거 기록**. ⚠ degradation은
  평범한 no-action과 **구별**되어 기록된다(사유가 다름 — 시리즈 "구조 파생·정직 기록" 교훈). degraded outcome은
  **commitment flow(§4) 진입 금지** — no-action은 §4의 시퀀스를 시작조차 안 함(§3.1 step 4 emit 후 종료).
- **DCE-INV-007 bound(§8)**: DSL 평가 time/resource bound(`work_steps`/`budget_steps`의 `budget`)는 승인된 bound
  키다 — register §8-1:223 `strategy-dsl:540-546`이 프로파일에 **키 자체 부재**(신설 대상). ⇒ 슬라이스는 **provisional
  budget 값**으로 배선(§8)·승인 전이라 증거 provisional.
- **검토·기각 대안**: (A) DecisionKind에 DEGRADED 멤버 추가 — 기각: vocabulary(evaluator 표면) 변경·기구현 4멤버
  닫힘 훼손. degradation은 **outcome type이 아니라 배선 사건**이라 NO_ACTION 접기 + 별도 증거가 정합. (B) degraded를
  ERROR로 예외 전파 — 부분 기각: bare `AttributeError`(스파이크 소소·determinism.py:268 `policy=None`)는 비정형
  fail-closed. 코어는 이를 **정형 degradation 기록**으로 승격(정직 기록)하되 진행은 여전히 차단.

### 3.5 D4 — G11/G12 admission 분기 (in-process typed·직렬화 경로 명시 이연·D1 강제 소유)

**문제(스파이크 G11/G12)**: `DecisionPolicy`/`AuthoredStrategy` → `CandidateProgram` 변환 함수가 tos.dsl 어디에도
없음(admissibility.py:108·전 10모듈 반환 negative-grep). checker 입력 도메인(candidate.py)과 저작 algebra
(vocabulary.py)가 분리. `AdmissibilityResult`는 strategy_id/digest 바인딩 필드 부재(evidence.py:95) — 퇴화 1-node
mirror도 ADMISSIBLE(판정이 실 아티팩트에 귀속 불가).

**판정(정직 프레임·스파이크 §2 그룹 C): 슬라이스 #1은 in-process typed `DecisionPolicy`/`AuthoredStrategy` 객체만
수용한다.**

- **근거**: typed algebra는 **구성상 admissible**(candidate.py "cannot express an escape attempt"·스파이크 §2)·
  escape-checker는 **타입 시스템 밖**에서 오는 후보용. in-process 구성은 타입 시스템이 곧 enforcement. ⇒ 슬라이스는
  escape-checker(`analyze`)를 **호출하지 않으며**(호출하면 G11 `AttributeError`), 이 seam은 **이연**(exercise 아님).
- **직렬화 경로 명시 이연 + seam 예약**: config-주도 원칙(CLAUDE.md "Configuration-driven only")은 전략이 나중에
  **직렬화/YAML/builder-UI 데이터**로 도착할 것을 요구. 그때 D-E1의 admission 인터페이스는 (i) 파싱→`CandidateProgram`
  lowering, (ii) escape-checker `analyze`/`is_admissible` 게이트, (iii) **전략↔verdict 바인딩**(G12 부재분 —
  strategy digest를 AdmissibilityResult에 결속)을 소유해야 한다. 본 문서는 이 **분기점을 명시**하고(스파이크 §5-5),
  타입 경계(typed admission boundary)를 지금 정의하되 직렬화 lowering+checking+binding은 **후속 사이클 소유**.
- **⚠ D1↔D4 결합(admission이 D1 부분 봉인 소유·v1.1 재정의·MAJOR-2)**: admission은 수용하는 전략의 **outcome-게이팅
  `Compare`가 ≥1 capsule-sourced `ref` operand를 가짐**을 typed AST walk로 검증한다(§3.2(3) 재정의·`DecisionPolicy.
  rules`:307 walk). 전 operand가 const/config인 compare는 inadmissible — 시장-의존 결정의 config-우회 재라벨링을
  **부분 봉인**. **완전 봉인은 D-E2 Snapshot provenance**(RFC-004 §9:242-244) 소유(정직 명기). in-process typed
  경로에서도 이 AST 검증은 수행(escape-checker `analyze`와 무관·순수 구조 walk).
- **정직 한계**: in-process-only는 슬라이스가 escape-checker seam을 **실증하지 않음**을 뜻한다 — 직렬화 경로의
  escape-safety를 슬라이스가 주장하지 않는다(over-claim 금지·시리즈 교훈). §9 not-slice-1에 명기.

---

## 4. Execution Coordinator 시퀀서 계약 (하중 안전 콘텐츠)

### 4.1 시퀀서 = 주입 stage의 순서 호출 (ADR-002-002 §11 19-step)

emit된 Proposal(§3.4 종료 — no-action/degraded면 시퀀서 미진입)은 §1.3의 19-step을 **순서대로** 통과한다. 시퀀서는
각 step을 **주입 stage 인터페이스**(Protocol)로 호출한다:

- 각 stage = `(입력) -> StageVerdict`. StageVerdict는 stage 고유 verdict 타입(ioc `OrderConformanceProof`·venue
  `OrderAdmissibilityDecision`·rcl `CapacityVector` 등 — §0.3 계약-타이핑 edge)을 **positive-admit 판정**으로 래핑.
- **stage 구현 소스 3종**(§0.4): 순수 available 술어(ioc/venue/cur 등)·provisional stand-in(approval/ARA/AFG/RCL)·
  D-E4(send). 시퀀서는 **어느 소스인지 모른다**(주입) — 이것이 백/paper/test-double 패리티(D5·§12)의 기반.
- **동일 시퀀서·동일 순서**를 백테스트 이벤트와 paper 이벤트가 공유(엔진 §3-2). 순서는 ADR-002-002 §11 정본
  (RFC-005 §7:192 SHALL NOT reorder/abridge — §1.3).

### 4.2 fail-closed 배선 (positive-admit·UNKNOWN-restrictive·None/deny/missing → 중단+기록)

**이것이 시리즈가 겨누는 지점**("fail-open은 배선에 산다"·엔진 §2:45-47). 시퀀서 진행 규칙:

1. **positive-admit gate(양성 identity·§6).** 다음 step으로 진행하는 것은 **오직** 현 stage verdict가 **명시
   admit**(`verdict is ADMIT` / 해당 stage의 positive 판정 술어 True)일 때뿐. `verdict is not DENY` 류의 음성 게이트
   **금지**(None·미지 verdict에 fail-open). venue의 positive-polarity 플래그(`is True`·venue/__init__:42)는 이 형.
2. **deny/None/missing → 즉시 중단.** 어떤 stage든 admit이 아니면(deny·None·미충족·예외) **시퀀스 중단·send 금지·
   restrictive 종단(no-send)·중단 사유 증거 기록.** RFC-002 §10.8:761 "reject … when any required fact is missing,
   stale, conflicting, or unverifiable"의 시퀀서 층 미러.
3. **UNKNOWN은 restrictive이되 특별하다.** RFC-005 §11:325-327·RFC-008 §10:347-350·ADR-002-002 INV-006:174 —
   UNKNOWN은 rejection도 safe-to-retry도 아니고 **worst-credible bound로 exposure를 소비**. ⇒ send 경계(step 15-19)
   에서의 UNKNOWN/timeout(`EGRESS_RESULT`)은 단순 "깨끗한 중단"이 아니라 **provisional reservation을 POTENTIALLY_LIVE로
   보수 유지**(§2.4)·blind resubmit 금지(RFC-002 §9.1:574). ADR-002-002 INV-005:168 — `SEND_STARTED` 후 크래시는
   capacity release 금지.
4. **degrade 접기(§3.4)는 시퀀서 진입 전에 이미 no-action으로 접혀** 시퀀서를 시작하지 않는다(2중 방어).

### 4.3 Coordinator 자체 규율 (SHALL NOT — RFC-002 §9.1·§10.7)

Coordinator(=D-E1)는 **순수 요청자/시퀀서**이며 **어떤 권위도 보유하지 않는다**:

- **SHALL NOT mutate capacity**(RFC-002 §9.1:557 — "Execution Coordinator SHALL NOT mutate capacity"·RCL이 유일
  serialization/mutation 권위). 시퀀서의 RCL step 호출은 **요청**이지 mutation 아님.
- **SHALL NOT infer missing-ack = rejection**(RFC-002 §10.7:722). §4.2 규칙 3의 규범 원천.
- **SHALL NOT invent/default/normalize/round/repair broker-command fields**(RFC-002 §10.7:724·RFC-005 §7:210-213).
  candidate 구성은 ioc(ADR-002-020) 소유·시퀀서는 digest 보존만.
- **직접 행위 = step 12 attempt request 생성뿐**(ADR-002-002 §11.3:599 — bound to exact conformance proof +
  Action Flow Permit). 그 외 전부 요청/시퀀싱. **attempt-id 결정론 파생(MAJOR-3·비-RNG)**: attempt-id =
  conformance-proof digest + Action Flow Permit id + 주입 reference 좌표(§2.3)의 **content-addressed 파생**(uuid4/
  timestamp nonce 금지 — RFC-003 §10:360-363 recorded-seed·replay identity 보존; 동일 (proof, permit, 좌표) → 동일
  attempt-id·재현). tos/ 전체 content-addressing 규율 정합. RFC-002 §9.1:551 "Propose … Decision Service … **None** [state
  authority]"·:565 "Create transmission attempt … Execution Coordinator"·:566 "Transmit … Execution Coordinator
  **requests** … Broker Egress final"·:574 "Retry … UNKNOWN … SHALL NOT cause blind resubmission."
- **RFC-005 §12:346-377 11 SHALL NOT 전수 미러**: 시퀀서는 originate/approve/widen(352)·mutate RCL(354)·construct
  command(356)·issue/reuse Transmission Capability(358)·bypass currentness(360)·treat timeout=rejection(362)·
  create aggregate exposure via retry(364)·exceed AFG budget(366)·assert venue/session(368)·self-classify
  protective(371)·TCA as authority(373) 중 **어느 것도 하지 않는다.** 각각 소유 stage에 위임.

### 4.4 provisional 권위 stand-in (approval·ARA·AFG·RCL — 비권위·닫는 EV 0)

step 4·6·8-10·13-14는 슬라이스 #1에서 **비권위 provisional stand-in**이다:

- **정의**: stand-in은 해당 stage의 verdict **타입**을 실 available 술어로 산출하되(예: are decision 술어·rcl
  CapacityVector 산술) **상태 있는 권위 행위**(실 독립 승인·linearizable RCL commit·Transmission Capability 발행)는
  수행하지 않는 in-memory·비권위 대역이다.
- **⚠ at-most-one retention(MAJOR-1·SAFE-021 provisional 미러·핵심)**: provisional RCL/reservation stand-in은
  **미해소 outstanding POTENTIALLY_LIVE reservation을 retain**하고, **동일 scope(account+instrument)의 겹치는
  economic-effect 요청을 capacity-stage에서 deny**한다. ⇒ send 요청↔`EGRESS_RESULT`(또는 timeout) 사이에 2차
  `DECISION_TICK`가 와도(§2.1(iv)) 2차 flow는 capacity-stage에서 restrictive-deny되어 겹치는 노출을 만들지 못한다
  (SAFE-021 At-Most-One Exposure Effect의 provisional 미러·RFC-005 §11:319-343·§12 item 7 :364-365·ADR-002-002
  INV-006:174). **bound = `MAX_unresolved_send_per_scope 1`**(register §3:90·§8). 이 deny는 **producer-local
  counter로 headroom을 만드는 것이 아니라**(RFC-002 §9.1:558 "SHALL NOT create headroom" 정합) reservation projection의
  restrictive-only 관측이다. **정직**: 이 provisional retention은 실 linearizable ledger의 fencing-epoch/CAS 원자성을
  주장하지 않는다 — 동시성 권위는 여전히 RCL 런타임 이연.
- **왜 EV를 닫지 못하나**: 실 RCL은 유일-writer·fencing-epoch·CAS linearizable ledger(ADR-002-002 §8.1:403·§8.3:434·
  §8.4:449)여야 한다. provisional in-memory reservation은 이 semantics를 **주장하지 않는다** — 동시성·크래시-복구·
  epoch fencing 미실현. ⇒ ADR-002-002의 capacity 관련 INV(INV-004:164 No Transmission Without Capacity·INV-006:174·
  INV-008:187 Stale Authority Cannot Mutate)를 **실증하지 못하고**, 따라서 capacity/approval **EV를 닫을 수 없다**
  (§1.1). 슬라이스는 **호출 순서·바인딩 전달·fail-closed 중단만 실증**.
- **경계 정직**: 각 stand-in은 코드/증거에서 **NON-AUTHORITATIVE PROVISIONAL**로 라벨. 실 런타임(are Authority·afg
  Governor·RCL ledger·iap 독립 승인자)은 **각자 미래 owning-runtime 설계**(are/__init__:17-18·afg/__init__:28-29).
  본 문서는 그 인터페이스 slot만 확정하고 실 구현을 이연.
- **검토·기각 대안**: (A) 권위 step을 슬라이스에서 **생략**(decision→바로 send) — 기각: Normal Commitment Flow가
  "every child order runs the full machinery"(RFC-005 §6:170-172)·생략은 배선 실증(슬라이스의 유일 가치)을 무효화.
  (B) 실 RCL ledger를 슬라이스에서 구현 — 기각: ADR-002-016 ENGINE(register G5)·ADR-002-002 §8 런타임은 슬라이스
  범위 밖·수개월 작업(엔진 §2). stand-in이 정직한 중간.

### 4.5 send 경계 핸드오프 → D-E4 (주입 transmit 인터페이스)

- step 15-19는 D-E4(Broker Egress Gateway)다. 시퀀서는 **주입 transmit 인터페이스**(`(bound attempt) ->
  EgressResult`)를 호출하고 즉시 반환(D5 — 코어는 블로킹 network에 안 매임). 결과는 `EGRESS_RESULT` 이벤트로 재주입
  (§2.2).
- **transmit 인터페이스는 추상 타입**(EgressResult)으로 타이핑 — brokercap·egress·cur의 concrete 타입은 **D-E1
  closure에 미포함**(§0.3·§10.2 공격 지점). D-E4가 그 구현에서 brokercap `environment_binding_ok`(non-live-test
  바인딩·register §3:88)·egress QCC·cur currentness·network를 소유.
- RFC-002 §10.8:763 — Egress Gateway는 "final live-transmission enforcement point"이며 "SHALL NOT expose a
  general-purpose live-order method to strategy, research, simulation, **backtest**, or operator-interface
  components." ⇒ **백테스트(D-E3)는 이 transmit 인터페이스에 fill-model 대역을 주입**(실 send 아님)·paper(D-E4)는
  실 paper 계좌 송신 대역 주입. **동일 시퀀서·다른 주입**(패리티).
- **⚠ 시퀀서 fail-closed 보장 범위(item-7·정직 경계)**: §4.2 fail-closed 보장은 **step 1-14**(결정→attempt binding→
  Transmission Capability slot)까지다. **step 15-19(Send Boundary — final-egress currentness·QCC·single-use
  capability·actual-outbound 대조)는 구성상 전부 D-E4 이연**(RFC-002 §10.8:741-759 verify 목록·§9.1:567 currentness).
  ⇒ D-E1은 send 경계 자체의 안전(currentness/QCC/single-use)을 **보장하지 않는다** — 그 enforcement는 D-E4 Broker
  Egress Gateway 소유(§10.2-3).

---

## 5. seam 지도 (REUSE / WIRING / NEW / 주입 + 소유권 분할)

### 5.1 REUSE (기구현·재저작 금지 — 자체 실측 file:line)

| seam | 심볼(file:line) |
|---|---|
| 결정 파이프라인 evaluator | dsl: `evaluate`(determinism.py:238)·`build_environment`(:88)·`EvaluationResult`(:81)·`Proposal`/`build_proposal`/`build_flat`(proposal.py:179/244)·`NoActionOutcome`(outcome)·`DecisionKind`(vocabulary.py:137) — dsl/__init__:70-98 |
| bounded-evaluation degrade | dsl: `resolve_bound`(bounds.py:40)·`degrades_to_no_action`(:70)·`select_outcome`(:82)·`BoundState`(:32) |
| Decision Context | capsule: `DecisionContextCapsule`(capsule.py:170)·`CriticalInputSnapshot`·`FieldState` — capsule/__init__:46-53 |
| 주입 time 좌표·freshness | time: `freshness_verdict`(:66)·`snapshot_age_admissible`(:71)·`session_open_positively`(:70)·`HealthState`(:38) — clock-free(time/__init__:7-9) |
| 인과 순서 | ordering: `compare_order`(ordering/__init__)·canonical substrate |
| provisional 증거 sink | evidence: `SafetyEvidenceEnvelope`(:54)·`ReplayCapsule`(:97)·`compute_replay_result`(:99) — 완전 Evidence Store 런타임(ADR-002-016) 아님·§9 |

### 5.2 계약-타이핑 edge (19-step stage verdict 타입 — 로직은 주입)

ioc: `compile_command`/`command_conforms`/`OrderConformanceProof`/`mutation_fence_holds`(ioc/__init__:76-104)·
`EconomicEffectEnvelope`=rcl `CapacityVector`(:34-35 — 유일 ioc→rcl edge) · venue: `session_phase_admits`/
`order_shape_admissible`/`OrderAdmissibilityDecision`(venue/__init__:112-141) · rcl: `CapacityVector`(:84) ·
are/afg: decision 술어(provisional stand-in 대역) · cur: currentness 술어. **stage 로직은 주입**(§4.1) — 이 타입들은
시퀀서 계약의 정밀 타이핑용.

### 5.3 NEW (owning runtime — negative-grep 부재 확정·§0.5)

`tos.engine` 신규: (1) 이벤트 코어(§2)·(2) 결정 파이프라인 오케스트레이터(§3)·(3) 19-step fail-closed 시퀀서(§4)·
(4) provisional core state projection(§2.4)·(5) provisional 증거 sink 어댑터(§5.1). 전부 부재(`ls
tos/src/tos/*engine*` → 0·§0.5).

### 5.4 sibling edge 정책 + forward seam

- **sibling edge**: 엔진은 통합자라 **다수 edge**(§0.3) — 이는 정상(통합의 본질). 단 **로직 결합은 주입으로 최소화**
  (§4.1)·타입 edge만 직접. `tos.egress`(ADR-002-013 QCC 커널) **잠식 금지**(서베이 §7-4) — 엔진은 egress를 import
  안 함(send는 D-E4 주입 인터페이스 너머·§4.5).
- **forward seam**: (a) orthostate(core state 권위·§2.4)·(b) D-E2 Snapshot 값 표면(§3.2)·(c) D-E4 transmit·
  brokercap·egress·cur(§4.5)·(d) 실 RCL/ARA/AFG/iap 런타임(§4.4). 전부 **구현 시점 디스크 재실측**(병렬 트랙 착지
  가능·서베이 §6-2).

### 5.5 소유권 분할표 (D-E1 vs D-E2/3/4 — 최대 함정·§12 상세)

| 관심사 | D-E1 소유 | 이연 소유 |
|---|---|---|
| evaluator | 구동(호출 배선) | — (dsl 기구현) |
| Critical Input 값 표면 | seam **계약**(§3.2) | **D-E2** 값 표면·resolver |
| market feed | — | **D-E2** |
| 백테스트·fill·cost-realism·차등 오라클 | transmit 인터페이스 slot | **D-E3** |
| order construction·send·brokercap·egress·cur·network | transmit 인터페이스 slot·시퀀서 순서 | **D-E4** |
| approval·ARA·AFG·RCL 원자 commit | 시퀀서 stage slot·provisional stand-in | 각 **미래 런타임** |
| 이벤트 코어·시퀀서·결정 파이프라인·core state | **전부** | — |

---

## 6. fail-closed 규율 + 극성 (시리즈 술어 규율의 오케스트레이션 적용)

- **positive-admit(양성 identity).** 진행 게이트는 `verdict is ADMIT`(명시 positive)만. `is not DENY`류 음성 게이트
  금지(§4.2 규칙 1). 이벤트 kind·레지스트리 키·stage verdict 전부 positive membership.
- **음극성 bool|None은 `is False`만**(시리즈 교훈·`is not True` 금지). 음극성 플래그(예: `is_stale`·`is_revoked`·
  degraded 계열)를 소비할 때 `flag is False`만 "affirmatively-safe"로 읽고 None·True는 restrictive. **주의**: venue의
  **양극성** 플래그(`is True`/`is not True`·venue/__init__:42)는 positive-polarity라 정합(양극성 admit은 `is True`·
  restrictive 여집합 `is not True` 합법). 극성별 규율은 stage verdict 소비 지점마다 명기(§11 canary).
- **UNKNOWN-restrictive + 보수 capacity 유지.** §4.2 규칙 3 — worst-credible 소비(ADR-002-002 INV-006:174)·blind
  resubmit 금지·POTENTIALLY_LIVE 보수(INV-005:168).
- **degrade fold.** §3.4 — degradation → NO_ACTION + 구별 기록(구조 파생·정직).
- **∅ 양방향.** explicit-empty(예: 명시적 no-strategy registry) vs missing(레지스트리 자체 부재)을 구분. missing은
  fail-closed(무평가), explicit-empty(등록된 0-전략 심볼)는 정의된 no-action. core state의 UNKNOWN 멤버는 명시(누락
  아님·§2.4).
- **구조 파생 > 자기신고.** 디스패치 키(§3.3)·outcome 바인딩(§3.1 RecordedInputSignature)·degrade 사유 — 전부 구조/
  아티팩트 파생. **⚠ (Gap-1) RecordedInputSignature는 reproducibility(동일 입력→동일 outcome)를 주고 distinctness
  (다른 bar→다른 id)는 주지 않는다** — 후자는 D-E2 distinct-digest 의존·§7.2-5·§9-9 이연.

---

## 7. firewall allowlist + property test 타깃

### 7.1 import-closure allowlist (`test_engine_import_closure.py` 예정)

- fresh interpreter에서 `tos.engine` 전 submodule import 후 top-level `tos.*` set ⊆ §0.3 allowlist. **광폭 통합자**
  이므로 allowlist가 큼(정상·§10.2). planted-leak canary: `shared.config`·`shared.execution`·`tos.egress`(잠식
  금지)·미래 sibling `tos.brokeradapter`가 새어들면 실패.
- 추가 assert(설계 #1 §0.3): 어떤 engine 소스도 `os.environ`/`getenv`·network stdlib·동적 escape(`exec`/`eval`/
  `compile`/`importlib`) 미참조. **wall-clock 미참조**(§2.3 — `time`/`datetime` 직접 호출 negative-grep canary).
- **결정론 canary(MAJOR-3)**: `random`/`secrets`/`uuid`/`hash`-seed(비결정 nonce) 미참조 negative-grep — step-12
  attempt-id가 content-addressed(§4.3)임을 강제·uuid4/nonce 도입 시 replay identity 파괴를 canary가 검출(RFC-003
  §10:360-363). (맥락: 현 tos/ 비테스트 코드 uuid/random/now 0건 실측 — 위험은 엔진 신규 glue 한정.)

### 7.2 property test 타깃 (오케스트레이션 불변식 — 저작 증거·acceptance 아님)

닫는 EV 0이므로 이 테스트들은 **저작(authoring) 증거**다(dsl/__init__:24-26 동형 정직). 타깃:

1. **시퀀서 fail-closed 전수**: 임의의 stage가 deny/None/UNKNOWN/예외 반환 시 시퀀스가 **그 지점에서 중단·send 미발생·
   중단 사유 기록**(§4.2). positive-admit 게이트 뮤테이션(`is ADMIT`→`is not DENY`) KILLED.
2. **UNKNOWN-restrictive**: send 경계 UNKNOWN/timeout → POTENTIALLY_LIVE 보수 유지·no blind resubmit·capacity
   미해제(§4.2 규칙 3·INV-005/006).
3. **degrade fold**: bound exhausted → NO_ACTION + 구별 degradation 증거·commitment flow 미진입(§3.4).
4. **디스패치 구조 파생**: 키↔전략 선언 instrument 불일치 등록 거부·event↔strategy instrument 불일치 무평가(§3.3).
5. **결정 파이프라인 재현성(reproducibility, same→same)**: 동일 (registry, event) → byte-identical outcome·
   RecordedInputSignature(§3.1·RFC-003 §10:345-348). 동기·결정론(D5) 실증. **⚠ 범위 축소(Gap-1)**: 이는
   **reproducibility(동일 입력→동일 출력)**이지 **distinctness(다른 bar→다른 id)가 아니다** — per-bar identity
   distinctness(스파이크 G13: 같은 Snapshot digest 공유 두 bar가 한 proposal_id로 붕괴)는 **D-E2 distinct-digest
   보장 의존·§9 이연**. G7(config_version per-bar churn 오염·스파이크 G7)은 **D1이 root 해소**(시장값이 config를
   안 거치므로 config_version이 bar마다 안 바뀜).
6. **Coordinator 무권위**: 시퀀서가 capacity mutation·command 구성·Transmission Capability 발행을 **직접 하지 않음**
   (RFC-002 §9.1:557·§10.7:724 미러·주입 stage만 호출) — AST/호출 canary.
7. **닫힌 이벤트 어휘**: 미지 event kind → fail-closed 오류(silent drop 아님·§2.2).
8. **env-구성 admission(v1.1 재정의·MAJOR-2)**: **outcome-게이팅 compare가 전부 const/config operand**(capsule
   operand 0)이면 admission 거부(§3.2(3)·§3.5·`DecisionPolicy.rules` AST walk). ≥1 capsule operand 강제·부분 봉인·
   완전은 D-E2 provenance.
9. **at-most-one 재진입 deny(MAJOR-1)**: 미해소 POTENTIALLY_LIVE reservation 존재 시 동일 instrument 2차 flow의
   **capacity-stage deny**(§4.4·SAFE-021 provisional 미러). send 요청↔`EGRESS_RESULT` 사이 2차 `DECISION_TICK`가
   겹치는 노출을 못 만듦을 실증. `MAX_unresolved_send_per_scope 1` 미준수 뮤테이션 KILLED.

---

## 8. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

엔진은 **어떤 수치도 하드코딩하지 않는다**(RFC-005 §13:386 "SHALL NOT be hardcoded"·시리즈 규율). 소비 수치는 전부
주입 bound/INSTANCE:

| 수치 | 소유 | 현상태(register 실측) |
|---|---|---|
| DSL 평가 time/resource budget(`budget_steps`·§3.4) | DCE-INV-007 | **키 자체 부재·신설 대상**(register §8-1:223 `strategy-dsl:540-546`) → provisional 값 배선·승인 전 provisional 증거 |
| snapshot freshness/staleness 임계(§2.3) | trustworthy-time bound 계열 | **다수 신설 대상**(register §8-1:204-211)·`MAX_clock_drift_ppm 200`(register §3:90 확정 5중 1) provisional |
| `MAX_unresolved_send_per_scope 1`(**at-most-one 재진입 deny bound**·§4.4) | limits(register §3:90) | **RCL capacity + egress single-use가 집행**, 코어는 POTENTIALLY_LIVE projection을 restrictive-only 관측(producer-local counter로 headroom 생성 아님·RFC-002 §9.1:558) |
| `MAX_normal_capability_age_ms 1000`(capability age·send 경계) | limits(register §3:90) | 확정 5중·주입 소비(D-E4) |
| non-live-test 환경 바인딩 | brokercap INSTANCE(P0-2·D-E4) | `environment: non-live-test`(register §3:88 유일 확정 scope)·나머지 KIS 값 트랙 d |

⇒ 슬라이스 소비 bound 다수가 null/미신설(register §8-1) → **provisional 값 배선·산출 provisional**(§1.1). bound 승인은
P0-1(운영자·Bounds-Approver).

---

## 9. Phase-0 / not-slice-1 체크리스트 (닫지 않음·후속 게이트)

**본 계약이 실현 지침을 제공(슬라이스 #1)**: 이벤트 코어·결정 파이프라인 오케스트레이션·19-step fail-closed 시퀀서·
5 핵심 결정·provisional core state·property test 타깃(저작 증거).

**닫지 않음(명시 이연·후속)**:
1. **정식 EV-L2 PASS** — G2 canonicalization·P0-1 bounds·P0-3 독립 리뷰어·정식 실행·독립 서명 선결(register §4:108·
   §6:132·§2 사슬). 슬라이스 산출은 EV **후보** 아님·provisional(§1.1).
2. **실 RCL/ARA/AFG/iap 권위 런타임**(§4.4) — 각 미래 owning-runtime 설계.
3. **완전 Evidence Store 런타임**(ADR-002-016 ENGINE·register G5) — 슬라이스는 provisional sink(§5.1).
4. **직렬화 전략 admission**(escape-checker+lowering+binding·§3.5) — 후속 사이클(seam 예약).
5. **D-E2 Critical Input 값 표면**(§3.2)·**D-E3 백테스트/fill/cost-realism**·**D-E4 send/egress/brokercap**(§12).
6. **비동기 I/O·라이브 실주문**(§2.1·GOV-001 제3행위).
7. **orthostate core state 권위·crash-recovery 재조정**(J3·§2.4)·**fault-injection 시나리오**(J1-J5·서베이 §5·EV-L2+
   트랙 b — 접합 위치만 표기).
8. **DCE-INV-007·freshness bound 신설·승인**(§8·register §8-1).
9. **per-bar identity distinctness(스파이크 G13·Gap-1)** — 같은 Snapshot digest 공유 두 bar의 proposal_id 붕괴 방지는
   **D-E2 distinct-digest 보장 의존**. 슬라이스는 reproducibility만 실증·distinctness 이연(§7.2-5).
10. **Coordinator positive 인증 게이트(Gap-2)** — RFC-002 §10.7:713-714 "verify current Safety Authority"·"verify
    live authorization". 슬라이스 non-live-test라 정당 이연이나 **명시 이연으로 승격**: Safety Authority epoch 검증·
    live authorization은 각 런타임(RFC-002 §10.11 Safety Authority·§10.13 Live Authorization) 착지 후 stage로 배선.

---

## 10. 명명 결정 + 리뷰어 공격 지점

### 10.1 명명 `tos.engine` (운영자 판단 지점)

- **선정**: `tos.engine` — owning-runtime(이벤트 코어 + Execution Coordinator) 통합자. negative-grep 충돌 0·미예약
  (§0.5). runner-up: `tos.coordinator`(Execution Coordinator 직결이나 이벤트 코어·결정 파이프라인 포괄 부족)·
  `tos.runtime`(과광범·모호). **`tos.egress` 잠식 절대 금지**(서베이 §7-4 — QCC 커널)·D-E4의 `tos.egressgw`와도 구분.
- **register prefix 부재**: ADR-002 시리즈와 달리 엔진은 ADR-EV register 행이 없다(Part-2/3 RFC 실현·닫는 EV 0). 이는
  명명이 register CSV 배제 목록의 soft load-bearing(SIR/WDR 선례)을 **갖지 않음**을 뜻함 — `tos.engine`은 순수 설계
  선택. 운영자 확정 지점.

### 10.2 리뷰어 공격 지점 (선제 반론)

1. **"광폭 import-closure = firewall 위반 아닌가?"** — 반론: 아니다. firewall(설계 #1 §3.2/§3.3)은 `shared.*`·
   `os.environ`·network·동적 escape를 막지 `tos.*` 내부 edge 수를 제한하지 않는다. 엔진은 **통합자**라 커널 상위집합
   closure가 본질(§0.3). allowlist는 여전히 부분집합·canary 유효(§7.1). 오히려 통합자를 **인위 분할**하면 seam이 늘어
   fail-open 표면 증가.
2. **"provisional stand-in이 실 안전을 준다고 오독될 위험."** — 반론: §1.1·§4.4가 **NON-AUTHORITATIVE·닫는 EV 0**을
   최상위 선언·각 stand-in 코드/증거 라벨. 슬라이스는 **배선 실증**이지 capacity/approval 증거 아님을 반복 명기.
3. **"D-E1/D-E4 import 경계(brokercap/egress 제외)가 자의적."** — 인정+반론: 경계는 **협상 가능**(§5.4 forward seam)·
   구현 시점 재실측(서베이 §6-2). 원칙: **로직 결합은 주입 최소화**(§4.1)·send 경계는 추상 EgressResult로 타이핑해
   brokercap/egress를 D-E1 closure 밖에 둠(§4.5). 재측 결과 typed-reuse가 나으면 조정. **시퀀서 fail-closed 보장은
   step 1-14까지·step 15-19 send 경계는 전부 D-E4 이연**(§4.5 item-7 — D-E1은 final-egress currentness/QCC/single-use를
   보장하지 않음).
4. **"19 vs 12 step — 서베이와 불일치."** — 반론(재실측 승): ADR-002-002 §11이 규범 19-step·RFC-005 §7은 비규범 요약·
   §7:192 SHALL NOT reorder/abridge(§1.3). 서베이 "12"는 RFC-005 요약 계수. **정본은 19-step**.
5. **"env-구성 계약이 config relabel을 완전 봉인 못 함."** — 인정+반론: 값만으로 파생 여부 판정 불가(§3.2 (3)). 봉인은
   **conformant 경로 유일화(provenance-실린 Snapshot)+명시 계약 위반 고정**·admission의 `"config"` Critical-Input
   참조 거부(§3.5 D1↔D4)로 구조 최대. 완전 검출 불가는 정직 명기(over-claim 금지).

---

## 11. 선제 defect-class 봉합 (전 시리즈 교훈 오케스트레이션 적용)

| defect class | 봉합 |
|---|---|
| **fail-open in wiring**(엔진 §2·본 시리즈 핵심) | positive-admit 게이트·전 stage 중단 canary(§4.2·§7.2-1)·Coordinator 무권위 canary(§7.2-6) |
| **음성 게이트/극성 회귀**(#18/#22/#23/#25) | `is not DENY` 금지·음극성 `is False`·양극성 `is True`(venue) 극성별 명기(§6)·AST canary |
| **truthy-sentinel**(`is not True` 오용) | 양극성 admit만 `is not True` 여집합 허용·음극성 소비 `is False`(§6·§10.2-5) |
| **UNKNOWN 무처리/blind retry**(RFC-005 §11) | UNKNOWN-restrictive+POTENTIALLY_LIVE 보수·no resubmit(§4.2-3·§7.2-2·INV-005/006) |
| **phantom 인용**(전 시리즈) | anti-phantom §0.5·전 file:line 재실측·부재 negative-grep 병기 |
| **over-claim**(escape-safety·admissible backtest) | in-process-only escape seam 미실증 명기(§3.5)·admissible backtest 자기-disqualify 회피(§1.1·서베이 §7-2) |
| **자기신고 fail-open**(#21/#24) | 디스패치 키·outcome 바인딩·degrade 사유 구조 파생(§6) |
| **∅ vacuous/과잉거부**(#17/#26 WDR MAJOR-1) | explicit-empty vs missing 구분(§6)·registry 0-entry는 정의된 no-action·missing만 fail-closed |
| **provisional over-realization**(EGRESS #22) | provisional stand-in을 실 권위로 승격 금지·NON-AUTHORITATIVE 라벨(§4.4) |

---

## 12. D-E2/D-E3/D-E4 인터페이스 핸드오프 계약 (D-E1이 확정하는 plug 지점)

D-E1이 **선행 단독**(서베이 §6-2 Phase A)인 이유 = 이 인터페이스들을 확정해야 D-E2/3/4가 배선. 계약 slot:

1. **`DecisionContextResolver`(D-E2 구현)**: `SnapshotRef` → resolved `CriticalInputSnapshot`(값-싣는 observation·
   provenance) + reference time 좌표. `DECISION_TICK` 페이로드를 채운다(§2.2·§3.2). **D1 seam 계약 준수**(시장값=
   capsule 소스·config 아님).
2. **`Stage` Protocol 집합(주입)**: 19-step 각 stage `(입력)->StageVerdict`(§4.1). D-E4가 construction·venue·send
   stage 구현·미래 런타임이 approval·ARA·AFG·RCL stage 구현·슬라이스는 provisional stand-in.
3. **`Transmit` 인터페이스(D-E4/D-E3 주입)**: `(bound attempt)->EgressResult`(§4.5). **D-E3=fill-model 대역**(실
   send 아님·백테스트)·**D-E4=paper 계좌 송신 대역**. 동일 시퀀서·다른 주입(패리티). 결과는 `EGRESS_RESULT` 재주입.
4. **`EventSource`(D-E2 feed / D-E3 bar 재생 주입)**: 이벤트를 코어에 공급. 백테스트=역사 bar·paper=실시간 feed.
5. **`EvidenceSink`(provisional·§5.1)**: outcome·중단 사유·degradation·egress 결과를 기록. 완전 Evidence Store는 이연.

⇒ **단일 코어 = 백/라이브 패리티**의 구체: EventSource·Transmit·Stage 주입만 바뀌고 **코어·시퀀서·결정 파이프라인은
불변**(D5·엔진 §3-2).

---

## 13. Self-Check (task 요구·독립 비평 리뷰 전 자가 확인)

- [x] **닫는 EV 0·provisional 최상위 선언** — 배너·§1.1·§4.4. EV-L2 PASS 미주장.
- [x] **5 핵심 결정 판정** — env-seam(§3.2)·디스패치(§3.3)·degrade(§3.4)·admission(§3.5)·동기/비동기(§2.1). 각
      대안 검토·기각 사유·리스크 병기.
- [x] **evaluator 재작성 금지** — §3.1·§0.2-1. 주변 오케스트레이션만.
- [x] **파이프라인 오케스트레이션 = 19-step fail-closed 시퀀서** — §4·§1.3(규범 재실측 정정).
- [x] **wall-clock 금지·tos.time 주입** — §2.3.
- [x] **import-firewall(tos.* self + 통합자 광폭 allowlist)** — §0.3·§7.1.
- [x] **anti-phantom(존재/부재 양방향 grep·file:line)** — §0.5·전 인용 실측.
- [x] **음극성 `is False`·양성 identity·구조 파생·∅ 양방향·UNKNOWN-restrictive** — §6·§11.
- [x] **seam 지도(소비 패키지·file:line·소유권 분할)** — §5·§12.
- [x] **Phase-0 provisional 제약·수치 하드코딩 0** — §8·§9.
- [x] **명명 결정·리뷰어 공격 선제 반론** — §10.
- [x] **v1.1 열린-세계 배선 봉합**: 재진입 at-most-one(§4.4·§7.2-9)·admission AST 술어 재정의(§3.2·§3.5)·결정론
      canary+attempt-id 파생(§7.1·§4.3)·partial-fill(§2.2)·symbolic 예산(§3.4)·distinctness/positive-gate 이연(§9).
- [ ] **미해결(운영자/후속)**: 명명 `tos.engine` 확정(§10.1)·D-E1/D-E4 import 경계 재실측(§10.2-3)·D-E2 값 표면
      착지 여부(§3.2 provisional 봉인 해소)·bound 신설·승인(§8).

---

## 14. 요약

**tos.engine(D-E1)은 시리즈 최초의 owning-runtime 설계다** — 32 순수 커널을 배선하는 열린 세계의 첫 문서. 확정:
(1) 동기·결정론 단일 이벤트 코어(닫힌 어휘·wall-clock 금지·tos.time 주입·비권위 core state), (2) RFC-003 §7 4단계
결정 파이프라인(기구현 `evaluate` 구동·재작성 금지), (3) **ADR-002-002 §11 19-step Normal Commitment Flow의
fail-closed 시퀀서**(positive-admit·UNKNOWN-restrictive·Coordinator 무권위) — 본 문서의 하중 안전 콘텐츠, (4) 5
핵심 결정(env-seam 계약[D-E2 블록커·D1↔D4 결합]·instrument-키 구조파생 디스패치·bounded degrade 접기·in-process
admission·동기 코어), (5) D-E2/3/4 plug 인터페이스(단일 코어=백/라이브 패리티).

**정직 스코프**: 닫는 EV 0. 슬라이스는 **배선의 기계·패리티 실증**이지 결정/실행/리스크 모델 acceptance 아님 —
G2·P0-1·P0-3 미결·권위 런타임(RCL/approval/ARA/AFG) provisional stand-in(§1.1·§4.4). D-E1 코드 직접 실현 step =
Normal Commitment Flow의 1·12뿐이며, 진짜 산출은 그 사이 19-step fail-closed 시퀀서와 결정 파이프라인이다.

**재실측 발견(서베이 정정)**: Normal Commitment Flow 정본은 RFC-005 §7 요약 "12단계"가 아니라 ADR-002-002 §11의
**19 numbered step**(§7:192 SHALL NOT reorder/abridge). 시퀀서는 19-step을 정본으로 배선한다.

---

## 15. 개정 로그 (v1.1 — 2026-07-29 독립 비평 리뷰 REVISE 반영)

**평결**: REVISE(CRITICAL 0·MAJOR 3·MINOR 3·Gap 2·NIT 2). 인용 무결성 91/92(phantom 0·§0.5 규율 작동). 아키텍처
4판정·5 핵심 결정·provisional 스코프는 리뷰 지지로 **유지**. finding별 처분(전건 적용·실증 반론 0 — 전 finding이
열린-세계 배선의 정당한 미명세):

| finding | 처분 | 변경 위치 |
|---|---|---|
| **MAJOR-1** 비동기-send 재진입 중복노출·RCL retention 미명세 | 적용(전건) | §4.4 at-most-one retention 미러 신설·§2.1(iv) 위험 명시·§7.2-9 property test·§8 라벨 정정(RCL+egress 집행·producer-local no-headroom RFC-002 §9.1:558) |
| **MAJOR-2** D1↔D4 술어가 DSL 부재 속성 의존 | 적용(오케스트레이터 재정 (a)) | 술어 재정의("outcome-게이팅 compare ≥1 capsule operand"·AST walkable)·"Critical-Input-결정 operand" 문구 철회·부분 봉인 정직 명기·완전=D-E2 provenance(§3.2(3)·§3.5·§7.2-8) |
| **MAJOR-3** 결정론 canary RNG/uuid 미봉인·step-12 파생 미명세 | 적용(전건) | §7.1 random/secrets/uuid/hash-seed canary·§4.3 attempt-id content-addressed 파생(비-RNG) |
| **Gap-1** replay identity 과청구 | 적용 | §7.2-5 reproducibility(same→same)로 축소·G13 distinctness §9-9 이연·G7 D1 root 해소 명기 |
| **Gap-2** Coordinator positive 인증 게이트 암묵 이연 | 적용 | §9-10 명시 이연(RFC-002 §10.7:713-714 Safety Authority·live authorization) |
| **MINOR-1** None-instrument·VECTOR outcome | 적용 | §3.3 None-instrument 등록 거부(vocabulary.py:204-205)·§3.1 VECTOR(:143) fail-closed |
| **MINOR-2** resolve_bound symbolic·work_steps 파생 | 적용 | §3.4 symbolic 정수 회계 명시(런타임 인터럽트 아님·bounds.py:53-67)·work_steps=정적 구조 계수 |
| **MINOR-3** partial fill 표현 | 적용 | §2.2 EGRESS_RESULT payload partial-fill(RFC-005 §11:338-339) |
| **NIT-1** 인용 오프셋 2건 | 적용 | RFC-004 §9:242-243→:242-244(§3.2)·ADR-002-002 §11.4 step 15-19→:605-609(§1.3) |
| **item-7** 시퀀서 보장 범위 | 적용 | §4.5·§10.2-3 — fail-closed 보장 step 1-14·step 15-19 send 경계 D-E4 이연 명기 |

**재실측 인용(쓰기 전 재grep·anti-phantom §0.5)**: `DecisionPolicy.rules`(vocabulary.py:307)·`Rule.all_of`(:284)·
`Compare.left`/`right`(:188/:190)·`Operand.const`/`ref`(:167·`resolve_operand`:316-333)·`ADMISSIBLE_CONTEXT_SOURCES`
(:88)·`TargetSpec.account`/`instrument: str | None`(:204-205)·`DecisionKind.VECTOR`(:143)·`resolve_bound`
(bounds.py:40-67 순수 정수 비교·`COMPLETED`/`BOUND_EXHAUSTED`)·RFC-004 §9:242-244(admitted Critical Input·source/
continuity/provenance·"or side channel" :244)·RFC-002 §9.1:558(producer-local counter "SHALL NOT create headroom")·
ADR-002-002 §11.4 step 15-19:605-609·§11.3:599(unique attempt request)·INV-006:174(UNKNOWN consumes capacity)·
RFC-003 §10:360-363(recorded seed). **전건 실측 일치·MAJOR-2 DSL-부재 속성 negative-grep 확인**
(`critical.?input.?determin|is_critical` in `tos/src/tos/dsl/` = 0).
