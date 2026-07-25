"""MANDATED test-only seam cross-check: brokercap <-> liveauth (design #10 §3.4).

brokercap does NOT import ``tos.liveauth`` at runtime (the import-closure test asserts its
absence); this file imports **both** as a **test** to lock the produced-value seam. liveauth
already declared the injected coordinates brokercap fills:

* ``broker_capability_sufficient`` — one of the ten injected continuous-validity conditions
  (``liveauth/state.py:136``; ``_INJECTED_CONTINUOUS_CONDITIONS`` at
  ``liveauth/predicates.py:94``). brokercap's :func:`broker_capability_sufficient` produces
  the ``bool`` it consumes; a ``False`` fails ``continuous_validity`` closed.
* ``broker_capability_profile_version`` / ``broker_conformance_class`` — the scalar version /
  class references on the ``LiveAuthorization`` record (``records.py:124/125``), filled by
  :func:`active_profile_version` / :func:`active_conformance_class`.

Both directions are asserted with causal isolation (MINOR-2): reusing liveauth's own
``valid_continuous_validity_inputs`` + ``issue_authorization`` test builders, a fully-valid
authorization + all ten conditions are held fixed and **only** brokercap's produced
``broker_capability_sufficient`` is flipped — so the ``False`` result is attributable to the
injected condition, not to an absent authorization (recon/orthostate-seam-isomorphic). This
test is NOT a runtime package edge (design #10 §3.4/§7.1).
"""

from __future__ import annotations

from tos.brokercap import (
    CapabilityDimension,
    active_conformance_class,
    active_profile_version,
    broker_capability_sufficient,
)
from tos.liveauth import (
    ContinuousValidityInputs,
    LiveAuthorization,
    continuous_validity,
)
from tos.liveauth.predicates import _INJECTED_CONTINUOUS_CONDITIONS

from ..liveauth._liveauth_strategies import (
    issue_authorization,
    valid_continuous_validity_inputs,
)
from ._brokercap_strategies import issue_profile, required_set, verified_declaration

_OID = CapabilityDimension.ORDER_IDENTITY


def test_broker_capability_sufficient_is_a_continuous_condition() -> None:
    """(§3.4 signature integrity) liveauth declares broker_capability_sufficient as an injected condition."""
    assert "broker_capability_sufficient" in _INJECTED_CONTINUOUS_CONDITIONS
    assert "broker_capability_sufficient" in ContinuousValidityInputs.model_fields


def test_brokercap_false_fails_continuous_validity_closed() -> None:
    """brokercap broker_capability_sufficient False => continuous_validity False (fail-closed side)."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    # A required set the profile does NOT satisfy (undeclared dimension) => not sufficient.
    unmet = required_set(dimensions=frozenset({CapabilityDimension.CANCELLATION}))
    sufficient = broker_capability_sufficient(profile, unmet, version_current=True)
    assert sufficient is False
    # Wire the produced bool into liveauth's injected condition; a False there fails closed.
    inputs = ContinuousValidityInputs(broker_capability_sufficient=sufficient)
    assert continuous_validity(None, inputs) is False


def test_brokercap_sufficient_is_plain_bool_matching_injected_flag() -> None:
    """brokercap emits a plain ``bool`` (type-matches liveauth's ``bool | None`` injected condition)."""
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    sufficient = broker_capability_sufficient(
        profile, required_set(), version_current=True
    )
    assert isinstance(sufficient, bool)
    # It is accepted by the field and, alone, is not sufficient for full validity (egress etc.).
    inputs = ContinuousValidityInputs(broker_capability_sufficient=sufficient)
    assert continuous_validity(None, inputs) is False  # None authorization fails closed


def test_brokercap_sufficient_causally_flips_continuous_validity() -> None:
    """(MINOR-2 causal isolation) With a fully-valid authorization + all other inputs held fixed,
    flipping ONLY brokercap's produced ``broker_capability_sufficient`` flips continuous_validity.

    This isolates the seam's causal direction (recon/orthostate-seam-isomorphic): the ``False``
    result is attributable to the injected condition, not to an absent authorization. The
    fully-valid authorization + inputs are reused from liveauth's own test strategies
    (``valid_continuous_validity_inputs`` sets all ten conditions True; we override only the one
    brokercap produces). A test-only cross-import of another test package's strategies is NOT a
    runtime package edge (design #10 §7.1).
    """
    auth = issue_authorization()  # a fully-valid, ISSUED Live Authorization

    # brokercap produces True for a satisfied scope, False for an unmet one — same profile.
    profile = issue_profile(declarations=(verified_declaration(dimension=_OID),))
    produced_true = broker_capability_sufficient(
        profile, required_set(), version_current=True
    )
    produced_false = broker_capability_sufficient(
        profile,
        required_set(dimensions=frozenset({CapabilityDimension.CANCELLATION})),
        version_current=True,
    )
    assert produced_true is True and produced_false is False

    # All other continuous-validity inputs are identical; only the brokercap flag differs.
    valid_true = valid_continuous_validity_inputs(
        broker_capability_sufficient=produced_true
    )
    valid_false = valid_continuous_validity_inputs(
        broker_capability_sufficient=produced_false
    )
    # Baseline: the True wiring is genuinely continuously valid (the guard fires True).
    assert continuous_validity(auth, valid_true) is True
    # Flipping ONLY the brokercap-produced condition to False flips the result to invalid.
    assert continuous_validity(auth, valid_false) is False


def test_scalar_producers_match_authorization_record_fields() -> None:
    """(§3.4 MINOR-2) active_profile_version / active_conformance_class fill the scalar record fields."""
    profile = issue_profile()
    version = active_profile_version(profile)
    conformance = active_conformance_class(profile)
    assert isinstance(version, str) and isinstance(conformance, str)
    # The LiveAuthorization record declares both as scalar ``str | None`` fields.
    assert "broker_capability_profile_version" in LiveAuthorization.model_fields
    assert "broker_conformance_class" in LiveAuthorization.model_fields
    auth = LiveAuthorization(
        broker_capability_profile_version=version,
        broker_conformance_class=conformance,
    )
    assert auth.broker_capability_profile_version == version
    assert auth.broker_conformance_class == conformance
