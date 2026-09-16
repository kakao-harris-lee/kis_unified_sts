"""``tos_runtime.marketfeed.capsule`` — ``CapsuleIssuer`` binding + refusals (TOS tick-source
wave, plan §2 decision 1; lane A).

Hermetic (D1.4): every case writes its own policy YAML under ``tmp_path``; no network, no clock.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule
from tos_runtime.marketfeed.capsule import CapsuleIssuanceError, CapsuleIssuer
from tos_runtime.marketfeed.snapshot import SnapshotIssuer

from ._fixtures import (
    ACCOUNT,
    BAR_ONE_AS_OF,
    DECISION_CLASS,
    ENVIRONMENT,
    INSTRUMENT,
    SCHEME,
    loaded_policy,
    observation,
)


def _issued_snapshot(tmp_path: Path):
    policy = loaded_policy(tmp_path)
    snap_issuer = SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)
    issued = snap_issuer.issue(observation(), now_ms=BAR_ONE_AS_OF + 100)
    return issued.snapshot


def _capsule_issuer(policy_ref) -> CapsuleIssuer:
    return CapsuleIssuer(
        account=ACCOUNT,
        instrument=INSTRUMENT,
        environment=ENVIRONMENT,
        decision_class=DECISION_CLASS,
        direction="LONG",
        quantity_basis="RISK",
        unit="contract",
        issuer_principal_id="iss-1",
        critical_input_policy=policy_ref,
        scheme=SCHEME,
    )


def test_issue_binds_snapshot_ref_exactly(tmp_path: Path) -> None:
    snapshot = _issued_snapshot(tmp_path)
    issuer = _capsule_issuer(snapshot.critical_input_policy)

    capsule = issuer.issue(snapshot)

    assert isinstance(capsule, DecisionContextCapsule)
    assert capsule.critical_input_snapshot.snapshot_id == snapshot.snapshot_id
    assert capsule.critical_input_snapshot.canonical_digest == snapshot.canonical_digest
    assert capsule.scope.environment == ENVIRONMENT
    assert capsule.scope.account == ACCOUNT
    assert capsule.scope.instrument == INSTRUMENT
    assert capsule.scope.decision_class == DECISION_CLASS
    assert capsule.safety_critical_facts.direction == "LONG"
    assert capsule.safety_critical_facts.quantity_basis == "RISK"
    assert capsule.safety_critical_facts.unit == "contract"


def test_refuses_snapshot_with_null_id_and_digest(tmp_path: Path) -> None:
    """A DRAFT snapshot (never issued) has ``snapshot_id=None``/``canonical_digest=None`` — a
    real deployment can never construct one this way, but a caller passing one in error must be
    refused with a typed error, not a silent null-bound ``SnapshotRef``."""
    draft = CriticalInputSnapshot()
    assert draft.snapshot_id is None
    assert draft.canonical_digest is None

    issuer = _capsule_issuer(_issued_snapshot(tmp_path).critical_input_policy)
    with pytest.raises(CapsuleIssuanceError, match="snapshot_id"):
        issuer.issue(draft)


def test_two_snapshots_of_distinct_observations_bind_distinct_capsules(
    tmp_path: Path,
) -> None:
    """Distinct as-of -> distinct snapshot digest -> distinct capsule digest (design #32 §4, the
    D-E1 Gap-1 residue this wave discharges)."""
    policy = loaded_policy(tmp_path)
    snap_issuer = SnapshotIssuer(policy=policy, scheme=SCHEME, account=ACCOUNT)
    issued_one = snap_issuer.issue(
        observation(raw_event_id="raw-1"), now_ms=BAR_ONE_AS_OF + 100
    )
    issued_two = snap_issuer.issue(
        observation(raw_event_id="raw-2", as_of_ms=BAR_ONE_AS_OF + 60_000),
        now_ms=BAR_ONE_AS_OF + 60_100,
    )
    assert issued_one.snapshot.canonical_digest != issued_two.snapshot.canonical_digest

    issuer = _capsule_issuer(issued_one.snapshot.critical_input_policy)
    capsule_one = issuer.issue(issued_one.snapshot)
    capsule_two = issuer.issue(issued_two.snapshot)
    assert capsule_one.capsule_id != capsule_two.capsule_id
