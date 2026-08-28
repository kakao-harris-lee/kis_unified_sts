"""The D-E2 resolver slot + the bar → time-coordinate projection (design #33 §3.3/§3.5).

Two injected surfaces meet here, and the design keeps them strictly apart:

* **the value surface is D-E2's.** :class:`~tos.engine.DecisionContextResolver` is the engine-typed
  plug ``(capsule, *, instrument_key) -> DecisionTickPayload`` that resolves a Capsule's
  ``SnapshotRef`` into value-carrying Critical Input observations with source identity, continuity,
  and provenance (RFC-004 §9:242-244). That body **is not reachable from a slice-1 payload**:
  ``DecisionContextCapsule.critical_input_snapshot`` is a :class:`~tos.capsule.SnapshotRef`
  (``snapshot_id`` + ``canonical_digest``, ``capsule.py:41-50``), and slice #1 binds that reference
  only (``records.py:161-163``). :class:`ProvisionalContextResolver` therefore resolves *nothing*:
  the mechanism runs while the decision **starves of real numerics**, and that is recorded honestly
  instead of being papered over with a config-relabelled market value — which RFC-008 §10:327-331
  prohibits and design #31 §3.2 seals.

* **the time surface is D-E3's.** :class:`BarTimeProjection` derives every
  :class:`~tos.engine.TimeAdmissionInputs` coordinate from the bar's own opaque coordinate plus
  injected bounds. No ``time`` / ``datetime`` call appears anywhere (design #33 §3.3/§9); the
  freshness verdict stays a pure function of injected values, which is what makes replay
  byte-identical and what makes ADR-DEV-010 BTE-INV-004's "bounded by the current context
  timestamp" structural rather than promised.

**Forward seam.** When D-E2's typed resolver lands it is injected in place of the provisional one —
the converter's call site does not change (design #33 §7.4 (a)). Nothing here is authoritative and
nothing here closes an EV.

Firewall: ``pydantic`` + stdlib + ``tos.*`` only (design #33 §0.3). No clock, no RNG.
"""

from __future__ import annotations

from pydantic import model_validator

from tos.backtest._base import (
    BacktestIntegrityError,
    FrozenModel,
    seal_performance_surface,
)
from tos.backtest.bars import Bar
from tos.capsule import DecisionContextCapsule
from tos.engine import DecisionTickPayload, InstrumentKey, TimeAdmissionInputs
from tos.time import HealthState, SessionContext, UncertaintyInterval

__all__ = ["BarTimeProjection", "ProvisionalContextResolver", "resolved_value_surface_absent"]


class BarTimeProjection(FrozenModel):
    """Injected bounds that turn a bar coordinate into ``TimeAdmissionInputs`` (design #33 §3.3).

    Every threshold is **injected** (design #33 §10 — hardcoded numbers: 0) and every one of them is
    *provisional*: the trustworthy-time bounds are register §8-1 new-key candidates and the Phase-0
    bounds approval (P0-1) is incomplete, so a run built on them closes no EV (design #33 §1.1).

    Two coordinates are genuinely **bar-derived** rather than constant:

    * ``uncertainty_interval`` = ``[bar.timestamp_coordinate, + interval_width]`` — the reference
      frame's "now" window advances with the bar;
    * ``session_context.boundary_value`` = ``bar.timestamp_coordinate - boundary_lag`` — the session
      boundary is placed strictly *before* the window, so ``session_open_positively`` never has to
      judge a boundary-straddling window it cannot resolve (``predicates.py:599-604``).

    ``source_age`` is an injected observation lag, and is labelled as injected: slice #1 has no
    observation pipeline to derive it from, and inventing one would be a phantom.
    """

    #: The injected conservative source-event age (negative = future-dated; never clamped).
    source_age: int
    #: The applicable injected delay-class upper bounds (ADR-002-008 §9).
    delay_bounds: tuple[int | None, ...] = ()
    #: The injected freshness threshold.
    max_age_bound: int
    #: The injected future-timestamp tolerance.
    future_tolerance: int
    #: The injected effective snapshot age bound.
    snapshot_age_bound: int
    #: The injected maximum consumer age.
    maximum_consumer_age_ms: int
    #: The width of the reference-frame uncertainty window anchored at the bar coordinate.
    interval_width: int
    #: How far **before** the window the injected session boundary sits (strictly positive).
    boundary_lag: int
    #: The injected calendar/session authority determination (never recomputed here).
    session_template: SessionContext
    #: The injected time health state; only ``TRUSTED`` permits new normal risk.
    health_state: HealthState

    @model_validator(mode="after")
    def _bounds_are_bounds(self) -> BarTimeProjection:
        """Reject an ill-formed injected bound — an unestablished threshold is not a threshold."""
        seal_performance_surface(type(self).__name__, type(self).model_fields)
        for name in (
            "max_age_bound",
            "future_tolerance",
            "snapshot_age_bound",
            "maximum_consumer_age_ms",
            "interval_width",
        ):
            value: int = getattr(self, name)
            if value < 0:
                raise BacktestIntegrityError(
                    f"BarTimeProjection.{name} must be non-negative (got {value}) — a negative "
                    "bound is not a bound (ADR-002-008 §9 fail-closed)"
                )
        if self.boundary_lag <= 0:
            raise BacktestIntegrityError(
                f"BarTimeProjection.boundary_lag must be strictly positive (got "
                f"{self.boundary_lag}) — a zero lag would place the session boundary inside the "
                "uncertainty window, which denies (predicates.py:599-604)"
            )
        return self

    def project(self, bar: Bar) -> TimeAdmissionInputs:
        """Project one bar's coordinate onto the engine's injected time inputs.

        Args:
            bar: The bar whose coordinate anchors the reference frame.

        Returns:
            The :class:`~tos.engine.TimeAdmissionInputs` for that bar's ``DECISION_TICK``. No clock
            is read: every field is either an injected bound or a function of
            ``bar.timestamp_coordinate`` (design #33 §3.3).
        """
        anchor = bar.timestamp_coordinate
        return TimeAdmissionInputs(
            source_age=self.source_age,
            delay_bounds=self.delay_bounds,
            max_age_bound=self.max_age_bound,
            future_tolerance=self.future_tolerance,
            snapshot_age_bound=self.snapshot_age_bound,
            maximum_consumer_age_ms=self.maximum_consumer_age_ms,
            session_context=self.session_template.model_copy(
                update={"boundary_value": anchor - self.boundary_lag}
            ),
            uncertainty_interval=UncertaintyInterval(lo=anchor, hi=anchor + self.interval_width),
            health_state=self.health_state,
        )


class ProvisionalContextResolver:
    """⚠ NON-AUTHORITATIVE PROVISIONAL :class:`~tos.engine.DecisionContextResolver` (§3.5).

    It satisfies the engine's plug signature and **resolves no value**: the payload it returns binds
    the Capsule (and through it the Capsule's ``SnapshotRef``) and nothing else. That is the honest
    slice-1 position — the value-carrying observation body is D-E2's to add (``core.py:93-98``), and
    a resolver that fabricated one would be exactly the over-realization the design forbids.

    The consequence is stated plainly: **the mechanism runs, the decision starves.** A policy in
    slice #1 can gate on capsule *identity/scope* facts, not on market numerics, so the differential
    oracle's numeric layer is gated on D-E2 (design #33 §6.2 ②).
    """

    #: The label every provisional artifact in this slice carries (design #31 §4.4 mirror).
    authority_label = "NON_AUTHORITATIVE_PROVISIONAL"

    def __call__(
        self, capsule: DecisionContextCapsule, *, instrument_key: InstrumentKey
    ) -> DecisionTickPayload:
        """Bind one Decision Context Capsule into a tick payload — reference binding only.

        Args:
            capsule: The Decision Context Capsule for this bar.
            instrument_key: The dispatch scope.

        Returns:
            The :class:`~tos.engine.DecisionTickPayload`. ``time`` and ``reference`` are left at
            their engine defaults on purpose: the bar-derived time coordinates are applied by the
            converter (§3.3) and the causal coordinate is stamped by the driver at yield time
            (§3.4), so this resolver claims neither.
        """
        return DecisionTickPayload(instrument_key=instrument_key, capsule=capsule)


def resolved_value_surface_absent(payload: DecisionTickPayload) -> bool:
    """Whether the resolved payload reaches **no** value-carrying Critical Input body (§3.5).

    The anti-phantom form of the design's honesty claim (design #33 §0.5): rather than asserting
    "D-E2 does not exist" in prose, this reads the shipped structure. A slice-1 payload reaches the
    snapshot only through :class:`~tos.capsule.SnapshotRef`, whose entire surface is
    ``snapshot_id`` + ``canonical_digest`` (``capsule.py:41-50``) — no observation, no field
    evaluation, no value.

    Args:
        payload: The resolved ``DECISION_TICK`` payload.

    Returns:
        ``True`` iff the payload's snapshot binding is a pure reference.
    """
    snapshot = payload.capsule.critical_input_snapshot
    return set(type(snapshot).model_fields) == {"snapshot_id", "canonical_digest"}
