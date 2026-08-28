"""Pure recon predicates (design #9 §4, §5, §6).

The EV-L1 *functions* the property tests verify — none is a stored field; all are
computed on demand over **injected** state (design #9 §0.2: no clock, no egress, no
persistence — those are runtime EV-L2/L3). Every predicate is conservative /
**fail-closed**: an empty observation set, a single source, an absence observation, a
``None`` independence / tolerance / proof / freshness flag, or a conflict can never
become a ``CORROBORATED`` class, a narrowed bound, or a release proof.

No-blended-release is **structural** (design #9 §4.1): there is no numeric confidence
score type or averaging function anywhere here. Confidence is a class + a
:class:`~tos.recon.records.ConservativeBound`; :func:`merge_conservative` produces the
widest **union** envelope (never a midpoint); the release predicates take **per-field**
inputs only and gate by all-must-pass conjunction (no aggregate scalar path).

Produced-bool seam (design #9 §3.4): recon imports neither ``tos.orthostate`` nor
``tos.rcl`` — it produces plain ``bool`` outputs their already-ratified predicates
consume as injected ``bool | None`` flags. Polarity / fail-closed alignment:

* :func:`field_reconciled_proof_ok` ``True`` <=> orthostate
  ``knowledge_transition_allowed(..., corroboration=True,
  final_quantity_proof_where_broker_involved=True)`` may reach ``RECONCILED``.
* :func:`freshness_lost` ``True`` <=> orthostate
  ``knowledge_transition_allowed(..., freshness_lost=True)`` may reach ``STALE``.
* :func:`any_field_conflicted` ``True`` is the Knowledge-``CONFLICTED`` antecedent
  (feeds orthostate CPL-5 / Capacity ``QUARANTINED_UNKNOWN``).

recon returns ``bool``; the consuming signatures are ``bool | None`` (``None`` fails
closed), so a recon ``False`` and a caller-supplied ``None`` are both safe. Runtime
wiring is the caller's (future Reconciliation Service) concern; the MANDATED test-only
cross-check (``tos/tests/recon/test_seam_orthostate.py``) asserts this alignment
without making the seam a package edge.

Pure module: ``pydantic`` + stdlib + ``tos.recon`` only; no ``shared.*``, no sibling
``tos.*`` (design #9 §0.3).
"""

from __future__ import annotations

from collections.abc import Sequence

from tos.recon.records import ConservativeBound, FieldConfidence, FreshnessMarker
from tos.recon.state import EvidencePathObservation, ReleaseProofInputs
from tos.recon.vocabulary import (
    CAPACITY_RELEASING_FIELDS,
    FieldConfidenceClass,
    SafetyRelevantField,
)

# ===========================================================================
# §6.3 — freshness / time-confidence (RECON-EV-004 substrate)
# ===========================================================================


def freshness_ok(marker: FreshnessMarker) -> bool:
    """Whether a field's evidence is fresh under the approved bound (ADR §7 line 103).

    Requires **all** of (each fail-closed on ``None`` — design #9 §6.3):

    * ``fresh_within_horizon is True`` — within the approved (injected) freshness
      horizon; past the horizon => ``STALE`` => must not authorize new risk.
    * ``time_confidence_held is True`` — trustworthy-time confidence is held; if lost,
      all time-dependent freshness fails closed (ADR §7 line 103).
    * both ``time_generation`` and ``anchored_generation`` are concrete **and equal** —
      a time service that restarts to a new generation does **not** auto-refresh an old
      marker merely because time recovers (RECON-EV-004 "do not become current merely
      because time service recovers"); the field needs fresh evidence to re-establish.

    Args:
        marker: The injected freshness / time-confidence marker.

    Returns:
        ``True`` iff the evidence is fresh; ``False`` on any aged / time-lost /
        generation-changed / ``None`` condition (fail-closed).
    """
    if marker.fresh_within_horizon is not True:
        return False
    if marker.time_confidence_held is not True:
        return False
    if marker.time_generation is None or marker.anchored_generation is None:
        return False
    return marker.time_generation == marker.anchored_generation


def freshness_lost(marker: FreshnessMarker) -> bool:
    """Whether freshness is lost — the negation of :func:`freshness_ok` (design #9 §3.4).

    The produced bool orthostate consumes as its ``freshness_lost`` injected flag
    (``knowledge_transition_allowed(..., freshness_lost=True)`` may reach ``STALE``).
    ``True`` whenever the marker is aged, time-confidence is lost, the generation
    changed, or any flag is ``None`` (fail-closed).

    Args:
        marker: The injected freshness / time-confidence marker.

    Returns:
        ``True`` iff freshness is lost / unproven.
    """
    return not freshness_ok(marker)


# ===========================================================================
# §5.1 — classify_field (RECON-EV-001 substrate)
# ===========================================================================


def classify_field(
    observations: Sequence[EvidencePathObservation],
    freshness_marker: FreshnessMarker,
) -> FieldConfidenceClass:
    """Classify a field's per-field evidence confidence (ADR §5 line 73-80; §6 line 92-95).

    ``observations`` are the evidence-path observations for **one** safety field (the
    caller partitions by field). ``freshness_marker`` is the field-level injected
    freshness marker (the "previously sufficient" premise is a caller-side precondition —
    design #9 §5.1 / §9.2 item 11). Classification (fail-closed throughout):

    * 0 usable paths (empty, or all absence) => ``UNKNOWN`` (maximum conservative bound) —
      never a vacuous ``CORROBORATED`` (design #9 §4.4).
    * exactly 1 usable path => ``SINGLE_SOURCE`` — a single source can never reach
      ``CORROBORATED`` (design #9 §4.5; ADR §6 line 94; SAFE-023).
    * >=2 **sufficiently independent** paths (>=2 distinct non-``None``
      ``independence_class``) that **all agree within tolerance** => ``CORROBORATED``.
    * >=2 sufficiently independent paths with an explicit disagreement
      (``agrees_within_tolerance is False``) => ``CONFLICTED`` (ADR §7 line 101).
    * otherwise (>=2 common-mode paths, or agreement unproven / ``None``) =>
      ``SINGLE_SOURCE`` — common-mode paths (shared ``independence_class``) cannot
      corroborate each other (RECON-EV-001), and unproven agreement fails closed.

    STALE precedence (m1): a would-be ``CORROBORATED`` field whose ``freshness_marker`` is
    not fresh (:func:`freshness_lost`) is pinned to ``STALE`` — freshness loss overrides
    corroboration (ADR §5 line 78). Release stays fail-closed either way because
    :func:`field_reconciled_proof_ok` requires freshness independently (design #9 §6.1).

    Absence observations (``is_absence=True``) are excluded from the usable set: an
    absence may not raise confidence, establish a terminal, or narrow a bound (ADR §7
    line 102; design #9 §5.3).

    Args:
        observations: The field-scoped evidence-path observations.
        freshness_marker: The injected field-level freshness marker.

    Returns:
        The :class:`~tos.recon.vocabulary.FieldConfidenceClass`.
    """
    usable = [o for o in observations if not o.is_absence]
    if not usable:
        return FieldConfidenceClass.UNKNOWN

    if len(usable) == 1:
        base = FieldConfidenceClass.SINGLE_SOURCE
    else:
        distinct_independent = {
            o.independence_class for o in usable if o.independence_class is not None
        }
        sufficiently_independent = len(distinct_independent) >= 2
        all_agree = all(o.agrees_within_tolerance is True for o in usable)
        any_disagreement = any(o.agrees_within_tolerance is False for o in usable)
        if sufficiently_independent and all_agree:
            base = FieldConfidenceClass.CORROBORATED
        elif sufficiently_independent and any_disagreement:
            base = FieldConfidenceClass.CONFLICTED
        else:
            # >=2 but common-mode, or agreement unproven (None) — cannot corroborate.
            base = FieldConfidenceClass.SINGLE_SOURCE

    if base is FieldConfidenceClass.CORROBORATED and freshness_lost(freshness_marker):
        return FieldConfidenceClass.STALE
    return base


def is_corroborated(
    observations: Sequence[EvidencePathObservation],
    freshness_marker: FreshnessMarker,
) -> bool:
    """Whether the field is ``CORROBORATED`` (``classify_field(...) is CORROBORATED``; §5.3).

    Args:
        observations: The field-scoped evidence-path observations.
        freshness_marker: The injected field-level freshness marker.

    Returns:
        ``True`` iff the field classifies as ``CORROBORATED``.
    """
    return (
        classify_field(observations, freshness_marker)
        is FieldConfidenceClass.CORROBORATED
    )


def is_conflicted(
    observations: Sequence[EvidencePathObservation],
    freshness_marker: FreshnessMarker,
) -> bool:
    """Whether the field is ``CONFLICTED`` (``classify_field(...) is CONFLICTED``; §5.3).

    Conflict resolution requires evidence, never selection of the most convenient source
    (ADR §7 line 101; ADR-002-002 INV-012) — recon has no "preferred source" path.

    Args:
        observations: The field-scoped evidence-path observations.
        freshness_marker: The injected field-level freshness marker.

    Returns:
        ``True`` iff the field classifies as ``CONFLICTED``.
    """
    return (
        classify_field(observations, freshness_marker)
        is FieldConfidenceClass.CONFLICTED
    )


# ===========================================================================
# §5.2 / §4.3 — conservative bound merge + monotonicity (RECON-EV-003 substrate)
# ===========================================================================


def merge_conservative(*bounds: ConservativeBound) -> ConservativeBound:
    """Merge bounds into the **widest** (union) envelope — never an average (§5 line 82-86).

    ``upper = max`` of the uppers, ``lower = min`` of the lowers, with **``None``
    dominating** (``None`` = unbounded = the most adverse / most conservative): if any
    input's ``upper`` is ``None`` the merged ``upper`` is ``None``; likewise for ``lower``.
    There is **no** midpoint / average function — merging conflicting fills of 100 and 150
    yields ``upper=150`` (max adverse), never 125 (design #9 §4.1 / §5.2; RECON-EV-003).

    An empty merge yields the fully-unbounded bound (``lower=None, upper=None``) — the
    most conservative value (fail-closed: a union of no evidence never narrows).

    Args:
        *bounds: The conservative bounds to merge.

    Returns:
        The widest-envelope :class:`~tos.recon.records.ConservativeBound`.
    """
    if not bounds:
        return ConservativeBound()
    upper = (
        None
        if any(b.upper is None for b in bounds)
        else max(b.upper for b in bounds if b.upper is not None)
    )
    lower = (
        None
        if any(b.lower is None for b in bounds)
        else min(b.lower for b in bounds if b.lower is not None)
    )
    return ConservativeBound(lower=lower, upper=upper)


def conservative_bound_of(
    observations: Sequence[EvidencePathObservation],
) -> ConservativeBound:
    """The field's risk-usable conservative bound: the union of positive assertions (§5.2).

    Merges the ``asserted_bound`` of every **non-absence** observation (absence asserts no
    positive bound — omission never narrows, design #9 §5.3). With no positive observation
    the result is fully unbounded (most conservative). Because :func:`merge_conservative`
    only widens, adding any observation (positive or absence) can never narrow the result.

    Args:
        observations: The field-scoped evidence-path observations.

    Returns:
        The merged conservative bound.
    """
    positive = tuple(o.asserted_bound for o in observations if not o.is_absence)
    return merge_conservative(*positive)


def bound_narrowing_allowed(
    from_bound: ConservativeBound,
    to_bound: ConservativeBound,
    *,
    strong_basis: bool | None,
) -> bool:
    """Whether moving ``from_bound`` -> ``to_bound`` is permitted (ADR §8 line 121; §4.3).

    "Reducing conservatism requires stronger proof than increasing it" (ADR §8 line 121):

    * widen or hold (``to_bound`` covers ``from_bound``, i.e. ``to ⊇ from``): allowed
      under any basis.
    * narrow (or incomparable — a partial narrowing, treated conservatively as narrowing):
      requires ``strong_basis is True``. ``None`` / ``False`` => fail-closed (not allowed).

    Args:
        from_bound: The current bound.
        to_bound: The proposed next bound.
        strong_basis: Positive proof sufficient to reduce conservatism. ``None`` /
            ``False`` fails closed.

    Returns:
        ``True`` iff the transition is permitted.
    """
    if to_bound.covers(from_bound):
        return True
    return strong_basis is True


# ===========================================================================
# §6.1 / §6.2 — field release proof rule (RECON-EV-005 substrate)
# ===========================================================================


def field_reconciled_proof_ok(
    field: SafetyRelevantField,
    confidence: FieldConfidence,
    inputs: ReleaseProofInputs,
) -> bool:
    """Whether a field satisfies its RECONCILED proof rule (ADR §8 line 112-118 verbatim).

    The §8 generic contract, as a four-conjunct all-must-pass rule (each fail-closed)::

        RECONCILED(field) requires:
          - corroborating evidence sufficient for the field's hazard severity; AND
          - for capacity-releasing fields (final filled quantity, remaining executable
            quantity): Final Quantity Proof per the approved Broker Capability Profile
            (ADR-002-004), including the broker's late-fill / correction semantics; AND
          - freshness within the approved bound; AND
          - no unresolved conflict on the same field.

    Realized as: (a) ``confidence.confidence_class is CORROBORATED`` — ``SINGLE_SOURCE`` /
    ``UNKNOWN`` / ``STALE`` / ``CONFLICTED`` all fail, which also satisfies (d) "no
    unresolved conflict" since ``CORROBORATED`` excludes ``CONFLICTED``; (b) for a
    capacity-releasing field, ``inputs.final_quantity_proof_token is True`` (+Broker
    deferred — the token content is the Broker Capability Profile's concern); (c)
    :func:`freshness_ok`. There is **no** aggregate / blended input path and **no**
    single-source residual-lifting flag — ``SINGLE_SOURCE`` can never reach release grade
    (design #9 §4.1 / §4.5).

    The produced bool orthostate consumes as ``corroboration`` /
    ``final_quantity_proof_where_broker_involved`` (design #9 §3.4). Per-field only —
    multi-field gating is all-must-pass conjunction (no k-of-n / weighted path).

    Args:
        field: The safety-relevant field (determines whether FQP is required).
        confidence: The field's per-field confidence. A concrete ``confidence.field``
            that differs from ``field`` is an incoherent pairing and fails closed
            (code-review MINOR-1 defense-in-depth guard).
        inputs: The injected release-proof side-conditions.

    Returns:
        ``True`` iff the field's proof rule is satisfied.
    """
    # (0) field/confidence coherence — a confidence object belonging to ANOTHER field
    # cannot prove THIS field (fail-closed; code-review MINOR-1 guard).
    if confidence.field is not None and confidence.field is not field:
        return False
    # (a) corroborating evidence sufficient  (also (d): CORROBORATED excludes CONFLICTED)
    if confidence.confidence_class is not FieldConfidenceClass.CORROBORATED:
        return False
    # (b) capacity-releasing fields require a Final Quantity Proof token
    if (
        field in CAPACITY_RELEASING_FIELDS
        and inputs.final_quantity_proof_token is not True
    ):
        return False
    # (c) freshness within the approved bound
    return freshness_ok(inputs.freshness)


def field_specific_release_proof_ok(
    field: SafetyRelevantField,
    confidence: FieldConfidence,
    inputs: ReleaseProofInputs,
) -> bool:
    """Whether a capacity-releasing field may authorize a release (ADR §8; RECON-EV-005).

    A capacity release occurs only after the field-specific proof rule — **including**
    the Final Quantity Proof — is met (AC-006-5). Applies **only** to the capacity-
    releasing subset (``{cumulative filled quantity, remaining executable quantity}``,
    design #9 §6.2); any other field returns ``False`` (it has no release proof). For a
    capacity-releasing field this delegates to :func:`field_reconciled_proof_ok`, which
    enforces the full ``CORROBORATED ∧ FQP ∧ fresh ∧ no-conflict`` conjunction. All weaker
    evidence fails closed (design #9 §6.2):

    * cancel ACK / terminal-status-without-quantity => no FQP token => ``False``.
    * single-source query => not ``CORROBORATED`` => ``False``.
    * late correction (pending) => unresolved conflict / freshness unmet => ``False``.
    * only a complete broker-profile Final Quantity Proof (with ``CORROBORATED`` + fresh +
      no conflict) => ``True``.

    recon returns this bool only; it never performs the release — rcl INV-007
    (``transition_allowed(.., FINAL_QUANTITY_PROOF)``) and orthostate CPL-2
    (``final_quantity_proof``) consume it (design #9 §3.4/§4.7).

    Args:
        field: The safety-relevant field.
        confidence: The field's per-field confidence.
        inputs: The injected release-proof side-conditions.

    Returns:
        ``True`` iff the field is capacity-releasing and its full release proof holds.
    """
    if field not in CAPACITY_RELEASING_FIELDS:
        return False
    return field_reconciled_proof_ok(field, confidence, inputs)


def any_field_conflicted(confidences: Sequence[FieldConfidence]) -> bool:
    """Whether any field in scope is ``CONFLICTED`` (design #9 §3.4 — CPL-5 antecedent).

    The produced bool for the Knowledge-``CONFLICTED`` antecedent that feeds orthostate
    CPL-5 (Capacity ``QUARANTINED_UNKNOWN``). A field with an unset class does not count as
    conflicted (only an explicit ``CONFLICTED`` does).

    Args:
        confidences: The per-field confidences in scope.

    Returns:
        ``True`` iff at least one field classifies as ``CONFLICTED``.
    """
    return any(
        c.confidence_class is FieldConfidenceClass.CONFLICTED for c in confidences
    )
