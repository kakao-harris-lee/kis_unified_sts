# 검증 실행 로그 (오케스트레이터 · 쓰기 가능한 환경) — HEAD 2c2bc607b95bdcd82cad66c6e8c6b71760e92bbc (C5)

Codex 샌드박스에 임시 디렉터리가 없어 pytest/--check 를 못 돌리는 문제의 대체 증거 — 자기 승인이 아니라 실행 출력 원문.

## pytest tests/tools/test_tos_completion_status.py -q -p no:cacheprovider

```
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
rc=0
```

Total test characters: 236; Failed tests: 0

## tools/tos_completion_status.py --check

```
d0a_entry_state=ENTRY_OK
  D0-5[backtest__init__]=UNBOUND (dsl_evaluation_budget_steps)
  D0-5[resolver]=VALUED+UNBOUND (MAX_future_timestamp_tolerance_ms:VALUED; MAX_critical_input_consumer_receipt_age_ms:VALUED; MAX_time_transport_and_queue_uncertainty_ms:VALUED; MAX_clock_domain_conversion_uncertainty_ms:VALUED; MAX_time_source_precision_ms:VALUED; MAX_time_source_sequence_gap_ms:VALUED; max_age_bound:UNBOUND)
  D0-5[results]=UNBOUND (dsl_evaluation_budget_steps)
  D0-5[construction]=UNBOUND (risk_budget:UNBOUND; per_unit_risk:UNBOUND; lot_size:UNBOUND; min_quantity:UNBOUND; max_quantity:UNBOUND; max_notional:UNBOUND)
  D0-5[records]=UNBOUND (risk_budget:UNBOUND; per_unit_risk:UNBOUND; lot_size:UNBOUND; lot_rounding:UNBOUND; min_quantity:UNBOUND; max_quantity:UNBOUND; max_notional:UNBOUND)
  D0-5[engine]=UNBOUND (dsl_evaluation_budget_steps; CONTRAST: MAX_dsl_evaluation_ms)
  D0-5[marketfeed]=VALUED+UNBOUND (MAX_future_timestamp_tolerance_ms:VALUED; MAX_critical_input_consumer_receipt_age_ms:VALUED; MAX_time_transport_and_queue_uncertainty_ms:VALUED; MAX_clock_domain_conversion_uncertainty_ms:VALUED; MAX_time_source_precision_ms:VALUED; MAX_time_source_sequence_gap_ms:VALUED; max_age_bound:UNBOUND)
RESULT: GREEN (violations=0)
```

rc=0

## 생성물 핵심 행

```
41:- `d0a_entry_state=ENTRY_OK`
129:- `U-12`: `MET`
131:- `U-15`: `MET`
143:- `D0-5`: `MET`
```

## ruff / black / mypy

```
All checks passed!
ruff rc=0
```

```
2 files would be left unchanged.
```

```
mypy rc=0
```

## 지정 claim 문장 — 계약 (마) 대조

```
3880:_D1_NO_DEPENDENCY_CLAIM_SENTENCE = (
3881-    "이 사이트 범위는 VERIFICATION-PROFILE-002 결속 값을 소비하지 않는다"
3882-)
```

```
「**이 사이트 범위는 VERIFICATION-PROFILE-002 결속 값을 소비하지
                 않는다**」를 검토했다는 기록이며, **canonical site_id** 와
```

## 범위 사실

```
tests/tools/test_tos_completion_status.py | 243 +++++++++++++++++++++++++++++-
 tools/tos_completion_status.py            |  83 ++++++++--
 2 files changed, 310 insertions(+), 16 deletions(-)
```

```
1 file changed, 468 insertions(+), 11 deletions(-)
```

```
tos/src/tos/marketfeed/__init__.py | 23 ++++++++++++++++++-----
 1 file changed, 18 insertions(+), 5 deletions(-)
```

```
(clean)
```

---

**File:** `.omc/review/20260904-154559/evidence/verification-run.md`  
**Lines:** 81  
**RC:** 0
