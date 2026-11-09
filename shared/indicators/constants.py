"""Shared indicator-pipeline constants (single source of truth).

Values here are referenced by both the live streaming runtime and the
declarative strategy-builder schema so their bounds cannot silently drift
apart (live/backtest parity).
"""

from __future__ import annotations

# Depth of the live per-symbol candle history, in completed 1-minute bars.
# Producers/consumers that cap candle history MUST reference this constant:
# - ``StreamingIndicatorEngine(candle_maxlen=...)`` default
#   (shared/indicators/streaming/engine.py) — CandleAccumulator deque maxlen.
# - ``StreamingIndicatorResolver`` ``get_recent_candles(limit=...)``
#   (shared/indicators/resolver.py) — the ``ohlcv`` window handed to
#   builder_v1 strategies.
# (``BuilderCondition.window`` validation in shared/strategy_builder/schema.py
#  was a third consumer — a percentile window larger than this could fire in
#  backtest but NEVER live, a silent parity trap. That package fell outside the
#  import closure and went in the legacy removal L7,
#  docs/plans/2026-11-07-legacy-removal-plan.md §3.)
LIVE_CANDLE_HISTORY_MAXLEN = 240
