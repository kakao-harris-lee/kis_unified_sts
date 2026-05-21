from shared.models.signal import Signal
from shared.strategy.position.sizers import FixedSizer, FixedSizerConfig


def test_fixed_sizer_applies_signal_position_size_multiplier():
    sizer = FixedSizer(
        FixedSizerConfig(
            fixed_amount=1_000_000,
            max_position_pct=100.0,
            max_positions=5,
        )
    )
    signal = Signal(
        code="005930",
        price=50_000,
        metadata={"position_size_multiplier": 0.2},
    )

    qty = sizer.calculate(
        signal=signal,
        account_balance=10_000_000,
        current_positions=[],
    )

    assert qty == 4
