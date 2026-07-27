"""Failure-Domain Isolation coordinate vocabulary + predicate substrate (Phase 1, EV-L1).

Realizes the ADR-002-009 (Failure-Domain Isolation and Deployment Safety) part of
IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the ratified design contract
``docs/plans/2026-07-27-tos-failure-domain-design.md`` (v1.1).

**This is the thinnest package in the series, and that is the answer, not a shortfall.**
ADR-002-009 declares "Depends On: ADR-002-001 through ADR-002-008" and is an **integration /
ownership-partition layer**: nearly every L1-decidable proposition it states is *by construction*
already owned by a sibling. The design #27 §3.5 ownership table attributes each one to its real
owner with a measured code citation and forbids re-authoring (DRY, CLAUDE.md), and this package
authors only the residue no sibling owns:

* the **coordinate vocabulary** — :class:`~tos.failuredomain.vocabulary.FailureDomainKind` (22 =
  ADR §4.1 18 + the RFC-002 §24.1 supply-chain floor 4),
  :class:`~tos.failuredomain.vocabulary.FailureBehaviorKind` (9),
  :class:`~tos.failuredomain.vocabulary.IsolationClaimStatus` (3),
  :class:`~tos.failuredomain.vocabulary.IsolationKind` (3, a genuine original — negative-grep
  confirmed no sibling owned it), plus the
  :class:`~tos.failuredomain.vocabulary.ExplicitlyAnalyzedEmpty` ``∅`` marker and the
  :class:`~tos.failuredomain.state.SafetyCellScope` seven-scope coordinate (ADR §4.3);
* the **document-level** record shapes
  :class:`~tos.failuredomain.records.FailureDomainAllocationEntry` (ADR §5 eleven fields +
  ``isolation_kind``) and :class:`~tos.failuredomain.records.IsolationClaim` (ADR §4.4 five
  fields), both plain frozen — **not** digest-bound (Q1);
* **exactly three** domain-agnostic predicates —
  :func:`~tos.failuredomain.predicates.unproven_isolation_is_common_mode`,
  :func:`~tos.failuredomain.predicates.new_risk_blocked_by_unproven_isolation`,
  :func:`~tos.failuredomain.predicates.decision_sole_sourced_from_volatile` — the §1 core
  principles that generalize to no sibling's domain-specific instance.

``safety_cell`` and ``failure_domain`` **scalars are already sibling coordinates** and are
referenced, never redefined; the six sibling hard-fence owners, spg's whole deployment / rollback
fencing surface, sbr's recovery-isolation proof, time's ``common_mode_group``, cur's currentness
mechanism, and rcl's aggregate serialization are **re-authored not at all** (design #27 §3.5).

This package is **pure, non-transmitting, clock-free and number-free** (design #27 §0.2): frozen
pydantic models over injected coordinates plus conservative fail-closed predicates. It grants no
authority, releases no capacity, transmits nothing, proves no isolation, and enforces no
containment — the §2.2 all-false authority block makes any such flag unconstructable. Every
blast-radius / broker-session / partition / detection / containment bound is an **injected slot**;
the two real VP-002 keys ``B_failure_domain_detect`` (line 611) and ``B_failure_domain_contain``
(line 618) both still hold ``null`` and their approval is a Phase-0 human gate — **no new VP key
is authored and no number is hardcoded** (design #27 §7, CLAUDE.md configuration-driven).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (``FrozenModel`` /
``ArtifactIntegrityError`` — **PROMOTE 0**) — no ``numpy`` / ``pandas`` / ``yaml``, no
``shared.*``, **no ``tos.ordering``** (a matrix row carries no causal append-only order), and
**none of its siblings**: ``tos.failuredomain`` holds **sibling edge 0** (design #27 §0.3/§3.1).
Sibling coordinates enter as **injected owner tokens** (bare strings — see
:data:`~tos.failuredomain.vocabulary.SIBLING_OWNER_TOKENS`), and the §6.2 drift-lock seam test
resolves every one of them against the real sibling in a **test-only** import. Actively verified
by the §6.1 import-closure test in ``tos/tests/failuredomain``.

**Completion discipline (design #27 §1) — zero-closure.** ``EVIDENCE-REGISTER-002.csv`` lines
101-112 record ``FD-EV-001..012`` as all ``Critical`` / ``NOT_IMPLEMENTED`` with a minimum level
of **EV-L3 or higher** (5 rows ``EV-L3``, 6 rows ``EV-L3+Security``, 1 row ``EV-L3/5``) — **not
one row has an EV-L1 slice**. Phase 1 therefore closes **no** FD-EV item at all, and
VER-002-001 line 175 forbids substituting downward ("A lower level cannot substitute for a
required higher level"). Tag for any claim: "**EV-L1 predicate substrate only; FD-EV-001..012
remain NOT_IMPLEMENTED pending EV-L3(+Security) fault injection; the L1-decidable content is
sibling-owned per design #27 §3.5; EV-L1-complete claim forbidden.**" ADR-002-009 stays
**Proposed** — its §22 line 513 is explicit that "Authorship of this ADR does not satisfy these
conditions and does not authorize restricted-live or production operation", and the same holds
for this package.
"""

from __future__ import annotations

from tos.failuredomain._base import (
    AllFalseFailureDomainAuthority,
    ArtifactIntegrityError,
    FrozenModel,
)
from tos.failuredomain.predicates import (
    decision_sole_sourced_from_volatile,
    new_risk_blocked_by_unproven_isolation,
    unproven_isolation_is_common_mode,
)
from tos.failuredomain.records import (
    FailureDomainAllocationEntry,
    FailureDomainAuthorityEffect,
    IsolationClaim,
)
from tos.failuredomain.state import SafetyCellScope
from tos.failuredomain.vocabulary import (
    SIBLING_OWNER_TOKENS,
    ExplicitlyAnalyzedEmpty,
    FailureBehaviorKind,
    FailureDomainKind,
    IsolationClaimStatus,
    IsolationKind,
)

__all__ = [
    # base
    "AllFalseFailureDomainAuthority",
    "ArtifactIntegrityError",
    "FrozenModel",
    # vocabulary
    "SIBLING_OWNER_TOKENS",
    "ExplicitlyAnalyzedEmpty",
    "FailureBehaviorKind",
    "FailureDomainKind",
    "IsolationClaimStatus",
    "IsolationKind",
    # state (the ADR §4.3 coordinate)
    "SafetyCellScope",
    # records (document-level shapes)
    "FailureDomainAllocationEntry",
    "FailureDomainAuthorityEffect",
    "IsolationClaim",
    # predicates (exactly three — design #27 §3.4/§4)
    "decision_sole_sourced_from_volatile",
    "new_risk_blocked_by_unproven_isolation",
    "unproven_isolation_is_common_mode",
]
