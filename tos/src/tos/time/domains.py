"""Time domain + state enumerations (time design §2.3, §2.4, §2.5, §4).

Authored from ADR-002-008 prose. Every enum is broker-agnostic; no market hours,
broker name, or threshold is encoded here (time design §0/§4.7).

Pure module: stdlib only (no ``pydantic`` needed for the enums).
"""

from __future__ import annotations

from enum import StrEnum


class TimeDomain(StrEnum):
    """The 7 time domains that MUST NOT be collapsed (ADR §4 line 71-107).

    Held as distinct fields/types on the models so a disagreement between domains
    is preserved as evidence, never merged into one timestamp (§4 line 107).
    """

    #: §4.1 (75-79) — per-continuity elapsed; never compared across process/host.
    LOCAL_MONOTONIC = "LOCAL_MONOTONIC"
    #: §4.2 (81-85) — audit only; never a sole basis for expiry/freshness/ordering.
    LOCAL_WALL = "LOCAL_WALL"
    #: §4.3 (87-89) — corroborated reference time (source/path/quality/common-mode).
    REFERENCE = "REFERENCE"
    #: §4.4 (91-93) — source event time (identity/sequence/precision/uncertainty).
    SOURCE_EVENT = "SOURCE_EVENT"
    #: §4.5 (95-97) — broker/venue time; Broker-Capability-Profile restricted.
    BROKER_VENUE = "BROKER_VENUE"
    #: §4.6 (99-101) — authorization validity (holdover lease lifetime).
    AUTHORIZATION_VALIDITY = "AUTHORIZATION_VALIDITY"
    #: §4.7 (103-105) — trading session (tz/calendar/phase/boundary), broker-agnostic.
    TRADING_SESSION = "TRADING_SESSION"


class HealthState(StrEnum):
    """The 5 time-health states (ADR §6 line 134-145; §6.1-6.3).

    The evidence-based correction to the briefing's "7-state" note: ADR §6 has
    **5 states** and **7 directed transitions** (time design §2.4). No extra state
    is invented.
    """

    #: No trustworthy-time basis yet established.
    UNINITIALIZED = "UNINITIALIZED"
    #: Acquiring/validating reference synchronization.
    SYNCHRONIZING = "SYNCHRONIZING"
    #: Every required check in-bound (§6.1 line 149).
    TRUSTED = "TRUSTED"
    #: Online reference lost, monotonic anchor still within holdover budget; no new
    #: normal risk, only a pre-issued degraded protective lease (§6.2 line 151-155).
    DEGRADED_HOLDOVER = "DEGRADED_HOLDOVER"
    #: Trustworthiness unprovable; no new permissive action (§6.3 line 157-161).
    UNTRUSTED = "UNTRUSTED"


class FreshnessVerdict(StrEnum):
    """Freshness / ordering ambiguity verdict (ADR §9 line 241-243; §19 TIME-AC-007).

    ``UNKNOWN`` is not zero and not fresh: an unestablished bound is fail-closed
    (time design §2.6, §4). ``CONFLICTED`` is a non-clamped negative age or a
    future-beyond-tolerance timestamp (§9 line 243; §18 line 443).
    """

    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    CONFLICTED = "CONFLICTED"


class ReasonCode(StrEnum):
    """Provisional degradation / denial reason codes (ADR §8 line 205; §13 line 327-338).

    Derived from the ADR §13 failure table + §6 states. §13 is an *illustrative*
    table, so this set is **provisional** and Phase-0-extensible (time design §2.5
    B, §9.2); an unregistered code is fail-closed. Broker-agnostic (no KIS-specific
    code).
    """

    WALL_ROLLBACK = "WALL_ROLLBACK"
    WALL_JUMP = "WALL_JUMP"
    CLOCK_FREEZE = "CLOCK_FREEZE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_DISAGREEMENT_OUT_OF_BOUND = "SOURCE_DISAGREEMENT_OUT_OF_BOUND"
    DRIFT_EXCEEDED = "DRIFT_EXCEEDED"
    MONOTONIC_DISCONTINUITY = "MONOTONIC_DISCONTINUITY"
    RESTART = "RESTART"
    SUSPENSION_EXCEEDED_OR_UNKNOWN = "SUSPENSION_EXCEEDED_OR_UNKNOWN"
    BROKER_TIME_CONFLICT = "BROKER_TIME_CONFLICT"
    CALENDAR_OR_TZ_UNAVAILABLE = "CALENDAR_OR_TZ_UNAVAILABLE"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    UNESTABLISHABLE_GENERATION = "UNESTABLISHABLE_GENERATION"
    HOLDOVER_LIFETIME_NONPOSITIVE = "HOLDOVER_LIFETIME_NONPOSITIVE"
