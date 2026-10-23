# KRX 규정 원문 — 유가증권시장 주권 호가가격단위 사다리 (주식 트리 `price_band_ticks` 의 1차 출처)

- 수집: 2026-10-23 KST · 작업 목록 `docs/plans/2026-10-23-tos-local-parallel-work.md` L3
- 출처: **KRX 법무포털** `https://rule.krx.co.kr/out/index.do` → 유가증권시장 업무규정 · 같은 시행세칙. 포털은 POST 전용이라
  조문별 고정 URL 이 없다(선례 `../2026-10-08-krx-venue-limits/README.md` 와 같은 방식).
- 대상: `config/tos_runtime/cp3-setup-d-stock-005930/venue_constraint_policy.yaml::_model_view.shape_constraints.price_band_ticks` 7행.
  **값은 바꾸지 않는다** — 이 디렉터리는 인용 근거만 더한다.
- ⚠ 이 디렉터리의 파일은 브로커 API 아티팩트(JSON)가 아니라 **규정 텍스트**다. `../CITATION-RULE.md` §1 의 토큰은 JSON 에만 풀리므로
  선례처럼 값 옆에 **`파일명:행`** 을 적는다. `tools/tos_evidence_citation_check.py` 가 이 README 에서 푸는 토큰은 0 개다.

## 문서 판

| 문서 | 판 | 포털 bookid |
|---|---|---|
| 유가증권시장 업무규정 | 제61차 일부개정 2026-09-09 규정 제2497호 · 시행 2026-09-14 | `330007789` |
| 유가증권시장 업무규정 시행세칙 | 제177차 일부개정 2026-09-11 제2499호 · 시행 2026-09-14 | `330011206` |
| 같은 시행세칙 (연혁) | 제153차 일부개정 2023-08-08 · 시행 2023-09-01 | `204846256` |
| 같은 시행세칙 (연혁) | 제149차 일부개정 2022-11-11 · 시행 2022-11-14 | `204846252` |

## 파일

| 파일 | 무엇 |
|---|---|
| `kospi_enforcement_rule_177th_20260914.txt` | 시행세칙 제177차 본문 전문(포털 HTML 에서 추출한 텍스트) |
| `kospi_business_rule_61st_20260914.txt` | 업무규정 제61차 본문 전문(같은 방식) |
| `history_excerpt_enforcement_153rd_20230901_art32.txt` | 시행세칙 제153차의 제32조 발췌 — 2023-01-25 개편 뒤, 호·목 재편 전 |
| `history_excerpt_enforcement_149th_20221114_art32.txt` | 시행세칙 제149차의 제32조 발췌 — 2023-01-25 개편 전 |

## 값 (파일명:행)

조문 체인: 업무규정 제21조(호가가격단위는 세칙으로 정한다) → 시행세칙 제32조(호가단위)제2항제1호(주권 · 외국주식예탁증권 ·
신주인수권증서 · 신주인수권증권 · 수익증권) 가~사목.

| 트리 행 (원) | 규정 원문 | 어디 | 대조 |
|---|---|---|---|
| (조문 체인) | 업무규정 제21조 | `kospi_business_rule_61st_20260914.txt:288` | — |
| (조문 체인) | 시행세칙 제32조제2항 본문 · 제1호 | `kospi_enforcement_rule_177th_20260914.txt:722-723` | — |
| 2,000 미만 → 1 | 가목 「2,000원 미만인 종목 : 1원」 | `kospi_enforcement_rule_177th_20260914.txt:724` | 일치 |
| 2,000~5,000 미만 → 5 | 나목 「2,000원 이상 5,000원 미만인 종목 : 5원」 | `kospi_enforcement_rule_177th_20260914.txt:725` | 일치 |
| 5,000~20,000 미만 → 10 | 다목 「5,000원 이상 20,000원 미만인 종목 : 10원」 | `kospi_enforcement_rule_177th_20260914.txt:726` | 일치 |
| 20,000~50,000 미만 → 50 | 라목 「20,000원 이상 50,000원 미만인 종목 : 50원」 | `kospi_enforcement_rule_177th_20260914.txt:727` | 일치 |
| 50,000~200,000 미만 → 100 | 마목 「50,000원 이상 200,000원 미만인 종목 : 100원」 | `kospi_enforcement_rule_177th_20260914.txt:728` | 일치 |
| 200,000~500,000 미만 → 500 | 바목 「200,000원 이상 500,000원 미만인 종목 : 500원」 | `kospi_enforcement_rule_177th_20260914.txt:729` | 일치 |
| 500,000 이상 → 1,000 | 사목 「500,000원 이상인 종목 : 1,000원」 | `kospi_enforcement_rule_177th_20260914.txt:730` | 일치 |
| 시행 2023-01-25 | 부칙 <제2094호, 2022. 12. 22.> 제1조 | `kospi_enforcement_rule_177th_20260914.txt:2404-2405` | 일치 |

- 경계는 원문이 「이상 … 미만」이라 트리의 포함 경계(`band_max` = 다음 칸 시작 − 0.01원, ×100 정수)와 같은 뜻이다.
- 연혁 대조:
  - 제149차(2023-01-25 개편 전)의 사다리는 달랐다: 1,000원 미만 1원 등 7칸(`history_excerpt_enforcement_149th_20221114_art32.txt:11-17`).
  - 제153차는 현행과 같은 값이다(`history_excerpt_enforcement_153rd_20230901_art32.txt:11-17`). 제177차의 `2023. 10. 17.` 개정 표시는 같은 7칸을
    제1호 가~사목으로 재편한 것이다. 해석(측정 아님): 두 판의 7행을 눈으로 대조했고, 신구조문 대비표는 받지 않았다.
- 범위 밖(참고): 같은 항 제2호(ETF · ETN)는 2,000원 미만 1원 · 이상 5원(`kospi_enforcement_rule_177th_20260914.txt:731-733`), 제3호(ELW)는 5원(`:734`)이다.
  005930 은 주권이라 제1호다.

## 남은 것

- 브로커 `aspr_unit` 과의 대조: band 프로브가 세션마다 대조하고, 다르면 band 줄을 쓰지 않는다(PR #930). 장중 실측 기록은 아직 없다
  (작업 목록 L2-b, deploy 호스트).
- 코스닥 시행세칙의 같은 사다리는 이 디렉터리의 대상이 아니다(조문 체인 미확인).

## 재현

```text
GET  https://rule.krx.co.kr/out/index.do                         # 세션 + <meta id="_csrf">
POST https://rule.krx.co.kr/out/sch/outsearch.do                 # stxt=유가증권시장 업무규정 index=law_rule gbn=out
                                                                 # 결과 82건은 관련도 순이 아니라 목록 순 — 전 페이지를 훑어 제목으로 bookid 를 고른다
POST https://rule.krx.co.kr/out/regulation/regulationViewPop.do  # bookid=330011206 (시행세칙) · 330007789 (업무규정) noformyn=N
POST https://rule.krx.co.kr/out/regulation/regulationViewPop.do  # 연혁: bookid=204846256 · 204846252
```

조문이 본문에 있어 첨부(HWP) 다운로드는 쓰지 않았다. 포털 HTML 은 세션마다 CSRF 토큰이 달라 sha256 으로 결속하지 않는다 — 판은 위 표의
차수 · 규정 번호 · 시행일로 식별한다. 현행 판이 바뀌었으면 제32조제2항을 다시 대조한다.
