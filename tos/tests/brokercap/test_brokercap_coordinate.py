"""4-axis coordinate non-collapse (design #10 §4.4)."""

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
    assert "UNKNOWN" not in {k.value for k in KnowledgeState}


def test_value_equality_does_not_imply_identity() -> None:
    """StrEnum value equality ('UNKNOWN' == 'UNKNOWN') never collapses the axes' identity."""
    assert CapabilityStatus.UNKNOWN == "UNKNOWN"
    assert BrokerOrderState.UNKNOWN == "UNKNOWN"
    assert CapabilityStatus.UNKNOWN is not BrokerOrderState.UNKNOWN
