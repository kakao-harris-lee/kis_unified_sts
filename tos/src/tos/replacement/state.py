"""replacement workflow-lifecycle + authorization-currentness predicates (§5.3/§6.2).

The decision rules that concern **workflow state and state over time** (design #18
§5.3 / §5.4 / §6.2):

* **label-grants-nothing (§5 line 137/139, §9 line 245)** —
  :func:`workflow_label_grants_nothing` and :func:`workflow_record_axes_not_collapsed`:
  a lifecycle label is a non-authoritative coordinate, and the five §5 line 107 axes stay
  five separate fields;
* **authorization currentness / expiry (§7 line 201-203)** —
  :func:`replacement_authorization_current` and
  :func:`expiry_releases_no_economic_effect`: a material change invalidates the
  authorization, and expiry blocks only *future transmission* — it never expires the
  economic effect of an already-transmitted old or new order;
* **append-only generation order (§5 / §7 line 196 / §16)** —
  :func:`workflow_generation_order` and :func:`workflow_generation_append_only`.

**Transition validity is deliberately absent (design #18 §5.3, Open Q3).** Whether one
:class:`~tos.replacement.vocabulary.ReplacementWorkflowState` may follow another depends
on the rcl capacity commit, the orthostate attempt state, and per-leg ADR-002-019
admissibility — all runtime gates (EV-L3) — exactly as orthostate owns
``attempt_transition_allowed``. Phase 1 authors the vocabulary, label-grants-nothing, and
the no-collapse structure only; nothing here *sets* a state.

The append-only generation order is **not** re-authored: it REUSES ``tos.ordering``
(``Ordering`` / ``OrderingEvent`` / ``compare_order``, which depends only on
``tos.canonical``) — design #18 §3.2. **A wall clock never orders**: §15 line 349 "Every
measured duration SHALL use ADR-002-008 trustworthy time" and §7 line 203 "Authorization
expiry ... does not expire the economic effect", so ``tos.replacement`` reads **no**
clock at all — time-health generation, expiry, and trustworthiness are injected flags
produced by ``tos.time`` / the authorization runtime.

Pure module: ``pydantic`` + stdlib + ``tos.ordering`` + ``tos.canonical`` (via the
records) only; **no sibling** ``tos.*`` (sibling edge 0, design #18 §0.3/§0.4b).
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.ordering import Ordering, OrderingEvent, compare_order
from tos.replacement.records import (
    ReplacementAuthorityEffect,
    ReplacementWorkflowRecord,
)
from tos.replacement.vocabulary import ORTHOGONAL_WORKFLOW_AXES

__all__ = [
    # §5.3 label-grants-nothing + no-collapse
    "workflow_label_grants_nothing",
    "workflow_record_axes_not_collapsed",
    # §6.2 authorization currentness / expiry
    "replacement_authorization_current",
    "expiry_releases_no_economic_effect",
    # §3.2 append-only generation order (tos.ordering REUSE)
    "workflow_generation_order",
    "workflow_generation_append_only",
]


# ===========================================================================
# §5.3 label-grants-nothing + §5 line 107 no-collapse
# ===========================================================================


def workflow_label_grants_nothing(effect: ReplacementAuthorityEffect | None) -> bool:
    """Whether a replacement label / record grants no authority (ADR §5 line 137).

    §5 line 137 verbatim: "**No lifecycle label by itself authorizes capacity release or
    removal of protection.**" §5 line 139: "No lifecycle label or 'protective'
    classification proves that cancel, amend, replace, reduce-only, or new protection is
    executable." §9 line 245: "Workflow completion, timeout, authority expiry, cancel ACK,
    or local terminal state is insufficient" to reduce capacity.

    :class:`~tos.replacement.records.ReplacementAuthorityEffect` already rejects any
    ``True`` flag at construction, so on the normal validation path this predicate is
    unconditionally ``True`` for every constructible block **and for every workflow state,
    including ``COMPLETED``**. It exists as **defence in depth**: ``model_construct``
    skips validators, so a forged block can carry a ``True`` (or a truthy non-``bool``
    such as ``1`` / ``"yes"`` / ``[1]``) flag. The re-check therefore demands every
    declared flag be the singleton ``False`` — ``is not True`` would clear ``1`` and
    ``"yes"``, which is why the check is ``is False``.

    A ``None`` block is **not** a pass: a missing authority block is unknown, not
    all-false (design #18 §4.7 row 12 — the ∅ workflow state has no permissive side).

    Args:
        effect: The authority block to re-check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff every declared authority flag is positively ``False``.
    """
    if effect is None:
        return False
    return all(
        getattr(effect, name, None) is False for name in type(effect).model_fields
    )


def workflow_record_axes_not_collapsed(
    record: ReplacementWorkflowRecord | None,
) -> bool:
    """Whether the record keeps the five §5 line 107 axes separate (design #18 §4.4).

    §5 line 107 verbatim: a replacement workflow "SHALL NOT collapse order state,
    transmission state, knowledge confidence, capacity state, and protection state into
    one enum". The structural realization is one **separate field per axis**
    (:data:`~tos.replacement.vocabulary.ORTHOGONAL_WORKFLOW_AXES`, count = 5) plus the
    replacement-owned ``workflow_state`` label as a *sixth*, distinct coordinate.

    This predicate asserts the structure has not drifted: every named axis must exist as
    its own field, and none of them may be the ``workflow_state`` field itself. It is a
    regression guard against a future refactor that folds an injected sibling coordinate
    into the lifecycle enum (design #18 §2.2-5 coordinate non-collapse).

    Args:
        record: The workflow record to check (``None`` ⇒ ``False``).

    Returns:
        ``True`` iff all five orthogonal axes are present as separate fields.
    """
    if record is None:
        return False
    fields = type(record).model_fields
    if "workflow_state" not in fields:
        return False
    return all(
        axis in fields and axis != "workflow_state" for axis in ORTHOGONAL_WORKFLOW_AXES
    )


# ===========================================================================
# §6.2 replacement-authorization currentness / expiry (ADR §7; PR-EV-008)
# ===========================================================================


def replacement_authorization_current(
    *,
    material_change: bool | None,
    expired: bool | None,
    economic_effect_persists: bool | None,
) -> bool:
    """Whether a replacement authorization is still current (ADR §7; PR-EV-008).

    §7 line 201 verbatim: "**Any material change invalidates the authorization**" and
    requires re-evaluation (the invalidating changes are exposure, fill, order state,
    capability, session, time health, capacity, profile, epoch, instrument identity,
    market state, and deployment generation). §7 line 203: "Authorization expiry blocks
    further transmission. It does **not** expire the economic effect of an already
    transmitted old or new order."

    ``True`` **only** as one positive conjunction, with the polarity split design #18
    §0.1(j) mandates:

    * ``material_change is False`` — **negative polarity** (safe value ``False``). A
      ``None`` materiality is unknown and therefore treated as material: unknown
      materiality invalidates. ``is not True`` would let ``None`` through and is
      forbidden.
    * ``expired is False`` — **negative polarity**. An unknown expiry status is treated
      as expired (further transmission blocked).
    * ``economic_effect_persists is True`` — **positive polarity** (design #18 §6.2,
      Open Q2). This is the afg-owned produced bool (``tos.afg.state:545``), which is
      ``True`` unless a Final Quantity Proof is positively present. Requiring it
      positively is the conservative direction: an authorization is only "current" while
      the runtime still acknowledges the economic effect of what it already sent, so an
      unknown (``None``) effect state blocks rather than clears.

    Currentness is **not** a permission: §5 line 137 still applies, and a current
    authorization transmits nothing. **Minimum ``EV-L2/3`` — this closes no PR-EV.**
    [SAFE-021; SAFE-022]

    Args:
        material_change: Whether a §7 line 201 material change occurred.
        expired: Whether the authorization expired.
        economic_effect_persists: The afg-produced economic-effect persistence bool.

    Returns:
        ``True`` iff the authorization is positively proven current.
    """
    return (
        material_change is False
        and expired is False
        and economic_effect_persists is True
    )


def expiry_releases_no_economic_effect(
    *,
    expired: bool | None,
    economic_effect_persists: bool | None,
    economic_effect_release_claimed: bool | None,
) -> bool:
    """Whether the expiry-does-not-expire-the-effect rule holds (ADR §7 line 203).

    §7 line 203 verbatim: "Authorization expiry blocks further transmission. It does
    **not** expire the economic effect of an already transmitted old or new order." §9
    line 245 adds that "workflow completion, timeout, **authority expiry**, cancel ACK, or
    local terminal state is insufficient" to reduce capacity.

    The rule **holds** when either:

    * ``economic_effect_release_claimed is False`` — no release is being claimed at all
      (negative polarity: an unknown claim is treated as a claim); or
    * ``economic_effect_persists is False`` — the effect is **positively proven gone**,
      which for the afg producer means a Final Quantity Proof is present. That is the
      only legitimate basis for a release, and notably it is *not* expiry.

    It is **violated** exactly when a release is (or may be) claimed while the effect
    still persists or its persistence is unknown — the forbidden
    ``expire-economic-effect-on-authorization-expiry`` verb (design #18 §4.7). ``expired``
    is retained as the §7 coordinate and is deliberately **not** a way to satisfy the
    rule: no value of it can make a release legitimate, which is the whole point of line
    203. A §7 canary asserts the verdict is invariant across its ``True`` / ``False`` /
    ``None`` values.

    Args:
        expired: Whether the authorization expired (retained coordinate).
        economic_effect_persists: The afg-produced persistence bool.
        economic_effect_release_claimed: Whether a release is being claimed.

    Returns:
        ``True`` iff no release rests on expiry.
    """
    return economic_effect_release_claimed is False or economic_effect_persists is False


# ===========================================================================
# §3.2 append-only generation order (tos.ordering REUSE — no new ordering law)
# ===========================================================================


def workflow_generation_order(
    earlier: ReplacementWorkflowRecord,
    later: ReplacementWorkflowRecord,
) -> Ordering:
    """Compare two workflow generations with the core ordering law (design #18 §3.2).

    The append-only order of replacement generations, authorization re-issuances, and
    workflow records is **not** re-authored here: it REUSES ``tos.ordering``
    (``compare_order`` over ``OrderingEvent``), which depends only on ``tos.canonical``.
    A generation is a plain ``int`` coordinate on the record, not a heavy artifact (the
    #13 are / #16 afg precedent).

    **A wall clock never orders** (§15 line 349 / §18): the comparison rests only on the
    injected ``workflow_generation`` carried on the core ``source_native_sequence``
    coordinate, scoped by ``workflow_id`` as the ``source_continuity_id`` — so two
    records from **different** workflows are ``AMBIGUOUS``, never silently ordered
    (``tos.ordering`` compares a native sequence within one continuity only). A missing
    generation is likewise ``AMBIGUOUS`` rather than an assumed precedence.

    Args:
        earlier: The record believed to be earlier.
        later: The record believed to be later.

    Returns:
        The :class:`~tos.ordering.Ordering` verdict (``AMBIGUOUS`` when either generation
        is absent or the two records belong to different workflows).
    """
    return compare_order(
        OrderingEvent(
            source_continuity_id=earlier.workflow_id,
            source_native_sequence=earlier.workflow_generation,
        ),
        OrderingEvent(
            source_continuity_id=later.workflow_id,
            source_native_sequence=later.workflow_generation,
        ),
    )


def workflow_generation_append_only(
    records: Sequence[ReplacementWorkflowRecord],
) -> bool:
    """Whether a workflow record sequence is strictly append-only (design #18 §2.3/§3.2).

    Each generation is an **immutable** record: a legitimate progression or re-issuance is
    a **new** generation (fresh id + generation), never an in-place mutation. This
    predicate asserts that discipline over an observed sequence: every generation must be
    concrete and strictly increasing.

    A sequence shorter than two records has nothing to violate and is ``True``; an absent
    (``None``) generation is UNKNOWN and fails closed, because an unordered record cannot
    be proven append-only.

    Args:
        records: The observed workflow records, in claimed order.

    Returns:
        ``True`` iff every generation is concrete and strictly increasing.
    """
    previous: int | None = None
    for record in records:
        current = record.workflow_generation
        if current is None:
            return False
        if previous is not None and current <= previous:
            return False
        previous = current
    return True
