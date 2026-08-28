"""4-axis coordinate non-collapse (design #10 §4.4).

A **test-only** cross-import of the four axes that share the ``UNKNOWN`` token — brokercap
``CapabilityStatus`` (broker capability), orthostate ``BrokerOrderState`` / ``KnowledgeState``
(broker-order / per-action state), recon ``FieldConfidenceClass`` (per-field confidence). The
shared token is intentional; non-collapse rests on **distinct types + non-import** (brokercap
imports none of the sibling axes at runtime — the import-closure test proves that). This test
imports them only to assert type identity; a test-only import is NOT a package edge (design
#10 §3.4/§7.1).

Note (design deviation, disclosed): the contract's illustrative literal
``CapabilityStatus.UNKNOWN is not KnowledgeState.UNKNOWN`` cannot be written verbatim —
``KnowledgeState`` deliberately has **no** ``UNKNOWN`` member (that token lives on the Broker /
Capacity dimensions and on recon; orthostate ``KnowledgeState`` uses ``UNOBSERVED`` /
``CONFLICTED``). The non-collapse intent is realized against the axes that actually share the
token (``BrokerOrderState`` / ``FieldConfidenceClass``), plus a guard that ``KnowledgeState``
tokens (``RECONCILED`` etc.) are absent from ``CapabilityStatus``.
"""

from __future__ import annotations

from tos.brokercap import CapabilityStatus
from tos.orthostate import BrokerOrderState, KnowledgeState
from tos.recon import FieldConfidenceClass


def test_capability_status_unknown_is_distinct_type_from_broker_order() -> None:
    """CapabilityStatus.UNKNOWN is not BrokerOrderState.UNKNOWN (distinct types)."""
    assert CapabilityStatus.UNKNOWN is not BrokerOrderState.UNKNOWN
    assert type(CapabilityStatus.UNKNOWN) is not type(BrokerOrderState.UNKNOWN)


def test_capability_status_unknown_is_distinct_type_from_field_confidence() -> None:
    """CapabilityStatus.UNKNOWN is not FieldConfidenceClass.UNKNOWN (distinct types)."""
    assert CapabilityStatus.UNKNOWN is not FieldConfidenceClass.UNKNOWN
    assert type(CapabilityStatus.UNKNOWN) is not type(FieldConfidenceClass.UNKNOWN)


def test_knowledge_state_tokens_absent_from_capability_status() -> None:
    """Per-action Knowledge tokens (RECONCILED / RECONCILING / QUARANTINED) are not capability statuses."""
    capability_values = {s.value for s in CapabilityStatus}
    for token in ("RECONCILED", "RECONCILING", "QUARANTINED", "CONSISTENT", "VALID"):
        assert token not in capability_values
    # And KnowledgeState indeed has no UNKNOWN member (the contract's note).
    assert "UNKNOWN" not in {k.value for k in KnowledgeState}


def test_value_equality_does_not_imply_identity() -> None:
    """StrEnum value equality ('UNKNOWN' == 'UNKNOWN') never collapses the axes' identity."""
    # As str subclasses the VALUES compare equal, but the members are distinct objects on
    # distinct types — coordinate non-collapse rests on identity / type, not value.
    assert CapabilityStatus.UNKNOWN == "UNKNOWN"
    assert BrokerOrderState.UNKNOWN == "UNKNOWN"
    assert CapabilityStatus.UNKNOWN is not BrokerOrderState.UNKNOWN
