# P0-2 실행 계획 — KIS Broker Capability Profile INSTANCE 완성 경로 (2026-07-29)

> **문서 성격**: 비규범 작업 메모(Phase-0 트랙). 어떤 게이트도 닫지 않으며, 승인 효력 없음. 근거 조사 =
> 병렬 추출 2트랙(① spec 측 요구 표면 ② repo 측 KIS 사실 census 169건) — 본 문서는 그 종합·실행 배선이다.

## 0. 상태 재정의 (선행 발견)

**INSTANCE 초안은 이미 존재한다** — 병렬 세션 커밋 `662f87cc`:
`docs/broker-profiles/KIS-BROKER-CAPABILITY-PROFILE-draft.yaml`(1,588행 · 모의 MOCK_VTS / 실전 REAL_PROD
2문서 분리 — §13.14 상속 금지 정합) + 작업 메모 `2026-07-29-tos-broker-capability-profile-kis-draft.md`
(327행 · 프로브 12건 정의 · quirk 16건 · 템플릿↔모델 불일치 10건 · **VERIFIED 0 정직 상태**).
⇒ P0-2 잔여는 저작이 아니라 **검증·측정·blocker 처분·승인 배선**이다.

또한 병렬 세션이 미커밋 설계 3건(`2026-07-29-tos-egressgw-brokeradapter-design.md`[quirk 16건 처분 매핑
:756-779 포함]·`tos-backtest-design.md`·`tos-marketfeed-design.md`)을 진행 중 — **본 트랙은 이들과 파일
비중첩을 유지**하고, quirk 처분은 그 문서 착지 후 정합 확인한다.

## 1. 잔여 작업 4갈래

### T1 — 템플릿 blocker 스펙 패치 (Patch-0056 · 즉시 착수 가능)

| # | blocker | 처방 |
|---|---|---|
| B-1 | `restriction_approved` 필드 부재 — §5.3:146 "explicitly approved VERIFIED_WITH_RESTRICTION" 표현 불가 | 템플릿 capability 공통 필드에 `restriction_approved: false` 추가 |
| B-2 | FQP recipe 원소 스키마 부재 — §15.4 마커 2필드 없이는 `fqp_adequate` 구조적 False | `final_quantity_proof.recipes[]` 원소 스키마 명시(§15.2 7결과 + `no_later_change_asserted`/`late_event_window_defined`) |
| B-3 | `reduced_off_unattended_partition_protection` 대응 필드 부재 — §13.15 판정 표현 불가 | `live_scope`에 필드 추가 |
| B-4 | 어휘 비매칭: `CLASS-D`↔`CLASS_D_NON_LIVE`·`TRANSPORT_RECEIVED_ONLY`(enum 비멤버)·`EV-L0`↔`LEVEL_0_UNKNOWN`(evidence-level과 문자열 공간 공유 — 좌표 붕괴 위험) | 템플릿 값을 코드 enum 문자열로 정렬 + 주석 0줄 상태에 기입 규칙 헤더 추가 |

부수: §7.2 append-only 승계 3필드(`evidence_package_version`·`superseded_version_link`·`change_reason`)와
residual_risks 4속성 원소 스키마도 같은 패치에 포함(요구 표면 §2.2 불일치 6-7).

### T2 — 측정 트랙 (프로브 실행 — "MEASURED, not guessed")

- **프로브 정의 정본**: 초안 메모 §5의 12건(P-*·N-1~N-14 계열) + census 추가 4건:
  N-15(토큰 1분 재발급 제한 × invalidate→retry 상호작용 — 토큰 공백 구간 측정·`auth.py:46-49` 결합)·
  N-16(`CTFN6118R` 야간 잔고 1콜 — 응답 스키마 확정 후 `config/kis/tr_ids.yaml` 편입)·
  N-17(**명세 대조만으로 해소 가능** — 주문 요청 필드 전수·TIF 허용값·정정취소 값집합; 과거 실적 있는
  `kis-code-assistant-mcp` 경로·모의서버 불필요)·N-18(잔여 실전 토큰 1콜 3건).
- 실행 환경: [[verify-on-paper-server]] — 모의투자 서버(+실전 토큰 1콜 항목은 운영자 판단). 산출 =
  probe 스크립트 + 런북 + 결과 기록 양식(각 결과는 INSTANCE `evidence_refs`와 broker bounds 10키의 원천).
- broker bounds 10키 ↔ 프로브 매핑은 런북에 명시(예: `B_broker_query_consistency` ← 주문 직후 조회 수렴
  간격 프로브·`B_late_fill_observation` ← 체결통보 지연 관측 창 등).

### T3 — 결정 2건 (운영자)

- **D5 canonicalization**: `canonical_semantic_digest`/`byte_digest` 산출 알고리즘 미결(B-5·G2 결부).
  선택지 = (a) 잠정 `ev-l1-provisional-0` canonicalizer 채택(비프로덕션 라벨 명시 — non-live INSTANCE에
  정합·프로덕션 canonicalization은 G2 후속 유지) / (b) digest 공란 유지(승인·번들 바인딩 불가 지속).
- **D6 명세 대조 수단**: `kis-code-assistant-mcp` 재가동 가능 여부(가능하면 N-17 즉시 처리·불가면 공식
  문서 수동 대조로 대체).

### T4 — 승인 배선 (T1~T3 후)

B-6 required-capability-set/minimum-live-gate 매핑 저작 → 프로브 결과 반영·INSTANCE `DRAFT` 해제 패키지
→ 독립 리뷰(D1 혼합 방식) → 운영자 승인(`approvers[]`) → `VERIFICATION-PROFILE-002.yaml`
`scope.broker_capability_profiles` 링크 + broker bounds 10키 값 기입(Bounds-Approver) → register
`pending-P0-2` 64행 해소 → **P0-2 종결**.

## 2. census 핵심 판정 (INSTANCE 검증 입력)

- **사실 169건**(CODE-OBSERVED 99·CONFIG 35·SPEC-DOC 16·UNVERIFIED 19)·시크릿 노출 0.
- **folklore 철회 확정**: "REST 20건/s·WS 41건" 수치의 발원은 2026-07-02 로드맵 한 줄(무근거)이며 초안의
  `hard_limits: {}` 판단이 정당 — 실측 전 기입 금지 유지.
- **SoT 결손**: `config/kis/tr_ids.yaml`에 잔고 TR 0건(실사용 TR은 `client.py` 인라인·`CTFN6118R`은 문서만)
  — `futures-legal-review.md:38`의 감사 항목이 구조적으로 충족 불가. N-16 후 tr_ids 편입으로 해소.
- **stale 런북 2건**(live 게이트 문서): `futures-legal-review.md` 개장 시각 09:00(현행 08:45)·§1 브로커 ToS
  절 전체 공란; 휴장일 "KIS official" 주장 vs 휴장일 API 호출 0건(정적 YAML만). → 별도 위생 커밋 후보.
- **상호작용 리스크 1건**: 토큰 1분 재발급 제한 × 만료-즉시-invalidate 재시도 경로 = 토큰 공백 창 가능
  (N-15로 실측).

## 3. 이 계획이 명시적으로 하지 않는 것

- INSTANCE 값의 발명(전 기입은 프로브/명세 대조 결과 또는 provenance 등급 부착 사실만).
- live 관련 어떤 승인(REAL_PROD 문서는 별도 트랙·CLASS-D 유지).
- ADR-002-004 acceptance(§30 15조건 중 profile은 1개 — EV 실행·독립 리뷰 등 잔여).
- 병렬 세션 소유 문서(egressgw-brokeradapter 등) 수정.
