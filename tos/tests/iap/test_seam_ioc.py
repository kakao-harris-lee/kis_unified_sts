"""MANDATED test-only seam cross-check: iap <-> ioc (design #15 §3.4; §11 line 288; v1.1 MAJOR-1).

Two directions:

* **produced (downstream reference)**: the ioc ``ApprovedIntentContract.approval_identity``
  (``ioc/records.py:199``) is a plain ``str | None`` scalar that references the iap decision
  identity — the ioc side holds the seam scalar, iap imports nothing.
* **consumed (upstream binding)**: the iap ``IndependentApprovalDecision`` binds the ioc
  ``ApprovedIntentContract`` approved-Intent envelope by ``(id, digest)`` scalar (§11 line 288 /
  §12 line 309 "byte-for-byte or canonically equivalent") — iap holds the scalar, ioc imports
  nothing.

**v1.1 MAJOR-1 correction**: ioc ``OrderConformanceProof`` (``ioc/records.py:357``) does **not**
carry an approval / consumption identity field — the §13 line 346 proof-binding is a -023
**downstream / future wiring** (§9.2 item 14), NOT an existing field. This test asserts that
absence so the "future wiring" boundary is regression-locked, not silently over-claimed.

A test-only cross-import is NOT a runtime package edge (§3.4/§7.1); ioc is one of the fifteen
siblings iap never imports at runtime (sibling edge 0).
"""

from __future__ import annotations

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.ioc import ApprovedIntentContract, OrderConformanceProof

from ._iap_strategies import issue_decision

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)


def test_ioc_approved_intent_contract_accepts_iap_decision_identity_scalar() -> None:
    """(§11 line 288 / ioc/records.py:199) The ioc contract's approval_identity accepts the iap decision id scalar."""
    decision = issue_decision(decision_id="iap-dec-1")
    assert decision.decision_id is not None
    contract = ApprovedIntentContract.issue(
        scheme=_SCHEME,
        intent_id="int-1",
        intent_generation=1,
        intent_version="v1",
        approval_identity=decision.decision_id,
    )
    # The ioc side holds a plain str scalar of the iap decision identity — never an iap object.
    assert contract.approval_identity == decision.decision_id
    assert isinstance(contract.approval_identity, str)
    assert not isinstance(contract.approval_identity, type(decision))


def test_iap_decision_binds_ioc_approved_intent_envelope_scalar() -> None:
    """(§11 line 288 / §12 line 309) The iap decision binds the ioc approved-Intent envelope (id, digest) scalar."""
    contract = ApprovedIntentContract.issue(
        scheme=_SCHEME, intent_id="int-1", intent_generation=1, intent_version="v1"
    )
    assert contract.intent_id is not None and contract.canonical_digest is not None
    decision = issue_decision(
        approved_intent_envelope_id=contract.intent_id,
        approved_intent_envelope_digest=contract.canonical_digest,
    )
    assert decision.approved_intent_envelope_id == contract.intent_id
    assert decision.approved_intent_envelope_digest == contract.canonical_digest


def test_tampered_envelope_digest_does_not_bind() -> None:
    """(polarity) A decision binding a tampered envelope digest does NOT reference the contract."""
    contract = ApprovedIntentContract.issue(
        scheme=_SCHEME, intent_id="int-1", intent_generation=1, intent_version="v1"
    )
    decision = issue_decision(approved_intent_envelope_digest="tampered")
    assert decision.approved_intent_envelope_digest != contract.canonical_digest


def test_order_conformance_proof_has_no_approval_field_future_wiring() -> None:
    """(v1.1 MAJOR-1 / §9.2 item 14) OrderConformanceProof carries NO approval/consumption field — future wiring.

    The §13 line 346 proof-binding (the proof SHALL include the approval decision + consumption
    record identities) is -023 **downstream / future wiring**, not an existing ioc field. Locking
    the absence prevents the phantom over-claim the v1.1 MAJOR-1 review corrected.
    """
    proof_fields = set(OrderConformanceProof.model_fields)
    for absent in (
        "approval_identity",
        "approval_decision_id",
        "consumption_record_id",
        "consumption_record_identity",
    ):
        assert absent not in proof_fields, (
            f"OrderConformanceProof unexpectedly carries {absent!r} — the §13:346 proof-binding "
            "is future wiring (v1.1 MAJOR-1), not an existing field"
        )
