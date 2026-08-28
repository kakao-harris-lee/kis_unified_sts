# 스코핑 노트 — ②(b) env-주입 재검증의 K7·K8·K15 정합 선행 판정 (비규범·서베이·닫는 EV 0건) (2026-08-06)

> **문서 지위.** 본 노트는 #38 §10-1(`docs/plans/2026-08-05-tos-cis-injection-port-design.md:505-508`)이
> 지정한 오케스트레이터 판정의 **근거 아티팩트**다. 판정 질문: *"env-주입 재검증(#32 §9-6 — dishonest
> producer·신뢰 seam)을 dsl 시그니처 확대 없이 K7·K8·K15와 정합시킬 경로가 존재하는가?"* 본 노트가 그
> 판정의 실측 기반이 되며, 부재 시 (b) 계약 저작 착수가 금지된다(#38 §10-1·§14 :612-613). **본 노트는
> 어떤 EV도 닫지 않고 어떤 비준도 구성하지 않는다.** 서베이 형식(참조:
> `docs/plans/2026-08-05-tos-deferral-closure-scoping-survey.md`).
>
> **실측 기준선.** 전 file:line 인용은 `git HEAD 8121856a`(브랜치
> `mission-critical-trading-operating-system`) **2026-08-06 본 세션 직접 read 재측정**이다(#38 §12
> 에라타 v1.3 자기 인용 재측정 의무 이행 — `cis-port:552-557`). 설계 문서의 인용 line은 그대로 신뢰하지
> 않고 코드/테스트 표면에서 재-grep 했다.
>
> **인용 약칭.** `determinism.py`=`tos/src/tos/dsl/determinism.py` · `context_value.py`=
> `tos/src/tos/dsl/context_value.py` · `value.py`=`tos/src/tos/marketfeed/value.py` · `records.py`=
> `tos/src/tos/marketfeed/records.py` · `canonicalization.py`=`tos/src/tos/canonical/canonicalization.py`
> · `T-ctxval`=`tos/tests/dsl/test_dsl_context_value.py` · `T-determ`=`tos/tests/dsl/test_dsl_determinism.py`
> · `T-nsenv`=`tos/tests/marketfeed/test_marketfeed_namespace_and_env.py` · `T-port`=
> `tos/tests/marketfeed/test_marketfeed_cis_port.py` · `cis-port`=
> `docs/plans/2026-08-05-tos-cis-injection-port-design.md` · `mf-design`=
> `docs/plans/2026-07-29-tos-marketfeed-design.md`.

---

## A. (b)의 원문 정의 전수 인용

(b)를 판정하려면 (b)가 **무엇을 하기로 한 것인지**를 그 정의 원천에서 정확히 고정해야 한다. 세 원천
전수 인용:

**A-1. (b)의 근원 정의 — #32 §9-6**(`mf-design:660`, 슬라이스가 닫지 않는 것 목록의 6번):

> 6. **완전 side-channel/look-ahead 강제·env-주입 재검증**(dishonest producer·신뢰 seam) — 상류
>    정직·§2.3·§4.3·§5.4.

**A-2. "재검증"이 가리키는 대상 — #32 §2.3 신뢰 seam 정직 명기**(`mf-design:314-320`):

> ⚠ **신뢰 seam 정직 명기(v1.1 MAJOR-2b·Gap-1)**: 이 검증은 **marketfeed 생산 시점**에 일어난다.
> **env-주입 지점(`build_environment`)은 값⟺digest를 재검증하지 않고** 발행된 `ContextValueView`를
> 신뢰한다. 즉 부정직·버그 producer가 payload_digest와 불일치하는 값을 실은 view를 발행하면 env가
> 그대로 소비한다 … D-E2 봉인: (a) 생산자 검증 + property·(b) **서명 append** … (c) 완전 강제는 상류
> Context Integrity Service. over-claim 금지: 구조 바인딩은 생산자 검증 + 서명 검출을 주지 env-주입
> 지점의 재검증을 주지 않는다.

**A-3. (b)의 경계·판정 지정 — #38 §0.3·§10-1**(`cis-port:96-100`, `:505-508`):

> §0.3: `build_environment`/`evaluate_resolved`가 발행된 `ContextValueView`의 값⟺digest를 재검증하는
> 계약(#32 §2.3·§9-6)인데, **재검증에 필요한 `scheme`/검증자를 진입점에 실으면 K7 정확-집합 잠금 …을
> 깨거나 ambient smuggle이 된다.** ⇒ (b)는 K7 정합 선행 판정이 필요한 별개 이연으로 잔존.
>
> §10-1: (b) 착수 전, 오케스트레이터가 "재검증을 시그니처 확대 없이 K7·K8·K15와 정합시킬 경로가
> 있는가"를 판정하고 … **그 아티팩트 부재 시 (b) 저작 착수 금지.**

**A-4. (b)의 소유 — #38 §3.4 N3 행**(`cis-port:286`): `| N3 | env-주입 재검증 | **비-보장** | **②(b)** |
**K7·K8·K15 GREEN** |`. N1(as-of distinctness)=상류 CIS 소유와 **다른 소유**임을 §3.4 정합 주석
(`:288-290`)이 못박는다.

> **(b)의 고정된 의미(A-1~A-4 종합).** (b) = "env-주입 지점(dsl `build_environment`/`evaluate_resolved`)에서
> **값⟺digest를 재검증**한다." 여기서 "값⟺digest"는 §2.3이 명시한 **부정직 producer가 `payload_digest`와
> 불일치하는 값을 실은 view**를 잡는 것 — 즉 각 `ContextValue.value`가 그 `payload_digest`가 어드레스하는
> covered payload에서 나왔는지를 소비 지점에서 다시 확인하는 것이다. 이하 이 정확한 대상을 **A1 공격면**
> 이라 부른다. (b)의 정의는 뷰 자기-digest 자기정합(A2)이나 capsule↔뷰 바인딩(A3)이 **아니다** — 이
> 구별이 판정의 핵심이다(§C).

---

## B. 잠금·발명금지의 현 HEAD 실측 (8121856a)

### B-1. K7 — dsl 진입점 시그니처 정확-집합 잠금 (2중)

| canary | 위치(재측정) | 정확히 잠그는 것 |
|---|---|---|
| K7-a (원본·#32 에라타가 인용) | `T-determ:136-146` `test_evaluate_signature_exposes_no_ambient_source` | `set(inspect.signature(evaluate).parameters) == {strategy, capsule, config, scheme, enforcement_mechanism_version}` + ambient-이름 부재 |
| K7-b (#38이 K7로 인용) | `T-ctxval:316-324` `test_evaluate_is_unchanged...` | 동일 5-집합 |
| K7-c | `T-ctxval:327-361` `test_evaluate_resolved_has_its_own_locked_signature` | `evaluate_resolved` 정확-집합 = 5 + `resolved_context`, **ambient 배제** `not set(params) & {clock, now, time, random, rng, network, session, fetch, fetcher, loader, callback}` (`:344-356`), scheme/enforcement/resolved_context keyword-only |
| K7-d | `T-ctxval:363-368` `test_evaluate_resolved_adds_exactly_one_parameter_to_evaluate` | `resolved - plain == {resolved_context}` **및** `plain - resolved == set()` — **"정확히 +1"** |

**핵심 관찰 1(크럭스에 결정적):** `evaluate`·`evaluate_resolved`는 **이미 `scheme` 파라미터를 보유**한다
(`determinism.py:324`, `:367`; `scheme: Any` keyword-only). 테스트가 `SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)`을
그대로 주입한다(`T-ctxval:68`, `:379`, `:401`). 즉 **재검증에 필요한 scheme은 진입점 시그니처 확대 없이
이미 도달 가능**하다 — §0.3이 우려한 "scheme을 진입점에 실으면 K7 깨짐"은 **`evaluate_resolved`에는
해당하지 않는다**(scheme이 이미 5-집합 안에 있음). 이 사실은 판정을 §0.3의 표면 논거(시그니처)에서
**더 깊은 크럭스(digest 함수 도달성·preimage 부재)**로 옮긴다(§C).

### B-2. K8 — `build_environment.resolved_context` 잠금 (부분)

`T-ctxval:263-267` `test_the_resolved_context_parameter_is_keyword_only`: `build_environment`의
`resolved_context` 파라미터가 **KEYWORD_ONLY + default None**임만 단언. **build_environment의 전체
파라미터 집합은 잠그지 않는다.** 인접 canary `T-determ:165-172` `test_build_environment_is_pure_and_ambient_free`는
**출력 env 키**(`set(e1.keys()) == {"capsule","config"}`)와 결정성(e1==e2)만 단언하지 **파라미터 집합은
아니다.** ⇒ **반례 명시(전칭 주장 회피):** "build_environment 시그니처가 잠겨 있다"는 **거짓**이다. build_environment에
파라미터를 추가해도 어떤 committed 정확-집합 canary도 직접 터지지 않는다. (그럼에도 build_environment는
dsl 공개 진입점이며 추가는 발명금지 "dsl 시그니처 확대"의 정신에 저촉 — §C 경로 A.)

### B-3. K15 — value-free env byte-identical

`T-nsenv:192-200` `test_the_value_free_environment_is_byte_identical_to_the_pre_d_e2_one`:
`build_environment(capsule, _CONFIG) == legacy` **및** `build_environment(capsule, _CONFIG, resolved_context=None) == legacy`.
dsl-측 거울: `T-ctxval:255-260`. ⇒ **`resolved_context is None` 경로에 착지하는 어떤 변경도 K15를 깬다.**
재검증을 value-free 경로 밖(`resolved_context is not None`일 때만)에 두면 K15 보존.

### B-4. 발명금지 실측 (재검증이 저촉할 표면)

| 발명금지 | 현 HEAD 실측 근거 | 재검증이 저촉하는가 |
|---|---|---|
| capsule/**carrier 모델 변경 금지** | `ContextValue` 필드 = `{field_key, value, as_of, payload_digest, observation_ref}` **정확 잠금**(`T-ctxval:162-172`)·**preimage 필드 0**(`context_value.py:117-121`; grep 0 hits) | A1 재검증에 preimage가 필요 → carrier 필드 추가 → `T-ctxval:162-172` FAIL |
| dsl 시그니처 확대 금지 | K7(§B-1) | evaluate_resolved는 scheme 이미 보유(무저촉); build_environment 추가는 시그니처 확대 |
| over-claim 금지 | 신뢰 seam 문장 pin: carrier docstring `context_value.py:26-34` "does **not** re-verify … No over-claim is made here"; value.py docstring `:35-37` "does not re-verify it"; P3 positive pin `T-port:551-565`·trust-seam 문장 pin `T-port:603-620` | 재검증을 "producer 정직 강제"로 문서화하면 P3 co-occurrence seal FAIL(`T-port:567-624`) |
| K1 as-of 게이트 무변경 | `test_marketfeed_distinctness.py`(K1)·발행 게이트 as-of | (b)는 env-주입 지점·K1은 발행 게이트 → 무저촉 |

### B-5. 재검증 메커니즘의 소재 (도달성 실측 — 크럭스)

- **A1 검증기**(값⟺payload_digest) = `value.py:508-517` `_admit_one`: `scheme.compute_digest(candidate.preimage.as_mapping()) == payload_digest`.
  입력 `candidate.preimage`는 **`AdmittedValue`(후보)에만 존재**(`records.py:160` `preimage: RawPayloadPreimage`;
  `as_mapping` `records.py:124`)하고 **발행된 `ContextValue`에는 없다**(§B-4). 생산 시점에 소비·폐기됨.
- **A2 검증기**(뷰 자기-digest) = `value.py:441-460` `view_digest_matches` → `context_value_view_digest`
  (`value.py:408-438`) → preimage 형태 `_covered_view_content`(`value.py:385-405`, **뷰 자기 필드만** 사용) +
  주입 `scheme`. **뷰 자기 필드에서 재계산 가능**하나, 함수가 **`tos.marketfeed`에 소재**.
- **import 방화벽(F1)**: `tos.dsl`은 **`tos.marketfeed`를 import 하지 않는다**(src grep 0 hits; F1 아키텍처
  `context_value.py:3-12` "no `dsl -> marketfeed` … edge exists, so the cycle has no origin"). dsl은
  `tos.canonical`은 import 가능(`tos/src/tos/dsl/_base.py:39`) → `get_scheme`(`canonicalization.py:235`)·
  `scheme.version`(`:201`)·`CanonicalizationScheme` Protocol(`:62`, `compute_digest` `:76`)은 dsl에서 도달
  가능하나, **digest preimage 형태(`_covered_view_content`)는 marketfeed 소유**.
- **현 소비 지점 실측**: `_evaluate`(`determinism.py:277-316`)는 merge(`build_environment` :292)·`evaluate_policy`·
  outcome 조립·서명 append(`:298-303`, `resolved_context is not None`일 때 `view.canonical_digest`를
  `captured_external_value_refs`에 append)만 수행. **`view_digest_matches` 호출 0·snapshot 바인딩 재검사 0**
  (grep: determinism.py의 `critical_input_snapshot` 유일 사용은 `:157` 서명 포인터). 즉 **오늘 evaluate_resolved은
  일체 재검증하지 않는다** — 이것이 (b)가 채우려는 정확한 공백이다.

---

## C. 후보 경로별 정합 분석

### C-0. 공격면 분류 (재검증이 "무엇을 새로 닫는가"의 정확한 델타)

env-주입 지점이 받는 것: `capsule`(frozen·`SnapshotRef`만·body 없음)·`config`·`resolved_context`(발행된 뷰).
받지 **않는** 것: snapshot **body**·observations·candidate **preimage**·(build_environment의 경우)scheme.
부정직 producer/resolver(발행 게이트 `publish_context_value_view`를 충실히 쓰지 않는 자)의 공격면:

| 공격 | 무엇인가 | 잡으려면 필요한 입력 | env-주입 지점에서 도달? |
|---|---|---|---|
| **A1** | value ⟺ payload_digest 불일치(§2.3·§9-6이 **명명한 그것**) | payload **preimage** + snapshot-covered **observation body** | **불가** — preimage는 carrier에 없음(§B-5)·body는 env에 없음 |
| **A2** | `canonical_digest` ⟺ `values` 자기정합 불일치 | 뷰 자기 필드 + scheme | 재계산 가능하나 digest 함수가 marketfeed(§B-5) |
| **A3** | 뷰가 capsule의 `SnapshotRef`와 다른 snapshot에 바인딩 | capsule + 뷰(둘 다 보유) | **가능**(scheme·marketfeed 불요) |

**결정적 비대칭(위험-가중).** **A1(고위험·결정 오염: 거짓 값이 결정을 바꿈)은 env-주입 지점에서 구조적으로
잡을 수 없다.** A2(저위험: 값이 정직하면 결정은 정상·digest 거짓은 감사 포인터만 오염)와 A3(저위험·상류
게이트 재라벨)만 잡힌다. §9-6이 (b)로 명명한 것은 A1이다.

### C-1. 경로 대조표

| 경로 | 형태 | K7 | K8 | K15 | 발명금지 | 무엇을 실제로 닫나 | 판정 |
|---|---|---|---|---|---|---|---|
| **A** `build_environment` 본문 재검증 (`resolved_context is not None`일 때만) | A2를 build_environment에서 | build_environment 정확-집합 canary **부재**(§B-2)이나 scheme 추가=dsl 시그니처 확대 | resolved_context kind/default 무변경→**OK** | value-free 경로 무변경→**OK** | **저촉**: digest 함수가 marketfeed(dsl→marketfeed edge 금지·§B-5) or preimage 형태 dsl 재구현(DRY·drift) | A2뿐(A1 preimage 부재로 불가) | **충돌/불가** — import edge + preimage 부재. 근본 blocker는 시그니처가 아니라 도달성 |
| **B** 제3 진입점 `evaluate_reverified` | 새 dsl 함수 | K7-d(`T-ctxval:363-368`)는 evaluate/evaluate_resolved **쌍만** 대조 → 제3 함수 **무직접저촉**; 단 제3은 자체 ambient-배제 잠금 요구(K7-c 선례) | 무관 | 무관 | 동일 import edge/preimage blocker 상속 | A1 여전 불가·A2 여전 edge-blocked | **충돌** — 문제를 이동시킬 뿐 크럭스 미해결 + 진입점 증식(#32 에라타가 2번째로 이미 고비용 지불·`determinism.py:385-396`) |
| **C** `ContextValueView` 구성-시점 자기검증 승격 | frozen validator가 digest 재계산 | 무관(시그니처 아님) | 무관 | 무관 | **committed 테스트 다수 파괴**: `_view(digest="view-0"/"view-alpha"/"view-high"/"view-low")`·`canonical_digest="d"`로 뷰를 합성 digest로 구성하는 `T-ctxval:96-112,222-235,238-247,394-443` 전부 FAIL(validator가 실제 digest 요구) → "committed 테스트 파괴 0" 위반 | A2뿐(preimage 부재로 A1 불가); **과잉 봉합**(정직한 합성-digest 테스트 구성까지 거부) | **충돌** — 광범위 canary 파괴 + 근-공허 A2 + 과잉 봉합(그 자체 결함) |
| **D** resolver/포트 층 재검증 | marketfeed resolver에서 재검사 | 무관(dsl 진입점 무접촉) | 무관 | 무관 | 무저촉이나 resolver는 `publish_context_value_view`로 뷰를 **생산**(`value.py:661-672`·digest를 by-construction 정확 계산) → 자기 방금 생산물 재검사 | **공허**(정직 생산자 자기산출물 재확인); A1은 여기서 이미 발생(`value.py:508-517`) | **재라벨·공허** — "env-주입 재검증"이 아니라 이미 있는 생산 게이트. (b) 정의 미충족(§A 정직 판정) |
| **E**(자체발굴) capsule↔뷰 바인딩 재검사 @evaluate_resolved | `view.snapshot_id/digest == capsule.critical_input_snapshot.*` | 시그니처 무변경(capsule·뷰 이미 보유)→**OK** | 무변경→**OK** | value-free 무변경→**OK** | 무저촉 | **A3뿐** — value⟺digest(§9-6)가 아니라 capsule↔뷰 바인딩(ADR-002-018 §15 = G1 재라벨). 커밋 아키텍처에선 resolver가 by-construction 바인딩(`value.py:594`)→근-공허 | **정합하나 off-point** — (b) 정의(§9-6 value⟺digest) 미충족·근-공허 |

### C-2. 경로별 상세 판정 근거

**경로 A — 불가(도달성).** §0.3은 "scheme을 진입점에 실으면 K7 깨짐"을 blocker로 들었으나, 실측상
`evaluate_resolved`은 이미 scheme을 보유하므로(§B-1 관찰1) 시그니처는 A의 진짜 blocker가 아니다. 진짜
blocker는 둘: (i) A2 재계산 함수(`context_value_view_digest`)가 `tos.marketfeed`에 있고 dsl은 marketfeed를
import할 수 없다(F1·§B-5) — build_environment/`_evaluate`가 이를 호출하면 `dsl→marketfeed` edge 신설로
engine import-closure allowlist(14패키지·marketfeed 부재) 위반·`engine→dsl→marketfeed→…` 순환. (ii)
dsl이 preimage 형태를 **재구현**하면(marketfeed `_covered_view_content` 복제) DRY 위반 + **drift 위험**
(두 preimage 정의가 byte-동일을 유지 못하면 정직한 뷰를 거부 — #35 submodule-drift 교훈). 그리고 A가
겨냥할 수 있는 것은 A2뿐이며 A1(§9-6이 명명한 것)은 preimage가 carrier에 없어(§B-5) 원리적으로 불가.

**경로 B — 충돌(이동·증식).** K7-d의 "정확히 +1" 잠금은 `evaluate_resolved − evaluate == {resolved_context}`
및 `evaluate − evaluate_resolved == ∅`만 단언(`T-ctxval:365-368`) — 제3 함수 `evaluate_reverified`의 존재
자체는 이 쌍-대조에 무직접저촉. 그러나 (i) 제3 진입점도 A2 재계산에 marketfeed digest 함수가 필요(A와
동일 edge blocker), (ii) A1은 여전히 preimage 부재로 불가, (iii) `evaluate_resolved` 도입 시 #32 에라타가
"neutered-canary 방지 위해 별도 진입점"이라는 큰 비용을 이미 치렀는데(`determinism.py:385-396` 장문 정직
기록) 제3은 그 비용을 배가한다. 크럭스 미해결.

**경로 C — 충돌(canary 파괴 + 과잉 봉합).** `ContextValueView`에 digest 재계산 validator를 달면: (i)
validator는 `get_scheme(self.canonicalization_version)`로 scheme 도달 가능(dsl→canonical 허용)하나 preimage
형태는 여전히 marketfeed 소유(재구현 시 DRY·drift), (ii) **결정적 문제**: 커밋된 dsl/marketfeed 테스트가
뷰를 **임의 합성 digest**로 구성한다 — `_view(digest="view-0")`(`T-ctxval:96-112`)·중복키 테스트
`canonical_digest="d"`(`:222-235`)·explicit-empty `"d"`(`:238-247`)·서명 append 테스트
`"view-high"/"view-low"`(`:394-443`). digest-재계산 validator는 이들을 전부 거부 → "committed 테스트 파괴
0"(#38 sanction 전제) 위반. 특히 `:409-443`은 **임의 digest로 뷰를 구성할 수 있어야** 서명 append를
검증하므로, validator는 그 테스트의 성격 자체를 파괴한다. 게다가 이는 **과잉 봉합**(정직한 합성-digest
구성까지 거부) — 코퍼스 규율상 과잉 봉합 자체가 결함. 그리고 여전히 A2뿐(A1 불가).

**경로 D — 재라벨·공허.** resolver(marketfeed)는 `SnapshotStore`+`ValueCandidateSource`(candidates)를
주입받아(#38 §2.1) **스스로** `publish_context_value_view`를 호출해 뷰를 생산한다(`value.py:562-688`).
그 생산이 이미 A1을 수행한다(`value.py:508-517` value⟺payload_digest against covered observation). 따라서
resolver가 방금 생산한 뷰를 다시 검사하는 것은 **정직 생산자의 자기 산출물 재확인 = 공허**(`view_digest_matches`는
by-construction 참). 그리고 이는 "env-주입 재검증"이 아니라 **생산-시점 검증** — (b)의 정의(A-2: "env-주입
지점은 재검증 안 함")를 재라벨한 것이지 충족한 것이 아니다. (참고: slice e2e 테스트가 이미 뷰 자기정합을
슬라이스 층에서 단언한다 — `tos/tests/slice/test_slice_end_to_end.py:87` `view_digest_matches`·
`test_marketfeed_value_binding.py:79` — A2 자기정합은 이미 생산/슬라이스 층에서 커버됨.)

**경로 E(자체발굴) — 정합하나 off-point·근-공허.** `evaluate_resolved`에서 `resolved_context.snapshot_id ==
capsule.critical_input_snapshot.snapshot_id AND …canonical_digest 동일`을 재검사. capsule·뷰 둘 다 보유
→ 시그니처 무변경(K7 OK)·K8 OK·value-free 무변경(K15 OK)·marketfeed import 불요·preimage 불요. **정합
가능**. 그러나 이것은 **capsule↔뷰 바인딩**(ADR-002-018 §15·발행 게이트 G1 `snapshot_binds_capsule_reference`
`value.py:139/594`의 재라벨)이지 **value⟺digest**(§9-6)가 아니다 — (b)의 정의를 충족하지 않는다.
또한 커밋 아키텍처에서 resolver가 뷰를 capsule의 snapshot에서 by-construction 생산하므로 정직 경로에선
결코 미스바인딩이 없어 **근-공허**(out-of-band 주입된 뷰에만 물림). defense-in-depth 카나리로는 유효하나
(b)로 팔아선 안 됨.

---

## D. 판정 권고

### D-1. 판정: **on-point·비-공허·정합 경로 = 부재.** signature-compatible 경로 = 공허 or off-point.

세 술어를 동시에 만족하는 경로는 존재하지 않는다:
- **(i) on-point** — (b)가 §9-6/§2.3에서 정의한 그 재검증(A1: value⟺payload_digest, dishonest producer),
- **(ii) 비-공허** — #38 확립 규율("비-공허 논증 = 오늘 단언되지 않는 것의 정확한 델타"·`cis-port:520-529`),
- **(iii) K7·K8·K15-safe + 발명금지 준수(시그니처 확대·carrier 모델 변경 없이).**

근거(구조적·실측):

1. **on-point 재검증(A1)은 env-주입 지점에서 원리적으로 불가.** A1을 재계산하려면 payload **preimage**
   (`records.py:160`·후보에만·발행 뷰엔 없음 `context_value.py:117-121`)와 snapshot-covered **observation
   body**(env에 없음·capsule은 `SnapshotRef`만)가 필요하다. 둘 다 **carrier가 의도적으로 버린 것**
   (lean container·`context_value.py:18-24`)이고 env가 담지 않는 것이다. 이를 소비 지점으로 들이려면
   carrier에 preimage 필드 추가(`T-ctxval:162-172` FAIL·carrier 모델 변경 금지 저촉) 또는 snapshot
   store/body를 dsl 진입점에 threading(env/시그니처 확대 + 이는 CIS의 검증 맥락 전체를 seam으로 재수입 =
   §0.1 방화벽 판정과 정면 충돌)이 필요하다 — **전부 발명금지가 봉쇄**한다.
   - **선제 반론(유일한 이론적 우회 봉쇄).** producer가 preimage를 `capsule.bindings`(저작자-상수
     채널)에 자기신고로 실어 env로 나르면 A1 재검증이 가능한 듯 보이나 — (i) 이는 **자기신고를
     자기신고로 검증하는 순환**(producer가 값과 preimage를 동시 공급 → "구조 파생 > 자기신고" 정면
     위반)이고, (ii) 시장값을 `config`/bindings로 나르는 것은 §3.2 alt-D가 기각한 **G10 재라벨링**
     (RFC-008 §10:327-331·RFC-004 §9:251-252 금지)이다. 이 우회는 판정을 흔들지 않고 **강화**한다:
     A1의 유일한 이론적 거처마저 발명금지가 봉쇄함을 보이므로.

2. **K7·K8·K15-safe한 재검증(A2·A3·E)은 근-공허 또는 off-point.** A2(뷰 자기정합)는 (a) marketfeed
   import edge에 막히고(dsl→marketfeed 금지), (b) 값이 정직하면 결정은 정상이라 잡히는 것은 **감사
   포인터 오염뿐**(저위험)이며, (c) 그마저 서명 append(`determinism.py:298-303`)+replay 재구성 모델
   (D-E3·§5.4)에서 이미 검출 가능하고, 슬라이스 층이 이미 `view_digest_matches`를 단언한다
   (`test_slice_end_to_end.py:87`). A3/E는 **value⟺digest가 아닌 capsule↔뷰 바인딩**(G1 재라벨)이며 커밋
   아키텍처에서 근-공허. 어느 것도 "오늘 단언되지 않는 것의 정확하고 유의미한 델타"가 아니다.

3. **위험-가중 비대칭(판정의 심장).** 잡히는 것(A2·A3)은 결정을 바꾸지 않는 저위험 사건이고, 결정을
   오염시키는 고위험 사건(A1)은 이 seam에서 잡을 수 없다. 따라서 env-주입 지점은 (b)가 겨냥한 위협에
   대해 **구조적으로 잘못된 장소**다. 완전 강제가 상류 CIS 소관이라는 #32 §0.2-4(`mf-design:125-126`)·
   #35 §10-4·#38 §3.3/N3(`cis-port:266`/`:286`)의 배치는 **정확**하다 — 재량이 아니라 도달성의 귀결.

> **⇒ 오케스트레이터 판정 권고: "정합 경로 부재"로 판정하라.** 단 이는 "방법을 못 찾음"이 아니라
> **"(b)가 명명한 대상이 env-주입 지점에 비-공허한 거처를 갖지 않음"**이다. 그 강제는 이미 상류 CIS에
> 정당 배치돼 있고(§0.2-4·N3), 그 검출은 이미 서명 append가 제공한다(`determinism.py:298-303`·
> `T-ctxval:409-443`). #38 §10-1의 게이트 판정으로서, **(b)를 "env-주입 재검증"의 형태로 저작 착수하는
> 것은 금지 유지**가 옳다.

### D-2. (b)의 정직한 재처분 (권고)

(b) 계약 #39가 저작된다면, 그것은 재검증을 **구현**하는 계약이 아니라 **§0-판정 아티팩트**여야 하며, 본
노트를 근거로 다음 중 하나를 등재한다:

- **(재처분 I·권장) 라인 흡수·재라벨 은퇴.** "②(b) env-주입 재검증"을 **오분류로 정직 은퇴**하고, 그
  강제를 (1) 상류 CIS 런타임 이연(#38 §10 항목2·`cis-port:509`·방화벽상 tos 안팎 불가 §0.1)과 (2) D-E3
  replay look-ahead 강제 이연(§5.4)으로 흡수한다. 별개 이연 라인으로서의 "(b)"는 폐기(닫는 EV 0·비준
  아님). 근거: on-point 재검증의 유일한 거처는 입력이 존재하는 상류(CIS)·replay(D-E3)이며 dsl 진입점이
  아니다.
- **(재처분 II·검토 후 기각) seam에 좁은 defense-in-depth 카나리 신설.** 오케스트레이터가 seam에
  committed 방어(경로 E capsule↔뷰 바인딩 재검사, 및/또는 경로 A2 뷰 자기정합)를 둘 수 있으나 —
  **검토 후 기각**한다. 기각 사유 3축:
  1. **경로 E는 근-공허** — resolver가 뷰를 capsule의 snapshot에서 by-construction 생산
     (`value.py:594`/`:661`)하므로 정직 경로에서 **결코 발화하지 않는다**; out-of-band 주입된 뷰에만
     물리는 가드는 실 파이프라인에서 죽은 코드.
  2. **경로 A2(relocated)는 F1 소유권 역전 + 미측정 파장** — A2를 dsl에서 하려면
     `context_value_view_digest`를 `tos.dsl`로 이전해야 하는데, 이는 #32 F1이 확정한 **소유권 분할
     (marketfeed=생산·검증 / dsl=carrier)의 역전**이며(`context_value.py:14-16`·`mf-design:93-96`),
     marketfeed `__all__`(`value.py:82-93`)·P-tests·순수층 import-closure(`value.py:6`) 파장은 **미측정**
     (§E-2). 비용이 이득(근-공허 A2)을 압도.
  3. **발화하지 않는 committed 가드 = 과잉 봉합 결함류(#26 WDR 선례).** E도 A2도 A1을 닫지 않는다.
     seam에 "재검증" 이름표를 단 가드가 상주하면 **A1이 덮였다는 거짓 안심**을 만든다 — 실제로는
     고위험 A1이 여전히 상류에만 걸려 있는데. 정직 문서화(P3 강제·`T-port:567-624`)로 이 오해를 사후
     봉인할 수는 있으나, 오해를 만들고 다시 봉인하는 것보다 **가드를 두지 않는 편이 정직**하다.
  ⇒ **#39가 열릴 경우에도 재처분 II를 기본값으로 부활시키지 말 것.** 방어가 필요하면 그것은 A1의 실
  거처(상류 CIS·D-E3 replay)에 두어야지 seam의 대리 가드로 두지 않는다.

### D-3. (b) 미밀수 canary와의 무충돌 확인 (P1-P5)

(b) 관련 어떤 형태(A2/A3/E)도 **포트 canary P1-P5(`T-port`)와 충돌하지 않는다**: P1(Protocol 표면·
`:175-299`)·P2(생성자 required 주입·`:333-372`)·P5(exclusivity 뮤테이션·`:375-427`)는 marketfeed 포트
표면만 잠그고 dsl 진입점 무접촉; P4(포트 경계 게이트·`:626-697`)는 생산 게이트 재실증. **단 P3(over-claim
seal·`:567-624`)은 능동 가드** — over-claim하는 (b) 문서화를 정확히 FAIL시킨다. 이는 재처분 II 기각
사유 (iii)과 정합한다: P3이 강제하는 정직 기재는 II가 만드는 '거짓 안심'을 사후 봉인할 뿐이므로, 애초에
가드를 두지 않는 편이 낫다. **무충돌의 함의(정직):** (b)의 기각은 **잠금 충돌이 아니라 공허성·off-point
때문**이다 — A2/A3/E는 K7·K8·K15와 value-free 경로·시그니처 무변경으로 정합 *가능*하다(재처분 I은 구현
0이라 자명 GREEN). **정합 가능성이 (b) 착수를 정당화하지 못한다**는 것이 §D-1 판정의 핵심이다.

---

## E. 확인하지 못한 것 (정직 보고)

1. **build_environment 파라미터 집합 잠금의 완전성.** §B-2에서 `T-ctxval`·`T-determ`·
   `test_dsl_import_closure.py`를 재측정해 build_environment 전체 파라미터-집합 canary **부재**를 확인했으나,
   전 `tos/tests/dsl/*` 파일을 전수 grep하지는 않았다. 다른 파일에 exact-set 잠금이 있으면 경로 A의 "시그니처
   미저촉" 서술이 강화될 뿐(A는 이미 import edge로 사망) 판정은 불변. REGREP 소관.
2. **A2 digest 함수의 dsl 이전이 marketfeed canary를 깨는지.** 재처분 II의 A2 옵션은
   `context_value_view_digest`/`_covered_view_content`의 `tos.dsl` 이전을 전제하는데, 그 이전이 marketfeed
   `__all__`(`value.py:82-93`)·P-tests·import-closure(marketfeed 순수층 closure `value.py:6`)를 깨는지는
   **시뮬레이션하지 않았다.** 이는 A2-relocated 옵션의 비용 측면 — 별도 구현-시점 실측 필요.
3. **replay 재구성 모델의 현존성.** "A2는 replay에서 검출 가능"은 replay가 저장된 digest를 신뢰하지 않고
   candidates에서 뷰를 **재구성**하는 D-E3 모델을 전제한다(§5.4·이연). 그 재구성 경로의 구현 현황은 이
   노트 범위 밖 — D-E3 소관. (단 A2 미검출도 결정을 바꾸지 않으므로 판정에 무영향·§C-0 비대칭.)
4. **서베이 상속 인용.** #38이 서베이에서 상속한 K10 engine 잠금·#31/#33 인용은 본 판정에 무관해 재측정
   생략(§B는 K7/K8/K15 + carrier/digest 표면만 대상).
5. **실행 무수행.** 본 노트는 분석 아티팩트다. 어떤 테스트도 실행하지 않았다. 가령 seam 방어(재처분
   II·기각)를 구현하더라도 그 full-suite 통과 여부는 구현·적대적 코드 리뷰 소관이지 본 아티팩트의
   주장이 아니다.

---

## F. 오케스트레이터 판정 (2026-08-06, #38 §10-1 지정 권한 행사)

1. 본 노트를 §10-1 판정 아티팩트로 **채택**한다. 판정: **"on-point·비-공허·K7/K8/K15-정합인 env-주입
   재검증 경로는 부재한다."** 독립 검증 SOUND(A1 구조적 불가의 반례 사냥 실패 — capsule dump 전문
   스캔·dsl 전체 preimage 0회 포함).
2. **재처분 I 채택**: "②(b) env-주입 재검증" 이연 라인은 **misnomer로 종결**한다. (b)가 명명한 위협
   (A1)의 집행 의무는 상류 CIS 이연(#38 §10 item 2)과 D-E3 replay(#32 §5.4)에 이미 귀속되어 있으며,
   이 종결은 그 귀속이 재량이 아니라 도달성의 귀결임을 확정한다. **계약 #39는 열지 않는다.**
3. 재처분 II는 **검토 후 기각**(§D-2 강등 절 참조).
4. 후속 지시: #38에 에라타 v1.4(§0.3 근거 정정 — `evaluate`/`evaluate_resolved`는 이미 `scheme` 보유·
   실제 차단자는 marketfeed import edge와 preimage 부재 — + §10-1 종결 마킹)를 적용한다.
5. 이로써 이 세션 레인에 배정된 D-E2 계열 이연은 전부 처분 완료된다. 이 판정은 어떤 EV도 닫지 않고
   어떤 비준도 구성하지 않는다.

---

<!-- 저작 증거·닫는 EV 0·비준 아님. 본 노트는 #38 §10-1 판정 아티팩트이며, 오케스트레이터 판정은
§F에 정본으로 기록된다(재처분 I 채택·(b) misnomer 종결·#39 미개시). 전 file:line = HEAD 8121856a 재측정. -->
