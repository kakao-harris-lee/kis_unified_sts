프로젝트 리팩토링 지시서

목적

현재 시스템은 한국투자증권 Open API Sample의 Strategy Builder를 기반으로 개발되었으며, YAML 기반 전략 정의 기능을 유지하고 있다.

그러나 자체 구현한 기술지표 계산기와 전략 실행 엔진의 유지보수 비용이 매우 높고, 버그 발생 빈도가 높아 장기간 안정적인 백테스트 및 실거래 검증이 어려운 상태이다.

따라서 검증된 오픈소스 라이브러리를 적극 활용하여 시스템을 재설계한다.

⸻

최우선 목표

직접 구현한 모든 기술지표 계산 로직을 제거한다.

직접 구현한 포지션 관리 및 전략 실행 로직을 최소화한다.

전략은 YAML만 작성하면 실행될 수 있는 선언형(Declarative) 구조로 변경한다.

새로운 기술지표 추가 시 Registry 등록만으로 사용할 수 있도록 설계한다.

⸻

반드시 사용할 라이브러리

기술지표

* TA-Lib

전략 및 백테스트

* vectorbt

데이터 처리

* pandas
* numpy

실거래

* 한국투자증권 Open API

⸻

반드시 유지해야 하는 기능

* 기존 YAML Strategy Builder
* 기존 Strategy Builder UI
* 기존 YAML 포맷과 최대한의 호환성
* 한국투자 Open API Adapter
* 실시간 주문 기능
* 실시간 데이터 수신 기능

⸻

새 아키텍처

                YAML Strategy
                      │
                      ▼
             Strategy Compiler
                      │
                      ▼
            Indicator Registry
                      │
                      ▼
              TA-Lib Adapter
                      │
                      ▼
              Indicator Context
                      │
                      ▼
             Signal Generator
                      │
                      ▼
             vectorbt Engine
                      │
                      ▼
         Portfolio / Position Engine
                      │
                      ▼
           Futures Risk Engine
                      │
                      ▼
       Korea Investment Adapter
                      │
                      ▼
                Live Trading

⸻

설계 원칙

1. Strategy Builder

Builder는 계산하지 않는다.

Builder는 Strategy YAML만 생성한다.

⸻

2. Indicator Engine

Indicator Engine은

YAML

↓

IndicatorSpec

↓

TA-Lib

호출만 수행한다.

직접 EMA, RSI 등을 계산하는 코드는 모두 제거한다.

⸻

3. Indicator Registry

모든 지표는 Registry로 관리한다.

예시

EMA

RSI

MACD

ATR

ADX

CCI

BBANDS

MFI

OBV

ROC

STOCH

등 TA-Lib에서 제공하는 모든 지표를 Registry에서 관리한다.

새로운 지표 추가는 Registry 수정만으로 가능해야 한다.

⸻

4. Strategy Engine

전략 엔진는 계산을 하지 않는다.

전략 엔진은

Indicator Context

만 읽는다.

예시

RSI < 30

EMA20 > EMA60

MACD Cross

ATR > ATR SMA

등의 조건만 평가한다.

⸻

5. vectorbt

포지션 상태

주문 상태

수익률 계산

Portfolio

Backtest

Performance

Position

Drawdown

Sharpe

Trade Log

등은 vectorbt 기능을 최대한 활용한다.

직접 구현을 최소화한다.

⸻

6. Futures Engine

TA-Lib에서 처리하지 않는 선물 특화 기능을 별도 모듈로 분리한다.

예)

외국인 선물 순매수

미결제약정

Basis

Contango

Backwardation

Roll-over

틱 가치

증거금

헤지 비율

선물/현물 동시 보유 상태

현물 헤지 계산

이 기능은 Futures Context Engine에서 관리한다.

⸻

7. Hedge Engine

현물

코스피200 선물

동시 운용을 지원한다.

예)

현물 Long

선물 Short

부분 헤지

전체 헤지

헤지 비율 계산

노출(Exposure) 계산

순노출(Net Exposure) 계산

등을 독립 모듈로 구현한다.

⸻

8. Risk Engine

ATR 기반 Stop

Trailing Stop

Max Drawdown

Position Size

일 최대 손실

동시 진입 제한

레버리지 제한

증거금 체크

등을 Risk Engine으로 분리한다.

⸻

9. 실행 계층

실거래와 백테스트는 동일한 Strategy를 사용한다.

차이점은 실행 계층만 다르다.

Backtest

↓

vectorbt

Live

↓

한국투자 API

전략은 동일하게 유지한다.

⸻

YAML 역할

YAML은 계산식을 가지지 않는다.

YAML은 선언만 한다.

예)

Indicator

Condition

Entry

Exit

Risk

Portfolio

만 정의한다.

⸻

직접 구현 금지

다음 기능은 직접 구현하지 않는다.

EMA

MACD

ATR

RSI

Bollinger

Position Engine

Portfolio Engine

Trade Statistics

Drawdown

Sharpe

Trade History

가능한 모든 기능은 TA-Lib 또는 vectorbt를 사용한다.

⸻

최종 목표

플랫폼을 개발하는 것이 아니라 전략을 개발하는 플랫폼으로 전환한다.

직접 유지보수하는 코드를 최소화한다.

검증된 라이브러리를 적극 활용한다.

새로운 전략은 YAML만 작성하면 즉시 백테스트와 실거래가 가능해야 한다.

모든 모듈은 단일 책임 원칙(SRP)을 준수하고, 의존성은 Registry와 Adapter 계층을 통해서만 연결되도록 설계한다.

리팩토링은 기존 기능을 최대한 유지하면서 단계적으로 진행하며, 각 단계마다 테스트 가능한 상태를 유지한다. 먼저 현재 구조를 분석하여 변경 영향도를 정리하고, 이후 아키텍처에 맞춰 모듈을 재구성한 뒤, 기존 테스트와 신규 테스트를 작성하여 기능 동일성을 검증한다.
