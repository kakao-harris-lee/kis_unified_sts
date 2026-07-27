"""MANDATED test-only seam cross-check: spg Hard Safety Envelope verdict ↔ wdr injection (§3.5/§7).

spg (ADR-002-014) owns the Hard Safety Envelope / ``profile_within_envelope`` / ``residual_risk_ceiling``
/ break-before-make. wdr **consumes the spg envelope-containment verdict as an injected bool** — the
``within_hard_safety_envelope`` (acceptance) / ``combined_within_envelope`` (active set) coordinates —
and re-authors **none** of the spg logic (§0.4c). This file imports the real spg predicate as a **test**
to witness that its verdict is a plain ``bool`` (``SemanticValidationResult.valid``) that flows into
wdr's injected slot; the import-closure test proves ``tos.spg`` is **absent** from the wdr runtime
closure (edge 0), and wdr re-authors no spg envelope type.

Regime tag: structural / injected-verdict seam substrate only; WDR-EV-012 substrate; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import tos.wdr as wdr
from tos.spg import SemanticValidationResult, profile_within_envelope

from ._wdr_strategies import clean_active_set


def test_spg_envelope_verdict_is_a_plain_bool_wdr_injects() -> None:
    """(§0.4c) spg profile_within_envelope produces a SemanticValidationResult.valid bool wdr consumes.

    wdr's ``combined_set_no_permissive_union`` takes ``member_within_envelope: bool`` — the spg verdict
    — never an spg type. Here the real spg predicate produces a ``.valid`` bool (fail-closed ``False`` on
    a ``None`` envelope / profile) and wdr consumes exactly that bool.
    """
    verdict = profile_within_envelope(None, None)
    assert isinstance(verdict, SemanticValidationResult)
    assert isinstance(verdict.valid, bool)
    # a False spg verdict denies the combined set (positive-polarity injection).
    aset = clean_active_set(member_decisions=("d1",))
    assert (
        wdr.combined_set_no_permissive_union(aset, frozenset({"d1"}), verdict.valid)
        is False
    )
    # a True spg verdict lets a complete, matching set pass.
    assert wdr.combined_set_no_permissive_union(aset, frozenset({"d1"}), True) is True


def test_wdr_within_hard_safety_envelope_slot_is_plain_bool() -> None:
    """(§0.4c) The acceptance's spg-injected verdict field is typed ``bool | None``, not an spg type."""
    annotation = wdr.ResidualRiskAcceptanceRecord.model_fields[
        "within_hard_safety_envelope"
    ].annotation
    assert annotation == (bool | None)


def test_wdr_reauthors_no_spg_envelope() -> None:
    """(§0.4c / §3.4) wdr re-authors NO spg envelope type (edge 0; an spg import is forbidden)."""
    assert not hasattr(wdr, "HardSafetyEnvelope")
    assert not hasattr(wdr, "profile_within_envelope")
    assert not hasattr(wdr, "residual_risk_ceiling")
