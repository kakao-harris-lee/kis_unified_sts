"""Convergence — unknown_stays_conservative + timeout_is_restrictive (design #17 §5.4; SBR-EV-006).

Regime tag: predicate / model substrate only; SBR-EV-006 NOT_IMPLEMENTED (`/3` residue);
EV-L1-complete claim forbidden.
"""

from __future__ import annotations

import hypothesis.strategies as st
from hypothesis import given
from tos.sbr import ObligationResult, timeout_is_restrictive, unknown_stays_conservative

# ---------------------------------------------------------------------------
# unknown_stays_conservative (§14 line 393; SBR-INV-006)
# ---------------------------------------------------------------------------


def test_all_terminal_satisfied_converges_positive_side() -> None:
    """(§5.4 positive) Every field terminal-SATISFIED with no drop => converged."""
    prior = {"f1": ObligationResult.UNKNOWN, "f2": ObligationResult.UNKNOWN}
    current = {"f1": ObligationResult.SATISFIED, "f2": ObligationResult.SATISFIED}
    assert unknown_stays_conservative(current, prior) is True


def test_repeated_identical_unknown_is_non_converged() -> None:
    """(§14 line 393) A repeated identical UNKNOWN never converts to known — non-converged."""
    prior = {"f1": ObligationResult.UNKNOWN}
    current = {"f1": ObligationResult.UNKNOWN}
    assert unknown_stays_conservative(current, prior) is False


def test_any_current_unknown_is_non_converged() -> None:
    """(§14 line 393) Any field still UNKNOWN (even newly) blocks convergence."""
    prior = {"f1": ObligationResult.SATISFIED}
    current = {"f1": ObligationResult.UNKNOWN}
    assert unknown_stays_conservative(current, prior) is False


def test_dropped_field_is_non_converged() -> None:
    """(§14 line 386) A previously-tracked field dropped from observation => non-converged."""
    prior = {"f1": ObligationResult.SATISFIED, "f2": ObligationResult.SATISFIED}
    current = {"f1": ObligationResult.SATISFIED}
    assert unknown_stays_conservative(current, prior) is False


def test_conflicted_field_is_not_treated_as_unknown_but_still_not_satisfied() -> None:
    """(fold, no-blend) A CONFLICTED field is not UNKNOWN, so convergence is not blocked here —
    it is blocked at obligation_graph_closed (only SATISFIED passes), never blended (§3.5).
    """
    prior = {"f1": ObligationResult.UNKNOWN}
    current = {"f1": ObligationResult.CONFLICTED}
    # unknown_stays_conservative only forbids a lingering UNKNOWN; the CONFLICTED result is
    # rejected by obligation_graph_closed downstream, never averaged into a pass.
    assert unknown_stays_conservative(current, prior) is True


# ---------------------------------------------------------------------------
# timeout_is_restrictive (§14/§19; SBR-INV-012)
# ---------------------------------------------------------------------------


def test_obligation_set_shrink_is_a_violation() -> None:
    """(SBR-INV-012) A shrunk obligation set (retry/timeout reduced it) => False (violation)."""
    assert timeout_is_restrictive(True, False, 5, 3) is False


def test_non_decreasing_obligation_set_holds() -> None:
    """(SBR-INV-012 positive) A non-decreasing obligation set holds the discipline."""
    assert timeout_is_restrictive(True, False, 5, 5) is True
    assert timeout_is_restrictive(True, False, 5, 7) is True


def test_none_size_fails_closed() -> None:
    """(∅) A None obligation-set size fails closed."""
    assert timeout_is_restrictive(True, False, None, 5) is False
    assert timeout_is_restrictive(True, False, 5, None) is False


def test_elapse_and_convergence_claim_never_relax_the_gate() -> None:
    """(§19 line 478) elapsed / converged are accepted-and-discarded — they never shrink the set."""
    # Regardless of elapsed/converged, only the size relation decides.
    for elapsed in (True, False, None):
        for converged in (True, False, None):
            assert timeout_is_restrictive(elapsed, converged, 4, 4) is True
            assert timeout_is_restrictive(elapsed, converged, 4, 2) is False


@given(
    before=st.integers(min_value=0, max_value=50),
    delta=st.integers(min_value=-10, max_value=10),
    elapsed=st.sampled_from([True, False, None]),
    converged=st.sampled_from([True, False, None]),
)
def test_property_timeout_iff_no_shrink(
    before: int, delta: int, elapsed: bool | None, converged: bool | None
) -> None:
    """(property) The verdict is exactly `size_after >= size_before` — never a timeout fallback."""
    after = before + delta
    expected = after >= before
    assert timeout_is_restrictive(elapsed, converged, before, after) is expected
