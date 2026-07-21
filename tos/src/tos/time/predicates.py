"""Pure trustworthy-time predicates (time design §3, §4, §6; EV-L1 substrate).

The EV-L1 *functions* whose contract the property tests verify. None reads a real
clock: every time value is an opaque injected coordinate (time design §0.3/§3).
All are conservative / fail-closed — none can turn an unknown, discontinuity,
suspension, or conflict into freshness/order/authority.

Revision — v1.2 (implementation, code-review REJECT reflected; the ratified
design doc is NOT edited): MAJOR fail-closed guards for **negative injected
magnitude terms** in ``conservative_usable_lifetime`` /
``effective_snapshot_age_bound`` (=> ``None``) and ``freshness_verdict`` bounds
(=> ``UNKNOWN``), which previously let producer-optimism / a discontinuity
lengthen a lease or hide staleness. MEDIUM-1 (§8-208 env/scope is version-proxied
in Phase-1 — see ``snapshot_consumer_binding_ok``), MEDIUM-2 (injected-boolean
seam preconditions + ``effective_snapshot_age_bound_from_continuity`` composition
wrapper), LOW-2 (FSM AND-composition note) recorded in the relevant docstrings.

**Completion discipline (time design §1, inherited from design #2 §7 / #4 §7):**
these are EV-L1 *predicate substrate only*. Every TIME-EV-001..010 has a register
minimum of **EV-L2 or higher** (EVIDENCE-REGISTER-002.csv line 69-78), so **no
TIME-EV item is closed here**. Tag for any claim: "EV-L1 predicate substrate
only; TIME-EV-### remains NOT_IMPLEMENTED pending EV-L2/L3 (010 is +Security)
fault injection."

Contents (design section -> TIME-EV substrate mapping):

* §3(1) : ``elapsed_within_continuity`` — cross-continuity non-subtraction
  (TIME-EV-004/-010 substrate).
* §3(2) : ``anchor_valid`` — continuity-change / discontinuity / restart /
  suspension invalidation (TIME-EV-004/-005 substrate).
* §3(3) : ``conservative_usable_lifetime`` — holdover usable lifetime
  (TIME-EV-006 substrate).
* §3(4) : ``effective_snapshot_age_bound`` — cross-continuity snapshot age via the
  §8 5-step receipt-anchor path (TIME-EV-010 substrate).
* §4   : ``freshness_verdict`` — negative-not-clamped / future / UNKNOWN!=0
  (TIME-EV-007 substrate).
* §6   : ``health_transition_allowed`` / ``transition_to_trusted_requires_new_
  generation`` / ``recovery_generation_revives_nothing`` /
  ``state_permits_new_normal_risk`` — FSM conservatism + non-revival
  (TIME-EV-009 substrate + §6.4).
* §6   : ``snapshot_grants_no_authority`` — authority-absence (SAFE-044).
* §6/§12: ``session_open_positively`` — session-boundary uncertainty
  (TIME-EV-008 substrate).
* §7   : ``snapshot_consumer_binding_ok`` — wrong/null-generation + config-version
  rejection, mirroring evidence ``eip_binding_ok`` (§8 line 208).
* §2.5A: ``independent_reference_count`` / ``source_disagreement_within_bound`` —
  common-mode collapse + disagreement bound (TIME-EV-003 substrate).

Pure module: ``pydantic`` + stdlib + ``tos.canonical`` / ``tos.ordering`` /
``tos.time`` only; no real clock, no ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.time.domains import FreshnessVerdict, HealthState
from tos.time.elements import (
    ConsumerReceiptAnchor,
    MonotonicReading,
    ReferenceSource,
    SessionContext,
    TimeContinuityIdentity,
    UncertaintyInterval,
)
from tos.time.snapshot import TimeHealthSnapshot

# ===========================================================================
# §3(1) — cross-continuity non-subtraction (TIME-EV-004/-010 substrate)
# ===========================================================================


def elapsed_within_continuity(a: MonotonicReading, b: MonotonicReading) -> int | None:
    """Elapsed ``b - a`` only within one monotonic continuity, else ``None`` (§3(1)).

    Generalizes the shipped ``compare_order`` ``same_continuity`` guard to age
    arithmetic: a subtraction is performed **only** when both readings share a
    concrete ``monotonic_continuity_id``; otherwise no subtraction is done at all
    (returns ``None``). This is the safety core of the §8 line 212 / §10 line 259
    non-subtraction rule. [TIME-AC-004, TIME-AC-010; SAFE-031, SAFE-035]

    Args:
        a: The earlier reading.
        b: The later reading.

    Returns:
        ``b.local_monotonic_value - a.local_monotonic_value`` within one
        continuity, else ``None`` (cross-continuity or any missing coordinate).
    """
    if a.monotonic_continuity_id is None or b.monotonic_continuity_id is None:
        return None
    if a.monotonic_continuity_id != b.monotonic_continuity_id:
        return None
    if a.local_monotonic_value is None or b.local_monotonic_value is None:
        return None
    return b.local_monotonic_value - a.local_monotonic_value


# ===========================================================================
# §3(2) — anchor invalidation (TIME-EV-004/-005 substrate)
# ===========================================================================


def anchor_valid(
    continuity_now: TimeContinuityIdentity,
    anchor: TimeContinuityIdentity,
    *,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
) -> bool:
    """Whether an anchor is still valid across ``now`` (§3(2); ADR §5 line 124).

    Returns ``False`` (invalid — **not** merely "less fresh") if ANY of:
    continuity/host/boot/process identity changed or is unknown (restart / reboot
    / new continuity), the claimed-continuity ``monotonic_anchor_value`` went
    non-monotone (discontinuity / reset), or the suspension is unknown / exceeds
    the injected ``max_suspension_ms``. On invalidation the anchor, any holdover
    lease, and any cached snapshot are unusable for new permissive use.
    [TIME-AC-004, TIME-AC-005; SAFE-048]

    Args:
        continuity_now: The current continuity identity.
        anchor: The anchor's continuity identity to validate against.
        suspension_ms: Observed suspension magnitude (``None`` => unknown =>
            invalid).
        max_suspension_ms: Injected maximum suspension bound (``None`` => cannot
            establish => invalid).

    Returns:
        ``True`` iff the anchor is provably continuous and in-bound.
    """
    for field in ("host_or_runtime_id", "boot_id", "process_id", "monotonic_anchor_id"):
        now_v = getattr(continuity_now, field)
        anc_v = getattr(anchor, field)
        if now_v is None or anc_v is None or now_v != anc_v:
            return False
    now_value = continuity_now.monotonic_anchor_value
    anchor_value = anchor.monotonic_anchor_value
    if now_value is None or anchor_value is None:
        return False
    if now_value < anchor_value:  # non-monotone within the claimed continuity
        return False
    if suspension_ms is None or max_suspension_ms is None:
        return False
    return suspension_ms <= max_suspension_ms


# ===========================================================================
# §3(3) — conservative usable lifetime (TIME-EV-006 substrate)
# ===========================================================================


def conservative_usable_lifetime(
    *,
    issued_lifetime: int | None,
    elapsed_monotonic: int | None,
    source_transport_uncertainty: int | None,
    max_drift_error: int | None,
    suspension_uncertainty: int | None,
    safety_margin: int | None,
) -> int | None:
    """Conservative remaining usable lifetime (§3(3); ADR §11.2 line 283-294).

    Formula: ``issued − elapsed − source_transport_unc − max_drift_error −
    suspension_unc − safety_margin``. **If any term is unknown (``None``),
    **negative**, or the result is non-positive, the lease is invalid** (returns
    ``None``) — never clamped to zero (§11.2 line 294). The negative guard is
    fail-closed (v1.2 code-review MAJOR): a negative magnitude term is not a valid
    input (a negative ``elapsed_monotonic`` is a §13 discontinuity, a negative
    drift/transport/suspension/margin is producer-optimism), and without the guard
    it would *extend* the lease — the exact "turn a discontinuity/conflict into
    authority" fail-open this predicate must never allow. Monotone in every
    uncertainty term over the valid (non-negative) domain: a larger uncertainty
    yields a shorter (or invalid) lifetime. [TIME-AC-006; SAFE-048]

    Args:
        issued_lifetime: The lifetime issued while TRUSTED.
        elapsed_monotonic: Same-continuity elapsed since issue.
        source_transport_uncertainty: Injected transport uncertainty bound.
        max_drift_error: Injected maximum drift error bound.
        suspension_uncertainty: Injected suspension uncertainty bound.
        safety_margin: Injected approved safety margin.

    Returns:
        The positive remaining lifetime, or ``None`` if any term is unknown or
        negative, or the result is non-positive (invalid for new transmission).
    """
    terms = (
        issued_lifetime,
        elapsed_monotonic,
        source_transport_uncertainty,
        max_drift_error,
        suspension_uncertainty,
        safety_margin,
    )
    if any(term is None for term in terms):
        return None
    if any(term < 0 for term in terms):  # type: ignore[operator]
        return None  # fail-closed: a negative magnitude term must not extend a lease
    result = (
        issued_lifetime  # type: ignore[operator]
        - elapsed_monotonic
        - source_transport_uncertainty
        - max_drift_error
        - suspension_uncertainty
        - safety_margin
    )
    if result <= 0:
        return None
    return result


# ===========================================================================
# §3(4) — cross-continuity snapshot age (TIME-EV-010 substrate)
# ===========================================================================


def effective_snapshot_age_bound(
    snapshot: TimeHealthSnapshot,
    consumer_receipt_anchor: ConsumerReceiptAnchor,
    *,
    issuer_signed_age: int | None,
    issuer_age_uncertainty: int | None,
    transport_bound: int | None,
    queue_bound: int | None,
    conversion_bound: int | None,
    consumer_elapsed_since_receipt: int | None,
    consumer_anchor_valid: bool,
) -> int | None:
    """Effective cross-continuity snapshot age bound via the §8 5-step path (§3(4)).

    When issuer and consumer continuities differ, ADR §8 line 212-220 permits age
    only by: (i) trusting the issuer-signed age + uncertainty; (ii) the consumer
    recording receipt in its **own** monotonic continuity
    (``consumer_receipt_anchor``); (iii) adding injected transport/queue/
    conversion bounds; (iv) adding consumer-**local** elapsed since receipt
    (subtraction only inside the consumer's own continuity); (v) returning UNKNOWN
    if any bound is missing or the consumer anchor is invalid. The issuer monotonic
    value is **never** subtracted from a consumer clock (§8 line 220). The caller
    compares the returned bound against ``maximum_consumer_age_ms`` (see
    ``snapshot_age_admissible``). [TIME-AC-010; SAFE-031, SAFE-035, SAFE-030, SAFE-050]

    Args:
        snapshot: The issuer's Time Health Snapshot (identity/provenance only).
        consumer_receipt_anchor: The consumer's own receipt anchor.
        issuer_signed_age: Issuer-signed age at issue.
        issuer_age_uncertainty: Issuer-signed age uncertainty.
        transport_bound: Injected source->receipt transport bound.
        queue_bound: Injected queue/buffer/replay/batch bound.
        conversion_bound: Injected clock-domain-conversion bound.
        consumer_elapsed_since_receipt: Consumer-local elapsed since receipt.
        consumer_anchor_valid: Whether the consumer receipt anchor is still valid
            (no consumer restart/discontinuity, §8 line 220).

    ``consumer_anchor_valid`` MUST be the result of
    :func:`anchor_valid` for the consumer's own continuity (see
    :func:`effective_snapshot_age_bound_from_continuity`, which composes the two so
    an L2 caller cannot skip the anchor check — MEDIUM-2). Any **negative**
    additive term is fail-closed to ``None`` (v1.2 code-review MAJOR): a negative
    age/uncertainty/transport/queue/conversion/elapsed term is not a valid input
    and would otherwise *shrink* the cross-host age, masking staleness.

    Returns:
        The conservative additive age bound, or ``None`` (UNKNOWN) if the consumer
        anchor is invalid or any additive term is missing or negative.
    """
    del snapshot  # identity/provenance only; no monotonic value is subtracted
    if not consumer_anchor_valid:
        return None
    if consumer_receipt_anchor.consumer_monotonic_continuity_id is None:
        return None
    additive_terms = (
        issuer_signed_age,
        issuer_age_uncertainty,
        transport_bound,
        queue_bound,
        conversion_bound,
        consumer_elapsed_since_receipt,
    )
    if any(term is None for term in additive_terms):
        return None
    if any(term < 0 for term in additive_terms):  # type: ignore[operator]
        return None  # fail-closed: a negative term must not shrink cross-host age
    return sum(additive_terms)  # type: ignore[arg-type]


def snapshot_age_admissible(
    age_bound: int | None, maximum_consumer_age_ms: int | None
) -> bool:
    """Whether a snapshot age bound is admissible (§3(4)(v); ADR §8 line 210).

    Fail-closed: an UNKNOWN age bound (``None``) or an unestablished
    ``maximum_consumer_age_ms`` (``None``) is inadmissible; otherwise the bound
    must not exceed the injected maximum. [SAFE-030, SAFE-050]

    Args:
        age_bound: The effective age bound (``None`` => UNKNOWN => reject).
        maximum_consumer_age_ms: The injected max age (``None`` => reject).

    Returns:
        ``True`` iff both are concrete and ``age_bound <= maximum_consumer_age_ms``.
    """
    if age_bound is None or maximum_consumer_age_ms is None:
        return False
    return age_bound <= maximum_consumer_age_ms


def effective_snapshot_age_bound_from_continuity(
    snapshot: TimeHealthSnapshot,
    consumer_receipt_anchor: ConsumerReceiptAnchor,
    *,
    consumer_continuity_now: TimeContinuityIdentity,
    consumer_anchor: TimeContinuityIdentity,
    suspension_ms: int | None,
    max_suspension_ms: int | None,
    issuer_signed_age: int | None,
    issuer_age_uncertainty: int | None,
    transport_bound: int | None,
    queue_bound: int | None,
    conversion_bound: int | None,
    consumer_elapsed_since_receipt: int | None,
) -> int | None:
    """Compose ``anchor_valid`` with ``effective_snapshot_age_bound`` (MEDIUM-2, v1.2).

    Closes the injected-boolean seam: instead of trusting a caller-supplied
    ``consumer_anchor_valid`` flag, this derives it from :func:`anchor_valid` over
    the consumer's **own** continuity (``consumer_continuity_now`` vs
    ``consumer_anchor`` + injected suspension bounds), so an L2 caller cannot skip
    the consumer-restart / discontinuity / suspension check before accruing age.
    All the fail-closed rules of :func:`effective_snapshot_age_bound` (missing /
    negative additive terms => ``None``) still apply. [TIME-AC-010; SAFE-048]

    Args:
        snapshot: The issuer's Time Health Snapshot (identity/provenance only).
        consumer_receipt_anchor: The consumer's own receipt anchor.
        consumer_continuity_now: The consumer's current continuity identity.
        consumer_anchor: The consumer's receipt-time continuity identity.
        suspension_ms: Observed consumer suspension (``None`` => invalid anchor).
        max_suspension_ms: Injected max suspension bound (``None`` => invalid).
        issuer_signed_age: Issuer-signed age at issue.
        issuer_age_uncertainty: Issuer-signed age uncertainty.
        transport_bound: Injected source->receipt transport bound.
        queue_bound: Injected queue/buffer/replay/batch bound.
        conversion_bound: Injected clock-domain-conversion bound.
        consumer_elapsed_since_receipt: Consumer-local elapsed since receipt.

    Returns:
        The conservative additive age bound, or ``None`` (UNKNOWN) if the consumer
        anchor is invalid or any additive term is missing or negative.
    """
    valid = anchor_valid(
        consumer_continuity_now,
        consumer_anchor,
        suspension_ms=suspension_ms,
        max_suspension_ms=max_suspension_ms,
    )
    return effective_snapshot_age_bound(
        snapshot,
        consumer_receipt_anchor,
        issuer_signed_age=issuer_signed_age,
        issuer_age_uncertainty=issuer_age_uncertainty,
        transport_bound=transport_bound,
        queue_bound=queue_bound,
        conversion_bound=conversion_bound,
        consumer_elapsed_since_receipt=consumer_elapsed_since_receipt,
        consumer_anchor_valid=valid,
    )


# ===========================================================================
# §4 — freshness verdict (TIME-EV-007 substrate)
# ===========================================================================


def freshness_verdict(
    *,
    source_age: int | None,
    delay_bounds: Sequence[int | None],
    max_age_bound: int | None,
    future_tolerance: int | None,
) -> FreshnessVerdict:
    """Conservative freshness verdict (§4; ADR §9 line 241-243; §18 line 443).

    ``source_age`` is the conservatively-estimated age of the source event (the
    capsule ``Freshness.source_age`` analog); a **negative** value means the source
    timestamp is in the future and is **never clamped to zero**. ``delay_bounds``
    are the applicable ADR §9 delay-class upper bounds (each injected); a ``None``
    among them means an unestablished bound. Rules:

    * ``source_age`` unknown (``None``) => ``UNKNOWN`` (missing source time).
    * a **negative** ``delay_bounds`` element, ``max_age_bound``, or
      ``future_tolerance`` => ``UNKNOWN`` (an unestablished/corrupt bound is not a
      bound; v1.2 code-review MAJOR fail-closed — a negative delay would otherwise
      *hide* staleness). NB: a negative ``source_age`` is legitimate future-dating
      and is NOT rejected here.
    * negative ``source_age`` with no ``future_tolerance`` => ``CONFLICTED``
      (cannot bound the future — fail-closed).
    * negative ``source_age`` beyond ``future_tolerance`` => ``CONFLICTED``.
    * negative ``source_age`` within tolerance => ``FRESH`` (skew within bound; the
      negative age was *evaluated*, not clamped).
    * any ``delay_bounds`` term unknown => ``UNKNOWN`` (upper bound unestablished).
    * ``max_age_bound`` unknown (``None``) => ``UNKNOWN`` (no threshold => cannot
      declare fresh; permissive use rejected, §8 line 210).
    * total (``source_age`` + Σ delay bounds) > ``max_age_bound`` => ``STALE``.
    * otherwise ``FRESH``.

    UNKNOWN is not zero and not fresh (time design §2.6). [TIME-AC-002, TIME-AC-007;
    SAFE-030]

    Args:
        source_age: Conservative source-event age (negative => future); ``None`` =>
            missing.
        delay_bounds: Applicable injected delay-class upper bounds.
        max_age_bound: Injected freshness threshold (``None`` => UNKNOWN).
        future_tolerance: Injected future-timestamp tolerance (``None`` for a
            negative age => CONFLICTED).

    Returns:
        The :class:`~tos.time.domains.FreshnessVerdict`.
    """
    if source_age is None:
        return FreshnessVerdict.UNKNOWN
    # A negative injected bound is unestablished/corrupt => UNKNOWN (fail-closed).
    # A negative source_age (future-dated source) is legitimate and handled below.
    if future_tolerance is not None and future_tolerance < 0:
        return FreshnessVerdict.UNKNOWN
    if any(bound is not None and bound < 0 for bound in delay_bounds):
        return FreshnessVerdict.UNKNOWN
    if max_age_bound is not None and max_age_bound < 0:
        return FreshnessVerdict.UNKNOWN
    if source_age < 0:
        if future_tolerance is None:
            return FreshnessVerdict.CONFLICTED
        if -source_age > future_tolerance:
            return FreshnessVerdict.CONFLICTED
        return FreshnessVerdict.FRESH
    if any(bound is None for bound in delay_bounds):
        return FreshnessVerdict.UNKNOWN
    if max_age_bound is None:
        return FreshnessVerdict.UNKNOWN
    total_age = source_age + sum(bound for bound in delay_bounds)  # type: ignore[misc]
    if total_age > max_age_bound:
        return FreshnessVerdict.STALE
    return FreshnessVerdict.FRESH


# ===========================================================================
# §6 — health FSM conservatism + non-revival (TIME-EV-009 substrate + §6.4)
# ===========================================================================

#: The 7 directed transitions of the ADR §6 FSM (line 134-145). Any pair outside
#: this set is not a permitted transition.
_ALLOWED_TRANSITIONS: frozenset[tuple[HealthState, HealthState]] = frozenset(
    {
        (HealthState.UNINITIALIZED, HealthState.SYNCHRONIZING),
        (HealthState.SYNCHRONIZING, HealthState.TRUSTED),
        (HealthState.TRUSTED, HealthState.DEGRADED_HOLDOVER),
        (HealthState.TRUSTED, HealthState.UNTRUSTED),
        (HealthState.DEGRADED_HOLDOVER, HealthState.UNTRUSTED),
        (HealthState.DEGRADED_HOLDOVER, HealthState.SYNCHRONIZING),
        (HealthState.UNTRUSTED, HealthState.SYNCHRONIZING),
    }
)


def health_transition_allowed(from_state: HealthState, to_state: HealthState) -> bool:
    """Whether a health-state transition is one of the 7 permitted (§6 line 134-145).

    LOW-2 (v1.2): this is the shape gate only. An L2 transition executor MUST
    **AND** this with :func:`transition_to_trusted_requires_new_generation` for any
    ``to_state == TRUSTED`` transition (a shape-legal SYNCHRONIZING->TRUSTED still
    needs a strictly-new generation). The two are separate predicates here because
    an illegal shape is already rejected outright (no fail-open in isolation).
    """
    return (from_state, to_state) in _ALLOWED_TRANSITIONS


def transition_to_trusted_requires_new_generation(
    from_generation: int | None, to_generation: int | None
) -> bool:
    """Whether a return to TRUSTED carries a strictly-new generation (§6.4; §16 line 401).

    A transition *into* ``TRUSTED`` is valid only with a strictly greater health
    generation ("a new Trustworthy Time Service generation"). Fail-closed on any
    unknown generation. [TIME-AC-009; SAFE-044]

    Args:
        from_generation: The generation before the transition.
        to_generation: The generation of the TRUSTED target.

    Returns:
        ``True`` iff both are concrete and ``to_generation > from_generation``.
    """
    if from_generation is None or to_generation is None:
        return False
    return to_generation > from_generation


def recovery_generation_revives_nothing(
    *, invalidated_under_generation: int | None, new_generation: int | None
) -> bool:
    """Whether a new generation revives an earlier invalidation — never (§6.4; §16 line 406-409).

    Unconditionally ``True``: what generation N invalidated is **not** revived by
    generation N+1 (or any later). Establishing time readiness under a new
    generation "does not open the Recovery Barrier, issue Live Authorization, or
    re-arm" (§16 line 409). The model provides **no** operation mapping a
    generation increase to lease/authority validity restoration; this predicate
    documents and fixes that absence. [TIME-AC-009; SAFE-044]

    Args:
        invalidated_under_generation: The generation under which something was
            invalidated.
        new_generation: A later recovery generation.

    Returns:
        ``True`` always (non-revival holds).
    """
    del invalidated_under_generation, new_generation  # no revival path exists
    return True


def state_permits_new_normal_risk(state: HealthState) -> bool:
    """Whether a health state permits **new normal risk** — TRUSTED only (§6.1-6.3).

    ``DEGRADED_HOLDOVER`` permits only a pre-issued degraded protective lease, not
    new normal risk (§6.2); ``UNTRUSTED`` permits no new permissive action (§6.3);
    ``UNINITIALIZED``/``SYNCHRONIZING`` are not established. [SAFE-050]
    """
    return state is HealthState.TRUSTED


# ===========================================================================
# §6 — authority absence (SAFE-044)
# ===========================================================================


def snapshot_grants_no_authority(snapshot: TimeHealthSnapshot) -> bool:
    """Whether the snapshot grants no authority (§6; §14.1 line 348).

    A Time Health Snapshot is never authority: every ``authority_effect`` flag is
    ``False`` (already enforced at construction by
    :class:`~tos.time.elements.AllFalseAuthority`; this predicate is the consumer-
    side "reject snapshot-as-authority" check). [SAFE-044]

    Args:
        snapshot: The snapshot whose authority effect is checked.

    Returns:
        ``True`` iff every declared authority flag is ``False``.
    """
    authority = snapshot.authority_effect
    return not any(
        getattr(authority, name) is True for name in type(authority).model_fields
    )


# ===========================================================================
# §6 / §12 — session-boundary uncertainty (TIME-EV-008 substrate)
# ===========================================================================


def session_open_positively(
    session_ctx: SessionContext, uncertainty_interval: UncertaintyInterval
) -> bool:
    """Whether a trading session is **positively** open (§12 line 319).

    Denies (returns ``False``) on: not positively open, unknown phase, missing
    calendar, tz-version conflict, ambiguous local time (an unbounded uncertainty
    interval, either endpoint ``None``), or a session boundary that falls **inside**
    the uncertainty interval. Only a positively-open session with clean epistemics
    and a boundary strictly outside the uncertainty window is allowed. Broker-
    agnostic: no market hours are read (time design §4.7). [TIME-AC-008; SAFE-050]

    Precondition (MEDIUM-2, v1.2): ``session_ctx.is_open`` is an **injected**
    determination that MUST originate from the calendar/session authority — this
    Phase-1 predicate substrate does not recompute it (runtime calendar evaluation
    is L2+). The predicate still fail-closes on every *other* epistemic (phase /
    calendar / tz / boundary), so a wrongly-true ``is_open`` cannot alone open a
    boundary-straddling or ambiguous session.

    Args:
        session_ctx: The injected session context.
        uncertainty_interval: The reference-frame uncertainty interval for "now".

    Returns:
        ``True`` iff the session is positively, unambiguously open.
    """
    if not session_ctx.is_open:
        return False
    if session_ctx.phase is None:
        return False
    if session_ctx.trading_calendar_version is None:
        return False
    if session_ctx.tz_version_conflict:
        return False
    if uncertainty_interval.lo is None or uncertainty_interval.hi is None:
        return False  # ambiguous local time (unbounded)
    boundary = session_ctx.boundary_value
    # A boundary inside the uncertainty window straddles the session boundary => deny.
    return not (
        boundary is not None
        and uncertainty_interval.lo <= boundary <= uncertainty_interval.hi
    )


# ===========================================================================
# §7 (MINOR-1) — snapshot consumer binding / wrong-generation rejection
# ===========================================================================


def snapshot_consumer_binding_ok(
    snapshot: TimeHealthSnapshot,
    *,
    expected_snapshot_id: str,
    expected_canonical_digest: str,
    expected_generation: int | None = None,
    expected_verification_profile_version: str | None = None,
    expected_safety_profile_version: str | None = None,
) -> bool:
    """Whether a snapshot matches the consumer's ``(id, generation, digest)`` binding (§7; §8 line 208).

    Mirrors evidence ``eip_binding_ok``: a consumer rejects a snapshot whose
    declared ``snapshot_id`` / ``canonical_digest`` mismatches, whose generation is
    wrong or null when a concrete generation is expected, or whose config
    (verification/safety profile) version is wrong. Generation is **fail-closed**
    (design #4 §3.5 MINOR-2 mirror): because ``generation`` is excluded from the
    digest, a digest match alone does not prove the generation, so a concrete
    expected generation must be matched by an equal concrete snapshot generation
    (a null snapshot generation cannot mask same-body generation drift).

    A different ``issuer_continuity_id`` is **not** a binding mismatch here — it
    activates the §3(4) cross-continuity receipt-anchor path instead (time design
    §7 note). [TIME-AC-009; SAFE-044, SAFE-050]

    MEDIUM-1 (v1.2, honest lossy-proxy record): §8-208 "wrong-environment /
    wrong-scope" rejection is only **version-proxied** in Phase-1 via the
    verification/safety **profile-version** fields, and both are optional. So this
    predicate (a) cannot distinguish two environments that share a profile version,
    and (b) skips the env/scope check entirely when a consumer omits the expected
    versions. Dedicated ``environment_id`` / ``scope_id`` *covered* fields on the
    snapshot (for a non-proxied §8-208 check) are flagged as a Phase-0 / L2 item
    (time design §9.2); no such field is added in this slice.

    Args:
        snapshot: The snapshot to check.
        expected_snapshot_id: The snapshot id the consumer expects.
        expected_canonical_digest: The canonical digest the consumer expects.
        expected_generation: The expected generation (checked, fail-closed, if
            given).
        expected_verification_profile_version: Expected config version (checked if
            given).
        expected_safety_profile_version: Expected safety-profile version (checked
            if given).

    Returns:
        ``True`` iff every provided binding component matches exactly.
    """
    if snapshot.snapshot_id != expected_snapshot_id:
        return False
    if snapshot.canonical_digest != expected_canonical_digest:
        return False
    if expected_generation is not None and snapshot.generation != expected_generation:
        return False
    if (
        expected_verification_profile_version is not None
        and snapshot.verification_profile_version
        != expected_verification_profile_version
    ):
        return False
    return not (
        expected_safety_profile_version is not None
        and snapshot.safety_profile_version != expected_safety_profile_version
    )


# ===========================================================================
# §2.5 A — source independence / common-mode collapse (TIME-EV-003 substrate)
# ===========================================================================


def independent_reference_count(sources: Sequence[ReferenceSource]) -> int:
    """Count independent reference contributions, collapsing common-mode (§7 line 184).

    Sources sharing a concrete ``common_mode_group`` (one clock / network /
    hypervisor / sync-daemon) collapse to a **single** independent contribution;
    a source with no declared group (``None``) counts as its own contribution.
    "Multiple names served by one clock/path/hypervisor/daemon SHALL NOT be claimed
    as independent." [TIME-AC-003; SAFE-031, SAFE-035]

    Args:
        sources: The reference sources.

    Returns:
        The number of independent contributions after common-mode collapse.
    """
    seen_groups: set[str] = set()
    count = 0
    for source in sources:
        group = source.common_mode_group
        if group is None:
            count += 1
        elif group not in seen_groups:
            seen_groups.add(group)
            count += 1
    return count


def source_disagreement_within_bound(
    disagreement_ms: int | None, tolerance_ms: int | None
) -> bool:
    """Whether inter-source disagreement is within the injected tolerance (§7 line 184).

    Fail-closed: an unknown disagreement or an unestablished tolerance (``None``)
    is not within bound; disagreement above tolerance keeps the state out of
    TRUSTED. [TIME-AC-003; SAFE-031]

    Args:
        disagreement_ms: Observed inter-source disagreement (``None`` => reject).
        tolerance_ms: Injected disagreement tolerance (``None`` => reject).

    Returns:
        ``True`` iff both are concrete and ``disagreement_ms <= tolerance_ms``.
    """
    if disagreement_ms is None or tolerance_ms is None:
        return False
    return disagreement_ms <= tolerance_ms
