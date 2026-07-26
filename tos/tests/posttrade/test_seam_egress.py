"""Seam: ``tos.posttrade`` <-> ``tos.egress`` — non-transmission by structural absence.

ADR-002-030 §1 line 31 / PTF-INV-016 verbatim: "PTOL, reconciliation, statement, evidence,
dashboard, recovery, and operator identities **SHALL NOT hold a usable external-economic
credential and route**." §25.10 rejects "operations may directly send instructions".

The realization is **structural absence**, not a refusing branch: this package has no
credential field, no route field, no send method, and no transmission predicate. There is
nothing to bypass because there is nothing to hold. The one boolean that *names* the act —
``AllFalsePostTradeConsequence.authorizes_transmission`` — is forced ``False`` at
construction and re-checked in depth, but the enforcement is the absence.

egress (ADR-002-013) owns the final egress boundary, the credential / route disjointness, and
the commit-proof validity; this package produces obligation decisions that a future runtime
feeds *into* that boundary.

Locks **2** of the 19 injected tokens: ``EgressAdmission.ADMIT``,
``CommitProofValidity.VALID``. Test-only sibling imports are not runtime package edges.
"""

from __future__ import annotations

import inspect

import pytest
import tos.posttrade.predicates as posttrade_predicates
import tos.posttrade.records as posttrade_records
import tos.posttrade.state as posttrade_state
import tos.posttrade.vocabulary as posttrade_vocabulary
from tos.posttrade import (
    COMMIT_PROOF_VALIDITY_VALID,
    EGRESS_ADMISSION_ADMIT,
    AllFalsePostTradeConsequence,
    PostTradeDisposition,
    post_trade_consequence_all_false,
    post_trade_disposition,
)

from ._posttrade_strategies import (
    clean_break_record,
    clean_disposition_kwargs,
    clean_finality_proof,
    clean_obligation_record,
    clean_statement_manifest,
)

_MODULES = (
    posttrade_predicates,
    posttrade_records,
    posttrade_state,
    posttrade_vocabulary,
)


def test_egress_admission_token_drift_lock() -> None:
    """(token 15 of 19) egress ``EgressAdmission.ADMIT``."""
    from tos.egress import EgressAdmission

    assert EgressAdmission.ADMIT.value == EGRESS_ADMISSION_ADMIT


def test_commit_proof_validity_token_drift_lock() -> None:
    """(token 16 of 19) egress ``CommitProofValidity.VALID``."""
    from tos.egress import CommitProofValidity

    assert CommitProofValidity.VALID.value == COMMIT_PROOF_VALIDITY_VALID


def test_egress_owns_the_credential_route_disjointness() -> None:
    """(§1 line 31) The rule has an owner, and it is not this package."""
    from tos.egress import credential_route_authority_disjoint

    assert callable(credential_route_authority_disjoint)


def test_no_credential_route_or_send_exists_anywhere_in_this_package() -> None:
    """(PTF-INV-016) Structural absence across **all four** modules.

    Not "a send that refuses", but no send at all — and no credential and no route for one to
    use.

    A bare ``str`` constant is skipped: an injected sibling **token** (such as the egress
    ``ADMIT`` coordinate locked above) is a value this package *recognizes*, not a surface it
    exposes. A token cannot transmit anything; a callable or a model field could.
    """
    forbidden = (
        "credential",
        "credentials",
        "route",
        "routes",
        "send",
        "transmit",
        "submit",
        "dispatch",
        "instruct",
        "egress",
    )
    offenders: list[str] = []
    for module in _MODULES:
        for name in dir(module):
            if name.startswith("_"):
                continue
            if isinstance(getattr(module, name), str):
                continue  # an injected coordinate token, not an exposed surface
            lowered = name.lower()
            for token in forbidden:
                if lowered == token or lowered.startswith(f"{token}_"):
                    offenders.append(f"{module.__name__}.{name}")
    assert offenders == [], f"a transmission surface appeared: {offenders}"


def test_the_skipped_token_constants_really_are_only_tokens() -> None:
    """(both-ways) The ``str``-constant carve-out above cannot hide a callable surface.

    Every public ``str`` attribute in the vocabulary whose name mentions egress is asserted to
    be exactly the recognized coordinate value and nothing more.
    """
    egress_named = {
        name: getattr(posttrade_vocabulary, name)
        for name in dir(posttrade_vocabulary)
        if not name.startswith("_") and "EGRESS" in name.upper()
    }
    assert egress_named == {"EGRESS_ADMISSION_ADMIT": EGRESS_ADMISSION_ADMIT}
    assert isinstance(EGRESS_ADMISSION_ADMIT, str)
    assert not callable(EGRESS_ADMISSION_ADMIT)


@pytest.mark.parametrize(
    "artifact_builder",
    [
        clean_obligation_record,
        clean_finality_proof,
        clean_statement_manifest,
        clean_break_record,
    ],
)
def test_no_artifact_carries_a_credential_or_route_field(artifact_builder) -> None:
    """(PTF-INV-016) None of the four digest-bound citizens can hold one."""
    artifact = artifact_builder()
    fields = set(type(artifact).model_fields)
    for forbidden in (
        "credential",
        "route",
        "endpoint",
        "destination",
        "transport_target",
        "send_token",
    ):
        assert forbidden not in fields


def test_the_transmission_flag_is_unconstructable_as_true() -> None:
    """(§1 line 31) The one boolean that names the act cannot be set."""
    with pytest.raises(ValueError, match="authorizes_transmission must be false"):
        AllFalsePostTradeConsequence(authorizes_transmission=True)


def test_a_forged_transmission_flag_is_caught_by_the_re_check() -> None:
    """(defence in depth) ``model_construct`` skips the validator; the predicate does not."""
    forged = AllFalsePostTradeConsequence.model_construct(authorizes_transmission=True)
    assert post_trade_consequence_all_false(forged) is False


def test_even_an_admissible_disposition_authorizes_no_transmission() -> None:
    """(§4.7) A verdict is not a permission — the consuming egress runtime enforces."""
    verdict = post_trade_disposition(**clean_disposition_kwargs())
    assert verdict is PostTradeDisposition.POST_TRADE_ADMISSIBLE
    assert not hasattr(verdict, "send")
    signature = inspect.signature(post_trade_disposition)
    assert not any(
        "send" in name or "route" in name or "credential" in name
        for name in signature.parameters
    )
