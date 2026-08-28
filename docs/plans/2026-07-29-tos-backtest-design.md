# 설계 문서 #33 — tos.backtest: 이벤트 백테스트 하네스 + paper fill 모델 (D-E3, 수직 슬라이스 #1, provisional·닫는 EV 0건) (2026-07-29, v1.1)

> **⚖ 비준 기록**: **2026-07-29 운영자 위임 자동 비준(v1.1)** — 2026-07-29 운영자 지시(Part-2/3 설계 비준
> 위임 연장)에 따라, 오케스트레이터가 게이트 조건(독립 비평 리뷰 REVISE[CRITICAL 0·MAJOR 2] → v1.1 전건
> 처방 반영·실증 반론 0 → 오케스트레이터 재실측 스팟체크 통과[monotone yield-순서 카운터·오라클 2층
> 분해·core.py:301 주장 실측·시나리오 A·§17 개정 로그])을 검증하고 기록함. 품질 파이프라인 잔여 단계
> (구현 → 적대적 코드 리뷰 → 게이트)는 유지. ADR acceptance(EV 실행 증거)·live authorization과 무관(§1).
> 효력: Phase 1 `tos/src/tos/backtest/` 구현 착수.

> **v1.1 개정(2026-07-29, 독립 비평 리뷰 REVISE 반영 — CRITICAL 0·MAJOR 2·MINOR 2·NIT 2; 인용 실측 전건
> 정확·phantom 0·§16 재실측 5건 재검증 성립·§12.2 선제 반론 6종 SOUND 유지)**: 두 MAJOR는 반론이 선점하지
> 못한 축에서 성립 — **(MAJOR-1)** 재주입 좌표를 bar_index-결합 `2i/2i+1`에서 **드라이버 소유 전역 monotone
> yield-순서 카운터**(좌표 순서 ≡ 처리 순서)로 재정의해 엔진 전역 `_last_reference` 게이트(core.py:246·:280·
> :301 — LEDGER-halt tick도 갱신)와 정합화·next-bar 정산 허위 REVERSED 제거(§3.4·§3.6·§8-1)·**(MAJOR-2)**
> 차등 오라클을 슬라이스-1 **비-numeric 구조 배선 비교**로 축소하고 numeric-decision 비교를 **D-E2 값 표면에
> gated**로 명기(§6.2·§6.5·§7.4 (e)). MINOR/NIT 전건 반영(개정 로그 §17). **핵심 판정(B1-B5)·NIT-3 처리·
> 시나리오·6반론은 리뷰 지지로 유지.**
>
> **⚖ 비준 지위**: **위임 자동 비준 대상(2026-07-29 연장)**. 후속 파이프라인: 1차 심사 → 독립 비평 리뷰 →
> 개정 → 오케스트레이터 게이트 검증 후 "운영자 위임 자동 비준(2026-07-29 Part-2/3 연장 지시)" 기록 → 구현 →
> 적대적 코드 리뷰 → 게이트. 본 문서는 **저작 산출(초안)**이며 아직 비준되지 않았다. 서베이 §6-3(L286-298)
> 해소 주석 — "Part-2/3 설계 비준도 위임 자동비준으로 연장". **ADR acceptance(EV 실행 증거)·live
> authorization은 위임 밖 별개 게이트로 잔존.**
>
> **⚠ provisional·닫는 EV 0건 (본 문서 최상위 정직 선언 — §1.1)**: 본 슬라이스 산출은 **엔지니어링-통합
> provisional**이며 **어떤 EV-L2+ PASS도, 어떤 admissible backtest도, 어떤 전략 성과(edge)도 주장하지 않는다.**
> D-E3 백테스트는 **이벤트 코어·시퀀서 배선의 기계·패리티 실증**이지 전략 우위의 증거가 아니다. 단일-런 슬라이스
> 백테스트는 ADR-DEV-010 §8:191-192("unrepresentative population — too few decisions, a single favorable
> run")의 **disqualifier**에 원리적으로 걸리며, §8:196-197은 "it is out"(가중치 하향이 아니라 **배제**)로 규정한다.
> 따라서 본 설계는 백테스트를 **"기계·패리티 실증(mechanism/parity demonstration)"**으로 **구조 봉인**하고
> (§1.2), admissible backtest 성과 주장으로 제시하지 않는다(서베이 §7-2:311-317 자기-disqualify 회피 규율).
>
> **문서 지위**: kis_unified_sts 프로젝트 측 설계 계약. tos-spec에 대해 **non-normative**이며 RFC/ADR/템플릿/
> 프로파일/register를 **변경하지 않는다.** 본 문서는 D-E1(설계 #31·`tos.engine`)이 확정한 **단일 이벤트 코어 +
> 19-step 시퀀서**를 소비해, 역사 bar를 이벤트로 재생하고 합성 fill을 재주입하는 **백테스트/paper-fill 하네스**를
> 그린필드 `tos/src/tos/backtest/`로 실현하는 계약이다. 코드·git 커밋은 본 문서 범위 밖이다.
>
> **⚠ 코어 재저작·재인스턴스화 금지 (본 설계의 하드 제약)**: D-E3는 D-E1의 `EngineCore.run`(core.py:253-262)·
> `run_commitment_flow`(sequencer.py:278-565)·이벤트 어휘·records를 **재저작하지 않는다.** bar마다 코어를
> **재인스턴스화해 ledger를 리셋하는 우회는 금지**(§2.4 — 단일-코어 패리티 파괴·비존재 capacity headroom 위조).
> D-E3의 산출은 **주변 하네스**(EventSource·Transmit fill 모델·재주입 드라이버·시나리오·차등 오라클)뿐이다.
>
> **broker-agnostic**(project memory `tos-spec-broker-agnostic`): 본 계약의 이벤트·fill·시나리오 어휘는
> broker-agnostic이다. KIS·KRX 사실은 규범 자리에 등장하지 않으며, broker 능력은 brokercap 주입값(D-E4)으로만
> 표현한다. 본 문서는 프로젝트 설계이므로 KIS-adjacent 서술은 허용하나 tos-spec 텍스트에 넣지 않는다.
>
> **선행 문서(의존)**:
> - [설계 #31 — tos.engine 단일 이벤트 코어 + 결정 파이프라인 (v1.1, 위임 자동 비준)](2026-07-29-tos-engine-event-core-design.md).
>   D-E3가 소비하는 코어·시퀀서·이벤트 어휘·seam(§2·§4·§12)의 정본. **committed 코드** `tos/src/tos/engine/` 실측.
> - [수직 슬라이스 스코핑 서베이 (비규범)](2026-07-29-tos-engine-vertical-slice-scoping-survey.md) — §0 판정
>   3(L47-58)·D-E3 행(L53)·§7-2 자기-disqualify 규율(L311-317)·§7-5 차등 오라클(L329-332). **비규범이므로
>   규범 판정(조항 인용·seam 채택)은 본 설계가 재실측으로 수행.**
> - [엔진 완주 경로 평가 메모 (비규범)](2026-07-29-tos-engine-completion-path-assessment.md) — §3-2(:63-65)
>   단일-코어 패리티·§3-3b(:69-70) 차등 오라클·§4(:71-73) 보정 게이트(WDR deviation budget).
> - [Phase-0 인간 게이트 register (비규범)](2026-07-29-tos-phase0-human-gate-register.md) — provisional 제약 원천
>   (G2:132·§4:108·§3:88-90·§8-1:223).
>
> **규범 원천(전부 2026-07-29 자체 grep 실측·anti-phantom §0.5)**: ADR-DEV-010 §7 Admissibility Bar
> (:155-174)·§8 Disqualifiers(:178-197)·BTE-INV-001~006(:127-143)·RFC-010 §6 원칙(:183-202)·§10 한계(:301-329)·
> §11 경계(:355-372)·RFC-003 §10 결정론(:345-382)·§9.1 atomic unit(:285-339)·RFC-002 §9.1 권위 매트릭스(:557-558·
> :580)·§10.8 Egress Gateway(:761-763)·RFC-005 §9 cost(참조)·§11 UNKNOWN/partial(:325-339).

---

## 0. 이 문서가 확정하는 것 / 하지 않는 것

### 0.1 확정하는 것 (7건)

1. **패키지 명명 `tos.backtest`** (서베이 §0 L53 D-E3 행 확정·negative-grep 실측 충돌 0·§12.1). 신규 그린필드
   하네스 패키지(`tos/src/tos/backtest/`).
2. **bar → EngineEvent 변환 계약** — 순수 `Bar` 스트림을 `DECISION_TICK` 이벤트로 변환하는 **인과 스트리밍
   컨버터**·시간 좌표는 tos.time 주입(wall-clock 직접 호출 0)·좌표 배정은 monotone `OrderingEvent`(§3).
3. **결정론 paper fill 모델** — `Transmit` 인터페이스(sequencer.py:103-116)를 구현하는 **합성 EGRESS_RESULT
   생산자**. RNG 0·슬리피지/체결 규칙은 주입 파라미터·seed 규율(RFC-003 §10:360-363)은 forward seam(§4).
4. **재주입 드라이버 계약** — Transmit이 즉시 반환한 뒤 합성 fill을 `EGRESS_RESULT` 이벤트로 **동일 코어에
   재주입**하는 interleaving EventSource 제너레이터(D-E1 §2.1 단일-코어 재주입 모델 소비·§4.1).
5. **ADR-DEV-010 스코프 경계 계약** — 백테스트를 **기계·패리티 실증**으로 구조 봉인(cost-realism·no-look-ahead·
   reproducible만 realize·population/not-overfit 명시 이연·edge 미주장). 자기-disqualify 회피(§1.2).
6. **1-entry 시나리오 집합 + 리플레이 계약** — NIT-3 무해제 제약과 정합적인 단일-주문 시나리오 7종·round-trip
   명시 이연·리플레이 재현성(D-E1 §7.2-5 소비·§5).
7. **차등 오라클 계약** — `shared/backtest`를 import 없이 **out-of-tree 아티팩트 비교** 오라클로 쓰는 경계·
   비교 스코프(entry-decision 합의·PnL 아님)·deviation budget(§6).

### 0.2 하지 않는 것 (NO 목록·경계)

1. **코어·시퀀서·이벤트 어휘·records 재저작 금지.** D-E1이 출하·비준(v1.1). D-E3는 **주변 하네스만**(§0 배너·§7).
2. **bar마다 코어 재인스턴스화(ledger 리셋) 금지.** 단일-코어 패리티 파괴·비존재 headroom 위조(§2.4).
3. **fill PRICE를 엔진 projection에 주입 금지.** `EgressResultPayload`는 수량-only(records.py:186-191)·엔진
   코어는 PnL/포지션 원장이 아니다. 체결가·cost-realism은 **D-E3-로컬 fill 레코드**에 산다(§4.3).
4. **admissible backtest·edge·Sharpe/return 주장 금지.** 단일-런은 ADR-DEV-010 §8:191-192 disqualifier(§1.2).
5. **round-trip(entry→exit 2주문) 금지.** NIT-3 무해제로 슬라이스는 scope당 최대 1주문. 실 RCL release 착지 후
   (RFC-002 §9.1:557·:580·ADR-002-002 §10.1)로 이연(§2.2).
6. **D-E2 Critical Input 값 표면 하드 의존 금지.** 값 표면은 D-E2 `DecisionContextResolver`(core.py:85-105 —
   "the slot only ... does not exist yet"). D-E3는 **주입 계약 슬롯**으로 설계·provisional resolver로 슬라이스
   구동(§3.5).
7. **라이브 실주문·비동기 I/O·다피드 동시성.** `environment: non-live-test`(register §3:88)·GOV-001 제3행위 밖.
8. **bar 데이터 로딩(parquet/pandas) 내장 금지.** firewall(numpy/pandas 금지·§0.3). bar는 순수 typed data로
   **주입**·로딩은 out-of-tree(§3.1·§6.1).
9. **닫는 EV/AC 0건.** §1.1 — provisional. acceptance는 §11 후속 게이트 소관.
10. **통계적 edge·multi-symbol portfolio vector.** 서베이 OUT-4(L97-98)·OUT-5(L99-100).

### 0.3 firewall 준수 선언 (설계 #1 §3.2/§3.3에 대한 본 계약의 준수)

- **`tos.backtest`는 D-E1 통합자(`tos.engine`)의 소비자다.** 그 import-closure는 `tos.engine` closure의
  **부분집합 + 자기**여야 한다:

  ```
  {tos, tos.canonical, tos.ordering, tos.time, tos.dsl, tos.capsule, tos.rcl, tos.engine, tos.backtest}
  ```

  근거: 하네스는 `tos.engine`의 공개 표면(EngineCore·run_commitment_flow·EventSource·Transmit·records·
  standins·adapters — engine/__init__ 실측)만 소비하고, bar/fill 모델링에 canonical(digest)·ordering(좌표)·
  time(freshness 주입)·dsl(Proposal 판독)·capsule(SnapshotRef)·rcl(CapacityState 판독)를 직접 참조한다.
  **are·afg·ioc·venue·cur는 D-E3가 직접 import하지 않는다** — 시퀀서 stage 대역은 `tos.engine.standins`의
  provisional_stage_map(standins.py:116-166)와 `tos.engine.adapters` 어댑터를 **재사용**하므로(재저작 금지).
- **여전히 금지**: `shared.*` 운영 패키지·`numpy`/`pandas`/`vectorbt`·`os.environ`/`getenv`·network stdlib·
  `importlib`/`exec`/`eval`/`compile`·wall-clock 직접 호출(§4.4 canary). **`shared/backtest`·
  `shared/determinism/lookahead_guard.py`·`shared/kis`는 차등 오라클·지식 참조일 뿐 import 아님**(서베이
  §7-5:329-332·엔진 §3-3:66-70). 차등 오라클 비교는 **tos.* closure 밖 out-of-tree 검증 레인**에 산다(§6.1).
- **sibling 잠식 금지**: `tos.egress`(ADR-002-013 QCC 커널)·`tos.engine`(코어) 잠식 금지(서베이 §7-4:325-327).
  D-E3는 send를 **주입 Transmit 인터페이스 너머**로만 다룬다(실 send는 D-E4 `tos.egressgw` 소유).

### 0.4 핵심 아키텍처 판정 요지 (5개 핵심 결정 + 경계)

| # | 결정 | 판정 | 근거(요지) | 리스크 |
|---|---|---|---|---|
| **B1** | ADR-DEV-010 스코프 (§1.2) | 백테스트 = **기계·패리티 실증**으로 구조 봉인. cost-realism·no-look-ahead·reproducible(§7:159-168)만 realize·population/significance·not-overfit(§7:162-171) **명시 이연**. edge/Sharpe/admissibility 표면 **부재**(구조 파생 — 자기신고 disclaimer 아님) | §8:191-192 단일-런 disqualifier·§8:196-197 "it is out". 서베이 §7-2:311-317 자기-disqualify 회피 | admissible로 오독 시 자기-disqualify → 결과 타입에 성과 표면 자체를 두지 않음 |
| **B2** | NIT-3 무해제 (§2) | 슬라이스는 **scope당 최대 1주문**. `commit_unbound`(state.py:197-229)은 미해소 reservation 존재 시 raise·release 메서드 **부재**(state.py:22). round-trip은 실 RCL 착지 후. **다bar 백테스트는 at-most-one 봉인의 FIRING을 양성 실증** | state.py:28-29 "scope stays occupied for the lifetime". RFC-002 §9.1:557 release=RCL 전권 | 코어 재인스턴스화 우회 유혹 → **명시 금지**(§2.4) |
| **B3** | fill 모델 재주입 (§4.1) | `Transmit`(sequencer.py:103)은 `SendHandoff`만 즉시 반환·**fill은 별도 `EGRESS_RESULT` 이벤트로 재주입**. interleaving EventSource 제너레이터가 인과 순서로 tick↔egress 교직. RNG 0·결정론 | core.py:253-262 lazy `run`·§2.1 단일-코어 재주입. records.py:373-387 SendHandoff=hand-off ack | 코어 게이트는 **직전 admit 이벤트**와 비교(core.py:280·:301 — LEDGER-halt tick도 갱신) → 드라이버 yield-카운터 좌표(§3.4·MAJOR-1) |
| **B4** | fill PRICE 위치 (§4.3) | 체결가·cost-realism = **D-E3-로컬 fill 레코드**. 엔진 `EgressResultPayload`는 수량-only(records.py:186-191)·projection은 PnL 미보유. 엔진 records **미개조** | 코어는 capacity/commitment 머신이지 포지션 원장 아님(§2.4·records.py:389-409). 가격 필드 추가는 over-realization | 미래 슬라이스가 가격 projection 필요 시 `EgressResultPayload` 확장 = forward seam(§4.3) |
| **B5** | 차등 오라클 (§6) | **out-of-tree 아티팩트 비교**. 2층: 슬라이스-1=**비-numeric 구조 배선 비교**·numeric entry-decision 합의는 **D-E2 값 표면 gated**(§6.2·MAJOR-2). 순수 stdlib 비교기·deviation budget(WDR) | firewall: shared=pandas/vectorbt(§0.3)·서베이 §7-5. 슬라이스-1 tos는 numerics 굶음(§3.5) → numeric 비교 D-E2 이연 | 성과/numeric 대조로 오독 시 B1 위반 → 오라클 스코프를 구조 배선으로 봉인·numeric은 §7.4 (e) |

- **경계·provisional 정책(핵심)**: 시퀀서 stage 대역은 D-E1의 `provisional_stage_map`(standins.py) **비권위
  stand-in**(closes no EV·NON_AUTHORITATIVE_PROVISIONAL 라벨)을 재사용한다. fill 모델은 실 broker가 아니라
  **합성 대역**이다. 따라서 D-E3 산출은 **배선·패리티 실증**이며 어떤 approval/capacity/admissibility EV도 닫지
  못한다(§1.1). 이것이 §1.1 "닫는 EV 0"의 구조적 이유다.

### 0.5 anti-phantom 규율 (D-E1 §0.5·FD #27·SIR #28 상속 — 부재 주장·존재 주장 양방향 grep)

- 본 문서의 **모든 file:line 인용은 2026-07-29 자체 grep/read 실측값**이다(엔진 코드·D-E1 문서·ADR-DEV-010·
  RFC-010/003/002·서베이·register·완주 메모 전건 재실측). 스펙/코드 개정 시 행 이동 — 재사용 시 재실측.
- **부재 주장은 negative-grep 병기**: (1) `tos.backtest` 충돌 부재 — `ls -d tos/src/tos/*/ | grep -iE
  'backtest|fill|replay|harness'` → 매칭 0(§12.1). (2) `EgressResultPayload`에 fill-price 필드 부재 —
  records.py:186-191 필드 열거(instrument_key·attempt_id·kind·filled_quantity·remaining_quantity·reference)에
  price 없음(§4.3). (3) state.py에 release/free/clear 메서드 부재 — state.py:22 "No release path at all"·
  `grep -n 'def release\|def free\|def clear' state.py` → 0(§2.1). (4) `Proposal`에 절대 가격/주식수 부재 —
  proposal.py:120-135 필드에 price/shares 없음·`quantity_basis`(:128)는 "evidence, never capacity"(§4.3).
- **⚠ 재실측 발견(입력 브리프와 어긋남 — §16 보고)**: 브리프 NIT-3은 "REJECT조차 RELEASE_PENDING_PROOF·
  RELEASED 상태 자체가 없음"이라 했으나, **committed state.py는 `RELEASE_PENDING_PROOF`를 보유**(state.py:64
  PROJECTION_ORDER 말미·:83 REJECT→RELEASE_PENDING_PROOF 매핑). **부재한 것은 `RELEASED` 상태(state.py:57
  "RELEASED is absent")와 release 메서드(state.py:22)뿐.** 무해제 제약 자체는 확정·오히려 더 강함(§2.1).
- **존재 주장 실측 확인**: 인용 심볼 전부 export 표면/정의부 read 확인(engine/__init__ 공개표면·core.py:85-124·
  sequencer.py:103-135·records.py:157-230·state.py:58-333·standins.py:44-166·vocabulary.py:85-149·
  ordering/_ordering.py:49-74·proposal.py:68-135·ADR-DEV-010:127-197·RFC-003:345-382·RFC-002:557-763).

---

## 1. 범위 + provisional 선언 + ADR-DEV-010 스코프 경계

### 1.1 provisional 선언 — 왜 슬라이스 백테스트가 EV를 닫지 못하는가 (정직 스코프)

D-E1 §1.1의 세 사유 + ADR-DEV-010 disqualifier가 합류한다:

1. **G2 프로덕션 canonicalization 미결.** register §6:132 — "프로덕션 canonical serialization·digest 승인 …
   EV-L2+ 실행 전 필요." 백테스트 트레이스의 모든 digest는 비프로덕션(`ev-l1-provisional-0`).
2. **P0-1 bounds 승인·P0-3 독립 리뷰어 지정 미완.** register §4:108. 소비 bounds(§10)가 provisional.
3. **권위 런타임 부재(구조적).** stage 대역은 D-E1 `provisional_stage_map` 비권위 stand-in·fill 모델은 합성
   대역. 실 승인·실 RCL·실 broker 부재 → 배선만 실증(§0.4).
4. **⚠ 단일-런 disqualifier(D-E3 고유).** ADR-DEV-010 §8:191-192 — "unrepresentative population — too few
   decisions, a single favorable run"은 **disqualifier**·§8:196-197 "it is not 'weaker evidence' … it is out."
   슬라이스 #1의 단일-전략·단일-런은 이 바를 **원리적으로 통과 불가**(서베이 §7-2:311-313).

⇒ 슬라이스 #1 백테스트의 가치는 **배선(seam)의 기계·패리티 실증**이다(완주 메모 §2:45-47 "fail-open은 배선에
산다"·서베이 §7-3 권고 (a) L322-323). **닫는 EV = 0.** 본 문서는 "가설 증거로서의 admissible backtest"를
제시하지 않는다 — 그렇게 하면 ADR-DEV-010 §8로 자기-disqualify.

### 1.2 ADR-DEV-010 admissibility 스코프 경계 계약 (자기-disqualify 회피의 구조 봉인)

**판정: 백테스트 하네스는 ADR-DEV-010 §7 admissibility bar 5-conjunct 중 "기계-정직" 부분집합만 realize하고,
"edge-증명" conjunct은 명시 이연하며, admissible backtest 판정 자체를 산출하지 않는다.**

ADR-DEV-010 §7:157 "A Backtest is an **Admissible Backtest** only when all hold(BTE-INV-002…006)" — 5 conjunct
전수:

| # | conjunct (ADR-DEV-010 §7) | BTE-INV | D-E3 처분 |
|---|---|---|---|
| 1 | cost realism(:159-161) | INV-002(:130-132) | **REALIZE(구조)** — fill 모델이 주입 cost/slippage/impact를 적용·optimistic 금지(§4.3). 단 apparatus 정의는 RFC-005 §9·RFC-006 §11 소유(ADR §9.5:211) — D-E3는 소비만 |
| 2 | population and significance(:162-164) | INV-003 | **명시 이연** — 단일-런은 §8:191-192 disqualifier. edge 미주장(§1.1) |
| 3 | no look-ahead(:165-166) | INV-004(:137-139) | **REALIZE(구조)** — 인과 스트리밍 컨버터가 결정 입력을 컨텍스트 timestamp에 bounded·구조적 불가(§3.6) |
| 4 | hermetic and reproducible(:167-168) | INV-005(:140-143) | **REALIZE(구조)** — RNG 0·clock 0·기록 입력 재현(§5.2) |
| 5 | not overfit(:169-171) | INV-006 | **명시 이연** — 파라미터 튜닝·out-of-sample 부재(단일 시나리오) |

- **§7:173-174 bound 소비**: "Meeting the bar makes a Backtest admissible *as evidence toward a hypothesis*
  — it does not accept, promote, or demonstrate live edge." D-E3는 **bar를 meet조차 하지 않는다**(conjunct 2·5
  미충족 선언) — hypothesis-evidence 지위조차 주장 안 함·**기계·패리티 실증**에 그침.
- **⚠ 구조 봉인(자기신고 disclaimer 아님)**: 백테스트 결과 타입은 **Sharpe/return/edge/admissibility-verdict
  표면을 갖지 않는다.** "우리는 성과를 주장하지 않습니다"라는 문장(자기신고)이 아니라, **성과를 담을 필드가
  결과 구조에 부재**하도록 설계한다(구조 파생 > 자기신고·시리즈 교훈). 산출은 (a) 이벤트-흐름 트레이스, (b)
  fail-closed halt 레코드, (c) 단일-entry fill 레코드(수량·D-E3-로컬 가격), (d) out-of-tree 차등 wiring-합의
  레코드. 전부 **기계·패리티 라벨·닫는 EV 0**.
- **⚠ 하류 PnL 재구성도 하네스 주장 밖(MINOR-1)**: D-E3가 원재료(D-E3-로컬 체결가 + 주입 bar close·§4.3)를
  emit하더라도, 하류 소비자가 이로 **mark-to-market PnL을 재구성하는 것은 하네스 주장 밖**이며, 그 재구성 자체가
  **단일-런 새 백테스트로서 ADR-DEV-010 §8:191-192 disqualified**이다(성과 주장의 우회 봉인).
- **RFC-010 정합**: §6 원칙 1(:183-185) "Tests are evidence, not authority … it never itself accepts, admits,
  promotes, or authorizes"·§6 원칙 6(:200-202) "Backtests do not demonstrate live edge"·§10(:306-309) "A
  passing suite is not acceptance." D-E3 백테스트는 정확히 이 evidence-producing 역할(§11:370-372).
- **검토·기각 대안**: (A) admissible backtest를 슬라이스 목표로 — 기각: §8 자기-disqualify·서베이 §7-3 권고
  (a)는 (b) 정식 EV-L2를 나중으로 분리. (B) "약한 증거"로 제시 — 기각: §8:196-197 "not 'weaker evidence' …
  it is out"이 가중치-하향 자체를 금지.

### 1.3 조항 하중 지도 (ADR-DEV-010/RFC-010/RFC-005/RFC-003 → D-E3 Realize / Defer)

| 원천 | Realize (D-E3 하중) | Defer (명시 이연) |
|---|---|---|
| **ADR-DEV-010 §7** bar | cost-realism(:159-161)·no-look-ahead(:165-166)·hermetic/reproducible(:167-168) 구조 realize | population/significance(:162-164)·not-overfit(:169-171) — edge 증명(§1.2) |
| **ADR-DEV-010 §8** disqualifiers | look-ahead(:182-184)·optimistic-cost(:189-190)·irreproducibility(:193-194) **구조적 회피** | 자기-disqualify 유발 주장 자체(단일-런을 admissible로 제시) |
| **RFC-010 §6/§10/§11** 테스트=증거 | 원칙 1(:183-185)·4(:193-196 failure-path first-class)·§10 not-acceptance(:306-309)·§11 evidence-only(:370-372) | §11 item 8(:355-356) no test/backtest→live 경계 준수(라이브 미접촉) |
| **RFC-005 §9** cost | fill 모델이 cost apparatus **소비**(주입 파라미터) | apparatus **정의**(RFC-005 §9·RFC-006 §11 소유·ADR §9.5) |
| **RFC-003 §10** 결정론 | reproducibility(:345-348)·point-in-time snapshot/digest(:352-354) 소비 | :365-367 "Replayable is not independently recomputable"(SAFE-034 — audit-grade만·§5.2) |
| **RFC-002 §10.8** Egress | :763 "SHALL NOT expose general-purpose live-order method to … **backtest**" — fill 모델은 실 send 아님(§4.1) | §10.8 실 currentness/QCC/single-use = D-E4(§4.1) |

---

## 2. NIT-3 — at-most-one-order 무해제 제약 (본 설계의 최대 난제)

### 2.1 재실측 — 무해제의 구조 (브리프 정정 포함)

**committed `tos/src/tos/engine/state.py` 실측(2026-07-29):**

- **release 메서드 구조적 부재.** state.py:22 모듈 docstring — "There is deliberately no ``release`` /
  ``free`` / ``clear`` method." negative-grep(`def release|def free|def clear`) = 0. 근거: release는 RCL 행위
  (RFC-002 §9.1:557 "Risk Capacity Ledger is the sole serialization and mutation authority"·:558
  producer-local counter "SHALL NOT create headroom"·:580 Reconcile "SHALL NOT arbitrarily release capacity").
- **⚠ 브리프 정정(§16 보고)**: 브리프는 "REJECT조차 RELEASE_PENDING_PROOF·RELEASED 상태 자체가 없음"이라
  했으나 — **`RELEASE_PENDING_PROOF`는 존재**(state.py:64 PROJECTION_ORDER 6번째 멤버·:83
  `EgressResultKind.REJECT → CapacityState.RELEASE_PENDING_PROOF`). **부재한 것은 `RELEASED` 상태**(state.py:57
  "``RELEASED`` is **absent**, because this projection cannot release")뿐. 즉 REJECT는 상태로 표현되되(knowledge
  =REJECTED), scope는 **여전히 점유**된다(release 없음).
- **at-most-one의 기계**: `commit_unbound`(state.py:197-229)은 `admits_new_exposure`(state.py:163-177 —
  `outstanding_count < max_unresolved_send_per_scope`) False면 raise(:216-221). `_store`(state.py:181-195)는
  forward-only advance·삭제 없음. ⇒ 주입 bound `MAX_unresolved_send_per_scope 1`(register §3:90 확정)에서 **첫
  `commit_unbound` 이후 scope의 outstanding은 영구 non-None** → 후속 flow는 시퀀서 step 8
  LEDGER_VERIFICATION(sequencer.py:382-401 `AT_MOST_ONE_EXPOSURE_HELD`) 또는 step 9 재확인(sequencer.py:492-503)
  에서 **fail-closed 중단**. 결론: **scope당 commit+send는 하네스 생애 통틀어 정확히 1회.**
- **정직 귀결(state.py:28-29)**: "a slice-1 scope stays occupied for the lifetime of the projection; real
  release is deferred with the RCL runtime."

### 2.2 슬라이스가 실증하는 것 vs 실 RCL 착지 후 (정직 분리)

| 항목 | 슬라이스 #1 (D-E3) | 실 RCL 착지 후 (이연) |
|---|---|---|
| 단일 entry 주문 1건 (proposal→19-step→hand-off→fill) | **실증** — 배선·패리티·projection 전이(ACK/FULL/PARTIAL/REJECT/UNKNOWN/TIMEOUT) | — |
| 다bar에서 at-most-one 봉인 **FIRING** (bar 2+ 중복 노출 deny) | **실증(양성)** — §2.3 | — |
| fail-closed halt (stage deny/UNKNOWN/missing) | **실증** — 배선의 유일 안전 가치(완주 메모 §2:45-47·§5.1) | — |
| round-trip (entry→exit 2주문·same scope) | **불가**(§2.2) | **필요** — RCL release가 entry fill 후 capacity 해제 |
| 반복 발주 (연속 진입/청산) | **불가** | **필요** — release 경로(RFC-002 §9.1:557) |
| linearizable·fencing-epoch·CAS 동시성 | **불가** — provisional projection은 미주장(state.py:3-9) | **필요** — ADR-002-002 §8 |

### 2.3 리프레임 — at-most-one 봉인의 FIRING은 한계가 아니라 양성 안전 실증

무해제가 다bar 백테스트를 "1주문으로 제약"하는 것은 사실이나, **그 제약이 발화하는 것을 백테스트가 positively
실증**한다. bar 1에서 entry가 실현되면, bar 2+의 동일-scope proposal은 capacity-stage에서
`AT_MOST_ONE_EXPOSURE_HELD`(sequencer.py:382-401)로 **정확히 거부**된다. 이는 SAFE-021 At-Most-One Exposure
Effect의 provisional 미러(D-E1 §4.4)가 **겹치는 economic effect를 만들지 않음**을 실증하는 것 — 숨길 한계가
아니라 **테스트 시나리오 #6**(§5.1)이다. 다bar 백테스트의 정직한 산출 = (1 실현 entry) + (N−1 정확한
capacity-denial), 전부 기록.

### 2.4 코어 재인스턴스화 우회 금지 (하드 제약)

bar마다 `EngineCore`를 새로 만들어 `ProvisionalReservationLedger`를 리셋하면 scope가 매 bar 비어 반복 발주가
"되는 것처럼" 보인다. **이는 금지된다:**

- **단일-코어 패리티 파괴**: D-E1 §2.1/§12·완주 메모 §3-2:63-65 — 백테스트와 paper가 **동일 코어·동일
  시퀀서·동일 ledger 수명**을 공유해야 백/라이브 괴리가 구조적으로 줄어든다. bar별 재인스턴스화는 백테스트만의
  가짜 semantics를 만들어 paper와 어긋난다.
- **비존재 headroom 위조**: 리셋은 실 시스템에 없는 capacity headroom을 만든다 — RFC-002 §9.1:558
  "producer-local counters SHALL NOT create headroom"의 정면 위반의 하네스 층 재현. 무해제는 **실 RCL이 아직
  없다는 사실의 정직한 반영**이지 우회 대상이 아니다.
- **정합 대안(허용)**: reservation 수명이 하네스 run 전체에 걸치는 **단일 `EngineCore` 인스턴스**로 전체 bar
  스트림을 돌린다(§4.1 드라이버). round-trip이 필요하면 실 RCL release 착지를 기다린다(forward seam).

### 2.5 entry→FLAT 청산 포함 여부 (task 질문의 정면 답)

**답: 2-주문 round-trip(entry 후 FLAT 청산)은 무해제 제약과 비정합이므로 슬라이스 #1에 포함하지 않는다.** FLAT
proposal(`target_kind` 필드=proposal.py:123·값 `TargetKind.FLAT` / RFC-003 §9.1:296-298 explicit-flat=action)은
결정 파이프라인이
**정확히 생성**하나, 동일 scope에 미해소 entry reservation이 있으면 시퀀서 capacity-stage에서 **차단**된다. 두
정합 시나리오:

1. **entry-only** (ACTION proposal 1건) — §5.1 시나리오 1-4.
2. **flat-only** (FLAT proposal 1건·fresh scope) — §5.1 시나리오 7. 단일 주문이므로 무해제와 정합.

round-trip(1→2 연속·same scope)은 시나리오 #6(at-most-one FIRING)으로 **차단이 실증**되고, 실제 청산 발주는 실
RCL release 착지 후로 이연(§2.2). 이 정직 분리가 브리프 NIT-3 요구("무엇이 실증·무엇이 실 RCL 착지 후인가")의
계약이다.

---

## 3. bar → EngineEvent 변환 계약 (인과 스트리밍·time 주입·좌표)

### 3.1 순수 `Bar` 모델 + 인과 스트리밍 컨버터 (NEW)

- **`Bar`(D-E3 신규·pydantic FrozenModel)**: broker-agnostic OHLCV — `(bar_index: int, open/high/low/close:
  CanonicalDecimal, volume: CanonicalDecimal, session_token: str-opaque, ...)`. **순수 typed data**·numpy/pandas
  0. **로딩(parquet/duckdb→Bar)은 out-of-tree**(firewall §0.3) — 하네스는 `tuple[Bar, ...]`를 **주입** 받는다.
- **인과 스트리밍 컨버터**: `bars → Iterator[EngineEvent]`. bar를 **순서대로** 소비하며 각 bar에 대해 하나의
  `DECISION_TICK` 이벤트를 산출한다. 컨버터는 **미래 bar에 대한 참조를 보유하지 않는다**(prefix-only·§3.6
  look-ahead 구조 보장). fill 모델의 재주입은 이 스트림에 **교직**된다(§4.1 드라이버가 소유).

### 3.2 DECISION_TICK 구성 (capsule + TimeAdmissionInputs + OrderingEvent)

`DecisionTickPayload`(records.py:157-171) **4필드**(instrument_key·capsule·time·reference)를 채운다:

1. **`instrument_key`**(records.py:166) — 전략 `TargetSpec` 구조 파생 키(D-E1 §3.3). 단일-scope 슬라이스는 고정.
2. **`capsule: DecisionContextCapsule`**(records.py:167) — bar t의 Decision Context. 슬라이스 #1은 capsule의
   `SnapshotRef`만 바인딩(records.py:161-163 "slice #1 binds the Capsule's ``SnapshotRef`` only"·값 표면=D-E2·
   §3.5). **D-E2 forward seam**: 값-싣는 observation 표면은 `DecisionContextResolver`(core.py:85-105)가 소유.
3. **`time: TimeAdmissionInputs`**(records.py:168) — §3.3.
4. **`reference: OrderingEvent`**(records.py:170) — §3.4.

### 3.3 time 주입 (wall-clock 직접 호출 0)

- **규율**: 컨버터는 `time`/`datetime`/wall-clock을 **직접 호출하지 않는다.** `TimeAdmissionInputs`
  (records.py:125-155)의 `source_age`(:138)·`snapshot_age_bound`(:146)·`session_context`(:150)·
  `health_state`(:154) 등은 **bar timestamp에서 파생**한 주입 값이다(records.py:127-131 "a bar timestamp for a
  backtest … :mod:`tos.time` is itself clock-free"). freshness verdict는 tos.time 순수 술어가 판정(D-E1 §2.3).
- **결정론 귀결**: 백테스트의 시간은 **bar가 실어 오는 좌표**·실 clock 무관 → 리플레이 재현(§5.2)·no-look-ahead
  (§3.6)의 시간 축 구체화(ADR-DEV-010 BTE-INV-004:137-139 "bounded by the current context timestamp").
- **provisional bounds(§10)**: freshness 임계(register §8-1:204-211 신설 대상)·`MAX_clock_drift_ppm 200`
  (register §3:90 확정)는 주입 — 미승인분은 provisional 값 배선.

### 3.4 좌표 배정 (드라이버 소유 monotone yield-순서 카운터·MAJOR-1)

- **`OrderingEvent`**(ordering/_ordering.py:49-74)는 우선순위 좌표(:66-74). 백테스트는 **동일 continuity 내
  총순서**를 쓴다: `source_continuity_id`(:69) = 고정 스트림 id, `source_native_sequence`(:70) = **드라이버
  소유 전역 monotone yield-순서 카운터**(§4.1). `compare_order`(ordering/_ordering.py:86-130)의 "same
  continuity → source_native_sequence" 우선순위로 전부 **MONOTONE**(core.py:160-181 `ordering_admission`).
- **⚠ 불변식(MAJOR-1 재정의): 좌표 순서 ≡ 처리 순서.** 코어 게이트는 **트리거 tick이 아니라 "직전 admit된
  이벤트"**와 비교한다 — 단일 전역 `_last_reference`(core.py:246)를 `ordering_admission(self._last_reference,
  reference)`(core.py:280)로 비교하고 **모든 non-REVERSED 이벤트마다 갱신**(core.py:301)한다. 특히 무해제로
  LEDGER-halt하는 tick도 line 301이 handler halt(sequencer.py:382) **전에** 실행되어 `_last_reference`를
  갱신한다. ⇒ 좌표를 **bar_index에 결합하면 취약**하다(예: `2i/2i+1`에서 next-bar 정산 처리 순서 `tick_0,
  tick_1, egress_0`이면 `egress_0`=1이 `_last_reference`=`tick_1`=2보다 앞서 `compare_order(1,2)=BEFORE` →
  **허위 REVERSED halt**·core.py:281). **처방**: 드라이버가 yield하는 **모든** 이벤트(tick·egress 불문)에
  yield 시점의 전역 카운터를 순서대로 배정한다. 드라이버 yield 순서 = 코어 처리 순서 = 카운터 순서이므로,
  same-bar·next-bar 정산 무관하게 **항상 strictly-increasing → 항상 MONOTONE**. 좌표는 bar_index와 **탈동조**
  (bar_index는 fill 정산 bar 조회·오라클 정렬용으로 **별도** 기록·§4.3·§6).
- **정직**: `time_lo`/`time_hi`(:73-74) trustworthy-time 인터벌은 **좌표 순서에 쓰지 않는다**(cross-continuity
  wall-clock 미참여·ordering/_ordering.py:52-63). 순서는 yield-카운터(`source_native_sequence`), freshness는
  `TimeAdmissionInputs`로 **분리**.

### 3.5 D-E2 forward seam (값 표면·비하드-의존)

- **`DecisionContextResolver`(D-E2·core.py:85-105)**: `(capsule, *, instrument_key) → DecisionTickPayload` —
  Capsule의 `SnapshotRef`를 값-싣는 `CriticalInputSnapshot` observation(source/continuity/provenance)으로
  resolve. **이 값 표면은 아직 부재**(core.py:93-98 "The slot only … does not exist yet and is D-E2's to add")·
  RFC-004 §9:242-244 규범(시장값=admitted Critical Input·"never by unattributed fetch or side channel").
- **D-E3 비하드-의존 계약(task #5)**: D-E3는 컨버터를 **주입 resolver 슬롯**으로 설계한다. 슬라이스 #1(D-E2
  미착지)에서는 **provisional resolver**(SnapshotRef만 바인딩·값 0)로 코어를 구동 — 결정은 **기계는 돌되 실
  numerics를 굶는다**. 시장 numerics가 필요한 시나리오는 D-E1 §3.2의 **비-conformant config-relabel 채널**로만
  흐르며, 이를 **명시 provisional·§10 위반 seam으로 표기**하고 출하 계약에서 금지(D-E1 §3.2 provisional 봉인
  상속). **D-E2 착지 시 typed resolver로 교체**(구현 시점 디스크 재실측·서베이 §6-2:283-284 seam 규율).
- **공동설계(서베이 §6-2:280-282)**: D-E3는 D-E2의 capsule 출력을 소비하므로 경계 계약을 D-E2와 공동설계(D-E2
  소폭 선행). D-E3는 **무엇이 흐르는가(값=capsule 소스·config 아님)의 계약**만 확정하고 값 표면 구현을 이연.

### 3.6 look-ahead 구조 보장 (결정 입력 prefix-bounded · 결정 vs 체결 분리)

- **ADR-DEV-010 BTE-INV-004(:137-139)**: "Every indicator and input SHALL be bounded by the current context
  timestamp." **look-ahead=disqualifier**(§8:182-184).
- **구조 보장(D-E3)**: 컨버터는 bar t의 결정 입력을 **인과적으로 이용가능한 prefix(≤ t)로만** 구성한다. 컨버터는
  **미래 bar 참조를 보유하지 않으므로**(§3.1) bar t 결정에 t+1을 넣는 것이 **구조적으로 불가**. 이는 shared/
  determinism/lookahead_guard.py의 tos-네이티브 재저작(서베이 §7-5:329-332 — REUSE 아님·NEW). 완전 지표-바운딩
  enforcement는 D-E2 값 표면 소유(forward seam·§3.5).
- **⚠ 결정 vs 체결 분리(리뷰어 오독 선제 봉인)**: fill 정산은 정산 bar(t 또는 t+1)를 **정당히** 이용한다 —
  이는 **실행 현실성**(미래에 체결)이지 look-ahead(미래 데이터로 **결정**)가 아니다. 결정 입력(≤ t·look-ahead-
  free)과 fill 정산(정산 좌표)은 **엄격 분리**하며, next-bar 정산을 look-ahead로 오독하지 않도록 §4.3에 명기.
  next-bar 정산의 **인과 순서**는 §3.4 드라이버 yield-카운터가 보장(bar_index 무관 MONOTONE·MAJOR-1).

---

## 4. paper fill 모델 (결정론·RNG 0·재주입)

### 4.1 `Transmit` 계약 + 재주입 아키텍처 (핵심)

- **fill 모델 = `Transmit`(sequencer.py:103-116)**: `(AttemptRequest) → SendHandoff`. **즉시 반환**(코어는
  블로킹 network에 안 매임·D-E1 §2.1 D5). RFC-002 §10.8:763 — Egress Gateway는 "SHALL NOT expose a
  general-purpose live-order method to … **backtest**." fill 모델은 **실 send 아님**·합성 대역.
- **⚠ Transmit은 fill을 반환하지 않는다(재실측 핵심)**: `transmit(attempt)`는 `SendHandoff`(records.py:373-387
  — `accepted_for_transmission: bool | None`·hand-off ack)만 반환한다. **실 fill 결과는 별도 `EGRESS_RESULT`
  이벤트로 나중에 재주입**(sequencer.py:528-533 — `mark_potentially_live` 후 `transmit` 호출·결과는 후속
  이벤트). 따라서 fill 모델은 **두 책임**을 진다: (a) Transmit 호출 시 합성 fill을 **stage**(attempt_id·kind·
  수량·정산 좌표), (b) 하네스 드라이버가 staged fill을 `EGRESS_RESULT` 이벤트로 **재주입**.
- **interleaving EventSource 드라이버(재주입 계약)**: `EngineCore.run`(core.py:253-262 —
  `tuple(self.handle(e) for e in events)`)은 **lazy**하게 이벤트를 소비한다. ⇒ **stateful 제너레이터
  EventSource**가 (i) bar에서 `DECISION_TICK`을 yield → (ii) `run`이 `core.handle(tick)` 실행 →
  `run_commitment_flow`가 `transmit` 호출 → fill 모델이 fill을 shared staging queue에 stage → (iii) `run`이
  제너레이터에서 다음 이벤트 pull → 제너레이터가 staged fill을 pop → `EGRESS_RESULT` yield → (iv) `core.handle
  (egress)`가 `apply_egress_result`(state.py:292-333)로 projection 전이. **동일 `EngineCore.run`·동일 코어 —
  paper(D-E4)는 동일 제너레이터 표면에 실 feed를 실어 재주입**(단일-코어 패리티·core.py:108-116 EventSource
  "The core cannot tell them apart — that indistinguishability *is* the backtest/live parity claim").
- **정산 컨텍스트 바인딩**: fill 모델은 `AttemptRequest`(records.py:317-334 — attempt_id·digests만·**economics
  부재**)만 받으므로 정산 bar를 attempt에서 직접 못 읽는다. 드라이버가 각 tick yield **직전** fill 모델의
  현재-bar 정산 컨텍스트를 **동기 설정**한다(결정론·no-clock). NIT-3 at-most-one 유일성(§2.1)이 scope당 in-flight
  attempt를 1개로 보장하므로 상관은 **명료**(order book 불요·§4.5).
- **검토·기각 대안**: (A) `run` 재저작해 fill을 inline 적용 — 기각: 코어 재저작 금지(§0.2)·재주입 모델(§2.1)
  훼손·paper 패리티 파괴. (B) 정적 EventBatch(core.py:124) 사전 빌드 — 기각: fill이 코어 결정에 의존해 사전
  빌드 불가. **제너레이터 드라이버가 유일 정합.**

### 4.2 fill result kinds (결정론 규칙·전수)

`EgressResultKind`(vocabulary.py:108-124) **6멤버 전수** — 전부 **결정론 규칙**(RNG 0):

| kind | 매핑 (state.py:76-86) | 수량 필요 | 결정론 규칙(주입 파라미터) |
|---|---|---|---|
| `ACK` | ACKNOWLEDGED·capacity 불변(None) | 무(records.py:201-207) | 항상 ACK(주입 "즉시 ack" 모드) |
| `FULL_FILL` | FILLED·POSITION_CONSUMED | 유 | `Q ≤ 이용가능`이면 full(§4.3) |
| `PARTIAL_FILL` | PARTIALLY_FILLED·PARTIALLY_CONSUMED | 유 | `Q > 참여상한·volume` → filled=min(Q, cap)·remaining>0(§4.3) |
| `REJECT` | REJECTED·RELEASE_PENDING_PROOF | 무 | 주입 거부 조건(예: 가격 밴드 밖) — 결정론 술어 |
| `UNKNOWN` | UNKNOWN·capacity 불변 | 무 | 주입 "미확인" 시나리오 |
| `TIMEOUT` | UNKNOWN·capacity 불변 | 무 | 주입 timeout 시나리오(J1 — D-E1 §2.1 엣지 (i)) |

- **partial은 partial로**(RFC-005 §11:338-339·D-E1 §2.2): `EgressResultPayload._fill_shape_consistent`
  (records.py:193-230)가 **magnitude에서 partial/full을 구조 파생**(:221-229 `partial_by_magnitude =
  remaining_quantity > 0`)·label 자기신고 거부. fill 모델은 이 검증을 통과하는 payload만 생산.
- **UNKNOWN/TIMEOUT 보수(RFC-005 §11:325-327·INV-005:168)**: capacity를 `POTENTIALLY_LIVE`로 **유지**(state.py:
  84-85 → None·전이 없음)·blind resubmit 0. scope는 점유 유지(§2.1).

### 4.3 economics: 수량 Q·fill PRICE 위치 (재실측 핵심·B4)

- **⚠ 슬라이스 flow에 concrete 수량/가격 부재(재실측)**: `Proposal`(proposal.py:68-135)은 `quantity_basis`
  (:128 — "evidence, never capacity"·RFC-008 §7 L215)·`direction`(:126)·`position_effect`(:127)만 싣고 **절대
  주식수·가격 부재**. concrete 수량 파생(Order Construction·ioc/ADR-002-020 step 2)은 슬라이스 #1에서 provisional
  stand-in(standins.py — verdict shape·digest만·concrete command 아님). ⇒ **flow 어디에도 concrete 수량/가격이
  없다.**
- **수량 Q = 시나리오 파라미터(정직)**: FULL/PARTIAL이 요구하는 `filled_quantity`/`remaining_quantity`
  (records.py:189-190)는 **주입 시나리오 수량 Q**에서 나온다(flow 파생 아님 — concrete-수량 파생이 provisional
  stand-in이므로). partial/full 분기 = 결정론 함수 `f(Q, 주입 참여상한, bar.volume)`. 이 Q는 projection의
  `filled_quantity`(records.py:407)로 흘러 PARTIALLY_CONSUMED 전이를 실증하되, **"시나리오 수량"임을 라벨**.
  ACK/REJECT/UNKNOWN/TIMEOUT은 수량 불요(records.py:201-207)라 Q 없이 완전 실증.
- **fill PRICE(체결가) 위치 = D-E3-로컬(B4·구조 근거)**: **`EgressResultPayload`는 가격 필드 부재**
  (records.py:186-191 — instrument_key·attempt_id·kind·filled_quantity·remaining_quantity·reference·
  negative-grep price=0)·projection `ProvisionalReservation`(records.py:389-409)도 PnL/가격 미보유. ⇒ 체결가·
  슬리피지·impact(cost-realism)는 **D-E3 하네스의 자체 fill 레코드**(신규 pydantic 모델)에 산다·엔진 EGRESS에
  주입하지 않는다. 근거: **엔진 코어는 capacity/commitment 머신이지 포지션/PnL 원장이 아니다**(§2.1) — 가격
  필드 추가는 코어가 의도적으로 갖지 않은 표면의 over-realization·**엔진 records 개조 금지**(§0.2-1·비준된 D-E1
  경계 존중). cost-realism은 본질적으로 D-E3(백테스트 충실도) 관심사(ADR-DEV-010 §7:159-161).
- **forward seam**: 미래 슬라이스가 fill 가격을 projection에 흘려야 하면 `EgressResultPayload` 확장이 그 seam·
  본 슬라이스는 미개조.

### 4.4 결정론·seed 규율 (RNG 0·seed=forward seam·canary)

- **RNG 0**: fill 모델은 **stochastic 컴포넌트 0**·전 결정은 `(bar, 주입 파라미터)`의 결정론 함수. 슬리피지도
  주입 파라미터(예: 고정 bps·volume-비례 규칙)·**난수 draw 없음**.
- **seed 규율(RFC-003 §10:360-363·forward seam)**: 만약 미래 fill 모델이 stochastic 슬리피지를 도입하면,
  그것은 **recorded seed + recorded response에서 재현 가능**해야 하고 artifact가 **decision evidence의 일부**여야
  한다(RFC-003 §10:360-363). 슬라이스 #1 fill 모델은 완전 결정론이라 **seed 불요** — seed 슬롯은 forward seam
  (미사용)이되 **규율은 지금 명기**. (RFC-003 §10:365-367 proviso: replayable≠independently-recomputable·
  audit-grade만·§5.2.)
- **결정론 canary(D-E1 §7.1 미러)**: `tos.backtest` 소스는 `random`/`secrets`/`uuid`/`time`/`datetime`
  (wall-clock)·network stdlib **미참조** negative-grep. fill 모델에 uuid4/now 도입 시 리플레이 identity 파괴를
  canary가 검출(§9).

### 4.5 economics 상관 via NIT-3 유일성 (한계의 긍정적 활용)

`Transmit`은 `AttemptRequest`(economics 부재)만 받으므로 fill 모델이 "어느 주문의 fill인가"를 알아야 한다.
**NIT-3 at-most-one이 scope당 outstanding attempt를 1개로 보장**(§2.1)하므로, fill 모델은 "이 scope의 그
outstanding 주문"을 **유일하게** 상관한다 — **order book·매칭 엔진 불요**. 무해제 제약은 여기서 **fill 상관을
자명하게 만드는 자산**이다(한계의 긍정적 활용·구조 파생 > 자기신고).

---

## 5. 시나리오 계약 (1-entry 집합 + 리플레이)

### 5.1 시나리오 집합 (전부 scope당 단일-주문·NIT-3 정합·전수)

| # | 시나리오 | 경로 | 종단 projection / halt |
|---|---|---|---|
| A | entry → ACK (표준-단독·MINOR-2) | ACTION proposal → 19-step ADMIT → hand-off → ACK egress | knowledge=ACKNOWLEDGED(vocabulary.py:145)·capacity **불변(None·state.py:77)** — UNKNOWN(:149)과 knowledge 축 상이 |
| 1 | entry → FULL_FILL | ACTION proposal → 19-step ADMIT → hand-off → FULL_FILL egress | POSITION_CONSUMED·FILLED |
| 2 | entry → PARTIAL_FILL | 동 → PARTIAL_FILL(remaining>0·기체결분 **재요청 0**) | PARTIALLY_CONSUMED·PARTIALLY_FILLED |
| 3 | entry → REJECT | 동 → REJECT egress | RELEASE_PENDING_PROOF·REJECTED(scope 점유 유지·§2.1) |
| 4 | entry → UNKNOWN / TIMEOUT | 동 → UNKNOWN/TIMEOUT egress | POTENTIALLY_LIVE 유지·blind resubmit 0(RFC-005 §11:325-327) |
| 5 | fail-closed halt | stage deny(venue INADMISSIBLE)/UNKNOWN(approval)/missing → 중단 | hand-off 0·halt_reason 기록(§4.2 배선·완주 §2:45-47) |
| 6 | at-most-one FIRING (다bar) | bar 1 entry 실현 → bar 2+ proposal → capacity-stage deny | `AT_MOST_ONE_EXPOSURE_HELD`(§2.3 양성 실증) |
| 7 | flat-only | FLAT proposal(fresh scope) → 단일 주문 → fill | 단일 주문·round-trip 아님(§2.5) |

- **EgressResultKind 6종 전수 대응(MINOR-2)**: A(ACK)·1(FULL_FILL)·2(PARTIAL_FILL)·3(REJECT)·4(UNKNOWN·
  TIMEOUT) — vocabulary.py:119-124 6멤버 전부 시나리오/§8-2 property로 커버. knowledge 축(ACKNOWLEDGED vs
  UNKNOWN)까지 구별.
- **닫는 EV 0**: 각 시나리오는 **배선·패리티 실증**이지 approval/capacity/admissibility 증거 아님(§1.1).
- **failure-path first-class(RFC-010 §6 원칙 4:193-196)**: 시나리오 3-6은 실패/경계 경로 — "passing the nominal
  path proves nothing about failure." 시나리오 5는 **fail-closed 배선의 유일 안전 가치**.
- **round-trip 부재(§2.5)**: 1↔7 연속(same scope)은 시나리오 6으로 **차단이 실증**·실 청산 발주는 실 RCL 이연.

### 5.2 리플레이 검증 (D-E1 재현성 계약 소비)

- **재현성(D-E1 §7.2-5·RFC-003 §10:345-348)**: 동일 `(bars, 주입 파라미터, stage map, fill 시나리오)` →
  **byte-identical `EventResult` 트레이스 + 증거 레코드**. 결정론(clock 0·RNG 0·§4.4)이 자명하게 보장. 이것이
  ADR-DEV-010 §7:167-168(BTE-INV-005) hermetic/reproducible의 **구조 realize**.
- **⚠ 범위 축소(D-E1 Gap-1 상속)**: 이는 **reproducibility(동일 입력→동일 출력)**이지 **distinctness(다른
  bar→다른 id)가 아니다**. 같은 Snapshot digest를 공유하는 두 bar는 proposal_id가 붕괴할 수 있다(D-E1 §7.2-5·
  §9-9) — distinctness는 **D-E2 distinct-digest 의존**·forward seam. 백테스트는 distinctness를 주장하지 않는다.
- **⚠ audit-grade only(RFC-003 §10:365-367)**: "Replayable is not independently recomputable"·재현성은
  **audit**을 만족하지 SAFE-034 independent-recomputation을 만족하지 않는다. ⇒ 백테스트 재현성은 audit-grade·
  acceptance-grade 아님(닫는 EV 0 정합).

---

## 6. 차등 오라클 계약 (shared/backtest·firewall 준수)

### 6.1 firewall 준수 placement (out-of-tree 아티팩트 비교)

- **문제**: 완주 메모 §3-3b(:69-70)는 "shared/backtest를 차등 테스트 오라클로 사용 — 같은 데이터에 두 엔진을
  돌려 결과 대조." 그러나 firewall(전략 B·설계 #1)은 `shared/*` import를 막고(서베이 §7-5:329-332),
  shared/backtest는 pandas/vectorbt 의존(§0.3 금지).
- **판정: 차등 비교는 `tos.*` import-closure 밖 out-of-tree 검증 레인에 산다. 아티팩트-기반(해석 B).**
  - tos.backtest는 자기 트레이스(결정·halt — 순수 canonical digest)를 **직렬화 아티팩트로 emit**(pydantic→
    canonical JSON·pandas 0).
  - shared/backtest(실재 — adapter.py·ats_simulator.py·bootstrap.py·decision_harness.py 실측)는 **별도 실행**·
    자기 entry-signal 트레이스를 emit.
  - **순수 stdlib 비교기**(out-of-tree·양쪽 import 안 함)가 두 아티팩트를 bar 좌표로 정렬·합의 대조.
  - **placement**: `scripts/`(존재) 또는 전용 검증 디렉터리 — **`tos/src/` 밖·`tos/tests/` 밖**(tos/tests에
    shared import 선례 0 실측·§0.3). tos.backtest의 아티팩트 emit는 firewall-clean.
- **검토·기각 대안**: (A) 한 스크립트가 tos.backtest·shared.backtest **동시 import** — 부분 기각: 작동하나
  단일 프로세스가 양쪽 import(firewall 이야기 약화). (B) **아티팩트-기반(채택)** — 어떤 프로세스도 양쪽 import
  안 함·비교기 firewall-trivial·WDR deviation budget 재사용(§6.4)·최강 firewall 이야기. (C) tos.backtest가
  shared 참조 — 기각: firewall 정면 위반.

### 6.2 의미 비교가능성 (2층: 슬라이스-1 구조 배선 vs D-E2-gated numeric·MAJOR-2)

- **⚠ 핵심 긴장 1**: shared/backtest(vectorbt·portfolio·multi-position·EOD·PnL)와 tos.engine(단일-주문·이벤트·
  fail-closed·capacity·PnL 미보유)은 **성과/PnL 층에서 비교 불가**.
- **⚠ 핵심 긴장 2(MAJOR-2)**: **슬라이스-1 tos 결정은 실 numerics를 굶는다**(§3.5 — 값 표면=D-E2·config-relabel
  채널은 §10 위반·출하 금지). ⇒ "tos가 shared/backtest와 **동일 시장-entry 결정**에 도달하는가"라는 numeric
  비교는 **슬라이스-1에서 성립하지 않는다**(tos가 시장값으로 결정하지 못하므로). 이 비대칭을 정직 분해한다:
- **① 슬라이스-1 오라클 = 비-numeric 구조 배선 비교(하향 축소)**: numeric 판정이 아니라 **구조 배선 대응**만
  대조한다 — bar cadence ↔ `DECISION_TICK` 산출 타이밍, 파이프라인이 proposal-emit 단계 vs no-action에 이르는
  **구조 경로**(시장값 무관·저작 상수/구조로 결정되는 부분), fail-closed halt 지점. 이는 **배선 존재·순서
  정확성**의 오라클(완주 §2:45-47)이지 **"술어 입력 정확성"이나 성과 오라클이 아님**(v1.0 §6.2의 "술어 입력
  공급 정확성" 주장을 **하향**).
- **② numeric entry-decision 합의 = D-E2 값 표면에 gated(이연)**: "tos가 shared/backtest와 동일 bar에서 동일
  enter/no-action에 도달"하는 **numeric 비교는 D-E2 값 표면 착지 후**에만 가능(§3.5·§6.5·§7.4 (e)). 그때
  오라클은 첫 entry까지 bounded(NIT-3 이후 capacity 발산은 예상·실패 아님)·shared/backtest 대부분 표면
  (portfolio·EOD·재진입·PnL)은 **비교 불가·미주장**.
- **B1 정합**: ①② 어느 오라클도 **narrow 배선/결정 합의**이지 backtest-등가·성과 증명 아님 — 성과 대조로
  오독하면 §1.2 자기-disqualify. 오라클 결과 타입은 합의 boolean·발산 좌표만 싣고 **성과 표면 부재**.

### 6.3 무엇인가 / 아닌가 (닫는 EV 0)

- **이다**: wiring/authoring 증거(RFC-010 §6 원칙 1:183-185 "Tests are evidence, not authority"). property
  test(§8)와 동형의 저작 증거.
- **아니다**: EV-closer 아님·admissible backtest 아님·성과 증명 아님·acceptance 아님. **닫는 EV 0.**
- **보정 게이트와 구분(완주 §4:71-73)**: paper 체결 vs 백테스트 체결 **괴리 예산(calibration gate)**은 실 KIS
  fill 데이터를 요구하는 **미래 EV-L2+**·차등 오라클(shared vs tos)과 **별개**·이연.

### 6.4 deviation budget (WDR 개념 재사용)

- 완주 메모 §4:71-73 — "괴리 예산(WDR[ADR-002-026]의 deviation budget 개념 재사용)." 오라클 비교기는 두
  트레이스의 entry-decision 합의를 **주입 budget** 하에 판정(정확 일치 요구가 과경직하면 좌표-정렬 tolerance).
  budget은 **주입 파라미터**(하드코딩 0·§10). 첫 entry 이후 발산은 budget 밖(예상·§6.2).

### 6.5 전략 등가-표현 계약 (tos.dsl ↔ shared/backtest·MAJOR-2 (c))

오라클이 대조하려면 "같은 전략"이 양측에 표현되어야 한다. 등가 계약:

- **tos 측**: `tos.dsl` `AuthoredStrategy`/`DecisionPolicy` — 저작 상수(`config.bindings`) + (D-E2 착지 후)
  ≥1 capsule-sourced operand(D-E1 §3.2(3)). **shared 측**: `shared/backtest`의 등가 결정 규칙(예:
  `decision_harness`의 임계 비교 — 구현 시점 실측 파일).
- **등가성 성분**: (i) 동일 instrument·account scope, (ii) 동일 비교 연산자·방향, (iii) 동일 저작 임계 상수,
  (iv) **동일 지표 정의**(양측이 지표를 동일하게 계산). **①(슬라이스-1)은 (i)(ii)의 구조 등가**(compare 구조가
  1:1 매핑)만 검증 가능. **(iii)(iv)의 numeric 등가는 ②(D-E2-gated)** — tos 값 표면(capsule)과 shared pandas
  계산의 지표 산출이 동치임을 대조하는 것이 numeric 오라클의 실체.
- **정직 한계**: 지표 정의 동치는 D-E2 값 표면 없이는 tos 측이 산출 자체를 못 하므로 슬라이스-1에서 **미검증**
  (over-claim 금지). 등가 계약은 **분기점을 명시**하고 numeric 검증을 D-E2에 이연.

---

## 7. seam 지도 (REUSE / WIRING / NEW / INJECTED-forward)

### 7.1 REUSE (D-E1 기구현·재저작 금지 — 자체 실측 file:line)

| seam | 심볼(file:line) |
|---|---|
| 이벤트 코어·run | `EngineCore`(core.py:202)·`run`(:253)·`EventSource`/`EventBatch`(:108/:124)·`EventResult`(:184) |
| 시퀀서 | `run_commitment_flow`(sequencer.py:278)·`Transmit`/`Stage`/`FlowResult`(:103/:88/:119) |
| 이벤트/페이로드 records | `EngineEvent`(records.py:233)·`DecisionTickPayload`(:157)·`EgressResultPayload`(:173)·`TimeAdmissionInputs`(:125)·`EngineConfiguration`(:428) |
| core state | `ProvisionalReservationLedger`(state.py:111)·`apply_egress_result`(:292)·`CapacityState`(rcl) |
| stage 대역 | `provisional_stage_map`/`ProvisionalStandIn`(standins.py:116/:44)·sibling verdict 어댑터(adapters.py) |
| 좌표·capsule·time·digest | `OrderingEvent`/`compare_order`(ordering)·`DecisionContextCapsule`(capsule)·tos.time 술어·canonical scheme |

### 7.2 WIRING (신규 배선·술어 재사용)

bar→DECISION_TICK 컨버터(§3)·interleaving EventSource 드라이버(§4.1)·현재-bar 정산 바인딩(§4.1)·EGRESS_RESULT
재주입(§4.1)·시나리오 빌더(§5.1)·D-E3 증거 수집기.

### 7.3 NEW (owning — negative-grep 부재 확정·§0.5)

`tos.backtest` 신규: (1) 순수 `Bar` 모델(§3.1)·(2) 결정론 fill 모델(Transmit·§4)·(3) 결정론 정산/cost 모델 +
**D-E3-로컬 fill 레코드**(가격·§4.3)·(4) 시나리오 계약(§5)·(5) out-of-tree 차등 오라클 아티팩트 emitter +
순수 비교기(§6). 전부 부재(`ls tos/src/tos/*backtest*` → 0·§0.5).

### 7.4 INJECTED / forward seam (구현 시점 디스크 재실측·서베이 §6-2:283-284)

- (a) `DecisionContextResolver`(D-E2 값 표면·§3.5) — 착지 시 typed resolver 교체.
- (b) `Bar` 로더(out-of-tree·pandas·§3.1) — parquet→Bar.
- (c) 실 `Transmit`(D-E4 paper sender — **동일 seam·다른 주입**·§4.1) — 백테스트 fill 대역과 동일 인터페이스.
- (d) `EngineConfiguration` bounds(provisional·§10)·seed 슬롯(미사용·§4.4).
- (e) **numeric 차등 오라클**(§6.2 ②·§6.5) — tos 시장-decision 비교는 **D-E2 값 표면에 gated**·슬라이스-1은
  비-numeric 구조 배선 비교만(MAJOR-2).

### 7.5 sibling edge 정책

- **재저작 0**: D-E3는 D-E1 심볼을 **소비만**·재저작 금지(§0.2-1). shared/backtest·lookahead_guard.py는 **지식
  참조**·import 아님(§0.3·서베이 §7-5).
- **잠식 금지**: `tos.egress`(QCC 커널)·`tos.engine`(코어) 잠식 금지(서베이 §7-4). send=D-4 주입 인터페이스 너머.

---

## 8. fail-closed·결정론 규율 + property test 타깃 (저작 증거·acceptance 아님)

닫는 EV 0이므로 이 테스트들은 **저작(authoring) 증거**다(RFC-010 §6 원칙 1:183-185·§10:306-309 "A passing
suite is not acceptance"). 타깃:

1. **재주입 순서 정합(MAJOR-1)**: 드라이버 yield-카운터가 tick·egress에 **처리 순서대로** 좌표 배정 → 코어
   MONOTONE 소비(§3.4·core.py:160-181·280·301). **next-bar 정산 시퀀스 1개 포함**(`tick_0, tick_1, egress_0`
   순서도 MONOTONE 실증). bar_index-결합 `2i/2i+1` 좌표 뮤테이션 → 허위 REVERSED halt로 검출·KILLED.
2. **fill kind 6종 결정론 전수(§4.2)**: 각 kind → 정확한 projection 전이(state.py:76-86)·partial은 magnitude
   구조 파생(records.py:221-229)·label 자기신고 뮤테이션 KILLED.
3. **UNKNOWN/TIMEOUT 보수(§4.2)**: → POTENTIALLY_LIVE 유지·capacity 미해제·blind resubmit 0.
4. **at-most-one FIRING(§2.3·시나리오 6)**: bar 1 entry 후 bar 2+ 동일 scope → capacity-stage
   `AT_MOST_ONE_EXPOSURE_HELD`. 재인스턴스화 우회 뮤테이션(§2.4) 검출.
5. **no-look-ahead 구조(§3.6)**: 컨버터가 미래 bar 참조 보유 0(구조)·결정 입력 prefix-bounded. 미래 참조 주입
   뮤테이션 KILLED.
6. **리플레이 재현성(§5.2)**: 동일 입력 → byte-identical 트레이스. clock/RNG 도입 뮤테이션 KILLED. distinctness는
   **미주장**(Gap-1).
7. **결정론 canary(§4.4·§9)**: random/secrets/uuid/wall-clock/network negative-grep.
8. **차등 오라클 스코프 봉인(§6.2)**: 오라클 결과 타입에 성과 필드 0(구조)·첫 entry 이후 발산=예상.
9. **admissibility 표면 부재(§1.2)**: 백테스트 결과 타입에 Sharpe/return/edge/verdict 필드 0(구조 봉인).
10. **fail-closed halt 전수(§5.1 시나리오 5)**: stage deny/UNKNOWN/missing/raised → 중단·사유 기록·hand-off 0
    (sequencer.py:404-476 미러). RFC-010 §8:256-259 "Negative tests are required."

---

## 9. firewall allowlist + canary

- **import-closure allowlist(`test_backtest_import_closure.py` 예정)**: fresh interpreter에서 `tos.backtest` 전
  submodule import 후 top-level `tos.*` set ⊆ §0.3 allowlist. planted-leak canary: `shared.*`·`numpy`·`pandas`·
  `vectorbt`·`tos.egress`(잠식)가 새어들면 실패.
- **추가 assert**: 어떤 backtest 소스도 `os.environ`/`getenv`·network stdlib·동적 escape(`exec`/`eval`/
  `compile`/`importlib`) 미참조. **wall-clock 미참조**(`time`/`datetime` 직접 호출 negative-grep·§3.3).
- **결정론 canary(§4.4)**: `random`/`secrets`/`uuid`/`hash`-seed 미참조 — fill 모델·좌표 배정·attempt 상관이
  content-addressed/결정론임을 강제(RFC-003 §10:360-363).

---

## 10. 수치 → Phase-0 / INSTANCE (숫자 하드코딩 0)

fill/정산/오라클의 **어떤 수치도 하드코딩하지 않는다**(RFC-005 §13 시리즈 규율). 소비 수치는 전부 주입:

| 수치 | 소유 | 현상태(register 실측) |
|---|---|---|
| `MAX_unresolved_send_per_scope 1`(NIT-3·§2.1) | limits(register §3:90) | **확정**·주입(RCL+egress single-use 집행·코어는 restrictive-only 관측) |
| slippage/participation-cap/cost 파라미터(§4.3) | RFC-005 §9 cost apparatus(정의 소유) | apparatus 미정의(RFC-005 §9·RFC-006 §11)·**provisional 주입 값**·산출 provisional |
| freshness/staleness 임계(§3.3) | trustworthy-time bound(register §8-1:204-211) | **다수 신설 대상**·`MAX_clock_drift_ppm 200`(register §3:90 확정) provisional |
| `dsl_evaluation_budget_steps`(DCE-INV-007·D-E1 §3.4) | DCE-INV-007(register §8-1:223) | **키 부재·신설 대상** provisional |
| deviation budget(§6.4) | D-E3 오라클(주입) | provisional·WDR 개념 재사용 |
| `environment: non-live-test`(§0.2-7) | brokercap INSTANCE(register §3:88) | **유일 확정 scope**·paper 대역 |

⇒ 소비 bound 다수가 null/미신설 → **provisional 값 배선·산출 provisional**(§1.1). bound 승인은 P0-1.

---

## 11. Phase-0 / not-slice-1 체크리스트 (닫지 않음·후속 게이트)

**본 계약이 실현 지침 제공(슬라이스 #1)**: bar→이벤트 변환·재주입 드라이버·결정론 fill 모델·1-entry 시나리오·
차등 오라클·property test 타깃(저작 증거).

**닫지 않음(명시 이연)**:
1. **정식 EV-L2 PASS** — G2 canonicalization(register §6:132)·P0-1 bounds·P0-3 독립 리뷰어·정식 실행·독립 서명
   선결(register §4:108). 슬라이스 산출은 provisional(§1.1).
2. **admissible backtest / edge 증명** — population/significance·not-overfit conjunct(§1.2)·단일-런 disqualifier
   (§8:191-192).
3. **round-trip / 반복 발주** — 실 RCL release 착지 후(NIT-3·§2.2·RFC-002 §9.1:557).
4. **D-E2 Critical Input 값 표면**(§3.5)·**완전 지표-바운딩 look-ahead enforcement**(§3.6) — D-E2 소유.
5. **실 send/egress/brokercap/currentness**(§4.1) — D-E4(`tos.egressgw`).
6. **fill 가격 projection 흐름**(§4.3)·**stochastic 슬리피지 seed**(§4.4) — forward seam.
7. **paper vs 백테스트 fill 보정 게이트**(§6.3·완주 §4) — 실 KIS fill 데이터 요구·미래 EV-L2+.
8. **완전 Evidence Store 런타임**(ADR-002-016 ENGINE·register G5:135) — 슬라이스는 provisional sink(D-E1 §5.1).
9. **fault-injection 시나리오 완전판**(J1-J5·crash-recovery 재조정) — EV-L2+ 트랙·접합 위치만 표기.
10. **per-bar identity distinctness**(D-E1 Gap-1·§5.2) — D-E2 distinct-digest 의존.

---

## 12. 명명 결정 + 리뷰어 공격 지점

### 12.1 명명 `tos.backtest` (서베이 확정·운영자 확인 지점)

- **선정**: `tos.backtest` — 서베이 §0 L53 D-E3 행이 이미 지정. negative-grep 충돌 0·미예약(§0.5). **`tos.egress`
  (QCC 커널)·`tos.egressgw`(D-E4)·`tos.engine`(코어) 잠식 금지**(서베이 §7-4:325-327). "harness/replay" 접미
  대안은 서베이 확정 명명 이탈이라 기각.
- **register prefix 부재**: D-E3는 ADR-EV register 행이 없다(Part-2/3 RFC 실현·닫는 EV 0). 명명은 순수 설계
  선택·soft load-bearing 배제목록 없음(D-E1 §10.1 동형).

### 12.2 리뷰어 공격 지점 (선제 반론)

1. **"단일-런 백테스트는 ADR-DEV-010로 자기-disqualify."** — 반론: 정확히 그래서 **admissible backtest를 주장
   안 한다**(§1.2). 결과 타입에 성과 표면을 **구조적으로 두지 않아**(자기신고 disclaimer 아님) §8:196-197 "it is
   out"의 대상이 될 주장 자체를 안 만든다. 산출은 **기계·패리티 실증**(서베이 §7-2·§7-3 권고 (a)).
2. **"fill 모델이 실 체결가를 못 준다(EGRESS에 가격 필드 없음)."** — 인정+반론: 맞다(records.py:186-191). 그래서
   가격은 **D-E3-로컬 fill 레코드**에 두고 엔진 projection(capacity 머신)에 주입 안 한다(§4.3). 엔진 개조는
   over-realization·비준된 D-E1 경계 침범. cost-realism은 D-E3 관심사.
3. **"차등 오라클이 firewall 위반(shared import)."** — 반론: 아니다. 비교는 **out-of-tree 아티팩트 기반**·어떤
   프로세스도 양쪽 import 안 함(§6.1). tos.backtest는 순수 트레이스 emit만·shared는 별도 실행·순수 비교기가 대조.
4. **"next-bar fill = look-ahead."** — 반론: 아니다. look-ahead는 미래 데이터로 **결정**하는 것(§8:182-184).
   fill 정산은 미래에 **체결**하는 실행 현실성이지 결정 아님. 결정 입력(≤ t)과 fill 정산(정산 좌표)은 엄격
   분리(§3.6).
5. **"NIT-3 무해제 = 백테스트가 쓸모없음."** — 반론: 슬라이스는 **단일-entry 배선·패리티 + at-most-one 봉인
   FIRING**을 실증(§2.2·§2.3). 다bar 백테스트의 가치는 (1 entry) + (N−1 정확한 capacity-denial) — 배선 안전의
   양성 실증. round-trip은 실 RCL 이연(정직 분리).
6. **"코어 재인스턴스화로 반복 발주 되게 하면 되지 않나."** — 반론: **금지**(§2.4). 단일-코어 패리티 파괴·비존재
   headroom 위조(RFC-002 §9.1:558). 무해제는 우회 대상이 아니라 실 RCL 부재의 정직한 반영.

---

## 13. 선제 defect-class 봉합 (전 시리즈 교훈 적용)

| defect class | 봉합 |
|---|---|
| **over-claim(admissible backtest·edge)** | 결과 타입에 성과 표면 구조적 부재(§1.2·§8-9)·자기-disqualify 회피(서베이 §7-2) |
| **fail-open in wiring(완주 §2)** | fail-closed halt 전수(§5.1-5·§8-10)·재주입 순서 canary(§8-1) |
| **provisional over-realization(EGRESS #22)** | fill=합성 대역·NON_AUTHORITATIVE stand-in 재사용·닫는 EV 0(§0.4·§4.1)·가격 엔진 미주입(§4.3) |
| **자기신고 fail-open(#21/#24)** | partial=magnitude 구조 파생(records.py:221-229·§4.2)·fill 상관=NIT-3 유일성(§4.5) |
| **비결정론/RNG(리플레이 파괴)** | RNG 0·clock 0·content-addressed·canary(§4.4·§9)·seed 규율 명기(RFC-003 §10:360-363) |
| **phantom 인용** | anti-phantom §0.5·전 file:line 재실측·부재 negative-grep(price/release/충돌) |
| **∅ vacuous/과잉거부(#17/#26)** | D-E1 registry MISSING vs EXPLICIT_EMPTY 재사용(vocabulary.py:314-325)·flat-only=정의된 단일 주문(§5.1-7) |
| **firewall 누수(numpy/pandas/shared)** | allowlist canary(§9)·bar 로딩 out-of-tree(§3.1)·오라클 out-of-tree(§6.1) |
| **look-ahead 오독(next-bar fill)** | 결정 vs 체결 분리 명기(§3.6·§12.2-4) |

---

## 14. D-E2/D-E4 인터페이스 핸드오프 계약 (D-E3가 확정하는 plug 지점)

| slot | 방향 | 계약 |
|---|---|---|
| `DecisionContextResolver`(§3.5) | D-E2 → D-E3 | `(capsule, instrument_key) → DecisionTickPayload` 값 표면. D-E3는 provisional resolver로 슬라이스 구동·D-E2 착지 시 교체(공동설계·서베이 §6-2) |
| `Bar` 로더(§3.1) | out-of-tree → D-E3 | parquet/duckdb → 순수 `tuple[Bar,...]` 주입(pandas out-of-tree) |
| `Transmit`(§4.1) | D-E3 fill 대역 ↔ D-E4 실 sender | **동일 seam·다른 주입**: 백테스트=합성 fill·paper=실 paper 계좌 송신. 동일 `EngineCore.run`·동일 제너레이터 드라이버(단일-코어 패리티) |
| 차등 오라클 아티팩트(§6) | D-E3 → out-of-tree 비교기 | 순수 결정/halt 트레이스 emit·비교기는 tos.* 밖·shared/backtest와 대조 |

⇒ **단일 코어 = 백/라이브 패리티**(D-E1 §12·완주 §3-2): EventSource·Transmit 주입만 바뀌고 **코어·시퀀서·
드라이버 형태는 불변**. D-E3의 fill 대역과 D-E4의 실 sender가 **정확히 같은 Transmit 인터페이스**를 만족하는 것이
패리티의 구체.

---

## 15. Self-Check (task 요구·독립 비평 리뷰 전 자가 확인)

- [x] **닫는 EV 0·provisional 최상위 선언** — 배너·§1.1. admissible backtest/edge 미주장(§1.2 구조 봉인).
- [x] **NIT-3 정면 처리** — §2 전체. 재실측 정정(RELEASE_PENDING_PROOF 존재·RELEASED 부재·§2.1·§16). 실증 vs
      실 RCL 착지 후 정직 분리(§2.2)·리프레임(§2.3)·재인스턴스화 금지(§2.4)·entry→FLAT 답(§2.5).
- [x] **ADR-DEV-010 스코프 경계** — §1.2 5-conjunct 전수·구조 봉인(성과 표면 부재)·자기-disqualify 회피.
- [x] **bar→EngineEvent 변환·time 주입·좌표** — §3(인과 스트리밍·wall-clock 0·monotone OrderingEvent).
- [x] **결정론 fill 모델·RNG 0·재주입** — §4(Transmit→SendHandoff·EGRESS 재주입·6 kind 전수·seed 규율).
- [x] **fill PRICE 위치 결정** — §4.3(D-E3-로컬·엔진 records 미개조·구조 근거).
- [x] **1-entry 시나리오 + 리플레이** — §5(7 시나리오·round-trip 이연·재현성 audit-grade).
- [x] **차등 오라클 계약** — §6(out-of-tree 아티팩트·entry-decision 합의·firewall 준수·deviation budget).
- [x] **look-ahead 구조 보장** — §3.6(prefix-bounded·결정 vs 체결 분리).
- [x] **firewall(tos.* 부분집합·numpy/pandas/shared 금지·canary)** — §0.3·§9.
- [x] **anti-phantom(존재/부재 양방향 grep·file:line)** — §0.5·전 인용 실측.
- [x] **음극성 `is False`·양성 identity·구조 파생·∅ 양방향·UNKNOWN-restrictive** — §4.2·§13(D-E1 규율 상속).
- [x] **seam 지도·수치 하드코딩 0·명명·리뷰어 반론** — §7·§10·§12.
- [ ] **미해결(운영자/후속)**: 명명 `tos.backtest` 확정(§12.1)·D-E2 값 표면 착지 여부(§3.5 provisional 봉인
      해소)·차등 오라클 placement(scripts/ vs 전용 디렉터리·§6.1)·bound 신설·승인(§10).

---

## 16. 요약 + 재실측 발견

**tos.backtest(D-E3)는 D-E1 단일 코어를 소비하는 백테스트/라이브 패리티 축의 첫 하네스다.** 확정: (1) bar→
DECISION_TICK 인과 스트리밍 변환(wall-clock 0·tos.time 주입·monotone 좌표), (2) 결정론 paper fill 모델(`Transmit`
→ `SendHandoff` 즉시 반환·합성 fill을 `EGRESS_RESULT`로 **재주입**·6 kind 전수·RNG 0), (3) ADR-DEV-010 스코프
경계(**기계·패리티 실증**으로 구조 봉인·admissible backtest/edge 미주장·자기-disqualify 회피), (4) NIT-3 무해제
정면 처리(scope당 1주문·round-trip 이연·at-most-one FIRING 양성 실증·재인스턴스화 금지), (5) 차등 오라클
(out-of-tree 아티팩트·entry-decision 합의만·firewall 준수), (6) 1-entry 시나리오 7종 + 리플레이(audit-grade).

**정직 스코프**: 닫는 EV 0. 슬라이스는 **배선의 기계·패리티 실증**이지 전략 성과 acceptance 아님 — G2·P0-1·P0-3
미결·단일-런 disqualifier·권위 런타임 provisional·fill=합성 대역. fill 가격은 D-E3-로컬(엔진 capacity 머신
미개조).

**⚠ 재실측 발견(입력 브리프 정정)**:
1. **NIT-3 state 어휘 정정**: 브리프는 "REJECT조차 RELEASE_PENDING_PROOF·RELEASED 상태 자체가 없음"이라 했으나,
   committed state.py는 **`RELEASE_PENDING_PROOF`를 보유**(state.py:64·:83 REJECT 매핑)·부재한 것은 **`RELEASED`
   상태(state.py:57)와 release 메서드(state.py:22)뿐**. 무해제 제약은 확정·오히려 더 강함(REJECT도 scope 점유
   유지·§2.1).
2. **Transmit이 fill을 반환하지 않음**: `Transmit`(sequencer.py:103)은 `SendHandoff`(hand-off ack)만 반환·fill은
   별도 `EGRESS_RESULT`로 재주입(§4.1) — fill 모델은 stage + 드라이버 재주입 2책임.
3. **fill PRICE 무처(엔진)**: `EgressResultPayload`는 수량-only(records.py:186-191·price 필드 부재) — 체결가는
   D-E3-로컬(§4.3).
4. **concrete 수량/가격 flow 부재**: `Proposal`은 `quantity_basis`(evidence)·direction만·절대 주식수/가격 부재
   (proposal.py:120-135)·concrete 파생은 ioc provisional stand-in — fill 수량 Q는 **시나리오 파라미터**(§4.3).
5. **서베이 구조 정정(sub-agent)**: 서베이 §7-3은 (a)/(b)만(운영자 권고 (a))·"(c)" 부재. ADR-DEV-010에 literal
   "mechanism-only"/"seed"/"parity" 토큰 부재(개념은 §8:196-197·BTE-INV-001·RFC-003 §10로 delegate). register에
   backtest/cost/oracle bound 부재(§10 소비 bound는 RFC-005 §9·DCE-INV-007). ADR-002-016 = Evidence Store
   ENGINE(G5)이지 RCL 아님(RCL=ADR-002-002).

---

## 17. 개정 로그 (v1.1 — 2026-07-29 독립 비평 리뷰 REVISE 반영)

**평결**: REVISE(CRITICAL 0·MAJOR 2·MINOR 2·NIT 2). 인용 실측 전건 정확·phantom 0·§16 재실측 5건 재검증 성립·
§12.2 선제 반론 6종 자체 논리 SOUND(두 MAJOR는 반론이 **선점하지 못한 축**에서 성립). "register §3:90" 인용은
재검증에서 유효 확정(1차 심사의 소문자 grep 오탐). finding별 처분(전건 적용·실증 반론 0):

| finding | 처분 | 변경 위치 |
|---|---|---|
| **MAJOR-1** 재주입 좌표가 엔진 전역 `_last_reference` 게이트 오식별(next-bar 정산 허위 REVERSED) | 적용(전건) | §3.4 불변식 재정의(드라이버 소유 monotone yield-순서 카운터·좌표순서≡처리순서·"직전 admit 이벤트 뒤"·bar_index 탈동조)·§3.6 인과순서 cross-ref·§0.4 B3 리스크 정정·§8-1 property(next-bar 시퀀스 포함)·배너 |
| **MAJOR-2** 차등 오라클의 미조정 D-E2 의존 | 적용(하이브리드 (i)+(ii)) | §6.2 2층 분해(①슬라이스-1 비-numeric 구조 배선·②numeric=D-E2-gated·"술어 입력 정확성" 하향)·§6.5 신설(등가-표현 계약 (c))·§7.4 (e) 추가·§0.4 B5 정렬·배너 |
| **MINOR-1** 하류 mark-to-market PnL 재구성 봉인 | 적용 | §1.2 신규 bullet(원재료 재구성=단일-런 새 백테스트로 §8:191-192 disqualified) |
| **MINOR-2** ACK 표준-단독 시나리오·"전수" 실화 | 적용 | §5.1 시나리오 A(ACK·ACKNOWLEDGED vs UNKNOWN knowledge 축)·EgressResultKind 6종 전수 대응 명기 |
| **NIT-1** register bound 대문자 통일 | 적용 | §2.1 `MAX_unresolved_send_per_scope`(register 지칭·코드 attribute만 소문자 유지) |
| **NIT-2** 라인 정정 | 적용 | §3.3 snapshot_age_bound :145→:146·§3.2 DecisionTickPayload 4필드(instrument_key·capsule·time·reference)·§2.5 target_kind 필드(:123)·값 `TargetKind.FLAT` 구분 |

**유지(리뷰 지지)**: 핵심 판정 B1-B5(스코프 봉인·NIT-3·재주입·fill 가격 위치·차등 오라클)·NIT-3 처리(§2 재실측
정정 포함)·시나리오 계약(§5)·§12.2 선제 반론 6종(SOUND). §16 재실측 발견 5건 전부 재검증 성립으로 유지.

**재실측 인용(쓰기 전 재grep·anti-phantom §0.5)**: `_last_reference`(core.py:246·:280·:301 — 전역 단일·모든
non-REVERSED 갱신·LEDGER-halt tick도 line 301이 handler halt 전 실행)·`snapshot_age_bound`(records.py:146)·
`DecisionTickPayload` 4필드(records.py:166-170 instrument_key·capsule·time·reference)·`target_kind: TargetKind =
TargetKind.ACTION`(proposal.py:123)·`EgressKnowledge.ACKNOWLEDGED`(vocabulary.py:145)·`UNKNOWN`(:149)·ACK 매핑
(state.py:77 → None capacity). **전건 실측 일치·MAJOR-1 게이트 극성 core.py 재확인.**
