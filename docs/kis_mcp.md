# KIS MCP 운영 가이드

이 문서는 한국투자증권 공식 MCP 2종을 이 프로젝트에서 사용하는 방식만
정의한다. 자동매매 런타임은 기존 `KISClient`와 실행기 경로를 유지한다.

## 등록 상태

- 공식 체크아웃: `/home/deploy/.local/share/kis-mcp/open-trading-api`
- KIS Code Assistant MCP: Codex global, Claude local 등록
- KIS Trade MCP: Codex global, Claude local 등록
- Trade MCP 연결 URL: `http://localhost:3101/sse`

공식 문서:

- <https://apiportal.koreainvestment.com/tools-mcp>
- <https://github.com/koreainvestment/open-trading-api/tree/main/MCP/KIS%20Code%20Assistant%20MCP>
- <https://github.com/koreainvestment/open-trading-api/tree/main/MCP/Kis%20Trading%20MCP>

## 사용 원칙

- Code Assistant MCP는 API 검색, 샘플 코드, 파라미터 확인에 사용한다.
- Trade MCP는 조회 진단 전용이다. 시세, 잔고, 주문/체결 조회의 형태 비교까지만
  허용한다.
- Trade MCP를 주문 제출 경로로 쓰지 않는다. 실전/모의 주문은 기존
  `shared/execution`과 `shared/kis` 구현을 통해서만 처리한다.
- KIS 자격증명은 `.env` 또는 셸 환경변수에서만 읽는다. MCP 설정 파일에 키,
  시크릿, 계좌번호를 직접 쓰지 않는다.
- KIS Unified STS의 웹 포트는 8001 정책을 유지한다. Trade MCP 호스트 포트는
  다른 프로젝트의 3000 포트와 분리하기 위해 3101을 사용한다.

## 실행 명령

Code Assistant MCP는 stdio 서버로 등록되어 있어 별도 데몬이 필요 없다.

Trade MCP는 Docker/SSE 서버가 필요하다.

```bash
# 공식 Trade MCP 이미지 빌드
scripts/ops/kis_trade_mcp.sh build

# repo .env를 로드해 127.0.0.1:3101 -> container:3000 으로 실행
scripts/ops/kis_trade_mcp.sh start

# 상태 확인
scripts/ops/kis_trade_mcp.sh status

# 로그 확인
scripts/ops/kis_trade_mcp.sh logs

# 중지
scripts/ops/kis_trade_mcp.sh stop
```

`scripts/ops/kis_trade_mcp.sh build`는 현재 공식 Trade MCP 코드와 최신
`fastmcp 3.x`의 호환성 문제를 피하기 위해 외부 체크아웃의
`MCP/Kis Trading MCP/pyproject.toml`에 `fastmcp<3` 핀을 자동 적용한 뒤
이미지를 빌드한다.

사용되는 주요 환경변수는 기존 프로젝트 변수와 매핑된다.

| Trade MCP 변수 | 이 프로젝트 기본 매핑 |
| --- | --- |
| `KIS_APP_KEY` | `KIS_APP_KEY` 또는 `KIS_STOCK_APP_KEY` |
| `KIS_APP_SECRET` | `KIS_APP_SECRET` 또는 `KIS_STOCK_APP_SECRET` |
| `KIS_PAPER_APP_KEY` | `KIS_PAPER_APP_KEY`, 없으면 실전/주식 key |
| `KIS_PAPER_APP_SECRET` | `KIS_PAPER_APP_SECRET`, 없으면 실전/주식 secret |
| `KIS_ACCT_STOCK` | `KIS_STOCK_ACCOUNT_NO`의 앞 8자리 |
| `KIS_ACCT_FUTURE` | `KIS_FUTURES_ACCOUNT_NO`의 앞 8자리 |
| `KIS_PROD_TYPE` | `KIS_PROD_TYPE`, `KIS_ACCOUNT_PRODUCT_CODE`, 계좌 뒤 2자리, 없으면 `01` |

## 적용성 감사

공식 MCP 아티팩트와 현재 소스의 KIS endpoint 사용을 비교한다.

```bash
python scripts/analysis/kis_mcp_applicability_audit.py --format markdown
python scripts/analysis/kis_mcp_applicability_audit.py --format json
```

현재 감사 결과 요약:

- Code Assistant MCP 카탈로그: 334개 API
- Trade MCP tool 카탈로그: 166개 API
- 현재 로컬 KIS endpoint: 14개
- Trade MCP 카탈로그와 매칭: 13개
- 미매칭: `/uapi/domestic-stock/v1/trading/order-ats`

우선 적용 지점:

- `shared/kis/ranking_client.py`: 거래량순위, 등락률순위 파라미터와 시장 구분값
  확인.
- `shared/kis/client.py`: 현재가, 분봉, 잔고, 투자의견 조회 endpoint와 필수
  파라미터 확인.
- `shared/execution/executor.py`: 국내선물옵션 주문, 정정취소, 체결조회 schema
  확인.
- `config/kis/tr_ids.yaml`: TR ID 변경 여부 확인 시 Code Assistant MCP와 공식
  예제를 함께 대조.

## 운영 점검 예시

MCP를 이용한 운영 점검은 조회성 질문으로 제한한다.

- "KIS Code Assistant MCP로 국내주식 거래량순위 API 필수 파라미터를 찾아줘."
- "KIS Trade MCP로 모의 환경 삼성전자 현재가 조회 schema를 확인해줘."
- "현재 프로젝트의 `/uapi/domestic-futureoption/v1/trading/inquire-ccnl` 호출과
  공식 Trade MCP 파라미터 차이를 비교해줘."

금지 예시:

- "Trade MCP로 삼성전자 매수 주문 넣어줘."
- "자동매매 루프에서 Trade MCP를 직접 호출하도록 바꿔줘."
- "MCP가 찾은 값으로 리스크/수량 기준을 코드에 하드코딩해줘."
