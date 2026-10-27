"""RCL reservation identity — one reservation per *attempt*, named by its permit (#966).

Every compose-root wiring site and every W1/W2 recovery/reconciliation/release site that must
resolve an attempt onto the RCL reservation id it commits against used to hand-write
``f"resv-{account}-{instrument}"`` independently. :mod:`tos_runtime.rcl.obligation`'s own module
docstring already named that formula and the sites that shared it; W2-R's
:mod:`tos_runtime.posttrade.release_consumer` added an eighth hand-written copy — the first one
that WRITES to the RCL log rather than only reading it — and independent review flagged the
duplication itself (2026-09-10, finding M6). This module is the one place the formula can ever
change.

**Issue #966 — the identity is now per attempt, derived from the Action Flow Permit.** The
scope-level formula made the reservation lifecycle scope-wide: once an entry filled, that
``(account, instrument)`` scope held a forward-only ``POSITION_CONSUMED`` reservation and no
further order could ever be committed on it — not an exit, not a later re-entry (step 8 denied
any scope with a reservation row at all, and the RCL has no ``POSITION_CONSUMED ->
ATTEMPT_BOUND`` re-arm). :func:`permit_reservation_id` gives each attempt its own reservation.

**Why the permit identity and not the attempt id** (measured 2026-10-28, plan §2.1 revision):
the attempt id does not exist when the reservation is committed. Step 9 (``ATOMIC_COMMIT``) is
what mints the reservation, and ``tos.engine.sequencer`` builds the attempt id only at step 12,
*from* step 9's permit identity and step 11's conformance-proof digest —
``tos.engine.records.StageRequest.attempt`` is documented and implemented as ``None`` before
step 13. The Action Flow Permit identity is the earliest per-attempt identity that exists at
commit time, it is content-addressed (no RNG, no clock — the same replay reproduces it), and
``tos.engine.records.AttemptRequest.action_flow_permit_identity`` carries it forward, so every
later in-flow consumer (steps 10/13/14, the send-boundary context) re-derives the same id with
no extra plumbing. Post-trade consumers, which hold only an ``attempt_id``, resolve it through
:mod:`tos_runtime.rcl.reservation_lookup`'s durable evidence join.

:func:`scope_reservation_id` stays — a ledger written before #966 holds ``resv-{acct}-{instr}``
rows, and those must keep reading back (no migration, no rewrite). Nothing commits a new one.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.engine.records``
(``InstrumentKey``/``AttemptRequest``, read-only — the D1.1 ``tos_runtime -> tos`` edge, the
same one :mod:`tos_runtime.rcl.projection` already takes). No ``shared.*``.
"""

from __future__ import annotations

from tos.engine.records import AttemptRequest, InstrumentKey

__all__ = [
    "attempt_request_reservation_id",
    "permit_identity_of",
    "permit_reservation_id",
    "reservation_id_in_scope",
    "scope_reservation_id",
]

#: The shared prefix of every reservation id this module spells, scope-level and per-attempt
#: alike. Factored out because :func:`permit_identity_of` must strip exactly what
#: :func:`permit_reservation_id` wrote — a second literal here is precisely the drift finding
#: M6 was about.
_PREFIX = "resv"


def scope_reservation_id(account: str, instrument: str) -> str:
    """The pre-#966 scope-level reservation id — **read-only now**.

    Kept solely so a ledger committed before #966 still projects and replays: those rows are
    named by this formula and are never rewritten. No production site commits a new reservation
    under it; new reservations are per attempt (:func:`permit_reservation_id`).

    Args:
        account: The scope account.
        instrument: The scope instrument.

    Returns:
        ``f"resv-{account}-{instrument}"``.
    """
    return f"{_PREFIX}-{account}-{instrument}"


def permit_reservation_id(account: str, instrument: str, permit_identity: str) -> str:
    """This attempt's own RCL reservation id (module docstring).

    Args:
        account: The scope account.
        instrument: The scope instrument.
        permit_identity: The Action Flow Permit identity step 9 bound this commit to
            (``ActionFlowPermit.permit_id``, carried onward as
            ``AttemptRequest.action_flow_permit_identity``). Must be concrete — a caller with a
            possibly-absent identity uses :func:`reservation_id_in_scope` instead.

    Returns:
        ``f"resv-{account}-{instrument}-{permit_identity}"``.
    """
    return f"{scope_reservation_id(account, instrument)}-{permit_identity}"


def reservation_id_in_scope(
    key: InstrumentKey, permit_identity: str | None
) -> str | None:
    """:func:`permit_reservation_id` over ``key``, ``None``-safe in the permit identity.

    The form steps 10 and 14 need: both read the permit identity off an artifact that may not
    carry one yet (step 9's own verdict, or the not-yet-bound attempt), and neither may invent
    an id for an absent one — a fabricated id would be re-read against the log as if it were
    the attempt's, which is exactly the self-report those steps exist to avoid.

    Args:
        key: The attempt's ``(account, instrument)`` scope.
        permit_identity: The permit identity, or ``None``/empty when none is bound.

    Returns:
        The reservation id, or ``None`` when ``permit_identity`` is not concrete.
    """
    if not permit_identity:
        return None
    return permit_reservation_id(key.account, key.instrument, permit_identity)


def attempt_request_reservation_id(
    key: InstrumentKey, attempt: AttemptRequest | None
) -> str | None:
    """The reservation id of a bound attempt request, from the permit identity it carries.

    Args:
        key: The attempt's ``(account, instrument)`` scope.
        attempt: The step-12 attempt request, or ``None`` before step 12 bound one.

    Returns:
        The reservation id, or ``None`` when no attempt is bound yet.
    """
    if attempt is None:
        return None
    return reservation_id_in_scope(key, attempt.action_flow_permit_identity)


def permit_identity_of(
    reservation_id: str, *, account: str, instrument: str
) -> str | None:
    """The permit identity :func:`permit_reservation_id` wrote into ``reservation_id``.

    The inverse direction :mod:`tos_runtime.rcl.reservation_lookup` needs to get from a
    reservation row back to the attempt that committed it. Strips the exact prefix this module
    writes, so an account or instrument containing ``-`` (a KIS account number does:
    ``88888888-01``) is unambiguous — the prefix is known in full, never guessed by splitting.

    Args:
        reservation_id: A reservation id as the log holds it.
        account: The scope account this id must belong to.
        instrument: The scope instrument this id must belong to.

    Returns:
        The permit identity, or ``None`` when ``reservation_id`` is not a per-attempt id of
        this scope (a pre-#966 scope-level row, or another scope's row entirely).
    """
    prefix = f"{scope_reservation_id(account, instrument)}-"
    if not reservation_id.startswith(prefix):
        return None
    permit_identity = reservation_id[len(prefix) :]
    return permit_identity or None
