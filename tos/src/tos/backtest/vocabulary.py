"""Closed D-E3 harness vocabulary — fill modes, settlement, scenarios (design #33 §4/§5).

Everything the harness dispatches on is a **closed enumeration** here, inheriting the
:mod:`tos.engine.vocabulary` closure discipline: an unknown member is a fail-closed error, never a
silent drop, and every gate is positive membership.

**Nothing in this module re-authors the engine.** The result kinds a fill produces
(:class:`~tos.engine.EgressResultKind`), the halt reasons, the commitment steps, and the event kinds
are all the engine's closed vocabulary and are **imported**, never mirrored (design #33 §0.2-1 /
§7.1). What lives here is only the harness's own vocabulary: *how* a deterministic fill model is
parameterised, *when* it settles, and *which* mandated scenario a run realizes.

Two seals:

1. **Truthy-sentinel seal** (#14 M1 / #19 / #23 precedent, mirrored for D-E3's own verdict-shaped
   enum). :class:`SettlementStatus` has non-empty string members, so ``if status:`` would read
   ``UNSETTLED_AT_STREAM_END`` as *truthy* — a silent fail-open. ``__bool__`` therefore raises.
   The purely descriptive enums (:class:`FillMode`, :class:`SettlementPolicy`,
   :class:`ExecutionPriceBasis`, :class:`FillSide`, :class:`QuantityProvenance`,
   :class:`ScenarioId`) are *not* verdict-shaped — no gate reads them as a pass/deny — so they stay
   plain ``StrEnum`` rather than acquiring a seal that would only add noise.
2. **No ``FILLED_OPTIMISTICALLY`` / no performance member.** There is no member by which a fill
   model could declare a better-than-modelled execution: optimistic cost is an ADR-DEV-010 §8:189-190
   disqualifier, and the harness's structural answer is that the vocabulary offers no such word.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from enum import StrEnum

from tos.engine import EgressResultKind

__all__ = [
    "MANDATED_SCENARIO_IDS",
    "ExecutionPriceBasis",
    "FillMode",
    "FillSide",
    "QuantityProvenance",
    "ScenarioId",
    "SettlementPolicy",
    "SettlementStatus",
    "settleable_result_kinds",
]


class _NonTruthyStrEnum(StrEnum):
    """A ``StrEnum`` that refuses truthiness testing (truthy-sentinel seal, #14 M1 precedent).

    Every member is a non-empty string, so ``if value:`` would read an *unsettled* state as a
    *settled* one. Raising makes that misuse an immediate ``TypeError`` instead of a silent
    fail-open; consumers must use an explicit positive-identity gate.
    """

    def __bool__(self) -> bool:
        """Reject truthiness outright.

        Raises:
            TypeError: always — use the explicit positive-identity gate instead.
        """
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive-identity "
            "gate (e.g. `status is SettlementStatus.SETTLED`); a bare `if value:` would read an "
            "unsettled fill as a settled one (design #33 §13; #14 M1 precedent)"
        )


class FillMode(StrEnum):
    """The injected deterministic outcome family a fill model applies (design #33 §4.2).

    Every member is a **rule**, never a draw: the model has zero stochastic components and every
    decision is a deterministic function of ``(bar, injected parameters)`` (design #33 §4.4). The
    seed slot is a forward seam and stays unused (RFC-003 §10:360-363).

    ``SETTLE`` is the only mode that produces a magnitude, and inside it the fill/partial/reject
    distinction is **structurally derived**: the price-band predicate decides REJECT, and the
    filled/remaining magnitudes decide FULL vs PARTIAL (구조 파생 > 자기신고 — the model never
    declares a kind it has not derived; ``EgressResultPayload`` re-checks it at
    ``records.py:221-229``).
    """

    #: Derive the result from the settlement bar: band predicate ⇒ REJECT, else magnitudes ⇒
    #: FULL_FILL / PARTIAL_FILL.
    SETTLE = "SETTLE"
    #: The injected "immediate ack" mode — an acknowledgement carries no magnitude.
    ACKNOWLEDGE = "ACKNOWLEDGE"
    #: The injected "unconfirmed" scenario — neither a rejection nor safe to retry.
    REPORT_UNKNOWN = "REPORT_UNKNOWN"
    #: The injected timeout scenario (design #31 §2.1 edge (i) / J1).
    REPORT_TIMEOUT = "REPORT_TIMEOUT"


class SettlementPolicy(StrEnum):
    """When a staged fill settles, relative to the bar whose tick produced it (design #33 §3.6).

    ``NEXT_BAR`` is **execution realism, not look-ahead**: look-ahead is using future data to
    *decide* (ADR-DEV-010 §8:182-184), whereas settling on a later bar is filling in the future.
    Decision inputs stay prefix-bounded (design #33 §3.6 / §12.2-4), and the causal order of the
    re-injected result is carried by the driver's yield-order counter, not by the bar index
    (design #33 §3.4 MAJOR-1).
    """

    SAME_BAR = "SAME_BAR"
    NEXT_BAR = "NEXT_BAR"


class ExecutionPriceBasis(StrEnum):
    """Which settlement-bar price the deterministic execution price is built from (§4.3)."""

    OPEN = "OPEN"
    CLOSE = "CLOSE"


class FillSide(StrEnum):
    """The injected side a scenario's single order takes (design #33 §4.3 "시나리오 파라미터").

    ⚠ **Scenario parameter, not flow-derived.** Slice #1's flow carries no concrete quantity, side,
    or price: ``Proposal`` holds a ``quantity_basis`` that is "evidence, never capacity"
    (``proposal.py:128``) and ``AttemptRequest`` holds digests only (``records.py:317-334``). The
    side is therefore injected and **labelled** as injected — deriving it from a stand-in would be
    inventing provenance the slice does not have.
    """

    BUY = "BUY"
    SELL = "SELL"


class SettlementStatus(_NonTruthyStrEnum):
    """Whether a staged fill reached its settlement bar (design #33 §4.1)."""

    SETTLED = "SETTLED"
    #: The bar stream ended before the staged fill's settlement bar arrived. The harness records
    #: this **as-is** and invents no settlement bar: fabricating one would manufacture data the
    #: run never had (design #33 §13 fail-open-in-wiring seal).
    UNSETTLED_AT_STREAM_END = "UNSETTLED_AT_STREAM_END"


class QuantityProvenance(StrEnum):
    """Where a recorded fill magnitude came from (design #33 §4.3 정직 라벨).

    Slice #1 has exactly one member because slice #1 has exactly one honest source: the injected
    scenario. Concrete quantity derivation (Order Construction, ADR-002-020 step 2) is a provisional
    stand-in here, so a magnitude claiming flow provenance would be a phantom.
    """

    SCENARIO_PARAMETER = "SCENARIO_PARAMETER"


class ScenarioId(StrEnum):
    """The mandated single-order scenario set (design #33 §5.1, rows A and 1-7).

    Every member is NIT-3 consistent: **at most one order per scope** for the lifetime of the run,
    because the provisional projection has no release path (``state.py:22``) and a scope stays
    occupied (``state.py:28-29``). Round-trip (entry → flat on the same scope) is deliberately
    absent — its *blocking* is what :data:`AT_MOST_ONE_FIRING` demonstrates, and the real exit send
    waits for the RCL release path (design #33 §2.2/§2.5).
    """

    #: Row A — entry → ACK. Knowledge advances to ACKNOWLEDGED while capacity is unchanged.
    ENTRY_ACK = "ENTRY_ACK"
    #: Row 1 — entry → FULL_FILL (POSITION_CONSUMED / FILLED).
    ENTRY_FULL_FILL = "ENTRY_FULL_FILL"
    #: Row 2 — entry → PARTIAL_FILL (PARTIALLY_CONSUMED / PARTIALLY_FILLED; nothing re-requested).
    ENTRY_PARTIAL_FILL = "ENTRY_PARTIAL_FILL"
    #: Row 3 — entry → REJECT (RELEASE_PENDING_PROOF / REJECTED; the scope stays occupied).
    ENTRY_REJECT = "ENTRY_REJECT"
    #: Row 4a — entry → UNKNOWN (POTENTIALLY_LIVE retained; nothing resubmitted).
    ENTRY_UNKNOWN = "ENTRY_UNKNOWN"
    #: Row 4b — entry → TIMEOUT (same conservatism as UNKNOWN; never read as a rejection).
    ENTRY_TIMEOUT = "ENTRY_TIMEOUT"
    #: Row 5 — a stage deny / UNKNOWN / missing stops the flow; nothing is handed off.
    FAIL_CLOSED_HALT = "FAIL_CLOSED_HALT"
    #: Row 6 — multi-bar: bar 1 realizes the entry, bar 2+ is denied at the capacity stage. The
    #: **positive** demonstration of the at-most-one seal firing (design #33 §2.3).
    AT_MOST_ONE_FIRING = "AT_MOST_ONE_FIRING"
    #: Row 7 — a flat-only run on a fresh scope: a single order, not a round trip (design #33 §2.5).
    FLAT_ONLY = "FLAT_ONLY"


#: The mandated scenario ids in the design's own table order (design #33 §5.1). Tuple order **is**
#: the contract, mirroring the engine's ``COMMITMENT_FLOW_ORDER`` discipline.
MANDATED_SCENARIO_IDS: tuple[ScenarioId, ...] = (
    ScenarioId.ENTRY_ACK,
    ScenarioId.ENTRY_FULL_FILL,
    ScenarioId.ENTRY_PARTIAL_FILL,
    ScenarioId.ENTRY_REJECT,
    ScenarioId.ENTRY_UNKNOWN,
    ScenarioId.ENTRY_TIMEOUT,
    ScenarioId.FAIL_CLOSED_HALT,
    ScenarioId.AT_MOST_ONE_FIRING,
    ScenarioId.FLAT_ONLY,
)


def settleable_result_kinds(mode: FillMode) -> frozenset[EgressResultKind]:
    """The engine result kinds a fill mode may produce — positive membership (design #33 §4.2).

    The mapping is exhaustive over :class:`FillMode`; an unmapped mode raises rather than silently
    producing nothing, because a mode the harness cannot settle is a fail-closed error, not a no-op.

    Args:
        mode: The injected fill mode.

    Returns:
        The closed set of :class:`~tos.engine.EgressResultKind` members the mode may emit.

    Raises:
        KeyError: If the mode is outside the closed mapping (fail-closed).
    """
    return {
        FillMode.SETTLE: frozenset(
            {
                EgressResultKind.FULL_FILL,
                EgressResultKind.PARTIAL_FILL,
                EgressResultKind.REJECT,
            }
        ),
        FillMode.ACKNOWLEDGE: frozenset({EgressResultKind.ACK}),
        FillMode.REPORT_UNKNOWN: frozenset({EgressResultKind.UNKNOWN}),
        FillMode.REPORT_TIMEOUT: frozenset({EgressResultKind.TIMEOUT}),
    }[mode]
