"""Recon vocabulary — per-field evidence confidence classes + safety-relevant fields.

Spec terms = code terms (design #9 §2; boundary design #1 §2.4). The enums are
authored **verbatim** from ADR-002-006 §5 (confidence classes, line 73-80; the
safety-relevant field list, line 55-67). The confidence class is the **per-field
evidence confidence** axis — a distinct coordinate system from the orthostate
``KnowledgeState`` (per-action aggregate knowledge) and the capsule ``FieldState``
(per-field context freshness). The three axes deliberately share the tokens
``UNKNOWN`` / ``CONFLICTED`` / ``STALE`` (ADR uses the same words per-field and
per-action), so coordinate non-collapse rests on **distinct types + non-import**,
not global string distinctness (design #9 §4.2): recon imports neither ``tos.orthostate``
nor ``tos.capsule``, so a value from one axis can never be coerced onto another.

There is **no** numeric confidence score type anywhere in ``tos.recon`` — confidence
is exactly a class (this StrEnum) plus a :class:`~tos.recon.records.ConservativeBound`,
never a midpoint / average / blended scalar (ADR §5 line 86; design #9 §4.1).

Pure module: stdlib only; no ``shared.*`` (design #9 §0.3).
"""

from __future__ import annotations

from enum import StrEnum


class FieldConfidenceClass(StrEnum):
    """The 5 per-field evidence confidence classes (ADR-002-006 §5 line 73-80 verbatim).

    Verbatim from ADR §5::

        UNKNOWN        — no usable evidence; treat at maximum conservative bound
        SINGLE_SOURCE  — one source only; usable only under a recorded, independently
                         accepted single-source residual (ADR-002-004; SAFE-023)
        CORROBORATED   — >=2 sufficiently independent paths agree within tolerance
        CONFLICTED     — independent paths disagree beyond tolerance
        STALE          — previously sufficient, now older than the approved freshness bound

    This is the **per-field evidence confidence** axis (design #9 §0.4e / §4.2), distinct
    from orthostate ``KnowledgeState`` (per-action aggregate: UNOBSERVED / CONSISTENT /
    CONFLICTED / RECONCILING / RECONCILED / QUARANTINED / STALE) and capsule ``FieldState``
    (per-field context freshness: INVALID / CONFLICTED / STALE / UNKNOWN / VALID). The
    shared tokens are intentional but the types are separate:
    ``FieldConfidenceClass.CONFLICTED`` is **not** ``KnowledgeState.CONFLICTED``.

    There is deliberately **no** ``RECONCILED`` member here: ``CORROBORATED`` is the
    highest per-field grade; the per-action aggregate ``RECONCILED`` is owned by the
    orthostate Knowledge dimension, gated by recon's produced proof bools (design #9
    §3.4 seam). Per-field confidence never becomes ``RECONCILED`` on its own.
    """

    UNKNOWN = "UNKNOWN"
    SINGLE_SOURCE = "SINGLE_SOURCE"
    CORROBORATED = "CORROBORATED"
    CONFLICTED = "CONFLICTED"
    STALE = "STALE"


class SafetyRelevantField(StrEnum):
    """The safety-relevant fields reconciliation maintains evidence for (ADR §5 line 55-67).

    ADR §5 line 55: "Reconciliation SHALL maintain independent evidence for **at least**
    these safety-relevant fields." This is therefore a **non-closed minimum set** (design
    #9 §2.2 / §5.4): recon predicates are field-parametric and make **no** exhaustive-
    closure assertion — a downstream ADR (e.g. ADR-002-030) may extend it. The 13 named
    fields transcribed verbatim from the ADR §5 two-column list (line 57-67, read as
    pairs), preserving each ADR phrase; the first eight map one-to-one (concept, not
    string) to the ADR-002-002 §22.1 fields recon elaborates.
    """

    # Row 1 (ADR §5 line 58): order existence | broker order identity
    ORDER_EXISTENCE = "ORDER_EXISTENCE"
    BROKER_ORDER_IDENTITY = "BROKER_ORDER_IDENTITY"
    # Row 2 (line 59): cumulative filled quantity | remaining executable quantity
    CUMULATIVE_FILLED_QUANTITY = "CUMULATIVE_FILLED_QUANTITY"
    REMAINING_EXECUTABLE_QUANTITY = "REMAINING_EXECUTABLE_QUANTITY"
    # Row 3 (line 60): position quantity | cash / margin / collateral
    POSITION_QUANTITY = "POSITION_QUANTITY"
    CASH_MARGIN_COLLATERAL = "CASH_MARGIN_COLLATERAL"
    # Row 4 (line 61): protective coverage | instrument identity
    PROTECTIVE_COVERAGE = "PROTECTIVE_COVERAGE"
    INSTRUMENT_IDENTITY = "INSTRUMENT_IDENTITY"
    # Row 5 (line 62): external / unattributed activity
    EXTERNAL_UNATTRIBUTED_ACTIVITY = "EXTERNAL_UNATTRIBUTED_ACTIVITY"
    # Row 6 (line 63): post-trade obligation identity and version
    POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION = (
        "POST_TRADE_OBLIGATION_IDENTITY_AND_VERSION"
    )
    # Row 7 (line 64): settlement / cash availability / collateral eligibility
    SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY = (
        "SETTLEMENT_CASH_AVAILABILITY_COLLATERAL_ELIGIBILITY"
    )
    # Row 8 (line 65): borrow / custody / transfer / legal-title state
    BORROW_CUSTODY_TRANSFER_LEGAL_TITLE_STATE = (
        "BORROW_CUSTODY_TRANSFER_LEGAL_TITLE_STATE"
    )
    # Row 9 (line 66): statement coverage / break / correction / field-specific finality
    STATEMENT_COVERAGE_BREAK_CORRECTION_FIELD_SPECIFIC_FINALITY = (
        "STATEMENT_COVERAGE_BREAK_CORRECTION_FIELD_SPECIFIC_FINALITY"
    )


#: The capacity-releasing subset (ADR §8 line 114): only these two fields' RECONCILED
#: proof rule additionally requires a Final Quantity Proof (design #9 §6.2). "final
#: filled quantity" (ADR §8) is the ``CUMULATIVE_FILLED_QUANTITY`` field. This is a
#: closed subset of the (non-closed) field set — it names exactly which fields gate a
#: capacity release, not the full universe of legal fields.
CAPACITY_RELEASING_FIELDS: frozenset[SafetyRelevantField] = frozenset(
    {
        SafetyRelevantField.CUMULATIVE_FILLED_QUANTITY,
        SafetyRelevantField.REMAINING_EXECUTABLE_QUANTITY,
    }
)
