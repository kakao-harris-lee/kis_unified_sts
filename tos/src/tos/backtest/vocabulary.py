"""Closed D-E3 harness vocabulary — fill modes, settlement, scenarios (design #33 §4/§5)."""

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
    """A ``StrEnum`` that refuses truthiness testing (truthy-sentinel seal, #14 M1 precedent)."""

    def __bool__(self) -> bool:
        """Reject truthiness outright."""
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit positive-identity "
            "gate (e.g. `status is SettlementStatus.SETTLED`); a bare `if value:` would read an "
            "unsettled fill as a settled one (design #33 §13; #14 M1 precedent)"
        )


class FillMode(StrEnum):
    """The injected deterministic outcome family a fill model applies (design #33 §4.2)."""

    SETTLE = "SETTLE"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    REPORT_UNKNOWN = "REPORT_UNKNOWN"
    REPORT_TIMEOUT = "REPORT_TIMEOUT"
    REPORT_CANCEL_ACK = "REPORT_CANCEL_ACK"
    REPORT_EXPIRED = "REPORT_EXPIRED"


class SettlementPolicy(StrEnum):
    """When a staged fill settles, relative to the bar whose tick produced it (design #33 §3.6)."""

    SAME_BAR = "SAME_BAR"
    NEXT_BAR = "NEXT_BAR"


class ExecutionPriceBasis(StrEnum):
    """Which settlement-bar price the deterministic execution price is built from (§4.3)."""

    OPEN = "OPEN"
    CLOSE = "CLOSE"


class FillSide(StrEnum):
    """The injected side a scenario's single order takes (design #33 §4.3 "시나리오 파라미터")."""

    BUY = "BUY"
    SELL = "SELL"


class SettlementStatus(_NonTruthyStrEnum):
    """Whether a staged fill reached its settlement bar (design #33 §4.1)."""

    SETTLED = "SETTLED"
    UNSETTLED_AT_STREAM_END = "UNSETTLED_AT_STREAM_END"


class QuantityProvenance(StrEnum):
    """Where a recorded fill magnitude came from (design #33 §4.3 정직 라벨)."""

    SCENARIO_PARAMETER = "SCENARIO_PARAMETER"


class ScenarioId(StrEnum):
    """The mandated single-order scenario set (design #33 §5.1, rows A and 1-7)."""

    ENTRY_ACK = "ENTRY_ACK"
    ENTRY_FULL_FILL = "ENTRY_FULL_FILL"
    ENTRY_PARTIAL_FILL = "ENTRY_PARTIAL_FILL"
    ENTRY_REJECT = "ENTRY_REJECT"
    ENTRY_UNKNOWN = "ENTRY_UNKNOWN"
    ENTRY_TIMEOUT = "ENTRY_TIMEOUT"
    FAIL_CLOSED_HALT = "FAIL_CLOSED_HALT"
    AT_MOST_ONE_FIRING = "AT_MOST_ONE_FIRING"
    FLAT_ONLY = "FLAT_ONLY"


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
    """The engine result kinds a fill mode may produce — positive membership (design #33 §4.2)."""
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
        FillMode.REPORT_CANCEL_ACK: frozenset({EgressResultKind.CANCEL_ACK}),
        FillMode.REPORT_EXPIRED: frozenset({EgressResultKind.EXPIRED}),
    }[mode]
