"""VectorbtRunner 실데이터 parity (P3-b) — williams_r × 실 분봉 parquet.

배포 호스트의 `data/market/stock/minute` parquet 가 있을 때만 실행된다
(CI 러너에는 데이터가 없어 자동 skip). 활성 주식 전략 williams_r 을
레지스트리 경로(StrategyFactory + BacktestStrategyAdapter)로 구동해
legacy BacktestEngine 과 트레이드/지표 완전 일치를 고정한다.

엔트리 게이트(market_state_filter / trend_filter / volume_confirm)는 이
검증에서 완화한다: 해당 필터는 검증 윈도우에서 신호를 전부 차단하는데
(backtest 경로는 일봉 시딩이 없어 trend_filter 가 상시 False — memory:
indicator-audit-2026-07-05), parity 게이트의 목적은 *동일 신호에 대한
체결/포트폴리오 계층 동등성* 검증이므로 신호 경로가 양 엔진에 동일하게
적용되는 한 유효하다. 완화 내역은 parity 리포트에 문서화되어 있다.
"""

from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

import pytest

pytestmark = [pytest.mark.backtest, pytest.mark.slow]

_SYMBOL = "005930"
_START = date(2026, 6, 1)
_END = date(2026, 6, 12)
_DATA_DIR = (
    Path(__file__).resolve().parents[3]
    / "data"
    / "market"
    / "stock"
    / "minute"
    / f"code={_SYMBOL}"
)


def _load_config() -> dict:
    from shared.config.loader import ConfigLoader

    config = copy.deepcopy(ConfigLoader.load_strategy("stock", "williams_r"))
    entry_params = config["strategy"]["entry"]["params"]
    entry_params["market_state_filter"]["enabled"] = False
    entry_params["trend_filter"] = False
    entry_params["volume_confirm"] = False
    entry_params["signal_cooldown_seconds"] = 1800
    return config


@pytest.mark.skipif(
    not _DATA_DIR.exists(), reason="historical stock minute parquet not on this host"
)
def test_williams_r_real_minute_parity():
    pytest.importorskip("vectorbt")

    from shared.backtest import BacktestConfig, BacktestEngine
    from shared.backtest.adapter import BacktestStrategyAdapter
    from shared.backtest.config import RiskConfig
    from shared.backtest.vbt_runner import VectorbtRunner
    from shared.storage.market_data_store import load_market_bars_for_backtest
    from shared.strategy.registry import (
        StrategyFactory,
        register_builtin_components,
    )

    register_builtin_components()

    df = load_market_bars_for_backtest(
        symbol=_SYMBOL,
        asset_class="stock",
        timeframe="minute",
        start=_START,
        end=_END,
    )
    if df.empty:
        pytest.skip("no minute bars in validation window on this host")

    strategy_config = _load_config()
    bt = strategy_config["strategy"]["backtest"]
    pos_params = strategy_config["strategy"]["position"]["params"]
    config = BacktestConfig.stock(
        initial_capital=float(bt["initial_capital"]),
        order_amount_per_stock=(
            float(pos_params.get("order_amount_per_stock", 0)) or None
        ),
        max_positions=int(pos_params.get("max_positions", 5)),
    )
    config.risk = RiskConfig.from_dict(bt["risk"])

    def build_adapter():
        return BacktestStrategyAdapter(
            StrategyFactory.create(strategy_config), strategy_config
        )

    res_legacy = BacktestEngine(build_adapter(), config).run(df.copy())
    res_vbt = VectorbtRunner(build_adapter(), config).run(df.copy())

    # 검증 윈도우는 실거래가 발생하도록 선정됨 — 공허 parity 방지.
    assert res_legacy.total_trades > 0

    # 합성 매트릭스와 동일한 parity 계약 (단일 헬퍼 공유). equity_atol 만
    # 1e-4 KRW 로 완화: 초기자본 1e8 스케일에서의 부동소수 ulp 잔차
    # (상대 ~1e-12) — 여전히 원 단위 이하로 무의미한 크기다.
    from tests.unit.backtest.test_vbt_runner import _assert_parity

    _assert_parity(res_legacy, res_vbt, equity_atol=1e-4)
