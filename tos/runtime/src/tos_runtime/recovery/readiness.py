"""Recovery readiness vocabulary, the obligation record, and the three predicates the boot
barrier calls — what remained in use of the retired kernel ``tos.sbr`` package (plan
``docs/plans/2026-11-13-tos-code-halving-plan.md`` §S2-c).

``ReadinessVerdict.value`` is persisted (recovery evidence rows and the backup manifest's
``readiness_verdict_at_backup``), so its member values must not change.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import StrEnum

__all__ = [
    "ObligationResult",
    "ReadinessVerdict",
    "RecoveryAuthorityEffect",
    "RecoveryObligation",
    "obligation_graph_closed",
    "recovery_authority_separated",
    "recovery_completion_revives_nothing",
]


class _NonTruthyStrEnum(StrEnum):
    """Not truthy-testable: a denial member is a non-empty string, so ``if verdict:`` would
    fail open. Compare by identity (``verdict is ReadinessVerdict.READY``)."""

    def __bool__(self) -> bool:
        raise TypeError(
            f"{type(self).__name__} is not truthy-testable — use an explicit identity gate "
            "(e.g. `verdict is ReadinessVerdict.READY`)"
        )


class ReadinessVerdict(_NonTruthyStrEnum):
    """The recovery readiness verdict. Never an authority."""

    READY = "READY"
    READY_RESTRICTED = "READY_RESTRICTED"
    NOT_READY = "NOT_READY"


class ObligationResult(_NonTruthyStrEnum):
    """The terminal result of one recovery obligation; only ``SATISFIED`` closes it."""

    SATISFIED = "SATISFIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    TIMED_OUT = "TIMED_OUT"
    CONFLICTED = "CONFLICTED"
    MISSING_SOURCE = "MISSING_SOURCE"


@dataclass(frozen=True)
class RecoveryAuthorityEffect:
    """A recovery verdict's authority effect — every flag must be ``False``."""

    creates_capacity: bool = False
    issues_live_auth: bool = False
    issues_capability: bool = False
    classifies_protective: bool = False
    transmits_broker: bool = False
    grants_rearm: bool = False

    def __post_init__(self) -> None:
        for field in fields(self):
            if getattr(self, field.name) is not False:
                raise ValueError(
                    f"RecoveryAuthorityEffect.{field.name} must be False "
                    "(readiness is not authority)"
                )


@dataclass(frozen=True)
class RecoveryObligation:
    """One recovery obligation: an id, its prerequisites, and its observed result."""

    obligation_id: str | None
    prerequisite_ids: frozenset[str] = frozenset()
    acceptable_results: frozenset[ObligationResult] = frozenset()
    result: ObligationResult | None = None
    obligation_type: str | None = None
    owner: str | None = None
    independent_review_required: bool | None = None
    independent_review_satisfied: bool | None = None


def obligation_graph_closed(obligations: frozenset[RecoveryObligation]) -> bool:
    """Whether the obligation graph is non-empty, uniquely identified, has no dangling
    prerequisite, is acyclic, and every obligation is ``SATISFIED`` within its acceptable
    set (and independently reviewed where that is required). Empty fails closed."""
    if not obligations:
        return False

    by_id: dict[str, RecoveryObligation] = {}
    for obligation in obligations:
        oid = obligation.obligation_id
        if oid is None or oid == "TBD":
            return False
        if oid in by_id:
            return False
        by_id[oid] = obligation

    all_ids = frozenset(by_id)
    for obligation in obligations:
        if not obligation.prerequisite_ids <= all_ids:
            return False
        if obligation.result is not ObligationResult.SATISFIED:
            return False
        if obligation.result not in obligation.acceptable_results:
            return False
        if (
            obligation.independent_review_required is True
            and obligation.independent_review_satisfied is not True
        ):
            return False

    indegree: dict[str, int] = {
        oid: len(by_id[oid].prerequisite_ids) for oid in all_ids
    }
    dependents: dict[str, list[str]] = {oid: [] for oid in all_ids}
    for oid in all_ids:
        for prerequisite in by_id[oid].prerequisite_ids:
            dependents[prerequisite].append(oid)
    ready = [oid for oid in all_ids if indegree[oid] == 0]
    consumed = 0
    while ready:
        node = ready.pop()
        consumed += 1
        for dependent in dependents[node]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
    return consumed == len(all_ids)


def recovery_completion_revives_nothing() -> bool:
    """Recovery completion never revives a prior authority — unconditionally ``True``."""
    return True


def recovery_authority_separated(effect: RecoveryAuthorityEffect | None) -> bool:
    """``True`` only when the effect exists and every authority flag is ``False``.

    There is no operator ready-override input at all: the barrier's verdict comes only
    from :func:`obligation_graph_closed`."""
    if effect is None:
        return False
    return not any(getattr(effect, field.name) for field in fields(effect))
