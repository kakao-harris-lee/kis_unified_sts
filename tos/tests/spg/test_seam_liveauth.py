"""MANDATED test-only seam cross-check: spg <-> liveauth (design #12 §3.4).

spg does NOT import ``tos.liveauth`` at runtime (the import-closure test asserts its
absence); this file imports **both** as a **test** to lock the produced-value seam. liveauth
already declared the injected coordinates spg fills:

* ``hard_and_runtime_versions_match`` — one of the ten injected continuous-validity conditions
  (``liveauth/state.py:135``; ``_INJECTED_CONTINUOUS_CONDITIONS``). spg's
  :func:`~tos.spg.hard_and_runtime_versions_match` produces the ``bool`` it consumes; a
  ``False`` fails ``continuous_validity`` closed.
* ``hard_safety_envelope_not_expanded`` — a ``Safe053VariantAttestation`` control
  (``state.py:164``), filled by spg :func:`~tos.spg.envelope_not_expanded`.
* ``envelope_profile_covers_enlarged`` — an ``InPlaceExpansionInputs`` flag (``state.py:205``),
  filled by spg :func:`~tos.spg.envelope_profile_covers_enlarged`.
* the four :class:`~tos.spg.ActivationInputs` bools feed liveauth ``atomic_activation_ok``
  (``predicates.py:454``); spg's own ``activation_atomic`` folds the same four (dual-layer).

Causal isolation (MINOR-2): reusing liveauth's own ``valid_continuous_validity_inputs`` +
``issue_authorization`` builders, a fully-valid authorization + all ten conditions are held
fixed and **only** spg's produced ``hard_and_runtime_versions_match`` is flipped — so the
``False`` result is attributable to the injected condition, not an absent authorization. A
test-only cross-import of another test package's strategies is NOT a runtime package edge
(design #12 §3.4/§7.1).
"""

from __future__ import annotations

from decimal import Decimal

from tos.liveauth import (
    ContinuousValidityInputs,
    InPlaceExpansionInputs,
    Safe053VariantAttestation,
    atomic_activation_ok,
    continuous_validity,
)
from tos.liveauth.predicates import _INJECTED_CONTINUOUS_CONDITIONS
from tos.spg import (
    ActivationVerdict,
    activation_atomic,
    envelope_not_expanded,
    envelope_profile_covers_enlarged,
    hard_and_runtime_versions_match,
)

from ..liveauth._liveauth_strategies import (
    issue_authorization,
    valid_continuous_validity_inputs,
)
from ._spg_strategies import (
    committable_activation_inputs,
    envelope_dimension,
    issue_activation,
    issue_envelope,
    issue_profile,
    profile_dimension,
)

# ---------------------------------------------------------------------------
# hard_and_runtime_versions_match — signature integrity + causal isolation
# ---------------------------------------------------------------------------


def test_versions_match_is_a_continuous_condition() -> None:
    """(§3.4 signature integrity) liveauth declares hard_and_runtime_versions_match injected."""
    assert "hard_and_runtime_versions_match" in _INJECTED_CONTINUOUS_CONDITIONS
    assert "hard_and_runtime_versions_match" in ContinuousValidityInputs.model_fields


def test_spg_produces_plain_bool_versions_match() -> None:
    """spg emits a plain ``bool`` type-matching liveauth's ``bool | None`` injected condition."""
    produced = hard_and_runtime_versions_match(
        issue_envelope(),
        issue_profile(),
        issue_activation(),
        mixed_versions_present=False,
    )
    assert isinstance(produced, bool) and produced is True


def test_versions_match_causally_flips_continuous_validity() -> None:
    """(MINOR-2 causal isolation) Flipping ONLY spg's produced bool flips continuous_validity.

    A fully-valid authorization + all ten conditions are held fixed (reused from liveauth's
    own strategies); only spg's ``hard_and_runtime_versions_match`` differs — True from a
    matching-generation triple, False from a mismatched one.
    """
    auth = issue_authorization()  # fully-valid, ISSUED Live Authorization

    env = issue_envelope(envelope_generation=1)
    prof = issue_profile(target_envelope_generation=1, profile_generation=1)
    act = issue_activation(profile_generation=1)
    produced_true = hard_and_runtime_versions_match(
        env, prof, act, mixed_versions_present=False
    )
    # A mismatched activation generation => False.
    stale_act = issue_activation(activation_id="act-2", profile_generation=9)
    produced_false = hard_and_runtime_versions_match(
        env, prof, stale_act, mixed_versions_present=False
    )
    assert produced_true is True and produced_false is False

    valid_true = valid_continuous_validity_inputs(
        hard_and_runtime_versions_match=produced_true
    )
    valid_false = valid_continuous_validity_inputs(
        hard_and_runtime_versions_match=produced_false
    )
    assert continuous_validity(auth, valid_true) is True
    assert continuous_validity(auth, valid_false) is False


def test_mixed_versions_present_fails_versions_match_closed() -> None:
    """A mixed-generation flag (True) fails the produced bool closed => continuous_validity False."""
    produced = hard_and_runtime_versions_match(
        issue_envelope(),
        issue_profile(),
        issue_activation(),
        mixed_versions_present=True,
    )
    assert produced is False
    inputs = ContinuousValidityInputs(hard_and_runtime_versions_match=produced)
    assert continuous_validity(None, inputs) is False


# ---------------------------------------------------------------------------
# envelope_not_expanded -> Safe053VariantAttestation
# ---------------------------------------------------------------------------


def test_envelope_not_expanded_fills_safe053_control() -> None:
    """(§3.4) spg envelope_not_expanded fills the SAFE-053 hard_safety_envelope_not_expanded control."""
    assert "hard_safety_envelope_not_expanded" in Safe053VariantAttestation.model_fields
    old_env = issue_envelope(
        governed_dimensions=(envelope_dimension(envelope_max=Decimal("10")),)
    )
    new_env = issue_envelope(
        envelope_generation=2,
        governed_dimensions=(envelope_dimension(envelope_max=Decimal("100")),),
    )
    profile = issue_profile(
        governed_dimensions=(profile_dimension(profile_value=Decimal("5")),)
    )
    produced = envelope_not_expanded(old_env, new_env, profile)
    assert produced is True
    att = Safe053VariantAttestation(hard_safety_envelope_not_expanded=produced)
    assert att.hard_safety_envelope_not_expanded is True
    # Fail-closed side: a None input produces False.
    assert envelope_not_expanded(None, new_env, profile) is False


# ---------------------------------------------------------------------------
# envelope_profile_covers_enlarged -> InPlaceExpansionInputs
# ---------------------------------------------------------------------------


def test_covers_enlarged_fills_in_place_expansion_flag() -> None:
    """(§3.4) spg envelope_profile_covers_enlarged fills the InPlaceExpansionInputs flag."""
    assert "envelope_profile_covers_enlarged" in InPlaceExpansionInputs.model_fields
    env = issue_envelope(permitted_scope=("acct-1", "acct-2"))
    prof = issue_profile(scope=("acct-1", "acct-2"))
    produced = envelope_profile_covers_enlarged(
        env, prof, ("acct-2",), not_expanded=True
    )
    assert produced is True
    inputs = InPlaceExpansionInputs(envelope_profile_covers_enlarged=produced)
    assert inputs.envelope_profile_covers_enlarged is True
    # Fail-closed side: an unproven not_expanded => False.
    assert (
        envelope_profile_covers_enlarged(env, prof, ("acct-2",), not_expanded=None)
        is False
    )


# ---------------------------------------------------------------------------
# atomic activation — the 4 spg bools fold identically in both layers
# ---------------------------------------------------------------------------


def test_four_bools_fold_committable_in_both_layers() -> None:
    """spg activation_atomic COMMITTABLE <=> liveauth atomic_activation_ok True (dual-layer)."""
    inputs = committable_activation_inputs()
    assert activation_atomic(inputs) is ActivationVerdict.COMMITTABLE
    assert (
        atomic_activation_ok(
            version_fully_active=inputs.version_fully_active,
            mixed_versions_present=inputs.mixed_versions_present,
            units_compatible=inputs.units_compatible,
            envelope_bounded=inputs.envelope_bounded,
        )
        is True
    )


def test_four_bools_fold_denied_in_both_layers() -> None:
    """A mixed-generation flag => spg DENIED and liveauth atomic_activation_ok False (polarity)."""
    inputs = committable_activation_inputs(mixed_versions_present=True)
    assert activation_atomic(inputs) is ActivationVerdict.DENIED
    assert (
        atomic_activation_ok(
            version_fully_active=inputs.version_fully_active,
            mixed_versions_present=inputs.mixed_versions_present,
            units_compatible=inputs.units_compatible,
            envelope_bounded=inputs.envelope_bounded,
        )
        is False
    )
