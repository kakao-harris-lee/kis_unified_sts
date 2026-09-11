"""``tos_runtime.safety.ports`` — the one shared shape every Phase 5 W3 safety-mesh
runtime owner implements (plan ``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md``
§2 decision 1).

**Why one shape.** Phase 5 plan §2 decision 5 fixes the four safety-mesh services
(``SafetyProfileService`` — spg / item 7, ``DeviationService`` — wdr / item 8,
``IncidentService`` — sir / item 9, ``MonitoringService`` — stm / item 10) to the SAME
form so that three consumers can be wired generically, never per-service:

(i)   the currentness owner seam — :meth:`SafetyMeshService.dimension_report` feeds one
      :class:`~tos_runtime.currentness.vector.DimensionReport` into the
      ``CurrentnessAssembler`` reader map for :attr:`SafetyMeshService.dimension_key`;
(ii)  the egress deferred-item input — :meth:`SafetyMeshService.clear` supplies the
      kernel's ``SendBoundaryContext`` field for the service's deferred item (kernel round
      #2, ``tos/src/tos/egressgw/mesh.py`` closed item↔field table);
(iii) the Coordinator's third question — the same :meth:`clear` values are AND-ed inside
      ``RuntimeCoordinatorPreconditions.live_scope_authorized`` for a broker-reaching
      transport (T2 lane B "two questions" idiom, kernel diff 0).

**Polarity contract (mirrors the kernel's own reading in ``mesh.deferred_item_verdict``).**
``clear()`` returns ``True`` only when the service's kernel predicates are positively
satisfied; ``False`` when a predicate is positively violated (an explicit negative — the
kernel records DENIED, never UNKNOWN); ``None`` when the fact cannot be established (the
kernel records UNKNOWN, a rejection under RFC-002 §10.8:761). Consumers compare with
``is True`` / ``is False`` — never truthiness.

**Verdict authorship is forbidden here.** An implementation combines kernel predicate
results; it never authors a currentness/safety comparison of its own (Phase 5 plan §2
decision 1 (b) and kernel round #1 §0 "판정은 커널 술어만 한다").

Pure Protocols + one frozen record: stdlib (``typing``, ``dataclasses``) + ``tos.cur``
(``DimensionKey``) + ``tos_runtime.currentness.vector`` (``DimensionReport``) only. No
``shared.*``, no ``os.environ``, no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from tos.cur import DimensionKey

from tos_runtime.currentness.vector import DimensionReport

__all__ = [
    "MeshClearance",
    "SafetyMeshService",
]


@dataclass(frozen=True)
class MeshClearance:
    """One service's :meth:`SafetyMeshService.clear` outcome with its evidence-facing
    reasons — what the Coordinator's third question and the deferred-item input both
    consume, and what ``COORDINATOR_MESH_HELD`` evidence records when non-positive.

    Attributes:
        identity: The reporting service's :attr:`SafetyMeshService.identity`.
        clear: The tri-state verdict (module docstring "Polarity contract").
        reasons: Deterministic, ordered reason tokens naming every predicate that was
            NOT positively satisfied (empty exactly when ``clear is True``). Never a
            secret, never a free-text operator string.
    """

    identity: str
    clear: bool | None
    reasons: tuple[str, ...]


@runtime_checkable
class SafetyMeshService(Protocol):
    """The shared runtime-owner shape (module docstring). Implementations live in
    :mod:`tos_runtime.safety.profile` / ``.deviation`` / ``.incident`` / ``.monitoring``.
    """

    @property
    def identity(self) -> str:
        """The ``owner_identity`` this service stamps on its dimension and evidence —
        a code constant per service, never configuration."""
        ...

    @property
    def dimension_key(self) -> DimensionKey:
        """The one §9 currentness dimension this service owns."""
        ...

    def dimension_report(self) -> DimensionReport | None:
        """This owner's currentness verdict for :attr:`dimension_key`, or ``None`` when
        it cannot be evaluated yet (the assembler then leaves the dimension absent, so
        ``vector_complete`` is ``False`` — never a fabricated positive)."""
        ...

    def clear(self) -> MeshClearance:
        """The deferred-item / Coordinator verdict (module docstring "Polarity
        contract"), evaluated fresh on every call — never cached across ticks."""
        ...

    def describe(self) -> Mapping[str, Any]:
        """Evidence-facing description of the loaded policy documents (names, digests,
        generations). Never credential bytes, never a bearer token."""
        ...
