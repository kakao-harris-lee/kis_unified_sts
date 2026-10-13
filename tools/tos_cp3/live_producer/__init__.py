"""CP-3 ③ — the real-time fifteen-field producer (plan 2026-10-10 §3).

A host process that, during the session, appends ONE journal line per completed
one-minute bar of the mini KOSPI200 front month. The line's shape is B1a's
(:mod:`tools.tos_cp3.produce_fields`) and the fifteen field values are computed
by **the same function** (``produce_bars``) — three keys differ (plan §1):

=============  ==============================  ==============================
key            B1a (offline)                   ③ (real time)
=============  ==============================  ==============================
``as_of_ms``   the bar label                   the wall clock read INSIDE the
                                               journal write, immediately
                                               before the replace (§2 1-2)
``source_id``  ``tos-cp3-b1a/<ver>``           ``tos-cp3-live/<ver>``
``received_ms``  absent                        when the REST response arrived
=============  ==============================  ==============================

**Where the stamp is taken, precisely** (plan §2 1-2; review B1). ``build_line``
runs ``produce_bars`` and returns a row with NO ``as_of_ms``;
``ObservationJournal.append`` reads the clock and refuses a row that already
carries one. The tenant tree allows ``max_age_ms: 800`` with 300 ms for the
collector while ``produce_bars`` was measured at ~0.44 s late in a session, so
a stamp taken before that compute would be stale on arrival however fast the
write is. M6 therefore measures stamp → temp write → ``os.replace`` only;
everything earlier is decision latency (M2).

**One published line per boundary, and never a stale bar** (plan §2 4, §3.3;
reviews M1 and N1). Every completed bar is frozen into the frame and written to
Parquet — B1a reads that frame, so parity needs each bar to advance the causal
windows exactly once — but at most ONE line is written per boundary, for
``boundary - 1min`` or, when a poll comes back after a NEWER bar has completed
too, for the newest bar of that response as a catch-up (plan §2 4's 「가장 최근
완성 봉 하나만」); the boundary that catch-up already covered then returns without
polling. A bar that completes after its own boundary passed is counted
``late_completed`` and left unpublished: a fresh stamp on a stale bar is what
the runtime would consume as the current observation.

``raw_event_id`` and the fifteen ``FIELD_ORDER`` keys come from B1a's own
helpers, so the same bar's real-time and offline lines join in B3.

Modules:

* :mod:`~tools.tos_cp3.live_producer.config` — every tunable (δ, G, poll pace,
  retry counts, the two parser env pins, the consecutive-``produce_error``
  stop, the seed horizon) with its evidence citation. Nothing is hardcoded.
* :mod:`~tools.tos_cp3.live_producer.calendar` — trading days and the session
  window, read from the TENANT calendar tree (plan §3.2: NOT
  ``shared/collector/historical/calendar.py``, whose hardcoded holiday set is
  missing two 2026 substitute holidays).
* :mod:`~tools.tos_cp3.live_producer.frame` — bar completion on RAW rows, the
  frozen frame, and the window-filled seed.
* :mod:`~tools.tos_cp3.live_producer.sinks` — the atomically replaced
  observation journal (``flock``-held, monotone ``as_of_ms``) and the
  append-only Parquet part writer that is B3's offline input.
* :mod:`~tools.tos_cp3.live_producer.producer` — the pure ``build_line`` plus
  the thin outer loop (HTTP + file replacement) and the CLI.

Out of scope here (PR-3): the runner's boot order and EXIT cleanup, the
runtime's credential isolation, the consumed-id / live-decision extractors, and
the runbook step for delayed-open days.

Firewall: legacy side. ``shared.*`` is allowed, ``tos`` / ``tos_runtime`` is
NOT (``tools/tos_firewall_check.py`` TOS-FW-R). The journal row shape mirrors
the runtime reader through B1a's own mirrored literal, and
``tos/runtime/tests/marketfeed/test_journal_cp3_live_producer_row.py`` proves
the real reader accepts the committed fixture this package reproduces.

GET-only: the only broker call is the allowlisted quotation TR in
:mod:`tools.tos_cp3.quote_client`. ``shared.execution`` and
``tools.broker_probes.probes_real_order`` are absent from this package's whole
import graph, and ``tests/tools/test_cp3_live_producer.py`` pins that.
"""

from __future__ import annotations

from tools.tos_cp3.live_producer.config import (
    LiveProducerConfig,
    LiveProducerRefused,
)

__all__ = ["LiveProducerConfig", "LiveProducerRefused"]
