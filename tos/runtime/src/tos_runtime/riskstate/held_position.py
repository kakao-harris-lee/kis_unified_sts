"""One-use cache for a fresh, independent KIS stock holding observation.

The balance requests themselves belong to the composition root's existing asynchronous fetch
runner. That runner calls :meth:`publish` with two matching complete broker snapshots and the
monotonic grant instants of both balance reads. The decision path calls :meth:`consume`, which
never waits for I/O and burns a matching proof before returning it. An unavailable, stale,
cross-date, incomplete, synthetic, changed-view, or competing-order observation supplies no
proof. Scheduling the next read does not: a cached proof is held, under its own unchanged
freshness bound, until a newer one replaces it or that refresh FAILS (issue #1010).

KIS's current witness is stock-only and reports positive held quantities. It can prove a long
holding (including a complete flat result of zero); it cannot prove a short holding. Futures and
synthetic witnesses therefore remain unavailable to this cache.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol

from tos.engine.records import InstrumentKey

from tos_runtime.recon.ports import (
    WitnessOrder,
    WitnessOrderState,
    WitnessScope,
    WitnessSnapshot,
)

__all__ = [
    "HeldPositionCell",
    "HeldPositionConfig",
    "HeldPositionCurrentness",
    "HeldPositionProof",
    "PositionSide",
    "RclTip",
]

_KIS_STOCK_PROVENANCE = "kis-mock-stock"
_DATE_SHAPE = re.compile(r"[0-9]{8}")


class HeldPositionClock(Protocol):
    """The injected process-monotonic clock and trusted KST trading-date source."""

    def now_ms(self) -> int:
        """Return monotonic milliseconds from one process-local clock instance."""
        ...

    def today(self) -> str | None:
        """Return the trusted current trading date as ``YYYYMMDD``, or no date."""
        ...


class PositionSide(StrEnum):
    """The position side a CLOSE proposes to consume."""

    LONG = "LONG"
    SHORT = "SHORT"


@dataclass(frozen=True)
class RclTip:
    """One linearizable RCL revision; ``last_seq=None`` means a known empty log."""

    writer_epoch: int
    last_seq: int | None

    def __post_init__(self) -> None:
        if type(self.writer_epoch) is not int or self.writer_epoch < 0:
            raise ValueError("RclTip.writer_epoch must be a non-negative integer")
        if self.last_seq is not None and (
            type(self.last_seq) is not int or self.last_seq < 0
        ):
            raise ValueError("RclTip.last_seq must be None or a non-negative integer")


@dataclass(frozen=True)
class HeldPositionConfig:
    """Externally configured freshness bound for a broker balance observation."""

    max_age_ms: int

    def __post_init__(self) -> None:
        if type(self.max_age_ms) is not int or self.max_age_ms <= 0:
            raise ValueError("HeldPositionConfig.max_age_ms must be a positive integer")


@dataclass(frozen=True)
class HeldPositionProof:
    """Immutable holding quantity extracted from one accepted broker snapshot."""

    scope: WitnessScope
    proposal_id: str
    side: PositionSide
    held_quantity: Decimal
    trading_date: str
    age_origin_ms: int
    observed_at_generation: int
    provenance: str
    rcl_tip: RclTip
    max_age_ms: int


@dataclass(frozen=True)
class HeldPositionCurrentness:
    """Current trusted readings returned when step 9 revalidates a consumed proof."""

    current_now_ms: int
    current_trading_date: str
    rcl_tip: RclTip


@dataclass(frozen=True)
class _HeldPositionReading:
    """Validated broker reading before it is bound to a particular proposal."""

    scope: WitnessScope
    side: PositionSide
    held_quantity: Decimal
    trading_date: str
    age_origin_ms: int
    observed_at_generation: int
    provenance: str
    rcl_tip: RclTip
    max_age_ms: int


def _valid_trading_date(value: object) -> bool:
    if not isinstance(value, str) or _DATE_SHAPE.fullmatch(value) is None:
        return False
    try:
        return datetime.strptime(value, "%Y%m%d").strftime("%Y%m%d") == value
    except ValueError:
        return False


def _scope_instrument(scope: WitnessScope) -> InstrumentKey | None:
    """Return the single account-matched instrument this proof can cover."""
    if type(scope) is not WitnessScope:
        return None
    if type(scope.account) is not str or not scope.account:
        return None
    if type(scope.instrument_keys) is not tuple or len(scope.instrument_keys) != 1:
        return None
    if type(scope.attempt_ids) is not tuple or type(scope.order_dates) is not tuple:
        return None
    if not all(type(item) is str for item in (*scope.attempt_ids, *scope.order_dates)):
        return None
    (instrument_key,) = scope.instrument_keys
    if type(instrument_key) is not InstrumentKey:
        return None
    if (
        instrument_key.account != scope.account
        or type(instrument_key.instrument) is not str
        or not instrument_key.instrument
    ):
        return None
    if type(scope.as_of_generation) is not int or scope.as_of_generation < 0:
        return None
    return instrument_key


def _risk_scope_matches(scope: WitnessScope, *, account: str, instrument: str) -> bool:
    """Match a base risk scope without replacing its captured RCL generation."""
    key = _scope_instrument(scope)
    return (
        key is not None
        and key.account == account
        and key.instrument == instrument
        and scope.attempt_ids == ()
        and scope.order_dates == ()
    )


def _exact_tip_compatible(origin: RclTip, current: RclTip) -> bool:
    """Default to strict tip equality when no verified gap reader is injected."""
    return origin == current


def _quantity_for_snapshot(
    scope: WitnessScope, snapshot: WitnessSnapshot
) -> Decimal | None:
    """Validate the stock-specific snapshot and return its positive long amount."""
    key = _scope_instrument(scope)
    if key is None or type(snapshot) is not WitnessSnapshot:
        return None
    if (
        type(snapshot.observed_at_generation) is not int
        or snapshot.observed_at_generation != scope.as_of_generation
    ):
        return None
    if snapshot.positions_complete is not True:
        return None
    if snapshot.independent_of_evidence_store is not True:
        return None
    if (
        type(snapshot.provenance) is not str
        or snapshot.provenance != _KIS_STOCK_PROVENANCE
    ):
        return None
    if type(snapshot.positions) is not tuple or type(snapshot.orders) is not tuple:
        return None
    seen_symbols: set[str] = set()
    held_quantity = Decimal(0)
    for position in snapshot.positions:
        if type(position) is not tuple or len(position) != 2:
            return None
        symbol, quantity = position
        if not isinstance(symbol, str) or not symbol or symbol in seen_symbols:
            return None
        seen_symbols.add(symbol)
        if symbol != key.instrument:
            return None
        if (
            not isinstance(quantity, Decimal)
            or not quantity.is_finite()
            or quantity <= 0
        ):
            return None
        held_quantity += quantity

    order_identities: set[tuple[str, str]] = set()
    for order in snapshot.orders:
        if type(order) is not WitnessOrder:
            return None
        if type(order.state) is not WitnessOrderState:
            return None
        # KIS cancel semantics are not yet proven for this use. Only a fully filled row with
        # explicit zero remaining quantity and an unambiguous broker identity is terminal.
        if order.state is not WitnessOrderState.FILLED:
            return None
        if (
            not isinstance(order.quantity, Decimal)
            or not order.quantity.is_finite()
            or order.quantity <= 0
            or not isinstance(order.remaining, Decimal)
            or not order.remaining.is_finite()
            or order.remaining != 0
            or type(order.broker_execution_id) is not str
            or not order.broker_execution_id
            or type(order.order_date) is not str
            or order.order_date != snapshot.order_inquiry_date
            or not _valid_trading_date(order.order_date)
        ):
            return None
        identity = (order.order_date, order.broker_execution_id)
        if identity in order_identities:
            return None
        order_identities.add(identity)
    if held_quantity <= 0:
        return None
    return held_quantity


def _same_broker_view(first: WitnessSnapshot, confirming: WitnessSnapshot) -> bool:
    """Compare complete positions and every complete order row, ignoring row ordering only."""
    first_orders = tuple(
        sorted(
            first.orders,
            key=lambda order: (order.order_date, order.broker_execution_id),
        )
    )
    confirming_orders = tuple(
        sorted(
            confirming.orders,
            key=lambda order: (order.order_date, order.broker_execution_id),
        )
    )
    first_positions = tuple(sorted(first.positions, key=lambda position: position[0]))
    confirming_positions = tuple(
        sorted(confirming.positions, key=lambda position: position[0])
    )
    return first_positions == confirming_positions and first_orders == confirming_orders


def _fresh_window_valid(
    clock: HeldPositionClock,
    config: HeldPositionConfig,
    age_origin_ms: int,
    trading_date: str,
) -> bool:
    """Check the first FETCH grant against injected current time, date, and freshness."""
    try:
        now_ms = clock.now_ms()
        current_date = clock.today()
    except Exception:  # noqa: BLE001 - absent clock readings are fail-closed
        return False
    return (
        type(now_ms) is int
        and now_ms >= age_origin_ms
        and current_date == trading_date
        and now_ms - age_origin_ms <= config.max_age_ms
    )


class HeldPositionCell:
    """Thread-safe, nonblocking, one-use cache for one validated held-position snapshot.

    The asynchronous fetch owner calls :meth:`mark_pending` before scheduling a new broker
    read, then :meth:`publish` only after that read completes successfully. Exceptions,
    ``WitnessUnavailable``, and other failures should call :meth:`invalidate`. A decision
    consumes a proof synchronously; no broker request or wait occurs in :meth:`consume`.

    Exactly four events end a cached proof: it is consumed, it ages past ``max_age_ms``
    (checked at :meth:`consume` and again at :meth:`validate_consumed`, both against the one
    configured bound), its refresh fails, or a newer proof replaces it. Merely scheduling
    that refresh does not (issue #1010).
    """

    def __init__(
        self,
        *,
        config: HeldPositionConfig,
        clock: HeldPositionClock,
        rcl_tip_reader: Callable[[], RclTip | None],
        tip_compatible: Callable[[RclTip, RclTip], bool] | None = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._rcl_tip_reader = rcl_tip_reader
        self._tip_compatible = (
            _exact_tip_compatible if tip_compatible is None else tip_compatible
        )
        self._lock = threading.Lock()
        self._proof: _HeldPositionReading | None = None
        self._consumed_proof: HeldPositionProof | None = None
        self._revision = 0

    def mark_pending(self, scope: WitnessScope | None = None) -> int:
        """Reserve the token this refresh must present to publish; keep what is cached.

        This cache holds one scope at a time. The token prevents a slow, older worker result
        from replacing state from a newer refresh, and it alone orders publishes.

        Issue #1010: scheduling a read is not evidence against the proof already held. Burning
        it here emptied the cache for the whole worker window — four paced GETs, ~6.7 s to
        publish against a 12 s cadence — so a CLOSE proposed in that hole spent its one
        standing-approval use at step 4 and then read PROOF_UNAVAILABLE at step 6, and the
        position stayed open. The retained reading keeps its own ``age_origin_ms``, so
        :meth:`consume` still refuses it past ``max_age_ms``; a refresh that FAILS still burns
        it (:meth:`reject`, :meth:`invalidate`, and the publish validation below).
        """
        with self._lock:
            del scope  # Scope is carried back to publish; the token is cell-wide.
            self._revision += 1
            return self._revision

    def invalidate(self) -> None:
        """Burn the cached proof after a failed, unavailable, or incomplete refresh."""
        with self._lock:
            self._proof = None
            self._consumed_proof = None
            self._revision += 1

    def reject(self, pending_token: int | None) -> bool:
        """Invalidate only the refresh identified by ``pending_token``.

        A late failed worker must not clear a newer successful sample. ``False`` means this
        token is absent or no longer current; the cache state is left untouched on that path.
        """
        if type(pending_token) is not int:
            return False
        with self._lock:
            if self._revision != pending_token:
                return False
            self._proof = None
            self._consumed_proof = None
            self._revision += 1
            return True

    def _reject_refresh(self, pending_token: int) -> bool:
        """Refuse this refresh without letting a stale worker clear newer state."""
        with self._lock:
            if self._revision == pending_token:
                self._proof = None
                self._consumed_proof = None
                self._revision += 1
        return False

    def _compatible_current_tip(self, origin: RclTip) -> RclTip | None:
        """Return the observed tip only when the injected verifier accepts its full gap."""
        try:
            current = self._rcl_tip_reader()
            compatible = (
                type(current) is RclTip
                and current.writer_epoch == origin.writer_epoch
                and origin.last_seq is not None
                and current.last_seq is not None
                and current.last_seq >= origin.last_seq
                and self._tip_compatible(origin, current)
            )
        except Exception:  # noqa: BLE001 - tip or gap verifier failures deny proof use
            return None
        return current if compatible is True else None

    def publish(
        self,
        scope: WitnessScope,
        snapshot: WitnessSnapshot,
        *,
        confirming_snapshot: WitnessSnapshot | None = None,
        age_origin_ms: int | None = None,
        confirming_age_origin_ms: int | None = None,
        trading_date: str,
        rcl_tip_at_start: RclTip | None,
        pending_token: int | None = None,
    ) -> bool:
        """Publish a validated broker snapshot and its balance-request age origin.

        ``snapshot`` and ``confirming_snapshot`` are separate full witness reads. Their positions
        and order rows must match exactly; this detects a fill or other broker-side change during
        the worker window. ``age_origin_ms`` is the FIRST balance request's FETCH grant, not a
        timestamp copied from local evidence. ``confirming_age_origin_ms`` proves the second
        read followed the first; it never resets the freshness window. Both reads use the same
        trusted date passed to ``KisStockBrokerWitness.observe(..., today=...)``. The scope is the
        base account/instrument scope with no attempt IDs; no attempt exists in broker evidence.

        Invalid input is a failed refresh: it clears any cached proof and returns ``False``. It
        never converts an unavailable or malformed observation into a flat account. A superseded
        or absent token is not this refresh's failure — it returns ``False`` and leaves the
        cache untouched, so the proof in hand survives until this read answers (issue #1010).
        """
        if type(pending_token) is not int:
            return False
        with self._lock:
            if self._revision != pending_token:
                return False
        instrument_key = _scope_instrument(scope)
        generation = scope.as_of_generation
        if (
            instrument_key is None
            or type(generation) is not int
            or type(snapshot) is not WitnessSnapshot
            or type(confirming_snapshot) is not WitnessSnapshot
        ):
            return self._reject_refresh(pending_token)
        if scope.attempt_ids != ():
            return self._reject_refresh(pending_token)
        if (
            type(rcl_tip_at_start) is not RclTip
            or rcl_tip_at_start.last_seq is None
            or rcl_tip_at_start.last_seq != generation
        ):
            return self._reject_refresh(pending_token)
        if type(age_origin_ms) is not int or age_origin_ms < 0:
            return self._reject_refresh(pending_token)
        if (
            type(confirming_age_origin_ms) is not int
            or confirming_age_origin_ms < age_origin_ms
        ):
            return self._reject_refresh(pending_token)
        if not _valid_trading_date(trading_date):
            return self._reject_refresh(pending_token)
        if not _fresh_window_valid(
            self._clock, self._config, age_origin_ms, trading_date
        ):
            return self._reject_refresh(pending_token)
        if (
            snapshot.order_inquiry_date != trading_date
            or confirming_snapshot.order_inquiry_date != trading_date
        ):
            return self._reject_refresh(pending_token)
        held_quantity = _quantity_for_snapshot(scope, snapshot)
        confirming_quantity = _quantity_for_snapshot(scope, confirming_snapshot)
        if (
            held_quantity is None
            or confirming_quantity != held_quantity
            or not _same_broker_view(snapshot, confirming_snapshot)
        ):
            return self._reject_refresh(pending_token)
        try:
            current_rcl_tip = self._rcl_tip_reader()
        except Exception:  # noqa: BLE001 - unavailable linearizable tip fails closed
            return self._reject_refresh(pending_token)
        if type(current_rcl_tip) is not RclTip or current_rcl_tip != rcl_tip_at_start:
            return self._reject_refresh(pending_token)

        proof = _HeldPositionReading(
            scope=scope,
            side=PositionSide.LONG,
            held_quantity=held_quantity,
            trading_date=trading_date,
            age_origin_ms=age_origin_ms,
            observed_at_generation=generation,
            provenance=_KIS_STOCK_PROVENANCE,
            rcl_tip=rcl_tip_at_start,
            max_age_ms=self._config.max_age_ms,
        )
        with self._lock:
            if self._revision != pending_token:
                return False
            self._proof = proof
            self._consumed_proof = None
            self._revision += 1
        return True

    def consume(
        self,
        scope: WitnessScope,
        side: PositionSide,
        *,
        proposal_id: str | None,
    ) -> HeldPositionProof | None:
        """Return and burn one fresh proof for this exact scope, proposal, and held side.

        ``side`` is the holding side the caller's exact CLOSE direction is expected to close.
        The current proposal ID is bound only here; it is not attributed to the broker snapshot.
        A matching proof is burned before freshness, proposal, and side checks, so a CLOSE that
        is later denied cannot reuse its broker read. A stock snapshot cannot prove a short
        position; futures and synthetic provenance never publish in the first place.
        """
        return self._consume_matching(
            lambda cached_scope: cached_scope == scope,
            side=side,
            proposal_id=proposal_id,
        )

    def consume_for(
        self,
        account: str,
        instrument: str,
        side: PositionSide,
        *,
        proposal_id: str | None,
    ) -> HeldPositionProof | None:
        """Consume a proof by risk-only identity, retaining its original RCL generation.

        A verified non-reservation RCL gap may advance the live tip between FETCH and Step 6.
        This lookup therefore matches only the exact account/instrument base scope. It never
        rewrites the cached scope or snapshot generation to the newer tip.
        """
        if (
            type(account) is not str
            or not account
            or type(instrument) is not str
            or not instrument
        ):
            return None
        return self._consume_matching(
            lambda cached_scope: _risk_scope_matches(
                cached_scope, account=account, instrument=instrument
            ),
            side=side,
            proposal_id=proposal_id,
        )

    def _consume_matching(
        self,
        scope_matches: Callable[[WitnessScope], bool],
        *,
        side: PositionSide,
        proposal_id: str | None,
    ) -> HeldPositionProof | None:
        with self._lock:
            reading = self._proof
            if reading is None or not scope_matches(reading.scope):
                return None
            self._proof = None
            self._revision += 1
            revision = self._revision

        if (
            side is not PositionSide.LONG
            or type(proposal_id) is not str
            or not proposal_id
        ):
            return None
        try:
            now_ms = self._clock.now_ms()
            current_date = self._clock.today()
        except Exception:  # noqa: BLE001 - absent clock readings are fail-closed
            return None
        if type(now_ms) is not int or now_ms < 0 or now_ms < reading.age_origin_ms:
            return None
        if now_ms - reading.age_origin_ms > self._config.max_age_ms:
            return None
        if current_date != reading.trading_date:
            return None
        current_rcl_tip = self._compatible_current_tip(reading.rcl_tip)
        if current_rcl_tip is None:
            return None
        proof = HeldPositionProof(
            scope=reading.scope,
            proposal_id=proposal_id,
            side=reading.side,
            held_quantity=reading.held_quantity,
            trading_date=reading.trading_date,
            age_origin_ms=reading.age_origin_ms,
            observed_at_generation=reading.observed_at_generation,
            provenance=reading.provenance,
            rcl_tip=reading.rcl_tip,
            max_age_ms=reading.max_age_ms,
        )
        with self._lock:
            if self._revision != revision:
                return None
            self._consumed_proof = proof
        return proof

    def validate_consumed(
        self, proof: HeldPositionProof
    ) -> HeldPositionCurrentness | None:
        """Recheck and burn the exact proof at the step-9 commit boundary."""
        with self._lock:
            cached = self._consumed_proof
            if type(proof) is not HeldPositionProof or cached is not proof:
                return None
            self._consumed_proof = None
            self._revision += 1
            revision = self._revision

        current_rcl_tip: RclTip | None
        try:
            now_ms = self._clock.now_ms()
            current_date = self._clock.today()
        except (
            Exception
        ):  # noqa: BLE001 - unavailable currentness evidence fails closed
            return None
        current_rcl_tip = self._compatible_current_tip(proof.rcl_tip)
        if (
            type(now_ms) is not int
            or now_ms < proof.age_origin_ms
            or now_ms - proof.age_origin_ms > proof.max_age_ms
            or current_date != proof.trading_date
            or current_rcl_tip is None
        ):
            return None
        with self._lock:
            if self._revision != revision:
                return None
        return HeldPositionCurrentness(
            current_now_ms=now_ms,
            current_trading_date=current_date,
            rcl_tip=current_rcl_tip,
        )
