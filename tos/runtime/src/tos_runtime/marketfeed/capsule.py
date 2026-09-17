"""``tos_runtime.marketfeed.capsule`` — the Decision Context Capsule issuer (TOS tick-source
wave, plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decision 1).

:class:`CapsuleIssuer` binds one issued :class:`~tos.capsule.CriticalInputSnapshot` (from
:mod:`tos_runtime.marketfeed.snapshot`) into a kernel-issued
:class:`~tos.capsule.DecisionContextCapsule`, the shape
:class:`~tos.marketfeed.MarketFeedContextResolver` actually consumes
(``tos/src/tos/marketfeed/resolver.py:135``). Every deployment fact is injected at construction —
no literal is hard-coded in this module, per the repo's config-driven-only rule (root
``CLAUDE.md`` "Non-Negotiable Rules").

**``environment`` (addition beyond the task's literal constructor-param list, reported).** The
task's own enumeration of ``CapsuleIssuer``'s injected facts was ``account``, ``instrument``,
``decision_class``, ``direction``, ``quantity_basis``, ``unit``, ``issuer_principal_id``, and the
policy ref — no ``environment``. But
:attr:`~tos.capsule.DecisionContextCapsule._REQUIRED_COVERED` lists ``scope.environment`` as a
safety-load-bearing field that MUST be concrete to issue (``tos/src/tos/capsule/capsule.py``) —
without it, ``DecisionContextCapsule.issue`` raises ``CapsuleIntegrityError`` unconditionally, for
every deployment. This constructor therefore also takes ``environment``, injected like every other
fact; there was no way to satisfy the kernel's own issuance gate without it.

Firewall (R1, runtime scope): stdlib + ``tos.*`` only — no ``shared.*``, no network, no clock.
"""

from __future__ import annotations

from tos.canonical import CanonicalizationScheme
from tos.capsule import CriticalInputSnapshot, DecisionContextCapsule, PolicyRef
from tos.capsule.capsule import CapsuleScope, SafetyCriticalFacts, SnapshotRef

__all__ = [
    "CapsuleIssuanceError",
    "CapsuleIssuer",
]


class CapsuleIssuanceError(RuntimeError):
    """Refused to issue a capsule for a snapshot whose ``snapshot_id``/``canonical_digest`` is
    not yet concrete (module docstring; ``SnapshotRef`` would otherwise bind a null reference).
    """


class CapsuleIssuer:
    """Issues one :class:`~tos.capsule.DecisionContextCapsule` per issued snapshot, for one fixed
    per-deployment (account, instrument) pair (module docstring)."""

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
        """Bind ``snapshot`` into a Decision Context Capsule (module docstring).

        Args:
            snapshot: The issued snapshot to bind — its ``snapshot_id``/``canonical_digest`` must
                both be concrete (an issued :class:`~tos.capsule.CriticalInputSnapshot` always
                has both; this refuses a draft/placeholder passed in error).

        Returns:
            The issued capsule.

        Raises:
            CapsuleIssuanceError: ``snapshot.snapshot_id`` or ``snapshot.canonical_digest`` is
                ``None``.
        """
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
