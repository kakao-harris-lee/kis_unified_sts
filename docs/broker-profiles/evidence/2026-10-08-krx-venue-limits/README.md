# KRX 규정 원문 — 코스피200선물 호가수량한도 · 가격제한비율 (CP-3 결정 9 (a) 의 1차 출처)

- 수집: 2026-10-08 05:53 KST · 설계 문서 `docs/plans/2026-10-08-tos-cp3-venue-limit-source-and-probe-design.md` §2
- 출처: **KRX 법무포털** `https://rule.krx.co.kr/out/index.do` → `KRX규정 → 파생상품시장규정`. 포털은 POST 전용이라
  조문별 고정 URL 이 없다. `law.krx.co.kr` 은 2026-10-08 현재 무응답(인용 금지).
- 이 디렉터리의 파일은 브로커 API 아티팩트(JSON)가 아니라 **규정 별표의 파싱 텍스트**다. `CITATION-RULE.md` 의 인용
  토큰은 JSON 아티팩트용이므로 여기서는 쓰지 않고, 값 옆에 **파일명:행** 을 적는다.

## 문서 판

| 문서 | 판 | 포털 bookid |
|---|---|---|
| 파생상품시장 업무규정 | 제42차 일부개정 2026-04-15 규정 제2432호 · 시행 2026-06-29 | `210199976` |
| 파생상품시장 업무규정 시행세칙 | 제164차 일부개정 2026-07-06 세칙 제2474호 · 시행 2026-07-06 | `210228709` |

## 파일

| 파일 | 무엇 | 원본(HWP, 미커밋) sha256 | 원본 서버 파일명 |
|---|---|---|---|
| `byeolpyo17-2_order_quantity_limits.txt` | 시행세칙 [별표 17의2] 호가수량한도 및 누적호가수량한도(제61조·제79조의7 관련) — 파싱 텍스트 | `3fed6e682b5986b1332ceefdefd4e880d221260742de9191fd224835d1b2d71d` | `210064641.hwp` |
| `byeolpyo14_price_limit_ratios.txt` | 시행세칙 [별표 14] 호가가격제한 관련 비율(제56조·제56조의2·제59조·제59조의2·제60조 관련) — 파싱 텍스트 | `a3c753625f5359516d782da8139b00b41c1c0c4bd4dab029a054257220db2648` | `210064610.hwp` |

원본 HWP 둘과 시행세칙 제164차·업무규정 제42차 전문 텍스트, 조사용 파서(`hwpread.py`, 표준 라이브러리만)는 호스트
`~/.local/state/tos/measure/krx-rules-20261008/` 에 있다. 바이너리는 커밋하지 않고 위 sha256 으로 결속한다.

## 값 (파일명:행)

| 값 | 어디 |
|---|---|
| 코스피200선물거래 호가수량한도 **정규거래 2,000(200)계약 · 야간거래 1,000(100)계약** | `byeolpyo17-2_order_quantity_limits.txt:29-31` (괄호 = 유동성관리상품 지정 시, 비고) |
| 주가지수선물거래 가격제한비율 **1단계 8% · 2단계 15% · 3단계 20%** | `byeolpyo14_price_limit_ratios.txt:19-25` |

조문 체인(시행세칙 본문은 호스트 사본 `derivatives_enforcement_rule_164th_20260706.txt`):

- 호가수량한도: 업무규정 제71조 → 시행세칙 제61조제1항(별표 17의2 참조 · 단서: 거래소가 변경 가능) · 제61조제2항(누적한도는
  회원 자기거래계좌·사후위탁증거금계좌 한정) · **제61조제3항(회원은 그 수량 이내로 낮게 정할 수 있다 — 2,000 은 상한)**.
- 호가수량단위·거래수량단위 1계약: 업무규정 제9조의2제1항 → 시행세칙 제4조의5제1항·제2항(`…:779`).
- 호가가격단위 0.05 포인트: 업무규정 제12조 → 시행세칙 제4조의9제1호(`…:851`). 거래승수 25만: 제4조의8제1호.
- 가격제한: 업무규정 제70조 → 시행세칙 제55조(기준가격 = 직전 거래일 정산가격, 제1항제2호) · 제56조(상한가 내림·하한가 올림) ·
  제56조의2(단계 확대 — 정규거래 전용 · 개시 후 15분 이후 · 도달 후 5분 · 야간 및 08:45~09:00 은 1단계만) → 별표 14 제1호.

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
