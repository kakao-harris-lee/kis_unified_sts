# tests/unit/risk/test_filter_open_position.py
"""TDD tests for OpenPositionFilter.

Written BEFORE / alongside implementation (TDD red-green cycle).

The filter accepts a ``has_open_position_provider`` callable that maps a
symbol string to bool.  Tests supply simple lambdas to control the outcome
without touching live position-tracking infrastructure.
"""

from __future__ import annotations

from shared.decision.signal import Signal
from shared.risk.filters.open_position import OpenPositionFilter
from shared.risk.state import RiskStateSnapshot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SYMBOL = "A05603"
_OTHER_SYMBOL = "A05604"


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


def _make_snapshot() -> RiskStateSnapshot:
    return RiskStateSnapshot()


def _make_filter_no_position() -> OpenPositionFilter:
    """Filter whose provider always reports no open position."""
    return OpenPositionFilter(has_open_position_provider=lambda symbol: False)  # noqa: ARG005


def _make_filter_has_position() -> OpenPositionFilter:
    """Filter whose provider always reports an open position."""
    return OpenPositionFilter(has_open_position_provider=lambda symbol: True)  # noqa: ARG005


# ---------------------------------------------------------------------------
# Filter metadata
# ---------------------------------------------------------------------------


def test_filter_name():
    f = _make_filter_no_position()
    assert f.name == "open_position"


def test_filter_stores_provider():
    provider = lambda symbol: False  # noqa: E731,ARG005
    f = OpenPositionFilter(has_open_position_provider=provider)
    assert f._has_open_position_provider is provider


# ---------------------------------------------------------------------------
# Pass — provider returns False (no open position)
# ---------------------------------------------------------------------------


def test_pass_when_no_open_position():
    """Provider returns False → no open position → signal passes."""
    f = _make_filter_no_position()
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is True
    assert result.skip_reason is None
    assert result.filter_name == "open_position"


def test_pass_when_no_open_position_different_symbol():
    """Provider returns False for any symbol → pass."""
    f = _make_filter_no_position()
    result = f.check(_make_signal(symbol=_OTHER_SYMBOL), _make_snapshot())
    assert result.passed is True


# ---------------------------------------------------------------------------
# Reject — provider returns True (open position exists)
# ---------------------------------------------------------------------------


def test_reject_when_open_position_exists():
    """Provider returns True → open position detected → signal rejected."""
    f = _make_filter_has_position()
    result = f.check(_make_signal(), _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "position_already_open"
    assert result.filter_name == "open_position"


def test_reject_when_open_position_exists_different_symbol():
    """Provider returns True for any symbol → always rejected."""
    f = _make_filter_has_position()
    result = f.check(_make_signal(symbol=_OTHER_SYMBOL), _make_snapshot())
    assert result.passed is False
    assert result.skip_reason == "position_already_open"


# ---------------------------------------------------------------------------
# Provider is called with signal.symbol
# ---------------------------------------------------------------------------


def test_provider_called_with_signal_symbol():
    """Provider must receive the exact symbol from the signal."""
    received_symbols: list[str] = []

    def tracking_provider(symbol: str) -> bool:
        received_symbols.append(symbol)
        return False

    f = OpenPositionFilter(has_open_position_provider=tracking_provider)
    target_symbol = "A09999"
    f.check(_make_signal(symbol=target_symbol), _make_snapshot())

    assert received_symbols == [target_symbol]


def test_provider_called_with_signal_symbol_on_reject():
    """Provider receives signal.symbol even when returning True (reject path)."""
    received_symbols: list[str] = []

    def tracking_provider(symbol: str) -> bool:
        received_symbols.append(symbol)
        return True  # open position exists

    f = OpenPositionFilter(has_open_position_provider=tracking_provider)
    target_symbol = "A05603"
    result = f.check(_make_signal(symbol=target_symbol), _make_snapshot())

    assert result.passed is False
    assert received_symbols == [target_symbol]


def test_provider_called_on_each_check():
    """Provider is invoked for every check() call, not cached."""
    call_count = [0]

    def counting_provider(symbol: str) -> bool:
        call_count[0] += 1
        return False

    f = OpenPositionFilter(has_open_position_provider=counting_provider)
    snap = _make_snapshot()

    f.check(_make_signal(), snap)
    f.check(_make_signal(), snap)
    f.check(_make_signal(), snap)

    assert call_count[0] == 3


def test_provider_symbol_routing():
    """A symbol-aware provider allows per-symbol open-position logic."""
    open_symbols = {_SYMBOL}

    def symbol_aware_provider(symbol: str) -> bool:
        return symbol in open_symbols

    f = OpenPositionFilter(has_open_position_provider=symbol_aware_provider)
    snap = _make_snapshot()

    # Symbol with open position → reject
    result_open = f.check(_make_signal(symbol=_SYMBOL), snap)
    assert result_open.passed is False

    # Different symbol with no open position → pass
    result_free = f.check(_make_signal(symbol=_OTHER_SYMBOL), snap)
    assert result_free.passed is True


# ---------------------------------------------------------------------------
# size_multiplier is always 1.0 (filter does not reduce size, only rejects)
# ---------------------------------------------------------------------------


def test_pass_has_full_size_multiplier():
    f = _make_filter_no_position()
    result = f.check(_make_signal(), _make_snapshot())
    assert result.size_multiplier == 1.0


def test_rejected_has_default_size_multiplier():
    f = _make_filter_has_position()
    result = f.check(_make_signal(), _make_snapshot())
    assert result.size_multiplier == 1.0
