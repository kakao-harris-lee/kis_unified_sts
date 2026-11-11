"""Every ``fields.yaml`` refusal, by name.

Plan §2.2 lists what a producer must refuse at boot: unknown op, catalog version
mismatch, a forward or unknown input reference, a cycle, a publish naming a
missing field, duplicate names, bad parameters. Each gets a test here, and each
refusal carries its own message — a producer that refuses without saying which
rule it refused on is not operable.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
import yaml

from shared.indicators.fields import (
    CATALOG_VERSION,
    SCHEMA_VERSION,
    FieldSpecError,
    load_fields_file,
    parse_fields_document,
)

from .conftest import document

_CLOSE: dict[str, Any] = {"name": "close", "op": "bar.close"}
_POSITIVE: dict[str, Any] = {
    "name": "positive",
    "op": "gt",
    "inputs": ["close"],
    "params": {"const": 0},
}


def _refuse(raw: Any, match: str) -> str:
    with pytest.raises(FieldSpecError, match=match) as excinfo:
        parse_fields_document(raw)
    return str(excinfo.value)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


class TestVersions:
    def test_a_valid_document_loads(self) -> None:
        loaded = parse_fields_document(document([_CLOSE, _POSITIVE]))
        assert loaded.schema == SCHEMA_VERSION
        assert loaded.catalog == CATALOG_VERSION
        assert [spec.name for spec in loaded.fields] == ["close", "positive"]
        assert [entry.name for entry in loaded.publish] == ["positive"]

    def test_unknown_schema(self) -> None:
        _refuse(
            document([_CLOSE, _POSITIVE], schema="tos-fields/2"),
            "unknown schema",
        )

    def test_missing_schema(self) -> None:
        raw = document([_CLOSE, _POSITIVE])
        del raw["schema"]
        _refuse(raw, "unknown schema")

    def test_catalog_version_mismatch(self) -> None:
        """A catalog bump must not silently reinterpret a shipped declaration."""
        message = _refuse(
            document([_CLOSE, _POSITIVE], catalog="tos-field-catalog/2"),
            "catalog version",
        )
        assert CATALOG_VERSION in message

    def test_unknown_top_level_key(self) -> None:
        raw = document([_CLOSE, _POSITIVE])
        raw["publsh"] = []  # a typo must not produce an empty journal
        _refuse(raw, "unknown key")


# ---------------------------------------------------------------------------
# Fields
# ---------------------------------------------------------------------------


class TestFieldList:
    def test_fields_must_be_a_non_empty_list(self) -> None:
        raw = document([_CLOSE])
        raw["fields"] = []
        _refuse(raw, "fields must be a non-empty list")
        raw["fields"] = {"name": "close", "op": "bar.close"}
        _refuse(raw, "fields must be a non-empty list")

    def test_unknown_field_key(self) -> None:
        _refuse(
            document([{"name": "close", "op": "bar.close", "parms": {}}]),
            "unknown key",
        )

    def test_missing_name(self) -> None:
        _refuse(document([{"op": "bar.close"}]), "name must be a non-empty string")

    def test_unknown_op(self) -> None:
        message = _refuse(
            document([{"name": "probe", "op": "bar.typical_price"}]),
            "unknown op",
        )
        assert "bar.close" in message  # the refusal lists the known ops

    def test_duplicate_field_name(self) -> None:
        _refuse(
            document([_CLOSE, dict(_CLOSE), _POSITIVE]),
            "duplicate name",
        )


class TestReferences:
    def test_cycle_self_reference(self) -> None:
        _refuse(
            document([{"name": "loop", "op": "not", "inputs": ["loop"]}]),
            "cycle",
        )

    def test_forward_reference(self) -> None:
        """Fields may only read EARLIER fields — that is what makes a longer
        cycle impossible rather than merely unlikely."""
        _refuse(
            document(
                [
                    {"name": "a", "op": "not", "inputs": ["b"]},
                    {"name": "b", "op": "not", "inputs": ["a"]},
                ]
            ),
            "forward reference",
        )

    def test_unknown_reference(self) -> None:
        _refuse(
            document([{"name": "probe", "op": "abs", "inputs": ["nope"]}]),
            "unknown reference",
        )

    def test_sample_when_forward_reference(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    {
                        "name": "probe",
                        "op": "gated_lag",
                        "inputs": ["close"],
                        "params": {"sample_when": "later"},
                    },
                    _POSITIVE,
                    {"name": "later", "op": "not", "inputs": ["positive"]},
                ]
            ),
            "forward reference",
        )


class TestArityAndKinds:
    def test_too_few_inputs(self) -> None:
        _refuse(
            document([_CLOSE, {"name": "probe", "op": "ratio_z", "inputs": ["close"]}]),
            "arity",
        )

    def test_too_many_inputs(self) -> None:
        _refuse(
            document(
                [_CLOSE, {"name": "probe", "op": "abs", "inputs": ["close", "close"]}]
            ),
            "arity",
        )

    def test_a_bool_where_a_number_is_required(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    _POSITIVE,
                    {"name": "probe", "op": "abs", "inputs": ["positive"]},
                ]
            ),
            "value kind",
        )

    def test_a_number_where_a_bool_is_required(self) -> None:
        _refuse(
            document([_CLOSE, {"name": "probe", "op": "all", "inputs": ["close"]}]),
            "value kind",
        )

    def test_a_string_where_a_number_is_required(self) -> None:
        _refuse(
            document(
                [
                    {"name": "token", "op": "session.token"},
                    {"name": "probe", "op": "abs", "inputs": ["token"]},
                ]
            ),
            "value kind",
        )

    def test_sample_when_must_name_a_bool(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    {
                        "name": "probe",
                        "op": "gated_lag",
                        "inputs": ["close"],
                        "params": {"sample_when": "close"},
                    },
                    _POSITIVE,
                ]
            ),
            "value kind",
        )


class TestParams:
    def test_unknown_parameter(self) -> None:
        _refuse(
            document([{"name": "probe", "op": "atr", "params": {"periods": 14}}]),
            "unknown parameter",
        )

    def test_missing_required_parameter(self) -> None:
        _refuse(document([{"name": "probe", "op": "atr"}]), "missing required")

    def test_non_integer_count(self) -> None:
        _refuse(
            document([{"name": "probe", "op": "atr", "params": {"period": 14.5}}]),
            "must be an integer",
        )

    def test_count_below_one(self) -> None:
        _refuse(
            document([{"name": "probe", "op": "atr", "params": {"period": 0}}]),
            "must be >= 1",
        )

    def test_percentile_out_of_range(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    _POSITIVE,
                    {
                        "name": "probe",
                        "op": "gated_percentile",
                        "inputs": ["close"],
                        "params": {
                            "q": 120,
                            "window": 10,
                            "warmup": 2,
                            "sample_when": "positive",
                        },
                    },
                ]
            ),
            r"must be in \[0, 100\]",
        )

    def test_warmup_above_window(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    _POSITIVE,
                    {
                        "name": "probe",
                        "op": "gated_max",
                        "inputs": ["close"],
                        "params": {"window": 5, "warmup": 6, "sample_when": "positive"},
                    },
                ]
            ),
            "permanently None",
        )

    def test_between_with_an_empty_window(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    {
                        "name": "probe",
                        "op": "between",
                        "inputs": ["close"],
                        "params": {"lo": 10, "hi": 5},
                    },
                ]
            ),
            "window is empty",
        )

    def test_comparison_with_both_a_second_input_and_a_const(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    {
                        "name": "probe",
                        "op": "ge",
                        "inputs": ["close", "close"],
                        "params": {"const": 1},
                    },
                ]
            ),
            "ambiguous",
        )

    def test_comparison_with_no_right_hand_side(self) -> None:
        _refuse(
            document([_CLOSE, {"name": "probe", "op": "ge", "inputs": ["close"]}]),
            "no right-hand side",
        )

    @pytest.mark.parametrize("literal", [".nan", ".inf", "-.inf"])
    def test_non_finite_const(self, literal: str) -> None:
        """``gt const: .nan`` used to LOAD and then be false on every bar.

        Every comparison against NaN is false, so a NaN threshold is a gate that
        can never pass — exactly the silently dead gate this loader refuses
        elsewhere (``warmup > window``, ``lo > hi``). YAML spells it ``.nan``,
        so it arrives as an ordinary float scalar rather than a string.
        """
        raw = yaml.safe_load(
            "schema: tos-fields/1\n"
            f"catalog: {CATALOG_VERSION}\n"
            "fields:\n"
            "  - {name: close, op: bar.close}\n"
            f"  - {{name: probe, op: gt, inputs: [close], params: {{const: {literal}}}}}\n"
            "publish:\n"
            "  - {field: probe}\n"
        )
        assert not math.isfinite(raw["fields"][1]["params"]["const"])  # it parsed
        _refuse(raw, "must be finite")

    @pytest.mark.parametrize("bound", ["lo", "hi"])
    def test_non_finite_between_bound(self, bound: str) -> None:
        """``between lo: .nan`` is the same hazard on a window bound."""
        params = {"lo": 15, "hi": 345}
        params[bound] = float("nan")
        _refuse(
            document(
                [
                    _CLOSE,
                    {
                        "name": "probe",
                        "op": "between",
                        "inputs": ["close"],
                        "params": params,
                    },
                ]
            ),
            "must be finite",
        )

    def test_non_finite_mult(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    {
                        "name": "probe",
                        "op": "ge",
                        "inputs": ["close"],
                        "params": {"const": 1.0, "mult": float("inf")},
                    },
                ]
            ),
            "must be finite",
        )

    def test_bad_time_literal(self) -> None:
        _refuse(
            document([{"name": "probe", "op": "time_ge", "params": {"at": "15h40"}}]),
            "not a 'HH:MM'",
        )

    def test_non_bool_when_missing(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    _POSITIVE,
                    {
                        "name": "probe",
                        "op": "permissive",
                        "inputs": ["positive"],
                        "params": {"when_missing": "yes"},
                    },
                ]
            ),
            "must be true or false",
        )

    def test_open_anchor_bounds(self) -> None:
        _refuse(
            document(
                [
                    {
                        "name": "probe",
                        "op": "session.minutes_since_open",
                        "params": {"open_hour": 24, "open_minute": 0},
                    }
                ]
            ),
            "must be <= 23",
        )
        _refuse(
            document(
                [
                    {
                        "name": "probe",
                        "op": "session.minutes_since_open",
                        "params": {"open_hour": 8, "open_minute": 60},
                    }
                ]
            ),
            "must be <= 59",
        )


# ---------------------------------------------------------------------------
# Definite values
# ---------------------------------------------------------------------------

#: A field that is ``None`` during warmup: the lag has no previous sample on the
#: first bar, so the comparison that reads it propagates the missing value.
_MAYBE_MISSING: list[dict[str, Any]] = [
    _CLOSE,
    {"name": "t", "op": "gt", "inputs": ["close"], "params": {"const": 0}},
    {
        "name": "lag",
        "op": "gated_lag",
        "inputs": ["close"],
        "params": {"sample_when": "t"},
    },
    {"name": "raw", "op": "gt", "inputs": ["close", "lag"]},
]


class TestMayBeMissing:
    """A missing value must be refused at LOAD, not on the first warmup bar.

    ``all: [t, gt(c, gated_lag(c))]`` loaded cleanly and then raised on bar 1.
    A producer that boots and dies one bar later is worse than one that refuses
    to boot, so the reachability is decided on the declaration.
    """

    def test_all_operand_that_may_be_missing(self) -> None:
        message = _refuse(
            document(
                [*_MAYBE_MISSING, {"name": "bad", "op": "all", "inputs": ["t", "raw"]}]
            ),
            "may be missing",
        )
        assert "'raw'" in message  # the refusal names the culprit, not just the op

    @pytest.mark.parametrize("op", ["all", "any"])
    def test_any_boolean_combinator(self, op: str) -> None:
        _refuse(
            document(
                [*_MAYBE_MISSING, {"name": "bad", "op": op, "inputs": ["t", "raw"]}]
            ),
            "may be missing",
        )

    def test_not_operand_that_may_be_missing(self) -> None:
        _refuse(
            document(
                [*_MAYBE_MISSING, {"name": "bad", "op": "not", "inputs": ["raw"]}]
            ),
            "may be missing",
        )

    def test_sample_when_that_may_be_missing(self) -> None:
        _refuse(
            document(
                [
                    *_MAYBE_MISSING,
                    {
                        "name": "bad",
                        "op": "gated_max",
                        "inputs": ["close"],
                        "params": {"window": 3, "warmup": 1, "sample_when": "raw"},
                    },
                    {"name": "out", "op": "permissive", "inputs": ["raw"]},
                ]
            ),
            "may be missing",
        )

    def test_missingness_propagates_through_a_chain(self) -> None:
        """``abs(ratio_z(..., lag))`` is missing too — the check is transitive."""
        _refuse(
            document(
                [
                    *_MAYBE_MISSING,
                    {"name": "z", "op": "ratio_z", "inputs": ["close", "lag", "close"]},
                    {"name": "az", "op": "abs", "inputs": ["z"]},
                    {
                        "name": "far",
                        "op": "gt",
                        "inputs": ["az"],
                        "params": {"const": 1},
                    },
                    {"name": "bad", "op": "all", "inputs": ["t", "far"]},
                ]
            ),
            "may be missing",
        )

    def test_permissive_makes_it_definite(self) -> None:
        """The escape hatch, and the only one: wrap it in ``permissive``."""
        loaded = parse_fields_document(
            document(
                [
                    *_MAYBE_MISSING,
                    {"name": "ok", "op": "permissive", "inputs": ["raw"]},
                    {"name": "good", "op": "all", "inputs": ["t", "ok"]},
                ]
            )
        )
        assert [spec.name for spec in loaded.fields][-1] == "good"

    def test_a_definite_operand_still_loads(self) -> None:
        loaded = parse_fields_document(
            document(
                [
                    _CLOSE,
                    _POSITIVE,
                    {"name": "good", "op": "not", "inputs": ["positive"]},
                ]
            )
        )
        assert loaded.fields[-1].name == "good"


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------


class TestPublish:
    def test_publish_must_be_a_non_empty_list(self) -> None:
        raw = document([_CLOSE, _POSITIVE])
        raw["publish"] = []
        _refuse(raw, "publish must be a non-empty list")

    def test_publish_names_a_missing_field(self) -> None:
        _refuse(
            document([_CLOSE, _POSITIVE], [{"field": "hi_vol"}]),
            "which no field declares",
        )

    def test_duplicate_published_name(self) -> None:
        _refuse(
            document(
                [
                    _CLOSE,
                    _POSITIVE,
                    {"name": "other", "op": "not", "inputs": ["positive"]},
                ],
                [{"field": "positive", "as": "ok"}, {"field": "other", "as": "ok"}],
            ),
            "duplicate name",
        )

    def test_a_number_needs_a_scale(self) -> None:
        """The kernel drops a float at the border — an unscaled number is a
        field that would silently never arrive."""
        _refuse(
            document([_CLOSE, _POSITIVE], [{"field": "close"}]),
            "it needs a scale",
        )

    def test_a_bool_must_not_carry_a_scale(self) -> None:
        _refuse(
            document(
                [_CLOSE, _POSITIVE],
                [{"field": "positive", "scale": {"mult": 100, "round": "half_up"}}],
            ),
            "a scale is meaningless",
        )

    def test_unknown_rounding_mode(self) -> None:
        _refuse(
            document(
                [_CLOSE, _POSITIVE],
                [
                    {
                        "field": "close",
                        "as": "close_x100",
                        "scale": {"mult": 100, "round": "bankers"},
                    }
                ],
            ),
            "round='bankers' is unknown",
        )

    def test_scale_requires_both_keys(self) -> None:
        _refuse(
            document(
                [_CLOSE, _POSITIVE],
                [{"field": "close", "as": "close_x100", "scale": {"mult": 100}}],
            ),
            "scale is missing",
        )

    def test_scale_mult_must_be_a_positive_integer(self) -> None:
        for mult in (0, -100, 100.0):
            _refuse(
                document(
                    [_CLOSE, _POSITIVE],
                    [
                        {
                            "field": "close",
                            "as": "close_x100",
                            "scale": {"mult": mult, "round": "half_up"},
                        }
                    ],
                ),
                "scale mult",
            )

    def test_as_defaults_to_the_field_name(self) -> None:
        loaded = parse_fields_document(document([_CLOSE, _POSITIVE]))
        assert loaded.publish[0].name == "positive"
        assert loaded.publish[0].field == "positive"
        assert loaded.publish[0].scale is None


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------


class TestLoadFromFile:
    def test_loads_a_file(self, tmp_path: Path) -> None:
        path = tmp_path / "fields.yaml"
        path.write_text(
            "schema: tos-fields/1\n"
            f"catalog: {CATALOG_VERSION}\n"
            "fields:\n"
            "  - {name: close, op: bar.close}\n"
            "  - {name: eod, op: time_ge, params: {at: '15:40'}}\n"
            "publish:\n"
            "  - {field: close, as: close_x100, scale: {mult: 100, round: half_up}}\n"
            "  - {field: eod}\n",
            encoding="utf-8",
        )
        loaded = load_fields_file(path)
        assert [entry.name for entry in loaded.publish] == ["close_x100", "eod"]
        assert loaded.publish[0].scale is not None
        assert loaded.publish[0].scale.mult == 100

    def test_a_refusal_names_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / "fields.yaml"
        path.write_text("schema: tos-fields/9\n", encoding="utf-8")
        with pytest.raises(FieldSpecError, match=r"fields\.yaml: unknown schema"):
            load_fields_file(path)

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "fields.yaml"
        path.write_text("schema: [unterminated\n", encoding="utf-8")
        with pytest.raises(FieldSpecError, match="not valid YAML"):
            load_fields_file(path)
