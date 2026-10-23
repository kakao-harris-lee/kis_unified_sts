"""Post-ACK fill observer for the KIS 모의투자 stock order path (PR-3b, rescope plan §3 M2).

``KisMockTransport`` maps an order reply to ``ACK``/``REJECT``/``UNKNOWN``/``TIMEOUT`` only; what
happens to an ACKed order afterwards is only visible on 주식일별주문체결조회 (``VTTC0081R``, GET,
mock host). This module polls that TR for the ODNOs this runtime holds an ACK for, and turns what
it reads into ``PARTIAL_FILL``/``FULL_FILL``/``CANCEL_ACK``/``UNKNOWN`` results for the engine's
normal result path (``EGRESS_RESULT`` through the durable inbox, then finality and release).

**What it tracks comes from durable evidence, not memory.** An attempt is tracked when an
``EGRESS_RESULT_CONSUMED`` row records its ``ACK`` with an ODNO and a trading date. What was already
reported is the latest recorded result for that attempt, so a restart re-derives the same picture
and an execution observed twice is reported once.

**Two separate "done"s (PR-3b review HIGH 1).** The broker side is done when a terminal result
(``FULL_FILL``/``CANCEL_ACK``/``EXPIRED``/``REJECT``) is recorded — the observer stops reading the
broker for it. The capacity side is done only when the RCL holds the attempt's release command
(:func:`~tos_runtime.posttrade.release_consumer.release_command_id`). Between the two — the process
died after the engine consumed the result but before finality ran, or reconciliation / the RCL CAS
refused the release — the observer re-runs finality from the recorded result every
``finality_retry_interval_ms`` (``reproject``), never re-feeding the fill to the engine, until the
release commits.

**Only an engine that holds the reservation is fed (found while fixing review HIGH 1).** The
engine's in-memory reservation projection is not rebuilt on boot (``engine/driver.py``: "no ledger
rebuild; Phase 5 / J3"). A result fed after a restart for a pre-restart attempt is refused as an
orphan by the live engine, but the NEXT boot's replay — which does rebuild the reservation from
the inbox — re-derives it as applied and refuses the boot (``EngineReplayDiverged``). So when the
engine does not hold this attempt's reservation, nothing is enqueued: one
``FILL_OBSERVER_ENGINE_RESERVATION_ABSENT`` row records what the broker showed, the reservation
stays held (fail closed — no release, so no double release), and a terminal observation stops
the polling. Releasing it is the ledger-rebuild work, not this module's.

**Each ACK is read under its own trading date (review MEDIUM).** VTTC0081R takes the date, so an
ACK from an earlier day — the runtime was down across the KST date boundary — is still read, and
reconciled, under its ``ord_dt``; a read that fails is recorded, and the attempt still goes
overdue. Nothing is skipped silently.

**Attribution.** A row belongs to an attempt only when its ``odno`` equals the ACK's ODNO (both
sides canonicalized: whitespace and leading zeros dropped, ASCII digits only — measured
encodings differ, ``tools/broker_probes/probes_order.py::odno_key``) AND its ``ord_dt`` equals the
ACK's trading date (a KIS ODNO is a per-day sequence). The emitted result carries the ACK's ODNO
and date verbatim, so every receipt of the attempt names one broker order. A row that matches no
ACK this runtime recorded is recorded as ``FILL_OBSERVER_UNATTRIBUTED_ORDER`` and never enqueued —
and the release reconciliation then sees it as an orphan broker order, which blocks release.

**Fail closed.** A row that does not name this attempt's instrument (``pdno``; review HIGH 2 — the
witness refuses such a read outright as well), a row whose ``ord_qty`` is not the attempt's sealed quantity
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
    "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND",
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
FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND = "FILL_OBSERVER_ENGINE_RESERVATION_ABSENT"

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
        finality_retry_interval_ms: Minimum spacing between two finality re-runs for one
            attempt whose terminal result is recorded but whose release has not committed.
    """

    witness_fields: dict[str, Any]
    poll_interval_ms: int
    overdue_after_ms: int
    finality_retry_interval_ms: int


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
        finality_retry_interval_ms=_positive_int(
            raw, "finality_retry_interval_ms", path
        ),
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
        self, scope: WitnessScope, *, inquiry_date: str | None = None
    ) -> tuple[str, tuple[KisOrderRow, ...]]: ...


#: Feeds one result into the engine and returns its disposition (compose supplies it).
ResultSink = Callable[[EgressResultPayload], "ResultDisposition | None"]
#: Re-runs finality for an already-recorded terminal result; ``True`` iff the RCL committed.
Reprojector = Callable[[EgressResultPayload], "bool | None"]
#: Whether the RCL holds ``attempt_id``'s release command.
ReleaseCommitted = Callable[[str], bool]
#: Whether the live engine holds ``attempt_id``'s reservation (module docstring).
EngineHolds = Callable[[str], bool]


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
    #: The RCL holds this attempt's release command (capacity side done).
    released: bool = False
    #: Terminal only by an observation the engine could not take (no reservation held) — never
    #: re-projected: there is no engine receipt to project finality from.
    held_absent: bool = False
    #: ``(kind, filled, remaining)`` already recorded as ``ENGINE_RESERVATION_ABSENT``.
    absent_signatures: set[tuple[str, str | None, str | None]] = field(
        default_factory=set
    )
    #: ``SEND_SEALED.send_seal.outbound_quantity`` — what was actually put on the wire.
    sealed_quantity: Decimal | None = None


@dataclass(frozen=True)
class FillPollReport:
    """What one :meth:`KisMockFillObserver.poll_once` did."""

    polled: bool
    emitted: tuple[tuple[str, EgressResultKind, ResultDisposition | None], ...] = ()
    unattributed: tuple[str, ...] = ()
    read_failed: bool = False
    #: ``(attempt_id, rcl_released)`` for every finality re-run this poll made.
    reprojected: tuple[tuple[str, bool | None], ...] = ()
    #: ``(attempt_id, kind)`` observed but NOT fed: the engine holds no such reservation.
    held: tuple[tuple[str, EgressResultKind], ...] = ()


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
    reproject: Reprojector
    release_committed: ReleaseCommitted
    engine_holds: EngineHolds
    monotonic: MonotonicSource
    account: str
    instrument: str
    _last_poll_ms: int | None = field(default=None, init=False)
    _last_reproject_ms: dict[str, int] = field(default_factory=dict, init=False)
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
        """One pass: re-run unfinished finality, then read the broker for attempts still open.
        No GET at all when no ACKed attempt is outstanding on the broker side."""
        tracked = self._tracked_attempts()
        reprojected = self._reproject_unreleased(tracked)
        pending = [t for t in tracked.values() if not t.terminal]
        if not pending:
            return FillPollReport(polled=False, reprojected=reprojected)
        self._last_poll_ms = self.monotonic.now_ms()
        emitted: list[tuple[str, EgressResultKind, ResultDisposition | None]] = []
        held: list[tuple[str, EgressResultKind]] = []
        unattributed: list[str] = []
        read_failed = False
        for date in sorted({t.trading_date for t in pending}):
            on_date = [t for t in pending if t.trading_date == date]
            rows = self._read(date, on_date)
            if rows is None:
                read_failed = True
                continue
            unattributed.extend(self._flag_unattributed(rows, tracked))
            emitted.extend(self._emit(on_date, rows, held))
        if not read_failed:
            self._last_read_failed = False
        return FillPollReport(
            polled=True,
            emitted=tuple(emitted),
            unattributed=tuple(unattributed),
            read_failed=read_failed,
            reprojected=reprojected,
            held=tuple(held),
        )

    def _read(
        self, date: str, attempts: list[_Tracked]
    ) -> tuple[KisOrderRow, ...] | None:
        """One date's rows, or ``None`` after recording the failure (and still running the
        overdue check — a read that keeps failing must surface, never go quiet)."""
        scope = WitnessScope(
            account=self.account,
            instrument_keys=(
                InstrumentKey(account=self.account, instrument=self.instrument),
            ),
            attempt_ids=tuple(t.attempt_id for t in attempts),
            order_dates=(date,),
        )
        try:
            _date, rows = self.orders.order_rows(scope, inquiry_date=date)
        except WitnessUnavailable as exc:
            if not self._last_read_failed:
                self._record(
                    FILL_OBSERVER_READ_FAILED_KIND,
                    {"inquiry_date": date, "reason": str(exc)[:200]},
                )
            self._last_read_failed = True
            for attempt in attempts:
                self._check_overdue(attempt)
            return None
        return rows

    def _emit(
        self,
        attempts: list[_Tracked],
        rows: tuple[KisOrderRow, ...],
        held: list[tuple[str, EgressResultKind]],
    ) -> list[tuple[str, EgressResultKind, ResultDisposition | None]]:
        emitted = []
        for attempt in attempts:
            payload, reason = self._classify(attempt, rows)
            if payload is None:
                self._check_overdue(attempt)
                continue
            if not self.engine_holds(attempt.attempt_id):
                self._hold_absent(attempt, payload, reason)
                held.append((attempt.attempt_id, payload.kind))
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
            if payload.kind in _TERMINAL_KINDS:
                # The sink runs finality right now; the retry clock starts here, not at zero.
                self._last_reproject_ms[attempt.attempt_id] = self.monotonic.now_ms()
            disposition = self.result_sink(payload)
            emitted.append((attempt.attempt_id, payload.kind, disposition))
        return emitted

    def _hold_absent(
        self, attempt: _Tracked, payload: EgressResultPayload, reason: str
    ) -> None:
        """Record — once per distinct observation — what the broker showed for an attempt the
        engine does not hold (module docstring). Nothing is enqueued, nothing released.
        """
        signature = (
            payload.kind.value,
            _text(payload.filled_quantity),
            _text(payload.remaining_quantity),
        )
        if signature in attempt.absent_signatures:
            return
        self._record(
            FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND,
            {
                "attempt_id": attempt.attempt_id,
                "broker_execution_id": attempt.odno,
                "trading_date": attempt.trading_date,
                "kind": signature[0],
                "filled_quantity": signature[1],
                "remaining_quantity": signature[2],
                "reason": reason,
            },
        )
        attempt.absent_signatures.add(signature)

    def _reproject_unreleased(
        self, tracked: dict[str, _Tracked]
    ) -> tuple[tuple[str, bool | None], ...]:
        """Re-run finality for every attempt whose terminal result is recorded but whose release
        the RCL does not hold yet (module docstring "Two separate 'done's")."""
        now = self.monotonic.now_ms()
        done = []
        for attempt in tracked.values():
            if not attempt.terminal or attempt.released or attempt.held_absent:
                continue
            last = self._last_reproject_ms.get(attempt.attempt_id)
            if last is not None and now - last < self.config.finality_retry_interval_ms:
                continue
            self._last_reproject_ms[attempt.attempt_id] = now
            payload = self._payload(
                attempt, attempt.last_kind, attempt.last_filled, attempt.last_remaining
            )
            done.append((attempt.attempt_id, self.reproject(payload)))
        return tuple(done)

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
        self._apply_absent_rows(tracked)
        for attempt in tracked.values():
            if attempt.terminal:
                attempt.released = self.release_committed(attempt.attempt_id)
        return tracked

    def _apply_absent_rows(self, tracked: dict[str, _Tracked]) -> None:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_ENGINE_RESERVATION_ABSENT_KIND,),
        ).fetchall()
        for (payload_json,) in rows:
            row = json.loads(payload_json).get("payload", {})
            attempt = tracked.get(str(row.get("attempt_id")))
            if attempt is None:
                continue
            attempt.absent_signatures.add(
                (
                    str(row.get("kind")),
                    row.get("filled_quantity"),
                    row.get("remaining_quantity"),
                )
            )
            if row.get("kind") in {k.value for k in _TERMINAL_KINDS} and not (
                attempt.terminal
            ):
                attempt.terminal = True
                attempt.held_absent = True

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
        if mine[0].pdno != self.instrument:
            # Review HIGH 2: the ODNO and date say "ours", the instrument does not — a row for
            # another symbol (or naming none) never proves this attempt's fill.
            return self._unknown(attempt, "instrument_mismatch")
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
        """One ``FILL_OBSERVER_OVERDUE`` row per attempt, ever: the wait clock is process-local,
        the "already recorded" check is durable."""
        now = self.monotonic.now_ms()
        first = self._first_pending_ms.setdefault(attempt.attempt_id, now)
        if now - first < self.config.overdue_after_ms:
            return
        if attempt.attempt_id not in self._overdue_recorded:
            self._overdue_recorded |= self._recorded_overdue()
        if attempt.attempt_id not in self._overdue_recorded:
            self._record(
                FILL_OBSERVER_OVERDUE_KIND,
                {
                    "attempt_id": attempt.attempt_id,
                    "broker_execution_id": attempt.odno,
                    "trading_date": attempt.trading_date,
                    "waited_ms": now - first,
                },
            )
            self._overdue_recorded.add(attempt.attempt_id)

    def _recorded_overdue(self) -> set[str]:
        rows = self.evidence_store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ?",
            (FILL_OBSERVER_OVERDUE_KIND,),
        ).fetchall()
        return {
            str(json.loads(payload_json).get("payload", {}).get("attempt_id"))
            for (payload_json,) in rows
        }

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
