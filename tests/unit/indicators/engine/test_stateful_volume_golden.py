"""Golden pin: stateful VWAP / VolumeAcceleration relocation is value-preserving.

``stateful_volume_golden.json`` captures a live tick sequence through
``VWAPCalculator`` (incl. a KST date-boundary reset) and
``VolumeAccelerationCalculator`` BEFORE they were relocated from
``shared/indicators/volume.py`` into ``shared/indicators/engine/stateful.py``.
Asserts the relocated classes reproduce every per-tick result bit-for-bit, and
that the volume.py re-export + the engine export both resolve to them.
"""

from __future__ import annotations

import json
from pathlib import Path

from shared.indicators.engine import (
    VolumeAccelerationCalculator,
    VolumeConfig,
    VWAPCalculator,
)
from shared.indicators.volume import (
    VolumeAccelerationCalculator as VolAccelReexport,
)
from shared.indicators.volume import (
    VWAPCalculator as VWAPReexport,
)

_GOLDEN = json.loads(
    (Path(__file__).parent / "stateful_volume_golden.json").read_text()
)


def test_reexport_is_the_engine_class() -> None:
    # backward-compat: volume.py re-exports the very same classes
    assert VWAPReexport is VWAPCalculator
    assert VolAccelReexport is VolumeAccelerationCalculator


def test_vwap_session_sequence_matches_golden() -> None:
    vw = VWAPCalculator()
    for (code, price, volume, date_str), exp in zip(
        _GOLDEN["vwap_ticks"], _GOLDEN["vwap_out"]
    ):
        vw.add_tick(code, price, volume, date_str)
        r = vw.calculate(code, current_price=price)
        got = [
            r.vwap,
            r.price_vs_vwap,
            r.is_above_vwap,
            r.cumulative_pv,
            r.cumulative_volume,
        ]
        assert got == exp


def test_volume_acceleration_tick_sequence_matches_golden() -> None:
    va = VolumeAccelerationCalculator(VolumeConfig(window_size=60, lookback_seconds=10))
    for (ts, vol), exp in zip(_GOLDEN["va_seq"], _GOLDEN["va_out"]):
        va.add_tick("A", volume=vol, timestamp=ts)
        r = va.calculate("A")
        got = [
            r.velocity,
            r.acceleration,
            r.is_accelerating,
            r.current_window_volume,
            r.prev_window_volume,
        ]
        assert got == exp
