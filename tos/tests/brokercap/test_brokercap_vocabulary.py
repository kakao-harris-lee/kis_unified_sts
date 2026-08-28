"""Verbatim-transcription checks for the brokercap vocabulary (design #10 §2.2).

Guards the erratum defect class (design #10 §0.1(e)): each StrEnum has exactly the ADR
member count + token, so a silent transcription drift fails a test.
"""

from __future__ import annotations

from tos.brokercap import (
    AUTHORIZING_STATUSES,
    AcknowledgementState,
    Admissibility,
    AssuranceLevel,
    AssuranceSource,
    CapabilityDimension,
    CapabilityStatus,
    ConformanceClass,
    ProhibitedProof,
    ReplaceSemantics,
)


def test_capability_status_seven_verbatim() -> None:
    """(§2.2-1) CapabilityStatus has the 7 ADR §5.3 tokens verbatim."""
    assert [s.value for s in CapabilityStatus] == [
        "VERIFIED",
        "VERIFIED_WITH_RESTRICTION",
        "DOCUMENTED_NOT_VERIFIED",
        "UNSUPPORTED",
        "CONTRADICTORY",
        "UNKNOWN",
        "EXPIRED",
    ]


def test_capability_dimension_seventeen_verbatim() -> None:
    """(§2.2-2) CapabilityDimension has the 17 ADR §8.1-§8.17 tokens verbatim."""
    assert [d.value for d in CapabilityDimension] == [
        "ORDER_IDENTITY",
        "SUBMISSION_IDEMPOTENCY",
        "ACKNOWLEDGEMENT_SEMANTICS",
        "FILL_EVENTS",
        "OPEN_ORDER_QUERY",
        "ORDER_HISTORY_QUERY",
        "CANCELLATION",
        "REPLACE_OR_AMEND",
        "REDUCE_ONLY",
        "POSITIONS_BALANCES_MARGIN",
        "ACCOUNT_EVENT_PUSH",
        "CORPORATE_ADMINISTRATIVE_EVENTS",
        "RATE_LIMITS",
        "SESSION_CONNECTION_MODEL",
        "CREDENTIALS_AUTHORIZATION",
        "BROKER_TIME",
        "MARKET_INSTRUMENT_CONSTRAINTS",
    ]
    assert len(list(CapabilityDimension)) == 17


def test_assurance_level_five_verbatim() -> None:
    """(§2.2-3) AssuranceLevel has the 5 ADR §9 tokens verbatim."""
    assert [level.value for level in AssuranceLevel] == [
        "LEVEL_0_UNKNOWN",
        "LEVEL_1_DOCUMENTED",
        "LEVEL_2_CONTROLLED_TEST_VERIFIED",
        "LEVEL_3_RESTRICTED_PRODUCTION",
        "LEVEL_4_CONTINUOUSLY_MONITORED",
    ]


def test_conformance_class_four_verbatim() -> None:
    """(§2.2-4) ConformanceClass has the 4 ADR §10 tokens verbatim."""
    assert [c.value for c in ConformanceClass] == [
        "CLASS_A_DETERMINISTIC_LIVE",
        "CLASS_B_RESTRICTED_SERIALIZED_LIVE",
        "CLASS_C_PROTECTIVE_SUPERVISED_ONLY",
        "CLASS_D_NON_LIVE",
    ]


def test_assurance_source_eight() -> None:
    """(§2.2-8) AssuranceSource has the 8 ADR §5.4 sources."""
    assert len(list(AssuranceSource)) == 8


def test_acknowledgement_state_six_verbatim() -> None:
    """(§2.2-5) AcknowledgementState has the 6 ADR §8.3 tokens verbatim."""
    assert [a.value for a in AcknowledgementState] == [
        "TRANSPORT_RECEIVED",
        "BROKER_RECEIVED",
        "VALIDATED",
        "ACCEPTED",
        "WORKING",
        "REJECTED",
    ]


def test_replace_semantics_five_verbatim() -> None:
    """(§2.2-5) ReplaceSemantics has the 5 ADR §8.8 tokens verbatim."""
    assert [r.value for r in ReplaceSemantics] == [
        "ATOMIC_REPLACE",
        "CANCEL_THEN_NEW",
        "NEW_THEN_CANCEL",
        "BROKER_UNSPECIFIED",
        "UNSUPPORTED",
    ]


def test_admissibility_three_tokens() -> None:
    """(§2.2-9) Admissibility is the local 3-token verdict (no 'assume-admissible' extra)."""
    assert [a.value for a in Admissibility] == ["ADMISSIBLE", "REDUCED", "PROHIBITED"]


def test_prohibited_proof_seven_verbatim() -> None:
    """(§2.2 / §15.3) ProhibitedProof has the 7 ADR §15.3 tokens verbatim."""
    assert [p.value for p in ProhibitedProof] == [
        "CANCEL_ACKNOWLEDGEMENT",
        "ONE_OPEN_ORDER_QUERY_OMISSION",
        "LOCAL_TIMEOUT",
        "STRATEGY_CANCELLATION_INTENT",
        "PROCESS_RESTART",
        "ACCOUNT_POSITION_MATCHING_EXPECTED_VALUE",
        "OPERATOR_ASSERTION_WITHOUT_BROKER_EVIDENCE",
    ]


def test_authorizing_statuses_exactly_two() -> None:
    """(§5.3 line 146) Only VERIFIED and VERIFIED_WITH_RESTRICTION authorize."""
    assert (
        frozenset(
            {
                CapabilityStatus.VERIFIED,
                CapabilityStatus.VERIFIED_WITH_RESTRICTION,
            }
        )
        == AUTHORIZING_STATUSES
    )
