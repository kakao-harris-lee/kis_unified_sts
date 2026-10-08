# KRX 규정 원문 — 코스피200선물·미니코스피200선물 호가수량한도 · 가격제한비율 (CP-3 결정 9 (a) 의 1차 출처)

- 수집: 2026-10-08 05:53 KST · 설계 문서 `docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md` §2
- 출처: **KRX 법무포털** `https://rule.krx.co.kr/out/index.do` → `KRX규정 → 파생상품시장규정`. 포털은 POST 전용이라
  조문별 고정 URL 이 없다. `law.krx.co.kr` 은 2026-10-08 현재 무응답(인용 금지).
- ⚠ 이 디렉터리의 파일은 브로커 API 아티팩트(JSON)가 아니라 **규정 텍스트**다. `CITATION-RULE.md` §1 의 토큰 형식
  (`<아티팩트>.json:<경로>=<값>`)은 JSON 에만 풀리므로 여기서는 쓸 수 없고, 값 옆에 **`파일명:행`** 을 적는다. 따라서
  `tools/tos_evidence_citation_check.py` 는 이 README 에서 **토큰 0 개**를 풀며, 그 PASS 는 이 README 를 검증한 것이 아니다
  — 아래 `파일명:행` 은 리뷰어가 손으로 푼다. 규정 텍스트용 형식을 `CITATION-RULE.md` 에 추가하는 것은 후속(설계 문서 §8).

## 문서 판

| 문서 | 판 | 포털 bookid |
|---|---|---|
| 파생상품시장 업무규정 | 제42차 일부개정 2026-04-15 규정 제2432호 · 시행 2026-06-29 | `210199976` |
| 파생상품시장 업무규정 시행세칙 | 제164차 일부개정 2026-07-06 세칙 제2474호 · 시행 2026-07-06 | `210228709` |

## 파일

| 파일 | 무엇 | 원본·sha256 |
|---|---|---|
| `byeolpyo17-2_order_quantity_limits.txt` | 시행세칙 [별표 17의2] 호가수량한도 및 누적호가수량한도(제61조·제79조의7 관련) — 파싱 텍스트 | 원본 HWP(미커밋) `3fed6e682b5986b1332ceefdefd4e880d221260742de9191fd224835d1b2d71d` · 서버 파일명 `210064641.hwp` |
| `byeolpyo14_price_limit_ratios.txt` | 시행세칙 [별표 14] 호가가격제한 관련 비율(제56조·제56조의2·제59조·제59조의2·제60조 관련) — 파싱 텍스트 | 원본 HWP(미커밋) `a3c753625f5359516d782da8139b00b41c1c0c4bd4dab029a054257220db2648` · 서버 파일명 `210064610.hwp` |
| `derivatives_enforcement_rule_164th_20260706.txt` | 시행세칙 제164차 본문 전문(포털 HTML 에서 추출한 텍스트) — 조문 체인의 근거 | 이 파일 자체가 커밋됨(sha256 은 `git hash-object` 로) |

원본 HWP 둘과 업무규정 제42차 전문 텍스트, 조사용 파서(`hwpread.py`, 표준 라이브러리만)는 호스트
`~/.local/state/tos/measure/krx-rules-20261008/` 에 있다. HWP 바이너리는 커밋하지 않고 위 sha256 으로 결속한다.
⚠ 파싱 텍스트의 `0. 05포인트` 같은 숫자 안 공백은 포털 레이아웃 산물이다(값은 0.05).

## 값 (파일명:행)

| 값 | 어디 |
|---|---|
| **미니코스피200선물거래** 호가수량한도 **정규거래 10,000(1,000)계약 · 야간거래 5,000(500)계약** | `byeolpyo17-2_order_quantity_limits.txt:41-45` |
| 코스피200선물거래(·KRX300·변동성지수·ETF 선물) 호가수량한도 정규거래 2,000(200)계약 | `byeolpyo17-2_order_quantity_limits.txt:29-31` |
| 같은 행 야간거래 1,000(100)계약 | `byeolpyo17-2_order_quantity_limits.txt:33` |
| 괄호 안 숫자 = 해당 상품이 유동성관리상품인 경우의 한도(비고) | `byeolpyo17-2_order_quantity_limits.txt:118` |
| 주가지수선물거래 가격제한비율 **1단계 8% · 2단계 15% · 3단계 20%** | `byeolpyo14_price_limit_ratios.txt:19-25` |
| 호가수량단위·거래수량단위 1계약 (시행세칙 제4조의5제1항·제2항) | `derivatives_enforcement_rule_164th_20260706.txt:779-781` |
| 거래승수 코스피200선물 25만 / 미니코스피200선물·KRX300선물 5만 (제4조의8제1호·제2호) | `derivatives_enforcement_rule_164th_20260706.txt:838-841` |
| 호가가격단위 코스피200선물 0.05 / **미니코스피200선물 0.02** 포인트 (제4조의9제1호·제2호) | `derivatives_enforcement_rule_164th_20260706.txt:851-854` |

조문 체인(시행세칙 전문은 위 파일):

- 호가수량한도: 업무규정 제71조 → 시행세칙 제61조제1항(별표 17의2 참조 · 단서: 거래소가 변경 가능) · 제61조제2항(누적한도는
  회원 자기거래계좌·사후위탁증거금계좌 한정) · **제61조제3항(회원은 그 수량 이내로 낮게 정할 수 있다 — 규정값은 상한)**.
- 가격제한: 업무규정 제70조 → 시행세칙 제55조(기준가격 = 직전 거래일 정산가격, 제1항제2호; 제4항 호가가격단위 조정) · 제56조
  (상한가 내림·하한가 올림) · 제56조의2(단계 확대 — 정규거래 전용 · 개시 후 15분 이후 · 도달 후 5분 · 야간 및 08:45~09:00 은
  1단계만 · mini 는 코스피200선물과 동일 비율) → 별표 14 제1호.

## 재현

```text
GET  https://rule.krx.co.kr/out/index.do                         # 세션 + <meta name="_csrf">
POST https://rule.krx.co.kr/out/sch/outsearch.do                 # stxt=호가수량한도 index=law_rule gbn=out
POST https://rule.krx.co.kr/out/regulation/regulationViewPop.do  # bookid=210228709 noformyn=N
POST https://rule.krx.co.kr/login/getData.do                     # X-CSRF-TOKEN → 다운로드 토큰
POST https://rule.krx.co.kr/Download.do                          # Serverfile=210064641.hwp folder=ATTACH (별표 17의2)
                                                                 # Serverfile=210064610.hwp folder=ATTACH (별표 14)
```

다운로드한 HWP 의 sha256 이 위 표와 같으면 같은 판이다. 다르면 별표가 개정된 것이므로 설계 문서 §2.1 의 값을 재대조한다.
