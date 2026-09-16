"""``RuntimeTimeProjection`` — the runtime :class:`~tos.marketfeed.TimeCoordinateProjection`
(plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decision 6, lane C).

Composes three already-real runtime collaborators into one ``(*, as_of: int | None) ->
TimeAdmissionInputs`` projection — the exact injected surface
:class:`~tos.marketfeed.MarketFeedContextResolver` calls (``marketfeed/resolver.py:103-115``):

* :class:`~tos_runtime.time.service.TrustworthyTimeService` — the process's own trustworthy-time
  FSM: ``wall_clock_now()`` (gated on ``HealthState.TRUSTED``), ``health_state``, and
  ``current_snapshot()``.
* :class:`~tos_runtime.calendar.owner.SessionFactsOwner` — the real KST session/venue-facts owner;
  its ``session_context(instrument_class)`` is read verbatim, never fabricated.
* :class:`~tos_runtime.time.config.TrustworthyTimeConfig` — the fully-valued, fail-closed-loaded
  VER-002 bounds this module's own two-key addition extends (``time/config.py``'s
  ``_BOUND_KEYS``).

**This module does not judge.** Exactly like ``TrustworthyTimeService`` itself (its own module
docstring: "this service does not judge"), ``RuntimeTimeProjection`` derives coordinates and
carries them — the kernel's own ``tos.time`` predicates (``freshness_verdict``,
``snapshot_age_admissible``, ``session_open_positively``, ``state_permits_new_normal_risk``, all
folded together at ``tos.engine.time_admits``) are what decide whether a tick is admitted.

**Binding table — VERBATIM the same VER-002 keys ``tos.backtest.resolver.BarTimeProjection``
documents for the identical ``TimeAdmissionInputs`` fields** (``resolver.py:52-71``; this module
reuses that binding rather than inventing a parallel one):

* ``future_tolerance`` <- ``MAX_future_timestamp_tolerance_ms``
* ``maximum_consumer_age_ms`` <- ``MAX_critical_input_consumer_receipt_age_ms``
* ``max_age_bound`` <- ``MAX_time_conservative_freshness_age_ms``
* ``delay_bounds`` <- the composite-membership sum of FOUR keys, in the same order
  ``BarTimeProjection``'s own docstring lists them: ``MAX_time_transport_and_queue_uncertainty_ms``,
  ``MAX_clock_domain_conversion_uncertainty_ms``, ``MAX_time_source_precision_ms``,
  ``MAX_time_source_sequence_gap_ms`` (``freshness_verdict`` sums these order-agnostically, but the
  order is kept stable here for readability and so a diff on one config value maps to one tuple
  slot).

Two coordinates are NOT config-derived, deliberately:

* ``source_age`` <- ``wall_clock_now() - as_of`` when BOTH are concrete, else ``None`` — an
  injected *observation*, not a bound (mirrors ``BarTimeProjection.source_age``'s own "not
  VERIFICATION-PROFILE-002-governed" note).
* ``uncertainty_interval`` <- read off the time service's own current snapshot when it carries
  one, else ``None`` — see :meth:`RuntimeTimeProjection._uncertainty_interval`'s docstring for why
  this is honestly always ``None`` in the current runtime schema.

**``snapshot_age_bound`` is deliberately left at the engine default (``None``), not bound here.**
Unlike ``BarTimeProjection`` (a backtest artifact that injects it as a literal), this wave wires no
cross-continuity accounting for it (``tos.time.effective_snapshot_age_bound_from_continuity`` is a
DIFFERENT runtime surface — ``tos_runtime.authority.iap``'s decision-expiry path, not this one).
Leaving it ``None`` is the restrictive, honest choice (module docstring's own rule: "any coordinate
you cannot establish stays None"), and it has a real, immediate consequence worth stating plainly
rather than discovering later: ``tos.time.snapshot_age_admissible(None, maximum_consumer_age_ms)``
is unconditionally ``False`` (``predicates.py:303-305`` — an unknown age bound is fail-closed
regardless of what else is true), so a tick this projection helps build can reach ``FRESH``
freshness and a positively-open session and still never clear ``tos.engine.time_admits``'s full
four-check chain. That gap is this wave's honestly-recorded scope boundary (plan §1 비범위), not a
bug in this module — closing it is cross-continuity accounting for the marketfeed tick path, a
follow-up wave's work, not lane C's.

**Absence is restrictive, never permissive** (mirrors ``resolver.py``'s own module docstring). Any
coordinate this projection cannot establish stays ``None``, which can only narrow what
``time_admits`` allows — never widen it. In particular this module never substitutes a default, a
zero, or a "last known good" value for a missing bound or a missing session context.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib + ``tos.*`` + ``tos_runtime.*``
only. No network. The one clock read anywhere in this module's call graph is
``TrustworthyTimeService.wall_clock_now()`` itself, which this module treats as an opaque injected
value — it never calls ``time``/``datetime`` directly.
"""

from __future__ import annotations

from tos.engine import TimeAdmissionInputs
from tos.marketfeed import TimeCoordinateProjection
from tos.time import UncertaintyInterval

from tos_runtime.calendar.owner import SessionFactsOwner
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TimeServiceNotStarted, TrustworthyTimeService

__all__ = ["RuntimeTimeProjection", "TimeProjectionConfigError"]

#: The four VER-002 keys ``BarTimeProjection.delay_bounds`` composes, as the matching
#: :class:`~tos_runtime.time.config.TrustworthyTimeConfig` field names, in the exact order the
#: class docstring lists them. Kept as a tuple of attribute names (rather than four separate
#: reads inlined at the call site) so :meth:`RuntimeTimeProjection.__init__`'s completeness check
#: and :meth:`RuntimeTimeProjection.__call__`'s tuple construction cannot drift apart.
_DELAY_BOUND_FIELDS: tuple[str, ...] = (
    "max_time_transport_and_queue_uncertainty_ms",
    "max_clock_domain_conversion_uncertainty_ms",
    "max_time_source_precision_ms",
    "max_time_source_sequence_gap_ms",
)


class TimeProjectionConfigError(Exception):
    """Raised when a :class:`RuntimeTimeProjection` cannot be constructed fail-closed.

    Every one of the four ``delay_bounds`` terms must be an established (non-``None``) integer
    before construction succeeds. Omitting one silently would make ``freshness_verdict``'s summed
    conservative age SMALLER, not merely absent — a strictly more permissive answer, which is the
    one direction absence must never move (module docstring). Refusing construction, rather than
    quietly building a projection that emits a three- or two-term ``delay_bounds`` tuple, is what
    keeps that shrinkage impossible rather than merely unlikely.

    In production this can never actually fire: :func:`~tos_runtime.time.config.load_time_config`
    already refuses to build a :class:`~tos_runtime.time.config.TrustworthyTimeConfig` with any of
    these four keys missing or null (``time/config.py``'s ``_BOUND_KEYS``, extended by this wave's
    two-key addition). This check exists anyway as the projection's OWN guarantee — defense in
    depth against a future refactor of the config loader, or a caller that builds a
    ``TrustworthyTimeConfig``-shaped object some other way — rather than a guarantee borrowed
    silently from a collaborator this class does not control.
    """


class RuntimeTimeProjection:
    """The runtime ``(*, as_of: int | None) -> TimeAdmissionInputs`` projection (plan §2 decision 6).

    Args:
        config: The fully-valued Trustworthy Time config (:func:`~tos_runtime.time.config
            .load_time_config`'s only output shape) — every bound this class reads.
        time_service: This process's :class:`~tos_runtime.time.service.TrustworthyTimeService` —
            the SAME instance the rest of the runtime shares, never a second, independently-driven
            one (mirrors every other compose wiring module's own "SAME source" discipline).
        session_owner: This process's :class:`~tos_runtime.calendar.owner.SessionFactsOwner`.
        instrument_class: The single instrument class this projection serves (the scheduler's own
            single-instrument scope — ``ports.py``'s ``TickOutcome`` docstring, FORWARD-OBLIGATION-MS1).

    Raises:
        TimeProjectionConfigError: Any of the four ``delay_bounds`` config terms is unestablished.
            See :class:`TimeProjectionConfigError`'s own docstring for why this is checked here
            too, not just trusted from ``config``.
    """

    def __init__(
        self,
        *,
        config: TrustworthyTimeConfig,
        time_service: TrustworthyTimeService,
        session_owner: SessionFactsOwner,
        instrument_class: str,
    ) -> None:
        missing = [
            field_name
            for field_name in _DELAY_BOUND_FIELDS
            if getattr(config, field_name, None) is None
        ]
        if missing:
            raise TimeProjectionConfigError(
                "RuntimeTimeProjection requires every delay_bounds term to be established — "
                f"missing/unestablished: {missing}. Omitting one would silently sum three terms "
                "instead of four, making the conservative freshness age SMALLER — see "
                "TimeProjectionConfigError's own docstring."
            )
        self._config = config
        self._time_service = time_service
        self._session_owner = session_owner
        self._instrument_class = instrument_class

    def __call__(self, *, as_of: int | None) -> TimeAdmissionInputs:
        """Project ``as_of`` onto the engine's injected time coordinates (module docstring)."""
        wall_clock_now = self._time_service.wall_clock_now()
        source_age = (
            wall_clock_now - as_of
            if wall_clock_now is not None and as_of is not None
            else None
        )
        return TimeAdmissionInputs(
            source_age=source_age,
            delay_bounds=tuple(
                getattr(self._config, field_name) for field_name in _DELAY_BOUND_FIELDS
            ),
            max_age_bound=self._config.max_time_conservative_freshness_age_ms,
            future_tolerance=self._config.max_future_timestamp_tolerance_ms,
            maximum_consumer_age_ms=self._config.max_critical_input_consumer_receipt_age_ms,
            session_context=self._session_owner.session_context(self._instrument_class),
            uncertainty_interval=self._uncertainty_interval(),
            health_state=self._time_service.health_state,
        )

    def _uncertainty_interval(self) -> UncertaintyInterval | None:
        """The time service's current snapshot's uncertainty interval, or ``None``.

        Two reasons this reads ``None`` in the current runtime build, both honest absences rather
        than bugs:

        1. No snapshot is available yet — ``current_snapshot()`` raises
           :class:`~tos_runtime.time.service.TimeServiceNotStarted` before ``start()``/the first
           successful ``evaluate()``; that is caught here and treated as absence, never as a
           reason to fabricate an interval.
        2. :class:`~tos.time.TimeHealthSnapshot` (``tos/src/tos/time/snapshot.py``) carries no
           ``uncertainty_interval`` field in the current schema at all — ``getattr`` with a
           ``None`` default reads that absence honestly rather than raising ``AttributeError``,
           and stays forward-compatible with a future snapshot schema that does carry one.
        """
        try:
            snapshot = self._time_service.current_snapshot()
        except TimeServiceNotStarted:
            return None
        return getattr(snapshot, "uncertainty_interval", None)


#: Static conformance check — mypy fails this file if this class's call signature ever drifts
#: from the kernel's ``TimeCoordinateProjection`` Protocol (structurally; no explicit inheritance
#: edge exists, matching every other injected-port implementer in this package).
_conforms_to_time_coordinate_projection: type[TimeCoordinateProjection] = (
    RuntimeTimeProjection
)
