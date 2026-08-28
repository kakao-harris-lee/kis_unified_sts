"""MANDATED test-only seam cross-check: hag artifacts -> evidence carry slots (design #20 §3.4/§3.5/§7).

evidence (ADR-002-016) is the **downstream** custody / replay engine: it carries the HAG digests
and reconstructs the human-authority history — hag does **not** import ``tos.evidence`` (evidence is
downstream, §3.5). The seam anchors are grep-verified evidence slots that carry HAG-produced ids /
digests:

* ``ReplayBaseline.human_authority_policy_digest`` (``replay.py:114``);
* ``ReplayBaseline.effective_principal_graph_digest`` (``replay.py:115``);
* ``EnvelopeSource.effective_principal_id`` (``envelope.py:56``);
* ``EnvelopeSubjects.approval_set_id`` (``envelope.py:93``).

This file imports the real evidence models as a **test** to prove those slots exist and accept the
HAG-produced coordinates; the import-closure test proves ``tos.evidence`` is **absent** from the hag
runtime closure. **Evidence is not authority** (§22 line 596): carrying a digest reconstructs a
record, it never re-creates authority.

Regime tag: predicate / model substrate only; HAG-EV-012 substrate; EV-L1-complete claim forbidden.
"""

from __future__ import annotations

from tos.evidence.envelope import EnvelopeSource, EnvelopeSubjects
from tos.evidence.replay import ReplayBaseline
from tos.hag import EffectivePrincipalGraph, HumanApprovalSet, HumanAuthorityPolicy

from ._hag_strategies import SCHEME, clean_approval_set


def test_replay_baseline_carries_policy_and_graph_digests() -> None:
    """(§3.4 replay.py:114-115) The replay baseline carries the HAG policy + graph digests."""
    fields = ReplayBaseline.model_fields
    assert "human_authority_policy_digest" in fields
    assert "effective_principal_graph_digest" in fields
    # The HAG-produced digests fill those slots (evidence carries them; hag imports no evidence).
    policy = HumanAuthorityPolicy.issue(
        scheme=SCHEME, policy_id="pol-1", policy_generation=1
    )
    graph = EffectivePrincipalGraph.issue(
        scheme=SCHEME, graph_id="g-1", graph_generation=1, unresolved_control=False
    )
    baseline = ReplayBaseline(
        human_authority_policy_digest=policy.canonical_digest,
        effective_principal_graph_digest=graph.canonical_digest,
    )
    assert baseline.human_authority_policy_digest == policy.canonical_digest
    assert baseline.effective_principal_graph_digest == graph.canonical_digest


def test_envelope_source_carries_effective_principal_id() -> None:
    """(§3.4 envelope.py:56) The envelope source carries the effective-principal id coordinate."""
    assert "effective_principal_id" in EnvelopeSource.model_fields
    source = EnvelopeSource(effective_principal_id="alice")
    assert source.effective_principal_id == "alice"


def test_envelope_subjects_carries_approval_set_id() -> None:
    """(§3.4 envelope.py:93) The envelope subjects carry the HAG approval-set id."""
    assert "approval_set_id" in EnvelopeSubjects.model_fields
    approval_set: HumanApprovalSet = clean_approval_set(set_id="set-seam-1")
    subjects = EnvelopeSubjects(approval_set_id=approval_set.set_id)
    assert subjects.approval_set_id == "set-seam-1"


def test_hag_does_not_import_evidence() -> None:
    """(§3.5) evidence is downstream — hag re-authors no evidence custody / replay engine."""
    import tos.hag as hag

    assert not hasattr(hag, "ReplayBaseline")
    assert not hasattr(hag, "EnvelopeSource")
    assert not hasattr(hag, "SafetyEvidenceEnvelope")
