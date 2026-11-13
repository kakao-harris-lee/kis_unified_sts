"""CP-3 legacy-side tooling (``tools/tos_cp3``).

This package is **legacy-side**: it lives outside ``tos/`` and therefore may
NOT import ``tos`` or ``tos_runtime`` — the import firewall is bidirectional
and ``tools/`` is in its reverse scan (``tools/tos_firewall_check.py``
TOS-FW-R; design
``docs/plans/2026-07-20-tos-boundary-and-import-firewall-design.md`` §3.2).

**B3 대조는 은퇴했다 (2026-11-13).** The post-session comparison against the
legacy Setup D witness — B2 (``emit_legacy_decisions.py``), B3
(``diff_decisions.py``), its automation (``post_session_b3.py``) and its
``tos``-side B1b runner — was deleted once P2-b measured the declarative
producer equivalent to the legacy one (626,745 cells, 0 mismatches: #1065 /
#1066), which is the condition
``docs/plans/2026-11-11-tos-platform-roadmap.md`` §7 결정 3 set for retiring it.
``shared/decision/setups/vwap_reversion.py`` itself stays frozen until
``TOS_PAPER_READY`` because ``produce_fields.py`` still drives it. The deleted
code is in git history.

Contents:

* :mod:`tools.tos_cp3.produce_fields` — B1a, the shared indicator producer:
  Parquet minute bars → per-bar integer/bool field JSONL + lineage sidecar,
  computed by driving the legacy ``SetupDVWAPReversion`` bar by bar. It is the
  one copy of the band math the CP-3 field stream runs, until the P2-c
  declarative producer (#1067 / #1068) replaces that drive.
* :mod:`tools.tos_cp3.session_inputs` — the two session-derived inputs:
  the ``raw_event_id`` set the runtime actually consumed (from the session
  ``marketfeed.sqlite3``'s ``preimages``) with a reason for every produced bar
  it did not consume, and one record per live decision shaped like the retired
  B1b runner's offline trace (from the session ``evidence.sqlite3``, keyed to
  its bar through the ``inbox.sqlite3`` tick that carries both the capsule id the
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
* :mod:`tools.tos_cp3.minute_probe` — what is left of PR-1's real quotation GET
  measurement tool (evidence
  ``docs/broker-profiles/evidence/2026-10-12-cp3-pr1-minute-probe/README.md``):
  the two bar-frame helpers the live producer imports. The probe half was
  deleted 2026-11-13, its measurement being finished.
* :mod:`tools.tos_cp3.live_producer` — ③, the real-time fifteen-field producer:
  one journal line per completed minute bar, with the values computed by B1a's
  own ``produce_bars``. It is the one producer
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

Plans: ``docs/plans/2026-10-07-tos-cp3-first-tenant-kickoff.md`` §3 (구축물 B1a)
and §5 steps 1-2; ``docs/plans/2026-10-09-tos-cp3-tenant-render-and-
boot-path-plan.md`` §2.5-§2.6 (the boot-proof pair). The B3 retirement is
``docs/plans/2026-11-11-tos-platform-roadmap.md`` §7 결정 3.
"""

from __future__ import annotations

#: Tool-suite version string recorded in every lineage sidecar. Bump on any
#: change that can alter produced field values or the lineage schema.
TOS_CP3_VERSION = "0.1.0"

__all__ = ["TOS_CP3_VERSION"]
