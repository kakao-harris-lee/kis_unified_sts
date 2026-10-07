"""CP-3 B1a–B3 legacy-side tooling (``tools/tos_cp3``).

This package is **legacy-side**: it lives outside ``tos/`` and therefore may
NOT import ``tos`` or ``tos_runtime`` — the import firewall is bidirectional
and ``tools/`` is in its reverse scan (``tools/tos_firewall_check.py``
TOS-FW-R; design
``docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md`` §3.2).
Anything that needs ``tos.backtest`` types (``Bar``, ``BacktestDriver``) is
B1b and lives inside ``tos/``; the two sides meet only through files.

Contents:

* :mod:`tools.tos_cp3.produce_fields` — B1a, the shared indicator producer:
  Parquet minute bars → per-bar integer/bool field JSONL + lineage sidecar,
  computed by driving the legacy ``SetupDVWAPReversion`` bar by bar so both
  sides of the CP-3 comparison run ONE copy of the band math.

Plan: ``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §3 (구축물 B1a)
and §5 step 1.
"""

from __future__ import annotations

#: Tool-suite version string recorded in every lineage sidecar. Bump on any
#: change that can alter produced field values or the lineage schema.
TOS_CP3_VERSION = "0.1.0"

__all__ = ["TOS_CP3_VERSION"]
