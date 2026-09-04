# D-1(§7.4) 파생 규칙 — 에라타 후보 기록 (계약 밖, 판정 아님)

이 문서는 Codex verdict `review-mtljvycx-ouye7r`(job `review-mtljvycx-ouye7r`,
`.omc/review/20260903-165133/verdict.md`) finding 2 의 권고 "사이트 단위로 혼합
처분을 표현할 수 없는 문제는 계약 에라타 대상으로 별도 기록하되 계약 본문은
편집하지 마라"를 이행한다. **계약 문서
(`docs/plans/2026-08-12-tos-phase0-completion-contract-design.md`) 는 1바이트도
편집하지 않았다.** 이 기록 자체는 계약을 개정하지 않으며, 운영자 검토용 후보
메모다.

## (a) 사이트 하나가 여러 처분-등급 키에 걸쳐 있다

§7.4 완료 기준은 "7개 사이트 전부가 VALUED/BLOCKED/UNBOUND 중 **하나**를
배정받았을 때" D0-5 가 완료라고 말한다 — 사이트당 정확히 하나의 처분을
전제한다. 그러나 실측 결과 다수 사이트가 소속이 서로 다른 여러 키에 의존한다:

- `resolver`(`BarTimeProjection`): 실재 non-null 프로파일 키 6개(VALUED) +
  `max_age_bound`(우주 밖, UNBOUND) 1개.
- `engine`: 의존 키 `dsl_evaluation_budget_steps`(우주 밖, UNBOUND) + 대조
  인용 `MAX_dsl_evaluation_ms`(실재 키지만 이 사이트의 의존이 아님).

검사기는 이를 **UNBOUND > BLOCKED > VALUED** 우선순위로 접어(이번 구현의
설계 규칙 5 — 계약 §7.4 에는 이런 번호의 조항이 없다) 사이트 하나에 정확히
하나의 처분을 배정하되, 근거
(`basis`)에는 키별 세부 내역을 전부 노출한다(예: `max_age_bound∉VER-002 →
UNBOUND; VALUED: MAX_time_transport_and_queue_uncertainty_ms, …`). 이 우선순위
자체는 계약이 명시한 규칙이 아니라 이번 구현이 §11 완료 기준("전부 판정")과
§7.4 완료 기준("정확히 하나 배정")을 동시에 만족시키기 위해 채택한 해석이다
— 운영자 확인 대상.

## (b) `VER-002-KEYS:` 선언 행 문법은 D-2 의 구체 형식이다

계약 D-2: "키 공급은 표에 적는 행위가 아니라 **docstring 을 고치는 행위**다."
이번 구현은 이 요구를 만족하는 구체 문법으로 docstring 안에 정확히 한 줄의
선언(`VER-002-KEYS: ``k1``, ``k2``` / `; CONTRAST: ``k``` / `NONE`)을 도입했다.
`NONE`(의존 없음)은 §7.4 원문 어휘에 없는 사례이며, 이번 구현이 "이 사이트는
VER-002 결속 값을 소비하지 않는다"는 저작자 선언을 검사기의 **실측 스캔**
(module 은 패키지 디렉터리 재귀, class/method 는 그 파일)으로 검증하는
방식으로 파생했다 — `marketfeed` 사이트가 이 경로로 UNBOUND 판정을 받는다.

## (c) "VER-002 키가 아니다" 문언은 저작자 의무로 남지만 검사기 입력이 아니다

Codex finding 2 가 지적한 fail-open 은 산문("not a VERIFICATION-PROFILE-002
key" 류)을 처분 파생의 입력으로 사용한 것이었다. 이번 구현은 그 경로를
완전히 폐지했다(`_D1_UNBOUND_RE` 삭제, 관측 문자열로도 남기지 않음) — 처분의
유일한 입력은 `VER-002-KEYS:` 선언 + 프로파일 우주 대조뿐이다. 기존 산문
문장들(예: resolver.py 의 "``max_age_bound`` has no VERIFICATION-PROFILE-002
bound...")은 여전히 사람이 읽는 근거 문서로 docstring 에 남아 있지만, 검사기는
더 이상 그 문장을 파싱하지 않는다 — 순수 부수 효과 문서다.

## (d) 처분은 운영자 소관, 이 기록은 이행 메모

7사이트 실측 결과(2026-09-03 HEAD 기준, 전부 UNBOUND)와 그 근거는
`tos-spec/src/TOS-COMPLETION-STATUS.md` §D0-5 표에 기계 생성돼 있다. 이 문서는
그 결과를 바꾸지 않으며, D-1 파생 규칙의 해석상 빈틈 두 가지((a), (b))를
운영자가 검토할 수 있도록 별도로 기록한 것뿐이다. 계약 개정 여부와 시점은
운영자 소관이다. 이 기록은 Codex verdict `review-mtljvycx-ouye7r` finding 2
권고의 이행이다.

## (e) 재심 처분 (2026-09-04)

Codex 재심 `review-mtlo6mst-93vt2j` finding 1 은 (a)의 다중 키 접기 규칙과
(b)의 `NONE` 규칙 둘 다 §7.4 어휘 밖이며, 운영자 채택 전에는 완료값을
만들 수 없다고 판정했다(채택 3/3 — 오케스트레이터 수용검사 기록
`.omc/review/20260904-001114/verdict.md`). 검사기는 이제 아무것도 접지
않는다:

- 사이트 하나가 여러 키에 걸쳐 있어도 그 키들의 처분이 전부 같으면
  (우선순위 없이 유일하게 정해지는 경우) 그 처분을 그대로 사이트 처분으로
  쓴다 — `backtest__init__`/`results`/`construction`/`records`/`engine` 은
  전부 이 경로로 여전히 균일 `UNBOUND` 다.
- 키들의 처분이 갈리면(`resolver`: 실재 non-null 키 6개 VALUED + 
  `max_age_bound` 1개 UNBOUND) `UNDECIDED`(혼합 처분)로 멈춘다.
- `NONE` 선언은(`marketfeed`) 실측 스캔이 모순을 찾지 못해도 그 자체로는
  완료 처분의 근거가 되지 않는다 — `UNDECIDED`(§7.4 어휘 밖)로 유지된다.
  스캔은 `NONE` 자기신고와의 모순 여부를 걸러내는 용도로만 남는다.

실측 효과: `resolver` + `marketfeed` 가 `UNDECIDED` 로 전환되어 `D0-5` 는
`NOT MET`(2 UNDECIDED)이 된다. `marketfeed` 는 `UNCHK-026` 으로 신규 등재했고
`resolver` 는 기존 `UNCHK-024` 가 이미 다루고 있어 U-6 은 여전히 clean 이다.
`MET` 복원은 운영자의 계약 에라타 처분(§7.4 에 `NONE` 어휘 도입 및/또는
다중 키 처분 규칙 도입)으로만 가능하다 — 계약 본문은 이번에도 편집하지
않았다.

참고: `UNCHK-024`(PR #640)가 등재한 `max_age_bound` `UNBOUND` 는 이 에라타의
근거 자료이지 §7.4 규칙의 확장은 아니다 — 위 (a) 의 부수 실측 문단과 같다.
