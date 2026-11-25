"""Scaling goldens: the two rounding modes, their edges, and their one home."""

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
            (0.5, 1, 1),
            (1.5, 1, 2),
            (2.5, 1, 3),
            (3.5, 1, 4),
            (-0.5, 1, 0),
            (-1.5, 1, -1),
            (-2.5, 1, -2),
            (559.45, 100, 55945),
            (559.455, 100, 55946),
            (-559.455, 100, -55946),
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
            (1.7995, 1000, 1799),
            (-1.7995, 1000, -1799),
            (0.5, 1, 0),
            (-0.5, 1, 0),
            (1.5, 1, 1),
            (-1.5, 1, -1),
            (2.5, 1, 2),
            (-2.5, 1, -2),
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
        """``abs(scaled) >= scaled(threshold)`` only when ``abs(z) >= threshold``."""
        threshold = scaled_int_toward_zero(1.8, 1000)
        for z in (1.7999, -1.7999, 1.79999, -1.79999):
            assert abs(scaled_int_toward_zero(z, 1000)) < threshold
        for z in (1.8, -1.8, 1.80001, -1.80001):
            assert abs(scaled_int_toward_zero(z, 1000)) >= threshold

    def test_differs_from_half_up_exactly_where_it_should(self) -> None:
        assert scaled_int_half_up(1.7995, 1000) == 1800
        assert scaled_int_toward_zero(1.7995, 1000) == 1799


class TestOneHome:
    def test_rounding_modes_are_the_two_published_modes(self) -> None:
        assert sorted(ROUNDING_MODES) == ["half_up", "toward_zero"]
        assert ROUNDING_MODES["half_up"] is scaled_int_half_up
        assert ROUNDING_MODES["toward_zero"] is scaled_int_toward_zero

    def test_producer_reads_the_same_functions(self) -> None:
        """``produce_fields`` must not carry a second copy of either rule."""
        from tools.tos_cp3 import produce_fields

        assert produce_fields.scaled_int_half_up is scaled_int_half_up
        assert produce_fields.scaled_int_toward_zero is scaled_int_toward_zero
