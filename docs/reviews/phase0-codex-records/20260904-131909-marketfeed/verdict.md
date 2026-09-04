# 독립 확인 심사 — §7.4 D-4 (마) 기록 후보 · site_id marketfeed (결과: 기록 자격 없음)

```yaml
adjudicator: codex
verdict: needs-attention
kind: d1-no-dependency independent review record (§7.4 D-4 (마))
site_id: marketfeed
reviewed_plan_paths:
  - tos/src/tos/marketfeed/__init__.py
  - tos/src/tos/marketfeed/_base.py
  - tos/src/tos/marketfeed/records.py
  - tos/src/tos/marketfeed/resolver.py
  - tos/src/tos/marketfeed/value.py
  - tos/src/tos/marketfeed/vocabulary.py
reviewed_scope_digest: b3bf8f18e3e2109939524d2f27076c09286a65953d5076f2eb3c00c71b260947
digest_kind: scope_content_digest (내용 전용 · HEAD 미포함)
reviewed_at_head: c8209c34af581e899b9f07418909dde27a605931
captured_at_utc: 2026-09-04T04:19:09Z
claim: marketfeed — tos/src/tos/marketfeed 패키지는 VERIFICATION-PROFILE-002 의 결속 값을 소비하지 않는다
job_id: review-mtmg2lz7-88qdyb
job_class: review
completed_at_utc: 2026-09-04T04:22:21.132Z
```

**needs-attention · claim 거짓 · findings 1(high).** 독립 확인 심사(§7.4 D-4 (마) 기록용 · adjudicator codex) 결과 marketfeed 는
NONE 사이트가 아니다: `tos/src/tos/marketfeed/resolver.py:152-208` 에서 주입된 `time_projection` 포트가 반환하는
`TimeAdmissionInputs`(future_tolerance · maximum_consumer_age_ms · delay_bounds — 6개 VER-002 키 결속 · max_age_bound — 우주 밖)
를 `DecisionTickPayload.time` 으로 소비·전달한다. 검사기의 토큰 스캔(163 키 직접 참조 0 · 로더 경로 0 · 선언 정확 1행)은 이
의미 의존을 못 본다 — 55차가 (iv) 독립 기록을 요구한 이유가 첫 실전에서 그대로 실증됐다.

## 수용검사 (오케스트레이터)

| # | sev | file:line 실재 | silenced | 비협상 배치 | 처분 |
|---|---|---|---|---|---|
| 1 | high | 실재 — resolver.py:152(주입) · :199-203(취득) · :204-208(payload) · `TimeAdmissionInputs` 필드 실측 일치 · `__init__.py:54-57` 의 «시간 좌표만 전달» 서술과 불일치 | 아니오 | 없음 | **채택** — 이 기록은 approve provenance 가 아니다. marketfeed 는 D-5 선언을 실제 의존(6 VER-002 키 + max_age_bound)으로 재분류(docstring 전용 편집 · C4 lockstep) → D-3 으로 VALUED+UNBOUND «판정됨». 실코퍼스에서 NONE 사이트 0 → D-4 (iv) 기록 생산 불필요 · UNCHK-026(NONE 공시 행) 은 근거 소멸로 제거 · max_age_bound 의 §13 소관은 UNCHK-024 가 이미 짐 |

기각 0 · 채택 1/1. 이 결과는 `docs/reviews/d1-no-dependency/` 에 착지하지 않는다(approve 만 기록 자격) — `.omc/review/20260904-131909-marketfeed/` 에 보존.


---

## Codex 판정 (verbatim — 손대지 않음)

```json
{
  "verdict": "needs-attention",
  "summary": "NO-SHIP: claim은 거짓이다. 전문 실측: tos/src/tos/marketfeed/__init__.py 165줄, _base.py 127줄, records.py 240줄, resolver.py 226줄, value.py 688줄, vocabulary.py 94줄(총 1,540줄). scope_content_digest b3bf8f18e3e2109939524d2f27076c09286a65953d5076f2eb3c00c71b260947도 재현했다. 163개 프로파일 키의 직접 토큰 참조와 프로파일 로더 경로는 0건이고 선언은 72행의 정확히 한 줄이지만, resolver의 런타임 주입 경계가 프로파일 결속 값과 우주 밖 bound를 포함하는 TimeAdmissionInputs를 받아 전달하므로 (a)와 (c)가 성립하지 않는다.",
  "findings": [
    {
      "severity": "high",
      "title": "TimeCoordinateProjection 포트가 프로파일 결속 값과 UNBOUND 값을 실제 payload로 소비한다",
      "body": "MarketFeedContextResolver는 `time_projection`을 주입받고(152행), 이를 호출해 반환된 `TimeAdmissionInputs`를 취득한 뒤(199–203행) `DecisionTickPayload.time`에 넣는다(204–208행). 이 타입은 delay_bounds, max_age_bound, future_tolerance, snapshot_age_bound, maximum_consumer_age_ms를 운반한다. 실제 생산자 `BarTimeProjection`은 future_tolerance와 maximum_consumer_age_ms를 각각 VER-002 키에, delay_bounds를 네 VER-002 키의 합성값에 결속하며, max_age_bound는 우주 밖 UNBOUND로 명시한다. 따라서 marketfeed가 단순 시간 좌표만 전달한다는 __init__.py:54–57의 설명과 달리 bound-bearing 설정 객체 전체를 런타임 경로에서 소비·전달한다. 직접 키 토큰이 없다는 검사기 결과는 이 의미 의존을 포착하지 못한다.",
      "file": "tos/src/tos/marketfeed/resolver.py",
      "line_start": 152,
      "line_end": 208,
      "confidence": 0.99,
      "recommendation": "marketfeed의 NO_DEPENDENCY 승인을 기록하지 말고, 모듈 docstring과 D-5 선언에 실제 결속된 6개 프로파일 키(MAX_future_timestamp_tolerance_ms, MAX_critical_input_consumer_receipt_age_ms, MAX_time_transport_and_queue_uncertainty_ms, MAX_clock_domain_conversion_uncertainty_ms, MAX_time_source_precision_ms, MAX_time_source_sequence_gap_ms) 및 우주 밖 bound인 max_age_bound를 공개해 키별 처분을 받도록 한다."
    }
  ],
  "next_steps": [
    "이 심판 결과는 approve provenance가 아니라 needs-attention으로 처리한다.",
    "marketfeed의 `VER-002-KEYS: NONE`을 실제 time-projection 의존 선언으로 재분류한 뒤 독립 심사를 다시 수행한다."
  ]
}
```

원문 전체는 `.omc/review/20260904-131909-marketfeed/codex-result.json` · focus 는 `.omc/review/20260904-131909-marketfeed/focus.txt`.
