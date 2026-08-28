"""Authority-effect blocks + non-authoritative grant/decision reference (§4.1).

``capacity != authority`` (RCLP-INV-001/012; ADR-002-002 §7.1; ADR-002-012 §1/§10):
Aggregate Risk / Action Flow decisions and capacity-grant decisions are
**non-authoritative inputs**. They do not mutate, commit, or release capacity —
only a committed RCL transition (the deterministic reducer, §5.2) may. This module
carries the all-false authority block and the content-addressed grant/decision
reference; the ``grant_authorizes_exact_request`` predicate lives in
:mod:`tos.rcl.predicates`.

Pure module: ``pydantic`` + stdlib + ``tos.rcl`` only; no ``shared.*`` (§0.3).
"""

from __future__ import annotations

from tos.rcl._base import AllFalseAuthority, FrozenModel


class RclAuthorityEffect(AllFalseAuthority):
    """Authority effect of a grant / decision / capability / snapshot — all false.

    RCL design §0.1 item 4 / §4.1 layer 1: a non-authoritative artifact
    ``creates_capacity`` no capacity, ``may_mutate_live_state`` nothing,
    ``may_release_capacity`` nothing, ``permits_broker_transmission`` nothing, and
    ``may_rearm`` nothing. Any ``True`` value makes the artifact unconstructable
    (ADR-002-002 §7.1 line 322-331 "issues a capacity grant decision; does not
    directly mutate the Ledger; does not transmit; does not release capacity";
    ADR-002-012 §1 line 31). The full "no capacity-mutation / broker path anywhere"
    proof is EV-L2/L3 (RCLP-EV-002/007).
    """

    creates_capacity: bool = False
    may_mutate_live_state: bool = False
    may_release_capacity: bool = False
    permits_broker_transmission: bool = False
    may_rearm: bool = False


class GrantDecisionRef(FrozenModel):
    """Non-authoritative Aggregate Risk / Action Flow decision reference (§4.1).

    A content reference (id + generation + digest) plus the exact bindings a grant
    must carry to authorize a request (§4.1 layer 3; ADR-002-002 §11.1 step 6 line
    587; ADR-002-012 §8.4 line 461-463 "stale approval cannot be committed against
    changed Ledger state"): the exact committed ``bound_reservation_revision``, the
    exact ``bound_reservation_digest`` (effect digest), and the generation it was
    evaluated under. ``authority_effect`` is all-false — the grant is an input, not
    an authorization. Validity is decided by
    :func:`tos.rcl.predicates.grant_authorizes_exact_request`, never by holding this
    object.
    """

    decision_id: str | None = None
    decision_generation: int | None = None
    canonical_decision_digest: str | None = None
    bound_reservation_revision: int | None = None
    bound_reservation_digest: str | None = None
    bound_generation: int | None = None
    authority_effect: RclAuthorityEffect = RclAuthorityEffect()
