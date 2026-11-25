"""Shadow comparison primitives for gating engine delegation.

When we migrate a hand-rolled ``_calc_*`` to delegate to the engine, the value
may change (e.g. ATR SMA -> Wilder). :class:`ShadowDelta` is the small,
dependency-light record that measures new-vs-legacy so the same comparison drives
both the parity tests (``tests/unit/indicators/engine/test_shadow_parity.py``)
and an optional runtime shadow-logging mode later. It classifies each indicator
as delegate-safe (within tolerance) or gate-required (divergent).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShadowDelta:
    """The gap between an engine value and the legacy calculator's value."""

    indicator: str
    engine_value: float
    legacy_value: float

    @property
    def abs_delta(self) -> float:
        return abs(self.engine_value - self.legacy_value)

    @property
    def rel_delta(self) -> float:
        """Absolute delta over |legacy|; inf when legacy is ~0."""
        denom = abs(self.legacy_value)
        if denom <= 1e-12:
            return float("inf")
        return self.abs_delta / denom

    def within(self, *, abs_tol: float = 0.0, rel_tol: float = 0.0) -> bool:
        """True when new/legacy agree within either tolerance (delegate-safe)."""
        return self.abs_delta <= abs_tol or self.rel_delta <= rel_tol
