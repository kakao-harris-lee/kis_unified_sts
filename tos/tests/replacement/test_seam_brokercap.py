"""MANDATED test-only seam cross-check: replacement <-> brokercap (design #18 §3.4(d)).

``tos.replacement`` does **not** import ``tos.brokercap`` at runtime (sibling edge 0). This
file imports **both** as a **test** to lock the injected broker-capability seams:

* **PR-EV-012 (§6.1 atomic replace scope)** — the five replace/amend semantics live in
  brokercap ``ReplaceSemantics`` (``vocabulary.py:202``, ADR-002-004 §8.8). §6.1 line 147:
  atomic replacement is available **only** when the active profile proves the exact
  semantics by executed evidence; line 149: a method name or a happy path is not proof;
  line 151: unproven ⇒ non-atomic. replacement therefore consumes an ``atomic_proven``
  bool and never inspects a profile;
* **PR-EV-006 (§10 sufficiency, the ``+Broker`` half)** — ``broker_capability_sufficient``
  (``predicates.py:206``) is one of the two producers of
  ``new_protection_sufficiency_current`` (the other being the evidence per-field proof,
  locked in ``test_seam_evidence``);
* **PR-EV-004 / 003** — ``fqp_adequate`` and ``same_order_retry_allowed`` are consumed
  coordinates; replacement re-authors neither.

Every one of these rows is minimum ``EV-L3+Broker`` or ``EV-L3/5``: **nothing is closed
here** (design #18 §1/§6.3).

A test-only cross-import is **not** a runtime package edge (design #18 §3.4(d)/§7.1).
"""

from __future__ import annotations

from tos.brokercap import (
    ReplaceSemantics,
    RequiredCapabilitySet,
    broker_capability_sufficient,
    rate_admission_ok,
    same_order_retry_allowed,
)
from tos.replacement import (
    REPLACE_SEMANTICS_ATOMIC_REPLACE,
    CancelFirstConditions,
    ReplacementMode,
    ReplacementOutcome,
    cancel_first_admission_gate,
    overlap_first_sequencing_valid,
    replacement_mode_admissible,
)

from ._replacement_strategies import (
    clean_conditions,
    clean_mode_inputs,
    clean_sequencing_inputs,
)

# ---------------------------------------------------------------------------
# PR-EV-012 — the five replace/amend semantics (ADR-002-004 §8.8)
# ---------------------------------------------------------------------------


def test_the_five_replace_amend_semantics_are_brokercap_owned_and_exactly_five() -> (
    None
):
    """(drift lock, ADR-002-004 §8.8 line 386-391) Five members, ``ATOMIC_REPLACE`` first."""
    assert {member.value for member in ReplaceSemantics} == {
        "ATOMIC_REPLACE",
        "CANCEL_THEN_NEW",
        "NEW_THEN_CANCEL",
        "BROKER_UNSPECIFIED",
        "UNSUPPORTED",
    }
    assert ReplaceSemantics.ATOMIC_REPLACE.value == REPLACE_SEMANTICS_ATOMIC_REPLACE


def test_replacement_does_not_re_author_the_replace_semantics_axis() -> None:
    """(§0.2) replacement's mode axis is a *workflow* axis, not a broker-semantics axis."""
    assert set(ReplacementMode).isdisjoint(set(ReplaceSemantics))
    # ``BROKER_PROVEN_ATOMIC`` (workflow mode) is not ``ATOMIC_REPLACE`` (broker semantics).
    assert ReplacementMode.BROKER_PROVEN_ATOMIC != ReplaceSemantics.ATOMIC_REPLACE


def test_only_a_proven_atomic_semantics_admits_the_atomic_mode() -> None:
    """(§6.1 line 147-151) Four of the five semantics are non-atomic; unproven ⇒ denied.

    The mapping from a profile's declared semantics to the injected ``atomic_proven`` bool
    is brokercap's and the runtime's; what this asserts is the *polarity* of the
    consumption — only a positively proven atomic semantics may admit the mode.
    """
    for semantics in ReplaceSemantics:
        atomic_proven = semantics is ReplaceSemantics.ATOMIC_REPLACE
        outcome = replacement_mode_admissible(
            ReplacementMode.BROKER_PROVEN_ATOMIC,
            **clean_mode_inputs(atomic_proven=atomic_proven),
        )
        if atomic_proven:
            assert outcome is ReplacementOutcome.REPLACEMENT_ADMISSIBLE
        else:
            assert outcome is ReplacementOutcome.REPLACEMENT_DENIED


def test_an_unspecified_or_unknown_semantics_is_non_atomic() -> None:
    """(§6.1 line 151) ``BROKER_UNSPECIFIED`` / an unknown proof ⇒ non-atomic."""
    for unproven in (None, False):
        assert (
            replacement_mode_admissible(
                ReplacementMode.BROKER_PROVEN_ATOMIC,
                **clean_mode_inputs(atomic_proven=unproven),
            )
            is ReplacementOutcome.REPLACEMENT_DENIED
        )


# ---------------------------------------------------------------------------
# PR-EV-006 — broker_capability_sufficient feeds the §10 sufficiency conjunct
# ---------------------------------------------------------------------------


def test_an_absent_broker_profile_yields_an_insufficient_capability() -> None:
    """(``predicates.py:206`` seam) No profile ⇒ ``False`` ⇒ the old cancel is blocked."""
    produced = broker_capability_sufficient(
        None, RequiredCapabilitySet(), version_current=None
    )
    assert produced is False
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(new_protection_sufficiency_current=produced)
        )
        is False
    )


def test_a_stale_profile_version_yields_an_insufficient_capability() -> None:
    """(seam polarity) An out-of-date capability profile cannot establish sufficiency."""
    produced = broker_capability_sufficient(
        None, RequiredCapabilitySet(), version_current=False
    )
    assert produced is False
    assert (
        overlap_first_sequencing_valid(
            **clean_sequencing_inputs(new_protection_sufficiency_current=produced)
        )
        is False
    )


# ---------------------------------------------------------------------------
# PR-EV-003 / 007 — idempotency + rate admission are consumed coordinates
# ---------------------------------------------------------------------------


def test_idempotency_is_brokercap_owned_and_unproven_by_default() -> None:
    """(§14 seam) A replacement retry needs positively proven broker idempotency."""
    assert (
        same_order_retry_allowed(None, idempotency_proven_for_identity_and_window=None)
        is False
    )
    assert (
        same_order_retry_allowed(None, idempotency_proven_for_identity_and_window=True)
        is False
    ), "no profile at all can never license a same-order retry"


def test_broker_resource_availability_feeds_cancel_first_condition_six() -> None:
    """(§6.3 line 172) "necessary broker session/route/rate-limit/order capacity".

    brokercap decides rate admission; replacement consumes the bool into its sixth
    precondition. An unproven rate admission denies the whole cancel-first gate.
    """
    unavailable = rate_admission_ok(None, None)
    assert unavailable is False
    denied = clean_conditions(broker_resources_available_or_accounted=unavailable)
    assert cancel_first_admission_gate(denied, leg_admissibility=True) is False

    available = rate_admission_ok(True, True)
    assert available is True
    admitted = clean_conditions(broker_resources_available_or_accounted=available)
    assert cancel_first_admission_gate(admitted, leg_admissibility=True) is True


def test_replacement_authors_no_broker_capability_judgment() -> None:
    """(broker-agnostic, §0.2) No profile / semantics / FQP judgment on the PR surface."""
    from tos import replacement as replacement_pkg

    for forbidden in (
        "broker_capability_sufficient",
        "capability_admissible",
        "ReplaceSemantics",
        "BrokerCapabilityProfile",
        "rate_admission_ok",
        "same_order_retry_allowed",
    ):
        assert not hasattr(replacement_pkg, forbidden)
    # ...and the cancel-first condition model names broker *resources* generically, never
    # a concrete broker (project memory ``tos-spec-broker-agnostic``).
    assert (
        "broker_resources_available_or_accounted" in CancelFirstConditions.model_fields
    )
