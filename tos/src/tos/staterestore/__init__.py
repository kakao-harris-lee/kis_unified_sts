"""Durable composite-state store + conservative restart reload (EV-L3 pilot).

Realizes the ADR-002-005 §13 line 195-199 persistence-and-restart SHALLs on a **real
on-disk substrate**, per the ratified design contract
``docs/plans/2026-08-06-tos-ev-l3-pilot-design.md`` (v1.1) §5.1 S-1..S-4. This is the
first ``tos`` package that performs real I/O: the series' closed-world → open-world
transition (design #39 §2.1).

What this package adds, and what it deliberately does not
--------------------------------------------------------
It adds **local durable persistence only** — a sqlite3 file on the local filesystem.
It adds **no egress**: the tos-wide invariant ``tos/__init__.py`` line 6 verbatim
"This package is non-transmitting by construction (§4): no broker credentials, routes,
order-construction, or env-flag capability paths" is preserved unchanged (design #39
§5.1 MINOR-3 — *persistence (local disk) ≠ transmission (network egress)*). There is no
socket, no broker route, no credential, and no env-flag capability path here; the
firewall gate (``tools/tos_firewall_check.py``) mechanizes that as
``TOS-FW-B``/``TOS-FW-C``, and ``tos/tests/staterestore/test_staterestore_gaps.py``
locks it as an executable canary.

It is a **separate package, not a module inside** :mod:`tos.orthostate`: that package's
own docstring (line 11) states verbatim that it implements "**no** persistence / durable
restart", and adding a store there would falsify it. staterestore depends on orthostate
(one direction only); orthostate never references staterestore (design #39 OQ-4(i)).

Substrate decision and its status
---------------------------------
The store is stdlib ``sqlite3`` in WAL journal mode with ``synchronous=FULL`` (design
#39 §3.2 candidate A). This is a **pilot-scope** choice — the substrate an EV-L3
crash/restart run is executed against — and is explicitly **NOT** the ADR-002-005 §4
line 61 project persistence-technology decision ("This ADR does not decide the
persistence technology"), which remains an open governance gate (design #39 §3.3 /
OQ-1).

Crash model
-----------
:mod:`tos.staterestore._l3_worker` crashes with a deterministic ``os._exit`` at a
parametrized point (design #39 §4 / O-2 — *not* a racy external ``SIGKILL``). That
models an **application/process** crash faithfully; kernel page-cache loss, power loss,
and torn sectors are **not** modelled and are carried as residual R-D (§2.4).

Public surface
--------------
* :mod:`tos.staterestore.store` — :class:`CompositeStateStore`, the per-dimension
  durable marker store (S-1).
* :mod:`tos.staterestore.reload` — :func:`reload_conservative`, the restart read path
  (S-2 conservative fill + S-3 no-stale re-derivation).
* :mod:`tos.staterestore._l3_worker` — the ``python -m`` writer/reader entry point
  (S-4), parametrized by **argv only** (``os.environ`` / ``os.getenv`` are forbidden
  anywhere under ``tos/`` by TOS-FW-C).

⚠ Authoring is not evidence: this package closes no Evidence Register row. STATE-EV-004
remains NOT_IMPLEMENTED, and an executed EV-L3 stage covers its persistence + process +
reconstruction axes only — real network and real credential identity stay deferred
(design #39 §9; residuals R-N / R-I).
"""

from __future__ import annotations

from tos.staterestore.reload import (
    ABSENT_DIMENSION_FILL,
    IncompleteStoreError,
    RestartReconstruction,
    discard_caches,
    reload_conservative,
)
from tos.staterestore.store import (
    DIMENSION_COMMIT_ORDER,
    CompositeStateStore,
    StoreIntegrityError,
)

__all__ = [
    "ABSENT_DIMENSION_FILL",
    "CompositeStateStore",
    "DIMENSION_COMMIT_ORDER",
    "IncompleteStoreError",
    "RestartReconstruction",
    "StoreIntegrityError",
    "discard_caches",
    "reload_conservative",
]
