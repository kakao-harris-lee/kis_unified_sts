"""Independent-Proposal-Approval vocabulary — the approval-axis StrEnums (design #15 §2.2).

NOT human approval — ``tos.iap`` is **Independent Proposal Approval** (ADR-002-023); the ``iap``
token is a module path, never an order-type / In-App-Purchase value. Human dual-control approval
is ADR-002-015 (§0.2 / §4 non-scope); a human / protective label does **not** substitute for this
automated approval (IAP-INV-013 line 182).

Spec terms = code terms (design #15 §2.2; boundary design #1 §2.4). The enums are authored
**verbatim** from ADR-002-023 (§1 line 17 / §11 line 289 decision result, §12 single-use
consumption, §5.7 line 126 materiality). These are distinct coordinate systems from the
orthostate ``IntentState`` (Intent lifecycle, ``vocabulary.py:32``), the ioc ``ConformanceResult``
(conformance), and the rcl ``CapacityState`` (capacity). Token overlap is possible (e.g. the
strings ``"APPROVE"`` / ``"DENY"`` vs orthostate ``"APPROVED"`` / ``"DENIED"``) but they are
**distinct types on distinct axes** (design #15 §2.2(4)/§2.3): coordinate non-collapse rests on
**distinct types + non-import** — ``tos.iap`` imports none of those sibling axes (sibling edge 0,
§0.4b), so a value from one can never be coerced onto another.

**The critical non-collapse (design #15 §3.5):** :attr:`ApprovalResult.DENY` (a decision-result,
terminal *for the request*, §11 line 296) is **not** orthostate ``IntentState.DENIED`` (an Intent
state that branches from ``APPROVED`` after aggregate-risk/capacity denial, ``vocabulary.py:57``).
An approval ``DENY`` causes **no** Intent transition — the Intent simply stays ``PROPOSED`` (and
orthostate deliberately forbids ``PROPOSED -> DENIED``); ``IntentState.DENIED`` arises downstream
(are/rcl), outside iap. See ``tos/tests/iap/test_seam_orthostate.py``.

**Truthy-sentinel structural seal (design #15 §2.2(1)/§4.7 — the critical seal, #14 M1 adopted
from the start):** the decision / verdict / status / outcome enums are all non-empty ``StrEnum``
strings, so ``if result:`` / ``bool(result)`` would read a denial value (``DENY`` / ``UNKNOWN`` /
``CONSUMED`` / a rejected outcome) as **truthy** — a catastrophic silent fail-open. Every such
enum subclasses :class:`_NonTruthyStrEnum`, whose :meth:`~_NonTruthyStrEnum.__bool__` **raises**
``TypeError``, making them *truthy-untestable*: a future consumer's ``if result:`` misuse surfaces
as an immediate runtime error, never a silent pass. The mandated consume gate is the explicit
positive identity comparison (``result is ApprovalResult.APPROVE`` /
``status is ConsumptionStatus.ELIGIBLE``) — everything else is denial.

Pure module: stdlib only; no ``shared.*``, no sibling ``tos.*`` (design #15 §0.3).
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "ApprovalResult",
    "ConsumptionStatus",
    "MaterialityVerdict",
    "ConsumptionOutcome",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that is deliberately **not truthy-testable** (design #15 §2.2(1)/§4.7/M1).

    Every member is a non-empty string, so a bare ``if result:`` / ``bool(result)`` would read a
    denial member as truthy — a catastrophic silent fail-open. :meth:`__bool__` therefore raises
    ``TypeError`` on every member, so the misuse surfaces as a loud runtime error rather than a
    silent pass. Consumers MUST use the explicit positive-identity gate (``x is ENUM.SAFE_VALUE``).
    Isomorphic to the ioc ``ConformanceResult`` seal, promoted to a shared base here because iap
    has four such enums (DRY) — ``is`` identity, ``.value``, hashing, and ``model_dump`` are all
    unaffected (none calls ``__bool__``).
    """

    def __bool__(self) -> bool:
        """Reject truthiness testing outright (truthy-sentinel seal, design #15 §2.2(1)/M1).

        Raises:
            TypeError: always — the enum is not truthy-testable. Use the explicit positive
                identity gate (e.g. ``result is ApprovalResult.APPROVE``); a bare ``if result:``
                / ``bool(result)`` would fail open on the truthy denial strings.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive "
            "identity gate (e.g. `result is ApprovalResult.APPROVE`; "
            "`status is ConsumptionStatus.ELIGIBLE`) per the truthy-sentinel seal "
            "(design #15 §2.2(1)/§4.7/M1); the denial members are non-empty strings and a "
            "bare `if result:` would fail open."
        )


class ApprovalResult(_NonTruthyStrEnum):
    """The three Independent-Approval decision results (ADR-002-023 §1 line 17 / §11 line 289 verbatim).

    §1 line 17 / §11 line 289 verbatim: "The decision result is ``APPROVE``, ``DENY``, or
    ``UNKNOWN``". Semantics:

    * ``APPROVE`` — "the exact request is eligible to be consumed once by the Intent Registry
      while every binding remains current" (§1 line 21); a **non-authorizing business gate** — it
      is *not* equivalent to ``AUTHORIZED_FOR_CAPACITY``, capacity commitment, Live Authorization,
      capability issuance, or transmission (§11 line 294). The **only** consume-eligible value.
    * ``DENY`` — "terminal for the request" (§11 line 296). A denial. **Not** orthostate
      ``IntentState.DENIED`` (§3.5 / module docstring): a ``DENY`` triggers no Intent transition.
    * ``UNKNOWN`` — "restrictive and requires new evidence or a new request" (§11 line 296); it
      **cannot** be promoted to ``APPROVE`` by repeated evaluation, timeout, majority vote, unused
      capacity, human preference, prior success, or an expected broker rejection (§11 line 296).

    Both ``DENY`` and ``UNKNOWN`` are denial (§11 line 289 "never ``APPROVE``"). Truthy-untestable
    (``__bool__`` raises); the mandated consume gate is ``result is ApprovalResult.APPROVE``.
    """

    APPROVE = "APPROVE"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class ConsumptionStatus(_NonTruthyStrEnum):
    """The single-use decision-consumption states (ADR-002-023 §12 line 302-320).

    The **decision-consumption dimension** (owned by iap) — orthogonal to the orthostate Intent
    dimension (``IntentState``, ``vocabulary.py:32``) and a distinct coordinate system (design #15
    §2.2(2)/§3.5). Two states:

    * ``ELIGIBLE`` — an unconsumed, current ``APPROVE`` decision (§12 line 307 "unconsumed").
    * ``CONSUMED`` — a single-use decision already spent: at most one Approval Consumption Record
      and one immutable Intent (§12 line 312; IAP-INV-006 line 154).

    The transition ``ELIGIBLE -> CONSUMED`` happens **once**; a duplicate *identical* command
    returns the same record (idempotent), a *conflicting* command is rejected, and any re-use is
    rejected (§12 line 313; single-use). Truthy-untestable (``__bool__`` raises); the mandated
    consume gate is ``status is ConsumptionStatus.ELIGIBLE``.
    """

    ELIGIBLE = "ELIGIBLE"
    CONSUMED = "CONSUMED"


class MaterialityVerdict(_NonTruthyStrEnum):
    """Whether an approval-relevant change is material (ADR-002-023 §5.7 line 124-126 / §8 line 230).

    §5.7 line 126 verbatim: "Unknown materiality is material." Three verdicts — ``MATERIAL`` /
    ``IMMATERIAL`` / ``UNKNOWN`` — with the fail-closed rule ``UNKNOWN => MATERIAL`` realized by
    :func:`~tos.iap.predicates.materiality_is_material` (only a positively-``IMMATERIAL`` verdict
    is non-material). Materiality is policy-owned: "The proposer, approval evaluator, Intent
    Registry, consumer, or operator cannot self-exempt a field or dependency" (§8 line 230). It is
    the entry condition for the invalidation dependency closure (§5.4). Truthy-untestable
    (``__bool__`` raises).
    """

    MATERIAL = "MATERIAL"
    IMMATERIAL = "IMMATERIAL"
    UNKNOWN = "UNKNOWN"


class ConsumptionOutcome(_NonTruthyStrEnum):
    """The outcome of one single-use consumption attempt (design #15 §6.2; ADR-002-023 §12 line 306-314).

    The result label the :func:`~tos.iap.state.consumption_transition` state machine returns
    alongside the next :class:`ConsumptionStatus`:

    * ``CONSUMED_NEW`` — the first, admissible consumption (``ELIGIBLE`` + current ``APPROVE`` +
      an equivalent approved-Intent envelope): produces one Consumption Record + one Intent
      creation request (§12 line 306-309).
    * ``IDEMPOTENT_REPLAY`` — a duplicate **identical** command against an already-``CONSUMED``
      decision: the **same** record is returned, no new Intent (§12 line 313).
    * ``REJECTED_INELIGIBLE`` — the decision is not a current ``APPROVE`` / the envelope is not
      equivalent: no consumption (fail-closed).
    * ``REJECTED_CONFLICT`` — a **conflicting** command against a ``CONSUMED`` decision (same
      command identity, different bytes): rejected (§12 line 313).
    * ``REJECTED_REUSE`` — a distinct second consumption attempt against a ``CONSUMED`` decision:
      rejected (single-use; IAP-INV-006 line 154 "at most one immutable Intent").

    Truthy-untestable (``__bool__`` raises); the admissible outcomes are gated by explicit
    identity (``outcome is ConsumptionOutcome.CONSUMED_NEW`` / ``... .IDEMPOTENT_REPLAY``).
    """

    CONSUMED_NEW = "CONSUMED_NEW"
    IDEMPOTENT_REPLAY = "IDEMPOTENT_REPLAY"
    REJECTED_INELIGIBLE = "REJECTED_INELIGIBLE"
    REJECTED_CONFLICT = "REJECTED_CONFLICT"
    REJECTED_REUSE = "REJECTED_REUSE"
