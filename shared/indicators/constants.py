"""Shared indicator-pipeline constants (single source of truth).

Values here are referenced by both the live streaming runtime and the
declarative strategy-builder schema so their bounds cannot silently drift
apart (live/backtest parity).
"""

from __future__ import annotations

# Depth of the live per-symbol candle history, in completed 1-minute bars.
# Producers/consumers that cap candle history MUST reference this constant:
# - ``StreamingIndicatorEngine(candle_maxlen=...)`` default
#   (services/trading/indicator_engine.py) — CandleAccumulator deque maxlen.
# - ``StreamingIndicatorResolver`` ``get_recent_candles(limit=...)``
#   (shared/indicators/resolver.py) — the ``ohlcv`` window handed to
#   builder_v1 strategies.
# - ``BuilderCondition.window`` validation (shared/strategy_builder/schema.py)
#   — a percentile window larger than this could fire in backtest but NEVER
#   live (permanent missing-data), a silent parity trap.
LIVE_CANDLE_HISTORY_MAXLEN = 240
