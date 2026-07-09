"""P2-c pilot: williams_r legacy vs closest declarative candidate — GATE EVIDENCE.

Outcome: **DEFERRED**. The active ``config/strategies/stock/williams_r.yaml``
behavior is NOT expressible in the builder_v1 schema-v2 vocabulary, and this
test pins the concrete signal-sequence divergence that the equivalence gate
must reject. The legacy YAML stays the active definition.

Missing vocabulary (documented in the plan, §4 P2-c):

1. **Entry-session window** — ``skip_market_open_minutes=15`` /
   ``skip_market_close_minutes=15`` (KST). The schema has no time filter
   (known P2-a residual), so the declarative candidate fires inside the
   09:00-09:15 skip window where the legacy entry is structurally silent.
2. **Indicator timeframe** — the legacy entry reads Williams %R from the
   5-minute momentum bundle (``momentum_5m``, closed 5m candles), while
   ``BuilderIndicator`` has no timeframe field: the builder computes over the
   1-minute OHLCV window. Same market event → different W%R series → different
   signal bars.
3. **Market-state allow/block gate** — ``market_state_filter`` matches the
   context regime (MFI-classified live/backtest) against allow/block lists.
   ``gates.regime_gate`` (percentile/impact) is a different mechanism and
   cannot express it.
4. **Dynamic sizing metadata** — ``position_size_multiplier`` (overextension
   scaling via ``max_full_size_bb_distance_pct``) has no declarative
   counterpart.

The synthetic scenario stages the same two market events for both sides:

* Day 2, 09:04-09:09 — oversold dip + high-volume reversal inside the skip
  window. The 1m-W%R candidate fires at 09:09; the legacy entry would meet
  its own W%R conditions at 09:10 but is session-blocked (gap #1).
* Day 2, 13:30-13:45 — a 5-minute-scale dip + reversal in-session. The legacy
  entry fires at 13:45 off closed 5m candles; the 1m candidate sees the
  crossing earlier, on a bar that fails its BB trend condition, and stays
  silent (gap #2).

If this test ever starts reporting equivalence, the vocabulary gaps have
materially changed — re-run the migration decision, do not silence the test.
"""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

import yaml

from tests.unit.strategy_builder.migration.harness import (
    KST,
    collect_entry_signal_events,
    compare_signal_sequences,
    kst_session_bars,
)

_CODE = "005930"
_REPO_ROOT = Path(__file__).resolve().parents[4]
_LEGACY_YAML = _REPO_ROOT / "config" / "strategies" / "stock" / "williams_r.yaml"

# Mirrors the legacy YAML entry params this candidate CAN express.
_OVERSOLD = -85.0
_REVERSAL = -80.0
_VOLUME_THRESHOLD = 2.0
_COOLDOWN_SECONDS = 7200


def _legacy_config() -> dict:
    return yaml.safe_load(_LEGACY_YAML.read_text("utf-8"))


def _candidate_builder_state() -> dict:
    """Closest-expressible BuilderState for the williams_r entry.

    Encodes the condition core — oversold reversal (prev W%R below the
    oversold line, current at/above the reversal line, via
    ``cross_above(oversold) AND greater_equal(reversal)``), BB-middle trend
    filter, RVOL volume confirm — plus the signal cooldown as a schema gate.
    The four gaps listed in the module docstring are NOT expressible.
    """
    return {
        "metadata": {
            "id": "williams_r_declarative_candidate",
            "name": "Williams %R oversold reversal (declarative candidate)",
            "description": (
                "P2-c pilot candidate for config/strategies/stock/"
                "williams_r.yaml — deferred, see migration gate test."
            ),
        },
        "asset_class": "stock",
        "indicators": [
            {
                "id": "ind_wr",
                "indicator_id": "williams_r",
                "alias": "wr",
                "params": {"period": 14},
                "output": "value",
            },
            {
                "id": "ind_bb",
                "indicator_id": "bollinger",
                "alias": "bb",
                "params": {"period": 20, "std": 2},
                "output": "middle",
            },
            {
                "id": "ind_rvol",
                "indicator_id": "rvol",
                "alias": "rvol",
                "params": {"short_window": 5, "long_window": 20},
                "output": "value",
            },
        ],
        "entry": {
            "logic": "AND",
            "conditions": [
                {
                    # prev W%R <= oversold AND current W%R > oversold ...
                    "id": "cond_reversal_cross",
                    "left": {"type": "indicator", "indicator_alias": "wr"},
                    "operator": "cross_above",
                    "right": {"type": "value", "value": _OVERSOLD},
                },
                {
                    # ... AND current W%R >= reversal threshold
                    "id": "cond_reversal_level",
                    "left": {"type": "indicator", "indicator_alias": "wr"},
                    "operator": "greater_equal",
                    "right": {"type": "value", "value": _REVERSAL},
                },
                {
                    "id": "cond_trend",
                    "left": {"type": "price", "price_field": "close"},
                    "operator": "greater_than",
                    "right": {
                        "type": "indicator",
                        "indicator_alias": "bb",
                        "indicator_output": "middle",
                    },
                },
                {
                    "id": "cond_volume",
                    "left": {"type": "indicator", "indicator_alias": "rvol"},
                    "operator": "greater_equal",
                    "right": {"type": "value", "value": _VOLUME_THRESHOLD},
                },
            ],
        },
        "exit": {"logic": "AND", "conditions": []},
        "risk": {
            "order_amount": 1_000_000,
            "stop_loss": {"enabled": True, "percent": 3.0},
            "take_profit": {"enabled": False, "percent": 10.0},
            "trailing_stop": {"enabled": False, "percent": 3.0},
        },
        "gates": {"cooldown_seconds": _COOLDOWN_SECONDS},
    }


def _declarative_candidate_config() -> dict:
    state = _candidate_builder_state()
    return {
        "strategy": {
            "name": "williams_r_declarative_candidate",
            "asset_class": "stock",
            "enabled": False,
            "entry": {
                "type": "builder_v1",
                "params": {"builder_state": state, "cooldown_seconds": 0},
            },
            "exit": {
                "type": "builder_v1_exit",
                "params": {"builder_state": state},
            },
            "position": {"type": "fixed", "params": {}},
        }
    }


def _warmup_day_bars() -> list:
    """Day 1: monotone gentle uptrend — warms 1m/5m/MFI paths, no signals."""
    closes = [1000.0 + 0.25 * i for i in range(380)]
    return kst_session_bars(date(2026, 7, 6), closes, code=_CODE)


def _event_day_bars() -> list:
    """Day 2: the two staged events described in the module docstring."""
    closes: list[float] = []
    vols: list[float] = []

    # 09:00-09:03 plateau at 1095.
    closes += [1095.0] * 4
    vols += [1000.0] * 4
    # 09:04-09:08 oversold dip (inside the legacy 15-min open-skip window).
    closes += [1088.0, 1078.0, 1068.0, 1060.0, 1058.0]
    vols += [1000.0, 1000.0, 1000.0, 8000.0, 8000.0]
    # 09:09 high-volume reversal bar → declarative candidate signal.
    closes += [1090.0]
    vols += [8000.0]
    # 09:10-13:19 recovery then drift up to 1120 (no W%R oversold crossings).
    closes += [1100.0]
    vols += [1000.0]
    drift_bars = 249
    for i in range(drift_bars):
        closes.append(1100.0 + (20.0 * (i + 1)) / drift_bars)
        vols.append(1000.0)
    assert len(closes) == 260  # next bar is 13:20 KST
    # 13:20-13:29 plateau at 1120.
    closes += [1120.0] * 10
    vols += [1000.0] * 10
    # 13:30-13:39 five-minute-scale dive to 1080.
    for i in range(10):
        closes.append(1116.0 - 4.0 * i)
    vols += [1000.0] * 10
    # 13:40-13:45 high-volume recovery → legacy (5m W%R) signal at 13:45.
    closes += [1084.0, 1092.0, 1100.0, 1108.0, 1112.0, 1113.0]
    vols += [6000.0] * 6
    # Rest of the session: flat.
    remaining = 380 - len(closes)
    closes += [1113.0] * remaining
    vols += [1000.0] * remaining
    return kst_session_bars(date(2026, 7, 7), closes, volumes=vols, code=_CODE)


def test_williams_r_declarative_candidate_is_not_signal_equivalent() -> None:
    bars = _warmup_day_bars() + _event_day_bars()

    legacy_events = collect_entry_signal_events(bars, strategy_config=_legacy_config())
    declarative_events = collect_entry_signal_events(
        bars, strategy_config=_declarative_candidate_config()
    )

    report = compare_signal_sequences(legacy_events, declarative_events)

    # Both sides must actually fire — a 0-vs-0 run would prove nothing.
    assert legacy_events, "scenario failed to trigger the legacy entry"
    assert declarative_events, "scenario failed to trigger the candidate"

    # Gap #1 (entry-session window): the candidate fires inside the legacy
    # 09:00-09:15 open-skip window; the legacy entry never can.
    skip_open_end = time(9, 15)
    assert any(
        event.timestamp.astimezone(KST).time() < skip_open_end
        for event in declarative_events
    ), report.summary()
    assert all(
        event.timestamp.astimezone(KST).time() >= skip_open_end
        for event in legacy_events
    ), report.summary()

    # Gap #2 (indicator timeframe): the in-session 5m-scale reversal fires the
    # legacy entry, but no declarative signal lands on that bar.
    legacy_times = {event.timestamp for event in legacy_events}
    declarative_times = {event.timestamp for event in declarative_events}
    assert legacy_times - declarative_times, report.summary()

    # The equivalence gate must reject this migration.
    assert not report.equivalent, report.summary()
