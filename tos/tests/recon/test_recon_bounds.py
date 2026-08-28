"""ConservativeBound merge (union) + monotonicity + None-dominance (§4.3 / §5.2).

RECON-EV-003 predicate substrate. The central no-blended canary: merge is a widest-
envelope union — ``merge(100, 150) => upper=150``, **never 125** (design #9 §4.1 / §5.2).
None dominates (unbounded = most conservative). Narrowing requires positive strong proof.
"""

from __future__ import annotations

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st
from tos.recon import (
    ConservativeBound,
    bound_narrowing_allowed,
    conservative_bound_of,
    merge_conservative,
)

from ._recon_strategies import bounds, observation


def _b(lower, upper) -> ConservativeBound:
    dec = lambda v: None if v is None else Decimal(v)  # noqa: E731
    return ConservativeBound(lower=dec(lower), upper=dec(upper))


# ---------------------------------------------------------------------------
# merge_conservative — union, never average
# ---------------------------------------------------------------------------


def test_merge_is_union_never_average() -> None:
    """(canary RECON-EV-003) merge(100,150) => lower=100, upper=150 — never the midpoint 125."""
    merged = merge_conservative(_b(100, 100), _b(150, 150))
    assert merged.upper == Decimal(150)
    assert merged.lower == Decimal(100)
    assert merged.upper != Decimal(125)


def test_merge_widest_envelope() -> None:
    """merge takes max of uppers and min of lowers (the widest envelope)."""
    merged = merge_conservative(_b(10, 40), _b(20, 90), _b(5, 30))
    assert merged.lower == Decimal(5)
    assert merged.upper == Decimal(90)


def test_none_upper_dominates() -> None:
    """(None-dominance) An unbounded upper (None = +inf) dominates any finite upper."""
    merged = merge_conservative(_b(0, 100), _b(0, None))
    assert merged.upper is None


def test_none_lower_dominates() -> None:
    """(None-dominance) An unbounded lower (None = -inf) dominates any finite lower."""
    merged = merge_conservative(_b(50, 100), _b(None, 100))
    assert merged.lower is None


def test_empty_merge_is_fully_unbounded() -> None:
    """(fail-closed) A union of no bounds is fully unbounded (most conservative), not narrow."""
    merged = merge_conservative()
    assert merged.lower is None and merged.upper is None


def test_single_bound_merge_is_identity() -> None:
    """A one-bound merge returns that bound's envelope."""
    merged = merge_conservative(_b(10, 20))
    assert merged.lower == Decimal(10) and merged.upper == Decimal(20)


@given(a=bounds(), b=bounds())
def test_merge_covers_every_input(a: ConservativeBound, b: ConservativeBound) -> None:
    """(property §4.1) The merged envelope contains every input envelope (⊇, never narrower)."""
    merged = merge_conservative(a, b)
    assert merged.covers(a)
    assert merged.covers(b)


@given(bs=st.lists(bounds(), min_size=1, max_size=5))
def test_merge_covers_all_of_many(bs: list) -> None:
    """(property) merge over many bounds covers each one."""
    merged = merge_conservative(*bs)
    for b in bs:
        assert merged.covers(b)


# ---------------------------------------------------------------------------
# ConservativeBound.covers — the extended-order containment helper
# ---------------------------------------------------------------------------


def test_covers_none_is_widest() -> None:
    """A fully-unbounded bound covers everything; a finite bound never covers unbounded."""
    unbounded = _b(None, None)
    finite = _b(10, 20)
    assert unbounded.covers(finite) is True
    assert finite.covers(unbounded) is False


def test_covers_is_reflexive() -> None:
    """Every bound covers itself."""
    b = _b(10, 20)
    assert b.covers(b) is True


# ---------------------------------------------------------------------------
# bound_narrowing_allowed — widen free, narrow needs strong proof (§4.3)
# ---------------------------------------------------------------------------


def test_widen_allowed_under_any_basis() -> None:
    """Widening (to ⊇ from) is allowed even with no strong basis."""
    narrow, wide = _b(10, 20), _b(0, 40)
    assert bound_narrowing_allowed(narrow, wide, strong_basis=None) is True
    assert bound_narrowing_allowed(narrow, wide, strong_basis=False) is True


def test_hold_allowed_under_any_basis() -> None:
    """Holding the bound (to == from) is allowed with any basis."""
    b = _b(10, 20)
    assert bound_narrowing_allowed(b, b, strong_basis=None) is True


def test_narrow_requires_strong_basis() -> None:
    """(§8 line 121) Narrowing requires strong proof; None / False fails closed."""
    wide, narrow = _b(0, 40), _b(10, 20)
    assert bound_narrowing_allowed(wide, narrow, strong_basis=True) is True
    assert bound_narrowing_allowed(wide, narrow, strong_basis=False) is False
    assert bound_narrowing_allowed(wide, narrow, strong_basis=None) is False


def test_partial_narrow_treated_as_narrowing() -> None:
    """(conservative) An incomparable move (widen one side, narrow other) needs strong proof."""
    frm, to = _b(10, 100), _b(5, 90)  # wider lower, narrower upper
    assert bound_narrowing_allowed(frm, to, strong_basis=None) is False
    assert bound_narrowing_allowed(frm, to, strong_basis=True) is True


# ---------------------------------------------------------------------------
# conservative_bound_of — absence contributes no positive bound (§5.3)
# ---------------------------------------------------------------------------


def test_bound_of_absence_only_is_unbounded() -> None:
    """(§5.3) Absence-only observations yield a fully unbounded (most conservative) bound."""
    obs = (observation(is_absence=True, asserted_bound=_b(10, 20)),)
    result = conservative_bound_of(obs)
    assert result.lower is None and result.upper is None


def test_bound_of_ignores_absence_in_union() -> None:
    """(§5.3) Adding an absence observation never narrows the positive union."""
    positive = (observation(asserted_bound=_b(10, 50)),)
    with_absence = positive + (observation(is_absence=True, asserted_bound=_b(20, 30)),)
    base = conservative_bound_of(positive)
    widened = conservative_bound_of(with_absence)
    assert widened.covers(base)
    # the absence's narrower (20,30) did not narrow the (10,50) positive envelope
    assert widened.lower == Decimal(10) and widened.upper == Decimal(50)
