"""BacktestStrategyAdapter must keep fulfilling builder_v1's "ohlcv" contract.

Regression for the P2-c pilot precondition: ``StreamingIndicatorResolver``
used to attach the OHLCV candle window only while the engine's feature bundle
was cold (< 26 candles). From bar 26 onward the builder entry received the
feature bundle instead of ``indicators["ohlcv"]`` and went permanently dark —
in the live paper pipeline AND in the backtest adapter path, which makes any
legacy→declarative signal-equivalence comparison impossible.

Reproduction (pre-fix): feeding 60 bars through the adapter, the builder entry
saw ``ohlcv`` only on bars 20-25 (post-warmup, pre-feature-bundle) and ``None``
afterwards.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from shared.backtest.adapter import BacktestStrategyAdapter
from shared.strategy import register_builtin_components
from shared.strategy.factory import StrategyFactory

KST = ZoneInfo("Asia/Seoul")
_FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "builder"
    / "golden_cross_built.yaml"
)


def test_builder_entry_receives_ohlcv_after_feature_bundle_warms() -> None:
    register_builtin_components()
    doc = yaml.safe_load(_FIXTURE.read_text("utf-8"))
    strategy = StrategyFactory.create(doc)
    adapter = BacktestStrategyAdapter(strategy, doc)

    entry = strategy.entry
    original_generate = entry.generate
    ohlcv_sizes: list[int | None] = []

    async def spy(context):
        rows = (context.indicators or {}).get("ohlcv")
        ohlcv_sizes.append(len(rows) if isinstance(rows, list) else None)
        return await original_generate(context)

    entry.generate = spy  # type: ignore[method-assign]

    start = datetime(2026, 7, 6, 9, 0, tzinfo=KST)
    closes = [200.0 - 2.0 * i for i in range(40)] + [400.0] * 20
    for i, close in enumerate(closes):
        adapter.on_bar(
            {
                "datetime": start + timedelta(minutes=i),
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1000,
                "code": "005930",
            }
        )

    # The entry runs once per warm bar (warmup = 20 bars for BB period 20).
    assert len(ohlcv_sizes) == len(closes) - 20 + 1
    # EVERY evaluated bar must carry the OHLCV window — including bars >= 26
    # where the engine's 25-feature bundle is warm (the old dropout window).
    assert all(size is not None and size >= 20 for size in ohlcv_sizes), (
        "builder_v1 lost its ohlcv window on some bars: " f"{ohlcv_sizes}"
    )
