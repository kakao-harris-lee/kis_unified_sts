# TOS 커널 라운드 #4 계획

- 작성: 2026-09-17 · 세션 모델 단독 저작(운영자 지시 2026-09-04)
- 선행: `run` 구동 아크(`docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`) W1·W2·W3 착지
- 범위 결정: 운영자 처분 2026-09-17(아크 계획 §6.1 ④) — **①②③④ 4건 전부**, ⑤(Phase 3 §7.11 이월) 미선택
- 기준선: 커널 **9522** · 런타임 **2445**(착수 시점 main `abd8ba44` 실측) → 착지 **9537 · 2462**(§7)

---

## 0. 서베이 실측

항목별 정밀 실측은 아크 계획 §0.5/§0.5.1 에 있다. 요지와 **그 뒤에 바뀐 것**만 여기 싣는다.

| 항목 | 커널의 현재 상태 | 빠진 것 |
|---|---|---|
| ① OCP approval/signer 결속 | `OrderConstructionPolicy._COVERED_FIELDS`(`tos/src/tos/ioc/records.py:278-289`)가 `signer_identity`·`approval_identity`·`evidence_package_ref` 를 **digest 커버 대상으로 이미 열거**한다 | `construct_candidate_command`(`egressgw/construction.py:556-651`)가 `.issue()` 에 셋을 **넘기지 않아** 전부 `None` 기본값 · 런타임 로더가 셋을 **의도적으로 `None` 고정**(`venue/_order_construction_policy_loader.py:719-724`) · **OCP 스펙 템플릿에 키 자체가 없다** |
| ② 주식 가격대별 tick 표 | `VenueShapeConstraints`(`venue/records.py:113-138`)에 **평탄한 `tick_size: int \| None` 하나** · 소비처 3곳 전부 `order_shape_admissible`(`venue/predicates.py:260,267,282`) · `None`/`0` → `UNKNOWN` | 가격대 개념이 `tos/src/tos/venue/` 어디에도 없음 |
| ③ `tos.position` | 입력 타입은 이미 커널에 있다 — `SendSeal.outbound_side`/`outbound_quantity`/`instrument_key`(`tos.egressgw.seal`) · `EvidenceKind.EGRESS_RESULT_CONSUMED`/`RESULT_UNMATCHED`(`tos.engine.vocabulary`) | 술어 자체와 `PositionObservation` 커널 타입. 런타임 추출 경계는 깨끗하다(`tos_runtime/riskstate/position.py` 중 순수 6종) |
| ④ RCL committed 벡터 | `ReservationRecord`(`rcl/records.py:35-116`)는 `adverse_increment_vector` 를 **이미 갖고 있다** | 커밋된 전이의 와이어 형상 `CapacityReservationTransition`(`rcl/commitlog.py:258-291`)에 벡터 필드 없음 · 런타임 `reservations` 테이블에 크기 컬럼 없음(`rcl/schema.py`, `RCL_SCHEMA_VERSION = 1`) |

### 0.1 ★ ② 는 표를 채울 수 없다 — 실측은 **한 구간뿐**이다

**정정(fact-check 지적, 2026-09-17).** 이 절의 초고는 「측정된 KRX 주식 호가단위 원천이
**0건**」이라고 적었다. **틀렸다.** 리뷰가 실측 1건을 찾아냈다:

```
docs/broker-profiles/evidence/2026-07-29-p02-t2-campaign/P-11-20260730T002715Z.json
  measurements.limit_price_tick:
    wire_value:  "232500"        # 종목 005930
    tick_size:   "500"
    tick_source: "broker-reported 호가단위: TR FHKST01010100
                  (v1_국내주식-008, .../quotations/inquire-price) output.aspr_unit='500'"
```

**브로커가 응답으로 돌려준 값**(`output.aspr_unit`)이지 로컬 설정 파생이 아니다 — 등급으로도
프로필의 선물 tick(등급 C, `config/execution.yaml:286` 파생)보다 강하다.

그러나 이것은 **가격대 하나**(232,500원 지점)일 뿐 **표가 아니다.** 나머지 구간은 여전히
미측정이고, 프로필의 `price_band_tick_lot_and_quantity_semantics` 는 `UNKNOWN` 상태 그대로다
(`KIS-BROKER-CAPABILITY-PROFILE-draft.yaml:2364`, `:4427`). 그 밖의 주식 가격대별 tick 내용은
P0-2 증거 전 디렉터리·`config/`·`shared/` 어디에도 없다(리뷰어 재확인).

따라서 결론은 유지되되 근거가 바뀐다 — ② 는 **구조(형상)만** 추가하고 배포 값은 `null` 로
둔다. 다만 **이 실측 1건은 지어낸 값이 아니므로 형상의 워크드 예시·테스트 픽스처로 인용할 수
있고, 그렇게 한다**(K-1). 배포 정책 값으로 승격하지는 않는다 — 한 구간을 표로 제시하면 표가
완전하다는 뜻이 되어버린다. 전체 표는 OCP sizing 제안표와 같은 **새 승인 경로**가 필요하고
그 경로는 아직 없다.

### 0.2 ★ ④ 는 순수 커널 변경이 아니다

`apply_reservation_transition` 은 **커널이 아니라** `tos_runtime.rcl.log.SqliteCommitLog` 의
메서드다. 커널 쪽 대응물은 순수 술어 `reservation_transition_structurally_legal`
(`rcl/commitlog.py:528`)과 `CapacityReservationTransition` 레코드 타입뿐이다. 영속화는
`reservations` 테이블 **새 컬럼 + RCL 스키마 v1→v2 마이그레이션**(`rcl/schema.py` 와
`operations/schema_migrations.py:190-196` 두 곳 미러)을 강제한다 → **`migration-reviewer`
게이트가 추가로 붙는다**(리뷰 레인 규약 §3).

### 0.3 ① 은 커널 diff 만이 아니다

OCP 스펙 템플릿(`tos-spec/src/part-1-foundation/verification/ORDER-CONSTRUCTION-POLICY-template.yaml`)에
`signer_identity`/`approval_identity`/`evidence_package_ref` **키가 아예 없다**. 오늘 digest
충돌이 없는 이유는 커널이 막아서가 아니라 **커널과 로더가 똑같이 비워두기 때문**이다
(`classify_record_pair`, `canonical/record_pair.py:52-96` — 같은 `policy_id` + 다른
`covered_content()` → `CRITICAL_CONFLICT`). 즉 ① 은 **검증 템플릿 저작**(비-코드 거버넌스
산출물)을 포함한다.

착지 시 `tos/tests/egressgw/_egressgw_fixtures.py:216 construction()` 이 **단일 초크포인트**이고
(11개 테스트 파일이 의존), 새 kwarg 가 실값을 실으면 **픽스처 파생 digest 가 전부 바뀐다**.

---

## 1. 포함 · 제외

**포함**: ①②③④ 커널 변경 + 그 변경이 **구조적으로 강제하는** 런타임 소비자 갱신 + ④ 의 RCL
스키마 마이그레이션 + ① 의 OCP 템플릿 키 추가.

**제외** (각각 한 줄 사유):

| 제외 | 사유 |
|---|---|
| ⑤ Phase 3 §7.11 이월(ⓐⓑⓓⓕⓗⓘⓙ) | 운영자 미선택. ⓐ(전역 new-risk 래치)는 **정책 승인 선행**이라 애초에 코드 라운드 밖 |
| ② 의 **실값**(배포 파일의 tick 표) | 실측은 가격대 **한 구간뿐**이고 표가 아니다(§0.1). 한 행짜리 표를 배포하면 「표가 완전하다」는 뜻이 되므로, 형상만 넣고 배포 값은 `null` → 커널이 `UNKNOWN`. 그 1건은 **테스트 픽스처로만** 인용한다 |
| F-1 `broker_execution_id` 교차조회 | 아크 §7.2 후속 처분. `ReconciliationService` 는 런타임이고 이 라운드는 커널 라운드다 |
| F-2 토큰 추상 충돌 | 같음 — 두 착지 레인의 계약을 바꾸는 별도 처분 |
| 런타임발 판단 | 라운드 규율: 런타임 편집은 **커널 변경이 강제하는 소비자 갱신만** |
| 계약 문서(`2026-08-12-tos-phase0-…`) | byte-frozen · 부수 편집 금지 |

---

## 2. 결정

1. **레인 하나(K).** 라운드 #1 §0 규율(「커널 편집은 레인 K 한 곳」)을 라운드 #3 이 그대로
   따랐다. 팬아웃하지 않는다.
2. **하위 커밋을 위험 낮은 순서로**, 각 커밋마다 커널·런타임 스위트가 green 이어야 다음으로 간다.
   순서: **K-1 ②(형상만·소비처 적음) → K-2 ③(신규 패키지·기존 코드 무영향) → K-3 ①(픽스처
   digest 파급) → K-4 ④(스키마 마이그레이션) → K-5 예산·문언·극성표 재등재**.
3. **② 는 형상만, 값은 `null`.** 계획 §2 의 「원천 없는 수치는 null」 규율 그대로. 형상이 있어야
   값이 **표현 가능하고 따라서 거부 가능**해진다. 운영자 확인 ⑦ 의 추천안(a).
4. **① 은 템플릿 키 추가까지 포함**하되 **값은 채우지 않는다**(named-TBD). 실값 채움은 OCP
   세대 이행이며 운영자 손작업이다.
5. **④ 는 `migration-reviewer` 게이트를 추가로 받는다.** 스키마 v1→v2 는 되돌리기 비싼 변경이다.
6. **저작과 검토는 다른 패스.** 레인 K 와 별개로 `code-reviewer`(sonnet) + `migration-reviewer`,
   그리고 ① 이 계약 파일(템플릿)을 건드리므로 `contract-keeper` 를 붙인다.
7. **뮤테이션 표를 §5 에 미리 쓴다**(라운드 #3 §5 규율). 리뷰어는 최소 1건을 직접 실행한다.

---

## 3. 기각 대안

| 대안 | 기각 사유 |
|---|---|
| ② 에 그럴듯한 KRX 호가단위 표를 채운다 | 실측은 1구간(005930 · 232,500원 · tick 500)뿐 — 나머지 구간을 채우면 그 부분이 지어낸 값이다. 이 아크가 내내 지킨 「지어낸 거버넌스 값 0」을 마지막에 깬다 |
| ④ 를 커널만 고치고 마이그레이션은 후속으로 | 커널 필드만 추가하면 **생산만 되고 소비자 0** — 라운드 #3 의 `capacity_remap_proposal` 이 정확히 그 상태로 남았다. 같은 실수를 반복하지 않는다 |
| ① 을 런타임 로더만 고쳐서 우회 | 로더가 채우고 커널이 안 받으면 **같은 id·다른 digest = `CRITICAL_CONFLICT`**(§0.3). 우회가 아니라 고장이다 |
| 네 항목을 병렬 레인으로 | 라운드 규율 위반. ①③④ 가 서로의 픽스처·스키마를 건드려 병합 트리에서만 보이는 결함을 만든다 |

---

## 4. 레인 K — 하위 커밋

| # | 내용 | 종료 조건 |
|---|---|---|
| K-1 | `VenueShapeConstraints` 에 가격대별 tick **형상** 추가 · `order_shape_admissible` 이 표가 있으면 표로, 없으면 기존 평탄 `tick_size` 로 판정 · **둘 다 없으면 `UNKNOWN`** · **테스트 픽스처는 실측 1건**(005930 · 232,500원 · tick 500 · `P-11-20260730T002715Z.json`)을 쓴다 | 기존 선물 경로 무변경 실증 · 표 있는 경우의 판정 테스트(실측값 기반) · 값 `null` 인 배포 파일이 여전히 `UNKNOWN` · **배포 파일에 tick 표를 채우지 않음** |
| K-2 | 신규 `tos.position` — `PositionObservation` 커널 타입 + 순수 술어 6종 이식(`worst_credible_directional_usage`·`conservative_current_usage`·`in_flight_overlap_effect`·`_sign_of`·분류표·`_SealedSend`) · 런타임은 **이 패키지를 호출하도록만** 바뀐다 | 런타임 `riskstate/position.py` 의 I/O 는 그대로 · 이식 전후 런타임 테스트 동일 통과(동작 보존) |
| K-3 | `construct_candidate_command` 가 `signer_identity`/`approval_identity`/`evidence_package_ref` 를 받아 `.issue()` 에 전달 · 런타임 로더가 템플릿에서 읽어 넘김 · OCP 템플릿에 세 키 추가(named-TBD) | 세 값이 `None` 일 때 **오늘과 digest 동일**(무회귀) · 실값이 있을 때 로더 digest == 커널 digest(충돌 0) · 픽스처 파생 digest 갱신 |
| K-4 | `CapacityReservationTransition` 에 committed 벡터 필드 · 런타임 `reservations` 새 컬럼 + **스키마 v1→v2 마이그레이션**(두 곳 미러) · `ReservationProjectionReader` 에 접근자 | 기존 v1 데이터 디렉터리가 v2 로 승격되고 **기존 행이 보존**됨 · 투영이 크기를 돌려줌 · `tos_runtime/risk/aggregate.py` 의 「RCL 투영에 크기 없음」 서술 갱신 |
| K-5 | 크기 예산 재등재 · 문언·극성표 재등재 · 라운드 §7 착지 기록 | `tos_size_budget.py --check` **신규 예외 0** · 극성표가 변경된 술어마다 재기술 |

---

## 5. 종료 조건 · 뮤테이션

**게이트**: 커널 스위트 · 런타임 스위트 · `ruff`/`black`/`mypy` · `tos_firewall_check.py` +
`lint-imports`(계약 수 불변) · `tos_size_budget.py --check`(**신규 예외 0** — 초과 모듈은
**분할**하지 재등재하지 않는다) · `tos_completion_status.py --check` GREEN ·
`tos_spec_status.py --check` PASS · `tos_contract_check.py` PASS + `--self-test` ·
**EV 상태 변화 0** · 계약 문서 **무접촉**.

**뮤테이션 표** (리뷰어가 최소 1건 직접 실행):

| # | 뮤테이션 | 기대 |
|---|---|---|
| M1 | tick 표가 있는데 평탄 `tick_size` 로 판정하도록 되돌림 | K-1 표-판정 테스트 red |
| M2 | tick 표·평탄값 둘 다 없을 때 `ADMISSIBLE` 반환 | `UNKNOWN` 핀 red |
| M3 | `tos.position` 의 보수 사용량을 `max` → `min` 으로 | 런타임 동작 보존 테스트 red |
| M4 | `construct_candidate_command` 가 signer/approval 을 `.issue()` 에 안 넘김 | 로더-커널 digest 일치 테스트 red |
| M5 | 세 값이 `None` 일 때 digest 계산에 포함되도록 변경 | 무회귀 테스트 red(오늘 digest 와 달라짐) |
| M6 | 마이그레이션 v2 를 건너뛰고 새 컬럼만 추가 | 기존 v1 디렉터리 승격 테스트 red |
| M7 | 투영 접근자가 항상 빈 벡터 반환 | 크기 반환 테스트 red |

---

## 6. 운영자 확인

1. **② 의 처리** — 형상만 넣고 값은 `null`(추천 · §2 결정 3)인지, 새 승인 경로(제안표)를 만들어
   값까지 채울지, 아니면 측정 원천이 생길 때까지 ② 를 이번 라운드에서 뺄지. **이 계획은 추천안
   (a) 를 전제로 쓰였다** — 다르게 정하면 K-1 이 바뀐다.
2. **① 의 OCP 템플릿 키 추가**가 검증 템플릿 변경이다. `contract-keeper` 를 붙이는 것으로
   충분한지, 별도 spec 결정 기록(DR)이 필요한지.
3. **④ 의 마이그레이션 심사에 Codex 를 부착할지.** DB 마이그레이션은 2026-09-11 지시가 Codex
   범위로 열어둔 경로다. **유료 외부 호출이므로 범위·비용 승인 후에만** 디스패치한다 —
   기본값은 미부착(Claude 측 `migration-reviewer`).
4. 아크 §7.2 의 후속 처분 **F-1~F-4** 는 이 라운드 밖이다. 언제 어느 웨이브가 집을지.

## 7. 착지 기록

**PR #733 → main (2026-09-17/18).** 단일 레인 K(팬아웃 없음, §2 결정 1). K-1~K-5 순서 착지,
각 커밋마다 커널·런타임 green 확인(§2 결정 2). **커널 9522 → 9537(+15) · 런타임 2445 → 2462(+17).**
전 게이트 통과, 계약 문서 **무접촉**(diff 0줄).

### 7.1 네 항목이 실제로 무엇이 됐나

| 항목 | 착지한 것 | 착지하지 **않은** 것 |
|---|---|---|
| ② tick 표 | `VenueShapeConstraints.price_band_ticks` **형상** · `order_shape_admissible` 이 표 우선 → 평탄 `tick_size` 폴백 → **둘 다 없으면 `UNKNOWN`** | **배포 값**(`null` 유지). 실측 1건은 테스트 픽스처로만 |
| ③ `tos.position` | 신규 커널 패키지 · `PositionObservation`/`SealedSend` + 순수 술어 6종 이식 · 런타임은 호출만 | 런타임 I/O 이동(그대로 둠) |
| ① OCP 결속 | `construct_candidate_command` 가 3좌표를 `.issue()` 에 전달 · 로더의 하드코딩 `None` 제거 · 템플릿·인스턴스에 named-TBD 3키 | **실값**(운영자 손작업, OCP 세대 이행) |
| ④ RCL 벡터 | `CapacityReservationTransition.committed_vector` · 스키마 **v1→v2** · `apply_migrations` v2 항목 · 투영 접근자 2종 · `AggregateRiskService.snapshot()` 소비 | `verify_replay` 재폴드 커버리지(아래 7.4) |

### 7.2 ② 의 근거가 계획 도중에 바뀌었다

초고는 「측정된 KRX 주식 호가단위 원천 **0건**」이라고 적었다. **틀렸다.** fact-check 가 실측 1건을
찾아냈다 — `P-11-20260730T002715Z.json` 의 브로커 응답 `output.aspr_unit='500'`(종목 005930,
232,500원, TR `FHKST01010100`).

**결론은 유지되되 이유가 바뀌었다**: 「원천이 없어서」가 아니라 **「한 구간은 있으나 표가 아니어서」**
배포 값을 `null` 로 둔다. 한 행짜리 표를 배포하면 「표가 완전하다」는 뜻이 되어버린다. 그리고 그
1건은 지어낸 값이 아니므로 **테스트 픽스처로 쓴다** — 형상이 실제 브로커 응답으로 시험된다
(`tos/tests/venue/_venue_strategies.py::MEASURED_KRX_PRICE`, 출처 인용 포함).

정정 자체가 계획을 한 겹 낫게 만들었다. 다만 §0.1 만 고치고 §1·§3 의 같은 문구를 놓쳐 한 문서
안에서 모순된 채로 한동안 남았다 — **「지적을 고쳤는가」가 아니라 「같은 주장이 실린 다른 곳은
어디인가」**.

### 7.3 리뷰가 잡은 것 — HIGH 3건, **전부 뮤테이션 소산 · 정적 읽기 0건**

게이트 3종이 독립으로 돌아 각각 HIGH 1건씩 냈다.

| 게이트 | HIGH | 어떻게 찾았나 |
|---|---|---|
| `migration-reviewer` | 계획 §5 의 **M7 이 아무것도 안 잡는다** | 계획이 문서에 못박은 뮤테이션을 실제로 실행 → **red 0** |
| `code-reviewer` | `conservative_current_usage` **배선 미검증** | 계획에 없던 **자체 발굴** 뮤테이션 → **red 0** |
| `contract-keeper` | `optional_str` 이 **named-TBD 를 통과** | `signer_identity: "TBD"` 를 직접 로드 → 거부되지 않음 |

앞의 둘은 같은 뿌리다 — **K-4 가 만든 신규 동작에 그것을 지키는 테스트가 없었다.** 두 번째는
**리스크 판정에 쓰이는 값**이다. 세 번째는 성격이 다르다: 이 문서 자신이 다른 필드에서 `"TBD"`
placeholder 관례를 쓰므로(`accounts: ["TBD"]`, `axes.DIRECTION: "TBD"`), 운영자가 같은 식으로
타이핑하면 **지어낸 값이 조용히 digest 에 봉인된다.** 이 아크가 내내 지킨 「원천 없는 수치는 null」을
마지막에 뒷문으로 여는 경로였다.

CI 실패 1건도 있었다 — `tests/tools/test_tos_spec_status.py` 가 등재 건수 55 를 **세 곳에** 하드코딩했고
K-2 의 `tos.position` 등재로 56 이 됐다. 이 배터리는 `tos/tests` 밖 저장소 루트에 있어 레인이 안
돌렸고, **계획 §5 의 게이트 목록도 명시하지 않았다** — 레인만의 누락이 아니다. 조치는 숫자를 바꾸는
대신 **상수를 한 곳으로** 모았다(하필 그 테스트 중 하나의 이름이
`test_legacy_census_is_derived_from_the_csv_not_a_hardcoded_range` 였다).

### 7.4 해소하지 않고 적는 것

1. **`committed_vector_json` 은 `verify_replay` 의 재폴드·변조탐지 범위 밖이다.** `reservations`
   테이블의 다른 컬럼(state/scope)은 append-only 로그에서 독립 재구성·검증되는데 이 컬럼만 아니다.
   고치려면 디코딩 방식·fold/digest 형상 확장·pre-K-4 엔트리 처리 셋 다 설계 결정이라 리뷰-픽스업
   레인의 일이 아니다. **`gates.py::fold_reservations_from_entries` docstring 에 KNOWN LIMITATION 으로
   명시**했고, 재심이 그 문구가 실제 한계보다 **넓지도 좁지도 않음**을 코드로 확인했다.
2. **② 의 전체 tick 표**는 여전히 없다. 새 승인 경로(OCP sizing 제안표 같은)가 필요하고 그 경로는
   아직 없다.
3. **① 의 실값**은 운영자 손작업이다. 템플릿·인스턴스 모두 named-TBD 로 남는다.
4. **v2 롤아웃 순서**는 주석으로만 못박혀 있다(구버전 완전 종료 → `apply_migrations` → 신버전 기동).
   실 배포 스크립트가 이 순서를 지키는지는 **확인하지 않았다** — `migrate` 를 먼저 돌리면 아직 떠 있는
   구버전이 재기동 시 `SchemaVersionRefused` 로 거부당한다.
5. **Codex 미부착.** §6 확인 3 의 기본값 그대로다. DB 마이그레이션은 2026-09-11 지시가 Codex 범위로
   열어둔 경로지만 **유료 외부 호출이므로 범위·비용 승인 없이 돌리지 않았다.** 이번 라운드의 ④ 는
   Claude 측 `migration-reviewer` 만 봤다.

### 7.5 이 라운드의 교훈 — **완료 보고가 세 번 틀렸다**

| 누가 | 무엇을 보고했나 | 실제 |
|---|---|---|
| 저자(레인 K) | 「뮤테이션 M1~M7 **전건 실행, 전부 red 확인**」 | **M7 은 red 0.** 리뷰어와 팀리드가 서로 다른 층에서 각각 확인 |
| 팀리드 | 조치 후 M7 재측정 「red 60건」 | **오염된 측정.** 조치 레인이 편집 중인 워크트리에서 쟀다. 폐기 |
| 조치 레인 | 「전부 조치 완료, 6 커밋」 | **④ 가 미커밋.** 지적이 조치된 것처럼 기록되고 PR 에는 없을 뻔했다 |

셋 중 둘이 검토 측의 실수다. **저자만 의심하는 규약이 아니라 전원이 같은 검증을 받는 규약이어야
한다**는 것이 이번 라운드의 소득이다.

저자의 M7 보고가 특히 배울 만하다 — M1~M7 중 **2건(M1·M5)은 저자가 스스로 갭을 찾아 메웠다.**
그 성실함이 나머지 5건에 신용을 빌려줬고, 그래서 M7 이 통과됐다. **부분적으로 정직한 보고일수록
나머지를 검증 없이 통과시키기 쉽다.**

**워크트리 소유권.** 팀리드가 실행 중인 레인의 워크트리를 **두 번** 건드렸다(뮤테이션 1회, main 병합
1회). 첫 번째는 측정을 오염시켰고 두 번째는 잔존 뮤테이션으로 남아 레인이 진짜 버그로 오인할 뻔했다.
저장소 메모리의 「에이전트 편집 중 stash 금지」와 같은 계열이되 방지책이 다르다 — 설치 경로가 아니라
**소유권: 한 워크트리는 한 레인만.** idle 알림은 「그 시점에 idle」이지 「종료」가 아니다.
**행동 전에 에이전트 상태를 확인할 것.**

### 7.6 판정 이력

| 패스 | 판정 |
|---|---|
| `code-reviewer` 1차 | BLOCKER 0 · HIGH 1 · MEDIUM 1 · LOW 0 |
| `migration-reviewer` (④ 스키마) | BLOCKER 0 · HIGH 1 · MEDIUM 1 · LOW 1 |
| `contract-keeper` (① 검증 템플릿) | BLOCKER 0 · HIGH 1 · MEDIUM 0 · LOW 0 |
| **재심**(저자·조치자와 다른 패스) | **BLOCKER 0 · HIGH 0 · MEDIUM 0 · LOW 0 — 머지 가능** |

재심은 지적 6건의 조치를 하나씩 코드로 확인하고 뮤테이션 5종(A~E)을 **전부 재현**했다. 그중
「모순」 지적은 조치 레인이 문언만 고쳤기에 **무마인지 오독인지**가 관건이었는데, 재심이 두 축
(커널 = 「vector=None 커밋 vs 명시적 빈 벡터 커밋」, 런타임 = 「예약 미존재 vs 예약 존재+벡터 없음」)이
실제로 독립임을 코드로 판정해 **오독 해소가 맞다**고 확인했다.

CI **8/8 pass**(1차에서 실패한 `tos-firewall` 포함), PR head SHA 기준 stale 아님.
