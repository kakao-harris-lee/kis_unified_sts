"""boundary_denies_non_waivable yolk 1 + the 15-item anchor drift property (design #26 §5.1/§7.2).

Both-ways canary: "every condition met ⇒ True" and "each condition individually violated ⇒ False"
(single-directional seals are the #8 lesson). The 15-item ``NonWaivableBoundaryAnchor`` field set is a
**manually-transcribed regression anchor** of ADR §8 line 234-248 (design #26 §0.4h / appendix C); the
drift property asserts it, so an accidental add / drop is caught immediately.

Regime tag: boundary predicate substrate only; WDR-EV-001 NOT_IMPLEMENTED (EV-L1/3+Security);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import tos.wdr as w

from ._wdr_strategies import clean_boundary, clean_request, construct_request


def test_clean_request_outside_complete_boundary_proceeds() -> None:
    """(§5.1 positive) A waivable-eligible request against a complete unshrunk boundary ⇒ True."""
    assert w.boundary_denies_non_waivable(clean_request(), clean_boundary()) is True


def test_none_request_or_boundary_denies() -> None:
    """(§5.1 ∅-seal both-ways) A None request or None boundary is never vacuously permissive."""
    assert w.boundary_denies_non_waivable(None, clean_boundary()) is False
    assert w.boundary_denies_non_waivable(clean_request(), None) is False


def test_shrunk_boundary_is_forged_and_denies() -> None:
    """(§5.6 union-only) A boundary missing any of the 15 items is shrunk / forged ⇒ deny."""
    for item in w.NonWaivableBoundaryAnchor.BOUNDARY_ITEMS:
        shrunk = clean_boundary(**{item: False})
        assert w.boundary_denies_non_waivable(clean_request(), shrunk) is False, item


def test_non_waivable_or_unresolved_classification_denies() -> None:
    """(§8 line 252) NON_WAIVABLE / UNRESOLVED / a None classification ⇒ deny (only WAIVABLE_ELIGIBLE)."""
    for cls in (
        w.NonWaivableClassification.NON_WAIVABLE,
        w.NonWaivableClassification.UNRESOLVED,
        None,
    ):
        req = clean_request(non_waivable_classification=cls)
        assert w.boundary_denies_non_waivable(req, clean_boundary()) is False


def test_boundary_hit_denies() -> None:
    """(§8 line 234) A request that targets any §8 boundary item is denied (any hit ⇒ deny).

    A ``WAIVABLE_ELIGIBLE`` request with a boundary hit is unconstructable on the normal path (the
    §2.3 coexistence validator), so it is built via ``model_construct`` to exercise the predicate's
    defence-in-depth boundary-hit denial.
    """
    req = construct_request(boundary_hits=frozenset({"rfc_000_constitutional"}))
    assert w.boundary_denies_non_waivable(req, clean_boundary()) is False


def test_unresolved_applicability_denies() -> None:
    """(§9 line 273) None / False applicability_resolved ⇒ deny (positive polarity)."""
    for resolved in (None, False):
        req = clean_request(applicability_resolved=resolved)
        assert w.boundary_denies_non_waivable(req, clean_boundary()) is False


def test_unresolved_is_non_waivable_supporting() -> None:
    """(§8 line 252 supporting) Only WAIVABLE_ELIGIBLE is waivable; every other value ⇒ non-waivable."""
    assert (
        w.unresolved_is_non_waivable(w.NonWaivableClassification.WAIVABLE_ELIGIBLE)
        is False
    )
    for cls in (
        w.NonWaivableClassification.NON_WAIVABLE,
        w.NonWaivableClassification.UNRESOLVED,
        None,
    ):
        assert w.unresolved_is_non_waivable(cls) is True


def test_boundary_is_union_only_supporting() -> None:
    """(§5.6) The union-only supporting predicate: complete ⇒ True; any drop / None ⇒ False."""
    assert w.boundary_is_union_only(clean_boundary()) is True
    assert w.boundary_is_union_only(None) is False
    assert w.boundary_is_union_only(clean_boundary(rcl_exclusivity=False)) is False


def test_fifteen_item_anchor_drift() -> None:
    """(§7.2 drift / appendix C) BOUNDARY_ITEMS == the model's bool fields == exactly 15 items.

    A manually-transcribed regression anchor of ADR §8 line 234-248 — over-count (extra field) and
    under-count (dropped field) are both caught by the equality + the exact 15 count.
    """
    fields = set(w.NonWaivableBoundaryAnchor.model_fields)
    anchor = set(w.NonWaivableBoundaryAnchor.BOUNDARY_ITEMS)
    assert anchor == fields, f"drift: anchor={anchor} fields={fields}"
    assert len(w.NonWaivableBoundaryAnchor.BOUNDARY_ITEMS) == 15
