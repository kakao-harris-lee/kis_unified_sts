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
* :mod:`tools.tos_cp3.emit_legacy_decisions` — B2, the legacy per-bar
  candidate/reject emitter: the same bars (B1a's own ``load_window`` and join
  keys) → per-bar ``FIRED``/reject-reason JSONL + lineage, plus the
  walk-forward harness's single-position verdict per bar.
* :mod:`tools.tos_cp3.diff_decisions` — B3, the decision-level diff: B1a's
  fields, B2's outcomes and B1b's trace (read as a FILE — B1b lives inside
  ``tos/``) joined bar by bar → per-bar bucket + declared-difference
  attribution JSONL, a ``summary.json`` difference report, and lineage. It
  imports neither ``tos`` nor ``produce_fields``: its claim is about three
  files, so it must stay runnable after CP-4 removes the band math behind
  them.
* :mod:`tools.tos_cp3.bootproof_journal` — the tenant boot-proof journal: ONE
  row carrying a chosen B1a bar's fifteen fields, re-labelled onto the rendered
  mini contract and stamped with the WRITE time. It proves the tenant wiring
  before ③ (the real-time producer) exists; it does not prove field
  consumption.
* :mod:`tools.tos_cp3.bootproof_guard` — the refusal those boot proofs share
  with ``runners/run_tenant_session.sh``: a journal carrying the
  ``cp3-bootproof-synthetic`` marker on ANY row may only genesis a fresh, empty
  directory under the scratch root. Stdlib-only, so the shell template can call
  it as a guard.
* ``tools/tos_cp3/runners/run_tenant_session.sh`` — the tracked tenant session
  template (render → boot → stop), with the same checkout guards as
  ``tools/broker_probes/runners/run_p_ca.sh``, sourced from that file.

Plans: ``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §3 (구축물 B1a,
B2, B3) and §5 steps 1-2; ``docs/plans/2026-10-09-tos-cp3-tenant-render-and-
boot-path-plan.md`` §2.5-§2.6 (the boot-proof pair). Procedure: runbook
``docs/runbooks/tos-paper-boot.md`` §7.2-c.
"""

from __future__ import annotations

#: Tool-suite version string recorded in every lineage sidecar. Bump on any
#: change that can alter produced field values or the lineage schema.
TOS_CP3_VERSION = "0.1.0"

__all__ = ["TOS_CP3_VERSION"]
