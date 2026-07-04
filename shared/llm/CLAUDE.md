# LLM 시장 분석 모듈

KRX Open API와 OpenAI GPT를 활용한 통합 시장 분석 모듈.

## 모듈 구조

| 파일 | 설명 |
|------|------|
| `config.py` | LLMConfig - YAML/환경변수 기반 설정 |
| `data_classes.py` | 데이터 클래스 및 Enum (MarketSignal, RiskMode 등) |
| `krx_api_client.py` | KRX Open API 클라이언트 |
| `market_analyzers.py` | ETF/선물/옵션/채권/지수 분석기 |
| `unified_market_analyzer.py` | 통합 시장 분석 오케스트레이터 |
| `llm_analyzer.py` | LLM 기반 종목 분석 |

## 설정

설정은 `config/llm.yaml`과 환경변수에서 로드:

```yaml
# config/llm.yaml
krx_api:
  base_url: "http://data.krx.co.kr/svc/apis"
  timeout_seconds: 30
  sector_etfs:
    반도체: ["091160", "091170", "395160"]
    2차전지: ["305720", "371460", "394670"]
    # ...
```

```bash
# .env
KRX_API_KEY=your-api-key-here  # data.krx.co.kr에서 발급
OPENAI_API_KEY=your-openai-key
```

## 사용법

```python
from shared.llm import UnifiedMarketAnalyzer, LLMConfig

config = LLMConfig.from_yaml("config/llm.yaml")
analyzer = UnifiedMarketAnalyzer(config)
result = analyzer.run_analysis(mode="all")
report = analyzer.generate_report(result)
```

---

## KRX 데이터 기반 5대 전략

### 1. ETF 자금흐름 → 섹터 로테이션

| 조건 | 신호 |
|------|------|
| 거래량비율 > 1.5 + 수익률 > 2% | 섹터 강세 → 매수 |
| 거래량비율 < 0.8 + 수익률 < -2% | 섹터 약세 → 회피 |

### 2. 선물 베이시스 + 미결제약정

| 베이시스 | 해석 |
|---------|------|
| > +0.5pt (콘탱고) | 상승 기대, 롱 유리 |
| < -0.5pt (백워데이션) | 하락 우려, 숏/관망 |

| OI 변화 | 가격 | 해석 |
|--------|------|------|
| 증가 | 상승 | 신규 매수 → 상승 추세 강화 |
| 증가 | 하락 | 신규 매도 → 하락 추세 강화 |
| 감소 | 상승 | 숏커버링 → 추세 약화 |
| 감소 | 하락 | 롱청산 → 추세 약화 |

### 3. 옵션 풋콜비율 (역행 지표)

| PCR | 해석 | 신호 |
|-----|------|------|
| > 1.3 | 극단적 비관 | 🟢 반등 기대 |
| 0.7 ~ 1.3 | 중립 | 관망 |
| < 0.7 | 극단적 낙관 | 🔴 조정 주의 |

### 4. 채권 장단기 스프레드

| 스프레드 (10Y - 3Y) | 모드 | 전략 |
|--------------------|------|------|
| > 0.5%p | Risk On | 주식 비중 확대 |
| 0.2 ~ 0.5%p | Neutral | 균형 유지 |
| < 0.2%p | Risk Off | 현금/채권 비중 확대 |

### 5. KOSPI vs KOSDAQ 상대강도

| 상대강도 | 해석 |
|---------|------|
| KOSDAQ > KOSPI | 중소형/테마주 강세 |
| KOSPI > KOSDAQ | 대형주 강세 |

---

## KRX API 엔드포인트

| 데이터 | 엔드포인트 | 활용 |
|--------|-----------|------|
| KOSPI 지수 | `idx/kospi_dd_trd` | 시장 방향성 |
| KOSDAQ 지수 | `idx/kosdaq_dd_trd` | 대형/중소형 비교 |
| ETF 매매정보 | `etp/etf_dd_trd` | 섹터 로테이션 |
| 선물 매매정보 | `drv/fut_dd_trd` | 베이시스/OI |
| 옵션 매매정보 | `drv/opt_dd_trd` | 풋콜비율 |
| 채권지수 | `idx/bon_dd_trd` | Risk On/Off |
