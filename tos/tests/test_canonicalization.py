"""Canonicalizer contract properties (design §3.4).

Splits the two grades the design fixes (M1 seam):

* (A) must-pass invariants 1-5 — hold for **any** conforming canonicalizer, so
  they regress unchanged when a production scheme replaces the provisional one.
  Verified across two injected digest algorithms to show algorithm-independence.
* (B) provisional-only property 6 — magnitude decimal normalization, bound to
  ``ev-l1-provisional-0`` only; it must **not** fold the distinct
  scale/unit/multiplier/sign safety fields (design §3.4, §9.2 item 4).
"""

from __future__ import annotations

import hashlib

import hypothesis.strategies as st
from hypothesis import given
from tos.capsule.canonicalization import (
    EV_L1_PROVISIONAL_VERSION,
    EVL1ProvisionalCanonicalizer,
    _encode,
)

from ._strategies import CANON_DICTS, MIXED_DICTS, TEXT

# Two schemes over the same canonical serialization but different injected digest
# algorithms — the (A) suite must hold for both (design §3.1 injection).
_SHA256 = EVL1ProvisionalCanonicalizer(digest_factory=hashlib.sha256)
_SHA512 = EVL1ProvisionalCanonicalizer(
    version="test-sha512", digest_factory=hashlib.sha512
)
_SCHEMES = (_SHA256, _SHA512)


# ---- (A1) determinism ------------------------------------------------------


@given(covered=CANON_DICTS)
def test_a1_deterministic(covered: dict) -> None:
    """Same covered content yields the same digest, for each algorithm."""
    for scheme in _SCHEMES:
        assert scheme.compute_digest(covered) == scheme.compute_digest(dict(covered))


# ---- (A2) mapping key-order independence -----------------------------------


@given(
    items=st.lists(
        st.tuples(TEXT.filter(bool), CANON_DICTS),
        min_size=0,
        max_size=5,
        unique_by=lambda kv: kv[0],
    )
)
def test_a2_key_order_independent(items: list) -> None:
    """Reordering mapping keys does not change the digest."""
    forward = dict(items)
    reverse = dict(reversed(items))
    for scheme in _SCHEMES:
        assert scheme.compute_digest(forward) == scheme.compute_digest(reverse)


# ---- (A3) covered sensitivity ----------------------------------------------


@given(covered=CANON_DICTS, extra_key=st.text(min_size=1, max_size=5))
def test_a3_covered_sensitive(covered: dict, extra_key: str) -> None:
    """Changing a covered field (adding a key) changes the digest."""
    if extra_key in covered:
        return
    mutated = {**covered, extra_key: "sentinel-value"}
    for scheme in _SCHEMES:
        assert scheme.compute_digest(covered) != scheme.compute_digest(mutated)


# ---- (A5) domain-limited injectivity ---------------------------------------


@given(left=CANON_DICTS, right=CANON_DICTS)
def test_a5_injective_on_string_domain(left: dict, right: dict) -> None:
    """Distinct (number-free) covered content produces distinct canonical forms."""
    if left == right:
        assert _encode(left) == _encode(right)
    else:
        assert _encode(left) != _encode(right)


@given(left=MIXED_DICTS, right=MIXED_DICTS)
def test_a5_injective_on_mixed_int_string_domain(left: dict, right: dict) -> None:
    """(MINOR-5) Injectivity holds over a mixed string+int domain.

    On this domain (ints + strings + nesting, no bool/float/None) Python equality
    coincides with canonical equality, so distinct content must not fold and equal
    content must — and digest equality must track canonical-form equality.
    """
    if left == right:
        assert _encode(left) == _encode(right)
        assert _SHA256.compute_digest(left) == _SHA256.compute_digest(right)
    else:
        assert _encode(left) != _encode(right)
        assert _SHA256.compute_digest(left) != _SHA256.compute_digest(right)


# ---- (B6) provisional magnitude normalization ------------------------------


@given(magnitude=st.integers(min_value=-10_000, max_value=10_000))
def test_b6_magnitude_normalized(magnitude: int) -> None:
    """int / float / trailing-zero decimals of equal magnitude fold together."""
    from decimal import Decimal

    as_int = {"m": magnitude}
    as_float = {"m": float(magnitude)}
    as_decimal = {"m": Decimal(f"{magnitude}.00")}
    d_int = _SHA256.compute_digest(as_int)
    assert d_int == _SHA256.compute_digest(as_float)
    assert d_int == _SHA256.compute_digest(as_decimal)


@given(a=st.integers(-1000, 1000), b=st.integers(-1000, 1000))
def test_b6_distinct_magnitudes_differ(a: int, b: int) -> None:
    """Different magnitudes still produce different digests."""
    if a == b:
        return
    assert _SHA256.compute_digest({"m": a}) != _SHA256.compute_digest({"m": b})


@given(unit_a=TEXT, unit_b=TEXT)
def test_b6_does_not_fold_unit_or_scale(unit_a: str, unit_b: str) -> None:
    """Magnitude normalization never folds the distinct unit/scale safety fields."""
    if unit_a == unit_b:
        return
    left = {"value": 1.0, "unit": unit_a}
    right = {"value": 1.0, "unit": unit_b}
    assert _SHA256.compute_digest(left) != _SHA256.compute_digest(right)
    # scale distinction preserved at equal magnitude, too
    assert _SHA256.compute_digest(
        {"value": 1.0, "scale": "1"}
    ) != _SHA256.compute_digest({"value": 1.0, "scale": "2"})


def test_provisional_version_label() -> None:
    """The default provisional scheme carries the non-production version label."""
    assert EVL1ProvisionalCanonicalizer().version == EV_L1_PROVISIONAL_VERSION
