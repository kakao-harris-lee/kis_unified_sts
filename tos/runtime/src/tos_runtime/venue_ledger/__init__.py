"""The synthetic venue's own durable record (plan 2026-10-31 §3.1, 안 A).

The kernel's ``tos.brokeradapter.synthetic.SyntheticPaperTransport`` is a pure function —
"network 0, credentials 0, route 0", "no clock, no RNG, no ambient state" — so it keeps **no
durable record of what it accepted**. That absence is why the synthetic tree's only
``BrokerWitness`` (``tos_runtime.recon.witness_synthetic.SyntheticLedgerWitness``) has to re-read
the evidence store, declares ``independent_of_evidence_store=False``, and can therefore never
corroborate a capacity release (#1011 §1 F1-F4).

This package supplies the missing record rather than relaxing the rule: a **separate sqlite
file**, written at the transport boundary by :class:`~tos_runtime.venue_ledger.synthetic
.RecordingSyntheticTransport` before the result is returned, and read by
:class:`~tos_runtime.recon.witness_synthetic_venue.SyntheticVenueLedgerWitness` — a different
file, a different writer, and nothing derived from an evidence row.

Firewall: stdlib (``os``, ``re``, ``sqlite3``, ``datetime``, ``decimal``) + ``tos.*`` +
``tos_runtime.operations.schema_ledger`` only. No ``shared.*``, no network, no ``os.environ``.
"""

from __future__ import annotations

from tos_runtime.venue_ledger.synthetic import (
    VENUE_LEDGER_FILE_NAME,
    VENUE_LEDGER_SCHEMA_VERSION,
    RecordingSyntheticTransport,
    SyntheticVenueLedger,
    VenueLedgerFill,
    VenueLedgerReader,
    VenueLedgerWriteFailed,
    valid_trading_date,
)

__all__ = [
    "VENUE_LEDGER_FILE_NAME",
    "VENUE_LEDGER_SCHEMA_VERSION",
    "RecordingSyntheticTransport",
    "SyntheticVenueLedger",
    "VenueLedgerFill",
    "VenueLedgerReader",
    "VenueLedgerWriteFailed",
    "valid_trading_date",
]
