"""``tos_runtime.safety`` — the runtime safety modules that survived plan S2-a
(``docs/plans/2026-11-13-tos-code-halving-plan.md``).

* :mod:`.monitoring` — the slim monitor (evidence-tip stall + inbox backlog) that owns
  the MONITORING currentness dimension and emits ``STM_ALERT``.
* :mod:`.ack` — operator acknowledgement of one ``STM_ALERT`` row.
* :mod:`.latch` — the restrictive-latch / capacity owners (egress item 16).
* :mod:`.rearm` — the new-risk-halt clear door (one custody-gated operator approval).
* :mod:`.shutdown` — controlled shutdown: latch first, then close, then record.

The safety-mesh services (spg profile, wdr deviation, sir incident, the ``tos.stm``
coverage manifest, ``tos.protective``, ``tos.liveauth``, ``tos.hag``) were removed with
their kernel packages: their judgement inputs were static YAML constants in every shipped
tenant tree. Modules import their siblings by full path so this package's import graph
stays a DAG; nothing is re-exported here.
"""
