"""Live Authorization vocabulary — lifecycle states + re-arm dual-control paths.

Spec terms = code terms (design §2; boundary design #1 §2.4). The enums are authored
verbatim from ADR-002-007 §8 (Live Authorization lifecycle) and §13 (dual-control
paths, with the SAFE-053 Governed Single-Operator Re-Arm Variant).

Pure module: stdlib only; no ``shared.*`` (design §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class LiveAuthorizationState(StrEnum):
    """The 10 Live Authorization lifecycle states (ADR-002-007 §8 line 228-240).

    An explicit lifecycle **separate from the trading operating mode** (§8 line 226) and
    a **distinct coordinate** from :class:`tos.canonical.ArtifactStatus` (DRAFT / ISSUED
    / SUPERSEDED / INVALIDATED) — the name collisions (``ISSUED`` / ``SUPERSEDED``) are
    two different axes and are never collapsed (design §2.2/§4.4 coordinate non-collapse;
    the ``LiveAuthorization`` record carries only immutable claims in its digest, never
    this mutable state). Progression: ``REQUESTED → VALIDATED → APPROVED → ISSUED →
    ACTIVE``; the terminal states (``DENIED`` / ``SUSPENDED`` / ``REVOKED`` / ``EXPIRED``
    / ``SUPERSEDED``) have no outgoing transition — in particular none returns to
    ``ACTIVE`` (§8.3 line 250-252 non-revival).
    """

    REQUESTED = "REQUESTED"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    DENIED = "DENIED"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"


class ReArmPathKind(StrEnum):
    """The two lawful dual-control re-arm paths (ADR-002-007 §13; RFC-001 SAFE-053).

    ``QUORUM`` is the two-distinct-effective-principals path (§13 line 428; the external
    Independent Reviewer configuration is a genuine second effective principal and so
    routes here, ADR-002-015 §17.1.4 line 487). ``GOVERNED_SINGLE_OPERATOR`` is the
    SAFE-053 Governed Single-Operator Re-Arm Variant (§13 line 429; ADR-002-015 §17.1),
    lawful **only** through its compensating controls — it has no second principal
    (design §6.3).
    """

    QUORUM = "QUORUM"
    GOVERNED_SINGLE_OPERATOR = "GOVERNED_SINGLE_OPERATOR"
