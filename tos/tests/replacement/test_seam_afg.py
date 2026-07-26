"""MANDATED test-only seam cross-check: replacement <-> afg (design #18 §3.4(d)/§4.6).

``tos.replacement`` does **not** import ``tos.afg`` at runtime (sibling edge 0, asserted by
the §7.1 allowlist closure test). This file imports **both** as a **test** to lock the
three injected afg seams and their polarity.

The load-bearing content here is the **three-ADR ownership split** of the
cancel-ACK-is-not-a-Final-Quantity-Proof rule (design #18 §4.6):

* **afg owns the L1 predicate** — ``cancel_ack_not_final_quantity_proof``
  (``predicates.py:794``, AFG-EV-004 / AFG-INV-009). ADR-002-022 line 358 verbatim defers
  the coverage obligation *back* to this ADR: "The original order and any replacement
  remain covered for worst credible overlap, late fill, reversal, and protection gap
  **under ADR-002-002 and ADR-002-011**";
* **protective owns the arbiter application** — ``cancellation_admissible``'s §11.4
  no-optimistic-credit (locked in ``test_seam_protective``);
* **PR-EV-004 is the ``EV-L3+Broker`` integration coordinate** — proving that a broker
  really does send a late fill after a cancel ACK is broker integration, not an
  L1-decidable predicate. So ``tos.replacement`` authors **no** L1 predicate for it and
  **closes nothing**; it consumes the afg verdict and the orthostate coordinate.

A test-only cross-import is **not** a runtime package edge (design #18 §3.4(d)/§7.1).
"""

from __future__ import annotations

from tos.afg import (
    cancel_ack_not_final_quantity_proof,
    economic_effect_persists,
    no_blind_retry,
)
from tos.replacement import (
    ATTEMPT_STATE_SENT_UNCONFIRMED,
    BROKER_ORDER_STATE_CANCELLED,
    BROKER_ORDER_STATE_UNKNOWN,
    expiry_releases_no_economic_effect,
    overlap_first_sequencing_valid,
    replacement_authorization_current,
)

from ._replacement_strategies import clean_sequencing_inputs

# ---------------------------------------------------------------------------
# PR-EV-004 — cancel ACK is not a Final Quantity Proof (afg owns the L1 rule)
# ---------------------------------------------------------------------------


def test_the_l1_cancel_ack_rule_lives_in_afg_and_is_not_re_authored_here() -> None:
    """(§0.2 / §4.6) ``tos.replacement`` exposes **no** cancel-ACK / FQP L1 predicate.

    Re-authoring it would be authority duplication (the #8 lesson): the same prohibition
    would then have two implementations that could drift apart. The public surface is
    asserted to contain no such name.
    """
    from tos import replacement as replacement_pkg

    for forbidden in (
        "cancel_ack_not_final_quantity_proof",
        "fqp_adequate",
        "final_quantity_proof",
        "no_blind_retry",
        "oscillation_bounded",
    ):
        assert not hasattr(replacement_pkg, forbidden), (
            f"{forbidden} is re-authored in tos.replacement — design #18 §0.2 assigns "
            "the L1 rule to afg / brokercap and forbids duplication"
        )


def test_a_cancel_ack_without_a_final_quantity_proof_keeps_both_orders_covered() -> (
    None
):
    """(afg seam, §11 line 273) The old order stays in the worst-case executable set."""
    # A locally observed CANCELLED with no FQP and no coverage claim: the rule is violated.
    assert (
        cancel_ack_not_final_quantity_proof(
            BROKER_ORDER_STATE_CANCELLED,
            final_quantity_proof_present=False,
            original_and_replacement_covered=False,
            capacity_release_claimed=True,
        )
        is False
    )
    # Both orders positively covered for the worst credible overlap / late fill: it holds.
    assert (
        cancel_ack_not_final_quantity_proof(
            BROKER_ORDER_STATE_CANCELLED,
            final_quantity_proof_present=False,
            original_and_replacement_covered=True,
            capacity_release_claimed=False,
            replacement_reuse_claimed=False,
            retry_claimed=False,
        )
        is True
    )


def test_the_replacement_broker_order_tokens_match_the_afg_expectations() -> None:
    """(drift lock) The tokens replacement carries are the ones afg's predicate reads."""
    from tos.orthostate import BrokerOrderState

    assert BrokerOrderState.CANCELLED.value == BROKER_ORDER_STATE_CANCELLED
    assert BrokerOrderState.UNKNOWN.value == BROKER_ORDER_STATE_UNKNOWN
    # An UNKNOWN broker-order state can never satisfy the rule by itself.
    assert (
        cancel_ack_not_final_quantity_proof(
            None,
            final_quantity_proof_present=True,
            original_and_replacement_covered=True,
        )
        is False
    )


# ---------------------------------------------------------------------------
# PR-EV-003 — missing ACK / no blind retry (afg owns the L1 rule)
# ---------------------------------------------------------------------------


def test_a_missing_ack_leaves_the_attempt_potentially_live() -> None:  # noqa: D401
    """(afg seam, ADR §14) ``SENT_UNCONFIRMED`` is not proof of non-acceptance.

    A replacement retry after a missing ACK is admissible only on positively proven broker
    idempotency — which is brokercap's judgment, consumed through afg's L1 rule.
    """
    from tos.orthostate import TransmissionAttemptState

    assert (
        TransmissionAttemptState.SENT_UNCONFIRMED.value
        == ATTEMPT_STATE_SENT_UNCONFIRMED
    )
    assert (
        no_blind_retry(
            ATTEMPT_STATE_SENT_UNCONFIRMED,
            BROKER_ORDER_STATE_UNKNOWN,
            None,  # idempotency unproven
            1,
            complete_evidence_capability_coverage_authority=True,
            blind_failover_attempted=False,
        )
        is False
    )


# ---------------------------------------------------------------------------
# PR-EV-008 — economic_effect_persists (positive polarity, design #18 Q2)
# ---------------------------------------------------------------------------


def test_economic_effect_persists_is_true_until_a_final_quantity_proof_exists() -> None:
    """(afg ``state.py:545`` seam) Persistence is the default; only an FQP clears it."""
    assert (
        economic_effect_persists(
            final_quantity_proof_present=None,
            permit_expired=True,
            ack_missing=True,
        )
        is True
    )
    assert (
        economic_effect_persists(
            final_quantity_proof_present=False,
            decision_expired=True,
        )
        is True
    )
    assert (
        economic_effect_persists(
            final_quantity_proof_present=True,
        )
        is False
    )


def test_an_expiry_alone_never_releases_the_effect_across_the_seam() -> None:
    """(§7 line 203 seam) afg says the effect persists; replacement refuses the release."""
    persists = economic_effect_persists(
        final_quantity_proof_present=None,
        permit_expired=True,
        decision_expired=True,
        policy_or_retry_window_expired=True,
        queue_item_expired=True,
        cancel_ack_observed=True,
    )
    assert persists is True
    # (a) guard fires — a release claimed on the strength of the expiry is refused.
    assert (
        expiry_releases_no_economic_effect(
            expired=True,
            economic_effect_persists=persists,
            economic_effect_release_claimed=True,
        )
        is False
    )
    # (b) passing side — with a real Final Quantity Proof afg reports the effect gone,
    #     and only then is a release legitimate.
    gone = economic_effect_persists(final_quantity_proof_present=True)
    assert gone is False
    assert (
        expiry_releases_no_economic_effect(
            expired=True,
            economic_effect_persists=gone,
            economic_effect_release_claimed=True,
        )
        is True
    )


def test_authorization_currentness_consumes_the_afg_persistence_bool() -> None:
    """(design #18 Q2) ``economic_effect_persists`` is a **positive-polarity** conjunct."""
    persists = economic_effect_persists(final_quantity_proof_present=None)
    assert persists is True
    assert (
        replacement_authorization_current(
            material_change=False,
            expired=False,
            economic_effect_persists=persists,
        )
        is True
    )
    # Causal isolation: with the effect positively proven gone the authorization is no
    # longer "current" in the replacement sense — the workflow has moved past it.
    assert (
        replacement_authorization_current(
            material_change=False,
            expired=False,
            economic_effect_persists=economic_effect_persists(
                final_quantity_proof_present=True
            ),
        )
        is False
    )


def test_the_afg_cancel_ack_verdict_does_not_leak_into_the_sequencing_conjuncts() -> (
    None
):
    """(§4.6 ownership) PR-EV-004 is an L3+Broker coordinate, not a sequencing input.

    The four sequencing conjuncts are the §10 field proof, the aggregate-risk
    classification, the arbiter verdict, and the -019 leg admissibility. A cancel-ACK
    verdict — however positive — is **not** one of them and cannot substitute for any.
    """
    afg_rule_holds = cancel_ack_not_final_quantity_proof(
        BROKER_ORDER_STATE_CANCELLED,
        final_quantity_proof_present=False,
        original_and_replacement_covered=True,
        capacity_release_claimed=False,
        replacement_reuse_claimed=False,
        retry_claimed=False,
    )
    assert afg_rule_holds is True
    # It still cannot license the old cancel while the §10 field proof is unestablished.
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(new_protection_sufficiency_current=None)
        )
        is False
    )
