"""MANDATED test-only seam cross-check: egress TrialClaims 6-scalar ↔ rlp (design #25 §3.5/§7).

egress (ADR-002-013) owns the ``QuorumCommitCertificate`` + ``TrialClaims`` boundary seal
(``egress/state.py:190-227`` / ``records.py:210-227``): it carries the restricted-live trial claim
group as an opaque optional scalar group and its ``is_complete()`` is a **thin all-present boundary
seal**. egress **explicitly defers the trial-content validation to RLP by name** (``state.py:196`` "the
actual trial-content validation is deferred to RLP (``tos.rlp``, not landed ...)"). rlp is the
**upstream content owner** — its ``TrialClaimGroup`` is field-set identical to egress ``TrialClaims``
(a **manually-transcribed regression anchor**, §0.4h — NOT an import) and its
``trial_claims_complete`` is **thicker** (AND-s the plan's exact-scope content). This file imports the
real egress model as a **test**; the import-closure test proves ``tos.egress`` is **absent** from the
rlp runtime closure (and a rlp → egress import would be a cycle since egress consumes rlp).

Regime tag: structural / coordinate predicate substrate only; RLP-EV-001 substrate; EV-L1-complete
claim forbidden.
"""

from __future__ import annotations

import tos.rlp as rlp
from tos.egress import TrialClaims as EgressTrialClaims
from tos.rlp import TrialClaimGroup, trial_claims_complete

from ._rlp_strategies import clean_plan, clean_scope


def test_egress_trial_claims_field_set_matches_rlp_anchor() -> None:
    """(§0.4b/§0.4h) egress TrialClaims 6-scalar == rlp TrialClaimGroup field set (design-time anchor).

    This is a **manually-transcribed regression anchor**, not an import: the two independently-authored
    field sets must stay identical (egress §11.1 line 308 / rlp §0.4b). A drift on either side breaks
    this assertion — the seam contract that lets a rlp-produced generation flow into the egress QCC.
    """
    assert set(EgressTrialClaims.model_fields) == set(TrialClaimGroup.model_fields)
    assert set(EgressTrialClaims.model_fields) == set(TrialClaimGroup.REQUIRED_SCALARS)


def test_egress_is_complete_is_thin_all_present() -> None:
    """(§0.4b/c) egress ``is_complete()`` is a thin all-present seal (every scalar concrete)."""
    complete = EgressTrialClaims(
        trial_policy_generation=1,
        trial_plan_generation=2,
        trial_run_generation=3,
        promotion_generation=4,
        remaining_envelope="env",
        abort_generation=5,
    )
    assert complete.is_complete() is True
    # any None scalar ⇒ the thin seal fails closed.
    partial = EgressTrialClaims(trial_policy_generation=1)
    assert partial.is_complete() is False


def test_rlp_trial_claims_complete_is_thicker_than_egress_is_complete() -> None:
    """(§0.4b/c) rlp trial_claims_complete demands the plan's exact scope on top of all-present.

    A fully-present 6-scalar group whose plan scope is NOT exact-complete passes the egress thin
    all-present seal but FAILS the rlp content-completeness — proving the two are different axes (the
    rebuttal to "rlp re-authors the egress seal").
    """
    complete_scalars = rlp.TrialClaimGroup(
        trial_policy_generation=1,
        trial_plan_generation=2,
        trial_run_generation=3,
        promotion_generation=4,
        remaining_envelope="env",
        abort_generation=5,
    )
    assert complete_scalars.is_complete() is True  # thin seal passes
    # plan with an incomplete scope (INELIGIBLE so it is constructable) — thin seal would pass, but
    # the thicker content check must fail.
    incomplete_plan = clean_plan(
        scope=clean_scope(broker=None),
        result=rlp.PlanResult.INELIGIBLE,
        pre_registered=False,
        independently_reviewed=False,
    )
    assert trial_claims_complete(complete_scalars, incomplete_plan) is False
    # a genuinely exact plan + complete scalars ⇒ the thicker check passes.
    assert trial_claims_complete(complete_scalars, clean_plan()) is True


def test_rlp_reauthors_no_egress_quorum_commit_certificate() -> None:
    """(§0.4c / §3.4) rlp re-authors NO egress QuorumCommitCertificate (a cycle + boundary re-author)."""
    assert not hasattr(rlp, "QuorumCommitCertificate")
    assert not hasattr(
        rlp, "TrialClaims"
    )  # rlp names its own TrialClaimGroup, not egress's
