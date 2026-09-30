# 증거 README 인용 규율 (C-3 / F-4)

- 도입: 2026-09-26 · 상위 계획 `docs/plans/2026-09-18-tos-config-adoption-and-carryover-plan.md` W-C C-3
  (원 처분 F-4 — `docs/plans/2026-09-17-tos-run-boot-and-real-sources-arc-plan.md` §F 표).
- 검사기: `tools/tos_evidence_citation_check.py` · 테스트 `tests/tools/test_tos_evidence_citation_check.py`
  (tos-firewall 의 governance 배터리가 `tests/tools/test_tos_*.py` 로 자동 수집한다).

## 1. 규칙

**증거 README 에 적는 값은, 그 값이 들어 있는 아티팩트와 필드를 함께 적는다.** 형식은 인라인
코드 토큰 하나다:

```text
`<아티팩트 파일명>.json:<점 경로>=<값>`
```

- 아티팩트는 README 와 **같은 디렉터리**의 파일명만 쓴다(경로 불가).
- 점 경로는 키를 `.` 로, 리스트 원소를 `[n]` 으로 잇는다 — `measurements.truncation_risk.page_row_counts[1]`.
- 값은 문자열이면 그대로, 그 밖은 compact JSON 으로 적는다 — `25`, `0.5`, `true`, `null`, `[20,5]`.
  JSON 이 `6686725.0` 이면 `6686725.0` 이라 적는다(`6,686,725` 는 사람이 읽기 좋게 **옆에** 덧붙인다).
- 해석·추정은 인용 토큰을 달지 않고 **「해석(측정 아님)」** 으로 따로 표시한다(기존 README 관례).

## 2. 왜 — 같은 결함이 두 번 났다

| PR | README 가 쓴 것 | 실제 |
|---|---|---|
| #676 (`15ede78b`) | `P-BAL-20260915T131009Z.json` 행에 「SK텔레콤 017670 보유 포함」 | 그 아티팩트의 `observations` 에는 페이지별 행 수·`rt_cd`·연속조회 키뿐, `pdno` 없음 |
| #729 (`0d64b3ef`) | `P-BAL-20260916T233126Z.json` 행에 「SK텔레콤 017670 1주 보유(평단 90,900)」 | `pdno` 없는 아티팩트에 종목 사실 귀속(재발) + 「평단 90,900」은 **어느 아티팩트에도 없음** |

둘 다 리뷰가 사후에 잡았다. 공통점은 **값 옆에 아티팩트 이름이 있어서 출처가 있어 보였다**는 것이다.
이 형식으로 적으면 #729 의 주장은 `…233126Z.json:observations[0].pdno=017670` 이 되고, 검사기가
「field path does not exist」로 막는다(`test_the_729_claim_would_have_failed`).

## 3. 검사기가 하는 것 / 하지 않는 것

- **한다:** 모든 인용 토큰을 풀어 본다 — 파일 존재 · 경로 존재 · 값 일치. 하나라도 어긋나면 종료코드 1.
  건너뛰기는 없다.
- **하지 않는다:** 산문 속 **인용 없는** 숫자를 찾지 못한다. 그건 여전히 리뷰 규칙이다. 다만 이제 리뷰가
  물을 질문이 하나로 줄어든다 — 「이 값에 토큰이 붙어 있는가」. 붙어 있으면 참·거짓은 기계가 판정한다.

```bash
python tools/tos_evidence_citation_check.py            # 기본 집합: 캠페인 README 전부 + tos-evidence
python tools/tos_evidence_citation_check.py PATH...    # 지정한 README 만
```

## 4. 소급 적용 시연 (2026-09-26)

`2026-09-11-p02-t3-campaign/README.md` 의 세 곳을 이 형식으로 고쳤다. 값은 바꾸지 않았다 —
원래 적힌 값이 아티팩트와 일치함을 검사기가 확인했다(8 인용 전부 PASS).

1. 09-11 `P-BAL` 행 — 25행 / `[20,5]` / page_size 20 / `TRUNCATION_RISK_DEMONSTRATED` /
   `BROKER_END_OF_SET` 다섯 값에 필드 경로를 붙였다.
2. 09-17 본문 — `hldg_qty=1`, 예수금 `6686725.0` 을 `P-CA-20260917T130246Z.json:measurements.baseline.*` 로.
3. 09-17 08:31 행 — #729 조치가 산문으로 적은 `measurements.baseline.hldg_qty=1` 을 토큰으로.

나머지 행은 소급하지 않았다. 새로 쓰는 행부터 이 형식을 따른다. 오래된 행을 고칠 일이 생기면 그때 함께
옮긴다.
