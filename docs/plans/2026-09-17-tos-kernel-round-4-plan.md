# TOS 커널 라운드 #4 계획

- 작성: 2026-09-17 · 세션 모델 단독 저작(운영자 지시 2026-09-04)
- 선행: `run` 구동 아크(`docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md`) W1·W2·W3 착지
- 범위 결정: 운영자 처분 2026-09-17(아크 계획 §6.1 ④) — **①②③④ 4건 전부**, ⑤(Phase 3 §7.11 이월) 미선택
- 기준선: 커널 **9522** · 런타임 **2445**(착수 시점 main `abd8ba44` 실측 — 아크 4항 중 3항 착지 후)

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
| ② 의 **실값** | 측정 원천 0건(§0.1). 형상만 넣고 값은 `null` → 커널이 `UNKNOWN`. 지어내지 않는다 |
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
| ② 에 그럴듯한 KRX 호가단위 표를 채운다 | 측정 원천 0건. 이 아크가 내내 지킨 「지어낸 거버넌스 값 0」을 마지막에 깬다 |
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

(비어 있음)
