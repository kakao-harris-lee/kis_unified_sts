"""Critical Input Observation element schema (design §2.2 — gap 1).

``CRITICAL-INPUT-SNAPSHOT-template.yaml:observations: []`` (line 27) leaves the
element schema empty. This module authors it from ADR-002-018 §5.2 (line
114-116) and §9 (line 249-272). Field groups follow the design §2.2 table
verbatim (spec term == code term, design §2.4).

Neutrality (design §0.3, §2.7 broker-agnostic): identity/mapping fields are
neutral scalars (``str``/``int``/``bool``); no ``shared.models`` trading types.
``trust_identity.credential_ref`` holds a *reference only*, never a secret
(design §2.2 no-secret invariant) — reinforced structurally by the firewall
excluding ``shared.config`` (-> ``shared.config.secrets``, §0.3 C1).

Pure module: ``pydantic`` + stdlib only.
"""

from __future__ import annotations

from enum import StrEnum

from tos.capsule._base import FrozenModel
from tos.capsule.field_state import FieldState


class AdmissionResult(StrEnum):
    """Admission outcome for one observation (ADR §9 line 263-272)."""

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class SourceIdentity(FrozenModel):
    """Where the observation came from (ADR §9 line 253)."""

    principal_id: str | None = None
    provider: str | None = None
    product_feed: str | None = None
    endpoint: str | None = None
    environment: str | None = None
    account_scope: str | None = None
    venue_scope: str | None = None


class TrustIdentity(FrozenModel):
    """Trust class + credential *reference* (ADR §9 line 254; no secrets)."""

    credential_ref: str | None = None
    trust_class: str | None = None


class Continuity(FrozenModel):
    """Source continuity facts (ADR §9 line 255, 272).

    ``continuity_gap`` defaults ``True``-safe semantics via the predicate layer:
    continuity is never *inferred* from TCP health, uptime, credential validity,
    identical payload, or cached sequence (ADR §9 line 272). An unestablished
    continuity is modelled with ``continuity_gap=True``.
    """

    source_continuity_id: str | None = None
    connection_session_id: str | None = None
    native_sequence: int | None = None
    native_revision: int | None = None
    page_cursor: str | None = None
    completeness_claim: str | None = None
    continuity_gap: bool = False


class RawRef(FrozenModel):
    """Raw-event reference (ADR §9 line 256)."""

    raw_event_id: str | None = None
    payload_digest: str | None = None


class ObservationTime(FrozenModel):
    """Time anchors and uncertainties (ADR §9 line 257).

    ``source_event_time`` is the as-of / production time that anchors the
    Validity Window (design §6.2, EXV-INV-002) — never the capsule wrap time.
    Times are neutral integer epoch-milliseconds.
    """

    source_event_time: int | None = None
    receipt_trustworthy_time_anchor: int | None = None
    source_time_uncertainty: int | None = None
    transport_uncertainty: int | None = None


class Semantics(FrozenModel):
    """Schema / semantic contract versions (ADR §9 line 258)."""

    schema_version: str | None = None
    semantic_contract_version: str | None = None


class Mapping(FrozenModel):
    """Instrument/venue/unit/scale/sign mapping (ADR §9 line 259).

    ``unit``, ``scale``, ``multiplier`` and ``sign`` are economically significant
    *distinct* safety fields (ADR §9 line 259, 268; §12 line 323): the design
    §3.4 magnitude normalization never folds them together. Kept as neutral
    scalars.
    """

    instrument: str | None = None
    contract: str | None = None
    venue: str | None = None
    account: str | None = None
    currency: str | None = None
    unit: str | None = None
    scale: str | None = None
    multiplier: str | None = None
    sign: str | None = None


class CorrectionLinks(FrozenModel):
    """Links to superseded/corrected records (ADR §9 line 260).

    A correction is a new immutable observation linked to prior records, not a
    destructive overwrite (design §4.5, ADR §17 line 415).
    """

    correction_of: str | None = None
    retraction_of: str | None = None
    supersedes: str | None = None
    predecessor_ids: tuple[str, ...] = ()


class IngestionGenerations(FrozenModel):
    """Software/parser/policy/deployment/evidence generations (ADR §9 line 261)."""

    software_gen: int | None = None
    parser_gen: int | None = None
    policy_gen: int | None = None
    deployment_gen: int | None = None
    evidence_gen: int | None = None


class Admission(FrozenModel):
    """Admission decision for the observation (ADR §9 line 263-272)."""

    result: AdmissionResult = AdmissionResult.UNCERTAIN
    reject_reasons: tuple[str, ...] = ()


class Observation(FrozenModel):
    """A single admitted-or-rejected critical-input observation (design §2.2).

    Frozen element of ``CriticalInputSnapshot.observations``. Groups mirror the
    design §2.2 table; ``field_state`` carries the five-valued evaluation
    (ADR §11 line 302).
    """

    source: SourceIdentity = SourceIdentity()
    trust_identity: TrustIdentity = TrustIdentity()
    continuity: Continuity = Continuity()
    raw: RawRef = RawRef()
    time: ObservationTime = ObservationTime()
    semantics: Semantics = Semantics()
    mapping: Mapping = Mapping()
    correction_links: CorrectionLinks = CorrectionLinks()
    ingestion_generations: IngestionGenerations = IngestionGenerations()
    admission: Admission = Admission()
    field_state: FieldState = FieldState.UNKNOWN
