"""Scope-level RCL reservation identity (TOS Phase 5 W2-R independent-review M6 fix; DRY).

Every compose-root wiring site and every W1/W2 recovery/reconciliation/release site that must
resolve an attempt's ``(account, instrument)`` scope onto the RCL reservation id it shares with
every other attempt in that scope used to hand-write ``f"resv-{account}-{instrument}"``
independently. :mod:`tos_runtime.rcl.obligation`'s own module docstring already named this
formula and the sites that shared it (its own "Reservation-id resolution" section); W2-R's
:mod:`tos_runtime.posttrade.release_consumer` added an eighth hand-written copy — the first one
that WRITES to the RCL log rather than only reading it — and independent review flagged the
duplication itself (2026-09-10, finding M6): a drift on the writer side, with no matching change
elsewhere, produces a silent, fail-closed-but-undetected ``NO_RESERVATION`` hold with no test
catching it. This module is the one place the formula can ever change; every production call
site listed above now imports :func:`scope_reservation_id` instead of re-deriving it.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib only.
"""

from __future__ import annotations

__all__ = ["scope_reservation_id"]


def scope_reservation_id(account: str, instrument: str) -> str:
    """The scope-level RCL reservation id every attempt sharing ``(account, instrument)``
    resolves onto in this compose root (one reservation per scope, not per attempt — every
    caller of this function shares that same design, not merely the same string format).

    Args:
        account: The scope account.
        instrument: The scope instrument.

    Returns:
        ``f"resv-{account}-{instrument}"``.
    """
    return f"resv-{account}-{instrument}"
