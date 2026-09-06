"""Unit tests for shared.utils.parsing (0.0/0-defaulting numeric parsers).

Pins the exact semantics several call sites now delegate to directly
(O11-④ float-parser convergence) so a future edit cannot silently change
comma-stripping, the default value, or NaN/inf passthrough.
"""

from __future__ import annotations

import math

import pytest

from shared.utils.parsing import parse_float, parse_int


class TestParseFloat:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, 0.0),
            ("", 0.0),
            ("   ", 0.0),
            ("1,234", 1234.0),
            ("1,234.5", 1234.5),
            ("abc", 0.0),
            (0, 0.0),
            (2, 2.0),
            (2.5, 2.5),
            (True, 1.0),
            (False, 0.0),
            ("  3.5  ", 3.5),
        ],
    )
    def test_values(self, value, expected):
        assert parse_float(value) == pytest.approx(expected)

    def test_nan_passes_through(self):
        # parse_float does not reject non-finite results (unlike
        # shared.utils.coercion.to_float) — callers that need NaN/inf
        # rejected use to_float instead.
        assert math.isnan(parse_float("nan"))
        assert math.isnan(parse_float(float("nan")))

    def test_inf_passes_through(self):
        assert math.isinf(parse_float("inf"))
        assert parse_float(float("inf")) == float("inf")


class TestParseInt:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, 0),
            ("", 0),
            ("1,234", 1234),
            ("3.9", 3),
            ("abc", 0),
            (0, 0),
            (4, 4),
            (4.9, 4),
            (True, 1),
            (False, 0),
        ],
    )
    def test_values(self, value, expected):
        assert parse_int(value) == expected
