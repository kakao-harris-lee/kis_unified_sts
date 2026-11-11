"""Scaling goldens: the two rounding modes, their edges, and their one home.

The edges are the point. A price exactly on a half and a negative signed value
are where ``half_up``, ``toward_zero`` and Python's own ``round`` all disagree,
and a published integer that disagrees with the legacy producer by one unit is a
threshold that fires on a different bar.
"""

from __future__ import annotations

import math

import pytest

from shared.indicators.fields import (
    ROUNDING_MODES,
    scaled_int_half_up,
    scaled_int_toward_zero,
)


class TestHalfUp:
    @pytest.mark.parametrize(
        ("value", "scale", "expected"),
        [
            # Exact halves round AWAY from zero on the positive side...
            (0.5, 1, 1),
            (1.5, 1, 2),
            (2.5, 1, 3),  # round(2.5) is 2 — banker's rounding, not this
            (3.5, 1, 4),
            # ...and UP (toward zero) on the negative side: floor(x + 0.5).
            (-0.5, 1, 0),
            (-1.5, 1, -1),
            (-2.5, 1, -2),
            # Prices at scale 100 — the CP-3 journal's own cases.
            (559.45, 100, 55945),
            # 559.455 is 559.45500000000004 as a double, so *100 lands just
            # ABOVE the half and floor(x + 0.5) carries in BOTH directions —
            # the exact-half asymmetry above only shows on a true half.
            (559.455, 100, 55946),
            (-559.455, 100, -55946),
            # Below/above the half.
            (1.4999, 1, 1),
            (1.5001, 1, 2),
            (0.0, 100, 0),
            (-0.0, 100, 0),
        ],
    )
    def test_golden(self, value: float, scale: int, expected: int) -> None:
        assert scaled_int_half_up(value, scale) == expected

    def test_is_floor_of_value_plus_half(self) -> None:
        """The definition, restated: no parity dependence anywhere."""
        for raw in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 12.345, -12.345):
            assert scaled_int_half_up(raw, 100) == int(math.floor(raw * 100 + 0.5))

    def test_monotone_so_ohlc_relations_survive(self) -> None:
        """high >= low must still hold after scaling (a tos Bar validates it)."""
        high, low = 100.005, 100.004999
        assert scaled_int_half_up(high, 100) >= scaled_int_half_up(low, 100)


class TestTowardZero:
    @pytest.mark.parametrize(
        ("value", "scale", "expected"),
        [
            # The symmetry case from the z_x1000 docstring.
            (1.7995, 1000, 1799),
            (-1.7995, 1000, -1799),
            # Exact halves truncate, both signs.
            (0.5, 1, 0),
            (-0.5, 1, 0),
            (1.5, 1, 1),
            (-1.5, 1, -1),
            (2.5, 1, 2),
            (-2.5, 1, -2),
            # Magnitudes below one unit collapse to zero, never to -1.
            (0.9, 1, 0),
            (-0.9, 1, 0),
            (1.8, 1000, 1800),
            (-1.8, 1000, -1800),
            (0.0, 1000, 0),
        ],
    )
    def test_golden(self, value: float, scale: int, expected: int) -> None:
        assert scaled_int_toward_zero(value, scale) == expected

    def test_symmetric_about_zero(self) -> None:
        for raw in (0.0, 0.0004, 0.5, 1.7995, 1.8, 2.60001, 12.345):
            assert scaled_int_toward_zero(-raw, 1000) == -scaled_int_toward_zero(
                raw, 1000
            )

    def test_conservative_at_the_trigger(self) -> None:
        """``abs(scaled) >= scaled(threshold)`` only when ``abs(z) >= threshold``.

        The property the CP-3 journal's ``z_x1000`` is published for: a policy
        written on the integer never fires where the legacy setup did not.
        """
        threshold = scaled_int_toward_zero(1.8, 1000)
        for z in (1.7999, -1.7999, 1.79999, -1.79999):
            assert abs(scaled_int_toward_zero(z, 1000)) < threshold
        for z in (1.8, -1.8, 1.80001, -1.80001):
            assert abs(scaled_int_toward_zero(z, 1000)) >= threshold

    def test_differs_from_half_up_exactly_where_it_should(self) -> None:
        assert scaled_int_half_up(1.7995, 1000) == 1800  # the half-up rule
        assert scaled_int_toward_zero(1.7995, 1000) == 1799


class TestOneHome:
    def test_rounding_modes_are_the_two_published_modes(self) -> None:
        assert sorted(ROUNDING_MODES) == ["half_up", "toward_zero"]
        assert ROUNDING_MODES["half_up"] is scaled_int_half_up
        assert ROUNDING_MODES["toward_zero"] is scaled_int_toward_zero

    def test_producer_reads_the_same_functions(self) -> None:
        """``produce_fields`` must not carry a second copy of either rule.

        The CP-3 producer and the declarative evaluator publish the same journal
        fields; identity (``is``) is what makes "byte-identical rounding" a fact
        rather than a hope.
        """
        from tools.tos_cp3 import produce_fields

        assert produce_fields.scaled_int_half_up is scaled_int_half_up
        assert produce_fields.scaled_int_toward_zero is scaled_int_toward_zero
