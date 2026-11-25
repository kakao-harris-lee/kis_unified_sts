"""The closed vocabulary of the value surface — dispositions and rejection reasons (design #32 §6)."""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ADMITTING_DISPOSITIONS",
    "ValueRejectionReason",
    "ValueViewDisposition",
]


class ValueViewDisposition(StrEnum):
    """The terminal shape of one value-view resolution (design #32 §6 ∅ 양방향)."""

    RESOLVED = "RESOLVED"
    EXPLICIT_EMPTY = "EXPLICIT_EMPTY"
    SNAPSHOT_UNRESOLVED = "SNAPSHOT_UNRESOLVED"
    BINDING_MISMATCH = "BINDING_MISMATCH"
    NAMESPACE_COLLISION = "NAMESPACE_COLLISION"


ADMITTING_DISPOSITIONS: frozenset[ValueViewDisposition] = frozenset(
    {ValueViewDisposition.RESOLVED, ValueViewDisposition.EXPLICIT_EMPTY}
)


class ValueRejectionReason(StrEnum):
    """Why one candidate value did not reach the DSL environment (design #32 §2.2/§2.3/§2.5/§5)."""

    OBSERVATION_NOT_FOUND = "OBSERVATION_NOT_FOUND"
    OBSERVATION_AMBIGUOUS = "OBSERVATION_AMBIGUOUS"
    PAYLOAD_DIGEST_ABSENT = "PAYLOAD_DIGEST_ABSENT"
    AS_OF_ABSENT = "AS_OF_ABSENT"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"
    VALUE_NOT_IN_PAYLOAD = "VALUE_NOT_IN_PAYLOAD"
    FIELD_STATE_NOT_VALID = "FIELD_STATE_NOT_VALID"
    NON_DETERMINISTIC_NUMERIC = "NON_DETERMINISTIC_NUMERIC"
    LINEAGE_NOT_REPRODUCIBLE = "LINEAGE_NOT_REPRODUCIBLE"
    LINEAGE_LOOKAHEAD = "LINEAGE_LOOKAHEAD"
    LINEAGE_PARENT_UNRESOLVED = "LINEAGE_PARENT_UNRESOLVED"
    DUPLICATE_FIELD_KEY = "DUPLICATE_FIELD_KEY"
    WILDCARD_FIELD_KEY = "WILDCARD_FIELD_KEY"
