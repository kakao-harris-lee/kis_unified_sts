"""Item 12's venue/session/tradability/account-facts composite predicate (kernel round #3 §2
decision 4, splitting ``_check_venue_generations`` out of ``gateway.py`` — kernel round #2 §2
decision 1's ``mesh.py`` separation pattern, replicated here).

Two public names live here:

* :func:`venue_session_account_facts_current` — the pure None-propagating AND over the three
  sub-facts item 12's venue/session half rests on. This is the kernel-authored judgement round #1
  §0's common discipline requires ("판정은 커널 술어만 한다"): the owning runtime services
  (:class:`~tos_runtime.calendar.owner.SessionFactsOwner`) compute and supply the three raw
  sub-facts; composing them into one currency verdict happens here, never in compose.
* :func:`venue_generation_item_verdict` — judges item 12
  (:attr:`~tos.egressgw.vocabulary.SendVerifyItem.VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION`)
  in full: the venue/session/tradability/account composite first (kernel round #2 §2 decision 2's
  3-way polarity, extended here per kernel round #3 §11 결정 5 — ``False`` ⇒ ``DENIED``, not folded
  into ``UNKNOWN``), then the independent broker-constraint-generation half.

This module deliberately does **not** import :mod:`tos.egressgw.gateway` (that would be a
circular edge back to the module that imports this one) — the import-closure test pins this
absence structurally, the same way it pins ``mesh.py``'s absence (kernel round #2 §2 decision 1 /
mutation M5; kernel round #3 mutation M4 for this module's own item-12 field/verdict wiring).

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #34 §0.3). No clock, no RNG, no network.
"""

from __future__ import annotations

from tos.egressgw.records import SendBoundaryContext, VerifyItemVerdict, _verdict
from tos.egressgw.vocabulary import SendVerifyItem, VerifyOutcome

__all__ = [
    "venue_generation_item_verdict",
    "venue_session_account_facts_current",
]

#: item 12's venue-half sub-facts, in the order the "first non-positive sub-fact" naming rule
#: (kernel round #3 §2 decision 4) walks them — session first (the owner's own strict-boolean
#: read), then tradability, then account (both ``bool | None`` — ``None`` for a broker-reaching
#: scope with no tradability/account-halt query source yet).
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
    """None-propagating AND over the three venue-half sub-facts (kernel round #3 §2 decision 4).

    ``False`` dominates (any explicitly-negative sub-fact makes the whole conjunction negative,
    regardless of the other two); otherwise ``None`` if any conjunct is unresolved; ``True`` only
    when all three are positively known. Order of the three arguments does not affect the result
    (the AND is commutative) — only :func:`venue_generation_item_verdict`'s reason text cares about
    argument *order*, for naming the first non-positive one.
    """
    values = (session_facts_current, tradability_facts_current, account_facts_current)
    if any(v is False for v in values):
        return False
    if any(v is None for v in values):
        return None
    return True


def _first_non_positive_sub_fact(
    context: SendBoundaryContext,
) -> tuple[str, bool | None]:
    """The first (in :data:`_SUB_FACT_FIELDS` order) sub-fact that is not ``True`` — the one the
    reason text names (kernel round #3 §2 decision 4: "사유 문언은 어느 sub-fact 가 막았는지
    명시(첫 비양성 우선)"). Callers only reach this when the composite is not ``True``, so at
    least one sub-fact is guaranteed to qualify.
    """
    for name in _SUB_FACT_FIELDS:
        value = getattr(context, name)
        if value is not True:
            return name, value
    raise AssertionError(
        "_first_non_positive_sub_fact called with an all-True context — the composite would "
        "be True, so this is unreachable from venue_generation_item_verdict's own branching"
    )


def venue_generation_item_verdict(context: SendBoundaryContext) -> VerifyItemVerdict:
    """Judge item 12 (``VENUE_SESSION_ACCOUNT_AND_BROKER_CONSTRAINT_GENERATION``) in full.

    Two independent halves, venue checked first (unchanged order from the pre-split
    ``gateway._check_venue_generations``, so the reason text's "which half blocked" observation in
    ``tests/compose/test_kis_mock_e2e_honesty.py`` still holds):

    1. **Venue/session/tradability/account** — :func:`venue_session_account_facts_current` over
       the three injected :class:`~tos.egressgw.records.SendBoundaryContext` sub-facts.
       ``False`` ⇒ ``DENIED`` (kernel round #3 §11 결정 5 — an explicit negative sub-fact denies,
       it is not folded into ``UNKNOWN`` the way the pre-round-#3 gate did). ``None`` ⇒
       ``UNKNOWN``. Either way the reason names the first non-positive sub-fact
       (:func:`_first_non_positive_sub_fact`).
    2. **Broker-constraint generation** — only reached once the venue half is positively ``True``.
       ``broker_constraint_generation_current is False`` ⇒ ``DENIED``; ``is None`` ⇒ ``UNKNOWN``;
       ``is True`` ⇒ ``SATISFIED``. This gate judges only the supplied flag's polarity — deriving
       it is the caller's (compose's) job (Phase 4 plan §2 decision 4; kernel round #2 §2
       decision 4).

    Args:
        context: The send-boundary context carrying the three venue sub-facts plus
            ``broker_constraint_generation_current``.

    Returns:
        The :class:`~tos.egressgw.records.VerifyItemVerdict` for item 12.
    """
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
