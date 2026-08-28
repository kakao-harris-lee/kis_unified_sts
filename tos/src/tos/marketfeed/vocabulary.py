"""The closed vocabulary of the value surface — dispositions and rejection reasons (design #32 §6).

Two enums, both **positive-membership** closed sets:

* :class:`ValueViewDisposition` — what happened to the *view as a whole*. Its four members exist so
  the design §6 "∅ 양방향" distinction is recorded rather than collapsed: an **explicit-empty** view
  (the snapshot bound, nothing was admissible) is materially different from **no view at all**
  (the snapshot could not be resolved, or the binding disagreed with the Capsule). Both are equally
  restrictive downstream — every value operand resolves to ``UNKNOWN`` either way — but they are
  different facts about the world and are recorded as different members.

* :class:`ValueRejectionReason` — why one *candidate value* did not reach the environment. Every
  reason is a positive, named cause; there is no "OTHER" catch-all, because an unnamed rejection is
  an unauditable one.

⚠ **Provisional; closes no EV** (design #32 §1.1).

Firewall: stdlib only.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ADMITTING_DISPOSITIONS",
    "ValueRejectionReason",
    "ValueViewDisposition",
]


class ValueViewDisposition(StrEnum):
    """The terminal shape of one value-view resolution (design #32 §6 ∅ 양방향)."""

    #: The snapshot bound and at least one value was admitted.
    RESOLVED = "RESOLVED"
    #: The snapshot bound and **zero** values were admissible — a defined no-value context.
    EXPLICIT_EMPTY = "EXPLICIT_EMPTY"
    #: The Capsule's ``SnapshotRef`` could not be resolved to a snapshot body at all.
    SNAPSHOT_UNRESOLVED = "SNAPSHOT_UNRESOLVED"
    #: A snapshot body was produced but its id/digest disagreed with the Capsule's reference —
    #: refused rather than silently substituted (ADR-002-018 §15:386).
    BINDING_MISMATCH = "BINDING_MISMATCH"
    #: The reserved value namespace collided with a Capsule top-level key — merging would overwrite
    #: covered Capsule content, so publication is refused (design #32 §3.2 (1)).
    NAMESPACE_COLLISION = "NAMESPACE_COLLISION"


#: The dispositions under which a :class:`~tos.dsl.ContextValueView` exists at all. Membership is
#: **positive**: everything outside this set carries no view, and a consumer that tests
#: ``disposition not in ADMITTING_DISPOSITIONS`` is asking the restrictive question.
#: ``EXPLICIT_EMPTY`` is in the set on purpose — an explicit-empty view is a real, publishable,
#: signature-bearing artifact ("we resolved, and the answer is nothing"), not a failure.
ADMITTING_DISPOSITIONS: frozenset[ValueViewDisposition] = frozenset(
    {ValueViewDisposition.RESOLVED, ValueViewDisposition.EXPLICIT_EMPTY}
)


class ValueRejectionReason(StrEnum):
    """Why one candidate value did not reach the DSL environment (design #32 §2.2/§2.3/§2.5/§5)."""

    #: No observation in the snapshot carries the candidate's ``observation_ref``.
    OBSERVATION_NOT_FOUND = "OBSERVATION_NOT_FOUND"
    #: More than one observation carries that raw-event identity — attribution is ambiguous.
    OBSERVATION_AMBIGUOUS = "OBSERVATION_AMBIGUOUS"
    #: The attributed observation records no ``raw.payload_digest`` — no provenance to bind to.
    PAYLOAD_DIGEST_ABSENT = "PAYLOAD_DIGEST_ABSENT"
    #: The attributed observation records no ``time.source_event_time`` — no as-of anchor, so no
    #: Validity Window and no per-bar distinctness load (design #32 §4.2).
    AS_OF_ABSENT = "AS_OF_ABSENT"
    #: The candidate's payload preimage does not digest to the observation's recorded
    #: ``payload_digest`` — the value is not the value that observation attests (design #32 §2.3).
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    #: The preimage carries no entry under the candidate's ``field_key``.
    VALUE_NOT_IN_PAYLOAD = "VALUE_NOT_IN_PAYLOAD"
    #: The VALID gate did not return ``VALID`` (design #32 §2.2).
    FIELD_STATE_NOT_VALID = "FIELD_STATE_NOT_VALID"
    #: A fractional / floating magnitude: the deterministic-float projection rule is not yet fixed,
    #: so the fractional path is fail-closed rather than silently coerced (design #32 §2.5).
    NON_DETERMINISTIC_NUMERIC = "NON_DETERMINISTIC_NUMERIC"
    #: The lineage node producing this value is not reproducible or is missing an exact parent
    #: (ADR-002-018 §10:288; design #32 §5.2).
    LINEAGE_NOT_REPRODUCIBLE = "LINEAGE_NOT_REPRODUCIBLE"
    #: A recorded lineage parent's as-of is **after** the derived value's as-of — look-ahead
    #: (RFC-004 §6:162-165; design #32 §5.4).
    LINEAGE_LOOKAHEAD = "LINEAGE_LOOKAHEAD"
    #: A recorded lineage parent cannot be resolved to an observation, so causality cannot be
    #: established — fail-closed, not assumed sound.
    LINEAGE_PARENT_UNRESOLVED = "LINEAGE_PARENT_UNRESOLVED"
    #: Two admitted candidates claim the same ``field_key`` — never averaged, majority-voted, or
    #: arbitrarily folded (ADR-002-018 §11:311; design #32 §6).
    DUPLICATE_FIELD_KEY = "DUPLICATE_FIELD_KEY"
    #: The ``field_key`` is a wildcard / "latest" form (RFC-008 §7:239-240).
    WILDCARD_FIELD_KEY = "WILDCARD_FIELD_KEY"
