"""Time Health Snapshot artifact (time design §2.1, gap 1 + gap 6a).

ADR-002-008 §8 defines the snapshot in prose only (no dedicated template), so
this schema is a **project-side new authoring** (independent-review candidate,
time design §9.2 item 3). It subclasses :class:`tos.canonical.DigestBoundArtifact`
(digest verification REUSE) but its ``snapshot_id`` and ``generation`` are
**independent, service-assigned injected fields** — NOT ``f(digest)`` (time
design §0.4a). ADR §8 line 194 / §14.1 line 346-348 assign snapshot identity and
the TTS generation by the service, and §8 line 208 requires a consumer to
**reject** a snapshot whose declared generation / provenance is inconsistent with
its content. ``id = f(digest)`` would make that detection vacuous (same bytes =>
same id), exactly as design #4 kept ``evidence_record_id ⊥ canonical_digest``.
So ``IdDerivedArtifact`` (capsule-only, content-addressed) is NOT used; ``generation``
is excluded from the digest so a digest match alone cannot prove the generation
(design #4 §3.5 MINOR-2 mirror), letting a consumer's ``(snapshot_id, generation,
digest)`` binding detect generation drift.

Field field-name alignment with the inline SoT projection blocks (time design
§2.0): ``snapshot_id`` <-> ``trustworthy_time_snapshot_id``, ``generation`` <->
``time_health_generation``, ``wall_clock_observation`` <-> ``source_wall_time``,
``maximum_consumer_age_ms`` <-> ``maximum_age_ms``. capsule/evidence carry only
scalar references and never import this model (time design §0.3/§2.0).

``wall_clock_observation`` is Layer-1 *covered* (so tampering breaks the digest)
but is **audit-only**: no predicate reads it for expiry/freshness/ordering (time
design §2.1 invariant; §4.2 line 85). [TIME-AC-001; SAFE-035]

LOW-1 (v1.2, explicit decision): the design §2.1 Layer-0 integrity attestation
block (``integrity.source_signature_or_mac`` / ``integrity_key_id``) is **not**
carried as a field on this artifact in Phase-1 — that block (and its MAC/signature
verification) is deferred to the signature/evidence layer (time design §9.2 item
5). Phase-1 tamper-evidence is provided solely by the ``canonical_digest`` binding
(any covered-field mutation breaks the digest); the attestation field structure is
a follow-on if the operator wants it present-but-unverified now.

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` / ``tos.time`` only.
"""

from __future__ import annotations

from typing import ClassVar

from tos.canonical import DigestBoundArtifact
from tos.time.domains import HealthState, ReasonCode
from tos.time.elements import (
    Bounds,
    DiscontinuityStatus,
    EvaluatedMonotonicAnchor,
    ReferenceSource,
    SuspensionStatus,
    TimeAuthorityEffect,
    TimeContinuityIdentity,
)


class TimeHealthSnapshot(DigestBoundArtifact):
    """An immutable Time Health Snapshot (time design §2.1; ADR §8 line 190-206).

    Digest-verified (``canonical_digest == H_ver(canonicalize(Layer-1))``) with an
    **independent** service-assigned ``snapshot_id`` + monotonic ``generation``.
    Use :meth:`issue` (inherited) to compute the digest over the covered content
    while leaving ``snapshot_id``/``generation`` untouched (design #4 §3.2 path).

    numeric bound fields (``maximum_consumer_age_ms``, ``bounds.*``) are covered
    but **optional** (not required-covered): every Phase-1 profile bound is
    null/PROPOSED (time design §8), so requiring them would force every snapshot
    to DRAFT. Instead they are injected slots consumed fail-closed as UNKNOWN when
    null (time design §2.1); a null ``maximum_consumer_age_ms`` means a consumer
    cannot establish a max age and rejects the snapshot for permissive use (§8
    line 210). [SAFE-050]
    """

    _REQUIRED_COVERED: ClassVar[tuple[str, ...]] = (
        # Structural continuity / state / provenance / version fields only
        # (time design §2.1; §7 line 186; §8 line 194-204 "at least").
        "health_state",
        "time_continuity_identity.host_or_runtime_id",
        "time_continuity_identity.boot_id",
        "time_continuity_identity.process_id",
        "time_continuity_identity.monotonic_anchor_id",
        "time_continuity_identity.monotonic_anchor_value",
        "time_continuity_identity.tts_generation",
        "evaluated_monotonic_anchor.monotonic_anchor_id",
        "evaluated_monotonic_anchor.monotonic_anchor_value",
        "issuer_continuity_id",
        "issue_monotonic_value",
        "tz_db_version",
        "trading_calendar_version",
        "verification_profile_version",
        "safety_profile_version",
    )
    _COVERED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "health_state",
            "time_continuity_identity",
            "evaluated_monotonic_anchor",
            "wall_clock_observation",
            "reference_sources",
            "bounds",
            "suspension_status",
            "discontinuity_status",
            "tz_db_version",
            "trading_calendar_version",
            "issuer_continuity_id",
            "issue_monotonic_value",
            "maximum_consumer_age_ms",
            "verification_profile_version",
            "safety_profile_version",
            "reason_codes",
            "authority_effect",
        }
    )

    # ---- Layer-0 identity/meta (independent; excluded from the digest, §2.1) ---
    # canonical_digest / status / canonicalization_version inherited.
    #: Service-assigned, independent (NOT f(digest)) — SoT trustworthy_time_snapshot_id.
    snapshot_id: str | None = None
    #: TTS monotonic generation counter, independent + excluded from digest
    #: (design #4 §3.5 MINOR-2 mirror) — SoT time_health_generation.
    generation: int | None = None

    # ---- Layer-1 covered content (ADR §8 line 194-206) ----
    health_state: HealthState = HealthState.UNINITIALIZED
    time_continuity_identity: TimeContinuityIdentity = TimeContinuityIdentity()
    evaluated_monotonic_anchor: EvaluatedMonotonicAnchor = EvaluatedMonotonicAnchor()
    #: Audit-only; NO predicate reads it for expiry/freshness/ordering (§2.1
    #: invariant) — SoT source_wall_time.
    wall_clock_observation: int | None = None
    reference_sources: tuple[ReferenceSource, ...] = ()
    bounds: Bounds = Bounds()
    suspension_status: SuspensionStatus = SuspensionStatus()
    discontinuity_status: DiscontinuityStatus = DiscontinuityStatus()
    tz_db_version: str | None = None
    trading_calendar_version: str | None = None
    issuer_continuity_id: str | None = None
    issue_monotonic_value: int | None = None
    #: SoT maximum_age_ms; null => consumer cannot establish max age => reject for
    #: permissive use (fail-closed, §8 line 210).
    maximum_consumer_age_ms: int | None = None
    verification_profile_version: str | None = None
    safety_profile_version: str | None = None
    reason_codes: tuple[ReasonCode, ...] = ()
    authority_effect: TimeAuthorityEffect = TimeAuthorityEffect()
