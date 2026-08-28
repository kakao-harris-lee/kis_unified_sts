"""MANDATED test-only seam cross-check: hag request -> capsule digest binding (design #20 §2.4/§3.5/§7).

The **reverse-direction** seam (MAJOR-1): a :class:`~tos.hag.records.HumanApprovalRequest` **binds
the Decision Context Capsule identity and digest** (ADR §10 line 306 — request -> capsule), so the
HAG artifact carries the capsule coordinates. The capsule's own ``approval_request_id``
(``capsule.py:161``, on the ``Bindings`` forward-reference chain) is the **iap** automated-pipeline
field (iap ``ProposalApprovalRequest`` axis), **not** an HAG downstream reference — hag binds the
capsule digest, never the capsule's ``approval_request_id`` (§0.4a/§0.4e). This file imports the real
capsule models as a **test** to lock the reverse binding + the MAJOR-1 regression; the import-closure
test proves ``tos.capsule`` is **absent** from the hag runtime closure.

Regime tag: predicate / model substrate only; HAG-EV-002 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.capsule.capsule import Bindings, DecisionContextCapsule
from tos.hag import HumanApprovalRequest

from ._hag_strategies import clean_request


def test_hag_request_binds_the_capsule_identity_and_digest() -> None:
    """(§2.4 / ADR §10 line 306) The HAG request binds the capsule id + digest (request -> capsule)."""
    fields = set(HumanApprovalRequest.model_fields)
    assert "decision_context_capsule_id" in fields
    assert "decision_context_capsule_digest" in fields
    request = clean_request()
    assert request.decision_context_capsule_id == "dcc-1"
    assert request.decision_context_capsule_digest == "dcc-digest"


def test_capsule_is_the_content_addressed_artifact_hag_binds() -> None:
    """(§3.5) The capsule is capsule-owned (id = f(digest)); hag binds its digest, does not build it."""
    # The capsule owns its identity shape (capsule_id + canonical_digest) — hag references it only.
    fields = set(DecisionContextCapsule.model_fields)
    assert "capsule_id" in fields
    assert "canonical_digest" in fields
    assert DecisionContextCapsule._ID_FIELD == "capsule_id"


def test_capsule_approval_request_id_is_the_iap_bindings_axis() -> None:
    """(MAJOR-1) The capsule Bindings.approval_request_id is the iap axis — never an HAG seam."""
    # The capsule's approval_request_id lives on the iap-owned forward-reference Bindings chain…
    assert "approval_request_id" in Bindings.model_fields
    # …and the HAG request does NOT consume it (it binds the capsule DIGEST, not this field).
    assert "approval_request_id" not in set(HumanApprovalRequest.model_fields)


def test_hag_does_not_import_capsule() -> None:
    """(§3.5) capsule is capsule-owned — hag re-authors no capsule / Ref / Bindings type."""
    import tos.hag as hag

    assert not hasattr(hag, "DecisionContextCapsule")
    assert not hasattr(hag, "Bindings")
