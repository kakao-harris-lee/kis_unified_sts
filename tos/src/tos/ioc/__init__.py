"""Intent-to-Order Conformance + Canonical Command Construction pure models + predicates (Phase 1, EV-L1).

**NOT Immediate-Or-Cancel** — ``tos.ioc`` is Intent-to-Order Conformance (ADR-002-020); the
``ioc`` token is a module path, never an order-type value (design #14 §0.4a).

Realizes the ADR-002-020 (Intent-to-Order Conformance, Canonical Command Construction, and
Economic-Effect Fencing — "IOC") part of IMPLEMENTATION-PLAN-002 §4 Phase 1 (EV-L1), per the
ratified design contract ``docs/plans/2026-07-25-tos-intent-order-conformance-design.md`` (v1.1).
It authors the **conformance-decision rules** — intent-to-command exact-match conformance, the
deterministic-compiler property, economic-effect capacity dominance, no-silent-widening,
post-proof mutation fence, derived-command lineage / no-blind-retry, protective-creates-nothing,
all-false authority separation, non-revival, and economic continuity — over a five-artifact
digest-bound data model plus the rcl ``CapacityVector`` ``EconomicEffectEnvelope``. It is a
**conformance-decision kernel, not a serializer / signer / egress engine** (design #14 §0.2): the
production canonical form / registry / numeric bounds are Phase-0 (§4 non-scope); every mapping /
bound / registry value is injected.

This package is **pure, non-transmitting, non-signing, and clock-free** (design #14 §0.2/§4.6):
frozen pydantic models over injected state + conservative fail-closed predicates. It **cannot**
transmit / serialize / sign / mutate capacity / issue authorization / approve — it produces a
canonical command, an economic-effect envelope, and a non-authorizing conformance proof; the
owning runtime (a future Order Construction Service / Broker Egress Gateway) enforces them. There
is no "assume-match" / "default / alias / substitute / coerce" path: ``CONFORMANT`` / ``True``
comes only from positive exact-match proof, everything else is ``NON_CONFORMANT`` / ``UNKNOWN`` /
``False`` (design #14 §4.1 — the structural seal against the #6 fail-open REJECT lesson).

**Truthy-sentinel structural seal (v1.1 M1):** :class:`~tos.ioc.vocabulary.ConformanceResult` is a
*truthy-untestable* ``StrEnum`` — ``__bool__`` raises ``TypeError`` — so a consumer's ``if result:``
misuse fails loud, not silently open on the truthy ``NON_CONFORMANT`` / ``UNKNOWN`` strings; the
mandated consume gate is ``result is ConformanceResult.CONFORMANT`` (design #14 §2.2(1)/§4.7).

It imports only ``pydantic`` + stdlib + ``tos.canonical`` (the digest substrate +
``IndependentIdArtifact`` + ``CanonicalDecimal`` + ``CanonicalizationScheme``) + ``tos.ordering``
(the Construction-Generation fence order) + the rcl :class:`~tos.rcl.CapacityVector` **type** for
``EconomicEffectEnvelope`` (the single ``ioc -> rcl`` sibling edge, design #14 §0.4c; rcl does not
import ioc, so the edge is acyclic — the #13 are -> rcl precedent). It imports **none** of the
other twelve siblings (``tos.are`` / ``tos.dsl`` / ``tos.capsule`` / ``tos.orthostate`` /
``tos.brokercap`` / ``tos.spg`` / ``tos.liveauth`` / ``tos.authority`` / ``tos.time`` /
``tos.evidence`` / ``tos.protective`` / ``tos.recon``) — the dsl proposal / are decision / capsule
/ orthostate / brokercap / venue / spg seams are all consumed / produced scalars / digests (design
#14 §3.4/§3.5 — those seam edges stay 0). Actively verified by the §7.1 import-closure test in
``tos/tests/ioc``. **PROMOTE 0건** — ``CanonicalDecimal`` is already core (design #9 §0.4c).

Identity is **independent, not** ``f(digest)`` (design #14 §3.1): each intent / envelope / policy /
command / proof generation is an immutable record; a legitimate recompilation is a new independent
id, a same-id / different-bytes re-issuance / contradictory command / proof is a detectable
``classify_record_pair`` ``CRITICAL_CONFLICT``.

**Completion discipline (design #14 §1):** ``IOC-EV-001..012`` — the six core rows (001-006) carry
an EV-L1 slice, the other six are EV-L2+, and even the six have ``/3`` / ``+Security`` / ``+Broker``
residue — Phase 1 authors the L1-decidable substrate and closes **no** IOC-EV item (authoring is
not evidence, VER-002-001 §5). Tag for any claim: "predicate / model substrate only;
IOC-EV-001..012 remain NOT_IMPLEMENTED pending EV-L2/L3 fault injection, adversarial, +Security,
and +Broker evidence; EV-L1-complete claim forbidden."

Public surface groups by module:

* :mod:`tos.ioc.vocabulary` — the conformance-axis StrEnums (incl. the truthy-untestable
  ``ConformanceResult``).
* :mod:`tos.ioc.records` — the five digest-bound artifacts + the rcl ``EconomicEffectEnvelope``
  alias + value / injected-input models + all-false authority effect.
* :mod:`tos.ioc.predicates` — the core §5 conformance / determinism / economic-fencing rules + the
  deterministic compiler + the predicate-only §6.1-§6.5 rules.
* :mod:`tos.ioc.state` — the temporal §6.6 non-revival / economic-continuity predicates + the §5.7
  generation fence (``tos.ordering`` REUSE).
"""

from __future__ import annotations

from tos.ioc._base import (
    AllFalseConstructionAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
    IndependentIdArtifact,
)
from tos.ioc.predicates import (
    canonicalization_deterministic,
    command_conforms,
    compile_command,
    compiler_deterministic,
    construction_grants_no_authority,
    derived_command_conformance,
    economic_effect_dominated,
    mutation_fence_holds,
    no_silent_widening,
    numerical_safety,
    protective_creates_nothing,
)
from tos.ioc.records import (
    ApprovedIntentContract,
    AuthorizedConstructionEnvelope,
    AxisBinding,
    CanonicalBrokerCommand,
    EconomicEffectEnvelope,
    MaterialCommandChange,
    OrderConformanceProof,
    OrderConstructionAuthorityEffect,
    OrderConstructionPolicy,
)
from tos.ioc.state import (
    construction_generation_fences,
    economic_effect_outlives,
    recovery_revives_nothing,
)
from tos.ioc.vocabulary import (
    ConformanceAxis,
    ConformanceResult,
    MutationClass,
    OrderTypeKind,
    PositionEffectKind,
    QuantityUnitKind,
)
from tos.ordering import Ordering, OrderingEvent, compare_order

__all__ = [
    # base (reused core + ioc-local all-false authority)
    "AllFalseConstructionAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    "IndependentIdArtifact",
    # ordering (reused core — Construction-Generation fence order)
    "Ordering",
    "OrderingEvent",
    "compare_order",
    # vocabulary
    "ConformanceResult",
    "ConformanceAxis",
    "PositionEffectKind",
    "OrderTypeKind",
    "QuantityUnitKind",
    "MutationClass",
    # records
    "ApprovedIntentContract",
    "AuthorizedConstructionEnvelope",
    "OrderConstructionPolicy",
    "CanonicalBrokerCommand",
    "OrderConformanceProof",
    "EconomicEffectEnvelope",
    "OrderConstructionAuthorityEffect",
    "AxisBinding",
    "MaterialCommandChange",
    # core §5 predicates
    "command_conforms",
    "compile_command",
    "compiler_deterministic",
    "numerical_safety",
    "economic_effect_dominated",
    "no_silent_widening",
    # predicate-only §6 predicates
    "canonicalization_deterministic",
    "mutation_fence_holds",
    "derived_command_conformance",
    "protective_creates_nothing",
    "construction_grants_no_authority",
    # temporal §6.6 / §5.7 predicates
    "recovery_revives_nothing",
    "economic_effect_outlives",
    "construction_generation_fences",
]
