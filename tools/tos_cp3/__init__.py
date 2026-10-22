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
* :mod:`tools.tos_cp3.session_inputs` — §3.6's two session-derived B3 inputs:
  the ``raw_event_id`` set the runtime actually consumed (from the session
  ``marketfeed.sqlite3``'s ``preimages``) with a reason for every produced bar
  it did not consume, and one record per live decision shaped like B1b's
  offline trace (from the session ``evidence.sqlite3``, keyed to its bar
  through the ``inbox.sqlite3`` tick that carries both the capsule id the
  decision names and the snapshot id the bar came from). All three stores are
  read as plain sqlite files in ``mode=ro`` — the firewall forbids importing
  ``tos_runtime`` from here, so the schema versions, the columns read AND the
  stored ``payload_json`` bytes are pinned against a committed hinge the
  runtime side produces and checks
  (``tos/runtime/tests/fixtures/cp3-session-store-reads.json``).
* :mod:`tools.tos_cp3.quote_client` — the GET-only real-key minute quotation
  transport (``FHKIF03020200``): a three-way method/TR/path allowlist, an
  app-key-fingerprinted private token cache, bounded retries and a token-expiry
  re-issue. Extracted from PR-1's probe so ③ reuses the measured client rather
  than growing a second one. There is no POST code path in it.
* :mod:`tools.tos_cp3.minute_probe` — PR-1, the real quotation GET measurement
  tool that derived δ and G (evidence
  ``docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md``).
* :mod:`tools.tos_cp3.live_producer` — ③, the real-time fifteen-field producer:
  one journal line per completed minute bar, with the values computed by B1a's
  own ``produce_bars`` so the same bar's real-time and offline lines join in
  B3. It is the one producer
  :data:`tools.tos_cp3.bootproof_guard.APPROVED_REAL_PRODUCER_PREFIXES`
  approves to create a permanent corpus.
* :mod:`tools.tos_cp3.bootproof_journal` — the tenant boot-proof journal: ONE
  row carrying a chosen B1a bar's fifteen fields, re-labelled onto the rendered
  mini contract and stamped with the WRITE time. It proves the tenant wiring
  before ③ (the real-time producer) exists; it does not prove field
  consumption.
* :mod:`tools.tos_cp3.bootproof_guard` — the data-dir refusal those boot proofs
  share with ``runners/run_tenant_session.sh``, as an **allowlist**: the
  resident durable set is never a target; the designated tenant sets open only
  when EVERY row's ``source_id`` is from an approved real producer (that list is
  empty until ③ lands); everything else must be a fresh, empty directory under
  the scratch root. Stdlib-only, so the shell template can call it as a guard.
* ``tools/tos_cp3/runners/run_tenant_session.sh`` — the tracked tenant session
  template, with the same checkout guards as
  ``tools/broker_probes/runners/run_p_ca.sh``, sourced from that file. Since
  PR-3 its order is producer → first real journal row (bounded wait) → guard →
  render → boot → stop (plan §3.5): the guard refuses an empty journal, and the
  producer is what fills it. The stop path is armed BEFORE the producer starts,
  as an EXIT trap as well as a signal trap, so no refusal between them can
  leave a producer calling the real quotation API unattended.

Plans: ``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §3 (구축물 B1a,
B2, B3) and §5 steps 1-2; ``docs/plans/2026-10-09-tos-cp3-tenant-render-and-
boot-path-plan.md`` §2.5-§2.6 (the boot-proof pair). Procedure: runbook
``docs/runbooks/tos-paper-boot-history.md`` §7.2-c.
"""

from __future__ import annotations

#: Tool-suite version string recorded in every lineage sidecar. Bump on any
#: change that can alter produced field values or the lineage schema.
TOS_CP3_VERSION = "0.1.0"

__all__ = ["TOS_CP3_VERSION"]
