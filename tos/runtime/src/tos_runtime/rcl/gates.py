"""``SqliteCommitLog`` pre-insert gates + replay-fold helpers (design #40 D2.1).

Extracted from :mod:`tos_runtime.rcl.log` to keep that module under the
repo's 1000-line module size budget (``tools/tos_size_budget.py``) — a pure
decomposition, no behavior change. Every function taking a ``conn`` argument
here MUST be called from inside the SAME ``BEGIN IMMEDIATE`` transaction
:class:`~tos_runtime.rcl.log.SqliteCommitLog` already holds on that
connection — none of these functions opens, commits, or rolls back a
transaction itself; that discipline stays entirely in ``log.py``.

Contents:

* :data:`INITIAL_RESERVATION_STATES` + :func:`check_reservation_from_state`
  — the HIGH-1 fix (independent review, 2026-09-08): a claimed
  ``from_state`` is checked against the held ``reservations`` record before
  a transition is admitted. See ``log.py``'s own module docstring's "a
  claimed ``from_state`` is checked against the held record" section for
  the full rationale (ADR-002-012 :37 no automatic re-arm; mirrors
  ``tos.engine.state.ProvisionalReservationLedger._store``'s forward-only
  held-state check, ``engine/state.py`` lines 219-233).
* :func:`existing_command_row` + :func:`classify_duplicate_command` — the
  MEDIUM-3 fix (independent review, 2026-09-08): row-existence is reported
  separately from a possibly-``NULL`` stored digest, so a second
  ``command_digest=None`` append is classified as ``DUPLICATE_COMMAND_ID``
  instead of reaching the ``entries.command_id`` ``UNIQUE`` constraint
  unclassified.
* :func:`fold_reservations_from_entries` + :func:`digest_of_reservation_map`
  — fault ⑤'s independent re-fold, reading ONLY entries whose
  ``is_reservation_transition`` column is ``1`` (the MEDIUM-4 fix,
  independent review 2026-09-08 — see ``log.py``'s own module docstring's
  "the replay fold is discriminated, not payload-shape-matched" section for
  why a payload-shape match alone is forgeable via a plain ``append_cas``
  call's public ``payload_json`` argument). The folded value per
  ``reservation_id`` now carries ``scope_account``/``scope_instrument``
  alongside ``state`` (laneO port-fix round, design #40 runtime slice #2 §5
  disposition, 2026-09-08): the kernel's ``CapacityReservationTransition.scope``
  binding is part of what a transition commits, so a directly-tampered
  ``reservations.scope_account``/``scope_instrument`` column must disagree
  with the independent re-fold exactly like a tampered ``state`` column does
  — the digest :func:`digest_of_reservation_map` computes now covers both.
* :class:`ReservationRefusalReason` + :class:`ReservationTransitionRefusal` +
  :func:`reservation_lifecycle_refusal` — moved here from ``log.py`` (laneO
  port-fix round, design #40 runtime slice #2 §5, 2026-09-08; a pure
  decomposition for the 100-line function size budget, same discipline as
  every other extraction in this module's own history). The runtime-local
  reservation-lifecycle refusal vocabulary (NOT the kernel's closed
  ``tos.rcl.AppendRefusalReason`` — see ``log.py``'s own module docstring's
  "reservation-lifecycle refusal is a separate, runtime-local vocabulary"
  section for why) plus the pure evaluation of the three kernel lifecycle
  gates (structural legality, cause admissibility, release/finality-witness
  admissibility) :meth:`~tos_runtime.rcl.log.SqliteCommitLog.apply_reservation_transition`
  raises on.

Firewall: stdlib (``json``, ``sqlite3``) + ``tos.canonical``/``tos.rcl`` only
(R1 allowlist) — no ``tos_runtime`` sibling import (this module has no
dependency on :mod:`tos_runtime.rcl.log`; it is the other way around).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from tos.canonical import CanonicalizationScheme
from tos.rcl import (
    AppendRefusal,
    AppendRefusalReason,
    CapacityReservationTransition,
    CapacityState,
    CommandType,
    CommitEntry,
    TransitionCause,
    duplicate_command,
    release_admissible,
    reservation_transition_structurally_legal,
    transition_allowed,
)

__all__ = [
    "INITIAL_RESERVATION_STATES",
    "ReservationRefusalReason",
    "ReservationTransitionRefusal",
    "check_reservation_from_state",
    "classify_duplicate_command",
    "digest_of_reservation_map",
    "existing_command_row",
    "fold_reservations_from_entries",
    "reservation_lifecycle_refusal",
    "row_to_commit_entry",
]

#: The only capacity state a reservation-lifecycle transition may claim as its
#: ``from_state`` when the log holds NO prior row for that ``reservation_id``
#: yet (independent review HIGH-1, 2026-09-08). Derived, not invented, from
#: the kernel's own engine projection precedent
#: (``tos.engine.state.ProvisionalReservationLedger``): ``commit_unbound()``
#: is the ONLY entry point that admits a fresh scope with no prior projected
#: reservation; every other advance (``bind_attempt``, ``mark_potentially_live``,
#: ``apply_egress_result``) requires ``self.outstanding(key)`` to already
#: exist, raising ``ArtifactIntegrityError`` otherwise ("no projected
#: reservation for scope ... fail-closed", ``engine/state.py``). So
#: ``COMMITTED_UNBOUND`` is the sole state a reservation may be claimed to
#: originate from before the log has ever recorded one; ``ATTEMPT_BOUND`` —
#: despite also being named a structural analog of the D2.1 shorthand
#: ``RESERVED`` in ``tos.rcl.commitlog``'s own anti-phantom note — always
#: requires a preceding ``COMMITTED_UNBOUND`` row in the engine's own model
#: and is therefore NOT included here.
INITIAL_RESERVATION_STATES: frozenset[CapacityState] = frozenset(
    {CapacityState.COMMITTED_UNBOUND}
)


def existing_command_row(
    conn: sqlite3.Connection, command_id: str
) -> tuple[bool, str | None]:
    """Return ``(row_exists, stored_digest)`` — never collapses "no row" into ``None``.

    A stored ``command_digest`` of ``NULL`` on an EXISTING row is a real
    prior entry (a legitimate duplicate-classification candidate), not
    "nothing to conflict with" — collapsing "no row" and "row present with a
    NULL digest" into the same bare ``None`` return let a second
    ``command_digest=None`` append for the same ``command_id`` skip
    :func:`tos.rcl.duplicate_command` entirely (its own docstring contracts
    ``existing_digest_for_id is None`` to mean "no prior entry exists"),
    reach the ``entries.command_id`` ``UNIQUE`` constraint unclassified, and
    surface as a misleading ``PARTIAL_COMMIT_SUSPECTED`` instead of
    ``DUPLICATE_COMMAND_ID`` (independent review MEDIUM-3, 2026-09-08).

    Args:
        conn: The live sqlite3 connection, inside an open transaction.
        command_id: The command id to look up.

    Returns:
        ``(True, stored_digest)`` if a row exists (``stored_digest`` may
        itself be ``None``), else ``(False, None)``.
    """
    row = conn.execute(
        "SELECT command_digest FROM entries WHERE command_id = ?", (command_id,)
    ).fetchone()
    if row is None:
        return False, None
    return True, row[0]


def classify_duplicate_command(
    row_exists: bool,
    existing_digest: str | None,
    attempted_digest: str | None,
) -> AppendRefusalReason | None:
    """Classify a repeat ``command_id`` against the stored digest (MEDIUM-3 fix).

    The rule, stated explicitly rather than left implicit: when NO row
    exists for this ``command_id`` yet, this always admits (``None`` —
    nothing to conflict with). When a row DOES exist: a stored ``NULL``
    digest against an attempted ``NULL`` digest is treated as the SAME bytes
    (a genuine duplicate, ``DUPLICATE_COMMAND_ID``); a stored ``NULL``
    against a non-``NULL`` attempt (or the reverse) is treated as a bytes
    MISMATCH (``COMMAND_BYTES_MISMATCH`` — ``NULL`` is never silently
    treated as equal to a real digest); when both are non-``NULL``, this
    delegates to :func:`tos.rcl.duplicate_command`'s own byte-classification
    (identity vs. conflict).

    Args:
        row_exists: Whether a prior ``entries`` row exists for this id
            (from :func:`existing_command_row`).
        existing_digest: The stored digest on that row, if any.
        attempted_digest: The digest of the command now being appended.

    Returns:
        The :class:`~tos.rcl.AppendRefusalReason`, or ``None`` to admit.
    """
    if not row_exists:
        return None
    if existing_digest is None and attempted_digest is None:
        return AppendRefusalReason.DUPLICATE_COMMAND_ID
    if existing_digest is None or attempted_digest is None:
        return AppendRefusalReason.COMMAND_BYTES_MISMATCH
    return duplicate_command(existing_digest, attempted_digest)


def check_reservation_from_state(
    conn: sqlite3.Connection,
    reservation_id: str,
    claimed_from_state: CapacityState,
) -> AppendRefusal | None:
    """Refuse a transition whose claimed ``from_state`` disagrees with the held record.

    See ``log.py``'s own module docstring's "a claimed ``from_state`` is
    checked against the held record" section for the full rationale
    (independent review HIGH-1, 2026-09-08). Must be called inside the same
    ``BEGIN IMMEDIATE`` transaction as the eventual write so the held-state
    read and the admission decision are atomic together.

    Args:
        conn: The live sqlite3 connection, inside an open transaction.
        reservation_id: The reservation the transition claims to advance.
        claimed_from_state: The caller-supplied ``transition.from_state``.

    Returns:
        An :class:`~tos.rcl.AppendRefusal` (reason ``INTEGRITY_VIOLATION``)
        if the claim disagrees with reality, or ``None`` to admit.
    """
    held_row = conn.execute(
        "SELECT state FROM reservations WHERE reservation_id = ?",
        (reservation_id,),
    ).fetchone()
    if held_row is None:
        if claimed_from_state in INITIAL_RESERVATION_STATES:
            return None
        return AppendRefusal(
            reason=AppendRefusalReason.INTEGRITY_VIOLATION,
            detail=(
                f"reservation {reservation_id!r} has no held state yet — only an "
                "initial lifecycle state "
                f"({sorted(s.value for s in INITIAL_RESERVATION_STATES)}) may "
                f"originate a transition, but the claimed from_state="
                f"{claimed_from_state} is not one (fail-closed: a transition "
                "cannot originate from a state that was never held)"
            ),
        )
    held_state = CapacityState(held_row[0])
    if held_state != claimed_from_state:
        return AppendRefusal(
            reason=AppendRefusalReason.INTEGRITY_VIOLATION,
            detail=(
                f"reservation {reservation_id!r} is actually held at {held_state}, "
                f"but the caller claimed from_state={claimed_from_state} — a stale "
                "or mistaken claim must never be admitted (fail-closed; "
                "ADR-002-012 :37 no automatic re-arm; cf. "
                "tos.engine.state.ProvisionalReservationLedger._store's own "
                "forward-only held-state check, engine/state.py lines 219-233)"
            ),
        )
    return None


def fold_reservations_from_entries(
    conn: sqlite3.Connection,
) -> dict[str, dict[str, str]]:
    """Re-derive the final reservation-state map by replaying every entry.

    Reads ONLY entries whose ``is_reservation_transition`` column is ``1``
    (independent review MEDIUM-4, 2026-09-08) — never entries selected by
    ``payload_json`` shape alone, which a plain ``append_cas`` caller could
    forge (see ``log.py``'s own module docstring's "replay fold is
    discriminated, not payload-shape-matched" section).

    Each folded entry's ``payload_json`` carries a ``scope`` sub-object
    (``{"account": ..., "instrument": ...}``) alongside ``to_state`` since
    the kernel's ``CapacityReservationTransition.scope`` binding landed
    (laneO port-fix round, 2026-09-08) — an entry missing either scope
    component is excluded from the fold exactly like one missing
    ``reservation_id``/``to_state``, rather than folded in with a
    fabricated scope.

    Args:
        conn: The live sqlite3 connection.

    Returns:
        The reconstructed ``{reservation_id: {"state": ..., "scope_account":
        ..., "scope_instrument": ...}}`` map.
    """
    rows = conn.execute(
        "SELECT payload_json FROM entries WHERE is_reservation_transition = 1 "
        "ORDER BY seq ASC"
    ).fetchall()
    folded: dict[str, dict[str, str]] = {}
    for (payload_json,) in rows:
        payload = json.loads(payload_json)
        reservation_id = payload.get("reservation_id")
        to_state = payload.get("to_state")
        scope = payload.get("scope") or {}
        scope_account = scope.get("account")
        scope_instrument = scope.get("instrument")
        if (
            reservation_id is not None
            and to_state is not None
            and scope_account is not None
            and scope_instrument is not None
        ):
            folded[reservation_id] = {
                "state": to_state,
                "scope_account": scope_account,
                "scope_instrument": scope_instrument,
            }
    return folded


def digest_of_reservation_map(
    scheme: CanonicalizationScheme, mapping: Mapping[str, Mapping[str, str]]
) -> str:
    """Canonical digest of a ``{reservation_id: {state, scope_account,
    scope_instrument}}`` map (sorted, deterministic).

    Args:
        scheme: The registered ``tos.canonical`` scheme to digest with.
        mapping: The reservation-state-and-scope map to digest.

    Returns:
        The canonical digest string.
    """
    return scheme.compute_digest(
        {
            "reservations": {
                reservation_id: dict(sorted(value.items()))
                for reservation_id, value in sorted(mapping.items())
            }
        }
    )


# ===========================================================================
# reservation-lifecycle refusal vocabulary + gate evaluation (moved from
# log.py — laneO port-fix round, design #40 runtime slice #2 §5, 2026-09-08;
# 100-line function / 1000-line module size-budget decomposition)
# ===========================================================================


class ReservationRefusalReason(StrEnum):
    """Runtime-local (NOT the kernel's closed) reservation-lifecycle refusal reasons.

    See ``log.py``'s own module docstring's "reservation-lifecycle refusal
    is a separate, runtime-local vocabulary" section for why these are not
    force-fit onto ``tos.rcl.AppendRefusalReason``.
    """

    NOT_STRUCTURALLY_LEGAL = "NOT_STRUCTURALLY_LEGAL"
    CAUSE_NOT_ADMISSIBLE = "CAUSE_NOT_ADMISSIBLE"
    FINALITY_WITNESS_REQUIRED = "FINALITY_WITNESS_REQUIRED"


class ReservationTransitionRefusal(RuntimeError):
    """Raised by :meth:`~tos_runtime.rcl.log.SqliteCommitLog.apply_reservation_transition`
    on a lifecycle gate refusal."""

    def __init__(self, reason: ReservationRefusalReason, detail: str = "") -> None:
        super().__init__(f"reservation transition refused: {reason} {detail}".strip())
        self.reason = reason


def reservation_lifecycle_refusal(
    transition: CapacityReservationTransition,
    cause: TransitionCause,
    finality_witness: bool | None,
) -> tuple[ReservationRefusalReason, str] | None:
    """Evaluate the three kernel reservation-lifecycle gates, in order.

    :func:`tos.rcl.reservation_transition_structurally_legal` (the
    ADR-002-002 §10.1 whitelist), :func:`tos.rcl.transition_allowed` (the
    cause-specific conservatism check), and — only for a
    RELEASED/POSITION_CONSUMED destination — :func:`tos.rcl.release_admissible`
    (the finality-witness gate). Split out of ``log.py``'s
    ``apply_reservation_transition`` (100-line function size budget); the
    caller raises :class:`ReservationTransitionRefusal` with whatever this
    returns.

    Args:
        transition: The proposed transition.
        cause: The driving :class:`~tos.rcl.TransitionCause`.
        finality_witness: The broker-truth / evidence witness for a
            finality destination, or ``None``.

    Returns:
        ``(reason, detail)`` for the first gate that refuses, or ``None`` if
        all three admit.
    """
    from_state = transition.from_state
    to_state = transition.to_state
    if not reservation_transition_structurally_legal(from_state, to_state):
        return (
            ReservationRefusalReason.NOT_STRUCTURALLY_LEGAL,
            f"({from_state} -> {to_state}) is not on the closed whitelist",
        )
    if (
        from_state is None
        or to_state is None
        or not transition_allowed(from_state, to_state, cause)
    ):
        return (
            ReservationRefusalReason.CAUSE_NOT_ADMISSIBLE,
            f"cause {cause} does not authorize ({from_state} -> {to_state})",
        )
    if not release_admissible(transition, finality_witness):
        return (
            ReservationRefusalReason.FINALITY_WITNESS_REQUIRED,
            f"destination {to_state} requires finality_witness is True",
        )
    return None


def row_to_commit_entry(row: tuple[Any, ...]) -> CommitEntry:
    """Build a :class:`~tos.rcl.CommitEntry` from one ``entries`` row.

    Shared by :meth:`~tos_runtime.rcl.log.SqliteCommitLog.replay` and
    :meth:`~tos_runtime.rcl.log.SqliteCommitLog.read_linearizable` — moved here (a pure,
    row-shape-to-model helper, no transaction/connection state) purely for ``log.py``'s own
    1000-line module size budget (TOS Phase 5 W4, size-budget decomposition — no behavior
    change).
    """
    seq, writer_epoch, command_id, command_digest, kind, payload_digest = row
    return CommitEntry(
        seq=seq,
        writer_epoch=writer_epoch,
        command_id=command_id,
        command_digest=command_digest,
        kind=CommandType(kind) if kind is not None else None,
        payload_digest=payload_digest,
    )
