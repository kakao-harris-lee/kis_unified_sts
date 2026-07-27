"""Shared valid-artifact builders + strategies for the failuredomain property tests (design #27 §6).

Firewall-clean: imports only ``hypothesis`` and ``tos.failuredomain`` (design #27 §0.3). The
builders enforce the §6 clean-vs-illegal fixture discipline (the #8 lesson — a "clean" fixture
must be *genuinely* complete, never a permissive shortcut):

* a **clean** :class:`~tos.failuredomain.records.IsolationClaim` positively states **all five**
  ADR §4.4 fields with non-blank content, so a genuine ``ESTABLISHED`` is reachable rather than
  smuggled;
* a **clean** :class:`~tos.failuredomain.records.FailureDomainAllocationEntry` fills **all
  eleven** ADR §5 fields plus an explicit ``isolation_kind``, so a row is never "complete" by
  virtue of unset defaults;
* the **blank / ``∅`` strategies** deliberately generate ``None``, bare ``frozenset()``, and
  whitespace-only entries so the ``∅``-both-ways and blank-forgery seals are exercised on every
  claim field.

Nothing here is a *policy* number — this package is number-free by construction (design #27
§0.2): the real failure-domain bounds are Verification-Profile injected and both still ``null``
(``B_failure_domain_detect`` / ``B_failure_domain_contain``, design #27 §7).
"""

from __future__ import annotations

import hypothesis.strategies as st
from tos.failuredomain import (
    ExplicitlyAnalyzedEmpty,
    FailureBehaviorKind,
    FailureDomainAllocationEntry,
    FailureDomainKind,
    IsolationClaim,
    IsolationClaimStatus,
    IsolationKind,
    SafetyCellScope,
)

#: The ADR §4.4 five claim fields, in ADR line-90 order.
CLAIM_FIELDS: tuple[str, ...] = (
    "assumptions",
    "excluded_common_modes",
    "enforcement_mechanisms",
    "verification_cases",
    "residual_risk",
)

#: The ADR §5 line 116-132 eleven matrix fields, in ADR table order.
MATRIX_FIELDS: tuple[str, ...] = (
    "authority_or_state",
    "safety_cell",
    "failure_domains",
    "shared_dependencies",
    "failure_behavior",
    "unsafe_consequence",
    "prevention",
    "detection_and_containment",
    "recovery",
    "evidence",
    "residual_risk",
)

#: Blank-forgery texts: a bare ``""`` is falsy, ``" "`` / ``"\\t"`` / ``"\\n"`` are **truthy** —
#: the exact strings a ``if value:`` presence check would wrongly admit (design #27 §4.1).
BLANK_TEXTS: tuple[str, ...] = ("", " ", "\t", "\n", "   \t\n ")

#: Every ``∅``-shaped / absent value a claim collection field can take.
VOID_COLLECTIONS = st.sampled_from([None, frozenset()])

#: Status values that are **not** ``ESTABLISHED`` (every one must block).
NON_ESTABLISHED_STATUS = st.sampled_from(
    [IsolationClaimStatus.COMMON_MODE, IsolationClaimStatus.UNKNOWN, None]
)

#: Injected ``bool | None`` flag (the sibling tri-bool convention).
TRIBOOL = st.sampled_from([True, False, None])

#: A single taxonomy member.
DOMAIN_KIND = st.sampled_from(list(FailureDomainKind))

#: A (possibly empty) set of taxonomy members.
DOMAIN_SET = st.frozensets(DOMAIN_KIND, max_size=6)

#: A non-blank free-text token.
NON_BLANK_TEXT = st.text(min_size=1, max_size=24).filter(lambda s: s.strip() != "")

#: A non-empty set of non-blank tokens.
NON_BLANK_TOKENS = st.frozensets(NON_BLANK_TEXT, min_size=1, max_size=4)


def clean_claim(**overrides: object) -> IsolationClaim:
    """An IsolationClaim positively stating all five ADR §4.4 fields (genuinely complete).

    ``verification_cases`` carries the ``"sbr.IsolationFacts.all_proven"`` **reference token**
    (Q2, design #27 §9.4-1) — a bare string naming the owner of the executed recovery-isolation
    proof, never an imported sbr type.
    """
    kwargs: dict[str, object] = {
        "assumptions": frozenset(
            {"authority plane and egress plane fail independently"}
        ),
        "excluded_common_modes": frozenset({"shared credential", "shared clock"}),
        "enforcement_mechanisms": frozenset(
            {"egress.credential_route_authority_disjoint"}
        ),
        "verification_cases": frozenset({"sbr.IsolationFacts.all_proven"}),
        "residual_risk": "shared broker resource remains a common mode; owner: profile",
    }
    kwargs.update(overrides)
    return IsolationClaim(**kwargs)


def clean_cell(**overrides: object) -> SafetyCellScope:
    """A SafetyCellScope with all seven ADR §4.3 scopes explicitly bound."""
    kwargs: dict[str, object] = {
        field: f"cell-{field}" for field in SafetyCellScope.model_fields
    }
    kwargs.update(overrides)
    return SafetyCellScope(**kwargs)


def clean_entry(**overrides: object) -> FailureDomainAllocationEntry:
    """A matrix row with all eleven ADR §5 fields plus an explicit ``isolation_kind``.

    Every owner-ish field carries an **injected sibling owner token** (design #27 §3.2/§5) — the
    row *points at* the owner and re-authors nothing. No number appears anywhere.
    """
    kwargs: dict[str, object] = {
        "authority_or_state": "aggregate capacity commitment",
        "safety_cell": clean_cell(),
        "failure_domains": frozenset(
            {FailureDomainKind.CACHE, FailureDomainKind.EVENT_INFRASTRUCTURE}
        ),
        "shared_dependencies": frozenset({"one credential", "one clock"}),
        "failure_behavior": FailureBehaviorKind.STALE_SURVIVAL,
        "unsafe_consequence": "stale permission survives revocation",
        "prevention": "egress.credential_route_authority_disjoint",
        "detection_and_containment": "authoritative detection signal; bound injected",
        "recovery": "spg.rollback_requires_new_generation",
        "evidence": "FD-EV-004",
        "residual_risk": "shared broker resource; owner: deployment profile",
        "isolation_kind": IsolationKind.LOGICAL,
    }
    kwargs.update(overrides)
    return FailureDomainAllocationEntry(**kwargs)


#: A strategy over claims that are complete except for exactly one voided field.
def claim_missing_one_field(field: str, void_value: object) -> IsolationClaim:
    """A clean claim with exactly one of the five §4.4 fields voided."""
    return clean_claim(**{field: void_value})


__all__ = [
    "BLANK_TEXTS",
    "CLAIM_FIELDS",
    "DOMAIN_KIND",
    "DOMAIN_SET",
    "ExplicitlyAnalyzedEmpty",
    "MATRIX_FIELDS",
    "NON_BLANK_TEXT",
    "NON_BLANK_TOKENS",
    "NON_ESTABLISHED_STATUS",
    "TRIBOOL",
    "VOID_COLLECTIONS",
    "claim_missing_one_field",
    "clean_cell",
    "clean_claim",
    "clean_entry",
]
