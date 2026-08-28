# P0-2 — non_trade 2키 프로브 정의 설계 (`B_non_trade_event_detect` · `B_non_trade_reconcile`)

- **Date:** 2026-08-07
- **Status:** DESIGN (저작 트랙 — 코드/커밋 없음) · **v1.1 (독립 비평 REVISE 반영)**
- **Baseline:** HEAD `44fc4343` (T4-β3 fold). 인용 기준선 = 이 커밋 (초판 저작 시 `670aef6a` → 리프레시).
- **Scope:** VERIFICATION-PROFILE-002 인접 키 2건을 "측정 가능"으로 만드는 프로브
  정의. 프로브 정의 2건(N-19 명세-대조형 · P-CA 기회주의 관측형) + INSTANCE 기입면
  매핑 + `NOT_ESTABLISHED` 정직 기술 + `tools/broker_probes/registry.py` 등재 diff
  초안(코드 블록으로만) + 런북 편입 지점(§9.2 → §5.x).
- **Non-goals (이 문서가 하지 않는 것):**
  - registry.py 등재 **적용**(후속 레인이 같은 파일을 수정 중 — diff는 초안).
  - VP-002 `value_ms` 기입 (Bounds-Approver 독점 권한 — 런북 §6.5).
  - INSTANCE `status`/`assurance_level` 승격 (자동 아님 — 런북 §6.4-3).
  - ADR-002-010 acceptance / live authorization (별개 게이트 — ADR §26).
- **핵심 판단(이 문서의 존재 이유):** 두 키가 실제로 무엇을 재야 하는가 — §2. 독립 비평이
  이 판단을 SOUND로 확증했고(§0.5 코드 증거 편입), 본 개정은 그 근거를 최강 원천으로 교체했다.

---

## 0. 증거 앵커·기준선·행번호 드리프트 (anti-phantom)

모든 주장은 file:line. VP-002 정본은 `src` 판본
(`tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml` — `registry.py::_VP`가
가리키는 파일). `book/` 판본은 렌더 산출물이며 행이 다르다(§11 M-5).

### 0.1 기준선 고정 (MODERATE-5) — clean@HEAD vs M-status

HEAD = `44fc4343` (T4-β3 fold; 초판 `670aef6a`에서 리프레시). 앵커를 **안정군**과 **가변군(M-status)**으로 분리한다:

| 안정군 (clean@HEAD — 직접 인용 가능) | 가변군 (M-status — 아래 드리프트 규율) |
|---|---|
| `tos-spec/src/…/ADR-002-010-*.md` | `docs/runbooks/kis-capability-probes.md` |
| `tos-spec/src/…/VERIFICATION-PROFILE-002.yaml` (src) | `tools/broker_probes/registry.py` |
| `tos/src/tos/nontrade/records.py`·`predicates.py` | — |
| `docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml` (44fc4343 fold로 clean) | — |

**드리프트 실측 (git status + git show 44fc4343 대조):**

- `draft.yaml` `corporate_actions`: **HEAD 44fc4343 = 템플릿 :1771 / INSTANCE :4179 (clean).**
  T4-β3 fold 커밋 `44fc4343`가 이전 워킹트리 편집을 흡수했고, 리뷰어가 블록 **바이트
  동일성**을 확인(순수 위치 드리프트). 이전 관측(670aef6a :1509/:3514 · 워킹트리
  :1759/:4166)은 이 커밋으로 대체됨 — draft.yaml은 이제 **안정군**이며 :1771/:4179를 직접 인용.
- 런북·registry: **여전히 M-status.** 섹션 번호(§4.2, §9.2 등)로 인용하고, 행을 줄 때는
  "(HEAD 44fc4343; M-status — 병합 시 재확인)"을 병기.
- VP-002 `src` + `tos/nontrade/*.py`: **clean@HEAD** — 행 직접 인용, 재드리프트 없음.

**⚠ 과거 stale 앵커 (registry/런북 기입 vs current src, 일괄 +16):**

| 참조 | stale (기입 관측) | current src (clean@HEAD) |
|---|---|---|
| `B_external_activity_detect` | :221 | **:237** |
| `B_broker_query_consistency` | :752 | **:768** |
| "absence within it is not proof of non-existence" 절 | :756 | **:772** |
| `B_non_trade_event_detect` | :815 | **:831** |
| `B_non_trade_reconcile` | :833 | **:849** |
| `B_post_trade_effect_to_obligation_commit` | :662 | **:678** |

"관측 0건 ≠ 0"의 정본 토큰 `VP-002:756`은 **현재 :772**임을 특히 유의. registry(M-status)의
`vp_line`은 기입 관측 시 :815/:833이었으며, 타 레인이 이미 교정 중일 수 있으므로 §8 diff는
"병합 시 src 재직독"을 명시한다.

### 0.2 측정 대상 2키 — 축자 인용 (VP-002 src, clean@HEAD)

```yaml
# :831
  B_non_trade_event_detect:
    value_ms: null   # APPROVE per source and broker capability profile
    semantics: source_and_broker_specific
    owner: TBD
    rationale: "MEASURE. Maximum interval from an externally effective non-trade change to authoritative detection; entry limits must remain safe throughout this interval (ADR-002-010)."
    measurement_source: reference_source_and_broker_capability_profile
    failure_response: CONTAIN
    applicable_scope: per source and broker capability profile
    review_date: null
# :849
  B_non_trade_reconcile:
    value_ms: null   # APPROVE per event/instrument/broker scope
    semantics: source_and_broker_specific
    owner: TBD
    rationale: "MEASURE. Maximum permitted unreconciled interval after a non-trade event while old and new effects remain conservatively capacity-covered (ADR-002-010)."
    measurement_source: reconciliation_and_broker_capability_profile
    failure_response: QUARANTINE_UNKNOWN
    applicable_scope: per event/instrument/broker scope
    review_date: null
```

`measurement_source: reference_source_and_broker_capability_profile`(:836)는 핵심 어휘다 —
브로커 프로파일 **단독이 아니라** 독립 참조원(reference source)과의 결합을 명시한다(§7 공통모드·
§13.13 독립참조원과 정합).

### 0.3 선례 인접 키 2건 — 축자 인용 (VP-002 src, clean@HEAD)

```yaml
# :237 — poll-only 브로커 바운드의 선례 (과제 제약 2가 지목)
  B_external_activity_detect:
    value_ms: null   # MEASURE: bounded by the broker account-event/poll cadence
    semantics: hard_maximum
    rationale: "MEASURE from Broker Capability Profile. For a poll-only broker this is bounded by the poll interval; new-action size must be constrained so plausible external activity in this window cannot breach the Hard Safety Envelope (ADR-002-002 §23.4)."
    measurement_source: broker_capability_profile
    failure_response: CONTAIN
# :840 — non_trade 가족의 our-side 형제 (이미 APPROVED)
  B_non_trade_transition_apply:
    value_ms: 1000   # RECHECK: APPROVE after conservative transition protocol is selected
    semantics: hard_maximum
    failure_response: REMAIN_HALTED
```

**구조적 발견:** non_trade 가족은 3키다 — `_event_detect`(:831, broker-side, null, MEASURE,
**source_and_broker_specific**) · `_transition_apply`(:840, our-side, 1000, **APPROVED**,
hard_maximum) · `_reconcile`(:849, broker-side, null, MEASURE, **source_and_broker_specific**).
external_activity 가족(`_detect` null + `_contain` 1000 APPROVED)과 **동형이되 결정적으로
다르다**: (1) our-side `_transition_apply`가 이미 APPROVED, (2) 양 broker-side 키의 semantics가
`hard_maximum`이 **아니라** `source_and_broker_specific`. 이 두 차이가 §2 핵심 판단을 결정한다.

### 0.4 ADR-002-010 요구 의미론 — 축자 인용 (clean@HEAD)

- §1: "Before a known event can affect a live scope, the system SHALL either: 1. prove and
  pre-authorize a conservative transition within the aggregate hard envelope; or 2. block new
  risk and place the affected scope into restricted recovery or HALT."
- §8:169: "The system SHALL preserve distinct announcement, observation, record, ex, effective,
  payable, expiry, exercise, assignment, and settlement times where applicable."
- **§8:171 (no-collapse, MAJOR-2 근거)** — ADR 원문(곡선따옴표 그대로): It SHALL NOT collapse
  them into one “corporate action date.”
- §8:173: "…the affected scope SHALL block new risk **before the earliest credible effective
  boundary** and remain restricted **through the latest credible completion boundary**."
- §8:175: "Clock recovery or a later source update SHALL NOT retroactively grant authority to
  actions denied during the uncertainty interval."
- §6: "`APPLIED_LOCAL` is not proof that the broker or venue applied the same effect."
- §7: "Multiple feeds using one upstream vendor, parser, clock, or distribution path are
  common-mode and SHALL NOT be described as independent corroboration." / "If a required field
  cannot be established within approved confidence and freshness bounds, permissive processing is
  denied."
- §17: "A known event SHALL invalidate normal live authority when it can change any bound or
  assumption used by the current authorization…"
- §25 Open Q5: "Which numeric pre-event, reconciliation, settlement, and evidence-freshness
  bounds will be approved?" → **이 두 키가 정확히 OQ5의 대상이다.**

### 0.5 tos/nontrade 구현 앵커 — 판단 확증 (clean@HEAD, MAJOR-2·4의 최강 증거)

독립 비평이 지목한, 내 초판보다 강한 원천. 두 파일 모두 clean@HEAD.

**(a) 7-시각 분리 보존 — `tos/src/tos/nontrade/records.py:359-366` (어휘 정본):**

```python
# (4) §5 line 106 the seven times, kept separate (§8 line 171 no-collapse)
"announcement_time",
"observation_time",
"record_time",
"ex_time",
"effective_time",
"payable_time",
"settlement_time",
```

`NonTradeEventRecord`는 **7개 시각을 별도 필드로 유지**하며 주석이 "§8 line 171 no-collapse"를
명시 인용한다. ⇒ P-CA는 단일 `t0_effective`를 쓸 수 없다(MAJOR-2, §5.2).

**(b) 무수치 봉쇄 술어 — `tos/src/tos/nontrade/predicates.py:873-919`
(`effective_window_blocks_new_risk`, "§6.2 … ADR §8; NT-EV-007 substrate, predicate-only"):**

- :896 "This package reads **no clock** … the boundaries are **opaque injected tokens** …
  This predicate composes them and re-authors none."
- :900-902 "The numeric freshness / detection bounds are **VP-002 injected and null in Phase 1**
  (`B_non_trade_event_detect` / `B_non_trade_reconcile`, both `owner: TBD`), so **nothing numeric
  is defaulted here.** [SAFE-035; SAFE-023]"
- :889-894 "`True` **only** as one positive conjunction … Anything unestablished leaves the
  **whole** interval restricted … an unbounded window blocks, it never opens."

⇒ 봉쇄는 **수치 임계값 없는 4-연언 fail-closed** 술어가 담당하고, 두 bound은 **아직 in-repo
수치 소비자가 없는 불투명 주입 토큰**이다. 이것이 §2.2 재프레이밍의 코드 증거다.

### 0.6 아키텍처 해소 (설계 #10 — 이미 비준된 완화책, M-status 참조는 섹션으로)

- 설계 #10 `docs/plans/2026-07-25-tos-broker-capability-design.md` §13.13 행 — **no
  corporate-action feed | independent reference · pre-session identity/qty checks · contain on
  unexplained remap · prohibit live until revaluation | authority 차단**. (BC-AC-019 = `EV-L3`
  predicate-only, `authority_blocked_until_remap`; non-trade injection = EV-L3.)
- `docs/plans/2026-07-29-tos-p02-required-capability-mapping.md:145,172` —
  `CORPORATE_ADMINISTRATIVE_EVENTS` = 전 라이브 스코프 **조건부 `fb§13.13`**; §8.12 / §13.13
  (**독립 참조원**).

---

## 1. 문제 — 실측 재확인 (MAJOR-4 정정)

`registry.py::ADJACENT_BOUND_KEYS`에 두 키가 등재돼 있으나 근거는 "corporate-action 표면이
repo에 부재(draft memo §3.1 row 12: grep 0)"이며 **정의된 프로브가 없다**(런북 §9.2·§4.2 —
M-status). `docs/plans/2026-08-06-…residual-17key…md` §3.4(:144-147)·§3.6(:171)도 두 키를
"프로브 부재 · corporate-action reference source 착지 후 이연"으로 처분했다.

**전칭 정정 (MAJOR-4):** "corporate-action 표면 부재"는 **부정확한 전칭이다.** 정확히는:

> **(i) CA 데이터 소스/피드/캘린더는 부재**하나, **(ii) `tos/nontrade` 구조화 레코드 모델은
> 실재하되 미충전**이다(records.py 7-시각 필드 §0.5-a). 그리고 **(iii) 두 bound은 in-repo
> 수치 소비자가 없는 불투명 주입 토큰**이다(predicates.py §0.5-b).

즉 "표면이 없다"가 아니라 "**모델은 있는데 채울 소스가 없고, 그 수치를 소비할 소비자도 아직
없다**"가 실상이다. 이는 판단 1·2를 **약화가 아니라 강화**한다(모델이 7-시각을 요구하므로
프로브도 7-시각을 재야 하고, 수치 소비자가 없으므로 bound은 안전 게이트가 아니라 봉쇄창
치수화용임이 코드로 확증된다).

**과제 전제 정정 (bidirectional grep):** 과제는 "표면은 `llm_event_scorer.py` 1건뿐"이라 했으나
실측은 넓다 — 단 **어느 것도 구조화 CA 이벤트 피드가 아니다**:

| 표면 | file:line | 성격 |
|---|---|---|
| LLM 심각도 rubric 1줄 | `shared/forecasting/llm_event_scorer.py:18` | `"50 = … surprise corporate action"` — 프롬프트 가중치 |
| SEIBRO 배당/기업/주주 수집기 | `shared/llm/market_data_collectors.py:17-77` | `_get_dividend_info`(:57-66)은 **`{"status": "available"}`만 반환** — ex-date·비율 파싱 없음(liveness stub) |
| DART 공시 수집기 | `shared/llm/market_data_collectors.py:80-124` | 공시 **텍스트**를 news 파이프라인으로 |
| 뉴스 키워드 | `shared/llm/config.py:238,537` | `"유상증자"` |
| KRX Open API | `shared/llm/CLAUDE.md` 엔드포인트표 | 지수/ETF/선물/옵션/채권 — **CA 엔드포인트 없음** |
| KIS 클라이언트 | `config/kis/`·`shared/kis/` grep `배당\|권리\|dividend\|corp_action\|액면\|분할\|merger\|무상\|유상\|seibro\|entitlement` → **0 hits** | KIS에 CA 조회 API **미배선** |
| `shared/calendar.py:1-40` | — | **거래 휴장일**만. CA 캘린더 아님 |

draft memo의 좁은 grep(`corporate_action\|권리락\|액면분할` → 0)은 문자 그대로 참이고, 실효
있는 **구조화 CA 이벤트 피드/원장/캘린더는 없다.** SEIBRO/DART는 참조 수집기로 존재하나
effective-time·비율을 파싱하지 않는다.

**필기면은 존재한다:** `draft.yaml` `corporate_actions` 블록 — 템플릿 **:1771**(HEAD 44fc4343) /
INSTANCE **:4179**(HEAD 44fc4343). 필드는 `status`·`assurance_level`·`evidence_refs`·
`restrictions`·`restriction_approved`·**`fallback_reference`**·`assurance_sources`·
`_kis.measurement`. **전용 수치 슬롯(`detection_bound_ms` 류)은 없다** — §6의 결함 클래스.

---

## 2. 핵심 판단 — 이 두 bound은 실제로 무엇을 재는가 (독립 비평 SOUND 확증)

### 2.1 판정: `B_external_activity_detect`로 환원되지 않는다. 브로커 반영 지연이 지배한다.

**증거는 semantics 필드에 성문화돼 있다.** external_activity_detect = `hard_maximum`(:239, "bounded
by the poll interval" :241). 두 non_trade 키 = `source_and_broker_specific`(:833, :851, poll 불언급).
저작자가 **의도적으로 hard_maximum으로 두지 않았다.**

`B_non_trade_event_detect` rationale(:835): "Maximum interval from an **externally effective**
non-trade change to authoritative detection". t0가 "브로커 API가 바뀐 시점"이 아니라 **"경제적으로
실효된 시점"**(ADR §8 ex/effective/payable/settlement 중 하나)이다. 두 시계로 분해:

```
   경제적 실효 (ADR §8 7-시각 中)     broker API 반영              우리가 폴로 탐지
        │───────── clock (c) ─────────│──────── clock (b) ────────│
        │  브로커 반영 지연             │  폴 cadence                │
        │  T+0…T+n 일, source/broker/  │  ms~초, our-side 설정,     │
        │  event-class×leg specific,   │  = external_activity_detect │
        │  우리 통제 밖, poll 무관      │  구조 (유일한 poll-유계)    │
```

- **clock (c)** (지배항): CA가 "실효됐으나 브로커 API엔 아직 안 뜬" 구간. 일-단위,
  `source_and_broker_specific`, poll 무관. 확립 = N-19(문서 모델) + P-CA(관측 표본).
- **clock (b)** (무시가능 가산항): external_activity_detect 구조, poll-유계, ms~초.

`B_non_trade_event_detect = (c) + (b)`이고 **(c)가 (b)를 압도** ⇒ **poll cadence만 재면
무시가능한 (b)만 재는 것 = 프로브 무의미**(과제 경고 실체). 재야 할 것은 **(c)**.

`B_non_trade_reconcile`(:853): "Maximum **permitted** unreconciled interval … while old and new
effects remain conservatively capacity-covered" — **허용 예산**이되 상한은 브로커의 field-level
reconciliation 증거(final quantity·cash-in-lieu leg)·finality 시점에 유계(:854
`reconciliation_and_broker_capability_profile`). 역시 일-단위·`source_and_broker_specific`.

**코드 확증(§0.5):** records.py가 7-시각을 붕괴 금지로 분리 유지(§8:171)하고, predicates.py가
detection bound을 "null·불투명 주입 토큰"으로 다루며 "reads no clock". 즉 구현이 이미 (c)를
문서·계약 대상으로, (b)를 무관 항으로 취급한다.

### 2.2 재프레이밍: bound은 안전을 *결정*하지 않고 봉쇄 창을 *치수화*한다 (코드 증거)

ADR §8·설계 #10 §13.13은 이 지연이 크고 불확실함을 전제로 설계됐다. **안전은 빠른 탐지에
의존하지 않는다:**

- **알려진 이벤트**(참조원 소재): §8:173 — "block new risk **before the earliest credible
  effective boundary** and remain restricted **through the latest credible completion boundary**".
  캘린더 구동 **사전 authority 차단**이 1차 방어. 빠른 탐지 불요.
- **미지/기습 이벤트**: 탐지 지연이 관건 ⇒ `B_non_trade_event_detect`, failure_response
  **CONTAIN**.
- **구조적 안전 속성**은 `effective_window_blocks_new_risk`(predicates.py:873-919)와 BC-AC-019
  **EV-L3** 주입이 담당 — **수치 임계값 없는 4-연언 fail-closed**(§0.5-b). broker 지연 측정과 독립.

⇒ 두 bound의 직무는 **§13.13 봉쇄/사전세션 창을 치수화**하는 것. bound이 작아야 안전한 게
아니다(작을 수 없다). "measurable"의 올바른 의미 = 하드 스칼라 확립이 아니라 **class×leg별
provenance 부착 후보 특성화**를 산출하고, 참 하드 bound은 정직하게 `NOT_ESTABLISHED`로
남기는 것(§7·§11).

---

## 3. 구조 비판 — 과제의 2단(명세-대조 + 기회주의 관측)을 검토

### 3.1 대안 검토와 기각

- **대안 A — broker CA 조회 프로브(GET) 단독:** KIS가 CA 스케줄/통지 API를 노출하면 broker가
  참조원이 되어 `measurement_source: reference_source_and…`(:836)를 직접 충족. **그러나**
  `config/kis/`·`shared/kis/` grep 0 — 배선 부재이고 KIS REST 제공 여부 자체가 미지. ⇒ **N-19에
  흡수**: N-19 첫 질문 = "KIS가 CA 조회/통지 API를 노출하는가". 있으면 P-CA broker-native t0
  앵커 가능, 없으면 §13.13 fallback_reference(독립 참조원)가 외부여야 함.
- **대안 B — 관측 생략, N-19 + EV-L3만:** 안전은 predicates.py 무수치 술어 + BC-AC-019 EV-L3가,
  봉쇄창은 보수적으로 잡으니 P-CA 실측이 불필요하다는 입장. **부분 타당 — P-CA는 안전-필수가
  아니다.** 그러나 P-CA는 "N-19 문서 모델이 현실과 어긋나는 경우"를 잡는 **반증** 가치를 갖는다.
  ⇒ 기각 아니라 **P-CA를 bound-확립이 아닌 반증 프로브로 재정의**해 채택.
- **대안 C — 모의계좌 사전 보유만(과제 원안):** §3.2의 두 결함으로 불충분.

### 3.2 채택 구조 (과제 원안 대비 2개 강화)

**강화 1 — N-19는 P-CA의 경성 선행조건이다.** P-CA가 clock (c)를 재려면 ground-truth 7-시각
(t0)이 필요한데 repo엔 CA 캘린더가 없다(§1). t0는 **외부/운영자 공급**이거나 KIS CA API 존재
시 broker-native — 어느 쪽인지 **N-19가 먼저 판정**. 게다가 **모의서버가 CA를 실제 처리하는지도
미지**(N-19/관측 산출). t0 없이 P-CA는 clock (b)만 재게 되어 무의미. ⇒ **N-19 미착지 시 P-CA
unanchorable.**

**강화 2 — P-CA는 하드 스칼라를 확립할 수 없다. class×leg 반증·후보만 낸다.** CA 희소 ⇒ n 극소
(§8.2 소표본 과소평가), 늦은 reconcile 0관측 = 0 아님(§8.4 / VP-002:772). ⇒ P-CA 산출은
**`candidate_only`**, 1차 산출은 **"관측 반영이 N-19 문서 모델 또는 후보 봉쇄창보다 늦다"는
반증**(봉쇄창 과소치수 폭로).

---

## 4. 정책 게이트 — 자산군·환경·주문 (과제 제약 4)

| 환경·자산 | CA 관측 가능? | 근거 |
|---|---|---|
| **모의(VTS) 주식** | 조건부 — 모의서버 CA 처리 여부 미지 | 모의가 배당/분할을 잔고에 반영하는지 N-19/관측 전까지 UNKNOWN. 보유 셋업은 **KIS 모의투자 주문**(P-2/P-5/P-11식 ENV_MOCK 주문, real orders 0)으로 저렴 |
| **실전 주식 (GET 전용)** | 가능(유일한 REAL_PROD 표본원) | 실주식 GET 읽기는 정책 허용(P-BAL 선례: env REAL 대상 = 실주식). **선행 보유 필요**(정상 paper/live 운용 산물), 프로브는 **주문 0** |
| **모의 선물** | **불가** | 모의서버 선물 잔고 미지원 — `shared/kis/client.py:1031`("모의서버는 선물 잔고조회 미지원. is_real=True 필수"; `get_futures_balance` :1023, 가드 로그 :1047) |
| **실전 선물** | **불가·정책 금지** | 실선물 무증거금·무보유(CLAUDE.md Non-Negotiable). 실선물 주문 경로 영구 차단 |

**선물 CA의 형태:** ADR §4.2 — "A strategy-initiated rollover trade remains a trade. Exchange or
broker expiry and settlement effects are non-trade events." 선물 CA = **만기/인수도/현금결제**
(ADR §14). KOSPI200 선물 = 분기 현금결제 만기. **만기는 계약명세로 결정론적·캘린더 기지**라
"탐지"가 사소; 관건은 결제 반영(settlement_time leg). 그러나 위 표대로 **모의·실전 양 경로가
구조적으로 막혀** 선물 P-CA = `NOT_ESTABLISHED`. 선물은 **N-19(KIS 문서: 만기/결제 반영
semantics) + 결정론적 계약명세/캘린더**에 전적으로 의존.

**정책 정합:** P-CA는 **주문을 내지 않는다**(GET 전용 폴링, 보유는 선행조건). 모의 보유 셋업은
KIS 모의투자 주문뿐. 실주식 GET는 허용. 실선물 제외. ⇒ "실선물 무증거금·실주문 금지, GET-only
실읽기 허용"과 완전 정합.

---

## 5. 프로브 정의 2건

명명 규약 실측: 기존 ID = P-1/2/5/5b/8/11/13/14/15/16, P-EXT, P-FQP(draft §5), N-15/16/17/18
(census plan §1 T2), P-NMPR/P-BAL/P-R5-PRE/P-R5(후속). prefix는 **출처 문서** 반영일 뿐 kind가
아니다. 후속물은 `source`가 "draft"/"plan"으로 **시작하지 않게** 해 `coverage_report()` 정본
카운트를 불변 유지(registry.py 규율). 충돌 검사: `N-19`·`P-CA`·`probe_ca`·`probe_n19` grep → 0.

두 프로브 `bounds_keys`는 인접 키를 가리킨다. 이 키들은 `ADJACENT_BOUND_KEYS`에 있어
`coverage_report()`의 `bound_keys_not_touched = set(BOUND_KEYS) − covered`에 **영향 없음** —
커버리지 왜곡 없음.

### 5.1 N-19 — 명세-대조형 (SPEC_CROSSCHECK)

| 필드 | 값 |
|---|---|
| `probe_id` | `N-19` |
| `title` | `Spec cross-check — corporate-action reflection model (CA-schedule API 존부 / 7-시각별 반영 시점 / reconciliation 증거 / 독립 참조원)` |
| `source` | `non_trade 2키 프로브 정의 설계 (2026-08-07)` — "draft"/"plan" 아님 (카운트 불변) |
| `kind` | `SPEC_CROSSCHECK` (N-17 동형) |
| `environment` | `ENV_NONE` (문서 대조 — 모의서버 불요) |
| `dimension` | `CORPORATE_ADMINISTRATIVE_EVENTS` |
| `bounds_keys` | `("B_non_trade_event_detect", "B_non_trade_reconcile")` |
| `instance_fields` | `("capabilities.corporate_actions.fallback_reference", "capabilities.corporate_actions.status", "capabilities.corporate_actions.evidence_refs")` — **전용 수치 슬롯 없음**(§6) |
| `emits_orders` | `False` |
| `requires_confirm` | `False` (브로커 무접촉) |
| `supported` | `False` (스크립트 아님 — 문서 대조; N-17 선례) |
| `risk` | `LOW` |
| `duration` | `~2-3 h desk work` |
| `entrypoint` | `""` |

**차단 선행조건 없음 (MAJOR-1):** 수단(`kis-code-assistant-mcp` 조회 전용)은 이미 결정됐다 —
plan §1 T3 **D6 조건문은 2026-07-29 운영자의 MCP 재가동 완료 보고**(대화 수준·리포 외 행위)로
해소됐고, N-17이 그 수단으로 실제 대조를 수행했다(귀속 프레임 = **대화-수준 운영자 행위**; 이미
워킹트리 `registry.py` N-17 skip_reason·런북 §7이 반영. 형식화 기록은 in-flight
`docs/plans/2026-08-07-tos-p02-d5-d6-decision-record.md` §2.2 — 타 레인 개정 중이라 이 문서는
대화-수준 사실에 앵커한다). ⇒ **N-19는 N-17이 쓴 동일 MCP 경로로 즉시 착수 가능.**

**절차 (런북 §7-CA 체크리스트 신설):** 원전 = KIS 공식 API 포털 /
`github.com/koreainvestment/open-trading-api`(2차 커뮤니티 원천 금지 — 런북 §7). 확정 대상(전수):

1. **CA 조회/통지 API 존부** — KIS REST에 배당/권리/분할/병합/만기 스케줄·통지 조회 TR이 있는가?
   (있으면 broker-native 참조원 → §13.13 fallback_reference 후보·P-CA t0 앵커. 없으면 참조원은
   외부.) **부재는 문서로만 확인**(요청으로 확인 불가 — 런북 §7).
2. **7-시각별 반영 모델(자산·CA 클래스별)** — KIS가 각 CA를 잔고·포지션·체결통보 API에 언제
   반영하는가. ADR §8:171 no-collapse에 따라 `ex_time`/`effective_time`/`payable_time`/
   `settlement_time`을 **붕괴 없이** 클래스별로. clock (c) 문서값.
3. **reconciliation 증거·finality 시점** — final quantity·cash-in-lieu·rounding을 어떤 필드로
   언제 노출(`B_non_trade_reconcile` 상한의 문서 근거).
4. **독립 참조원 후보** — §13.13 "independent reference". §7 공통모드 주의: 단일 vendor/parser/
   clock는 독립 아님(ADR §7).

**verdict 기준:** categorical, 측정 아님. 각 항목 = `VERIFIED(URL+접근일자)` /
`UNSUPPORTED(문서상 미제공 명시)` / `UNKNOWN(문서 침묵)`. **문서에 반영 시점이 없으면 UNKNOWN이지
0/즉시가 아니다**(§8.4). 항목 1이 UNSUPPORTED/UNKNOWN이면 `CORPORATE_ADMINISTRATIVE_EVENTS`
라이브 스코프를 **`fb§13.13` 조건부로 고정**(required-capability-mapping:145).

### 5.2 P-CA — 기회주의 관측형 (MANUAL, GET-only)

| 필드 | 값 |
|---|---|
| `probe_id` | `P-CA` |
| `title` | `corporate_action reflection — 7-시각×leg별 (실효→broker-reflect→detect) latency (기회주의·GET-only·operator t0)` |
| `source` | `non_trade 2키 프로브 정의 설계 (2026-08-07)` — 카운트 불변 |
| `kind` | `MANUAL` (operator-in-loop: 7-시각 공급; P-EXT 선례) |
| `environment` | `ENV_MOCK` 기본 / `ENV_REAL` 오버라이드 (P-BAL식 `--env`; M-3 사유 아래) |
| `dimension` | `CORPORATE_ADMINISTRATIVE_EVENTS` |
| `bounds_keys` | `("B_non_trade_event_detect", "B_non_trade_reconcile")` |
| `instance_fields` | `("capabilities.corporate_actions.evidence_refs", "capabilities.corporate_actions.status")` — 수치 슬롯 없음(§6) |
| `emits_orders` | `False` (GET 전용 폴링. 보유는 **선행조건**; P-BAL 선례) |
| `requires_confirm` | `True` (모든 networked 프로브 — read-only라도) |
| `supported` | `False` (기회주의·N-19 선행·미구현 — skip_reason) |
| `risk` | `LOW` (GET 전용 — P-BAL 극성; **§8.2 diff와 일치**) |
| `duration` | `이벤트 창 전후 폴링, operator in the loop` |
| `entrypoint` | `""` (구현 후속) |

**`prerequisites` (MAJOR-3, P-EXT :523-526 / P-BAL :761-771 문형 — registry M-status, MAJOR-1發 +6 시프트):**

1. **N-19 선착지** — KIS CA-API 존부·모의 CA 처리 여부·독립 참조원(§13.13)이 확립되기 전엔
   unanchorable.
2. **operator 7-시각 기록** — 관련 `ex_time`/`effective_time`/`payable_time`/`settlement_time`을
   프롬프트 시 축자 기록(P-EXT식; in-repo CA 캘린더 부재).
3. **선행 보유** — 대상 종목을 대상 계좌가 미리 보유(모의=KIS 모의투자 주문 산물 / 실전=기존
   실주식 보유). 보유 0이면 아무것도 확립 못함(P-BAL 문형).
4. **선물 제외** — 모의 선물잔고 미지원(client.py:1031 NOTE·가드 :1047) + 실선물 무증거금·무보유.
5. **READ-ONLY** — GET 폴링만, 모듈에 주문 경로 없음(P-BAL 문형).
6. **`--env real` 시 운영자 승인** — 실 자격증명 소비. MOCK 아티팩트는 REAL_PROD 문서 인용 불가
   (§6.2·ADR-002-004 §13.14).

**절차:** ① N-19 착지 후 참조원에서 예정 CA 종목·7-시각 확보(operator). ② 대상 계좌 선행 보유.
③ 관련 시각 전후로 잔고·포지션·체결통보를 `--poll-ms`로 폴링. ④ operator가 프롬프트 시 각
시각을 축자 기록. ⑤ 각 CA leg의 broker 반영 폴을 포착.

**statistic·verdict (MAJOR-2 — class×leg별, 단일 t0_effective 폐기; MODERATE-7 estimand):**
ADR §8:171 no-collapse + records.py:359-366 어휘에 따라 **leg마다 7-시각 중 해당 시각을 t0,
그 leg의 broker 반영 폴을 t1로 짝짓는다:**

| event_class | leg | t0 (7-시각 中) | t1 |
|---|---|---|---|
| 배당(cash dividend) | 기준가-조정(배당락) | `ex_time` | broker가 기준가/수량 조정 반영한 폴 |
| 배당 | 현금 입금 | `payable_time` | broker가 현금 입금 반영한 폴 |
| 분할/병합/무상 | 수량 변환 | `effective_time` | broker가 신수량 반영한 폴 |
| (선물 만기/결제 — **관측 제외** §4) | 포지션0화·현금결제 | `settlement_time` | — |

- 각 셀 후보 = `candidate max(t1_leg − t0_leg)` within `(class, leg, source, broker)`.
- **집계 `B_non_trade_event_detect`/`_reconcile`는 스칼라가 아니라 class×leg 색인 표다.**
  semantics `source_and_broker_specific`의 추정량(estimand)을 런북 §8(통계 규율)이 **정의하지
  않으므로**(hard_maximum/broker_specific만 다룸 — §11), P-CA는 leg별 후보만 내고 집계 스칼라를
  주장하지 않는다. ⇒ §5.2는 `hard maximum`을 **셀-국소 후보**로만 쓰고 aggregate로 쓰지 않는다
  (§2.1 논증과 내적 정합).
- **반증 우선:** 어느 셀이든 관측 t1이 N-19 문서 모델/후보 봉쇄창보다 **늦으면** = 창 과소치수
  폭로(1차 산출). 늦은 반영 0관측 = 0 아님(§8.4 / VP-002:772). 희소·소표본 → 항상
  `candidate_only`. 단발로 하드 bound 주장 금지(§8.2). 모의가 CA 미반영이면 그 자체 findings
  ("mock does not apply CA") — 유효하나 clock (c) bound은 아님.

**환경 극성 (M-3):** `ENV_MOCK` 기본은 **정책-안전·저비용 프로브 개발 기본값**이다. 단 §6.2
(MOCK_VTS 아티팩트를 REAL_PROD 프로파일 문서에 인용 금지 — ADR-002-004 §13.14)에 따라 **모의
아티팩트는 "모의서버 CA 처리 여부" feasibility/behavior findings일 뿐 REAL_PROD-citable clock(c)
bound이 아니다.** REAL_PROD INSTANCE(draft.yaml:4179, HEAD 44fc4343)를 채우려면 `--env real` 주식 GET 암을
써야 하고, 아티팩트가 실제 env를 기록하며 §6.2가 교차환경 인용을 막는다(P-BAL env-override 및
런북 §4.1 이중환경 주의와 동형).

**§6.2 인용 적격성:** `mode:"live"` · `provenance_class:"MEASURED"` · `errors:[]` · `skips[]`
검토 · `repo_commit` 일치 · `environment` 일치(교차환경 인용 금지). 값 인용 시 `environment`와
`measurements.scope_and_transfer` 동반.

---

## 6. INSTANCE 기입면 매핑 + 전용 수치 슬롯 부재 (§9.1/§9.4와 같은 결함 클래스)

`corporate_actions` 블록(draft.yaml:1771, HEAD 44fc4343)에는 전용 수치 bound 슬롯이 없다. 따라서
N-19/P-CA 산출은 전용 필드를 **발명하지 않고**(런북 §9.4 "registry.py는 없는 필드명을 발명하지
않는다") N-16/P-BAL의 Patch-0057 재매핑과 동일하게 기입:

- **아티팩트(증거)** → `capabilities.corporate_actions.evidence_refs[]` (+ 보존 위치, §6.3).
- **도달 가능성/상태** → `capabilities.corporate_actions.status` (자동 승격 금지, §6.4-3).
- **독립 참조원 판정(N-19 항목 1·4)** → `capabilities.corporate_actions.fallback_reference`
  (§13.13 "independent reference"의 자연 착지면).
- **측정 등급** → `capabilities.corporate_actions._kis.measurement`
  (`NEEDS-LIVE-MEASUREMENT` → 실측 후 `OFFICIAL-DOC`/`CODE-EVIDENCED`).
- **bound 수치값** → `NOT_ESTABLISHED` 유지. `value_ms`는 Bounds-Approver만(§6.5), 후보는
  `candidate_only`.

**§9.4-class 갭 명시 등재:** `corporate_actions`에 `detection_bound_ms`/`reconcile_bound_ms`
전용 슬롯 신설이 옳은지, `evidence_refs`+`status` 흡수가 옳은지는 `docs/broker-profiles/`·tos-spec
템플릿 소관(§9.1 규율). **판정 전까지 P-CA 판정값은 evidence_refs가 가리키는 아티팩트 안에만
존재하고 INSTANCE 본문엔 올라가지 않는다** — 조용한 증발 방지 최소 조치.

---

## 7. `NOT_ESTABLISHED`로 남는 부분 (정직 원장)

| 항목 | 상태 | 사유 |
|---|---|---|
| `B_non_trade_event_detect` `value_ms` | **NOT_ESTABLISHED (null)** | clock (c) = source_and_broker_specific class×leg 표. N-19 문서값 + P-CA 소표본 후보만 |
| `B_non_trade_reconcile` `value_ms` | **NOT_ESTABLISHED (null)** | 동상. finality 시점은 브로커 노출 의존 |
| KIS CA 조회/통지 API 존부 | **UNKNOWN → N-19 항목 1** | grep 0(배선 부재); REST 제공 여부 문서 미확인 |
| 모의서버 CA 처리 여부 | **UNKNOWN** | N-19/P-CA 전까지 미지 |
| 선물 CA(만기/결제) 반영 지연 | **NOT_ESTABLISHED via probe** | 모의 선물잔고 부재(client.py:1047)·실선물 무보유. N-19 + 계약명세/캘린더 의존 |
| in-repo CA 7-시각 캘린더 | **부재(확정)** | SEIBRO stub·DART 텍스트·KRX 무엔드포인트·calendar=휴장일. P-CA t0는 외부/operator |
| 독립 참조원(§13.13) 확정 | **미확정 → N-19 항목 4** | 단일 vendor 공통모드 배제 필요(ADR §7) |

**value_ms 폐쇄 요건 (연언, MODERATE-6):** `B_non_trade_event_detect`/`_reconcile`의 value_ms
폐쇄 = **(A)** 템플릿/INSTANCE에 수치 슬롯을 신설할지 evidence_refs로 흡수할지의 **스펙-트랙
판정**(§6) **∧** **(B)** N-19의 class×leg 문서 모델에 대한 **Bounds-Approver의 보수 판단**(§6.5)
— **P-CA 단독으로는 어느 쪽도 충족하지 못한다**(P-CA는 (B)의 반증 입력일 뿐 (A)와 무관).

**"프로브 정의됨 ≠ 키 확립됨"을 승인 패키지에 명시.** 안전 속성(authority_blocked_until_remap /
`effective_window_blocks_new_risk` 무수치 술어)은 BC-AC-019 EV-L3가 담당하며 이 두 bound과 독립.

---

## 8. registry.py 등재 diff 초안 (코드 블록으로만 — 적용은 후속 레인)

> ⚠ **적용 금지.** 타 레인이 `registry.py`(M-status)를 수정 중. 병합 시 (a) 현재 파일에 rebase,
> (b) drift 교정값(`vp_line`)을 **현재 src 재직독**으로 재확인, (c) `--coverage`로 정본 카운트
> 불변 확인. **N-17 skip_reason의 D6 문구는 건드리지 않는다** — 이미 워킹트리가 "대화-수준
> 운영자 행위" 프레임으로 반영했고, 그 라인 교정은 D5/D6 기록 레인 소관.

### 8.1 `ADJACENT_BOUND_KEYS` 두 항목 갱신 (note + vp_line drift 교정)

```python
    "B_non_trade_event_detect": BoundKey(
        "B_non_trade_event_detect",
        831,  # was 815 (stale +16); re-read src before merge
        "null",
        "source_and_broker_specific",
        "CONTAIN",
        "reference_source_and_broker_capability_profile",
        True,
        "ADR-002-010. Dominated by broker reflection delay (clock c: effective->"
        "broker-reflect, per event_class x leg over the 7 separate times in "
        "tos/nontrade/records.py:359-366), NOT poll cadence — semantics is "
        "source_and_broker_specific, not hard_maximum. Probes: N-19 (spec) + P-CA "
        "(opportunistic, GET-only, N-19-gated). Bound stays NOT_ESTABLISHED; safety "
        "carried by effective_window_blocks_new_risk (predicates.py:873-919, no-numeric) "
        "and BC-AC-019 EV-L3.",
    ),
    "B_non_trade_reconcile": BoundKey(
        "B_non_trade_reconcile",
        849,  # was 833 (stale +16); re-read src before merge
        "null",
        "source_and_broker_specific",
        "QUARANTINE_UNKNOWN",
        "reconciliation_and_broker_capability_profile",
        True,
        "ADR-002-010. Permitted unreconciled budget, bounded by broker field-level "
        "reconciliation evidence + finality timing. Probes: N-19 + P-CA. NOT_ESTABLISHED.",
    ),
```

### 8.2 `PROBES` 두 항목 추가 (follow-up 블록 뒤)

```python
    # ---- non_trade follow-up (source starts with neither "draft" nor "plan" so
    # coverage_report()'s canonical-12 / census-4 counts stay exactly as ratified) ----
    "N-19": _S(
        probe_id="N-19",
        title=(
            "Spec cross-check — corporate-action reflection model "
            "(CA-schedule API 존부 / 7-시각별 반영 시점 / reconciliation 증거 / 독립 참조원)"
        ),
        source="non_trade 2키 프로브 정의 설계 (2026-08-07)",
        kind="SPEC_CROSSCHECK",
        environment=ENV_NONE,
        dimension="CORPORATE_ADMINISTRATIVE_EVENTS",
        bounds_keys=("B_non_trade_event_detect", "B_non_trade_reconcile"),
        instance_fields=(
            "capabilities.corporate_actions.fallback_reference",
            "capabilities.corporate_actions.status",
            "capabilities.corporate_actions.evidence_refs",
        ),
        statistic="categorical; documentary cross-check, no measurement (N-17 형).",
        risk="LOW",
        duration="~2-3 h desk work",
        supported=False,
        skip_reason=(
            "N-19 is a documentary cross-check, not a script (N-17 형). 수단"
            "(kis-code-assistant-mcp 조회 전용)은 이미 결정됨 -- plan §1 T3 D6 조건문은 "
            "2026-07-29 운영자 MCP 재가동 보고(대화 수준·리포 외 행위)로 해소됐고 N-17이 "
            "그 수단으로 실제 대조를 수행했다 (registry.py N-17 skip_reason·런북 §7이 반영). "
            "따라서 N-19는 동일 MCP 경로로 즉시 착수 가능 -- 차단 선행조건 없음. 첫 질문: "
            "KIS가 CA 조회/통지 API를 노출하는가. 체크리스트는 런북 §7-CA."
        ),
        entrypoint="",
    ),
    "P-CA": _S(
        probe_id="P-CA",
        title=(
            "corporate_action reflection -- 7-time x leg (effective->broker-reflect->"
            "detect) latency (기회주의·GET-only·operator t0)"
        ),
        source="non_trade 2키 프로브 정의 설계 (2026-08-07)",
        kind="MANUAL",
        environment=ENV_MOCK,  # P-BAL식 --env 오버라이드; 아티팩트가 실제 env 기록 (§5.2 M-3)
        dimension="CORPORATE_ADMINISTRATIVE_EVENTS",
        bounds_keys=("B_non_trade_event_detect", "B_non_trade_reconcile"),
        instance_fields=(
            "capabilities.corporate_actions.evidence_refs",
            "capabilities.corporate_actions.status",
        ),
        statistic=(
            "per (event_class x leg) — single t0_effective 폐기 (ADR §8:171 no-collapse; "
            "records.py:359-366). 배당 기준가-조정 leg: t0=ex_time; 배당 현금 leg: "
            "t0=payable_time; 분할/병합 수량 leg: t0=effective_time; (선물 결제 leg: "
            "t0=settlement_time — 관측 제외). 셀 후보 = candidate max(t1_leg - t0_leg). "
            "aggregate B_non_trade_* 는 스칼라 아닌 class x leg 표 (source_and_broker_specific "
            "추정량은 런북 §8 미정의). Rare event => tiny n => candidate_only; 단발로 "
            "hard_maximum 주장 금지. 늦은 반영 0관측 != 0 (VP-002:772). 1차 산출 = N-19 "
            "모델/후보 봉쇄창 대비 FALSIFICATION."
        ),
        risk="LOW",  # GET-only (P-BAL 극성); 표와 일치
        duration="이벤트 창 전후 폴링, operator in the loop",
        emits_orders=False,  # GET 전용; 보유는 선행조건(P-BAL 선례)
        requires_confirm=True,
        supported=False,
        skip_reason=(
            "기회주의: (a) N-19 선행 필수 — KIS CA-API 존부·모의 CA 처리 여부 UNKNOWN; "
            "(b) operator 공급 7-시각(ex/effective/payable/settlement) 필수 (in-repo CA "
            "캘린더 부재: SEIBRO stub market_data_collectors.py:57-66·DART 텍스트만); "
            "(c) REAL_PROD 표본은 예정 CA와 겹치는 선행 실주식 보유 필요. 선물 제외 "
            "(모의 잔고부재 client.py:1047 / 실선물 무증거금). (a) 미착지 시 unanchorable."
        ),
        prerequisites=(
            "N-19 선착지 — CA-API 존부·모의 CA 처리 여부·독립 참조원(§13.13) 확립 전 unanchorable",
            "operator가 관련 7-시각(ex/effective/payable/settlement)을 프롬프트 시 축자 기록 (P-EXT 문형)",
            "대상 종목 선행 보유 — 모의=KIS 모의투자 주문 산물 / 실전=기존 실주식 보유; 보유 0이면 확립 불가 (P-BAL 문형)",
            "선물 제외 — 모의 선물잔고 미지원(shared/kis/client.py:1031 NOTE·가드 :1047) + 실선물 무증거금·무보유",
            "READ-ONLY: GET 폴링만, 모듈에 주문 경로 없음 (P-BAL 문형)",
            "--env real 시 운영자 승인 (실 자격증명); MOCK 아티팩트는 REAL_PROD 문서 인용 불가(§6.2·ADR-002-004 §13.14)",
        ),
        entrypoint="",
    ),
```

**주의:** 두 프로브 `supported=False`이므로 `coverage_report()["unsupported"]`에 사유와 함께
자동 노출된다(기계 판독 정직성). "프로브가 정의됨(런북 §9.2 갱신) + 아직 실행 불가(사유 명시)"를
동시에 표현 — N-17이 정확히 이 상태다. **risk 표기 표↔diff 모두 `LOW`로 일치(M-4).**

---

## 9. 런북 편입 지점 (`docs/runbooks/kis-capability-probes.md`, M-status)

후속 레인이 적용할 편입(이 문서는 지정만; 행은 M-status라 섹션 번호로):

1. **§9.2 재작성** — "정의된 프로브가 없다"를 "N-19(명세-대조)·P-CA(기회주의·GET-only·N-19-gated)
   정의됨. 둘 다 `supported=False`(사유는 registry skip_reason). bound은 NOT_ESTABLISHED —
   clock (c) 지배·class×leg 표·hard 스칼라 확립 불가. 안전은 predicates.py 무수치 술어 +
   BC-AC-019 EV-L3 소관"으로. **stale 행 :815/:833 → :831/:849 교정.**
2. **§3 전수 표 + §3.1 한 줄** — N-19/P-CA 행 추가.
3. **§4.2 인접 키** — stale :815/:833/:662 → :831/:849/:678 교정, 공급 프로브 N-19/P-CA 표기.
4. **§7에 §7-CA 하위 체크리스트 신설** — N-19 4항목(§5.1)을 N-17 체크리스트와 병치. (D6은 §7이
   이미 "2026-07-29 해소"로 반영 — 재기술 불요.)
5. **신규 §5.x 절차** — P-CA 실행 절차를 §5.6(P-BAL)·§5.7(P-R5) 형식으로(선행조건·operator
   7-시각 기록·GET-only 강제·환경 파라미터·아티팩트 처리·정직 규율).

**관측 (기존 결함, 본 문서 비수정 — M-1):** registry.py P-BAL prerequisites의 client.py 행
인용(원문 그대로: `client.py:1026 NOTE, guard :1031-1033`; P-BAL prereq는 MAJOR-1發 +6로 현재 registry :761-771·M-status)은 stale — 실측 현행은 `get_futures_balance` :1023,
NOTE **:1031**, 가드 로그 **:1047**. 별개 결함이므로 관측만 기록; 교정은 registry 소관 레인.

---

## 10. 실행 시퀀스·선행조건 요약 (MAJOR-1: D6 차단 노드 제거)

```
N-19 명세-대조 (SPEC_CROSSCHECK, ENV_NONE)   ← 즉시 착수 가능: N-17이 쓴 kis-code-assistant-mcp
   │                                            조회-전용 경로. D6 조건문은 2026-07-29 운영자
   │                                            MCP 재가동 보고로 해소(대화-수준). 차단 선행조건 없음.
   ├─ 항목 1: KIS CA-API 존부  ─── UNSUPPORTED/UNKNOWN ─┐
   ├─ 항목 2: 7-시각별 반영 모델(class×leg)             │
   ├─ 항목 3: reconciliation/finality 증거              │
   └─ 항목 4: 독립 참조원(§13.13 fallback_reference)     │
        │ (참조원 + 7-시각 앵커 확보 시에만)             │
        v                                              v
   P-CA 기회주의 관측 (MANUAL, GET-only, --env)   [참조원 없으면 P-CA unanchorable]
        ├─ 모의 주식: 모의 CA 처리 여부 실측(부수 findings; REAL 인용 불가 §6.2)
        ├─ 실전 주식 GET: 유일한 REAL_PROD clock(c) 표본 (선행 보유 필요)
        └─ 선물: 제외(NOT_ESTABLISHED)
        │
        v
   class×leg 후보(candidate_only) → Bounds-Approver 판단(§6.5, 스펙-트랙 슬롯판정 §6과 연언 §7)
        → value_ms (또는 NOT_ESTABLISHED 유지)
```

**병렬 트랙 주의:** `docs/broker-profiles/`·tos-spec 템플릿(§6 수치 슬롯)과 `registry.py`(§8
적용)는 별개 레인(전부 M-status). 이 문서는 **저작 산출물**이며 적용·커밋은 후속. ADR-002-010
acceptance(§26)·live authorization은 별개 게이트.

---

## 11. 한계 (정직) + 선행 설계 정합

- KIS CA-API 존부·모의 CA 처리 여부는 **미확인**이며 N-19 산출 전까지 전 설계가 조건부다.
  "확인 못한 것은 추측"으로 명시: KIS REST의 CA 엔드포인트 존재 여부는 **추정하지 않았다** —
  grep은 *우리 배선*의 부재만 증명한다.
- **`source_and_broker_specific`의 추정량(estimand)이 미정의다 (MODERATE-7).** 런북 §8(통계
  규율)은 `hard_maximum`·`broker_specific`만 다루고 이 **제3 semantics의 추정량을 정의하지
  않는다.** 따라서 "bound이 스칼라인가·class×leg 색인 표인가·클래스 최악값인가" 자체가 스펙-트랙
  + Bounds-Approver 판단 대상이다. §5.2는 leg별 후보만 산출하고 집계 스칼라를 주장하지 않으며,
  `hard maximum` 표기를 **셀-국소**로만 쓴다(§2.1 논증과 내적 정합).
- P-CA는 안전-필수 프로브가 아니다(§3.1 대안 B). 미실행이 CORPORATE_ADMINISTRATIVE_EVENTS
  라이브를 막지 않는다 — 그 스코프는 이미 `fb§13.13` 조건부이고 안전은 무수치 술어 + EV-L3 소관.
- 이 문서는 `value_ms`도 `status` 승격도 하지 않는다. 프로브를 "정의"할 뿐 "확립"하지 않는다.
- drift 교정(§8.1 vp_line·§0.1 draft.yaml)은 **병합 시 재직독으로 재확인** — M-status 병렬 편집.

**선행 설계와의 정합 (M-5):**

- `docs/plans/2026-07-26-tos-non-trade-design.md`(ADR-002-010의 tos/nontrade 실현 설계)와 **완전
  정합**: §8.1(:245-246)이 3 NT키 실재·null을, :728(§5 row4)이 7-시각 붕괴금지(§8:171)를,
  :511/:880이 predicate-only 무수치 window(`effective_window_blocks_new_risk`)를 독립 확증한다.
  본 문서 판단 1·2를 강화. **단 그 문서는 VP-002 book판 행(646/653/660)을 인용** — 본 문서의
  src판(831/840/849)과 동일 키의 렌더 차이이며 `registry._VP`=src가 정본(§0.1). 모순 아님.
- `docs/plans/2026-08-06-…residual-17key…md` §3.4(:144-147)·§3.6(:171)이 두 키를 "프로브 부재 ·
  corporate-action reference source 착지 후 이연"으로 처분(src판 :831/:849 일치). 본 문서는 그
  **'착지' 기전**(N-19=reference source 판정, P-CA=관측)을 정의하므로 그 이연 조건을 여는
  산출물이다. 단 그 문서 §1은 "표면 부재"를 grep-0으로만 근거했고, 본 문서 §1은 그것을 "피드
  부재 ∧ 구조화 레코드 모델 실재(records.py)"로 정밀화(MAJOR-4).
