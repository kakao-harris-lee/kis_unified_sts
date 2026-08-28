"""scope_exact_and_complete yolk 2 + the 21-dimension anchor drift property (design #26 §5.2/§7.2).

Both-ways canary + the §5.7 line 128 21-dimension ``ScopeDimension`` anchor drift (design #26 §0.4h /
appendix B). This is the cleanest L1 slice (pure ``EV-L1/3``); it closes NO WDR-EV.

Regime tag: scope predicate substrate only; WDR-EV-002 NOT_IMPLEMENTED (EV-L1/3); EV-L1-complete claim
forbidden.
"""

from __future__ import annotations

import tos.wdr as w

from ._wdr_strategies import (
    clean_closure,
    clean_request,
    clean_scope,
    construct_request,
)


def test_clean_request_exact_complete_scope_proceeds() -> None:
    """(§5.2 positive) A full-scope, non-drifted, closure-complete request ⇒ True."""
    assert w.scope_exact_and_complete(clean_request(), w.MANDATED_SCOPE_FLOOR) is True


def test_none_request_or_empty_mandate_denies() -> None:
    """(§5.2 ∅-seal both-ways) None request or empty mandated_scope ⇒ deny."""
    assert w.scope_exact_and_complete(None, w.MANDATED_SCOPE_FLOOR) is False
    assert w.scope_exact_and_complete(clean_request(), frozenset()) is False


def test_missing_dimension_is_incomplete() -> None:
    """(§5.2 set both-ways) A single missing (None) mandated dimension ⇒ incomplete ⇒ deny.

    The classification is left non-eligible so the §2.3 coexistence validator (which forbids an
    eligible + blank scope at construction) does not fire — this isolates the scope predicate.
    """
    partial = clean_scope(account=None)
    req = clean_request(scope=partial, non_waivable_classification=None)
    assert w.scope_exact_and_complete(req, w.MANDATED_SCOPE_FLOOR) is False


def test_wildcard_dimension_denies() -> None:
    """(§5.2 / §10 line 299) A wildcard scope coordinate ⇒ not concrete ⇒ deny."""
    for bad in ("*", "latest", "KOSPI*", "  ", "%"):
        req = clean_request(
            scope=clean_scope(instrument=bad), non_waivable_classification=None
        )
        assert w.scope_exact_and_complete(req, w.MANDATED_SCOPE_FLOOR) is False, bad


def test_scope_drift_flags_deny() -> None:
    """(§4.3 negative polarity) Any scope-drift flag True / None ⇒ deny."""
    for field in (
        "scope_wildcard",
        "scope_patched",
        "scope_widened",
        "scope_stale",
        "scope_conflicting",
    ):
        for bad in (True, None):
            req = clean_request(**{field: bad})
            assert w.scope_exact_and_complete(req, w.MANDATED_SCOPE_FLOOR) is False


def test_empty_or_incomplete_closure_denies() -> None:
    """(§5.10) An empty closure, or a closure without the positive completeness proof, ⇒ deny."""
    empty = clean_request(dependency_closure=clean_closure(components=()))
    assert w.scope_exact_and_complete(empty, w.MANDATED_SCOPE_FLOOR) is False
    for bad in (None, False):
        req = clean_request(dependency_closure=clean_closure(closure_complete=bad))
        assert w.scope_exact_and_complete(req, w.MANDATED_SCOPE_FLOOR) is False
    # an absent closure (explicit None) — built via model_construct since the clean builder's
    # None-sentinel substitutes the default closure.
    assert (
        w.scope_exact_and_complete(
            construct_request(dependency_closure=None), w.MANDATED_SCOPE_FLOOR
        )
        is False
    )


def test_materiality_unknown_or_unresolved_applicability_denies() -> None:
    """(§9 line 273) materiality_unknown True/None ⇒ deny; applicability_resolved None/False ⇒ deny."""
    for bad in (True, None):
        assert (
            w.scope_exact_and_complete(
                clean_request(materiality_unknown=bad), w.MANDATED_SCOPE_FLOOR
            )
            is False
        )
    for bad in (None, False):
        assert (
            w.scope_exact_and_complete(
                clean_request(applicability_resolved=bad), w.MANDATED_SCOPE_FLOOR
            )
            is False
        )


def test_caller_mandate_floored_to_full_catalogue() -> None:
    """(§5.2 floor) A caller passing a *smaller* mandate is floored up — a partial scope still denies."""
    single = frozenset({w.ScopeDimension.ACCOUNT})
    # a full-scope request still passes (the floor lifts the mandate to the full catalogue).
    assert w.scope_exact_and_complete(clean_request(), single) is True
    # but a request missing one dimension is denied even under the smaller caller mandate.
    partial = clean_request(
        scope=clean_scope(venue=None), non_waivable_classification=None
    )
    assert w.scope_exact_and_complete(partial, single) is False


def test_supporting_no_wildcard_and_no_drift() -> None:
    """(§5.2 supporting) no_wildcard_scope / no_scope_drift / dependency_closure_complete fail-closed."""
    assert w.no_wildcard_scope(None) is False
    assert w.no_wildcard_scope(clean_request()) is True
    assert (
        w.no_wildcard_scope(
            clean_request(
                scope=clean_scope(broker="*"), non_waivable_classification=None
            )
        )
        is False
    )
    assert w.no_scope_drift(None) is False
    assert w.no_scope_drift(clean_request()) is True
    assert w.no_scope_drift(clean_request(scope_stale=None)) is False
    assert w.dependency_closure_complete(None) is False
    assert w.dependency_closure_complete(clean_request()) is True


def test_twenty_one_dimension_anchor_drift() -> None:
    """(§7.2 drift / appendix B) ScopeDimension == DeviationScope fields == exactly 21 dimensions."""
    dims = {d.name.lower() for d in w.ScopeDimension}
    fields = set(w.DeviationScope.model_fields)
    assert dims == fields, f"drift: dims={dims} fields={fields}"
    assert len(list(w.ScopeDimension)) == 21
    assert frozenset(w.ScopeDimension) == w.MANDATED_SCOPE_FLOOR
