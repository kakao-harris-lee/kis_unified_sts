"""Unit tests for shared.utils.coercion (None-returning field parsers)."""

from __future__ import annotations

import math

import pytest

from shared.utils.coercion import to_bool, to_float, to_int, to_text


class TestToFloat:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("1.5", 1.5),
            (2, 2.0),
            (0, 0.0),  # real zero survives (not None)
            (-3.25, -3.25),
            ("0.0000", 0.0),
        ],
    )
    def test_valid(self, value, expected):
        assert to_float(value) == pytest.approx(expected)

    @pytest.mark.parametrize("value", [None, "", "abc", [], {}])
    def test_absent_or_unparseable_is_none(self, value):
        assert to_float(value) is None

    def test_nan_and_inf_are_none(self):
        assert to_float(float("nan")) is None
        assert to_float(float("inf")) is None
        assert to_float("inf") is None
        assert to_float("nan") is None


class TestToInt:
    def test_truncates_via_float(self):
        assert to_int("3.9") == 3
        assert to_int(4) == 4

    @pytest.mark.parametrize("value", [None, "", "x"])
    def test_absent_is_none(self, value):
        assert to_int(value) is None

    def test_zero_survives(self):
        assert to_int("0") == 0


class TestToText:
    def test_strips(self):
        assert to_text("  A05607 ") == "A05607"

    @pytest.mark.parametrize("value", [None, "", "   "])
    def test_empty_is_none(self, value):
        assert to_text(value) is None

    def test_non_str_coerced(self):
        assert to_text(5) == "5"


class TestToBool:
    @pytest.mark.parametrize("value", [True, "true", "True", "1", "yes", "YES"])
    def test_truthy(self, value):
        assert to_bool(value) is True

    @pytest.mark.parametrize("value", [False, "false", "0", "no", "NO"])
    def test_falsy(self, value):
        assert to_bool(value) is False

    @pytest.mark.parametrize("value", [None, "", "maybe", "2"])
    def test_unrecognized_is_none(self, value):
        assert to_bool(value) is None

    def test_bool_passthrough_not_stringified(self):
        # Real bools bypass token matching.
        assert to_bool(True) is True
        assert to_bool(False) is False


def test_no_execution_import():
    """coercion must stay stdlib-only so the hedge lane can import it."""
    import sys

    import shared.utils.coercion  # noqa: F401

    bad = [
        n
        for n in sys.modules
        if n == "shared.execution" or n.startswith("shared.execution.")
    ]
    assert bad == []
    # sanity: module uses math for isfinite
    assert math.isfinite(1.0)
