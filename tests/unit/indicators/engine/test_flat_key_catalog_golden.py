"""Zero-drift pins for the ``flat_key`` catalog (P2-b alignment tripwire).

The platform has exactly one place that maps a catalog ``(indicator_id,
output)`` onto a flat runtime key: ``shared.indicators.engine.spec.flat_key``.
Both indicator-context paths converge on it:

* legacy/live — ``IndicatorResult.flat_latest()`` derives its keys from
  ``flat_key`` and the streaming payload assembly
  (``services/trading/indicator_queries.py``) publishes the same names;
* builder — the evaluator columns are user-scoped ``alias.output``, but every
  canonical/scalar consumer (cache panel, ``flat_latest``) uses ``flat_key``.

This module pins the shared vocabulary to exact literal strings so any edit to
the override table (or a new hand-maintained mapping) trips loudly instead of
silently forking the two paths. The 2026-07-09 audit found ZERO drift; keep it
that way.
"""

from __future__ import annotations

import pytest

from shared.indicators.engine.spec import flat_key

# The shared vocabulary: every (indicator_id, output) whose flat key is
# consumed by BOTH paths (live streaming payload literals in
# services/trading/indicator_queries.py AND the builder catalog /
# flat_latest()). Values are the exact live payload key strings.
_SHARED_VOCABULARY_PINS: dict[tuple[str, str], str] = {
    ("bollinger", "upper"): "bb_upper",
    ("bollinger", "middle"): "bb_middle",
    ("bollinger", "lower"): "bb_lower",
    ("stochastic", "k"): "stoch_k",
    ("stochastic", "d"): "stoch_d",
    ("stochrsi", "k"): "stochrsi_k",
    ("stochrsi", "d"): "stochrsi_d",
    ("macd", "value"): "macd",
    ("macd", "signal"): "macd_signal",
    ("macd", "histogram"): "macd_hist",
    ("trix", "value"): "trix",
    ("trix", "signal"): "trix_signal",
    ("rsi", "value"): "rsi",
    ("mfi", "value"): "mfi",
    ("adx", "value"): "adx",
    ("atr", "value"): "atr",
    ("vwap", "value"): "vwap",
    ("rvol", "value"): "rvol",
    ("volume_ma", "value"): "volume_ma",
    ("williams_r", "value"): "williams_r",
}


@pytest.mark.parametrize(
    ("indicator_id", "output", "expected"),
    [(iid, out, key) for (iid, out), key in _SHARED_VOCABULARY_PINS.items()],
)
def test_shared_vocabulary_flat_keys_are_pinned(
    indicator_id: str, output: str, expected: str
) -> None:
    assert flat_key(indicator_id, output) == expected


@pytest.mark.parametrize("period", [5, 20, 60])
def test_period_keyed_ema_sma_flat_keys_are_pinned(period: int) -> None:
    # Live payload publishes ema_{period} (indicator_queries.py); the catalog
    # derives the same key through flat_key's period-keyed rule.
    assert flat_key("ema", "value", {"period": period}) == f"ema_{period}"
    assert flat_key("sma", "value", {"period": period}) == f"sma_{period}"


def test_full_builder_catalog_derives_through_flat_key() -> None:
    """Every builder-catalog output must resolve to a non-empty flat key and
    multi-output indicators must not collapse onto one key."""
    from shared.strategy_builder.catalog import load_capabilities

    for indicator in load_capabilities().indicators:
        keys = {flat_key(indicator.id, output.id) for output in indicator.outputs}
        assert all(keys), f"{indicator.id}: empty flat key"
        assert len(keys) == len(
            indicator.outputs
        ), f"{indicator.id}: outputs collapse onto one flat key"
