"""MANDATED test-only seam cross-check: rcl CapacityVector ↔ rlp trial budget (design #25 §3.5/§0.4g).

rcl (ADR-002-002/012) owns the ``CapacityVector`` and ``within_limits`` (``rcl/vector.py`` /
``rcl/predicates.py``) — §7 "RCL only" mutates capacity. rlp's ``TrialBudget`` is an **upper request
envelope, NOT capacity** (§10 line 296 "Only RCL may commit capacity. Unused plan budget creates no
headroom"): it carries the ``credible_economic_effect_envelope`` as an **injected** rcl CapacityVector
coordinate and re-authors **no** capacity math — the worst-credible-effect computation is rcl +
+Broker (§3.5). This file imports the real rcl symbols as a **test**; the import-closure test proves
``tos.rcl`` is **absent** from the rlp runtime closure.

Regime tag: predicate substrate only; RLP-EV-002 NOT_IMPLEMENTED (``EV-L2/3+Broker``); EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import tos.rlp as rlp
from tos.rcl import CapacityVector, within_limits
from tos.rlp import TrialBudget, trial_budget_is_not_capacity


def test_rcl_owns_capacity_vector_and_within_limits() -> None:
    """(§0.4g / §3.5) The CapacityVector + within_limits live in rcl, not rlp."""
    assert CapacityVector is not None
    assert callable(within_limits)


def test_rlp_reauthors_no_capacity_vector() -> None:
    """(§0.4g / §3.4) rlp re-authors NO CapacityVector / within_limits (capacity is RCL-only)."""
    assert not hasattr(rlp, "CapacityVector")
    assert not hasattr(rlp, "within_limits")


def test_trial_budget_is_a_request_envelope_not_capacity() -> None:
    """(§0.4g / §10 line 296) The TrialBudget is a request envelope; capacity is a separate rcl vector.

    The budget carries the credible economic-effect envelope as an **injected** rcl CapacityVector
    coordinate (a ``str | None`` scalar here) — it holds no capacity-mutation coordinate, so unused
    budget creates no headroom (§10). The predicate affirms a present budget is not capacity.
    """
    budget = TrialBudget(
        max_action_count=None,
        duration_ms=None,
        credible_economic_effect_envelope="rcl-capacity-coord-1",
    )
    assert trial_budget_is_not_capacity(budget) is True
    # the envelope is an injected coordinate, not a re-authored capacity vector.
    assert budget.credible_economic_effect_envelope == "rcl-capacity-coord-1"
    # the budget model carries no capacity-mutation field (headroom cannot be created here).
    assert "commit_capacity" not in TrialBudget.model_fields
    assert "reserve" not in TrialBudget.model_fields
