# P0-1 잔여 17키 처분 패키지 — Bounds-Approver 검토 준비물 (초안, 2026-08-06)

> **문서 성격 (필수 고지).** 본 문서는 **비규범(non-normative) draft**다.
> **비준 대상이 아니며, 아무것도 승인하지 않고, 어떤 승인 효력도 없다.** 승인은
> 오직 Bounds-Approver(운영자)의 행위다(role-scheme/disposition §1, `docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md:16`).
> 본 문서는 `VERIFICATION-PROFILE-002.yaml`을 **수정하지 않으며**(YAML 무변경),
> **커밋하지 않는다.** 산출물은 오직 이 검토 준비 문서 1건이다.
> 선례 형식 정본 = `docs/plans/2026-07-29-tos-phase0-bounds-draft-package.md`(이하 "선례 패키지").
>
> 본 문서가 다루는 대상 = P0-1 프로파일-레벨 승인(2026-07-29, scope-limited, 커밋 `53980b64`) **이후**
> 잔존하는 **17개 null·key-level unapproved·fail-closed 키**의 처분 권고다. 실측 기준 = 증거 수집 baseline
> HEAD `209295b2`; 본 개정 시점 현 HEAD `65cb94df`로 재확인했다 — 그 사이 커밋이 `VERIFICATION-PROFILE-002.yaml`을
> 건드리지 않았음을 검증(`git log 209295b2..HEAD -- <VP>` = 공백)했고, 17키의 행번호·값·상태를 3자 재실측해 동일함을 확인했다.

> ---
>
> **[2026-08-07 — 승인됨. 위 성격 선언은 저작 시점(2026-08-06) 정확했고 재작성하지 않는다.]**
>
> 위 문단의 "비준 대상이 아니며, 아무것도 승인하지 않고, 어떤 승인 효력도 없다"는 **본 문서 자신의 성격**에
> 대한 진술로서 여전히 옳다 — 승인 효력은 문서가 아니라 **§6에 기입된 운영자 행위**에서 나온다. 그 행위가
> **2026-08-07에 발생**했다: 운영자(Bounds-Approver) 응답 축자 **"1. a, 2. 승인. 3. 선물 계좌는 추후 모의
> 운영 서버에서 실행."** 중 **2번이 본 패키지 승인**이다. 따라서 본 문서의 현재 지위는 **"승인 대기 초안"이
> 아니라 "승인 기입이 완료된 검토 준비물 + 승인 기록면(§6)"**이다. **§1–§5·§7·부록 본문은 승인 시점 그대로
> 보존**한다(권고가 무엇이었는지가 승인의 대상이므로 사후 재작성은 승인 내용을 흐린다).
>
> **stale 자기서술 2건(정직 관측, 해소하지 않고 표기만)**: (1) 위 "**커밋하지 않는다**"와 §7의 "커밋 없음"은
> **저작 시점 작업 규율**이며, 본 문서는 이후 **`7368e7c3`으로 실제 커밋**됐다. (2) 위 "**YAML 무변경**"도
> 저작 시점 사실이다 — 승인 결과로 `MIN_evidence_retention_ms` 1키의 값 기입이 **별도 편집 작업**으로
> 수행됐다(§6 "프로파일 반영 여부" 참조). 두 진술 모두 **저작 시점 규율의 기록**으로 남긴다.
>
> **승인 후 현재 상태 요약**: **147/163 승인 · null 16키 잔존**(브로커 10 = P0-2 측정 대기 + 인스턴스/
> 아키텍처 6 = 트리거-결부 이연 **비준**). **이연 비준은 값 승인이 아니다** — 6키는 key-level unapproved·
> fail-closed 그대로이며, 각 트리거는 §4가 정본이다.

---

## 0. 이 문서가 무엇인가 — 환경 스코프·실측 규율

### 0.1 환경 스코프 (선례 §0:31–49 계승)

프로파일 `scope.environment: non-live-test`(YAML:59). 여기서 논하는 값·처분은 전부 **EV-L1~L3 테스트 하네스**
소관이며 **live 운영 캘리브레이션이 아니다.** 프로파일은 이미 **profile-level APPROVED(scope-limited)** 상태다
(YAML 헤더 :38–49; `version: "2.1"` :52 · `status: APPROVED` :53 · `approved_by: ["operator"]` :54 ·
`effective_from: 2026-07-29` :55 · `review_due: 2027-01-29` :56). 그 승인은 **값을 가진 146키에 한정**되고,
잔여 17키는 프로파일 헤더 규칙(YAML:10–16)에 따라 **key-level unapproved·fail-closed**로 남는다(YAML:30–31; :32–34는
P0-1 프로파일-레벨 승인으로 대체된 이전 PROPOSED-상태 텍스트라 인용에서 제외).
gate-status **§4 currency-note(:1058)**가 동일하게 기록하며, **§3.22(:783 헤더 · 부분승인 기록 본문)**가 동반
기록이다(`tos-spec/src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md`).

### 0.2 이 문서가 명시적으로 준수하는 규율

- **broker-agnostic**(선례 §3). 브로커 고유명사·특정 시장 미시구조 값 미등장. 브로커 의존 값은 "P0-2 측정 이연"으로만 표기.
- **값 발명 금지.** 브로커 10키는 값 제안을 **절대 하지 않는다**(프로파일 헤더 규칙 YAML:11–13 — "MEASURED from an
  approved Broker Capability Profile, not guessed"). 비-브로커 키는 **스펙/설계 원문에서 도출**하며(file:line 인용)
  도출 불가분은 정직한 이연으로 남긴다.
- **anti-phantom.** 모든 주장에 file:line. 부재 주장에는 양방향 grep 결과를 병기한다.

### 0.3 실측 중 확인한 파일-정본·드리프트 함정 (인용 무결성 고지)

본 처분의 모든 프로파일 행번호는 **`tos-spec/src/.../VERIFICATION-PROFILE-002.yaml` 직독**으로 확정했다. 다음 함정을
확인·회피했다(후속 독자·리뷰어 주의):

1. **프로파일 사본 2개.** 정본 = `tos-spec/src/.../VERIFICATION-PROFILE-002.yaml`(status APPROVED). 별도로
   `tos-spec/book/.../VERIFICATION-PROFILE-002.yaml`은 **생성된 stale 미러**이며 행번호·일부 키가 다르다. 인용은
   전부 **src** 기준이다.
2. **런북·설계문서의 프로파일 행 인용은 stale.** `docs/runbooks/kis-capability-probes.md` §4.1의 bound 행번호
   (예: `:221`·`:752`)와 여러 설계문서 §8의 프로파일 행(예: trial 725/726/727)은 **Patch-0055 이전** 좌표다
   (**Patch-0054**가 26개 키를 신설하고 **Patch-0055**가 bound마다 `applicable_scope`·`review_date` 2행을 추가해 좌표가
   누적 이동했다). 본 문서는 **현행 src 행번호로
   재도출**했다(예: `B_external_activity_detect`는 런북 `:221` → **현행 :237**). 값/상태는 불변(본 문서 대상 17키는 전부 null).
3. **설계 failure-domain §7 "전용 키 부재"는 저작 시점(2026-07-27) 사실이며 stale.** Patch-0054가 이후 26키를 신설해
   `MAX_safety_cell_blast_radius`를 등록했다(현재 YAML:996에 실재, 값 null). 즉 **키는 이제 존재**하고 **값만 이연**이다.

---

## 1. 대상 17키 전수 확인 (누락 0 · 현행 src 행번호)

**브로커 10 bounds** (전부 `value_ms: null` · `owner: TBD`):

| # | 키 | 키 행 | semantics | failure_response | measurement_source(요지) | rationale ADR 앵커 |
|---|---|---:|---|---|---|---|
| 1 | `B_external_activity_detect` | 237 | hard_maximum | CONTAIN | broker_capability_profile | ADR-002-002 §23.4 (poll cadence) |
| 2 | `B_final_quantity_proof` | 732 | broker_specific | QUARANTINE_UNKNOWN | broker_capability_profile | ADR-002-002 §16 |
| 3 | `B_late_fill_observation` | 741 | broker_specific | PROFILE_CONTRADICTORY | broker_capability_profile | ADR-002-002 §16.4 |
| 4 | `B_protective_request_complete` | 759 | broker_specific | CONTAIN | broker_capability_profile | ADR-002-001 §12 |
| 5 | `B_broker_query_consistency` | 768 | broker_specific | CONSERVATIVE_UNKNOWN | broker_capability_profile | ADR-002-004 |
| 6 | `B_rate_limit_recovery` | 777 | broker_specific | RESTRICT_OR_CONTAIN | broker_capability_profile | ADR-002-001 §7.5 |
| 7 | `B_protection_gap` | 804 | broker_specific | CONTAIN | protective_replacement_and_broker_log | ADR-002-011 |
| 8 | `B_protection_overlap` | 813 | broker_specific | CONTAIN | protective_replacement_and_broker_log | ADR-002-011 |
| 9 | `B_non_trade_event_detect` | 831 | source_and_broker_specific | CONTAIN | reference_source_and_broker_capability_profile | ADR-002-010 |
| 10 | `B_non_trade_reconcile` | 849 | source_and_broker_specific | QUARANTINE_UNKNOWN | reconciliation_and_broker_capability_profile | ADR-002-010 |

**비-브로커 7 limits** (전부 null · `owner: TBD` · 인라인 `[DEFERRED 2026-07-29: instance/architecture decision]`):

| # | 키 | 키 행 | 방향 | rationale 앵커(YAML) |
|---|---|---:|---|---|
| 11 | `MIN_evidence_retention_ms` | 923 | MIN(floor) | "per record class; economic-effect and verification horizons dominate" |
| 12 | `MAX_trial_authorized_economic_effect` | 942 | MAX | "per exact trial scope; unknown/unbounded credible effect prohibits the trial" |
| 13 | `MAX_trial_concurrent_potential_effect` | 943 | MAX | "per shared capacity scope; potentially-live + abort/recovery overlap" |
| 14 | `MAX_trial_action_count` | 944 | MAX | "per exact plan; unavailable/ambiguous counter denies later trial action" |
| 15 | `MIN_reserved_protective_capacity` | 987 | MIN(floor) | "per capacity scope; unknown minimum is not a satisfied minimum (ADR-002-002 INV-009)" |
| 16 | `MIN_capacity_domain_voter_quorum` | 988 | MIN(floor)?§4.6 | "grants no consensus model; separate architecture decision (ADR-002-012)" |
| 17 | `MAX_safety_cell_blast_radius` | 996 | MAX | "per Failure-Domain Allocation Matrix; unbounded⇒scope 확대 (ADR-002-009 §13)" |

계수: 10 + 7 = **17** (task 명세·gate-status §3.22:804–807·선례 §15.3:646–652와 일치).

---

## 2. 처분 분류 규율

선례 §2(:98–118)의 3-way(+재확인)를 계승하되, 본 문서 대상은 그중 **이연 2류**(브로커 P0-2 · instance/architecture)에
`MIN_evidence_retention_ms`를 더한 17키다. 처분 유형은 3가지다:

1. **브로커 P0-2 측정 이연 (§3, 10키).** 값이 외부 브로커 타이밍/의미에 의존 → **값 제안 금지**, 처분은 "어느
   프로브가 원천인지" 귀속뿐.
2. **instance/architecture 이연 (§4, 6키).** 값이 배포 Allocation Matrix / live-trial scope / Capacity Domain
   합의모델에 의존. broker 문제는 아니나 지금 발명 불가 — **정직한 이연**(트리거 결부).
3. **후보값 도출 가능 (§4, 1키 = `MIN_evidence_retention_ms`).** 값이 이미 승인된 지평 앵커에서 파생 가능 →
   **보수적 floor 후보 제안**(+ 잔여 이연 명시).

---

## 3. 브로커 10키 절 — P0-2 T2 프로브 트랙 귀속 (값 제안 금지)

**값 제안 절대 금지.** 승인된 Broker Capability Profile INSTANCE에서 **측정(MEASURED)**해야 한다. 이 절은 값이 아니라
(a) 원천 프로브, (b) mock-유래 상한 충분성 vs 실계좌 GET 필요성, (c) null 동안 fail-closed 봉쇄 효과를 키별로 귀속한다.

### 3.1 프로브↔키 매핑 (정본 = 실행계획 §T2 + 런북 §4.1)

원천: 실행계획 §T2(`docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md:41-42` — "broker bounds 10키 ↔ 프로브
매핑은 런북에 명시…예: `B_broker_query_consistency` ← 주문 직후 조회 수렴 간격 프로브·`B_late_fill_observation` ←
체결통보 지연 관측 창")를 런북 `docs/runbooks/kis-capability-probes.md` §4.1(:201–240)·§4.2(:242–248)·§3.1(:172–196)이
구체화한다. **런북의 프로파일 행 인용은 stale(§0.3-2)** — 본 표의 키 행은 현행 src다.

| 키 | 원천 프로브 | 프로브 목적(런북 §3.1) | 실행 환경(런북 §3 프로브 표:136–152) | (b) mock-유래 상한 vs 실 GET |
|---|---|---|---|---|
| `B_external_activity_detect` | **P-EXT** | HTS/MTS 수동주문 탐지 지연; 폴링 간격이 하한(:186) | MOCK_VTS(MANUAL) | **mock-유래로 충분**(poll cadence는 환경 불변 구조) |
| `B_broker_query_consistency` | **P-5**(주, MOCK) | 주문 수락(t0)→조회 가시(t1) 수렴(:178) | MOCK_VTS(n=100) | **mock-유래**. 실 leg(P-R5)는 정책 차단 — §3.3 참조 |
| `B_final_quantity_proof` | **P-FQP** | 취소 직후 late-event 창; 관측 0 = "미확립"(:187) | MOCK_VTS | **mock-유래로 충분** |
| `B_late_fill_observation` | **P-FQP** | 동상(late-fill 창) | MOCK_VTS | **mock-유래로 충분** |
| `B_rate_limit_recovery` | **P-13** | 스로틀 지점·회복시간; repo 5/20rps는 자가상한(:182) | MOCK_VTS(QUERY) | **mock-유래**(submit-class 실 페이싱은 P-R5 소관=차단; 외삽 금지) |
| `B_protective_request_complete` | **P-8** | 정정 신/구 ODNO 관계·중첩 구간(:180) | MOCK_VTS | **mock-유래로 충분** |
| `B_protection_gap` | **P-8(부분)** | (인접 키·런북 §4.2:244 — P-8이 **부분 정보만**) | MOCK_VTS | mock-유래 **부분**; 미확립분은 fail-closed 유지 |
| `B_protection_overlap` | **P-8(부분)** | 동상(:245) | MOCK_VTS | mock-유래 **부분** |
| `B_non_trade_event_detect` | **정의된 프로브 없음** | corporate-action 표면 repo 부재·grep 0(런북 §4.2:246) | — | **프로브 부재** — §3.4 참조 |
| `B_non_trade_reconcile` | **정의된 프로브 없음** | 동상(:246–247) | — | **프로브 부재** — §3.4 참조 |

### 3.2 (b) mock-유래 상한 충분성 판정 (CLAUDE.md 정책 정합)

CLAUDE.md 비협상 규칙(`CLAUDE.md:36`): "measurements needing a real fill use the **mock-derived bound**. GET-only real
reads are fine." 위 8개 측정가능 키의 원천 프로브 P-EXT/P-5/P-8/P-FQP/P-13은 **전부 MOCK_VTS**(모의투자)에서 실행된다
(런북 §3 프로브 표). 따라서 **실계좌 주문(실체결)이 필요한 어떤 키도 mock-유래 상한으로 채운다** — 실계좌 GET 읽기가 별도로
요구되는 키는 없다(P-R5-PRE의 GET-only 실읽기는 P-R5 선행 관문이지 이 10키의 값 원천이 아니다).

### 3.3 `B_broker_query_consistency` 이중환경 주의 (런북 §4.1:233–240)

이 키만 원천이 두 환경이다: **P-5 = MOCK_VTS**(n=100, 주), **P-R5 = REAL_PROD**(n≤10). **P-R5는 이 표에서 유일하게
실계좌에 주문을 내는 프로브**(런북 §3 표 경고 :161)이고, **P-R5 stage-2는 CLAUDE.md 정책상 영구 차단**(실선물 무증거금 —
`CLAUDE.md:36,96`; zero-deposit preflight ABORT = terminal). 따라서 이 키의 사용가능 원천은 **mock P-5**다. 상속 금지는
양방향(런북 §4.1:235 · ADR-002-004 §13.14)이므로 두 환경 값을 섞어 쓰지 않는다. **어느 환경 값을 선언면에 쓰는지는
승인 사슬(운영자)의 판단**이며, 정책상 실 leg는 닫혀 있으므로 실무 결론은 "mock-유래 상한 + candidate_only 실소표본은
참고".

### 3.4 `B_non_trade_event_detect`·`B_non_trade_reconcile` — 프로브 부재(현 캠페인 범위 밖)

런북 §4.2(:246–247): corporate-action 표면이 repo에 **부재(grep 0)**하여 **정의된 프로브가 없다.** 이 2키는 현
P0-2 프로브 캠페인이 **채우지 못한다.** 원천은 corporate-action **reference source + broker capability**(둘 다 미착지)
이므로, 이 2키의 처분은 "프로브 실행"이 아니라 **캠페인 선행 조건(비-거래 이벤트 소스 착지) 이후로 이연**이다. null 동안
`CONTAIN`/`QUARANTINE_UNKNOWN`(YAML:837/855)으로 fail-closed 유지된다.

### 3.5 (c) null 동안 fail-closed 봉쇄 효과 + register pending-P0-2 관계

- **키 자체.** 각 키의 `failure_response`(§1 표)가 런타임 봉쇄를 정의한다: 값 없음 ⇒ 해당 bound 충족 불가 ⇒ 보수 반응
  (CONTAIN / QUARANTINE_UNKNOWN / CONSERVATIVE_UNKNOWN / PROFILE_CONTRADICTORY / RESTRICT_OR_CONTAIN). 이것은 결함이
  아니라 설계된 fail-closed다(선례 §13:581–582).
- **register 관계(실측).** `EVIDENCE-REGISTER-002.csv`에 **`pending-P0-2` 태그 행 = 64건**(grep -c 실측). 분포(scope
  prefix별 count): PTF 12 · VTG 6 · IOC 5 · SIR/RLP/NT/AFG 각 4 · WDR/PR/ARE 각 3 · RC/IAP/EGRESS/CUR 각 2 ·
  STM/SCI/SBR/SA/RECON/PRD/ERI/CII 각 1 (합 64). 이 64행은 P0-2 브로커 측정 트랙에 봉쇄되며, 실행계획 §T4
  (`...p02-execution-plan.md:56-57`)가 "register `pending-P0-2` 64행 해소 → P0-2 종결"로 명시한다.
- **anti-phantom 경계(중요).** CSV의 pending-P0-2 행에는 **위 10개 bound 키 이름이 문자적으로 등장하지 않는다**
  (각 키 grep count = 0, 실측). 즉 봉쇄 관계는 **의존성/scope 레벨**(브로커 측정 = P0-2 = Broker Capability Profile
  INSTANCE)이지 "행↔키 문자 참조"가 아니다. **"pending-P0-2 행이 특정 bound 키를 인용한다"고 주장하지 말 것** —
  10 bound는 P0-2 산출물의 프로파일-측 수치 부분이고, P0-2 종결이 64행을 함께 연다.

### 3.6 브로커 10키 처분 요약

| 처분 | 키 | 트리거/조건 |
|---|---|---|
| P0-2 프로브 측정(mock-유래) | detect·query_consistency·fqp·late_fill·rate_limit_recovery·protective_request_complete(6) | 런북 §5 프로브 실행(모의) → INSTANCE `evidence_refs` → Bounds-Approver 값 기입 |
| P0-2 프로브 **부분** | protection_gap·protection_overlap(2) | P-8 부분정보 + 미확립분 UNKNOWN 유지(런북 §4.2) |
| 캠페인 선행조건 이후 이연 | non_trade_event_detect·non_trade_reconcile(2) | corporate-action reference source 착지 후 |

**owner 처분(정직).** 선례 §15.3(:654–657) 그대로: 프로파일 `owner` 필드는 **`TBD` 유지**를 권고한다(rationale에
`pending-P0-2` 문자열이 없어 owner 필드에만 새 어휘를 도입하면 미정의 owner 값이 생김). 이연 사유는 owner 필드가
아니라 본 §3·프로파일 헤더가 기록한다. 값의 최종 승인 주체 = Bounds-Approver(운영자); 프로브 실행 주체(impl/evidence-owner)와
분리.

---

## 4. 비-브로커 7키 절 (핵심 숙고 대상)

각 키: **후보값(도출·보수 방향) 또는 정직한 이연(트리거)** 중 하나 권고 · fail-closed 결과 · owner 후보 · 재량 지점.

### 4.1 `MIN_evidence_retention_ms` (YAML:923) — **후보값 제안 가능** [권고: 보수적 floor 후보]

**결론: 후보값 제안 가능.** 이 키는 나머지 6키와 달리 **미결 아키텍처 결정을 요구하지 않고** 이미 승인된 지평 앵커에서
보수적 floor를 도출할 수 있다.

**도출 근거(스펙 원문).**
- ADR-002-016 §17:432(`ADR-002-016-Safety-Evidence-Audit-and-Deterministic-Replay-Integrity.md`): "The Evidence
  Integrity Policy SHALL define retention by record class and **the longest applicable**:" — 이하 6지평
  (:436 "order, position, exposure, and capacity **economic-effect horizon**" 포함). 즉 보존 = 6지평의 **max()**.
- **§17 지평 ↔ 프로파일 승인값 연결.** §17:437 "safety-profile, authority, credential, and deployment **review
  horizon**" · §17:439 "**verification and ADR acceptance lifetime**"가 프로파일의 승인된 리뷰 주기에 직접 대응한다:
  `MAX_residual_risk_review_interval_ms`=15552000000(YAML:949) · `MAX_envelope_review_interval_ms`=15552000000
  (YAML:993)[§17:437 리뷰 지평, 180일] · `MAX_critical_input_correction_horizon_ms`=86400000(YAML:977)[§17:434 정정
  지평, 1일].
- 단일 스칼라 floor 보수치 = 시간-유한 지평의 최댓값 = **15552000000 ms(180일)**. 이는 형제 지평 max일 뿐 아니라
  **프로파일 163키 전체의 최댓값**이다(실측: VP의 전 numeric 값을 파싱·정렬 비교 — 최대치 15552000000·정확히 2키
  동률·초과 0키; naive substring grep이 아니라 전키 파싱으로 초과-0을 증명).
- **보수 방향(MIN=길수록 안전) 유지.** floor의 과대설정은 과보존이라 저장비용만 증가시키고 증거를 잃지 않는다
  (ADR-002-016 §22:529 "economic and tombstone retention **dominates**"). MIN 방향 역전 금지(선례 §4:134–135).

**후보값 [제안]:** `MIN_evidence_retention_ms = 15552000000`(180일). **발명이 아니라** 승인된 리뷰 지평
(YAML:949/993)에서 §17:432/:437 규칙으로 파생한 값이며, 프로파일 163키 전체 최댓값이다.

**잔여 이연(정직 — floor를 넣어도 남는 것).**
1. **경제-효과/legal-hold 클래스는 지속시간이 아니라 상태 술어다.** §17:441 "Records supporting an open order,
   potentially-live attempt, UNKNOWN state, open position, unreleased capacity … SHALL NOT be deleted or compacted
   below reconstructability" + ERI-INV-011:180 "Evidence retention … never expires an order, attempt, exposure,
   UNKNOWN state … or other economic effect." ⇒ 이 클래스는 스칼라로 접을 수 없고 Evidence Integrity Policy(EIP)의
   상태 술어가 관장한다. **180일 floor는 이들을 상한으로 자르지 않는다(floor≠ceiling)** — 정합.
2. **per-record-class taxonomy 미결**(ADR-002-016 §27 Q9:653). 단일 전역 floor는 max로 이를 우회하나(짧은 지평
   클래스를 과보존 = 안전), 정밀 클래스 규칙은 EIP 소관.
3. **집행 지연-bound 3종 잠정 승인 · 내구성 메커니즘 선정만 미결 (정정: "substrate 통째 미착지" 아님).**
   `B_evidence_persist`=500(YAML:868)·`B_evidence_gap_detect`=2000(877)·`B_evidence_gap_contain`=1000(886)은
   **null이 아니라 2026-07-29 잠정 승인값**을 갖되 `RECHECK` 마커로 남아 있다(:868 "APPROVE after pre-effect and
   emergency durability mechanisms are selected and measured" · :877 per record class/EIP · :886 gap-to-authority
   봉쇄 선정 후). 이 세 키의 값 승인·측정을 미결로 남긴 정본은 **ADR-002-016 §27 Q12:656**("What values for
   `B_evidence_persist`, `B_evidence_gap_detect`, `B_evidence_gap_contain`, and evidence retention/replay limits are
   approved and measured?")다. 따라서 잔여의 정확한 성격은 **"지연 bound 3종은 잠정 승인·내구성 메커니즘 선정만
   미결" + Evidence Store 런타임 스코프 밖**이지 substrate 통째 미착지가 아니다. 180일 floor는 여전히 미래 Evidence
   Store가 지켜야 할 승인 임계이나, 그 집행을 뒷받침할 지연 bound 3종은 이미 잠정 승인돼 있다(내구성 메커니즘 확정 시
   RECHECK 해제).

**프로젝트 관행 대조(정직).** 현 런타임 보존은 Redis TTL **24h/48h**(`CLAUDE.md:27-28` · `config/risk.yaml:104`
`reference_ttl_seconds: 86400` · `:105` `samples_ttl_seconds: 172800`), 최장 8일(`config/feedback_reports.yaml`),
내구 원장은 무-TTL SQLite WAL(`shared/storage/runtime_ledger.py`). 스펙 증거 보존(≥180일 + 무한 경제/legal-hold)은
현 운영 TTL보다 **1.35~2.26 order of magnitude 길다**(실측: 180일 vs 최장 8일 = 10^1.35 · vs 48h = 10^1.95 · vs
24h = 10^2.26) — 두 regime은 다르며 현 런타임에 증거급 보존은 미구현. floor 값은
이 사실을 바꾸지 않는다(임계 선언일 뿐).

**null 동안 fail-closed.** 값 누락 ⇒ UNKNOWN ⇒ fail-closed(설계 evidence-store §8; 재구성가능성 증명 불가 시 거부).
즉 null도 안전-불활성이나, **§17 규칙과 승인 지평이 이미 보수 floor를 제공**하므로 이 키는 "값 제안 가능"으로 분류한다.

**owner 후보:** operator(Bounds-Approver). 값-게이트 없음(리뷰 시 즉시 채택 가능) — 단 잔여 이연 3항은 EIP/substrate 트랙.

**재량 지점(§15.6식):**
- (R-1) **180일 floor 채택 vs null 유지 — 게이트 효과 공시.**
  (a) **효과:** 값 기입은 YAML:45–47에 따라 그 키를 소비하는 scope의 "bounds were measured / approved Profile"
  precondition을 discharge한다(§3.5·§4.7에서 다른 키에 적용한 것과 동일 메커니즘).
  (b) **실측 완화:** 현 retention 소비 후보 register 행 `ERI-EV-010`(CSV:194)·`RLP-EV-005`(CSV:297)는 **키 null인
  지금 이미 `READY`**다 — 즉 이 키의 값 기입이 실제로 여는 행은 사실상 0이고, R-1은 양방향 저-리스크이며 "임계값
  문서화 가치" 문제로 축소된다.
  (c) **비대칭 되돌리기 비용:** 채택 후 철회는 GOV-001 change process를 타지만, null 유지는 언제든 채택 가능.
  본 문서 권고 = **floor 채택**(도출 근거 확정·안전 방향·저-리스크) — 단 (b)로 인해 긴급도는 낮다.
- (R-2) **floor 크기.** 180일은 승인된 최장 시간-유한 지평. 더 긴 값(예: verification/ADR-acceptance lifetime)도
  floor로 안전하나 승인된 수치 앵커가 없어 180일이 근거 있는 하한.

### 4.2–4.4 `MAX_trial_authorized_economic_effect`·`MAX_trial_concurrent_potential_effect`·`MAX_trial_action_count` (YAML:942–944) — **정직한 이연** [권고: 트리거-결부]

**결론: 후보값 아님 · 트리거-결부 이연.** 세 키는 정의상 **instance-scoped**("per exact trial scope / per shared
capacity scope / per exact plan", YAML:942–944)이며 **묶을 trial이 없다.**

**도출 근거(스펙 원문).**
- ADR-002-025 §4:87 "This ADR does not select:" → :90 "- **numeric trial bounds**;" (값 발명 금지 명문).
- §10:298 "If the credible effect cannot be finitely bounded inside the Hard Safety Envelope, **the trial is prohibited**."
  → null = unbounded = **trial 금지**(deny-on-null이 이미 최대안전).
- §28:720 "Unresolved questions reduce authority, prohibit the affected trial … They **never justify a permissive default**."
- §29:743 "**no specific restricted-live trial may start until this ADR and every applicable upstream ADR are Accepted**,
  the §11 pre-trial gate passes, numeric scope is approved, and fresh ADR-002-007/015 Live Authorization is issued."

**trial 미계획(실측).** trial PLAN은 **템플릿만** 존재(`RESTRICTED-LIVE-TRIAL-PLAN-template.yaml` = DRAFT/INELIGIBLE);
INSTANCE는 repo 어디에도 없다(find 전수 = `-template.yaml`만; `grep "artifact_type: RESTRICTED_LIVE_TRIAL_PLAN"` = 템플릿뿐).
대조: `ADVERSE-SCENARIO-SET-002-EVL2-PILOT.yaml`·`VERIFICATION-PROFILE-002.yaml`처럼 실재하는 INSTANCE는 `-002`/`-PILOT`
접미사를 갖는데 trial-plan은 그런 산출물이 0건. gate-status: ADR-002-025 = **Proposed(:1293)**, restricted-live readiness
NO(:1112). register G7 "첫 restricted-live scope 승인" = 후속 live-track(:137).

**원칙적 대조(이미 프로파일에 있음).** 바로 아래 형제 2키는 **승인됨** — `MAX_trial_duration_ms`=60000(YAML:945),
`MAX_trial_evidence_age_ms`=1000(YAML:946). 이 둘은 trial 없이도 보수적 **전역** 천장(ceiling·MAX_ 방향)을 갖기 때문에 2026-07-29 승인됐고,
세 키는 **instance-scoped라 묶을 trial이 없어** 보류됐다. 이 비대칭 자체가 이연이 원칙적임을 보인다.

**정책 결부(구조적 도달 불가 — 선물).** CLAUDE.md:36/96 — 실선물 계좌 영구 무증거금·실주문 경로(P-R5 stage-2 포함)
정책 영구 차단. ADR-002-025 trial은 실브로커/실경제 의미론 하 §10 worst-credible 경제효과의 RCL 사전 커버를 요구하므로,
**선물 restricted-live trial은 구조적으로 도달 불가**(zero-deposit preflight ABORT = terminal, "pending funding" 아님).
ADR-002-025는 broker/asset-agnostic이므로 이는 스펙 금지가 아니라 배포-맥락 금지 — 비-선물(주식) trial은 이 규칙 밖이나,
**그 역시 미계획**이다.

**null 동안 fail-closed.** deny-on-null(§10:298 · YAML:942–944 코멘트 "prohibits the trial"/"denies later trial action").
null이 이미 최대안전 — 안전 공백 0.

**owner 후보:** operator(Bounds-Approver), 값-게이트 = **첫 RESTRICTED-LIVE-TRIAL-PLAN INSTANCE 저작**.

**트리거(이연 해소 조건):** "첫 `RESTRICTED-LIVE-TRIAL-PLAN` **INSTANCE**가 exact·complete scope로 저작될 때, 각 키를
**그 exact plan·shared-capacity scope별로** 측정/승인 — 추가로 ADR-002-025 §11 pre-trial eligibility·ADR acceptance(G4)·
fresh Live Authorization(G7) 게이트 하." **선물 trial의 경우 이 트리거는 현 정책 하 발화 불가(N/A·구조적 도달 불가)**.

**재량 지점(§15.6식):**
- (R-3) 세 키 전부 이연 유지가 권고(트리거 미도달). 지금 임의 천장 기입 = §4:90 위반(발명).
- (R-4) 향후 trial 계획 시 자산군(주식 vs 선물) 결정이 선행 — 선물은 정책상 배제됨을 trial 계획서에 명기.

### 4.5 `MIN_reserved_protective_capacity` (YAML:987) — **분리(SPLIT): 구조 규칙 도출 가능 / 수치 이연**

**결론: 구조 rule-form은 지금 도출 가능(발명 아님) · 프로파일 스칼라 수치는 이연.**

**구조 규칙(스펙 원문에 이미 있음).** task가 예시한 "open scope당 protective replacement 1사이클 충족" 형태는
ADR-002-001 §11.4:501에 직접 대응: "capacity SHALL cover **the more conservative of worst credible order overlap or
the Protection Gap**;" — 여기에 INV-009(ADR-002-002 §198–200 "Protective Reserve Is Non-Borrowable / Normal strategy
activity SHALL NOT consume the configured minimum Reserved Protective Capacity") + §12.1 RCL 원자 커밋을 결합하면
**규칙 형태는 인용 가능**(신규 저작 불요). 단 정확한 문안은 "1사이클"보다 넓다: replacement-overlap은 예약의 **한
성분**일 뿐이고 예약은 ≥7 dimension(ADR-002-001 §4.6) · account/risk-domain별(§12.6:569)로 평가된다.

**수치 이연 근거(네 축, 각각 스펙 백업).**
1. **벡터·per-scope**(§4.6 dimension별 · §12.6:569 account/domain별) — 단일 스칼라는 접힌 표현.
2. **Safety-Profile 소유**(§4.4:195 "**the Safety Profile SHALL define the minimum protective reserve**" · §12.5:563
   "Exact thresholds belong in the Safety Profile and Verification Specification").
3. **동적(정적 아님)**(§12.5:551 "**Protective reserve is not a static configuration value**") — 정적 수치는 보수 하한 게이트일 뿐.
4. **미승인 instance 입력 의존** — worst-credible overlap vs Protection Gap은 Broker Capability Profile atomic-replace
   판정(P0-2·§11.4:495–497) + 승인된 Adverse Scenario Set에 의존; scope/dimension은 Allocation Matrix / Capacity Domain에 의존.

**보수 방향(MIN=클수록 안전) 유지 — 단조.** 예약이 클수록 보호 여유 증가(quorum 키와 달리 단조·비관계적).
Patch-0054:98 "the Reserved Protective Capacity minimum is a non-borrowable floor … Writing these as `MAX_` would
invert their safety direction."

**null 동안 fail-closed.** YAML:987 "an unknown minimum is not a satisfied minimum"; 설계 rcl §8:799 "값 누락 ⇒
UNKNOWN ⇒ fail-closed"; §8:823–824 "누락 시 UNKNOWN ⇒ normal usage 술어가 보수적으로 fail-closed." null은 안전-불활성
(예약 보존 증명 불가 시 정상 사용 거부 — zero-reserve 기본값이 아님).

**양방향 grep(부재 확정 · 자기-제외).** 본 draft 자신이 패턴 문자열을 담으므로 검색을 **VP YAML 파일로 한정**한다:
`grep -nE "MIN_reserved_protective_capacity: *[0-9]" tos-spec/**/VERIFICATION-PROFILE-002.yaml` → **0건**(값 미할당,
`null`만 — 본 문서 자기-일치 제외). "one replacement cycle per scope" 완성 문안도 스펙 전역에서 **0건**(일반 부모
§11.4:501만 존재).

**owner 후보:** operator(Bounds-Approver ≠ Live-Armer, 설계 rcl §9.2:861–862). 값-게이트 = capacity scope/dimension INSTANCE.

**트리거(수치 이연 해소):** (a) Allocation Matrix / Capacity Domain이 scope·dimension 확정, (b) Safety Profile이
§12.5 임계 설정, (c) Broker Capability Profile atomic-replace 판정 + Adverse Scenario Set이 worst-credible overlap/gap
확정(P0-2) — 세 조건 착지 전엔 클수록-안전이 곧 fail-closed `null`을 유지하란 뜻(placeholder 수치 금지).

**재량 지점(§15.6식):**
- (R-5) **구조 규칙을 지금 기록할지.** 권고 = 규칙 형태는 "도출 가능/이미 §11.4에 있음"으로 인정하되 **프로파일 스칼라는
  null 유지**(스칼라가 벡터를 표현 못 함). 규칙 문안을 어디에 두는가(Safety Profile vs 본 처분 각주)는 재량.
- (R-6) 구조 규칙 문안 채택 시 "1사이클"이 아니라 "more-conservative-of {worst-credible overlap, Protection Gap}, per
  scope/dimension, non-borrowable, §12.5 동적 충분성"으로 표기(overlap은 한 성분). 정본은 **Safety Profile**이며
  (§12.5:551 "not a static configuration value" · §12.6:569 per account/risk-domain), 프로파일 스칼라는 이 벡터를
  표현할 수 없으므로 규칙은 인정하되 스칼라 `null` 유지가 정합이다.

### 4.6 `MIN_capacity_domain_voter_quorum` (YAML:988) — **정직한 이연** [권고: Phase B 결정 대기 · 방향 주의]

**결론: 이연. 그리고 이 키에서 "MIN=클수록 안전"은 단순 성립하지 않는다 — 안전값은 관계적(strict majority)이다.**

**도출 근거(ADR-002-012 직독).**
- §1:19 "For a deployment designed to tolerate `f` crash or omission failures under a non-Byzantine replica model, the
  voting configuration SHALL contain **at least `2f + 1` voters**." (⇒ 다수 quorum = f+1 of 2f+1).
- §8:219 "A crash/omission failure tolerance claim of `f` requires at least `2f + 1` voting members **distributed
  according to the approved Failure-Domain Allocation Matrix**." · §8:221 "**Two voters do not tolerate one voter
  failure** while preserving quorum."
- §1:21 "This `2f + 1` rule does not claim Byzantine … or **classify that condition as an uncontained common mode and
  prohibit live authority** for the affected scope."
- §1:35 quorum 부재 시 "no new normal capacity mutation … is permitted" · RCLP-INV-002:155 · §3:69 "**Quorum loss must
  reduce authority rather than create a second writer**." · §15:385 partition.
- YAML:988 "APPROVE **together with the Capacity Domain boundary and fault-tolerance model, which is a separate
  architecture decision**; this key … **grants no consensus model**." register §8-1:213 "Capacity Domain 경계·f/2f+1 |
  rcl:825–827**(Phase B)**."

**방향 양방향 분석(task 핵심 지시).**
- **"클수록 안전"이 무조건 성립하지 않는다.** quorum floor의 안전 성질은 **관계적**이다 — commit은 선언된 voter
  집합의 **strict majority(f+1 of 2f+1)** 이상이 durably 동의해야 한다(§1:19). 배포된 voter 수의 다수(majority)보다
  **크게** 잡으면 더 안전한 게 아니라 **도달 불가 = 가용성 상실**이다: fail-closed 계에서 quorum 미달은 정상 변이를
  전부 거부하므로(§1:35 "no new normal capacity mutation … is permitted") 안전은 유지되나 시스템이 기능하지 못한다
  (ADR-002-012:59 "It **sacrifices permissive availability** when exclusivity cannot be proved"). 반대로 다수보다
  **작게** 잡으면(예: 소수 commit 허용) = split-brain·second-writer = §3:69가 금하는 바로 그 **안전 위반**. 즉 방향은
  비대칭이다 — 과대 = 가용성 상실(안전 유지), 과소 = 안전 위반. 위험의 핵심은 "선언 voter 집합의 진(真)다수 없이
  commit한다"이다.
- **단일-writer 국면 값(1) 안전성 — 양방향.**
  - (FOR 1) 현 런타임은 단일 인스턴스(single-writer). f=0이면 2f+1=1·quorum=1이 내부정합 config다. 지배 위험(second
    writer)은 writer가 하나면 구조적으로 부재 — 단 writer-epoch fencing + stale-epoch 거부(`B_stale_epoch_reject`=0,
    YAML:229, 승인됨)가 성립할 때. 즉 진짜 단일-인스턴스에선 1이 그 자체로 위험하지 않다.
  - (AGAINST 1) 프로파일은 **내구 승인 bound**다. 1을 고정하면 후일 다중-인스턴스 승격 시 "voter 1로 commit" =
    split-brain을 **상속**(미래-토폴로지 fail-open). 또 YAML:988 "grants no consensus model"·"separate architecture
    decision"에 반해 **미결 fault-tolerance 결정(f=0)을 암묵 단정**한다. §1:21 정신("인증만으론 모델 격상 불가")과도 상충.
- **종합 판정.** **일차 이연 근거는 키 자신의 승인 조건**이다: YAML:988이 "APPROVE **together with** the Capacity
  Domain boundary and fault-tolerance model"이라 명시하므로, 그 아키텍처 결정(Phase B) 전 **어떤 값 기입도 승인 조건
  위반**이다. 그 위에 방향 분석이 값 1조차 지지하지 않음을 보인다 — 현 비-live-test 하네스(단일 인스턴스)에서 1은 운영
  현실이자 fencing 전제 하 무해하나, **내구 프로파일 bound로서 1을 하드코딩하는 것은 미래-변경 fail-open 위험 + 미결
  아키텍처 단정**이다. 안전한 값은 절대 크기가 아니라 **배포 voter 집합의 strict majority(f+1)**이며, 그것은 Capacity
  Domain 경계 + fault-tolerance 모델(f)이 정해져야 결정된다(Phase B). ⇒ **이연이 정직**.

**null 동안 fail-closed.** §1:35 · RCLP-INV-002:155 — quorum/committed-prefix 증명 부재 시 정상 변이·권한·claim·전송
전부 금지. null(=미결 consensus 모델)은 곧 "정상 capacity 변이 봉쇄" = fail-closed.

**owner 후보:** operator, 값-게이트 = **Capacity Domain 경계 + fault-tolerance 모델(f) 아키텍처 결정(Phase B)**.

**트리거:** Capacity Domain 경계 + f(내결함 목표)가 승인되면 `2f+1` voter·quorum=f+1이 확정되고 그때 floor를 그 다수로
설정. 단일-인스턴스 non-live 하네스를 특별히 열려면 임의 큰 수가 아니라 **f=0/단일-writer를 명시적 승인 posture로 기록**하고
(그로부터 quorum=1 구조 파생) **다중-인스턴스 승격 시 재승인 트리거**를 병기해야 한다(=사실상 아키텍처 결정 자체).

**재량 지점(§15.6식):**
- (R-7) **승인 조건 위반 주의(일차 근거) + 방향 라벨.** **YAML:988 자신이 승인 조건을 명시한다** — "APPROVE
  **together with** the Capacity Domain boundary and fault-tolerance model" — 즉 그 아키텍처 결정 없이 **지금 어떤
  값(1 포함)을 기입하는 것은 키 자체의 승인 조건 위반**이다(방향 논증보다 상위의 이연 근거). 부차로, 이 키를 다른
  MIN floor(reserved-capacity 등)와 같은 "클수록 안전"으로 취급하지 말 것 — 안전은 관계적(majority)이고 상한(배포
  voter 수의 다수)이 존재한다.
- (R-8) **단일-writer posture를 명시 승인할지.** non-live 하네스 한정으로 f=0을 승인해 quorum=1을 구조 파생하는 경로는
  가능하나, 그 자체가 "별도 아키텍처 결정"이며 다중-인스턴스 승격 재승인 트리거 필수 — 본 문서 권고 = **이연 유지**.

### 4.7 `MAX_safety_cell_blast_radius` (YAML:996) — **정직한 이연** [권고: Allocation Matrix INSTANCE 게이트]

**결론: 이연. Matrix INSTANCE 승인 전엔 의미 있는(scope-축소) 보수 천장을 표현할 수 없다.**

**도출 근거(ADR-002-009 직독).**
- §4.6:106 "The **maximum accounts, portfolios, instruments, strategies, capacities, credentials, and broker paths
  that one failure can affect** before containment is authoritative." (max 대상 집합 = 토폴로지가 공급).
- §13:309/:313 "Every Safety Cell SHALL define: - **maximum economic exposure and capacity affected by one cell
  failure**;" + (§13) 공유 common-mode를 aggregate blast radius에 포함 요구.
- §5 Failure-Domain Allocation Matrix = cell별 도달 account/session·공유 dependency를 기록하는 INSTANCE 아티팩트.
- §22:502 "This ADR SHALL remain **Proposed** until … 1. **a concrete deployment profile and Failure-Domain
  Allocation Matrix are approved**;" + §21 OQ3/OQ4(cell 경계·잔여 common-mode 미결).
- §14-6:335 "escalate to the broader Safety Cell or **global HALT when blast radius cannot be bounded**." (null의 런타임 안전 반응).

**Matrix INSTANCE 부재(양방향 grep).** `find . -iname "*allocation*matrix*"` → **0건**(파일 부재, 실측). "Failure-Domain
Allocation Matrix" 언급은 전부 (a) ADR §5 정의, (b) 승인을 **요구하는** 전제조건 인용(ADR-002-025:533·ADR-002-012:99·
VER-002-001 등), (c) Phase-0 게이트 항목 — **INSTANCE 실재/승인 주장 0건**. gate-status: ADR-002-009 = Proposed(:1277).
register #27 fd:185 "배포 프로파일 + Allocation Matrix INSTANCE 승인(:717–718)" = **미결 게이트**. 설계 failure-domain
§8.2:717–718 "§5 shape는 **빈 매트릭스 틀**이며 실 allocation·common-mode 분석은 인간 승인."

**Matrix 전 값이 무의미한 이유(어려움이 아니라 불가).** 토폴로지-무관 유일 천장 = 전체 계좌/전체 시스템 aggregate — 이는
YAML:996이 경고하는 "unbounded value escalating rather than narrowing scope"이자 RCL aggregate 직렬화(§13)가 이미
강제하는 것을 재진술할 뿐, cell-blast의 **봉쇄 목적**(단일 cell 실패가 전체보다 **더 좁게** 묶임을 증명)을 달성 못 한다.
따라서 Matrix 전 어떤 수치도 (a) 전체-시스템 노출과 동일해 아무것도 축소 못 하거나 (b) 실 cell에 대조 불가한 임의값이다.

**null 동안 fail-closed.** 프로파일 헤더 규칙(YAML:6–8) + gate-status:1056 "keep every scope depending on them
contained." 의존 EV 행(FD-AC-011/FD-EV-011류)이 READY 불가; 런타임은 radius 미봉 시 global HALT로 에스컬레이션(§14-6).
null은 "unbounded 허용"이 아니라 "봉쇄 강제"로 안전 실패.

**owner 후보:** operator, 값-게이트 = **Failure-Domain Allocation Matrix INSTANCE 승인**(+ deployment profile).

**트리거:** ADR §22-1의 배포 프로파일 + Allocation Matrix INSTANCE 승인(register #27 미결) — cell 열거·cell별 도달
account/session·cross-cell 공유 common-mode 확정 시 MAX 천장이 측정·검증 가능. (키 자체는 Patch-0054가 이미 신설했으므로
신설 불요 — §0.3-3.)

**재량 지점(§15.6식):**
- (R-9) Matrix INSTANCE 승인 전 값 확정 시도 금지(무의미·발명). 이연 유지 권고.
- (R-10) non-live-test 하네스에서 사실상 단일-cell(전부 co-located)·실주문 0(VirtualBroker)이라 **실 경제 blast는 0**이나,
  이 키는 배포/production Allocation Matrix 개념이므로 EV 하네스에선 N/A에 가깝다 — 이 관측은 값 확정 근거가 아니라
  "왜 지금 무의미한지"의 방증.

### 4.8 비-브로커 7키 처분 요약

| # | 키 | 처분 | 방향 판정 | 트리거/근거 |
|---|---|---|---|---|
| 11 | `MIN_evidence_retention_ms` | **후보값 [제안]** 15552000000(180d floor) + 잔여 이연 | MIN 길수록 안전(성립·단조) | 163키 전체 max(YAML:949/993) · §17:432/:437 |
| 12 | `MAX_trial_authorized_economic_effect` | 이연 | MAX | 첫 trial PLAN INSTANCE(미계획) · §4:90 발명금지 |
| 13 | `MAX_trial_concurrent_potential_effect` | 이연 | MAX | 동상 |
| 14 | `MAX_trial_action_count` | 이연 | MAX | 동상 |
| 15 | `MIN_reserved_protective_capacity` | **SPLIT**: 구조규칙 도출가능 / 수치 이연 | MIN 클수록 안전(성립·단조) | §11.4:501 규칙 / capacity INSTANCE 수치 |
| 16 | `MIN_capacity_domain_voter_quorum` | 이연 | **관계적**(majority·단순 MIN 아님) | Capacity Domain+f(Phase B) |
| 17 | `MAX_safety_cell_blast_radius` | 이연 | MAX(단 Matrix 없이 계산 불가) | Allocation Matrix INSTANCE(§22-1) |

---

## 5. 재량 행사 지점 종합 (선례 §15.6식 — 승인 시 우선 검토)

| ID | 키 | 재량 지점 | 본 문서 권고 |
|---|---|---|---|
| R-1 | evidence_retention | 180d floor 채택 vs null 유지 — discharge 효과(YAML:45–47)·소비 후보 2행(ERI-EV-010·RLP-EV-005) 이미 READY→해제 효과 ~0·양방향 저-리스크 | floor 채택(도출·안전·**긴급도 낮음**) |
| R-2 | evidence_retention | floor 크기(180d = 최장 승인 지평) | 180d(근거 있는 하한) |
| R-3 | trial ×3 | 지금 임의 천장 기입 = §4:90 위반 | 전부 이연 유지 |
| R-4 | trial ×3 | 자산군(주식/선물) — 선물 정책 배제 | 계획서에 선물 배제 명기 |
| R-5 | reserved_capacity | 구조규칙 기록 위치 vs 스칼라 null | 규칙 인정 · 스칼라 null 유지 |
| R-6 | reserved_capacity | 규칙 문안("1사이클" 협소) | overlap=한 성분으로 정정 표기 |
| R-7 | voter_quorum | **일차: YAML:988 "APPROVE together with…" 승인 조건**(아키텍처 결정 전 값 기입=위반) + 방향 라벨(단순 MIN 아님·관계적·상한) | 이연(승인 조건 미충족)·다른 MIN과 동일취급 금지 |
| R-8 | voter_quorum | 단일-writer(f=0) posture 명시 승인 여부 | 이연 유지(다중승격 재승인 트리거 필수) |
| R-9 | blast_radius | Matrix 전 값 확정 시도 | 금지·이연 유지 |
| R-10 | blast_radius | non-live 단일-cell·실blast 0 관측 | 값근거 아님(무의미성 방증) |

---

## 6. 승인 기록 (Bounds-Approver 기입란 — **2026-08-07 기입 완료**)

> 본 절은 저작 시점 **빈 틀**이었다. 운영자(Bounds-Approver)가 검토 후 기입한다는 규약은 불변이며,
> **2026-08-07에 기입됐다.** YAML 갱신은 별도 편집 작업이고(선례 §12:556–572 절차 준수), 본 문서는 절차
> 기술 + 이 기록면이다. **§1–§5는 승인 대상이 된 권고 원문이므로 재작성하지 않는다.**

### 6.0 운영자 응답 — 축자 전문 (2026-08-07, harris.lee)

> **"1. a, 2. 승인. 3. 선물 계좌는 추후 모의 운영 서버에서 실행."**

**본 패키지에 해당하는 항 = 2번("승인")뿐**이다. 나머지 2항은 같은 응답 안의 별건이다:

| 응답 항 | 대상 | 본 문서와의 관계 |
|---|---|---|
| "1. a" | D5 귀속 확인 게이트(`docs/plans/2026-08-07-tos-p02-d5-d6-decision-record.md` §3-1) | **별건.** 그 문서 §3-1-A가 기록면 |
| **"2. 승인"** | **본 패키지(17키 처분 권고) 전건** | **본 절이 기록하는 승인.** 아래 §6.1 |
| "3. 선물 계좌는 추후 모의 운영 서버에서 실행" | 선물 계좌 관련 실행(P-R5-PRE 지문 확인·선물 프로브 재실행) | **별건·지금 처분 없음(기록만).** 브로커 10키(§3)의 값 원천은 여전히 **mock-유래**이고 실선물 무증거금 정책(CLAUDE.md:36,96)은 불변 |

**"승인"의 범위 해석(정직)**: 응답이 키별로 열거하지 않고 패키지를 통째로 승인했으므로, 그 내용은
**패키지가 권고한 바 그대로**다 — §4.8 요약표·§5 재량표(R-1~R-10)가 곧 승인된 처분이다. 패키지가 **값을
제안하지 않은 키에 대해서는 승인도 값을 만들지 않는다**(특히 §4.6 quorum — 아래 6.1 참조).

### 6.1 기입 (패키지 권고 그대로)

> **⚠ 본 절의 YAML 행번호는 §1–§5와 좌표계가 다르다.** §1–§5는 **저작 시점(2026-08-06, HEAD `65cb94df`)**
> 좌표이고 무접촉으로 보존한다. 본 §6은 **2026-08-07 신규 저작**이므로, 같은 변경이 프로파일 헤더에 dated
> 레코드를 추가해 아래쪽 키가 밀린 뒤의 **편집-후 좌표로 재측정**해 기입했다(`MAX_residual_risk_review_interval_ms`
> 949→**984** · `MAX_envelope_review_interval_ms` 993→**1028** · `MIN_capacity_domain_voter_quorum` 988→**1023**).
> 값·상태는 불변이고 행만 이동했다 — **같은 커밋에서 src를 편집하면 자기 인용을 재측정한다**는 규율의 적용이다.

- **결정 일자: `2026-08-07`**
- **Bounds-Approver(실체): `operator` (harris.lee)** — SoD 충족: **Live-Armer는 미지정**이며 본 승인은 arming이
  아니다(role-scheme §1:28–29; :20은 Live-Armer 행). 프로파일 `approved_by: ["operator"]` 불변.
- **브로커 10키 처분:** ☑ **전부 P0-2 이연 유지(값 null·owner TBD)** — 프로브 실행/INSTANCE 착지 후 재상정.
  **값 승인 0건**(§3 "값 제안 절대 금지" 준수). §3.6 3분류(측정가능 6 · P-8 부분 2 · 프로브 부재 2) 그대로.
- **비-브로커 처분(키별):**
  - `MIN_evidence_retention_ms`: ☑ **후보 15552000000 채택**(180일 floor) → **R-1·R-2 권고 채택.**
    근거 = ADR-002-016 §17:432/:437 "longest applicable" 규칙 + 승인된 리뷰 지평(YAML:984/1028)에서 파생·
    프로파일 163키 전체 최댓값. **잔여 이연 3항(§4.1)은 그대로 유지**(경제효과/legal-hold 상태 술어 ·
    per-record-class taxonomy · 내구성 메커니즘 선정) — floor는 **ceiling이 아니다.**
  - `MAX_trial_authorized_economic_effect`: ☑ **이연 유지** / 트리거: `첫 RESTRICTED-LIVE-TRIAL-PLAN INSTANCE가
    exact·complete scope로 저작될 때(§4.2–4.4 트리거 문안 정본) · ADR-002-025 §11 pre-trial · G4 · G7 게이트 하.
    선물 trial은 현 정책상 발화 불가(N/A·구조적 도달 불가)`
  - `MAX_trial_concurrent_potential_effect`: ☑ **이연 유지** / 트리거: `동상(§4.2–4.4) — per shared capacity scope`
  - `MAX_trial_action_count`: ☑ **이연 유지** / 트리거: `동상(§4.2–4.4) — per exact plan`
  - `MIN_reserved_protective_capacity`: ☑ **수치 이연 유지(구조규칙 인정)** / `R-5·R-6 권고 채택 — 구조 rule-form은
    ADR-002-001 §11.4:501에 이미 존재("more-conservative-of {worst-credible overlap, Protection Gap}, per
    scope/dimension, non-borrowable, §12.5 동적 충분성")하고 정본은 Safety Profile이다. 스칼라는 벡터를 표현할 수
    없으므로 프로파일 값은 null 유지. 트리거 = §4.5 (a)(b)(c) 3조건 착지`
  - `MIN_capacity_domain_voter_quorum`: ☑ **이연 유지(Phase B)** / ☐ f=0 posture 명시 **(미채택)** /
    **`값 기입 없음 — R-7 준수.`** YAML:1023 자신이 "APPROVE **together with** the Capacity Domain boundary and
    fault-tolerance model"을 승인 조건으로 명시하므로 **그 아키텍처 결정 전 어떤 값(1 포함) 기입도 키 자체의
    승인 조건 위반**이다. 본 승인은 그 조건을 충족시키지 않으며 **어떤 quorum 수치도 만들지 않는다.**
    방향 라벨 주의(§4.6·R-7): 안전은 **관계적**(strict majority f+1 of 2f+1)이고 상한이 존재하므로 다른 MIN floor와
    동일 취급 금지. R-8(단일-writer posture 명시)도 **권고대로 미채택**.
  - `MAX_safety_cell_blast_radius`: ☑ **이연 유지(Matrix INSTANCE 게이트)** / `R-9 권고 채택 — Failure-Domain
    Allocation Matrix INSTANCE + 배포 프로파일 승인(ADR-002-009 §22-1) 전 값 확정 시도 금지. R-10(non-live 단일-cell
    실blast 0)은 값 근거가 아니라 무의미성 방증으로만 기록`
- **재량 지점(§5) 검토 서명:** `R-1 ~ R-10 전 10건, 패키지 권고 그대로 채택 — operator (Bounds-Approver),
  2026-08-07.` 권고와 다른 처분을 택한 항목 **0건**.
- **프로파일 반영 여부:** ☑ **반영함**(별도 편집 · GOV-001 change process) — **반영 범위는 `MIN_evidence_retention_ms`
  1키의 값 기입뿐**이다. 나머지 16키는 값·`owner: TBD`·fail-closed 그대로이므로 프로파일에 값 변경이 없고,
  이연 비준 사실은 프로파일 헤더의 2026-08-07 dated 레코드와 gate-status 기록 절이 담당한다.

### 6.2 이 승인의 효과 — 그리고 명시적 비효과

**효과(정확히 이것뿐)**:

1. `MIN_evidence_retention_ms` = **15552000000**이 승인값이 되어 **147/163 numeric key가 승인값을 가진다**(146 → 147).
2. null·key-level unapproved 키가 **17 → 16**으로 준다(브로커 10 + 인스턴스/아키텍처 6).
3. 비-브로커 6키의 **트리거-결부 이연이 비준**됐다 — 즉 "지금 값을 넣지 않는 것"이 운영자 판단으로 확정됐다.

**비효과 — 반드시 혼동하지 말 것**:

1. **이연 비준 ≠ 값 승인.** 6키는 여전히 **key-level unapproved·fail-closed**이며, 각 트리거가 발화하고 값이
   측정·승인될 때까지 의존 scope는 봉쇄된 채다(§4 각 절의 fail-closed 문단이 정본).
2. **브로커 10키에 대한 값 승인 0건.** P0-2 측정 트랙 불변, register `pending-P0-2` **64행** 불변.
3. **프로파일 `status`/`approved_by`/`effective_from`/`review_due` 불변** — 이 승인은 **key-level** 행위이고
   프로파일 재승인이 아니다(§7 "프로파일 승인 아님" 그대로).
4. **`scope.environment: non-live-test` 불변 · live 무관.** Live-Armer 미지정 유지. arming·acceptance·
   restricted-live 어느 것도 열리지 않는다(§7 "live 무관").
5. **ADR acceptance 무관.** 관련 ADR(-009/-012/-016/-025 등) 전부 **Proposed** 유지. gate-status **§8 Gate
   Verdict 불변**.
6. **런타임 보존 구현 아님.** 180일 floor는 **EV 하네스/EIP 임계 선언**이며 현 Redis TTL 24h/48h 런타임을
   바꾸지 않는다(§4.1 "프로젝트 관행 대조" 그대로 — 두 regime은 다르다).

---

## 7. 이 패키지가 명시적으로 하지 **않는** 것 (정직 절)

- **YAML 무변경.** `VERIFICATION-PROFILE-002.yaml`을 읽기만 했다. 값·상태·owner·행 어느 것도 수정하지 않았다.
- **승인 없음.** 본 문서는 후보/권고/도출 근거를 제시할 뿐, 어떤 키도 승인하지 않는다. 승인은 §6 기입란을 통한 운영자 행위다.
- **커밋 없음.** 본 문서는 미커밋 상태로 남긴다(운영자 push는 수동).
- **P0-2 대체 아님.** 브로커 10키의 값은 여전히 승인된 Broker Capability Profile INSTANCE 측정으로만 채워진다 — 본
  문서는 프로브 귀속만 하고 측정을 수행하지 않는다.
- **프로파일 승인 아님.** 프로파일은 이미 profile-level APPROVED(scope-limited)이나, 17키 처분은 그 **key-level**
  잔여를 다룰 뿐 프로파일 재승인이 아니다.
- **live 무관.** `scope.environment: non-live-test` 불변. 어떤 처분도 live arming·acceptance·restricted-live를 열지
  않는다(Live-Armer 미지정 유지). `MIN_evidence_retention_ms` 후보값도 EV 하네스/EIP 임계 선언이지 런타임 보존 구현이 아니다.
- **ADR acceptance 아님.** 관련 ADR(-009/-012/-016/-025 등) 전부 Proposed 유지 — 본 처분은 acceptance와 무관.

---

## 부록 A — 참조 문서 (실측 원천)

| 원천 | 용도 |
|---|---|
| `tos-spec/src/part-1-foundation/verification/VERIFICATION-PROFILE-002.yaml`(직독) | 17키 정본 행번호·rationale·상태 |
| `docs/plans/2026-07-29-tos-phase0-bounds-draft-package.md` | 선례 형식 정본(§7·§8·§12·§13·§14·§15.3·§15.6) |
| `docs/plans/2026-07-29-tos-phase0-p02-execution-plan.md` | P0-2 §T2 프로브↔키 · §T4 pending-P0-2 64행 |
| `docs/runbooks/kis-capability-probes.md` | 프로브 정의(§3.1)·프로브↔bound 매핑(§4.1/§4.2)·실행환경(§3 프로브 표:136–152) |
| `docs/plans/2026-07-29-tos-phase0-human-gate-register.md` | §8-1 수치 키 출처 · #7/#27 게이트 · G7 |
| `docs/plans/2026-07-29-tos-phase0-role-scheme-and-disposition.md` | Bounds-Approver/Live-Armer 배정·owner 규약 |
| `tos-spec/src/part-1-foundation/ARCHITECTURE-GATE-STATUS.md` | §3.22 17키·ADR Proposed 상태·currency-note |
| `ADR-002-016`(§17:430–441·ERI-INV-011:178–180·§4:87·§22:529·§27 Q9/Q12) | 증거 보존 규칙 |
| `ADR-002-025`(§4:87–90·§10:298·§28:720·§29:743) | trial 수치 미선택·금지 |
| `ADR-002-001`(§4.4:195·§11.4:501·§12.5:551/563)·`ADR-002-002`(INV-009:198–200) | reserved protective capacity |
| `ADR-002-012`(§1:19/21·§1:35·§3:69·INV-002:155·§8:219/221·§15:385) | quorum/consensus/writer fencing |
| `ADR-002-009`(§4.6:106·§13:309/313·§5·§14-6:335·§21·§22-1:502) | Safety Cell blast radius |
| `docs/plans/2026-07-20-tos-evidence-store-design.md`·`2026-07-21-tos-risk-capacity-ledger-design.md`·`2026-07-27-tos-failure-domain-design.md` | 각 §7/§8 프로파일 주입 슬롯·fail-closed 계약 |
| `CLAUDE.md:27–28,36,96` · `config/risk.yaml:104–105` · `shared/storage/runtime_ledger.py` | 정책(실선물 무증거금·mock-유래)·프로젝트 보존 관행 대조 |

## 부록 B — 실측 규율 자기점검

- [x] 17키 전수 확인(누락 0) — 현행 src 행번호 직독
- [x] 브로커 10키 값 제안 0건(프로파일 헤더 규칙 준수)
- [x] 비-브로커 키 후보/이연 전부 스펙 file:line 도출(발명 0)
- [x] 부재 주장에 양방향 grep 병기(Matrix INSTANCE 0건·reserved 수치 0건·pending-P0-2 행 내 키명 0건·non-trade 프로브 0건)
- [x] 파일-정본 함정 3종 고지(§0.3) — src vs book 미러·런북/설계 stale 행·설계 §7 "키 부재" stale
- [x] 승인 기록 절 = 공란 틀(§6)
- [x] "명시적으로 하지 않는 것" 절 포함(§7) — YAML 무변경·승인 없음·커밋 없음·P0-2 대체 아님·live 무관
- [x] YAML 무수정·미커밋
