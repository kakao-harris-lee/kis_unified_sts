"""MANDATED test-only seam cross-check: hag effective-principal / quorum verdict ↔ wdr injection (§3.5/§7).

hag (ADR-002-015) owns the effective-principal collapse + quorum-independence counting. wdr **consumes
the hag verdict as an injected bool** — the ``effective_principal_verdict`` (decision) coordinate and
the ``independent_effective_person_approval`` predicate's verdict argument — and re-authors **none** of
the hag collapse / quorum logic (§0.4e; WDR-EV-004 is L2+). This file imports the real hag predicate as a
**test** to witness that ``quorum_independence_satisfied`` produces a plain ``bool`` that flows into
wdr's injected slot; the import-closure test proves ``tos.hag`` is **absent** from the wdr runtime
closure (edge 0), and wdr re-authors no hag collapse / quorum function.

Regime tag: structural / injected-verdict seam substrate only; WDR-EV-004 substrate; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import tos.wdr as wdr
from tos.hag import quorum_independence_satisfied


def test_hag_quorum_verdict_is_a_plain_bool_wdr_injects() -> None:
    """(§0.4e) hag quorum_independence_satisfied produces a bool verdict wdr consumes as injected.

    wdr's ``independent_effective_person_approval`` takes ``effective_principal_verdict: bool`` — the hag
    verdict — never a hag type. Here the real hag predicate produces a ``bool`` (fail-closed ``False`` on
    a degenerate empty / ``None`` quorum) and wdr consumes exactly that bool.
    """
    verdict = quorum_independence_satisfied([], None, None, frozenset())
    assert isinstance(verdict, bool)
    # a False hag verdict denies the independent-approval substrate (positive-polarity injection).
    assert (
        wdr.independent_effective_person_approval(
            wdr.AllFalseDeviationAuthority(), verdict, False
        )
        is False
    )
    # a True hag verdict + all-false authority + no common-mode ⇒ structural independence holds.
    assert (
        wdr.independent_effective_person_approval(
            wdr.AllFalseDeviationAuthority(), True, False
        )
        is True
    )


def test_wdr_effective_principal_verdict_slot_is_plain_bool() -> None:
    """(§0.4e) The decision's hag-injected verdict field is typed ``bool | None``, not a hag type."""
    annotation = wdr.SafetyDeviationDecision.model_fields[
        "effective_principal_verdict"
    ].annotation
    assert annotation == (bool | None)


def test_wdr_reauthors_no_hag_collapse_or_quorum() -> None:
    """(§0.4e / §3.4) wdr re-authors NO hag collapse / quorum (edge 0; a hag import is forbidden)."""
    assert not hasattr(wdr, "effective_principal_collapse")
    assert not hasattr(wdr, "quorum_independence_satisfied")
    assert not hasattr(wdr, "EffectivePrincipalGraph")
