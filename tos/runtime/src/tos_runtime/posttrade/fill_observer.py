"""Post-ACK fill observer for the KIS 모의투자 stock order path (PR-3b, rescope plan §3 M2).

``KisMockTransport`` maps an order reply to ``ACK``/``REJECT``/``UNKNOWN``/``TIMEOUT`` only; what
happens to an ACKed order afterwards is only visible on 주식일별주문체결조회 (``VTTC0081R``, GET,
mock host). This module polls that TR for the ODNOs this runtime holds an ACK for, and turns what
it reads into ``PARTIAL_FILL``/``FULL_FILL``/``CANCEL_ACK``/``UNKNOWN`` results for the engine's
normal result path (``EGRESS_RESULT`` through the durable inbox, then finality and release).

**What it tracks comes from durable evidence, not memory.** An attempt is tracked when an
``EGRESS_RESULT_CONSUMED`` row records its ``ACK`` with an ODNO and a trading date; it stops being
tracked once a terminal result (``FULL_FILL``/``CANCEL_ACK``/``EXPIRED``/``REJECT``) is recorded
for it. What was already reported is the latest recorded result for that attempt. So a restart
re-derives the same picture, and an execution observed twice is reported once.

**Attribution.** A row belongs to an attempt only when its ``odno`` equals the ACK's ODNO (both
sides canonicalized: whitespace and leading zeros dropped, ASCII digits only — measured
encodings differ, ``tools/broker_probes/probes_order.py::odno_key``) AND its ``ord_dt`` equals the
ACK's trading date (a KIS ODNO is a per-day sequence). The emitted result carries the ACK's ODNO
and date verbatim, so every receipt of the attempt names one broker order. A row that matches no
ACK this runtime recorded is recorded as ``FILL_OBSERVER_UNATTRIBUTED_ORDER`` and never enqueued —
and the release reconciliation then sees it as an orphan broker order, which blocks release.

**Fail closed.** A row whose ``ord_qty`` is not the attempt's sealed quantity
(``SEND_SEALED``), whose quantities do not parse or do not add up (``tot_ccld_qty + rmn_qty !=
ord_qty``), a rejected quantity, a cancel after a fill, two rows for one ODNO, a
cancel/modify row pointing at the order (``orgn_odno``), or a filled quantity smaller than one
already reported → ``UNKNOWN`` (the engine quarantines). Never a guessed fill. No row for the ODNO
yet is not evidence of anything: nothing is emitted, and after ``overdue_after_ms`` one
``FILL_OBSERVER_OVERDUE`` row is recorded.

GET only, mock host only: the reads go through
:meth:`~tos_runtime.recon.witness_kis.KisStockBrokerWitness.order_rows`, whose host and TR id are
sealed at load (mock ``V``-prefixed TR, the order transport's own mock host). This module never
sends anything to a broker.

Firewall: stdlib + ``pyyaml`` + ``tos.engine`` + ``tos_runtime.*`` only.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol

import yaml
from tos.engine.records import EgressResultPayload, InstrumentKey
from tos.engine.vocabulary import EgressResultKind, ResultDisposition

from tos_runtime._named_tbd import reject_named_tbd
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recon.ports import WitnessScope, WitnessUnavailable
from tos_runtime.recon.witness_kis import KisOrderRow
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "FILL_OBSERVED_KIND",
    "FILL_OBSERVER_CONFIG_NAME",
    "FILL_OBSERVER_OVERDUE_KIND",
    "FILL_OBSERVER_READ_FAILED_KIND",
    "FILL_OBSERVER_UNATTRIBUTED_KIND",
    "FillObserverConfig",
    "FillObserverConfigError",
    "FillPollReport",
    "KisMockFillObserver",
    "load_fill_observer_config",
    "odno_key",
]

FILL_OBSERVER_CONFIG_NAME = "fill_observer.yaml"

FILL_OBSERVED_KIND = "FILL_OBSERVED"
FILL_OBSERVER_UNATTRIBUTED_KIND = "FILL_OBSERVER_UNATTRIBUTED_ORDER"
FILL_OBSERVER_READ_FAILED_KIND = "FILL_OBSERVER_READ_FAILED"
FILL_OBSERVER_OVERDUE_KIND = "FILL_OBSERVER_OVERDUE"

_RESULT_KINDS = ("EGRESS_RESULT_CONSUMED", "RESULT_UNMATCHED")
_TERMINAL_KINDS = frozenset(
    {
        EgressResultKind.FULL_FILL,
        EgressResultKind.CANCEL_ACK,
        EgressResultKind.EXPIRED,
        EgressResultKind.REJECT,
    }
)


class FillObserverConfigError(Exception):
    """``fill_observer.yaml`` is missing, malformed, or has a non-positive bound."""


@dataclass(frozen=True)
class FillObserverConfig:
    """The observer's cadence and bounds plus the witness fields it seals (module docstring).

    Attributes:
        witness_fields: The GET-only witness fields (TR ids, paths, ``max_pages``) — validated
            by :func:`~tos_runtime.recon.witness_kis_config.kis_witness_config_from_mapping`
            together with the order transport's own sealed host.
        poll_interval_ms: Minimum spacing between two order-inquiry polls
            (:meth:`KisMockFillObserver.poll_if_due`), on the injected monotonic clock.
        overdue_after_ms: How long an ACKed attempt may show no terminal row before one
            ``FILL_OBSERVER_OVERDUE`` row is recorded (record only — nothing is guessed).
    """

    witness_fields: dict[str, Any]
    poll_interval_ms: int
    overdue_after_ms: int


_WITNESS_KEYS = (
    "balance_path",
    "balance_tr_id",
    "order_inquiry_path",
    "order_inquiry_tr_id",
    "max_pages",
)


def _positive_int(raw: dict[str, Any], key: str, path: Path) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise FillObserverConfigError(
            f"{path}: {key!r} must be a positive int, got {value!r}"
        )
    return value


def load_fill_observer_config(path: Path) -> FillObserverConfig:
    """Load ``fill_observer.yaml``, fail-closed.

    Raises:
        FillObserverConfigError: The file is absent, not a mapping, misses a key, or carries a
            non-positive bound.
    """
    if not path.is_file():
        raise FillObserverConfigError(f"fill observer config not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise FillObserverConfigError(f"{path}: unreadable ({exc})") from exc
    if not isinstance(raw, dict):
        raise FillObserverConfigError(f"{path}: must be a top-level mapping")
    missing = [key for key in _WITNESS_KEYS if key not in raw]
    if missing:
        raise FillObserverConfigError(f"{path}: missing {missing}")
    for key in _WITNESS_KEYS:
        # The witness config loader re-checks every one of these; refusing the placeholder here
        # names THIS file in the error rather than the witness's.
        reject_named_tbd(
            raw[key], field=key, context=str(path), error_cls=FillObserverConfigError
        )
    return FillObserverConfig(
        witness_fields={key: raw[key] for key in _WITNESS_KEYS},
        poll_interval_ms=_positive_int(raw, "poll_interval_ms", path),
        overdue_after_ms=_positive_int(raw, "overdue_after_ms", path),
    )


def odno_key(raw: str | None) -> str | None:
    """Canonical comparison key for a KIS ODNO: whitespace and leading zeros dropped (a single
    ``"0"`` kept); ``None`` for an absent, all-zero, or non-ASCII-digit value — a value that is
    not an order number never matches one (``tools/broker_probes/probes_order.py::odno_key``
    measured why both sides must be canonicalized)."""
    text = (raw or "").strip()
    if not text or not (text.isascii() and text.isdigit()):
        return None
    key = text.lstrip("0")
    return key or None


class OrderRowsReader(Protocol):
    """:meth:`~tos_runtime.recon.witness_kis.KisStockBrokerWitness.order_rows`."""

    def order_rows(
        self, scope: WitnessScope
    ) -> tuple[str, tuple[KisOrderRow, ...]]: ...


#: Feeds one result into the engine and returns its disposition (compose supplies it).
ResultSink = Callable[[EgressResultPayload], "ResultDisposition | None"]


@dataclass
class _Tracked:
    """One ACKed attempt as durable evidence describes it."""

    attempt_id: str
    instrument_key: InstrumentKey
    odno: str
    trading_date: str
    last_kind: EgressResultKind = EgressResultKind.ACK
    last_filled: Decimal | None = None
    last_remaining: Decimal | None = None
    max_filled: Decimal = Decimal("0")
    terminal: bool = False
    #: ``SEND_SEALED.send_seal.outbound_quantity`` — what was actually put on the wire.
    sealed_quantity: Decimal | None = None


@dataclass(frozen=True)
class FillPollReport:
    """What one :meth:`KisMockFillObserver.poll_once` did."""

    polled: bool
    emitted: tuple[tuple[str, EgressResultKind, ResultDisposition | None], ...] = ()
    unattributed: tuple[str, ...] = ()
    read_failed: bool = False


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@dataclass
class KisMockFillObserver:
    """Polls ``VTTC0081R`` for ACKed ODNOs and feeds what it reads to the engine (module
    docstring)."""

    config: FillObserverConfig
    orders: OrderRowsReader
    evidence_store: SqliteEvidenceStore
    result_sink: ResultSink
    monotonic: MonotonicSource
    account: str
    instrument: str
    _last_poll_ms: int | None = field(default=None, init=False)
    _first_pending_ms: dict[str, int] = field(default_factory=dict, init=False)
    _overdue_recorded: set[str] = field(default_factory=set, init=False)
    _last_read_failed: bool = field(default=False, init=False)

    # -- entry points --------------------------------------------------------------------

    def poll_if_due(self) -> FillPollReport:
        """:meth:`poll_once` when ``poll_interval_ms`` has passed since the last poll."""
        now = self.monotonic.now_ms()
        if (
            self._last_poll_ms is not None
            and now - self._last_poll_ms < self.config.poll_interval_ms
        ):
            return FillPollReport(polled=False)
        return self.poll_once()

    def poll_once(self) -> FillPollReport:
        """One poll: no GET at all when no ACKed attempt is outstanding."""
        tracked = self._tracked_attempts()
        pending = [t for t in tracked.values() if not t.terminal]
        if not pending:
            return FillPollReport(polled=False)
        self._last_poll_ms = self.monotonic.now_ms()
        scope = WitnessScope(
            account=self.account,
            instrument_keys=(
                InstrumentKey(account=self.account, instrument=self.instrument),
            ),
            attempt_ids=tuple(t.attempt_id for t in pending),
        )
        try:
            today, rows = self.orders.order_rows(scope)
        except WitnessUnavailable as exc:
            if not self._last_read_failed:
                self._record(FILL_OBSERVER_READ_FAILED_KIND, {"reason": str(exc)[:200]})
            self._last_read_failed = True
            return FillPollReport(polled=True, read_failed=True)
        self._last_read_failed = False
        unattributed = self._flag_unattributed(rows, tracked)
        emitted = []
        for attempt in pending:
            if attempt.trading_date != today:
                continue  # the inquiry covers today only; an older ACK cannot be read here
            payload, reason = self._classify(attempt, rows)
            if payload is None:
                self._check_overdue(attempt)
                continue
            self._record(
                FILL_OBSERVED_KIND,
                {
                    "attempt_id": attempt.attempt_id,
                    "broker_execution_id": attempt.odno,
                    "trading_date": attempt.trading_date,
                    "kind": payload.kind.value,
                    "filled_quantity": _text(payload.filled_quantity),
                    "remaining_quantity": _text(payload.remaining_quantity),
                    "reason": reason,
                },
            )
            disposition = self.result_sink(payload)
            emitted.append((attempt.attempt_id, payload.kind, disposition))
        return FillPollReport(
            polled=True, emitted=tuple(emitted), unattributed=unattributed
        )

    # -- durable picture -------------------------------------------------------------------

    def _tracked_attempts(self) -> dict[str, _Tracked]:
        placeholders = ",".join("?" for _ in _RESULT_KINDS)
        rows = self.evidence_store.connection.execute(
            f"SELECT kind, payload_json FROM entries WHERE kind IN ({placeholders}) "
            "ORDER BY seq ASC",
            _RESULT_KINDS,
        ).fetchall()
        tracked: dict[str, _Tracked] = {}
        for evidence_kind, payload_json in rows:
            row = json.loads(payload_json).get("payload", {})
            key = row.get("instrument_key") or {}
            if key.get("account") != self.account or key.get("instrument") != (
                self.instrument
            ):
                continue
            attempt_id = row.get("attempt_id")
            try:
                kind = EgressResultKind(row.get("egress_result_kind"))
            except ValueError:
                continue
            if not isinstance(attempt_id, str):
                continue
            if attempt_id not in tracked:
                if (
                    evidence_kind == "EGRESS_RESULT_CONSUMED"
                    and kind is EgressResultKind.ACK
                    and isinstance(row.get("broker_execution_id"), str)
                    and isinstance(row.get("trading_date"), str)
                ):
                    tracked[attempt_id] = _Tracked(
                        attempt_id=attempt_id,
                        instrument_key=InstrumentKey(
                            account=self.account, instrument=self.instrument
                        ),
                        odno=row["broker_execution_id"],
                        trading_date=row["trading_date"],
                    )
                continue
            attempt = tracked[attempt_id]
            filled = _decimal(row.get("filled_quantity"))
            attempt.last_kind = kind
            attempt.last_filled = filled
            attempt.last_remaining = _decimal(row.get("remaining_quantity"))
            if filled is not None and filled > attempt.max_filled:
                attempt.max_filled = filled
            if kind in _TERMINAL_KINDS:
                attempt.terminal = True
        for attempt_id, quantity in self._sealed_quantities().items():
            if attempt_id in tracked:
                tracked[attempt_id].sealed_quantity = quantity
        return tracked

    def _sealed_quantities(self) -> dict[str, Decimal | None]:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = 'SEND_SEALED'"
        ).fetchall()
        sealed: dict[str, Decimal | None] = {}
        for (payload_json,) in rows:
            seal = json.loads(payload_json).get("payload", {}).get("send_seal") or {}
            attempt_id = seal.get("attempt_id")
            if isinstance(attempt_id, str):
                sealed[attempt_id] = _decimal(seal.get("outbound_quantity"))
        return sealed

    def _flag_unattributed(
        self, rows: tuple[KisOrderRow, ...], tracked: dict[str, _Tracked]
    ) -> tuple[str, ...]:
        known = {(odno_key(t.odno), t.trading_date) for t in tracked.values()}
        already = self._recorded_unattributed()
        flagged = []
        for row in rows:
            identity = (odno_key(row.odno), row.ord_dt)
            if identity in known or (odno_key(row.orgn_odno), row.ord_dt) in known:
                continue
            label = f"{row.odno}@{row.ord_dt}"
            if label not in already:
                self._record(
                    FILL_OBSERVER_UNATTRIBUTED_KIND,
                    {
                        "broker_execution_id": row.odno,
                        "order_date": row.ord_dt,
                        "instrument": row.pdno,
                        "tot_ccld_qty": _text(row.tot_ccld_qty),
                    },
                )
                already.add(label)
            flagged.append(label)
        return tuple(flagged)

    def _recorded_unattributed(self) -> set[str]:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_UNATTRIBUTED_KIND,),
        ).fetchall()
        labels = set()
        for (payload_json,) in rows:
            row = json.loads(payload_json).get("payload", {})
            labels.add(f"{row.get('broker_execution_id')}@{row.get('order_date')}")
        return labels

    # -- one attempt -------------------------------------------------------------------

    def _classify(
        self, attempt: _Tracked, rows: tuple[KisOrderRow, ...]
    ) -> tuple[EgressResultPayload | None, str]:
        """The result to emit for ``attempt``, or ``None`` (nothing new / not visible yet)."""
        key = odno_key(attempt.odno)
        mine = [
            r
            for r in rows
            if odno_key(r.odno) == key and r.ord_dt == attempt.trading_date
        ]
        derived = [
            r
            for r in rows
            if odno_key(r.orgn_odno) == key and r.ord_dt == attempt.trading_date
        ]
        if not mine and not derived:
            return None, "not_visible"
        if len(mine) != 1:
            return self._unknown(attempt, "ambiguous_rows")
        if derived:
            return self._unknown(attempt, "derived_order_row")
        if (
            attempt.sealed_quantity is None
            or mine[0].ord_qty != attempt.sealed_quantity
        ):
            # The row's 주문수량 must be what this attempt sealed and sent — otherwise it is not
            # this order as we know it, whatever its number says.
            return self._unknown(attempt, "ordered_quantity_mismatch")
        kind, filled, remaining, reason = _fill_state(mine[0])
        if kind is None:
            return None, reason  # still working, nothing executed yet
        if kind is EgressResultKind.UNKNOWN:
            return self._unknown(attempt, reason)
        if filled is not None and filled < attempt.max_filled:
            return self._unknown(attempt, "fill_regressed")
        if (kind, filled, remaining) == (
            attempt.last_kind,
            attempt.last_filled,
            attempt.last_remaining,
        ):
            return None, "already_reported"
        return self._payload(attempt, kind, filled, remaining), reason

    def _unknown(
        self, attempt: _Tracked, reason: str
    ) -> tuple[EgressResultPayload | None, str]:
        if attempt.last_kind is EgressResultKind.UNKNOWN:
            return None, "already_reported"
        return self._payload(attempt, EgressResultKind.UNKNOWN, None, None), reason

    @staticmethod
    def _payload(
        attempt: _Tracked,
        kind: EgressResultKind,
        filled: Decimal | None,
        remaining: Decimal | None,
    ) -> EgressResultPayload:
        return EgressResultPayload(
            instrument_key=attempt.instrument_key,
            attempt_id=attempt.attempt_id,
            kind=kind,
            filled_quantity=filled,
            remaining_quantity=remaining,
            broker_execution_id=attempt.odno,
            trading_date=attempt.trading_date,
        )

    def _check_overdue(self, attempt: _Tracked) -> None:
        now = self.monotonic.now_ms()
        first = self._first_pending_ms.setdefault(attempt.attempt_id, now)
        if (
            now - first >= self.config.overdue_after_ms
            and attempt.attempt_id not in self._overdue_recorded
        ):
            self._record(
                FILL_OBSERVER_OVERDUE_KIND,
                {
                    "attempt_id": attempt.attempt_id,
                    "broker_execution_id": attempt.odno,
                    "waited_ms": now - first,
                },
            )
            self._overdue_recorded.add(attempt.attempt_id)

    def _record(self, kind: str, fields: dict[str, Any]) -> None:
        self.evidence_store.append(fields, kind=kind, record_class=kind)


def _fill_state(
    row: KisOrderRow,
) -> tuple[EgressResultKind | None, Decimal | None, Decimal | None, str]:
    """``(kind, filled, remaining, reason)`` for one attributed row (module docstring's
    fail-closed list). ``kind is None`` means the order is still working with nothing executed.
    """
    ordered, filled, remaining = row.ord_qty, row.tot_ccld_qty, row.rmn_qty
    if ordered is None or filled is None or remaining is None:
        return EgressResultKind.UNKNOWN, None, None, "quantity_unparseable"
    if row.rjct_qty is not None and row.rjct_qty > 0:
        return EgressResultKind.UNKNOWN, None, None, "rejected_quantity"
    if row.cancelled:
        if filled == 0:
            return EgressResultKind.CANCEL_ACK, None, None, "cancelled_unfilled"
        return EgressResultKind.UNKNOWN, None, None, "cancelled_after_fill"
    if filled < 0 or remaining < 0 or filled + remaining != ordered:
        return EgressResultKind.UNKNOWN, None, None, "quantity_inconsistent"
    if filled == 0:
        return None, None, None, "working"
    if remaining == 0:
        return EgressResultKind.FULL_FILL, filled, remaining, "filled"
    return EgressResultKind.PARTIAL_FILL, filled, remaining, "partially_filled"


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
