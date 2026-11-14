"""Action-Flow-Governance vocabulary — the action-flow-axis StrEnums (design #16 §2.2)."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum

__all__ = [
    "ActionFlowResult",
    "ActionClassKind",
    "ActionFlowScopeKind",
    "ActionFlowDimensionKind",
    "DocumentedScopeStatus",
    "MaterialChangeKind",
    "ACTION_CLASS_CONSERVATISM_ORDER",
    "ACTION_FLOW_SCOPE_BREADTH_ORDER",
    "ACTION_FLOW_DIMENSION_IDS",
    "AFG_DIMENSION_ID_PREFIX",
    "MATERIAL_CHANGE_KINDS",
    "RESERVED_GUARANTEE_TOKENS",
    "ADMISSIBILITY_ADMISSIBLE",
    "ATTEMPT_STATE_SENT_UNCONFIRMED",
    "ATTEMPT_STATE_SEND_FAILED_PROVEN",
    "BROKER_ORDER_STATE_CANCELLED",
    "BROKER_ORDER_STATE_UNKNOWN",
    "action_flow_dimension_id",
    "is_action_flow_dimension_id",
    "broadest_scope",
    "narrowest_scope",
    "most_conservative_action_class",
]


class ActionFlowResult(StrEnum):
    """The three action-flow decision results (ADR-002-022 §1 line 15 / §5.4 line 125)."""

    GRANT = "GRANT"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


class ActionClassKind(StrEnum):
    """The 9 governed action classes (ADR-002-022 §9 line 258-266 verbatim)."""

    NORMAL_NEW_RISK = "NORMAL_NEW_RISK"
    ORDINARY_REDUCE_OR_EXIT = "ORDINARY_REDUCE_OR_EXIT"
    SAFETY_PROTECTIVE = "SAFETY_PROTECTIVE"
    CANCEL_OR_REPLACE = "CANCEL_OR_REPLACE"
    RECONCILIATION_QUERY = "RECONCILIATION_QUERY"
    SESSION_OR_CONNECTION_CONTROL = "SESSION_OR_CONNECTION_CONTROL"
    HALT_SUPPORT = "HALT_SUPPORT"
    RECOVERY_NON_LIVE = "RECOVERY_NON_LIVE"
    ADMINISTRATIVE_NON_LIVE = "ADMINISTRATIVE_NON_LIVE"


ACTION_CLASS_CONSERVATISM_ORDER: tuple[ActionClassKind, ...] = tuple(ActionClassKind)


class ActionFlowScopeKind(StrEnum):
    """The 17 action-flow limit scopes (ADR-002-022 §10 line 274 verbatim)."""

    GLOBAL = "GLOBAL"
    ENVIRONMENT = "ENVIRONMENT"
    SAFETY_CELL = "SAFETY_CELL"
    BROKER = "BROKER"
    LEGAL_PORTFOLIO = "LEGAL_PORTFOLIO"
    ACCOUNT = "ACCOUNT"
    CREDENTIAL = "CREDENTIAL"
    SESSION = "SESSION"
    CONNECTION_POOL = "CONNECTION_POOL"
    ROUTE = "ROUTE"
    ENDPOINT = "ENDPOINT"
    VENUE = "VENUE"
    INSTRUMENT = "INSTRUMENT"
    STRATEGY = "STRATEGY"
    INTENT = "INTENT"
    CAUSE = "CAUSE"
    ACTION_CLASS = "ACTION_CLASS"


ACTION_FLOW_SCOPE_BREADTH_ORDER: tuple[ActionFlowScopeKind, ...] = tuple(
    ActionFlowScopeKind
)


class ActionFlowDimensionKind(StrEnum):
    """The named action-flow vector dimensions (ADR-002-022 §5.6 line 133; design §2.2-4)."""

    BROKER_REQUEST = "afg.BROKER_REQUEST"
    ORDER = "afg.ORDER"
    ORDER_MUTATION = "afg.ORDER_MUTATION"
    CANCEL_AMEND_REPLACE = "afg.CANCEL_AMEND_REPLACE"
    QUERY = "afg.QUERY"
    SESSION = "afg.SESSION"
    CONNECTION = "afg.CONNECTION"
    CREDENTIAL = "afg.CREDENTIAL"
    ROUTE = "afg.ROUTE"
    ENDPOINT = "afg.ENDPOINT"
    QUEUE = "afg.QUEUE"
    IN_FLIGHT = "afg.IN_FLIGHT"
    CAUSE_AMPLIFICATION = "afg.CAUSE_AMPLIFICATION"


AFG_DIMENSION_ID_PREFIX: str = "afg."

ACTION_FLOW_DIMENSION_IDS: frozenset[str] = frozenset(
    kind.value for kind in ActionFlowDimensionKind
)


class DocumentedScopeStatus(StrEnum):
    """Status of a broker's *documented* limit scope (ADR-002-022 §10 line 276)."""

    VERIFIED_COMPLETE = "VERIFIED_COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    CONTRADICTORY = "CONTRADICTORY"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"


class MaterialChangeKind(StrEnum):
    """The material-change kinds that invalidate a decision / permit (§19 line 413)."""

    POLICY = "POLICY"
    BROKER_LIMIT = "BROKER_LIMIT"
    CONSTRAINT = "CONSTRAINT"
    SESSION = "SESSION"
    CREDENTIAL = "CREDENTIAL"
    ROUTE = "ROUTE"
    ENDPOINT = "ENDPOINT"
    SCOPE_GRAPH = "SCOPE_GRAPH"
    TIME_HEALTH = "TIME_HEALTH"
    QUEUE_IN_FLIGHT = "QUEUE_IN_FLIGHT"
    CAUSE_LINEAGE = "CAUSE_LINEAGE"
    RCL = "RCL"
    PROTECTIVE_RESERVE = "PROTECTIVE_RESERVE"
    CAPABILITY = "CAPABILITY"
    CONSUMER_COMPATIBILITY = "CONSUMER_COMPATIBILITY"


MATERIAL_CHANGE_KINDS: frozenset[str] = frozenset(
    kind.value for kind in MaterialChangeKind
)


ADMISSIBILITY_ADMISSIBLE: str = "ADMISSIBLE"

RESERVED_GUARANTEE_TOKENS: frozenset[str] = frozenset(
    {"PHYSICALLY_RESERVED", "LOGICALLY_RESERVED"}
)

ATTEMPT_STATE_SENT_UNCONFIRMED: str = "SENT_UNCONFIRMED"

ATTEMPT_STATE_SEND_FAILED_PROVEN: str = "SEND_FAILED_PROVEN"

BROKER_ORDER_STATE_CANCELLED: str = "CANCELLED"

BROKER_ORDER_STATE_UNKNOWN: str = "UNKNOWN"


def action_flow_dimension_id(kind: ActionFlowDimensionKind) -> str:
    """The afg ``CapacityVector.dimension_id`` for ``kind`` (Gap-1 convention)."""
    return kind.value


def is_action_flow_dimension_id(dimension_id: str | None) -> bool:
    """Whether ``dimension_id`` is a governed afg action-flow dimension (§2.2-4)."""
    if dimension_id is None:
        return False
    return dimension_id in ACTION_FLOW_DIMENSION_IDS


def broadest_scope(scopes: Iterable[ActionFlowScopeKind]) -> ActionFlowScopeKind | None:
    """The **largest** credible containing scope in ``scopes`` (§10 line 276; C1 rule 2)."""
    present = frozenset(scopes)
    for scope in ACTION_FLOW_SCOPE_BREADTH_ORDER:
        if scope in present:
            return scope
    return None


def narrowest_scope(
    scopes: Iterable[ActionFlowScopeKind],
) -> ActionFlowScopeKind | None:
    """The **smallest** conservative containing scope in ``scopes`` (§1 line 25; C1 rule 1)."""
    present = frozenset(scopes)
    for scope in reversed(ACTION_FLOW_SCOPE_BREADTH_ORDER):
        if scope in present:
            return scope
    return None


def most_conservative_action_class(
    classes: Iterable[ActionClassKind],
) -> ActionClassKind | None:
    """The most conservative class in ``classes`` (§9 line 268 conflict rule)."""
    present = frozenset(classes)
    for action_class in ACTION_CLASS_CONSERVATISM_ORDER:
        if action_class in present:
            return action_class
    return None
