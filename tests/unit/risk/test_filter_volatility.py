# tests/unit/risk/test_filter_volatility.py
"""VolatilityFilter — rejection, permissiveness, and the anti-halt seal.

The filter takes ONE provider returning a
:class:`~shared.risk.volatility_reference.VolatilityReference` that carries the
current ATR *and* its threshold together.  The tests below split into two
groups, and the second is the reason this file was rewritten:

* **Gating** — a symbol whose current ATR exceeds its own recent upper-tail
  percentile is rejected; equality passes (strict ``>``).
* **Never a silent halt** — every way the threshold can be unavailable
  (no provider, no published reference, stale/corrupt reference, warmup)
  resolves to *pass with a warning*, and the old split-provider shape that
  made "reject everything" a one-line change no longer exists.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytest

from shared.decision.signal import Signal
from shared.risk.filters.volatility import VolatilityFilter
from shared.risk.state import RiskStateSnapshot
from shared.risk.volatility_reference import VolatilityReference

_SYMBOL = "A05603"
_OTHER_SYMBOL = "005930"
_THRESHOLD = 5.0
_NOW = datetime(2026, 8, 5, 10, 30, 0)

_FILTER_LOGGER = "shared.risk.filters.volatility"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_signal(symbol: str = _SYMBOL) -> Signal:
    return Signal(
        setup_type="test_setup",
        direction="long",
        symbol=symbol,
        entry_price=360.0,
        stop_loss=355.0,
        take_profit=370.0,
        confidence=0.8,
    )


def _reference(
    *,
    current_atr: float,
    threshold: float | None = _THRESHOLD,
    symbol: str = _SYMBOL,
    sample_size: int = 240,
) -> VolatilityReference:
    return VolatilityReference(
        symbol=symbol,
        current_atr=current_atr,
        atr_percentile=threshold,
        percentile=90.0,
        sample_size=sample_size,
        asof_ts=_NOW.isoformat(),
    )


def _make_filter(
    current_atr: float, threshold: float | None = _THRESHOLD
) -> VolatilityFilter:
    """Filter whose provider always returns one fixed reference."""
    return VolatilityFilter(
        reference_provider=lambda _symbol: _reference(
            current_atr=current_atr, threshold=threshold
        ),
        clock=lambda: _NOW,
    )


def _snapshot() -> RiskStateSnapshot:
    """The filter ignores the risk-state snapshot; a default one suffices."""
    return RiskStateSnapshot()


# ---------------------------------------------------------------------------
# Filter metadata
# ---------------------------------------------------------------------------


def test_filter_name() -> None:
    assert _make_filter(current_atr=1.0).name == "volatility"


def test_filter_stores_provider() -> None:
    def provider(_symbol: str) -> None:
        return None

    assert VolatilityFilter(reference_provider=provider)._reference_provider is provider


# ---------------------------------------------------------------------------
# The seal: a bare ATR cannot be supplied
# ---------------------------------------------------------------------------


def test_there_is_no_way_to_wire_only_a_current_atr() -> None:
    """The old split-provider shape is gone, not merely discouraged.

    ``VolatilityFilter(current_atr_provider=...)`` used to be constructible and
    compared the live ATR against a ``0.0`` default threshold — true for every
    reading, so every entry was rejected and all trading stopped silently.  The
    parameter no longer exists, so that call is a construction-time error.
    """
    with pytest.raises(TypeError):
        VolatilityFilter(current_atr_provider=lambda: 6.0)  # type: ignore[call-arg]


def test_a_zero_threshold_cannot_reach_the_filter() -> None:
    """The value object refuses the landmine before the filter ever sees it."""
    with pytest.raises(ValueError, match="atr_percentile must be > 0"):
        _reference(current_atr=6.0, threshold=0.0)


# ---------------------------------------------------------------------------
# Pass — current ATR at or below the symbol's percentile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("current_atr", [0.0, 1.0, 3.0, 4.999])
def test_pass_when_atr_below_percentile(current_atr) -> None:
    result = _make_filter(current_atr=current_atr).check(_make_signal(), _snapshot())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.filter_name == "volatility"


def test_pass_when_atr_exactly_equals_percentile() -> None:
    """Strict ``>``: equality is not "too volatile"."""
    result = _make_filter(current_atr=_THRESHOLD).check(_make_signal(), _snapshot())
    assert result.passed is True
    assert result.skip_reason is None


# ---------------------------------------------------------------------------
# Reject — current ATR above the symbol's percentile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("current_atr", [5.001, 6.0, 50.0])
def test_reject_when_atr_above_percentile(current_atr) -> None:
    result = _make_filter(current_atr=current_atr).check(_make_signal(), _snapshot())
    assert result.passed is False
    assert result.skip_reason == "volatility_too_high"
    assert result.filter_name == "volatility"


# ---------------------------------------------------------------------------
# Per-symbol: the threshold is looked up for the signal's own instrument
# ---------------------------------------------------------------------------


def test_provider_is_keyed_by_the_signal_symbol() -> None:
    """ATR is in absolute price units, so the lookup must be per-symbol.

    A single per-asset-class threshold could not have been correct for a
    multi-symbol stock universe — a KRW 500,000 name and a KRW 5,000 name have
    nothing comparable about their ATRs.
    """
    seen: list[str] = []

    def provider(symbol: str) -> VolatilityReference:
        seen.append(symbol)
        return _reference(current_atr=1.0, symbol=symbol)

    f = VolatilityFilter(reference_provider=provider, clock=lambda: _NOW)
    f.check(_make_signal(_SYMBOL), _snapshot())
    f.check(_make_signal(_OTHER_SYMBOL), _snapshot())

    assert seen == [_SYMBOL, _OTHER_SYMBOL]


def test_one_hot_symbol_does_not_block_another() -> None:
    """Per-symbol thresholds mean a volatile name never gates a calm one."""
    references = {
        _SYMBOL: _reference(current_atr=99.0, symbol=_SYMBOL),
        _OTHER_SYMBOL: _reference(current_atr=1.0, symbol=_OTHER_SYMBOL),
    }
    f = VolatilityFilter(
        reference_provider=references.get,  # type: ignore[arg-type]
        clock=lambda: _NOW,
    )

    assert f.check(_make_signal(_SYMBOL), _snapshot()).passed is False
    assert f.check(_make_signal(_OTHER_SYMBOL), _snapshot()).passed is True


def test_provider_called_on_each_check() -> None:
    """The reference is re-read per candidate, never cached at construction."""
    calls = []

    def provider(symbol: str) -> VolatilityReference:
        calls.append(symbol)
        return _reference(current_atr=3.0)

    f = VolatilityFilter(reference_provider=provider, clock=lambda: _NOW)
    for _ in range(3):
        f.check(_make_signal(), _snapshot())

    assert len(calls) == 3


def test_result_tracks_a_changing_reference() -> None:
    atrs = iter([3.0, 3.0, 7.0])
    f = VolatilityFilter(
        reference_provider=lambda _s: _reference(current_atr=next(atrs)),
        clock=lambda: _NOW,
    )
    assert f.check(_make_signal(), _snapshot()).passed is True
    assert f.check(_make_signal(), _snapshot()).passed is True
    assert f.check(_make_signal(), _snapshot()).passed is False


# ---------------------------------------------------------------------------
# Unavailable threshold → pass, loudly (never a silent halt)
# ---------------------------------------------------------------------------


def test_unwired_filter_is_inert_and_silent_per_candidate() -> None:
    """No provider at all: reads nothing, rejects nothing.

    The build-time announcement is RiskFilterLayer.from_config's job (pinned in
    test_provider_wiring.py); per-candidate the unwired filter stays quiet so
    the default configuration does not flood the log.
    """
    f = VolatilityFilter()
    result = f.check(_make_signal(), _snapshot())
    assert result.passed is True
    assert result.skip_reason is None


def test_absent_reference_passes_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A dead publisher / stale snapshot must not stop trading.

    Fail-open matches every sibling snapshot-reading filter in this layer
    (portfolio_mdd, margin_gate, leverage). Fail-closed here would recreate the
    exact silent trading halt this design exists to prevent — but silence would
    be almost as bad, so the pass is announced.
    """
    f = VolatilityFilter(reference_provider=lambda _s: None, clock=lambda: _NOW)
    with caplog.at_level(logging.WARNING, logger=_FILTER_LOGGER):
        result = f.check(_make_signal(), _snapshot())

    assert result.passed is True
    assert result.skip_reason is None
    messages = [r.getMessage() for r in caplog.records if r.name == _FILTER_LOGGER]
    assert len(messages) == 1
    assert _SYMBOL in messages[0]
    assert "inert" in messages[0]


def test_warmup_reference_passes_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A published reference with no threshold yet is permissive, not blocking.

    This is the state right after an operator flips the feature on: samples are
    still accumulating.  Blocking during warmup would make enabling the filter
    indistinguishable from breaking the pipeline.
    """
    f = VolatilityFilter(
        reference_provider=lambda _s: _reference(
            current_atr=99.0, threshold=None, sample_size=7
        ),
        clock=lambda: _NOW,
    )
    with caplog.at_level(logging.WARNING, logger=_FILTER_LOGGER):
        result = f.check(_make_signal(), _snapshot())

    assert result.passed is True
    messages = [r.getMessage() for r in caplog.records if r.name == _FILTER_LOGGER]
    assert len(messages) == 1
    assert "warmup" in messages[0]
    assert "7 samples" in messages[0]


def test_raising_provider_passes_with_a_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A provider exception must not escape into the guardless layer.

    ``RiskFilterLayer.evaluate`` has no per-filter guard, so a raise here would
    propagate to the daemon, leave the message un-ACKed and stall the pipeline
    — a fail-CLOSED outcome from a fail-open filter.
    """

    def _boom(_symbol: str) -> VolatilityReference:
        raise RuntimeError("redis exploded")

    f = VolatilityFilter(reference_provider=_boom, clock=lambda: _NOW)
    with caplog.at_level(logging.WARNING, logger=_FILTER_LOGGER):
        result = f.check(_make_signal(), _snapshot())

    assert result.passed is True
    messages = [r.getMessage() for r in caplog.records if r.name == _FILTER_LOGGER]
    assert len(messages) == 1
    assert "redis exploded" in messages[0]


def test_warning_is_throttled_per_symbol(caplog: pytest.LogCaptureFixture) -> None:
    """Noisy enough to notice, quiet enough not to drown the log.

    Every candidate hits this path while the reference is missing, so an
    unthrottled warning would be unreadable — but the interval must actually
    expire, or an operator watching a long warmup would see one line and assume
    the problem resolved itself.
    """
    times = iter(
        [
            _NOW,
            _NOW + timedelta(seconds=10),
            _NOW + timedelta(seconds=299),
            _NOW + timedelta(seconds=301),
        ]
    )
    f = VolatilityFilter(
        reference_provider=lambda _s: None,
        warn_interval_seconds=300.0,
        clock=lambda: next(times),
    )
    with caplog.at_level(logging.WARNING, logger=_FILTER_LOGGER):
        for _ in range(4):
            f.check(_make_signal(), _snapshot())

    messages = [r.getMessage() for r in caplog.records if r.name == _FILTER_LOGGER]
    assert len(messages) == 2  # first call + the one past the interval


def test_throttle_is_per_symbol_not_global(caplog: pytest.LogCaptureFixture) -> None:
    """A blind symbol must not be masked by another symbol's recent warning."""
    f = VolatilityFilter(
        reference_provider=lambda _s: None,
        warn_interval_seconds=300.0,
        clock=lambda: _NOW,
    )
    with caplog.at_level(logging.WARNING, logger=_FILTER_LOGGER):
        f.check(_make_signal(_SYMBOL), _snapshot())
        f.check(_make_signal(_OTHER_SYMBOL), _snapshot())

    messages = [r.getMessage() for r in caplog.records if r.name == _FILTER_LOGGER]
    assert len(messages) == 2
    assert any(_SYMBOL in m for m in messages)
    assert any(_OTHER_SYMBOL in m for m in messages)


# ---------------------------------------------------------------------------
# size_multiplier is always 1.0 (this filter rejects, it never resizes)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("current_atr", [2.0, 99.0])
def test_size_multiplier_is_always_full(current_atr) -> None:
    result = _make_filter(current_atr=current_atr).check(_make_signal(), _snapshot())
    assert result.size_multiplier == 1.0
