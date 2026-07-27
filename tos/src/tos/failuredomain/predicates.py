"""The three domain-agnostic failure-domain predicates (design #27 §4 — exactly three).

``tos.failuredomain`` is the thinnest package in the series **by design** (design #27 §0.4a):
ADR-002-009 is an integration / ownership-partition layer sitting on top of ADR-002-001 through
-008, so almost every L1-decidable proposition it states is **already owned by a sibling** and is
attributed there by the design #27 §3.5 ownership table rather than re-authored (DRY, CLAUDE.md).
What is left — and all that is authored here — are **exactly three** predicates that generalize
to no sibling's domain-specific instance because they are the §1 core principle itself:

1. :func:`unproven_isolation_is_common_mode`   — ADR §1 line 32, §4.4, §5 line 130;
2. :func:`new_risk_blocked_by_unproven_isolation` — ADR §1 line 32, structurally realizing the
   §18.2 / §18.6 / §18.7 rejections;
3. :func:`decision_sole_sourced_from_volatile` — ADR §8.2, §8.3, §10.1 item 5.

**Exactly three, and no fourth** (design #27 §3.4/§9.3-2): the §4.4 cell-partitioning numeric
predicate was withdrawn to rcl ``credible_union_capacity`` (ADR §13 line 322: "Aggregate capacity
remains serialized by the Risk Capacity Ledger"), and the §8.4 line 228 partition three-boolean
is a deliberate deferral (design #27 §9.3-4). Over-authoring is this package's biggest hazard.

**Polarity discipline.** Every predicate here **blocks or classifies**; none grants. Positive
authority is a sibling's (``tos.authority`` / ``tos.liveauth`` / ``tos.rcl`` / ``tos.egress``),
so a ``False`` from :func:`new_risk_blocked_by_unproven_isolation` means *not blocked by this
check*, never *permitted*. Unproven / unestablished / absent / ``None`` never becomes vacuously
permissive, and no predicate reads a value for truthiness — comparisons are ``is`` identity
against a member, an explicit ``is None``, or an explicit ``len(...) > 0`` plus a blank-string
rejection, so a whitespace-only or empty-string "statement" can never forge presence.

**No enforcement, no mechanism.** ADR §1 line 15: "Separate processes, services, containers,
nodes, or names do not by themselves prove isolation." These predicates classify; the actual
fences, partitions, and credential isolation live in the siblings and the runtime — including the
**six distinct sibling hard-fence owners** (authority ``hard_fence_proven``, rcl ``writer_fenced``,
afg ``stale_writer_hard_fenced``, sbr ``competing_owner_fenced``, cur ``fence_advances_floor``,
ioc ``mutation_fence_holds``), none of which is re-authored here (design #27 §3.5-3).

Regime tag: **EV-L1 predicate substrate only; closes no FD-EV; FD-EV-001..012 remain
NOT_IMPLEMENTED pending EV-L3(+Security) fault injection; the L1-decidable content is
sibling-owned per design #27 §3.5.**

Pure module: stdlib + ``tos.failuredomain`` only; no ``pydantic`` call, no ``shared.*``, no
sibling ``tos.*`` (design #27 §0.3).
"""

from __future__ import annotations

from tos.failuredomain.records import IsolationClaim
from tos.failuredomain.vocabulary import (
    ExplicitlyAnalyzedEmpty,
    FailureDomainKind,
    IsolationClaimStatus,
)

__all__ = [
    "decision_sole_sourced_from_volatile",
    "new_risk_blocked_by_unproven_isolation",
    "unproven_isolation_is_common_mode",
]


def _tokens_positively_listed(value: frozenset[str] | None) -> bool:
    """Whether a claim field positively lists at least one non-blank entry.

    ``None`` (never analysed) and a bare ``frozenset()`` (nothing listed, unmarked) are both
    **not** positively present — ADR §5 line 130 "Unknown, untested, or undocumented sharing
    SHALL be recorded as common-mode". A set whose entries are empty or whitespace-only is a
    blank forgery and is likewise rejected: presence is a *statement*, not a non-``None``
    container.
    """
    if value is None:
        return False
    if len(value) == 0:
        return False
    return all(item.strip() != "" for item in value)


def _exclusions_positively_analyzed(
    value: ExplicitlyAnalyzedEmpty | frozenset[str] | None,
) -> bool:
    """Whether ``excluded_common_modes`` was positively analysed (design #27 §4.1, ``∅`` both ways).

    The one §4.4 field where a *positively analysed* empty result is meaningful: an analysis
    that found no common mode to exclude is complete, whereas an unanalysed field is not. The
    :class:`~tos.failuredomain.vocabulary.ExplicitlyAnalyzedEmpty` marker separates them, so a
    vacuous ``∅`` can never buy an ``ESTABLISHED`` **and** a legitimate positively-empty
    analysis is not blocked either (both directions are canaried).

    The marker is matched by ``is`` identity against the single closed member — never by
    truthiness, and never by string equality (the marker is deliberately not a ``str``).
    """
    if value is ExplicitlyAnalyzedEmpty.EXPLICITLY_ANALYZED_EMPTY:
        return True
    return _tokens_positively_listed(value)


def _reject_foreign_domain_members(
    domains: frozenset[FailureDomainKind], parameter: str
) -> None:
    """Refuse any member that is not exactly a ``FailureDomainKind`` (design #27 §3.3).

    ``FailureDomainKind`` is a plain ``StrEnum``, so ``"ACCOUNT"`` and the *other* axis's
    ``rlp.ScopeDimension.ACCOUNT`` both hash and compare **equal** to
    ``FailureDomainKind.ACCOUNT``: a set operation would accept them silently and the
    proposition-identity boundary the §3.3 seam exists to hold would be crossed without a trace.
    A mistyped ``"CACHEE"`` is worse — it simply fails to match the volatile set and turns the
    verdict fail-open ``False``.

    Both are structural errors in the caller, not conservative outcomes to be classified, so
    they raise instead of returning. Uses ``type(...) is not`` rather than ``isinstance`` so a
    subclass cannot slip through either.
    """
    for domain in domains:
        if type(domain) is not FailureDomainKind:
            raise TypeError(
                f"{parameter} must contain only FailureDomainKind members; got "
                f"{domain!r} of type {type(domain).__name__} — a raw string or a member of "
                "another axis compares equal to this taxonomy and would cross the design #27 "
                "§3.3 proposition-identity seam silently"
            )


def _statement_positively_present(value: str | None) -> bool:
    """Whether a free-text claim field carries an actual statement.

    ``None`` and a blank / whitespace-only string are both absent: ADR §4.4 requires the claim
    to *state* residual risk, and ``" "`` states nothing. Checking ``strip() != ""`` rather than
    truthiness closes the whitespace forgery a bare ``if value:`` would let through.
    """
    if value is None:
        return False
    return value.strip() != ""


def _isolation_claim_status(claim: IsolationClaim | None) -> IsolationClaimStatus:
    """Classify a claim onto the ADR §4.4 / §1 line 32 status axis (design #27 §4.1 helper).

    Private on purpose: design #27 §3.4 fixes the public predicate surface of this package at
    **exactly three**, and this classifier is the internal step
    :func:`unproven_isolation_is_common_mode` folds (design #27 §4.1).

    ``ESTABLISHED`` requires the **positive identity conjunction** of all five ADR §4.4 line 96
    fields — "Every claim SHALL state assumptions, excluded common modes, enforcement
    mechanisms, verification cases, and residual risk" — and nothing else can produce it. A
    missing claim is ``UNKNOWN``; anything present but incomplete is ``COMMON_MODE`` (ADR §1
    line 32). ``UNKNOWN`` and ``COMMON_MODE`` are treated identically conservatively by every
    caller; they stay distinct only so a reviewer can tell "analysed, found common-mode" from
    "never claimed".

    Args:
        claim: The isolation claim, or ``None`` when none was made.

    Returns:
        ``UNKNOWN`` for an absent claim, ``ESTABLISHED`` only for a complete one, otherwise
        ``COMMON_MODE``.
    """
    if claim is None:
        return IsolationClaimStatus.UNKNOWN
    if (
        _tokens_positively_listed(claim.assumptions)
        and _exclusions_positively_analyzed(claim.excluded_common_modes)
        and _tokens_positively_listed(claim.enforcement_mechanisms)
        and _tokens_positively_listed(claim.verification_cases)
        and _statement_positively_present(claim.residual_risk)
    ):
        return IsolationClaimStatus.ESTABLISHED
    return IsolationClaimStatus.COMMON_MODE


def unproven_isolation_is_common_mode(claim: IsolationClaim | None) -> bool:
    """Whether an isolation claim falls back to common-mode (ADR §1 line 32; design #27 §4.1).

    ADR-002-009 §1 line 32 verbatim: "**If an asserted isolation property cannot be positively
    established, the affected paths SHALL be classified as common-mode.**" ADR §5 line 130:
    "Unknown, untested, or undocumented sharing SHALL be recorded as common-mode. It SHALL NOT
    be recorded as independent with an explanatory footnote."

    So ``True`` (= common-mode, the conservative default) whenever any of the ADR §4.4 five
    fields is absent, blank, or a bare unmarked ``∅``, and whenever ``claim is None``. ``False``
    (= established) **only** on the positive conjunction of all five — which is why there is no
    ``independent`` flag anywhere on
    :class:`~tos.failuredomain.records.FailureDomainAllocationEntry` to set instead.

    This classifies; it enforces nothing. The general cross-domain claim shape here is **not**
    sbr ``restricted_isolation_proven`` / ``IsolationFacts.all_proven`` (recovery-readiness,
    eight axes, ADR-002-017 §17), which stays sibling-owned and is referenced only by token
    (design #27 §3.5-1).

    Args:
        claim: The claim to classify, or ``None`` when none was made.

    Returns:
        ``True`` iff the claim does not positively establish isolation. [SAFE-030, SAFE-031]
    """
    return _isolation_claim_status(claim) is not IsolationClaimStatus.ESTABLISHED


def new_risk_blocked_by_unproven_isolation(
    status: IsolationClaimStatus | None,
) -> bool:
    """Whether new risk is blocked by an unestablished isolation claim (ADR §1 line 32).

    ADR-002-009 §1 line 32 verbatim: an unestablished isolation property "SHALL reduce
    authority, consume conservative capacity where economic state is uncertain, and **block new
    risk**. It SHALL NOT be converted into permission by **redundancy count, operator
    confidence, a healthy dashboard, replay capability, or an audit trail**."

    Those five would-be excuses are **structurally absent from this signature** (design #27 §4.2,
    M4): there is no ``redundancy_count``, no ``operator_confident``, no ``dashboard_healthy``,
    no ``replay_available`` and no ``audit_present`` parameter, so a caller cannot pass one and
    no future edit can make one permissive without changing the signature. This is the
    executable form of the ADR §18.2 ("High availability proves safety isolation" — rejected:
    "Availability redundancy can preserve the same unsafe authority or create split brain"),
    §18.6 ("Priority guarantees protective access" — rejected) and §18.7 ("A healthy dashboard
    proves containment" — rejected: "Observability and replay do not substitute for prevention")
    rejections.

    Negative polarity: ``True`` means *blocked*. ``None`` (no status at all) blocks, exactly like
    ``COMMON_MODE`` and ``UNKNOWN``. A ``False`` means only *not blocked by this check* — it is
    **not** a permission; granting authority is ``tos.authority`` / ``tos.liveauth`` business and
    the actual hard-fence proof is authority ``hard_fence_proven`` (design #27 §2.2/§3.5-3).

    Args:
        status: The isolation-claim status, or ``None`` when unknown.

    Returns:
        ``True`` iff ``status`` is not positively ``ESTABLISHED``. [SAFE-041, SAFE-051]
    """
    return status is not IsolationClaimStatus.ESTABLISHED


def decision_sole_sourced_from_volatile(
    support_domains: frozenset[FailureDomainKind],
    volatile_domains: frozenset[FailureDomainKind] | None,
) -> bool | None:
    """Whether a decision rests only on volatile domains (ADR §8.2 / §8.3 / §10.1 item 5).

    ADR-002-009 §8.3 line 212: "Redis or any other cache **SHALL NOT be the sole source** of
    current permission, revocation state, Final Quantity Proof, or capacity release", and line
    214: "Cache miss, expiration, eviction, restart, or stale replica read SHALL fail closed for
    permissive decisions." §8.2 line 206: "Receipt of an allow event is not continuing authority,
    and **absence of a deny event is not proof of permission**." §10.1 item 5 line 282: "their
    absence, deletion, expiry, or recovery **never establishes current permission** or clears the
    deny latch."

    Which domains count as volatile is **injected**, never hardcoded (design #27 §4.3, M5): the
    volatile set is per-deployment / per-broker profile business, so passing ``None`` means the
    profile has not established it and the answer is ``None`` (unknown ⇒ the consumer fails
    closed), not a guess.

    ``∅`` both ways:

    * ``support_domains`` empty ⇒ ``True`` — a decision with **no** support has no non-volatile
      basis at all, the worst case, and the subset law ``∅ ⊆ anything`` yields exactly that
      (deliberate, not incidental);
    * ``volatile_domains`` empty **but injected** ⇒ any non-empty support is non-volatile ⇒
      ``False``, so a profile that positively declares nothing volatile is not blocked.

    This is a **domain-agnostic structural classification only**. The runtime currentness proof
    and latch — the mechanism that actually refuses to admit — is cur ``ProofResult.UNKNOWN`` ⇒
    non-admit / ``CurrentnessAdmission`` / ``fence_advances_floor``, which is sibling-owned and
    not re-authored here (design #27 §3.5 §8.3 seam).

    **Foreign members are rejected loudly** (design #27 §3.3 proposition-identity seal): the
    subset test is a set operation over ``str``-backed members, so a raw ``"CACHE"`` or a
    look-alike member of *another* axis (rlp ``ScopeDimension.ACCOUNT``, which shares the token
    ``ACCOUNT`` with this taxonomy) would hash-compare **equal** and silently cross the seam,
    while a mistyped ``"CACHEE"`` would silently drop out of the volatile set and return a
    fail-open ``False``. Both are refused with :class:`TypeError` rather than answered.

    Args:
        support_domains: The failure domains the decision's support actually comes from. Every
            member must be a :class:`~tos.failuredomain.vocabulary.FailureDomainKind`.
        volatile_domains: The injected volatile domain set, or ``None`` when the profile has not
            established it. Same member-type requirement when it is not ``None``.

    Returns:
        ``True`` iff the support is drawn solely from volatile domains, ``False`` when some
        support is non-volatile, and ``None`` when the volatile set is not established.
        [SAFE-030, SAFE-048]

    Raises:
        TypeError: If any member of either set is not exactly a ``FailureDomainKind``.
    """
    _reject_foreign_domain_members(support_domains, "support_domains")
    if volatile_domains is None:
        return None
    _reject_foreign_domain_members(volatile_domains, "volatile_domains")
    return support_domains <= volatile_domains
