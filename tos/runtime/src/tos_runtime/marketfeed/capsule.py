"""``tos_runtime.marketfeed.capsule`` — the Decision Context Capsule issuer (TOS tick-source"""

from __future__ import annotations

from tos.canonical import CanonicalizationScheme
from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule, PolicyRef
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef

__all__ = [
    "CapsuleIssuanceError",
    "CapsuleIssuer",
]


class CapsuleIssuanceError(RuntimeError):
    """Refused to issue a capsule for a snapshot whose ``snapshot_id``/``canonical_digest`` is"""


class CapsuleIssuer:
    """Issues one :class:`~tos.capsule.DecisionContextCapsule` per issued snapshot, for one fixed"""

    def __init__(
        self,
        *,
        account: str,
        instrument: str,
        environment: str,
        decision_class: str,
        direction: str,
        quantity_basis: str,
        unit: str,
        issuer_principal_id: str,
        critical_input_policy: PolicyRef,
        scheme: CanonicalizationScheme,
    ) -> None:
        self._account = account
        self._instrument = instrument
        self._environment = environment
        self._decision_class = decision_class
        self._direction = direction
        self._quantity_basis = quantity_basis
        self._unit = unit
        self._issuer_principal_id = issuer_principal_id
        self._critical_input_policy = critical_input_policy
        self._scheme = scheme

    def issue(self, snapshot: CriticalInputSnapshot) -> DecisionContextCapsule:
        """Bind ``snapshot`` into a Decision Context Capsule (module docstring)."""
        if snapshot.snapshot_id is None or snapshot.canonical_digest is None:
            raise CapsuleIssuanceError(
                "cannot issue a capsule for a snapshot with no concrete snapshot_id/"
                f"canonical_digest (snapshot_id={snapshot.snapshot_id!r}, "
                f"canonical_digest={snapshot.canonical_digest!r}) — an unissued snapshot has "
                "nothing for SnapshotRef to bind"
            )

        capsule = DecisionContextCapsule.issue(
            scheme=self._scheme,
            issuer_principal_id=self._issuer_principal_id,
            critical_input_policy=self._critical_input_policy,
            critical_input_snapshot=SnapshotRef(
                snapshot_id=snapshot.snapshot_id,
                canonical_digest=snapshot.canonical_digest,
            ),
            scope=CapsuleScope(
                environment=self._environment,
                account=self._account,
                instrument=self._instrument,
                decision_class=self._decision_class,
            ),
            safety_critical_facts=SafetyCriticalFacts(
                account=self._account,
                instrument=self._instrument,
                direction=self._direction,
                quantity_basis=self._quantity_basis,
                unit=self._unit,
            ),
        )
        assert isinstance(capsule, DecisionContextCapsule)
        return capsule
