"""MANDATED test-only seam cross-check: brokercap <-> orthostate (design #10 §3.4; v1.1 MAJOR-1).

brokercap does NOT import ``tos.orthostate`` at runtime (the import-closure test asserts its
absence); this file imports **both** as a **test** to lock two produced-value seams:

* **BROKER_ORDER (enum-basis, v1.1 MAJOR-1 correction).** The orthostate BROKER_ORDER
  dimension consumes not an injected ``bool | None`` but a
  ``basis: ConservatismBasis | TransitionCause | None`` at ``conservative_direction_ok``
  (``orthostate/predicates.py:302``). The caller maps brokercap's
  ``broker_evidence_admissible_under_profile`` bool to a basis: ``True`` ->
  ``ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE`` (a **strong** basis, not in
  ``WEAK_BASES``, that alone may reduce conservatism from ``UNKNOWN`` to a definite state);
  ``False`` / ``None`` -> ``None`` (weak / absent => the reduction is blocked, fail-closed —
  ``predicates.py:352-355``).
* **KnowledgeState -> RECONCILED (bool|None).** brokercap ``fqp_adequate`` produces the
  ``bool`` orthostate consumes as
  ``knowledge_transition_allowed(..., final_quantity_proof_where_broker_involved=...)``
  (``orthostate/predicates.py:503``).

This test is NOT a package edge (design #10 §3.4/§7.1).
"""

from __future__ import annotations

from tos.brokercap import (
    ProhibitedProof,
    broker_evidence_admissible_under_profile,
    fqp_adequate,
)
from tos.orthostate import (
    BrokerOrderState,
    ConservatismBasis,
    KnowledgeState,
    StateDimension,
    conservative_direction_ok,
    knowledge_transition_allowed,
)

from ._brokercap_strategies import (
    broker_evidence,
    complete_fqp_evidence,
    fqp_rule,
    issue_profile,
    required_set,
)


def _basis(admissible: bool) -> ConservatismBasis | None:
    """Caller mapping (design #10 §3.4): brokercap bool -> orthostate BROKER_ORDER basis."""
    return ConservatismBasis.BROKER_EVIDENCE_UNDER_PROFILE if admissible else None


# ---------------------------------------------------------------------------
# Seam (i): BROKER_ORDER enum-basis (UNKNOWN -> definite reduction)
# ---------------------------------------------------------------------------


def test_admissible_evidence_enables_broker_order_reduction() -> None:
    """brokercap admissible True -> BROKER_EVIDENCE_UNDER_PROFILE basis -> UNKNOWN->WORKING allowed."""
    profile = issue_profile()
    admissible = broker_evidence_admissible_under_profile(
        profile, broker_evidence(), required_set(), version_current=True
    )
    assert admissible is True
    # UNKNOWN (rank 6) -> WORKING (rank 2) is a REDUCTION in conservatism: needs a strong basis.
    assert (
        conservative_direction_ok(
            StateDimension.BROKER_ORDER,
            BrokerOrderState.UNKNOWN,
            BrokerOrderState.WORKING,
            _basis(admissible),
        )
        is True
    )


def test_inadmissible_evidence_blocks_broker_order_reduction() -> None:
    """brokercap admissible False -> None basis -> UNKNOWN->WORKING blocked (fail-closed)."""
    profile = issue_profile()
    # No evidence reference => not admissible.
    admissible = broker_evidence_admissible_under_profile(
        profile, None, required_set(), version_current=True
    )
    assert admissible is False
    assert (
        conservative_direction_ok(
            StateDimension.BROKER_ORDER,
            BrokerOrderState.UNKNOWN,
            BrokerOrderState.WORKING,
            _basis(admissible),
        )
        is False
    )


def test_non_current_version_blocks_broker_order_reduction() -> None:
    """A non-current version => not admissible => None basis => reduction blocked."""
    profile = issue_profile()
    admissible = broker_evidence_admissible_under_profile(
        profile, broker_evidence(), required_set(), version_current=None
    )
    assert admissible is False
    assert (
        conservative_direction_ok(
            StateDimension.BROKER_ORDER,
            BrokerOrderState.UNKNOWN,
            BrokerOrderState.WORKING,
            _basis(admissible),
        )
        is False
    )


# ---------------------------------------------------------------------------
# Seam (ii): FQP -> KnowledgeState RECONCILED (bool|None)
# ---------------------------------------------------------------------------


def test_fqp_adequate_enables_reconciled() -> None:
    """brokercap fqp_adequate True + corroboration => RECONCILING->RECONCILED allowed."""
    fqp = fqp_adequate(fqp_rule(), complete_fqp_evidence())
    assert fqp is True
    assert (
        knowledge_transition_allowed(
            KnowledgeState.RECONCILING,
            KnowledgeState.RECONCILED,
            corroboration=True,
            final_quantity_proof_where_broker_involved=fqp,
        )
        is True
    )


def test_fqp_inadequate_blocks_reconciled() -> None:
    """brokercap fqp_adequate False (position-match sole basis) => RECONCILED blocked."""
    fqp = fqp_adequate(
        fqp_rule(),
        complete_fqp_evidence(
            sole_prohibited_basis=ProhibitedProof.ACCOUNT_POSITION_MATCHING_EXPECTED_VALUE
        ),
    )
    assert fqp is False
    assert (
        knowledge_transition_allowed(
            KnowledgeState.RECONCILING,
            KnowledgeState.RECONCILED,
            corroboration=True,
            final_quantity_proof_where_broker_involved=fqp,
        )
        is False
    )


def test_produced_values_are_plain() -> None:
    """brokercap emits a plain ``bool`` (type-matches orthostate's ``bool | None`` FQP flag)."""
    assert isinstance(fqp_adequate(fqp_rule(), complete_fqp_evidence()), bool)
    assert isinstance(
        broker_evidence_admissible_under_profile(
            issue_profile(), broker_evidence(), required_set(), version_current=True
        ),
        bool,
    )
