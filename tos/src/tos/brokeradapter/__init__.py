"""Broker Adapter transport boundary + the synthetic paper transport (Phase 1, provisional).

Realizes the transport half of the vertical slice #1 contract
``docs/plans/2026-07-29-tos-egressgw-brokeradapter-design.md`` (design #34, v1.1): RFC-002
§10.8:739 — "Broker-specific behavior SHALL remain isolated behind the Broker Adapter boundary" —
and ADR-002-002 §11.4 step 18 (the network call).

Two modules:

* :mod:`tos.brokeradapter.protocol` — the :class:`~tos.brokeradapter.protocol.Transport` Protocol
  (**one verified outbound, one result**) and the :class:`~tos.brokeradapter.protocol.OutboundSendRequest`
  record an implementation assembles behind the boundary.
* :mod:`tos.brokeradapter.synthetic` — a deterministic **synthetic paper transport**: network 0,
  credentials 0, route 0.

**What is deliberately not here: the real broker path.** It is *designed* — the Protocol is
exactly its injection point, and the gateway's verify contract, credential/route isolation
(ADR-002-013 §4.5), and non-live-test binding (brokercap §4.7) all apply to it unchanged — but it
is **not implemented**, and cannot be: ``tos/`` forbids network stdlib (design #1 §2.3), so any
real transport necessarily lives outside ``tos/``. The network-absence canary over this package's
sources is the mechanical evidence for that claim (design #34 §0.3/§2.2-①).

**Why the slice executes the synthetic path** (design #34 §2, on the broker-reached / synthetic
axis — *not* live / non-live): a real paper-account API call is non-live and still
**broker-resource-consuming**, so RFC-002 §10.8:741 triggers the full 17-item verify list for it,
and with the deferred safety-governance mesh plus the P0-2-blocked Broker Capability Profile its
required facts are unverifiable ⇒ §10.8:761 rejection. The synthetic transport is the opposite
side of that axis — it consumes no broker resource — not a way around it.

⚠ **NON-AUTHORITATIVE; closes no EV.** A synthetic result is not evidence that any broker
accepted anything, because no broker was contacted. RFC-002 §10.8:763 forbids exposing a
general-purpose live-order method to strategy / research / simulation / backtest / operator
interfaces; this transport is structurally incapable of being one.

**No blind resubmission, by construction** (design #34 §5.4/§13). The Protocol has one single-shot
method with no retry count, no attempt index, and no idempotency key, so the two HIGH KIS quirks
(``Q-IDEMP-1`` three-attempt resend, ``Q-IDEMP-2`` token-expiry resend wrapper) are
unrepresentable against it. Authentication is not part of a send. A retry is a new attempt — new
permit, new currentness proof, new content-addressed identity, whole flow again.

Import closure (design #34 §0.3 — the series' narrowest)::

    {tos, tos.canonical, tos.ordering, tos.engine, tos.brokercap, tos.brokeradapter}

``tos.egressgw`` is deliberately outside it: the gateway injects itself into this boundary
through a structural port, never the reverse. Forbidden throughout: ``shared.*``, ``os.environ``
/ ``getenv``, **network stdlib**, dynamic import / ``exec`` / ``eval``, wall clock, and
``random`` / ``secrets`` / ``uuid``.
"""

from __future__ import annotations

from tos.brokeradapter.protocol import OutboundSendRequest, Transport
from tos.brokeradapter.synthetic import (
    FILL_CONTEXT,
    NON_FILL_DECLARABLE_KINDS,
    SyntheticFillPolicy,
    SyntheticPaperTransport,
    synthetic_transport_nature_fields,
)

__all__ = [
    "FILL_CONTEXT",
    "NON_FILL_DECLARABLE_KINDS",
    "OutboundSendRequest",
    "SyntheticFillPolicy",
    "SyntheticPaperTransport",
    "Transport",
    "synthetic_transport_nature_fields",
]
