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
  ``RESULT_UNMATCHED`` (recorded but not applied) rows carry ``egress_result_kind``,
  ``filled_quantity`` and ``remaining_quantity`` per ``attempt_id``. **Deviation, reported:** :class:`~tos_runtime.recon.evidence_reader
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
``SEND_SEALED`` + latest ``EGRESS_RESULT_CONSUMED``       CONFIRMED: ``filled_quantity``
(highest ``seq``) whose ``egress_result_kind`` is in      (``0`` if the row carries none)
``tos.engine.TERMINAL_RESULT_KINDS`` (``FULL_FILL`` /     signed by
``REJECT`` / ``CANCEL_ACK`` / ``EXPIRED``)                ``send_seal.outbound_side``;
                                                           nothing outstanding.
``SEND_SEALED`` + latest ``EGRESS_RESULT_CONSUMED``       CONFIRMED ``filled_quantity`` as
whose kind is NOT terminal (``ACK`` / ``PARTIAL_FILL``    above, PLUS IN-FLIGHT: the
/ ``TIMEOUT`` / ``UNKNOWN``, or missing/unrecognized)     unfilled ``max(remaining_quantity,
                                                           outbound_quantity - filled, 0)``
                                                           signed by ``outbound_side`` — the
                                                           kernel records CONSUMED for every
                                                           APPLIED result, so a consumed
                                                           ACK resolves nothing (lane A
                                                           re-review #7; bucket rationale in
                                                           :mod:`tos.position.predicates`).
``SEND_SEALED`` + ``RESULT_UNMATCHED`` not superseded     IN-FLIGHT: the FULL sealed
by a LATER ``EGRESS_RESULT_CONSUMED``                     ``send_seal.outbound_quantity``,
                                                           signed by ``outbound_side`` — a
                                                           recorded-but-not-applied result
                                                           proves nothing was safely
                                                           resolved (plan §2.2 line 58).
``SEND_SEALED`` + ``RESULT_UNMATCHED`` with a higher      As the non-terminal CONSUMED row,
``seq`` than the latest ``EGRESS_RESULT_CONSUMED``,       whatever that result's kind: the
not a replay of an applied row (below)                    consumed fill stays CONFIRMED, the
                                                           unfilled remainder returns to
                                                           IN-FLIGHT.
``SEND_SEALED`` with NEITHER receipt kind present         IN-FLIGHT: the full sealed
                                                           quantity, signed by
                                                           ``outbound_side`` — genuinely
                                                           still outstanding.
An ``outbound_side`` that matches NEITHER of the two       UNKNOWN in BOTH directions
injected side tokens                                       (fail-closed — an unrecognized
                                                             side token proves no direction
                                                             at all, never defaults to one);
                                                             IN-FLIGHT quantities go to
                                                             IN-FLIGHT in both directions.
======================================================  =================================

**Why UNMATCHED is IN-FLIGHT.** UNKNOWN nets against an opposite confirmed position and
IN-FLIGHT never does (rationale and the ARE decision-sum argument in
:mod:`tos.position.predicates`), so moving an unmatched attempt to IN-FLIGHT can only raise the
decision sum — it equals the state before the result was recorded.

**Supersession is by evidence ``seq`` AND cumulative fill.** An unmatched row BEFORE the latest
consumed row is dropped only when that row's cumulative ``filled_quantity`` (which ``CONSUMED``
rows carry from the reservation) already covers the unmatched row's own fill — a later non-fill
result (``EXPIRED`` after a refused fill) does not account for it. An unmatched row AFTER the
latest consumed row is a result that was never applied (e.g. a fill
crossing a ``CANCEL_ACK``, whose quantity ``tos.engine.core`` records only on
``RESULT_UNMATCHED``), so it reopens the attempt even when the consumed kind is terminal. A
``DUPLICATE`` disposition is the exact already-applied result resent
(``tos.engine.vocabulary.ResultDisposition``), not a new fact, so it never reopens; every other
non-applied disposition can carry a real late fill and does — except a **replay**: an unmatched
row whose ``(egress_result_kind, filled_quantity, remaining_quantity, broker_execution_id)``
equals one of the attempt's own applied results (the kernel's ``DUPLICATE`` signature as far as
the evidence stores it; ``resolution_generation`` is on neither kind) and whose fill the latest
consumed cumulative fill already covers. The applied payload's magnitudes are rebuilt from its
row: a fill kind's stored pair is the payload's, a non-fill payload has none. A fill missing
either magnitude on either side is never a replay (fail closed). After
finality release the engine holds no reservation, so the same applied result re-sent is recorded
as ``ORPHAN_NO_RESERVATION`` (or ``MISMATCHED_ATTEMPT`` once a new attempt holds the scope) —
``ProvisionalReservationLedger.apply_egress_result`` checks the reservation before the
``DUPLICATE`` signature — and a released attempt can never be re-applied, so reopening it would
DENY the scope forever. A different fill or remaining quantity (``PARTIAL_FILL`` 4/5 after an
applied 4/6 — the broker reports a different open quantity), a kind no applied row carries
(``FULL_FILL`` after ``CANCEL_ACK``), or a different broker execution is a new fact and still
reopens. No result digest is persisted on either evidence kind, so identity is these durable
fields alone.

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

**Kernel round #4 K-2.** The pure value types (``PositionObservation``, ``SealedSend``) and
pure predicates (the three magnitude functions, ``sign_of``, the classification table) are
promoted to :mod:`tos.position` (kernel round #4 plan K-2) — this module re-exports them
unchanged (same names, same shapes) so every existing import of
``tos_runtime.riskstate.position`` keeps working, and now contains ONLY the durable-evidence
I/O (reading the ``SqliteEvidenceStore``, JSON decoding, ``(account, instrument)`` scope
filtering) plus the thin call into the kernel's pure classification.

Firewall (R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.evidence.store`` +
``tos_runtime.recon.ports`` (``WitnessUnavailable`` only — the shared read-failure exception
type) only.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from decimal import Decimal

from tos.engine import FILL_RESULT_KINDS, TERMINAL_RESULT_KINDS
from tos.position import (
    ConsumedResult,
    PositionObservation,
    classify_sealed_sends,
    conservative_current_usage,
    in_flight_overlap_effect,
    worst_credible_directional_usage,
)
from tos.position import (
    SealedSend as _SealedSend,
)

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

#: The kernel's terminal result vocabulary as the bare tokens ``egress_result_kind`` carries in
#: the durable payload (``model_dump(mode="json")``) — derived, never a second literal copy.
_TERMINAL_RESULT_TOKENS: frozenset[str] = frozenset(
    kind.value for kind in TERMINAL_RESULT_KINDS
)


#: The kernel's fill-bearing kinds as bare tokens — the only kinds whose payload carries
#: ``filled_quantity`` / ``remaining_quantity`` (``tos.engine.records.EgressResultPayload``).
_FILL_RESULT_TOKENS: frozenset[str] = frozenset(
    kind.value for kind in FILL_RESULT_KINDS
)


def _read_kind_payloads_with_seq(
    store: SqliteEvidenceStore, kind: str
) -> list[tuple[int, dict[str, object]]]:
    """Read every matching entry's ``(seq, scrubbed payload)``, in commit (``seq``) order — the exact
    by-kind raw-SQL idiom :mod:`tos_runtime.recon.witness_synthetic` /
    :mod:`tos_runtime.recon.evidence_reader` / :mod:`tos_runtime.safety.ack` already use over
    this same store (module docstring)."""
    try:
        cursor = store.connection.execute(
            "SELECT seq, payload_json FROM entries WHERE kind = ? ORDER BY seq ASC",
            (kind,),
        )
        rows = cursor.fetchall()
    except sqlite3.Error as exc:
        raise WitnessUnavailable(
            f"EvidencePositionReader: evidence store query failed for kind={kind!r}: {exc}"
        ) from exc
    payloads: list[tuple[int, dict[str, object]]] = []
    for seq, payload_json in rows:
        decoded = json.loads(payload_json)
        payload = decoded.get("payload", decoded)
        if isinstance(payload, dict):
            payloads.append((seq, payload))
    return payloads


def _read_kind_payloads(
    store: SqliteEvidenceStore, kind: str
) -> list[dict[str, object]]:
    return [payload for _, payload in _read_kind_payloads_with_seq(store, kind)]


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


#: One result's replay signature: ``(egress_result_kind, filled_quantity, remaining_quantity,
#: broker_execution_id)`` — the kernel's ``DUPLICATE`` signature minus the two axes the evidence
#: cannot supply (``attempt_id`` is the grouping key; ``resolution_generation`` is stored on
#: neither evidence kind).
_ResultSignature = tuple[object, Decimal | None, Decimal | None, object]


def _applied_signature(payload: Mapping[str, object]) -> _ResultSignature | None:
    """The applied result's own payload signature, rebuilt from its ``EGRESS_RESULT_CONSUMED``
    row. That row copies kind and ``broker_execution_id`` from the payload, but its magnitudes are
    the reservation's after the result (``tos.engine.core`` ``_handle_egress_result``). For a fill
    kind those equal the payload's (the ledger stores the fill's own pair); a non-fill payload
    carries no magnitude at all (``EgressResultPayload`` validator), so its pair is
    ``(None, None)`` whatever the row stores. ``None`` (never a replay target) for a fill row
    missing either magnitude — the engine never writes one, so it is not trusted."""
    kind = payload.get("egress_result_kind")
    execution_id = payload.get("broker_execution_id")
    if kind not in _FILL_RESULT_TOKENS:
        return (kind, None, None, execution_id)
    filled = _to_decimal(payload.get("filled_quantity"))
    remaining = _to_decimal(payload.get("remaining_quantity"))
    if filled is None or remaining is None:
        return None
    return (kind, filled, remaining, execution_id)


def _unmatched_signature(payload: Mapping[str, object]) -> _ResultSignature | None:
    """A ``RESULT_UNMATCHED`` row's signature — that row copies all four fields from the refused
    payload. ``None`` (never a replay) when the shape is one the engine cannot produce: a fill
    without both magnitudes, or a non-fill kind with any magnitude."""
    kind = payload.get("egress_result_kind")
    filled = _to_decimal(payload.get("filled_quantity"))
    remaining = _to_decimal(payload.get("remaining_quantity"))
    if kind in _FILL_RESULT_TOKENS:
        if filled is None or remaining is None:
            return None
    elif filled is not None or remaining is not None:
        return None
    return (kind, filled, remaining, payload.get("broker_execution_id"))


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
    ) -> tuple[dict[str, ConsumedResult], set[str], list[str]]:
        """Read the two terminal-result evidence kinds within scope (module docstring's
        "deviation, reported" note on why this reads them directly rather than reusing
        :class:`~tos_runtime.recon.evidence_reader.SqliteEvidenceReceiptReader`'s
        already-collapsed public type). Returns ``(consumed_by_attempt, unmatched_attempts,
        sources)`` — split out of :meth:`observe` purely for that method's own 100-line size
        budget; no behavioural difference from having this inline."""
        consumed_payloads = [
            (seq, payload)
            for seq, payload in _read_kind_payloads_with_seq(
                self._store, "EGRESS_RESULT_CONSUMED"
            )
            if _in_scope(payload, account=self._account, instrument=self._instrument)
        ]
        unmatched_payloads = [
            (seq, payload)
            for seq, payload in _read_kind_payloads_with_seq(
                self._store, "RESULT_UNMATCHED"
            )
            if _in_scope(payload, account=self._account, instrument=self._instrument)
        ]
        consumed_by_attempt: dict[str, ConsumedResult] = {}
        latest_consumed_seq: dict[str, int] = {}
        applied_signatures: dict[str, set[_ResultSignature]] = {}
        unmatched_attempts: set[str] = set()
        # ``consumed_payloads`` is in commit (``seq ASC``) order, so the last assignment per
        # attempt is its LATEST applied result — the one whose kind decides terminality and
        # whose stored (cumulative) magnitudes govern (module docstring's table).
        for seq, payload in consumed_payloads:
            attempt_id = payload.get("attempt_id")
            if not isinstance(attempt_id, str):
                continue
            latest_consumed_seq[attempt_id] = seq
            signature = _applied_signature(payload)
            if signature is not None:
                applied_signatures.setdefault(attempt_id, set()).add(signature)
            raw_kind = payload.get("egress_result_kind")
            consumed_by_attempt[attempt_id] = ConsumedResult(
                result_kind=raw_kind if isinstance(raw_kind, str) else None,
                filled_quantity=_to_decimal(payload.get("filled_quantity")),
                remaining_quantity=_to_decimal(payload.get("remaining_quantity")),
            )
        for seq, payload in unmatched_payloads:
            if payload.get("result_disposition") == "DUPLICATE":
                continue
            attempt_id = payload.get("attempt_id")
            if not isinstance(attempt_id, str):
                continue
            latest = consumed_by_attempt.get(attempt_id)
            if latest is None:
                unmatched_attempts.add(attempt_id)
                continue
            fill_covered = (
                _to_decimal(payload.get("filled_quantity")) or Decimal(0)
            ) <= (latest.filled_quantity or Decimal(0))
            superseded = seq < latest_consumed_seq[attempt_id]
            unmatched_signature = _unmatched_signature(payload)
            replayed = unmatched_signature is not None and (
                unmatched_signature in applied_signatures.get(attempt_id, set())
            )
            if not (fill_covered and (superseded or replayed)):
                unmatched_attempts.add(attempt_id)
        sources: list[str] = []
        if consumed_payloads:
            sources.append("evidence:EGRESS_RESULT_CONSUMED")
        if unmatched_payloads:
            sources.append("evidence:RESULT_UNMATCHED")
        return consumed_by_attempt, unmatched_attempts, sources

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
        ) = classify_sealed_sends(
            sealed,
            consumed_by_attempt=consumed_by_attempt,
            unmatched_attempts=unmatched_attempts,
            buy_side_token=self._buy_side_token,
            sell_side_token=self._sell_side_token,
            terminal_result_kinds=_TERMINAL_RESULT_TOKENS,
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
