"""tos_runtime.riskstate.position — single-source, conservative position observation
(TOS risk state service wave, plan §2.2; DR-0003 §2.2 "The position observation is a
single-source, conservative fill sum").

**Position is the evidence store's own fill sum, never a broker query.** There is no
broker-position/balance transport anywhere in ``tos_runtime`` (survey ``rs-survey-runtime.md``
§5, confirmed by grep: ``tos_runtime/transport/kis_mock/`` has zero balance/position hits) and
no fill/position/PnL ledger of any kind (same survey, same section). This module folds the
runtime's own durable evidence into a directional-usage observation:

* **Confirmed** — the kernel gateway's ``SEND_SEALED`` evidence record
  (``tos.egressgw.records.GatewayEvidenceRecord``, kind literal ``"SEND_SEALED"``,
  ``tos/src/tos/egressgw/gateway.py:1617``) carries the whole pre-``SEND_STARTED``
  :class:`~tos.egressgw.SendSeal` — ``send_seal.outbound_side`` /
  ``send_seal.outbound_quantity`` — for exactly one ``attempt_id``
  (``tos/src/tos/egressgw/records.py:643`` — "the whole ... SendSeal, carried on the
  SEND_SEALED record only"). :mod:`tos_runtime.compose._transport_wiring`'s own
  ``SealRegistry.capture`` (``_transport_wiring.py:374-386``) reads this SAME durable record
  for its own (in-memory, single-use, never durably stored itself) lookup — this module reads
  the DURABLE row directly via the evidence store's own by-kind raw-SQL idiom
  (:mod:`tos_runtime.recon.witness_synthetic` / :mod:`tos_runtime.recon.evidence_reader` /
  :mod:`tos_runtime.safety.ack`'s own ``SELECT payload_json FROM entries WHERE kind = ?``
  pattern), never the in-memory registry (which pops on first read and is wired only for the
  ``kis-mock`` transport kind).
* **Consumed egress result** — the durable ``EGRESS_RESULT_CONSUMED`` (applied) /
  ``RESULT_UNMATCHED`` (recorded but not applied) rows carry ``filled_quantity`` per
  ``attempt_id``. **Deviation, reported:** :class:`~tos_runtime.recon.evidence_reader
  .SqliteEvidenceReceiptReader` was the survey's pointer for this read, but its
  ``EgressReceiptObservation`` return type folds BOTH durable kinds into one stream with no
  field naming which SQL ``kind`` a row came from (measured against
  ``tos_runtime/recon/evidence_reader.py`` / ``ports.py`` directly — both share the same
  ``source_ref`` literal). This module's classification table needs CONSUMED told apart from
  UNMATCHED, so it reads the two kinds directly via the SAME by-kind raw-SQL idiom that reader
  uses internally, rather than reusing its already-collapsed public type.

**Classification table (per sealed attempt, DR-0003 §2.2 verbatim: "confirmed fills from
consumed egress results, signed by the sealed outbound side; every attempt that was sealed but
has no terminal result counted in full, in the direction that makes usage largest").**

======================================================  =================================
Evidence state for one ``attempt_id``                    Classification
======================================================  =================================
``SEND_SEALED`` + ``EGRESS_RESULT_CONSUMED`` present      CONFIRMED: ``filled_quantity``
                                                           (``0`` if the row carries none —
                                                           a positively recorded zero-fill
                                                           outcome, e.g. a plain ACK/CANCEL/
                                                           REJECT, is a resolved fact, not an
                                                           unknown) signed by
                                                           ``send_seal.outbound_side``.
``SEND_SEALED`` + ``RESULT_UNMATCHED`` present (no        UNKNOWN: the FULL sealed
``EGRESS_RESULT_CONSUMED`` for the same attempt)          ``send_seal.outbound_quantity``,
                                                           signed by ``outbound_side`` — a
                                                           recorded-but-not-applied result
                                                           proves nothing was safely
                                                           resolved (plan §2.2 line 58).
``SEND_SEALED`` with NEITHER receipt kind present         IN-FLIGHT: the full sealed
                                                           quantity, signed by
                                                           ``outbound_side`` — genuinely
                                                           still outstanding.
An ``outbound_side`` that matches NEITHER of the two       UNKNOWN in BOTH directions
injected side tokens                                       (fail-closed — an unrecognized
                                                             side token proves no direction
                                                             at all, never defaults to one).
======================================================  =================================

If BOTH a ``RESULT_UNMATCHED`` and an ``EGRESS_RESULT_CONSUMED`` row exist for the same
attempt (a re-injected result superseding an earlier unmatched one), the ``CONSUMED`` row
governs — it is the durably APPLIED fact.

**Side stays a policy/config-carried token — never a runtime-authored literal (deviation from
the plan §4.1 constructor signature, reported; long/short symmetry, CLAUDE.md "Futures must
preserve long/short symmetry").** ``tos/runtime/tests/test_no_side_literals.py`` is a
repo-wide, pre-existing structural pin (TOS Phase 5 W5 plan §2 decision 8/9) that fails the
whole runtime suite the instant a quoted side literal appears anywhere under
``tos_runtime/src`` outside the one allowlisted KIS mock wire-codec module — this module is
not that module, and ``outbound_side`` has no closed kernel enum (measured: no ``Side``
StrEnum exists anywhere under ``tos/src``; ``SendSeal.outbound_side`` is a bare ``str``,
``tos/src/tos/egressgw/seal.py:219``). :class:`EvidencePositionReader` therefore takes the two
recognized side tokens as REQUIRED constructor arguments (``buy_side_token``/
``sell_side_token``, no default — a default literal would itself be the same forbidden
constant) — the caller (lane b wiring) is responsible for sourcing them from the SAME
policy/config surface the venue side already uses (e.g. ``VenueShapeConstraints
.allowed_sides``), never a literal this package invents.

**Never reads a broker; never assumes independence.** ``PositionObservation.sources`` names
only the evidence kinds this module actually read. The snapshot-completeness witness
(``all_fields_attributed``) is NOT set by this module (DR-0003 §2.2's own disclosed limit) —
it remains the existing operator attestation under ``_restrictive_merge``
(``tos_runtime/compose/_risk_attestations.py``), which this package does not touch.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.evidence.store`` +
``tos_runtime.recon.ports`` (``WitnessUnavailable`` only — the shared read-failure exception
type) only.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.recon.ports import WitnessUnavailable

__all__ = [
    "PositionObservation",
    "worst_credible_directional_usage",
    "conservative_current_usage",
    "in_flight_overlap_effect",
    "EvidencePositionReader",
]

#: The gateway evidence kind carrying the whole pre-``SEND_STARTED`` seal (module docstring).
_SEND_SEALED_KIND = "SEND_SEALED"


@dataclass(frozen=True)
class PositionObservation:
    """One (account, instrument) scope's conservative position observation (plan §2.2 /
    §4.1). All magnitudes are contract counts (never a valuation/notional dimension — DR-0003
    §2.2 "it is contract-count only"). ``sources`` names only the evidence kinds actually read,
    never a blanket claim of corroboration."""

    scope_key: str
    confirmed_net: Decimal
    unknown_buy: Decimal
    unknown_sell: Decimal
    in_flight_buy: Decimal
    in_flight_sell: Decimal
    attempts_seen: int
    sources: tuple[str, ...]


def worst_credible_directional_usage(obs: PositionObservation) -> Decimal:
    """The worst-credible directional usage magnitude (plan §2.2, pure function).

    ``max(|confirmed_net + unknown_buy + in_flight_buy|, |confirmed_net - unknown_sell -
    in_flight_sell|)`` — every unconfirmed/in-flight quantity pushed to the direction that
    makes usage LARGEST (ARE-INV-006: UNKNOWN consumes conservative capacity, never assumed
    safe). Adding an unknown attempt in either direction can only enlarge (or leave unchanged)
    this magnitude, never shrink it.
    """
    long_case = obs.confirmed_net + obs.unknown_buy + obs.in_flight_buy
    short_case = obs.confirmed_net - obs.unknown_sell - obs.in_flight_sell
    return max(abs(long_case), abs(short_case))


def conservative_current_usage(obs: PositionObservation) -> Decimal:
    """Like :func:`worst_credible_directional_usage`, but WITHOUT the in-flight terms (plan
    §2.2: "``conservative_current_usage`` = 이 값 − in-flight 항(in-flight 는
    ``required_concurrent_overlap_effect`` 로 별도)") — the confirmed-plus-unconfirmed-only
    worst-credible magnitude, excluding attempts that are still genuinely outstanding.
    """
    long_case = obs.confirmed_net + obs.unknown_buy
    short_case = obs.confirmed_net - obs.unknown_sell
    return max(abs(long_case), abs(short_case))


def in_flight_overlap_effect(obs: PositionObservation) -> Decimal:
    """The magnitude an ARE ``ProjectedCell.required_concurrent_overlap_effect`` would take
    from this observation (plan §2.2) — the sum of both in-flight buckets, never netted (an
    in-flight buy and an in-flight sell are both still-outstanding overlap exposure, not
    offsetting positions)."""
    return obs.in_flight_buy + obs.in_flight_sell


def _read_kind_payloads(
    store: SqliteEvidenceStore, kind: str
) -> list[dict[str, object]]:
    """Read every matching entry's scrubbed payload, in commit (``seq``) order — the exact
    by-kind raw-SQL idiom :mod:`tos_runtime.recon.witness_synthetic` /
    :mod:`tos_runtime.recon.evidence_reader` / :mod:`tos_runtime.safety.ack` already use over
    this same store (module docstring)."""
    try:
        cursor = store.connection.execute(
            "SELECT payload_json FROM entries WHERE kind = ? ORDER BY seq ASC", (kind,)
        )
        rows = cursor.fetchall()
    except sqlite3.Error as exc:
        raise WitnessUnavailable(
            f"EvidencePositionReader: evidence store query failed for kind={kind!r}: {exc}"
        ) from exc
    payloads: list[dict[str, object]] = []
    for (payload_json,) in rows:
        decoded = json.loads(payload_json)
        payload = decoded.get("payload", decoded)
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _to_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (str, int, float)):
        try:
            return Decimal(str(value))
        except (ValueError, ArithmeticError):
            return None
    return None


@dataclass(frozen=True)
class _SealedSend:
    attempt_id: str
    side: str | None
    quantity: Decimal | None


def _seal_in_scope(
    seal: Mapping[str, object], *, account: str, instrument: str
) -> bool:
    """Whether a ``SEND_SEALED`` row's ``send_seal.instrument_key`` matches this reader's
    scope (``SendSeal.instrument_key`` — ``tos/src/tos/egressgw/seal.py:184`` — is the ONLY
    account/instrument coordinate a ``GatewayEvidenceRecord`` carries; unlike
    ``EngineEvidenceRecord``, it has no top-level ``instrument_key`` field of its own).
    """
    instrument_key = seal.get("instrument_key")
    if not isinstance(instrument_key, Mapping):
        return False
    return (
        instrument_key.get("account") == account
        and instrument_key.get("instrument") == instrument
    )


def _read_sealed_sends(
    store: SqliteEvidenceStore, *, account: str, instrument: str
) -> tuple[_SealedSend, ...]:
    """Every durably recorded ``SEND_SEALED`` row's ``(attempt_id, outbound_side,
    outbound_quantity)`` within this reader's ``(account, instrument)`` scope (module
    docstring). A row missing ``attempt_id`` or an unresolvable/out-of-scope
    ``send_seal.instrument_key`` is skipped — it cannot be attributed to this scope's position
    bucket at all (never guessed)."""
    sealed: list[_SealedSend] = []
    for payload in _read_kind_payloads(store, _SEND_SEALED_KIND):
        attempt_id = payload.get("attempt_id")
        if not isinstance(attempt_id, str):
            continue
        seal = payload.get("send_seal")
        if not isinstance(seal, dict) or not _seal_in_scope(
            seal, account=account, instrument=instrument
        ):
            continue
        raw_side = seal.get("outbound_side")
        side = raw_side if isinstance(raw_side, str) else None
        quantity = _to_decimal(seal.get("outbound_quantity"))
        sealed.append(_SealedSend(attempt_id=attempt_id, side=side, quantity=quantity))
    return tuple(sealed)


def _in_scope(payload: Mapping[str, object], *, account: str, instrument: str) -> bool:
    """Whether an ``EngineEvidenceRecord``-shaped payload's ``instrument_key`` matches this
    reader's scope (mirrors :mod:`tos_runtime.recon.witness_synthetic`'s own ``_in_scope``,
    narrowed to a single instrument rather than a set)."""
    instrument_key = payload.get("instrument_key")
    if not isinstance(instrument_key, Mapping):
        return False
    return (
        instrument_key.get("account") == account
        and instrument_key.get("instrument") == instrument
    )


class EvidencePositionReader:
    """Folds the durable evidence store into one :class:`PositionObservation` for a single
    ``(account, instrument)`` scope (module docstring's classification table)."""

    def __init__(
        self,
        evidence_store: SqliteEvidenceStore,
        *,
        account: str,
        instrument: str,
        buy_side_token: str,
        sell_side_token: str,
    ) -> None:
        """Bind this reader to a store, scope, and the two recognized side tokens.

        Args:
            evidence_store: The durable evidence store (read-only — this class never appends).
            account: The account this observation is scoped to.
            instrument: The instrument this observation is scoped to.
            buy_side_token: The caller-injected token meaning a directional-buy send (module
                docstring's "side stays a policy/config-carried token" section — REQUIRED, no
                default, sourced from the same policy/config surface the venue side vocabulary
                already uses).
            sell_side_token: The caller-injected token meaning a directional-sell send.
        """
        self._store = evidence_store
        self._account = account
        self._instrument = instrument
        self._buy_side_token = buy_side_token
        self._sell_side_token = sell_side_token

    def _read_terminal_results(
        self,
    ) -> tuple[dict[str, Decimal], set[str], list[str]]:
        """Read the two terminal-result evidence kinds within scope (module docstring's
        "deviation, reported" note on why this reads them directly rather than reusing
        :class:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader`'s
        already-collapsed public type). Returns ``(consumed_by_attempt, unmatched_attempts,
        sources)`` — split out of :meth:`observe` purely for that method's own 100-line size
        budget; no behavioural difference from having this inline."""
        consumed_payloads = [
            payload
            for payload in _read_kind_payloads(self._store, "EGRESS_RESULT_CONSUMED")
            if _in_scope(payload, account=self._account, instrument=self._instrument)
        ]
        unmatched_payloads = [
            payload
            for payload in _read_kind_payloads(self._store, "RESULT_UNMATCHED")
            if _in_scope(payload, account=self._account, instrument=self._instrument)
        ]
        consumed_by_attempt: dict[str, Decimal] = {}
        unmatched_attempts: set[str] = set()
        for payload in consumed_payloads:
            attempt_id = payload.get("attempt_id")
            if not isinstance(attempt_id, str):
                continue
            quantity = _to_decimal(payload.get("filled_quantity"))
            consumed_by_attempt[attempt_id] = (
                quantity if quantity is not None else Decimal(0)
            )
        for payload in unmatched_payloads:
            attempt_id = payload.get("attempt_id")
            if isinstance(attempt_id, str) and attempt_id not in consumed_by_attempt:
                unmatched_attempts.add(attempt_id)
        sources: list[str] = []
        if consumed_payloads:
            sources.append("evidence:EGRESS_RESULT_CONSUMED")
        if unmatched_payloads:
            sources.append("evidence:RESULT_UNMATCHED")
        return consumed_by_attempt, unmatched_attempts, sources

    def _sign_of(self, side: str | None) -> int | None:
        """The directional sign for ``side`` against this reader's two injected tokens, or
        ``None`` when it matches neither (module docstring's "side stays a policy/config-
        carried token" — fail-closed, never a guessed direction)."""
        if side == self._buy_side_token:
            return 1
        if side == self._sell_side_token:
            return -1
        return None

    def _classify_sealed_sends(
        self,
        sealed: tuple[_SealedSend, ...],
        *,
        consumed_by_attempt: dict[str, Decimal],
        unmatched_attempts: set[str],
    ) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, int]:
        """The module docstring's classification table, applied to every sealed send. Split
        out of :meth:`observe` purely for that method's own 100-line size budget."""
        confirmed_net = Decimal(0)
        unknown_buy = Decimal(0)
        unknown_sell = Decimal(0)
        in_flight_buy = Decimal(0)
        in_flight_sell = Decimal(0)
        attempts_seen = 0
        for send in sealed:
            attempts_seen += 1
            sign = self._sign_of(send.side)
            if send.attempt_id in consumed_by_attempt:
                filled = consumed_by_attempt[send.attempt_id]
                if sign is None:
                    # Unrecognized side on a CONFIRMED fill: fail-closed to UNKNOWN in both
                    # directions rather than silently dropping the confirmed magnitude.
                    unknown_buy += filled
                    unknown_sell += filled
                    continue
                confirmed_net += sign * filled
                continue
            quantity = send.quantity if send.quantity is not None else Decimal(0)
            if send.attempt_id in unmatched_attempts:
                if sign is None:
                    unknown_buy += quantity
                    unknown_sell += quantity
                    continue
                if sign > 0:
                    unknown_buy += quantity
                else:
                    unknown_sell += quantity
                continue
            # Sealed, no terminal result at all: genuinely in-flight.
            if sign is None:
                in_flight_buy += quantity
                in_flight_sell += quantity
                continue
            if sign > 0:
                in_flight_buy += quantity
            else:
                in_flight_sell += quantity
        return (
            confirmed_net,
            unknown_buy,
            unknown_sell,
            in_flight_buy,
            in_flight_sell,
            attempts_seen,
        )

    def observe(self) -> PositionObservation:
        """Fold the durable evidence into one :class:`PositionObservation` (module docstring's
        classification table). Never raises on genuinely absent evidence (a fresh store yields
        an all-zero observation); a real read failure propagates as
        :class:`~tos_runtime.recon.ports.WitnessUnavailable`, matching the same read-failure
        discipline :mod:`tos_runtime.recon.witness_synthetic` applies to this identical store.
        """
        sealed = _read_sealed_sends(
            self._store, account=self._account, instrument=self._instrument
        )
        consumed_by_attempt, unmatched_attempts, result_sources = (
            self._read_terminal_results()
        )
        (
            confirmed_net,
            unknown_buy,
            unknown_sell,
            in_flight_buy,
            in_flight_sell,
            attempts_seen,
        ) = self._classify_sealed_sends(
            sealed,
            consumed_by_attempt=consumed_by_attempt,
            unmatched_attempts=unmatched_attempts,
        )
        sources: list[str] = []
        if sealed:
            sources.append(f"evidence:{_SEND_SEALED_KIND}")
        sources.extend(result_sources)

        return PositionObservation(
            scope_key=f"{self._account}::{self._instrument}",
            confirmed_net=confirmed_net,
            unknown_buy=unknown_buy,
            unknown_sell=unknown_sell,
            in_flight_buy=in_flight_buy,
            in_flight_sell=in_flight_sell,
            attempts_seen=attempts_seen,
            sources=tuple(sources),
        )
