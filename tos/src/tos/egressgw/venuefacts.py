"""Item 12's venue/session/tradability/account-facts composite predicate (kernel round #3 §2"""

from __future__ import annotations

from tos.egressgw.records import SendBoundaryContext, VerifyItemVerdict, _verdict
from tos.egressgw.vocabulary import SendVerifyItem, VerifyOutcome

__all__ = [
    "venue_generation_item_verdict",
    "venue_session_account_facts_current",
]

_SUB_FACT_FIELDS: tuple[str, ...] = (
    "session_facts_current",
    "tradability_facts_current",
    "account_facts_current",
)


def venue_session_account_facts_current(
    session_facts_current: bool | None,
    tradability_facts_current: bool | None,
    account_facts_current: bool | None,
) -> bool | None:
    """None-propagating AND over the three venue-half sub-facts (kernel round #3 §2 decision 4)."""
    values = (session_facts_current, tradability_facts_current, account_facts_current)
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def _first_non_positive_sub_fact(
    context: SendBoundaryContext,
) -> tuple[str, bool | None]:
    """The first (in :data:`_SUB_FACT_FIELDS` order) sub-fact that is not ``True`` — the one the"""
    for name in _SUB_FACT_FIELDS:
        value = getattr(context, name)
        if value is not True:
            return name, value
    raise AssertionError(
        "_first_non_positive_sub_fact called with an all-True context — the composite would "
        "be True, so this is unreachable from venue_generation_item_verdict's own branching"
    )


def venue_generation_item_verdict(context: SendBoundaryContext) -> VerifyItemVerdict:
    """Judge item 12 (``VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION``) in full."""
    item = SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION
    composite = venue_session_account_facts_current(
        context.session_facts_current,
        context.tradability_facts_current,
        context.account_facts_current,
    )
    if composite is not True:
        blocker, blocker_value = _first_non_positive_sub_fact(context)
        outcome = VerifyOutcome.DENIED if composite is False else VerifyOutcome.UNKNOWN
        polarity = "an explicit negative" if composite is False else "unresolved"
        return _verdict(
            item,
            outcome,
            reason=(
                "the venue / session / tradability / account facts are not positively current "
                f"— {blocker} is {blocker_value!r}, the first non-positive sub-fact "
                f"({polarity}; kernel round #3 §2 decision 4 composes these three from the "
                "owning runtime services, never an attestation) — RFC-002 §10.8:741→:761"
            ),
        )
    broker_current = context.broker_constraint_generation_current
    if broker_current is False:
        return _verdict(
            item,
            VerifyOutcome.DENIED,
            reason=(
                "the broker-constraint generation is explicitly not current — the caller is "
                "responsible for deriving this flag from the scope table + INSTANCE (Phase 4 "
                "plan §2 decision 4); this gate judges only the supplied flag's polarity "
                "(kernel round #3 §2 decision 4 extends round #2 §2 decision 4's positivity-only "
                "read to the explicit-False case)"
            ),
        )
    if broker_current is not True:
        return _verdict(
            item,
            VerifyOutcome.UNKNOWN,
            reason=(
                "the broker-constraint generation is not positively current — the caller is "
                "responsible for deriving this flag from the scope table + INSTANCE (Phase 4 "
                "plan §2 decision 4); this gate judges only the supplied flag's positivity "
                "(kernel round #2 §2 decision 4)"
            ),
        )
    return _verdict(
        item,
        VerifyOutcome.SATISFIED,
        reason=(
            "venue / session / tradability / account facts and the broker-constraint "
            "generation are both current — the venue half is composed from three owning-"
            "runtime-service sub-facts (kernel round #3 §2 decision 4, replacing the retired "
            "operator attestation); the broker-constraint half is derived (Phase 4 plan §2 "
            "decision 4)"
        ),
    )
