# UNCHK-024 잔여 1필드 `max_age_bound` — VERIFICATION-PROFILE-002 신설 키 처분 패키지 (draft)

**Date:** 2026-09-04
**Track:** Phase 0 human gate register §8-1 (trustworthy-time bound 범주) · P0-1 Bounds-Approver 후속
**Operator directive:** 2026-09-04 「max_age_bound 키 신설 진행」
**Status:** DRAFT — §6 승인 기록은 빈 양식이다. 이 문서는 값을 승인하지 않는다.
**Precedent:** `docs/plans/2026-08-06-tos-phase0-p01-residual-17key-disposition-draft.md`(§4.1 도출 → §6 운영자 기입, ARCHITECTURE-GATE-STATUS §3.26) · PATCH-0054(키 등록은 승인이 아니다)

---

## 1. 문제

`tos/src/tos/backtest/resolver.py::BarTimeProjection` 의 아홉 주입 필드 중 여덟은 2026-09-02
(`44ffce5e`)에 처분이 확정됐다 — 2필드 1:1 키 결속 · `delay_bounds` 4키 합성 결속 · 5필드 구조적
비대상 선언. **`max_age_bound` 하나만 `UNBOUND`** 로 남았다: 그것은 `freshness_verdict` 가
`source_age + sum(delay_bounds)` 를 대조하는 **최상위 신선도 상한**인데, 그 역할을 지는 프로파일
키가 없었고 register §8-1 trustworthy-time 범주에도 그 항목이 없었다.

기계 노출: `tools/tos_completion_status.py` §7.4 D-1 이 `resolver`·`marketfeed` 두 사이트를
`VALUED+UNBOUND` 로 렌더한다(D0-5 는 MET — 갈린 처분도 결정된 처분이다). 계약 §11 은 이 상태로
2026-09-04 완료 판단이 발효됐다(`222dc4de`). 이 패키지는 그 판단을 바꾸지 않는다 — §8-1 잔여의
정직한 종결이다.

## 2. 신설 키 정의

| 항목 | 값 |
|---|---|
| 키 | `MAX_time_conservative_freshness_age_ms` |
| 블록 | `limits:` · PATCH-0054 trustworthy-time 군(`MAX_time_source_sequence_gap_ms` 다음) |
| 소유 결정 | ADR-002-008 §9 — 「Freshness SHALL be evaluated using a conservative upper bound … Freshness thresholds belong in an approved Safety Profile or Verification Profile.」 |
| 의미 | ADR-002-008 §9 보수적 상한 age(source age + 적용되는 delay-class bound 의 합)가 이 값을 넘거나, 상한 자체를 세울 수 없으면 `STALE` — 의존 신규 리스크를 거부한다. 0 으로 강제하거나 fresh 로 수용하지 않는다(§9 마지막 두 문장). |
| semantics | hard_maximum |
| applicable_scope | per critical-input consumer scope (bar-time projection 등 §9 상한을 소비하는 자리) |
| 결속 표면 | `resolver.py` BarTimeProjection docstring `VER-002-KEYS:` 선언 — `max_age_bound` 리터럴을 이 키로 교체(1:1). `tos/src/tos/marketfeed/__init__.py` 동일 선언 lockstep. |
| 등록 시 값 | `null` — 등록은 승인이 아니다(VER-002-001 §6 · PATCH-0054 선례). D-1 셀은 `UNBOUND` → `BLOCKED`(우주 안 · 값 없음)로 바뀐다. §6 기입 후 `VALUED`. |

**이름 근거.** 이 키는 ADR-002-008(trustworthy time) §9 의 산물이라 `MAX_time_*` 군을 따른다
(`MAX_time_transport_and_queue_uncertainty_ms` 등 같은 §9 의 항들과 같은 접두). «conservative
freshness age» 는 §9 첫 문장의 용어를 그대로 쓴다.

## 3. 기각한 대안

| 대안 | 기각 이유 (한 줄) |
|---|---|
| `MAX_critical_input_snapshot_age_ms`(1000) 재사용 | ADR-002-018 §14 가 snapshot age 와 delay class 를 **접지 말라**고 명시하고, resolver 도 `snapshot_age_bound` 를 별개 필드로 갖는다 — 총합 상한에 snapshot age 키를 붙이면 그 분리가 깨진다. |
| `MAX_time_health_snapshot_age_ms`(1000) 재사용 | 대상이 Time Health **proof** 의 소비자 보유 age 다 — bar 시각 투영의 총합 신선도가 아니다. 주석의 「including transport uncertainty」는 folded 표기로, 2026-07-21 설계 §8 이 바로 그 folding 을 §8-1 누락 근거로 삼았다. |
| `UNBOUND` 유지(정직 등재) | 2026-09-02 까지의 처분. 운영자 지시(2026-09-04)로 종결 경로를 택한다. 유지해도 §11 은 MET 였으므로 이 신설은 완료 판단의 근거를 «고치는» 것이 아니라 잔여를 «닫는» 것이다. |
| 검사기 쪽에서 `max_age_bound` 를 구조적 비대상으로 재분류 | 거짓이다 — 이 필드는 `MAX_*` 문턱 그 자체다(5필드와 달리 관측값·파생 합성·열거형이 아니다). |

## 4. 값 도출 (권고 · 승인 아님)

**권고값: 1000 ms.**

1. **만족 가능성 하한.** `freshness_verdict` 는 `source_age + sum(delay_bounds)` 를 이 상한과
   대조한다. 합성 결속된 delay bound 4키는 각 50 ms(승인값) → 합 200 ms. 상한이 200 ms 이하이면
   source age 0 인 bar 도 STALE 이 되어 키가 «모든 것을 거부»하는 상수가 된다. 하한 = 200 ms 초과.
2. **동류 앵커.** 2026-07-29 draft package §6-L1(정상-신선도 age 상한 38키 · 1000 ms · 「per
   scope; ≤ `MAX_normal_capability_age_ms`=1000, 느린 소스 클래스만 상향」)이 같은 클래스다.
   `MAX_critical_input_snapshot_age_ms`·`MAX_critical_input_consumer_receipt_age_ms` 도 1000 이다
   — 총합 상한이 그 구성항의 상한들보다 작을 이유가 없고, §6-L1 앵커를 넘길 이유도 없다.
3. **보수 방향.** 더 작은 값이 더 많이 거부한다(fail-closed 방향 = LOWER). 1000 ms 는 §6-L1
   앵커와 같아 상향이 아니다.
4. **런타임 영향 0.** 이 키는 D-1 **선언 결속**이다. `BarTimeProjection.max_age_bound` 값은
   테스트 픽스처와 호출자가 주입하며 프로파일 값을 읽는 코드는 없다(구조 파생: `tos/` 안에
   VERIFICATION-PROFILE-002.yaml 을 읽는 import 가 없다 — 방화벽상 불가). 값 승인은 EV-L1..L3
   하네스 상한의 등재이며 라이브 캘리브레이션이 아니다(프로파일 헤더 scope 문언과 동일).

## 5. 기계적 파급 (등록 커밋이 함께 움직여야 하는 자리)

| 자리 | 변화 |
|---|---|
| `VERIFICATION-PROFILE-002.yaml` + `-template.yaml` | 키 1 등록(null) · 헤더 census 163→164 · null 16→17 · 2026-09-04 기록 블록 |
| `tools/tos_spec_status.py` 전사 검사 | 헤더/게이트 status 의 census 문장 정규식이 「10 broker + 6 instance」괄호를 축자로 요구한다 → 신설 범주 1건을 문장과 정규식에 함께 반영(CI `tos-firewall` 의 `--check`) |
| `ARCHITECTURE-GATE-STATUS.md` | §3.27 등록 기록(Patch-0058 · APPLIED · 값 미승인) · :1075/:1375 census 문장 |
| `patches/VERIFICATION-PROFILE-002-Patch-0058.md` | 키 등록 패치 기록(PATCH-0054 양식) |
| `resolver.py` · `marketfeed/__init__.py` docstring | `VER-002-KEYS` 의 `max_age_bound` → 신설 키 · 결속 문단 재기술 |
| `PHASE0-UNCHECKABLE-REGISTER.csv` UNCHK-024 | ④ 잔여 문언 갱신(키 등록 · 값 승인 대기) |
| human-gate register §8-1 | 행 1 추가(27항) |
| `TOS-COMPLETION-STATUS.md` | `--write` 재생성 — D0-5[resolver]/[marketfeed] `VALUED+BLOCKED` |
| `tests/tools/test_tos_completion_status.py` | 실코퍼스 대조군(`max_age_bound` 우주 밖 핀) → 신설 키 우주 안·null 핀 |
| **계약 본문** | **무접촉.** :2974/:2979 의 「UNCHK-024 무영향」은 당시-참 기록이다. S-26 ⑥ 리셋 없음. |

§6 기입(값 승인) 시 추가로 움직이는 자리: 프로파일 값·마커 · census 147→148(헤더·게이트 status·
`tos_spec_status.py` 의 `147` 리터럴) · UNCHK-024 행 종결 · `--write` 재생성(`VALUED`).

## 6. 승인 기록 (Bounds-Approver · 빈 양식)

```yaml
key: MAX_time_conservative_freshness_age_ms
recommended_value_ms: 1000
approved_value_ms:            # 운영자 기입
approved_by:                  # operator (Bounds-Approver)
approved_at_utc:              # 운영자 기입
review_date: 2027-01-29       # 2026-07-29 승인분과 같은 주기
derivation: this package §4 at the commit that introduces it
```

이 양식이 채워진 diff 가 승인 기록이다(§3.26 선례 — «§6 기입 커밋을 인용하라, 도입 커밋이 아니라»).
