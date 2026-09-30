"""``tos_runtime.safety`` — Phase 5 W3 safety-mesh runtime owners (plan
``docs/plans/2026-09-11-tos-phase5-w3-safety-mesh-plan.md``).

Sub-modules (one file per lane, plan §4):

* :mod:`.ports` — the shared :class:`~tos_runtime.safety.ports.SafetyMeshService`
  Protocol + :class:`~tos_runtime.safety.ports.MeshClearance` (team-lead authored; the
  one contract every lane codes against).
* :mod:`.profile` (spg · item 7), :mod:`.deviation` (wdr · item 8) — lane W3-a1.
* :mod:`.incident` (sir · item 9), :mod:`.monitoring` (stm · item 10) — lane W3-a2.
* :mod:`.latch`, :mod:`.rearm` — lane W3-c (restrictive-latch / capacity owners and the
  HAG two-person re-arm workflow).

Only the shared port is re-exported here; lanes import their siblings by full path so
this package's import graph stays a DAG.
"""

from tos_runtime.safety.ports import MeshClearance, SafetyMeshService

__all__ = ["MeshClearance", "SafetyMeshService"]
