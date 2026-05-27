KOSPI200 선물 Daily 추세추종 전략 개발 설계서

## 2026-05-27 구현 판단

실제 운용/저장 데이터 확인 결과, 기존 인트라데이 추세추종 포트는 PF < 1 / 음수 Sharpe였고
현재 Setup A/C paper 경로도 아직 유효한 체결 표본이 부족하다. 따라서 본 문서의 MVP는
신규 추세추종 진입 전략이 아니라 **Daily Regime Trend Filter**로 축소 구현한다.

- Setup A/C가 만든 장중 후보 시그널의 방향이 일봉 추세와 충돌하면 차단한다.
- 일봉 데이터가 없으면 기본은 permissive로 두어 데이터 장애가 곧바로 거래 중단으로 이어지지 않게 한다.
- 선물 일봉 컨텍스트는 `config/execution.yaml`의 cross-asset reference symbol을 사용해
  `kospi200f_1m`을 일봉으로 집계하고, 실거래 대상 미니 코드(`A05xxx`)의 지표 컨텍스트로 주입한다.
- 계약 스펙은 본 문서의 full-size 기준이 아니라 repo 표준인
  `config/execution.yaml::futures_contract_spec.kospi200_mini`
  (50,000 KRW/pt, 0.02pt tick, 1,000 KRW/tick)을 따른다.

1. 목표

KOSPI200 선물에서 Daily 방향성 판단 + Intraday 진입/청산 구조의 반자동/자동 전략 시스템을 구현한다.

핵심 목표는 다음이다.

* Daily 기준으로 매수/매도 우위 판단
* 장중에는 5분/15분봉 기준으로 눌림목 또는 돌파 진입
* 변동성, 외국인 선물 수급, 미국장 흐름, 환율을 필터로 사용
* 횡보장에서는 거래 빈도 축소
* 손실 제한, 포지션 사이징, 자동 중단 조건 포함

KOSPI200 선물은 KRX 기준 계약승수 250,000원, 호가 단위 0.05pt, 1틱 가치 12,500원이며 정규장은 08:4515:45, 최종거래일은 15:20까지 거래된다. 야간장은 18:0006:00이다.

⸻

2. 전략 컨셉

전략명

K200 Daily Regime Trend Following

기본 구조

Daily Regime 판단
    ↓
거래 가능 방향 결정
    ↓
Intraday 타점 탐색
    ↓
ATR 기반 포지션 사이징
    ↓
손절 / 트레일링 / 일중 청산

⸻

3. 데이터 요구사항

3.1 필수 데이터

구분	데이터	주기
KOSPI200 선물	OHLCV, 거래량, 미결제약정	일봉, 15분봉, 5분봉
KOSPI200 현물지수	OHLCV	일봉
외국인 선물 수급	순매수 계약수, 누적 순매수	일봉, 가능하면 장중
프로그램 매매	차익/비차익 순매수	일봉, 장중
USD/KRW	환율	일봉, 장중
미국 지수	Nasdaq100, S&P500 futures	일봉, 야간
변동성	ATR, realized volatility	계산값

3.2 선택 데이터

구분	데이터
옵션	Put/Call ratio, Max pain, 만기일
뉴스	CPI, FOMC, NVIDIA 실적, 반도체 뉴스
ETF/수급	KODEX 레버리지/인버스 거래대금
반도체	삼성전자, SK하이닉스 일봉 추세

⸻

4. Daily Regime 판단

4.1 기본 지표

일봉 기준으로 아래 값을 계산한다.

ema20
ema60
ema120
rsi14
atr14
atr20_pct = atr20 / close
donchian_high_20
donchian_low_20
foreign_futures_net_5d
foreign_futures_net_20d
usdkrw_return_5d
nasdaq_return_1d
nasdaq_ema20_slope

⸻

5. 방향성 판단 로직

5.1 Long Bias 조건

Long Bias = True if:
1. close > ema20
2. ema20 > ema60
3. ema20 slope > 0
4. rsi14 >= 50
5. foreign_futures_net_5d > 0
6. usdkrw_return_5d <= +1.5%
7. nasdaq_return_1d > -1.0%

5.2 Short Bias 조건

Short Bias = True if:
1. close < ema20
2. ema20 < ema60
3. ema20 slope < 0
4. rsi14 <= 50
5. foreign_futures_net_5d < 0
6. usdkrw_return_5d >= 0
7. nasdaq_return_1d < +1.0%

5.3 No Trade 조건

No Trade if:
1. abs(ema20 - ema60) / close < 0.5%
2. atr20_pct < 최근 60일 하위 30%
3. rsi14 between 45 and 55
4. 옵션 만기일 당일 10:30 이전
5. FOMC/CPI 발표 직전 야간 또는 익일 장초반
6. 전일 미국장 급등락 후 국내장 갭이 ATR의 1.5배 이상

⸻

6. Intraday 진입 로직

6.1 Long Entry

Daily Regime이 Long Bias일 때만 매수 진입 허용.

A. VWAP Reclaim

조건:
1. 장 시작 후 09:05 이후
2. 가격이 VWAP 아래에서 위로 회복
3. 5분봉 종가가 VWAP 위
4. 거래량이 최근 20개 5분봉 평균 이상
5. 직전 고점 돌파
진입:
- 5분봉 종가 기준 시장가 또는 지정가
손절:
- VWAP 하회
- 또는 진입가 - 0.8 * intraday ATR

B. Opening Range Breakout

조건:
1. 08:45~09:15 고가를 opening_range_high로 저장
2. 09:15 이후 opening_range_high 상향 돌파
3. Daily Long Bias 유지
4. 외국인 선물 장중 순매수 증가
진입:
- 돌파 후 1틱 위 지정가 또는 5분봉 종가 진입
손절:
- opening_range_high 재하회

C. Pullback to EMA

조건:
1. 15분봉 ema20 상승
2. 가격이 ema20 근처까지 눌림
3. 5분봉 bullish reversal candle 발생
4. RSI 5분봉 40~55에서 반등
진입:
- 반등 캔들 고가 돌파
손절:
- 눌림 저점 이탈

⸻

6.2 Short Entry

Daily Regime이 Short Bias일 때만 매도 진입 허용.

Long Entry의 반대 조건 사용.

1. VWAP 하향 이탈
2. Opening Range Low 하향 돌파
3. 15분봉 ema20 하락 중 되돌림 후 재하락

⸻

7. 청산 로직

7.1 기본 청산

1차 익절:
- 진입가 + 1.0R 도달 시 50% 청산
2차 청산:
- 2.0R 도달
- 또는 trailing stop hit
- 또는 장 마감 10분 전
트레일링:
- Long: max(previous_stop, highest_price - 1.2 * intraday_ATR)
- Short: min(previous_stop, lowest_price + 1.2 * intraday_ATR)

7.2 강제 청산

1. 일일 손실 한도 도달
2. 체결 후 30분 이내 반대 신호 발생
3. 외국인 선물 수급 급반전
4. 장중 변동성이 ATR 기준 비정상 확대
5. 시스템 데이터 지연 또는 주문 오류

⸻

8. 리스크 관리

8.1 포지션 사이징

risk_per_trade = account_equity * 0.005  # 계좌의 0.5%
tick_value = 12500
point_value = 250000
stop_points = abs(entry_price - stop_price)
risk_per_contract = stop_points * point_value
contracts = floor(risk_per_trade / risk_per_contract)
contracts = min(contracts, max_contract_limit)

8.2 제한 조건

1회 거래 손실 한도: 계좌의 0.5%
일일 손실 한도: 계좌의 1.5%
일일 최대 거래 횟수: 3회
연속 손실 2회 발생 시 당일 거래 중단
월간 손실 -6% 도달 시 전략 중단

⸻

9. 백테스트 설계

9.1 기간

최소: 2016년 이후
권장: 2010년 이후
분봉 데이터 가능 기간 전체

9.2 수수료/슬리피지

수수료: 증권사 실제 수수료 입력 가능
슬리피지:
- 기본 1틱
- 변동성 확대 구간 2~3틱

9.3 검증 방식

1. 전체 기간 백테스트
2. 연도별 성과 분리
3. 상승장 / 하락장 / 횡보장 구분
4. Walk-forward test
5. Out-of-sample test
6. 수수료 2배, 슬리피지 2배 스트레스 테스트

9.4 주요 성과 지표

CAGR
MDD
Sharpe
Sortino
Profit Factor
Win Rate
Average R
Expectancy
Max Consecutive Loss
Daily VaR
월별 손익 분포
Regime별 손익

⸻

10. 시스템 아키텍처

/data
  market_data_loader.py
  futures_data_loader.py
  foreign_flow_loader.py
  macro_data_loader.py
/features
  technical_features.py
  regime_features.py
  flow_features.py
/strategy
  daily_regime.py
  intraday_entry.py
  exit_rules.py
  position_sizing.py
/backtest
  event_engine.py
  portfolio.py
  execution_simulator.py
  performance_report.py
/live
  broker_api.py
  order_manager.py
  risk_monitor.py
  live_runner.py
/config
  strategy.yaml
  risk.yaml
  broker.yaml
/tests
  test_regime.py
  test_entry.py
  test_risk.py
  test_backtest.py

⸻

11. 핵심 클래스 설계

11.1 DailyRegimeDetector

class DailyRegimeDetector:
    def calculate_features(self, daily_df, flow_df, macro_df):
        pass
    def detect(self, row):
        """
        return:
          LONG_BIAS
          SHORT_BIAS
          NO_TRADE
        """
        pass

11.2 IntradaySignalEngine

class IntradaySignalEngine:
    def generate_signal(self, intraday_df, regime):
        """
        return:
          ENTER_LONG
          ENTER_SHORT
          HOLD
          EXIT
        """
        pass

11.3 RiskManager

class RiskManager:
    def calculate_position_size(self, equity, entry, stop):
        pass
    def check_daily_loss_limit(self, pnl):
        pass
    def check_trade_allowed(self, state):
        pass

11.4 OrderManager

class OrderManager:
    def place_entry_order(self, side, quantity, price=None):
        pass
    def place_stop_order(self, side, quantity, stop_price):
        pass
    def close_position(self):
        pass

⸻

12. YAML 설정 예시

strategy:
  ema_fast: 20
  ema_slow: 60
  ema_long: 120
  rsi_period: 14
  atr_period: 14
  opening_range_start: "08:45"
  opening_range_end: "09:15"
  trading_start: "09:05"
  force_exit_time: "15:35"
risk:
  risk_per_trade_pct: 0.005
  daily_loss_limit_pct: 0.015
  monthly_loss_limit_pct: 0.06
  max_trades_per_day: 3
  max_consecutive_losses: 2
  default_slippage_ticks: 1
  volatile_slippage_ticks: 3
contract:
  multiplier: 250000
  tick_size: 0.05
  tick_value: 12500

⸻

13. MVP 구현 순서

Phase 1 — 백테스트 MVP

1. 일봉 데이터 로더
2. 분봉 데이터 로더
3. EMA/RSI/ATR 계산
4. Daily Regime 생성
5. VWAP Reclaim 진입
6. ATR 손절/익절
7. 성과 리포트 생성

Phase 2 — 필터 추가

1. 외국인 선물 수급 필터
2. USD/KRW 필터
3. Nasdaq 야간 필터
4. 옵션 만기일 필터
5. 변동성 regime 필터

Phase 3 — 실거래 준비

1. 증권사 API 연동
2. 실시간 데이터 수집
3. 주문/정정/취소 모듈
4. 실시간 리스크 모니터
5. 장애 발생 시 전체 청산

⸻

14. 개발자에게 중요한 구현 원칙

1. 전략 로직과 브로커 API를 분리한다.
2. 백테스트와 실거래가 같은 Signal Engine을 사용해야 한다.
3. 모든 주문/체결/상태 변경은 로그로 남긴다.
4. 슬리피지와 수수료는 반드시 보수적으로 적용한다.
5. 실거래 전 최소 1개월 paper trading을 거친다.
6. 첫 실거래는 1계약만 허용한다.

⸻

15. 최종 전략 요약

이 전략은 단순히 “이평선 골든크로스 매수”가 아니다.

핵심은 다음이다.

Daily에서 방향을 정하고,
Intraday에서 좋은 가격만 잡고,
수급/환율/미국장으로 가짜 신호를 줄이고,
손실은 ATR과 일일 손실 한도로 제한한다.

KOSPI200 선물의 현실적인 접근은 매일 거래하는 시스템이 아니라,
추세와 수급이 일치하는 날만 공격하는 시스템이어야 한다.
