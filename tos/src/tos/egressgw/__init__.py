"""Order Construction + Broker Egress Gateway — the D-E4 send boundary (Phase 1, provisional).

Realizes the send-boundary half of the vertical slice #1 contract
``docs/plans/2026-07-29-tos-egressgw-brokeradapter-design.md`` (design #34, v1.1, operator-
delegated auto-ratified 2026-07-29): the **owning runtime** for RFC-002 §10.8 (Broker Egress
Gateway), ADR-002-002 §11.1 step 2 / §11.4 steps 15-19 (Send Boundary), and RFC-005 §7 / §11 /
§12 (the approved-intent path, SAFE-021, and the eleven execution ``SHALL NOT``s).

Two modules, one package (design #34 §11.1 — a third package for Order Construction was
considered and rejected: the actual-outbound comparison is tightly coupled to the gateway's
``exact_binding_holds``, and a third seam is a fail-open surface, not a separation):

* :mod:`tos.egressgw.construction` — **Order Construction** (steps 2, 3, 5, 11). The G5
  quantity / price derivation: deterministic, bounded by a sizing rule *enclosed in the proposed
  Authorized Construction Envelope*, and repair-free. ioc ``compile_command`` then seals the
  result by declare-and-verify.
* :mod:`tos.egressgw.gateway` — the **Broker Egress Gateway** (steps 15-19): the RFC-002
  §10.8:741-759 17-item verify list, the broker-applicability positive gate, the single-use
  claim and ``SEND_STARTED`` ordering, delegation to an injected transport, and the result
  evidence.

⚠ **Provisional; closes no EV; authorizes nothing** (design #34 §1.1). Three facts bound the
honesty of everything here:

1. The slice's "send" is a **synthetic transport** (network 0), not a broker round-trip, so the
   ADR-002-013 §1 Final Egress Trust Boundary is never constituted and its invariants are never
   exercised.
2. **P0-2 is open** — there is no approved Broker Capability Profile INSTANCE
   (``broker_capability_profiles: []``), so every broker fact at this boundary is provisional.
3. The KIS draft profile carries **zero VERIFIED dimensions**, so brokercap
   ``capability_admissible`` is structurally ``PROHIBITED`` for every action class: this gateway
   **admits no live send**, by construction rather than by policy.

Of the seventeen verify items, six are verified by shipped predicates over structure and
coordinates (1, 2, 11, 13, 16, 17), five are non-authoritative provisional stand-ins (3, 6, 12,
14, 15), and six — the live safety-governance mesh (4, 5, 7, 8, 9, 10) — are deferred and gated
on broker-applicability. Tag for any claim: "send-boundary structural / coordinate wiring only;
no currentness, QCC, single-use, credential-isolation, or capacity acceptance; **no ADR
acceptance, restricted-live, or production is authorized**."

**``tos.egress`` is consumed, never encroached upon** (design #34 §0.3/§11-3): the ADR-002-013
QCC kernel's predicates are imported and called; no kernel file is modified and no kernel
behaviour is re-authored. The same holds for ioc, venue, cur, brokercap, rcl, and engine.

Import closure (design #34 §0.3, a strict subset allowlist)::

    {tos, tos.canonical, tos.ordering, tos.ioc, tos.venue, tos.cur, tos.egress,
     tos.brokercap, tos.rcl, tos.capsule, tos.evidence, tos.engine, tos.egressgw}

Of those, ``tos.capsule`` and ``tos.evidence`` are declared for a future evidence-sink edge and
are **imported by nothing today**; the §7.1 closure test therefore holds them out of the enforced
allowlist rather than exempting them from its own phantom-edge check, so each must be re-added at
the moment it is really consumed (anti-phantom — an unused declared edge is sealed as an absence,
not as an exemption).

``tos.brokeradapter`` is deliberately **outside** it: the transport arrives by injection through
the structural :class:`~tos.egressgw.gateway.SendTransport` port, exactly as D-E1 reaches this
gateway through its own ``Transmit`` port. Forbidden throughout: ``shared.*`` operational
packages, ``os.environ`` / ``getenv``, **network stdlib**, dynamic import / ``exec`` / ``eval``,
wall clock (``time`` / ``datetime``), and ``random`` / ``secrets`` / ``uuid`` — every identity on
this path is content-addressed or injected.
"""

from __future__ import annotations

from tos.egressgw._base import (
    CONSTRUCTION_SHALL_NOT_FLAGS,
    GATEWAY_SHALL_NOT_FLAGS,
    AllFalseConstructionCoordinatorAuthority,
    AllFalseGatewayAuthority,
    ArtifactIntegrityError,
    ArtifactStatus,
)
from tos.egressgw.construction import (
    DERIVATION_CONTEXT,
    DERIVATION_RULE,
    ConformanceProofStage,
    EconomicEffectStage,
    OrderConstructionStage,
    VenueConstraintStage,
    admitted_price_from_view,
    admitted_shape_price_from_view,
    build_order_conformance_proof,
    candidate_command_verdict,
    construct_candidate_command,
    derive_economic_effect_envelope,
    derive_order_size,
    fold_venue_admissibility,
)
from tos.egressgw.gateway import (
    OUTBOUND_COORDINATE_NAMES,
    UNCERTAIN_RESULT_KINDS,
    BrokerEgressGateway,
    GatewayEvidenceSink,
    NullGatewayEvidenceSink,
    RecordingGatewayEvidenceSink,
    SendAttemptLedger,
    SendTransport,
    outbound_binding_mismatch,
    outbound_coordinates,
    resolve_broker_applicability,
    verify_send_boundary,
)
from tos.egressgw.records import (
    DERIVED_AXES,
    AdmittedPriceObservation,
    CandidateConstruction,
    EffectDimensionSpec,
    GatewayEvidenceRecord,
    ProposedConstructionEnvelope,
    QuantityDerivation,
    SendBoundaryContext,
    SendBoundaryVerification,
    SizingBound,
    TransportNature,
    VenueQuantityConstraint,
    VerifyItemVerdict,
    positive_decimal,
    send_boundary_context,
)
from tos.egressgw.vocabulary import (
    ADMITTING_VERIFY_OUTCOMES,
    DEFERRED_ITEMS,
    PROVISIONAL_ITEMS,
    REALIZED_ITEMS,
    SEND_VERIFY_ITEMS,
    BrokerApplicability,
    DerivationOutcome,
    EffectBasis,
    LotRoundingPolicy,
    SendHaltReason,
    SendVerifyItem,
    VerifyDisposition,
    VerifyOutcome,
    verify_item_number,
)

__all__ = [
    # base
    "CONSTRUCTION_SHALL_NOT_FLAGS",
    "GATEWAY_SHALL_NOT_FLAGS",
    "AllFalseConstructionCoordinatorAuthority",
    "AllFalseGatewayAuthority",
    "ArtifactIntegrityError",
    "ArtifactStatus",
    # vocabulary
    "ADMITTING_VERIFY_OUTCOMES",
    "DEFERRED_ITEMS",
    "PROVISIONAL_ITEMS",
    "REALIZED_ITEMS",
    "SEND_VERIFY_ITEMS",
    "BrokerApplicability",
    "DerivationOutcome",
    "EffectBasis",
    "LotRoundingPolicy",
    "SendHaltReason",
    "SendVerifyItem",
    "VerifyDisposition",
    "VerifyOutcome",
    "verify_item_number",
    # records
    "DERIVED_AXES",
    "AdmittedPriceObservation",
    "CandidateConstruction",
    "EffectDimensionSpec",
    "GatewayEvidenceRecord",
    "ProposedConstructionEnvelope",
    "QuantityDerivation",
    "SendBoundaryContext",
    "SendBoundaryVerification",
    "SizingBound",
    "TransportNature",
    "VenueQuantityConstraint",
    "VerifyItemVerdict",
    "positive_decimal",
    "send_boundary_context",
    # construction (steps 2 / 3 / 5 / 11)
    "DERIVATION_CONTEXT",
    "DERIVATION_RULE",
    "ConformanceProofStage",
    "EconomicEffectStage",
    "OrderConstructionStage",
    "VenueConstraintStage",
    "admitted_price_from_view",
    "admitted_shape_price_from_view",
    "build_order_conformance_proof",
    "candidate_command_verdict",
    "construct_candidate_command",
    "derive_economic_effect_envelope",
    "derive_order_size",
    "fold_venue_admissibility",
    # gateway (steps 15-19)
    "OUTBOUND_COORDINATE_NAMES",
    "UNCERTAIN_RESULT_KINDS",
    "BrokerEgressGateway",
    "GatewayEvidenceSink",
    "NullGatewayEvidenceSink",
    "RecordingGatewayEvidenceSink",
    "SendAttemptLedger",
    "SendTransport",
    "outbound_binding_mismatch",
    "outbound_coordinates",
    "resolve_broker_applicability",
    "verify_send_boundary",
]
