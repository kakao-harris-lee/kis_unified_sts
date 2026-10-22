"""``_model_view.shape_constraints.price_band_ticks`` — the per-price-band tick table loader.

The kernel has carried ``VenueShapeConstraints.price_band_ticks`` since kernel round #4 K-1;
nothing in the runtime loaded it, so a deployment could only declare ONE flat ``tick_size``.
A KRX stock tick is a price ladder, so the flat field cannot be right on both sides of a rung:
the concrete input is 005930 at 199,900원 — a legal price on the 100원 rung — which a flat
500원 tick refuses (INADMISSIBLE, see ``test_the_flat_tick_refuses_a_legal_price_below_the_rung``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.venue import OrderAdmissibilityResult, OrderShapeFields, PriceBandTick
from tos.venue.predicates import order_shape_admissible
from tos_runtime.venue.band_source import BandRefusal, validate_band_values
from tos_runtime.venue.config import (
    VenuePolicyConfigError,
    load_venue_constraint_policy,
)

from .conftest import SCHEME, venue_policy_yaml, write_fixture_venue_policy

#: Two rungs of the KRX stock ladder at the ×100 integer price scale:
#: 50,000~199,999원 -> 100원 · 200,000~499,999원 -> 500원.
_TABLE = """    price_band_ticks:
      - {band_min: 5000000, band_max: 19999999, tick: 10000}
      - {band_min: 20000000, band_max: 49999999, tick: 50000}
"""


def _with_table(table: str) -> str:
    text = venue_policy_yaml()
    anchor = "    tick_size: 5\n"
    assert text.count(anchor) == 1
    return text.replace(anchor, anchor + table)


def _load(tmp_path: Path, text: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    return load_venue_constraint_policy(
        write_fixture_venue_policy(tmp_path, text), scheme=SCHEME
    )


def _shape(price: int) -> OrderShapeFields:
    return OrderShapeFields(
        price=price,
        quantity=1,
        order_type="LIMIT",
        tif="DAY",
        side="BUY",
        position_effect="OPEN",
        silently_rounded=False,
    )


def test_no_table_keeps_the_flat_tick_and_the_digest(tmp_path: Path) -> None:
    """Absent and ``null`` are the same document: every existing tree loads unchanged."""
    absent = _load(tmp_path / "a", venue_policy_yaml())
    null = _load(tmp_path / "b", _with_table("    price_band_ticks: null\n"))
    assert absent.policy.shape_constraints.price_band_ticks is None
    assert null.policy.shape_constraints.price_band_ticks is None
    assert absent.policy.canonical_digest == null.policy.canonical_digest


def test_a_declared_table_is_loaded_and_bound_into_the_digest(tmp_path: Path) -> None:
    flat = _load(tmp_path / "a", venue_policy_yaml())
    table = _load(tmp_path / "b", _with_table(_TABLE))
    assert table.policy.shape_constraints.price_band_ticks == (
        PriceBandTick(band_min=5_000_000, band_max=19_999_999, tick=10_000),
        PriceBandTick(band_min=20_000_000, band_max=49_999_999, tick=50_000),
    )
    assert table.policy.canonical_digest != flat.policy.canonical_digest


def _banded(loaded):
    return loaded.policy.shape_constraints.model_copy(
        # The fixture leaves the band and max_quantity null (UNKNOWN); fill them so the
        # TICK is the only thing under test.
        update={"price_min": 0, "price_max": 100_000_000, "max_quantity": 1}
    )


@pytest.mark.parametrize(
    ("price", "expected"),
    [
        (
            19_990_000,
            OrderAdmissibilityResult.ADMISSIBLE,
        ),  # 199,900원 on the 100원 rung
        (19_995_000, OrderAdmissibilityResult.INADMISSIBLE),  # 199,950원 off-grid
        (
            27_000_000,
            OrderAdmissibilityResult.ADMISSIBLE,
        ),  # 270,000원 on the 500원 rung
        (
            27_010_000,
            OrderAdmissibilityResult.INADMISSIBLE,
        ),  # 270,100원 off the 500 grid
        (
            60_000_000,
            OrderAdmissibilityResult.UNKNOWN,
        ),  # no row covers it — never widened
    ],
)
def test_the_table_resolves_the_tick_for_each_price(
    tmp_path: Path, price: int, expected: OrderAdmissibilityResult
) -> None:
    constraints = _banded(_load(tmp_path, _with_table(_TABLE)))
    assert order_shape_admissible(_shape(price), constraints) is expected


def test_the_flat_tick_refuses_a_legal_price_below_the_rung(tmp_path: Path) -> None:
    """Why the table exists: a flat 500원 tick (50000) refuses 199,900원, a legal price."""
    text = venue_policy_yaml().replace("    tick_size: 5\n", "    tick_size: 50000\n")
    constraints = _banded(_load(tmp_path, text))
    assert (
        order_shape_admissible(_shape(19_990_000), constraints)
        is OrderAdmissibilityResult.INADMISSIBLE
    )


@pytest.mark.parametrize(
    ("table", "why"),
    [
        ("    price_band_ticks: []\n", "non-empty list"),
        (
            "    price_band_ticks:\n      - {band_min: 1, band_max: 2}\n",
            "exactly band_min/band_max/tick",
        ),
        (
            "    price_band_ticks:\n"
            "      - {band_min: 1, band_max: 2, tick: 1, note: x}\n",
            "exactly band_min/band_max/tick",
        ),
        (
            "    price_band_ticks:\n" "      - {band_min: 1, band_max: 2, tick: 0}\n",
            "tick must be positive",
        ),
        (
            "    price_band_ticks:\n" "      - {band_min: 5, band_max: 2, tick: 1}\n",
            "band_min > band_max",
        ),
        (
            "    price_band_ticks:\n"
            "      - {band_min: 1, band_max: 10, tick: 1}\n"
            "      - {band_min: 10, band_max: 20, tick: 5}\n",
            "ascending and disjoint",
        ),
        (
            "    price_band_ticks:\n"
            "      - {band_min: 1, band_max: 2, tick: true}\n",
            "values must be ints",
        ),
    ],
)
def test_each_malformed_table_is_refused(tmp_path: Path, table: str, why: str) -> None:
    with pytest.raises(VenuePolicyConfigError, match=why):
        _load(tmp_path, _with_table(table))


# ---------------------------------------------------------------------------
# The band validator uses the same table (a band can straddle a rung)
# ---------------------------------------------------------------------------

_ROWS = (
    PriceBandTick(band_min=5_000_000, band_max=19_999_999, tick=10_000),
    PriceBandTick(band_min=20_000_000, band_max=49_999_999, tick=50_000),
)


def _validate(lower: str, upper: str, **kwargs):
    return validate_band_values(
        lower_raw=lower,
        upper_raw=upper,
        basis_raw="270000",
        price_scale=100,
        lower_label="lower",
        upper_label="upper",
        **kwargs,
    )


def test_a_band_straddling_a_rung_is_valid_against_the_table() -> None:
    """189,100원 (100원 rung) / 351,000원 (500원 rung): legal limits around 270,000원."""
    outcome = _validate("189100", "351000", tick_size=50_000, price_band_ticks=_ROWS)
    assert not isinstance(outcome, BandRefusal), outcome
    assert (outcome.price_min, outcome.price_max) == (18_910_000, 35_100_000)


def test_the_same_band_is_refused_by_the_flat_tick() -> None:
    """Why the band reader needs the table too: flat 500원 refuses the 189,100원 lower limit."""
    outcome = _validate("189100", "351000", tick_size=50_000)
    assert isinstance(outcome, BandRefusal)
    assert outcome.reason == "off_tick_grid"


@pytest.mark.parametrize(
    ("lower", "upper", "reason"),
    [
        ("189100", "351100", "off_tick_grid"),  # 351,100원 is off the 500원 rung
        ("189150", "351000", "off_tick_grid"),  # 189,150원 is off the 100원 rung
        ("189100", "600000", "tick_unresolved"),  # no row covers 600,000원
    ],
)
def test_a_bound_off_its_own_rung_is_refused(
    lower: str, upper: str, reason: str
) -> None:
    outcome = _validate(lower, upper, tick_size=50_000, price_band_ticks=_ROWS)
    assert isinstance(outcome, BandRefusal)
    assert outcome.reason == reason
