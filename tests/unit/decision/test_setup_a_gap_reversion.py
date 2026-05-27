"""Tests for SetupAGapReversion — TDD step 1 (written before implementation).

Test cases
----------
a) Happy path gap-down → long reversion emits Signal
b) Outside valid_minutes → None
c) SP500 gap too small → None
d) KR gap too small → None
e) Direction mismatch (SP500 up, KR open down) → None
f) Retrace below retrace_min → None
g) Retrace above retrace_max → None
h) Confidence in [0.5, 1.0] and increases with bigger gap / more centered retrace
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from shared.decision.context import MarketContext
from shared.decision.setups.gap_reversion import SetupAConfig, SetupAGapReversion
from shared.macro.base import MacroSnapshot

KST = ZoneInfo("Asia/Seoul")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_TS_MS = 1_700_000_000_000


def _macro(sp500_pct: float) -> MacroSnapshot:
    """Return a minimal MacroSnapshot with the given SP500 % change."""
    return MacroSnapshot(
        ts_ms=_BASE_TS_MS,
        session="overnight_us_close",
        sp500_change_pct=sp500_pct,
    )


def _ctx(
    *,
    now_hhmm: tuple[int, int] = (9, 30),  # (hour, minute) KST
    current_price: float = 346.00,  # below open — partly retraced gap-down
    prev_close: float = 350.00,
    today_open: float = 348.00,  # gap-down: open < prev_close
    atr_14: float = 1.0,
    macro: MacroSnapshot | None = None,  # default None, overridden per test
) -> MarketContext:
    """Build a MarketContext with sane defaults for gap-reversion tests.

    Default scenario: gap-DOWN (open < prev_close), SP500 negative overnight.
    current_price partially retraces back up toward today_open.
    """
    h, m = now_hhmm
    return MarketContext(
        now=datetime(2026, 4, 23, h, m, tzinfo=KST),
        symbol="A05603",
        current_price=current_price,
        prev_close=prev_close,
        today_open=today_open,
        vwap=347.50,
        atr_14=atr_14,
        atr_90th_percentile=1.5,
        last_15min_high=347.00,
        last_15min_low=345.50,
        current_spread_ticks=1.0,
        macro_overnight=macro,
        scheduled_events=[],
    )


def _default_config() -> SetupAConfig:
    """Return the default SetupAConfig (no YAML load needed)."""
    return SetupAConfig()


def test_zero_prev_close_is_skipped_without_division_error():
    setup = SetupAGapReversion(config=_default_config())

    signal = setup.check(
        _ctx(
            prev_close=0.0,
            today_open=348.0,
            current_price=348.8,
            macro=_macro(-0.8),
        )
    )

    assert signal is None


# ---------------------------------------------------------------------------
# (a) Happy path — gap-down → long reversion
# ---------------------------------------------------------------------------


def test_happy_path_gap_down_short_reversion():
    """Gap-down with SP500 down; price has partially bounced up → short reversion signal.

    Per spec §4.1 step 5:
        gap_pct < 0 (gap-DOWN) →
            retrace = (current_price - today_open) / (prev_close - today_open)
            direction = "short"

    Scenario:
        prev_close=350, open=347 → gap_pct ≈ -0.857 % (gap-down)
        SP500 -1.2 % (same direction ✓)
        current_price=348.5 → price bounced from gap-low toward open
            retrace = (348.5 - 347) / (350 - 347) = 1.5/3 = 0.50 ∈ [0.30, 0.55] ✓
        Signal: short the bounce, target near prev_close × gap_fill_ratio
    """
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),  # 30 min since open → in [10, 90] ✓
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,  # gap-down
        atr_14=1.0,
        macro=_macro(-1.2),  # SP500 down, matches gap direction
    )
    signal = setup.check(ctx)

    assert signal is not None, "Expected a signal for valid gap-down scenario"
    assert signal.setup_type == "A_gap_reversion"
    # gap-down → direction is "short" (fade the bounce back toward the gap low)
    assert signal.direction == "short"
    assert signal.symbol == "A05603"

    # entry = current_price
    assert signal.entry_price == pytest.approx(348.5)

    # stop = entry + stop_atr_mult * atr  (short stop is above entry)
    # = 348.5 + 1.5 * 1.0 = 350.0
    assert signal.stop_loss == pytest.approx(350.0)

    # target = prev_close + (today_open - prev_close) * target_gap_fill_ratio
    # = 350 + (347 - 350) * 0.9 = 350 - 2.7 = 347.3
    assert signal.take_profit == pytest.approx(347.3)

    # confidence in [0.5, 1.0]
    assert 0.5 <= signal.confidence <= 1.0

    # valid_until and generated_at are set
    assert signal.valid_until is not None
    assert signal.generated_at is not None
    assert signal.valid_until > signal.generated_at


# ---------------------------------------------------------------------------
# (b) Outside valid_minutes → None
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "now_hhmm",
    [
        (9, 5),  # 5 min after open — below valid_minutes_min=10
        (11, 30),  # 150 min after open — above valid_minutes_max=90
    ],
)
def test_outside_valid_minutes_returns_none(now_hhmm):
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=now_hhmm,
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-1.2),
    )
    assert setup.check(ctx) is None


# ---------------------------------------------------------------------------
# (c) SP500 gap too small → None
# ---------------------------------------------------------------------------


def test_sp500_gap_too_small_returns_none():
    """SP500 change 0.2 % < min_sp500_gap_pct=0.3 → None."""
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-0.2),  # too small
    )
    assert setup.check(ctx) is None


# ---------------------------------------------------------------------------
# (d) KR gap too small → None
# ---------------------------------------------------------------------------


def test_kr_gap_too_small_returns_none():
    """KR gap 0.1 % < min_kr_gap_pct=0.3 → None."""
    setup = SetupAGapReversion(config=_default_config())
    # prev_close=350, open=349.65 → gap_pct ≈ -0.1 % (too small)
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=349.7,
        prev_close=350.0,
        today_open=349.65,
        macro=_macro(-1.2),
    )
    assert setup.check(ctx) is None


# ---------------------------------------------------------------------------
# (e) Direction mismatch → None
# ---------------------------------------------------------------------------


def test_direction_mismatch_returns_none():
    """SP500 positive (+1.2 %) but KR open gapped DOWN — mismatch → None."""
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,  # gap-down (negative gap)
        macro=_macro(+1.2),  # SP500 positive — direction mismatch
    )
    assert setup.check(ctx) is None


# ---------------------------------------------------------------------------
# (f) Retrace below retrace_min → None
# ---------------------------------------------------------------------------


def test_retrace_below_min_returns_none():
    """Retrace < retrace_min (0.30) → None.

    Gap-down: prev_close=350, open=347 (gap = -3 pts).
    For a SHORT setup we'd look at (current_price - today_open)/(prev_close - today_open),
    but since gap_pct < 0 → direction='short', retrace =
        (current_price - today_open) / (prev_close - today_open).
    Wait — re-read spec §4.1 step 5:
        if gap_pct > 0 (gap-up):
            retrace = (today_open - current_price) / (today_open - prev_close)
            direction = "long"
        else (gap-down):
            retrace = (current_price - today_open) / (prev_close - today_open)
            direction = "short"

    So for gap-down, direction is SHORT, not long.  The happy-path test above
    uses gap_pct < 0, so direction should actually be short... but the target
    formula and stop formula apply differently.

    Let me re-check the happy-path:
        gap_pct = (347 - 350)/350*100 = -0.857 % (< 0 → gap-down)
        retrace = (current_price - today_open)/(prev_close - today_open)
                = (348.5 - 347)/(350 - 347) = 0.50  ← valid
        direction = "short"  ← price moved up from open, so short reversion

    For gap-down retrace below min:
        retrace = (current_price - today_open)/(prev_close - today_open) < 0.30
        current_price < today_open + 0.30*(prev_close - today_open)
        current_price < 347 + 0.30*(350 - 347) = 347 + 0.9 = 347.9
    """
    setup = SetupAGapReversion(config=_default_config())
    # current_price=347.5 → retrace = (347.5 - 347)/3 = 0.167 < 0.30
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=347.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-1.2),
    )
    assert setup.check(ctx) is None


# ---------------------------------------------------------------------------
# (g) Retrace above retrace_max → None
# ---------------------------------------------------------------------------


def test_retrace_above_max_returns_none():
    """Retrace > retrace_max (0.70) → None.

    For gap-down: retrace = (current_price - today_open)/(prev_close - today_open)
    prev_close=350, today_open=347 → gap_mag=3
    Must be > 0.70 → current_price > 347 + 0.70*3 = 349.1
    Use current_price=349.5 → retrace = 2.5/3 ≈ 0.833 > 0.70
    """
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=349.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-1.2),
    )
    assert setup.check(ctx) is None


# ---------------------------------------------------------------------------
# (h) Confidence in [0.5, 1.0] and increases with bigger gap / more central retrace
# ---------------------------------------------------------------------------


def test_confidence_in_valid_range():
    """Confidence must be in [0.5, 1.0] for every valid signal."""
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-1.2),
    )
    signal = setup.check(ctx)
    assert signal is not None
    assert 0.5 <= signal.confidence <= 1.0


def test_confidence_increases_with_bigger_sp500_gap():
    """Larger SP500 gap → higher confidence (gap_strength component).

    gap_strength = min(abs(sp500_pct) / 1.5, 0.3).
    Values must be chosen so neither one hits the 0.3 cap:
        -0.6% → 0.6/1.5 = 0.40 → capped at 0.30  (hits cap!)
    Use values well below the 1.5% saturation point:
        -0.6% → 0.6/1.5 = 0.40 … still capped.
    The cap is at abs(sp500_pct) >= 1.5 * 0.3 = 0.45 % — oops, any gap ≥ 0.45 %
    saturates gap_strength at 0.3.  Since min_sp500_gap_pct=0.5 (all valid signals
    have |sp500|≥0.5%) the formula always saturates for the current defaults.

    Workaround: use a custom config with a lower min_sp500_gap_pct so we can test
    two non-saturating values (0.5% and 0.9% both < 1.5 * 0.3 = 0.45? No, 0.5>0.45).

    Actually with the default threshold (min_sp500_gap_pct=0.5), any valid signal
    has |sp500_pct| ≥ 0.5, but gap_strength saturates at |sp500_pct| ≥ 0.45.
    So for default config, gap_strength is always 0.3 and only retrace_centrality
    differentiates confidence.

    To test the gap_strength slope we must lower min_sp500_gap_pct to allow
    sub-0.45 values. Use a custom config.
    """
    low_threshold_cfg = SetupAConfig(min_sp500_gap_pct=0.2)  # allow weaker gaps
    setup = SetupAGapReversion(config=low_threshold_cfg)

    base_ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-0.3),  # smaller SP500 gap → gap_strength = 0.3/1.5 = 0.20
    )
    big_ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(
            -0.6
        ),  # bigger SP500 gap → gap_strength = min(0.6/1.5, 0.3) = 0.30
    )

    sig_base = setup.check(base_ctx)
    sig_big = setup.check(big_ctx)

    assert sig_base is not None and sig_big is not None
    assert sig_big.confidence > sig_base.confidence


def test_confidence_increases_when_retrace_near_center():
    """Retrace closer to 0.425 center → higher confidence (centrality component)."""
    setup = SetupAGapReversion(config=_default_config())

    # gap-down: prev=350, open=347, gap=3 pts
    # retrace = (price - 347)/3, center at 0.425 → price = 347 + 1.275 = 348.275
    # peripheral: 0.32 → price = 347 + 0.96 = 347.96
    # central:    0.425 → price = 348.275

    central_ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.275,  # retrace ≈ 0.425 (center)
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-1.2),
    )
    peripheral_ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=347.96,  # retrace ≈ 0.32 (near min edge)
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-1.2),
    )

    sig_center = setup.check(central_ctx)
    sig_edge = setup.check(peripheral_ctx)

    assert sig_center is not None and sig_edge is not None
    assert sig_center.confidence >= sig_edge.confidence


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------


def test_macro_overnight_none_returns_none():
    """No macro snapshot → None."""
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        macro=None,
    )
    assert setup.check(ctx) is None


def test_gap_up_direction_long_signal():
    """Gap-UP scenario: SP500 positive, KR opens above prev_close → SHORT reversion.

    Actually per spec §4.1 step 5:
        gap_pct > 0 → retrace = (today_open - current_price)/(today_open - prev_close)
                    → direction = "long"   ← price fell from open, buy the dip

    This is a gap-UP where:
      prev_close=350, today_open=353.5 → gap_pct ≈ +1.0%  (gap-up)
      SP500 +1.2% (same direction ✓)
      current_price=352.45 → retrace = (353.5 - 352.45)/(353.5 - 350) = 1.05/3.5 = 0.30
      retrace = 0.30 ≥ retrace_min=0.30 → just valid
    """
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=352.45,
        prev_close=350.0,
        today_open=353.5,  # gap-up: open > prev_close
        atr_14=1.0,
        macro=_macro(+1.2),  # SP500 positive, matches gap-up
    )
    signal = setup.check(ctx)

    assert signal is not None
    assert signal.direction == "long"  # per spec: gap_pct>0 → "long"
    assert signal.entry_price == pytest.approx(352.45)
    # stop = entry - stop_atr_mult * atr (long)
    assert signal.stop_loss == pytest.approx(352.45 - 1.5 * 1.0)
    # target = prev_close + (today_open - prev_close)*0.9 = 350 + 3.5*0.9 = 353.15
    assert signal.take_profit == pytest.approx(350 + 3.5 * 0.9)


def test_gap_down_direction_short_signal():
    """gap_pct < 0 → direction='short', stop above entry."""
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        atr_14=1.0,
        macro=_macro(-1.2),
    )
    signal = setup.check(ctx)

    assert signal is not None
    assert signal.direction == "short"
    # stop = entry + stop_atr_mult * atr (short)
    assert signal.stop_loss == pytest.approx(348.5 + 1.5 * 1.0)


def test_reason_tags_contain_expected_substrings():
    """Signal reason_tags should reference sp500 gap, kr gap, and retrace."""
    setup = SetupAGapReversion(config=_default_config())
    ctx = _ctx(
        now_hhmm=(9, 30),
        current_price=348.5,
        prev_close=350.0,
        today_open=347.0,
        macro=_macro(-1.2),
    )
    signal = setup.check(ctx)
    assert signal is not None
    tags = " ".join(signal.reason_tags)
    assert "sp500_gap" in tags
    assert "kr_gap" in tags
    assert "retrace" in tags


def test_config_defaults_match_spec():
    """SetupAConfig defaults match spec §4.2 exactly."""
    cfg = SetupAConfig()
    assert cfg.enabled is True
    assert cfg.valid_minutes_min == 10
    assert cfg.valid_minutes_max == 120
    assert cfg.min_sp500_gap_pct == pytest.approx(0.3)
    assert cfg.min_kr_gap_pct == pytest.approx(0.2)
    assert cfg.retrace_min == pytest.approx(0.20)
    assert cfg.retrace_max == pytest.approx(0.70)
    assert cfg.stop_atr_mult == pytest.approx(1.5)
    assert cfg.target_gap_fill_ratio == pytest.approx(0.9)
    assert cfg.signal_ttl_minutes == 10
