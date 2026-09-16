"""``RuntimeTimeProjection`` — the runtime :class:`~tos.marketfeed.TimeCoordinateProjection`
(plan ``docs/plans/2026-09-16-tos-tick-source-plan.md`` §2 decision 6, lane C).

Composes three already-real runtime collaborators plus two injected construction parameters into
one ``(*, as_of: int | None) -> TimeAdmissionInputs`` projection — the exact injected surface
:class:`~tos.marketfeed.MarketFeedContextResolver` calls (``marketfeed/resolver.py:103-115``):

* :class:`~tos_runtime.time.service.TrustworthyTimeService` — the process's own trustworthy-time
  FSM: ``wall_clock_now()`` (gated on ``HealthState.TRUSTED``) and ``health_state``.
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

One coordinate is a genuine runtime *observation*, not config-derived:

* ``source_age`` <- ``wall_clock_now() - as_of`` when BOTH are concrete, else ``None`` — mirrors
  ``BarTimeProjection.source_age``'s own "not VERIFICATION-PROFILE-002-governed" note.

**Two more fields are INJECTED CONSTRUCTION PARAMETERS, not VER-002 bounds and not derived from
anything this module reads at call time** — ``BarTimeProjection`` carries the identical pair with
the identical meaning (``resolver.py:85-97, 124-133``), and this class follows that precedent
exactly rather than treating their absence from the VER-002 binding table above as an omission
(an earlier draft of this module did exactly that, and was wrong to):

* ``snapshot_age_bound: int`` — required at construction, no default, flows through verbatim into
  every emitted ``TimeAdmissionInputs``. ``BarTimeProjection``'s own docstring: "the injected
  effective snapshot age bound... structurally a derived/injected observation, not a bound"
  (``resolver.py:124-125``); UNCHK-024 ③ dispositioned this field, together with ``source_age``,
  ``interval_width``, ``boundary_lag``, and ``health_state``, as structurally ineligible to be a
  ``MAX_``/``MIN_`` profile key at all — a frame-of-reference construction parameter, injected per
  deployment (the existing compose e2e fixture injects the literal ``20``,
  ``tos/runtime/tests/compose/_fixtures.py:263``). **This is a configured bound, not a
  measurement**: ``tos.time.snapshot_age_admissible`` only checks that the injected bound does not
  EXCEED ``maximum_consumer_age_ms`` (``predicates.py:287-305``) — a passing check here is not
  evidence any particular snapshot was actually observed fresh, and nobody downstream should read
  it that way. A genuinely MEASURED, same-continuity alternative exists and is deliberately not
  used here: :class:`~tos.time.TimeHealthSnapshot` carries ``issue_monotonic_value`` +
  ``issuer_continuity_id`` + ``time_continuity_identity`` as required-covered fields
  (``tos/src/tos/time/snapshot.py:73-91``), from which a same-continuity age is genuinely
  derivable via ``anchor_valid`` + the ADR §8 fail-closed rules — but both kernel composers
  (``tos.time.effective_snapshot_age_bound``, ``..._from_continuity``) are explicitly
  *cross*-continuity and need an issuer-signed age this tick path has no issuer for. That
  derivation is a NAMED FOLLOW-UP, not authored in this wave.
* ``interval_width: int`` — required at construction, no default. Composes
  ``uncertainty_interval = UncertaintyInterval(lo=anchor, hi=anchor + interval_width)`` where
  ``anchor`` is the SAME ``wall_clock_now()`` reading ``source_age`` is computed from — exactly
  ``BarTimeProjection.project``'s own construction (``resolver.py:191-193``:
  ``UncertaintyInterval(lo=anchor, hi=anchor + self.interval_width)``), substituting the runtime's
  live wall-clock anchor for the backtest's bar coordinate. When the anchor is unknown
  (``wall_clock_now()`` is ``None``), ``uncertainty_interval`` stays ``None`` — restrictive,
  consistent with every other coordinate this class cannot establish.

**Absence is restrictive, never permissive** (mirrors ``resolver.py``'s own module docstring). Any
coordinate this projection cannot establish stays ``None``, which can only narrow what
``time_admits`` allows — never widen it. In particular this module never substitutes a default, a
zero, or a "last known good" value for a missing bound or a missing session context. With
``snapshot_age_bound``/``interval_width`` now genuinely wired, a tick built through this
projection while ``HealthState.TRUSTED`` and a positively-open session context are both real can
reach a real ``tos.engine.time_admits`` verdict end-to-end — the earlier draft's structural
unreachability (an always-``None`` ``snapshot_age_bound`` making ``snapshot_age_admissible``
unconditionally ``False``) is closed.

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
from tos_runtime.time.service import TrustworthyTimeService

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

    Two independent completeness rules both raise this:

    1. Every one of the four ``delay_bounds`` terms must be an established (non-``None``) integer.
       Omitting one silently would make ``freshness_verdict``'s summed conservative age SMALLER,
       not merely absent — a strictly more permissive answer, which is the one direction absence
       must never move (module docstring). Refusing construction, rather than quietly building a
       projection that emits a three- or two-term ``delay_bounds`` tuple, is what keeps that
       shrinkage impossible rather than merely unlikely. In production this can never actually
       fire from the ``config`` side: :func:`~tos_runtime.time.config.load_time_config` already
       refuses to build a :class:`~tos_runtime.time.config.TrustworthyTimeConfig` with any of
       these four keys missing or null. This check exists anyway as the projection's OWN
       guarantee — defense in depth against a future refactor of the config loader, or a caller
       that builds a ``TrustworthyTimeConfig``-shaped object some other way.
    2. ``snapshot_age_bound`` and ``interval_width`` must each be a non-negative ``int`` — mirrors
       ``BarTimeProjection._bounds_are_bounds``'s identical non-negativity check on these same two
       field names (``resolver.py``'s validator lists both). A caller has no type-checker guard at
       runtime (a plain Python parameter accepts ``None`` despite its annotation), so this is
       checked explicitly rather than merely declared.
    """


class RuntimeTimeProjection:
    """The runtime ``(*, as_of: int | None) -> TimeAdmissionInputs`` projection (plan §2 decision 6).

    Args:
        config: The fully-valued Trustworthy Time config (:func:`~tos_runtime.time.config
            .load_time_config`'s only output shape) — every VER-002 bound this class reads.
        time_service: This process's :class:`~tos_runtime.time.service.TrustworthyTimeService` —
            the SAME instance the rest of the runtime shares, never a second, independently-driven
            one (mirrors every other compose wiring module's own "SAME source" discipline).
        session_owner: This process's :class:`~tos_runtime.calendar.owner.SessionFactsOwner`.
        instrument_class: The single instrument class this projection serves (the scheduler's own
            single-instrument scope — ``ports.py``'s ``TickOutcome`` docstring, FORWARD-OBLIGATION-MS1).
        snapshot_age_bound: The injected effective snapshot age bound (module docstring) — a
            frame-of-reference construction parameter, not a VER-002 bound. Flows through
            verbatim into every emitted ``TimeAdmissionInputs``.
        interval_width: The injected reference-frame uncertainty window width (module docstring).
            Composes ``uncertainty_interval`` around the live ``wall_clock_now()`` anchor.

    Raises:
        TimeProjectionConfigError: Any of the four ``delay_bounds`` config terms is unestablished,
            or ``snapshot_age_bound``/``interval_width`` is missing or negative. See
            :class:`TimeProjectionConfigError`'s own docstring.
    """

    def __init__(
        self,
        *,
        config: TrustworthyTimeConfig,
        time_service: TrustworthyTimeService,
        session_owner: SessionFactsOwner,
        instrument_class: str,
        snapshot_age_bound: int,
        interval_width: int,
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
        if snapshot_age_bound is None or snapshot_age_bound < 0:
            raise TimeProjectionConfigError(
                "RuntimeTimeProjection requires snapshot_age_bound to be a non-negative int "
                f"(got {snapshot_age_bound!r}) — mirrors BarTimeProjection's own "
                "non-negativity check on the identical field."
            )
        if interval_width is None or interval_width < 0:
            raise TimeProjectionConfigError(
                "RuntimeTimeProjection requires interval_width to be a non-negative int "
                f"(got {interval_width!r}) — mirrors BarTimeProjection's own non-negativity "
                "check on the identical field."
            )
        self._config = config
        self._time_service = time_service
        self._session_owner = session_owner
        self._instrument_class = instrument_class
        self._snapshot_age_bound = snapshot_age_bound
        self._interval_width = interval_width

    def __call__(self, *, as_of: int | None) -> TimeAdmissionInputs:
        """Project ``as_of`` onto the engine's injected time coordinates (module docstring)."""
        wall_clock_now = self._time_service.wall_clock_now()
        source_age = (
            wall_clock_now - as_of
            if wall_clock_now is not None and as_of is not None
            else None
        )
        uncertainty_interval = (
            UncertaintyInterval(
                lo=wall_clock_now, hi=wall_clock_now + self._interval_width
            )
            if wall_clock_now is not None
            else None
        )
        return TimeAdmissionInputs(
            source_age=source_age,
            delay_bounds=tuple(
                getattr(self._config, field_name) for field_name in _DELAY_BOUND_FIELDS
            ),
            max_age_bound=self._config.max_time_conservative_freshness_age_ms,
            future_tolerance=self._config.max_future_timestamp_tolerance_ms,
            snapshot_age_bound=self._snapshot_age_bound,
            maximum_consumer_age_ms=self._config.max_critical_input_consumer_receipt_age_ms,
            session_context=self._session_owner.session_context(self._instrument_class),
            uncertainty_interval=uncertainty_interval,
            health_state=self._time_service.health_state,
        )


#: Static conformance check — mypy fails this file if this class's call signature ever drifts
#: from the kernel's ``TimeCoordinateProjection`` Protocol (structurally; no explicit inheritance
#: edge exists, matching every other injected-port implementer in this package).
_conforms_to_time_coordinate_projection: type[TimeCoordinateProjection] = (
    RuntimeTimeProjection
)
