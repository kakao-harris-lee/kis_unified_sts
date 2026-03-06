# KIS Unified Trading Platform

> 주식/선물 통합 단기매매 시스템 (Stock/Futures Unified Short-Term Trading System)

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 개요 (Overview)

KIS Unified Trading Platform은 한국투자증권 API를 활용한 알고리즘 트레이딩 시스템입니다. 주식과 선물 거래를 단일 플랫폼에서 통합 관리하며, 설정 기반(Configuration-Driven) 전략 시스템을 제공합니다.

### 주요 기능 (Key Features)

- **전략 프레임워크**: 진입/청산 로직 분리, YAML 기반 설정
- **백테스팅**: MLflow 통합, Optuna 파라미터 최적화
- **실시간 거래**: Redis Streams 기반 이벤트 파이프라인
- **모의투자 (Paper Trading)**: 가상 브로커를 통한 전략 검증
- **모니터링**: Prometheus 메트릭, Grafana 대시보드, Telegram 알림

### 운영 런북 (Runbooks)

- 선물 RL 데이터 신뢰 구간/모델 교체 기준:
  [docs/futures_rl_data_trust_runbook.md](docs/futures_rl_data_trust_runbook.md)

## 빠른 시작 (Quick Start)

### 요구 사항 (Requirements)

- Python 3.11+
- Redis (선택)
- Docker & Docker Compose (선택)

### 설치 (Installation)

```bash
# 저장소 클론
git clone https://github.com/kakao-harris-lee/kis-unified-sts.git
cd kis-unified-sts

# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -e ".[dev]"

# 환경 설정
cp .env.example .env
# .env 파일 편집하여 KIS API 키 설정
```

### Docker로 실행

```bash
# 환경 설정
cp .env.example .env
# .env 파일 편집

# 서비스 시작
./scripts/docker-start.sh

# 또는 직접 실행
docker compose up -d

# 서비스 중지
./scripts/docker-stop.sh
```

### 접속 URL

- Trading API: http://localhost:8000
- Dashboard: http://localhost:8001
- Grafana: http://localhost:3000
- Prometheus: http://localhost:9090

### CLI 사용

```bash
# 백테스트 실행
sts backtest run --strategy bb_reversion --asset stock

# 모의투자 시작
sts paper start --strategy bb_reversion --capital 100000000

# 모의투자 상태 확인
sts paper status

# MLflow UI 실행
sts mlflow ui

# 파라미터 최적화
sts optimize --strategy bb_reversion --asset stock --metric sharpe_ratio --trials 100
```

## 아키텍처 (Architecture)

```
┌─────────────────────────────────────────────────────────────┐
│                    Strategy Layer                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ EntrySignal │  │ ExitSignal  │  │ PositionSizing      │ │
│  │ Generator   │  │ Generator   │  │ Calculator          │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│                    Trading Pipeline                          │
│  Regime Detection → Entry Signal → Monitoring → Exit Signal │
├─────────────────────────────────────────────────────────────┤
│                    Infrastructure                            │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐│
│  │ KIS API   │  │ Redis     │  │ ClickHouse│  │ MLflow   ││
│  └───────────┘  └───────────┘  └───────────┘  └──────────┘│
└─────────────────────────────────────────────────────────────┘
```

## 프로젝트 구조 (Project Structure)

```
kis-unified-trading/
├── shared/                 # 공유 모듈
│   ├── config/            # 설정 로더 및 스키마
│   ├── strategy/          # 전략 프레임워크
│   │   ├── entry/        # 진입 시그널 생성기
│   │   └── exit/         # 청산 시그널 생성기
│   ├── backtest/          # 백테스트 엔진
│   ├── paper/             # 모의투자 엔진
│   ├── indicators/        # 기술적 지표
│   ├── regime/            # 시장 상태 감지
│   ├── execution/         # 주문 실행
│   └── alerts/            # 알림 시스템
├── domains/               # 도메인별 구현
│   ├── stock/            # 주식 도메인
│   └── futures/          # 선물 도메인
├── services/              # 애플리케이션 서비스
│   ├── api/              # REST API
│   ├── dashboard/        # 대시보드 API
│   └── trading/          # 거래 오케스트레이터
├── config/                # 설정 파일
│   ├── strategies/       # 전략 설정 (YAML)
│   └── risk/             # 리스크 설정
├── cli/                   # CLI 명령어
└── tests/                 # 테스트 코드
```

## 전략 설정 (Strategy Configuration)

전략은 YAML 파일로 정의됩니다:

```yaml
# config/strategies/stock/bb_reversion.yaml
strategy:
  name: bb_reversion
  asset_class: stock

  entry:
    type: bb_lower_reentry
    params:
      bb_period: 20
      bb_std: 2.0
      rsi_oversold: 30
      volume_confirm: true

  exit:
    type: three_stage
    params:
      hard_stop_pct: 1.5
      breakeven_threshold_pct: 1.5
      trailing_stop_pct: 3.0
```

## 포함된 전략 (Included Strategies)

### 진입 전략 (Entry Strategies)

| 전략 | 설명 | 자산군 | 상태 |
|------|------|--------|------|
| **trend_pullback** | 일봉 필터 + BB/Williams 풀백 진입 + ATR 동적 청산 | 주식 | 검증 중 |
| **momentum_breakout** | 일봉 고가 근접 + 거래량 트렌드 + 돌파 진입 + ATR 청산 | 주식 | 검증 중 |
| BB Reversion | 볼린저 밴드 + RSI 평균회귀 | 주식 | 비활성화 |
| V35 Optimized | BB + RSI + MACD 복합 지표 | 주식 | 레거시 |
| OFI Momentum | 주문흐름 불균형 기반 | 선물 | 레거시 |
| Microstructure | 복합 마이크로스트럭처 | 선물 | 레거시 |

### 청산 전략 (Exit Strategies)

| 전략 | 설명 | 상태 |
|------|------|------|
| **ATR Dynamic** | ATR 기반 동적 스탑/트레일 (신규 전략용) | 활성 |
| 3-Stage Exit | Survival → Breakeven → Maximize | 활성 |
| Trailing Stop | 동적 트레일링 스탑 | 활성 |
| Time-Based | 시간 기반 청산 | 활성 |

### 3-Stage Exit 동작 원리

```
Stage 1: SURVIVAL (손실 최소화)
├── Hard Stop: -1.5%에서 무조건 청산
└── 목표: 자본 보전

Stage 2: BREAKEVEN (+1.5% 도달 시)
├── 스탑을 본전으로 이동
└── 목표: 손실 없는 거래 확보

Stage 3: MAXIMIZE (+3.0% 도달 시)
├── 트레일링 스탑 활성화
└── 목표: 수익 극대화
```

## 테스트 (Testing)

```bash
# 전체 테스트
pytest tests/ -v

# 특정 모듈 테스트
pytest tests/unit/strategy/ -v
pytest tests/integration/ -v

# 커버리지 리포트
pytest tests/ --cov=shared --cov=services --cov-report=html

# 빠른 테스트 (커버리지 없이)
pytest tests/ -q
```

## 환경 변수 (Environment Variables)

| 변수 | 설명 | 필수 |
|------|------|------|
| KIS_APP_KEY | 한투 API 앱 키 | O |
| KIS_APP_SECRET | 한투 API 앱 시크릿 | O |
| KIS_IS_REAL | 실전투자 여부 (false=모의) | O |
| API_KEY | 내부 API 인증 키 | O |
| REDIS_URL | Redis 연결 URL | X |
| TELEGRAM_BOT_TOKEN | 텔레그램 봇 토큰 | X |
| TELEGRAM_CHAT_ID | 텔레그램 채팅 ID | X |

## 문서 (Documentation)

- [API 문서](docs/api.md)
- [전략 가이드](docs/strategies.md)
- [배포 가이드](docs/deployment.md)
- [주식 전략 검증 요약](docs/STOCK_STRATEGY_VALIDATION_SUMMARY.md) - trend_pullback & momentum_breakout 검증 현황

## 기여 (Contributing)

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 라이선스 (License)

MIT License - 자세한 내용은 [LICENSE](LICENSE) 파일 참조

---

**주의사항**: 이 시스템은 교육 및 연구 목적으로 개발되었습니다. 실제 투자에 사용하기 전에 충분한 테스트와 백테스트를 수행하시기 바랍니다. 투자에 따른 손실은 본인 책임입니다.
