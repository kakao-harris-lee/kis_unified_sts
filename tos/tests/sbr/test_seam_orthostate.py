"""MANDATED test-only seam cross-check: sbr <- orthostate (design #17 §3.4(d) / §7).

SBR **consumes** orthostate's ``reconstruct_conservative`` (per-dimension conservative
restart) as an injected result during the §14 RECONCILING phase; it does **not** re-author
state reconstruction (§3.5 — orthostate owns the reconstruction, SBR folds the result into
obligation inputs). This file imports the real orthostate ``reconstruct_conservative`` /
``CompositeState`` / ``KnowledgeState`` as a **test** to lock:

(a) the reconstruction codomain **structurally excludes** ``RECONCILED``
    (``orthostate/predicates.py:23-24``) — a restart never yields "proven reconciled", so a
    positive-knowledge state (``RECONCILED`` / ``CONSISTENT``) is downgraded to ``CONFLICTED``;
(b) **no re-authoring** — ``tos.sbr`` exposes no ``reconstruct_conservative`` / state-
    reconstruction surface of its own (the boundary that keeps SBR the orchestrator, not the
    per-dimension judge).

A test-only cross-import is **not** a runtime package edge (design #17 §3.4(d)/§7.1).
"""

from __future__ import annotations

import tos.sbr as sbr
from tos.orthostate import (
    BrokerOrderState,
    CompositeState,
    IntentState,
    KnowledgeState,
    TransmissionAttemptState,
    reconstruct_conservative,
)
from tos.rcl import CapacityState


def _composite(knowledge: KnowledgeState) -> CompositeState:
    """A pre-restart composite observation with the given knowledge state."""
    return CompositeState(
        composite_state_id=None,
        intent_identity="intent-1",
        intent_state=IntentState.ACTIVE,
        transmission_attempt_state=TransmissionAttemptState.SENT_UNCONFIRMED,
        broker_order_state=BrokerOrderState.WORKING,
        knowledge_state=knowledge,
        capacity_state=CapacityState.POTENTIALLY_LIVE,
    )


def test_reconstruction_codomain_excludes_reconciled() -> None:
    """(seam a, STATE-EV-004) A restart downgrades RECONCILED / CONSISTENT to CONFLICTED — never RECONCILED."""
    for positive in (KnowledgeState.RECONCILED, KnowledgeState.CONSISTENT):
        post = reconstruct_conservative(_composite(positive))
        assert post.knowledge_state is KnowledgeState.CONFLICTED
        assert post.knowledge_state is not KnowledgeState.RECONCILED


def test_reconstruction_result_is_a_fresh_draft() -> None:
    """(seam) The reconstruction is a fresh DRAFT observation SBR folds — SBR issues nothing here."""
    post = reconstruct_conservative(_composite(KnowledgeState.RECONCILED))
    assert post.composite_state_id is None  # DRAFT — no id / digest yet
    assert post.canonical_digest is None


def test_sbr_does_not_re_author_state_reconstruction() -> None:
    """(seam b, §3.5) SBR exposes NO reconstruction surface — it consumes orthostate's, re-authors none."""
    for forbidden in (
        "reconstruct_conservative",
        "reconstruct",
        "CompositeState",
        "KnowledgeState",
        "reconstruct_state",
    ):
        assert forbidden not in sbr.__all__
        assert not hasattr(sbr, forbidden)


def test_sbr_source_does_not_define_a_reconstruct_function() -> None:
    """(seam b, source seal) No sbr source defines a reconstruction function of its own."""
    from pathlib import Path

    sbr_src = Path(__file__).resolve().parent.parent.parent / "src" / "tos" / "sbr"
    for path in sorted(sbr_src.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "def reconstruct" not in text, f"{path.name} re-authors reconstruction"
