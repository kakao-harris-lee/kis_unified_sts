"""Hermetic tests for tos_runtime.marketfeed.time_projection (TOS 틱 원천 웨이브 §2 decision 6,
lane C).

D1.4 hermetic: ``TrustworthyTimeService`` is built with local fakes only (mirrors the
``FakeMonotonicSource``/``FakeEvidenceAppendPort``/``FakeReferenceReader`` idiom every other
``tos_runtime.time``/``tos_runtime.authority`` test file already uses — no shared fixture module
exists for these, by this package's own established convention). ``_FakeSessionOwner`` is a
narrow double for the ONE method ``RuntimeTimeProjection`` reads off
``tos_runtime.calendar.owner.SessionFactsOwner`` (``session_context``) — building the real owner
needs a ``CalendarConfig``/``WallClockReference``/``SqliteEvidenceStore`` wiring this module's own
logic never touches, so a duck-typed double is the right isolation boundary here (mypy does not
check this tests/ tree — see the gate list — so the double need not subclass the real owner).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

import pytest
from tos.engine import time_admits
from tos.evidence import EvidenceAppendReceipt
from tos.time import FreshnessVerdict, HealthState, SessionContext, freshness_verdict
from tos.workload import RuntimeIdentity
from tos_runtime.marketfeed.time_projection import (
    RuntimeTimeProjection,
    TimeProjectionConfigError,
)
from tos_runtime.time.config import TrustworthyTimeConfig
from tos_runtime.time.service import TrustworthyTimeService
from tos_runtime.time.sources import ReferenceObservation

# ----------------------------------------------------------------------------
# fakes (local to this file — see module docstring)
# ----------------------------------------------------------------------------


class FakeEvidenceAppendPort:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, object], str, str]] = []

    def append(
        self, payload: Mapping[str, object], *, kind: str, record_class: str
    ) -> EvidenceAppendReceipt:
        self.calls.append((dict(payload), kind, record_class))
        return EvidenceAppendReceipt(
            segment_id=None,
            seq=len(self.calls) - 1,
            chain_digest="fake",
            key_generation=1,
        )


class FakeMonotonicSource:
    def __init__(self, first: int = 1_000) -> None:
        self.value = first

    def now_ms(self) -> int:
        return self.value


@dataclass
class FakeReferenceReader:
    reachable: bool = True
    healthy: bool = True
    quality: str | None = "FAKE"
    common_mode_group: str | None = None
    wall_clock_unix_ms: int | None = 1_700_000_000_000

    def read(self) -> ReferenceObservation:
        return ReferenceObservation(
            reachable=self.reachable,
            healthy=self.healthy,
            quality=self.quality,
            common_mode_group=self.common_mode_group,
            wall_clock_unix_ms=self.wall_clock_unix_ms,
        )


class _FakeSessionOwner:
    """A narrow double for the one method RuntimeTimeProjection reads."""

    def __init__(self, session_context: SessionContext | None) -> None:
        self._session_context = session_context
        self.calls: list[str] = []

    def session_context(self, instrument_class: str) -> SessionContext | None:
        self.calls.append(instrument_class)
        return self._session_context


# ----------------------------------------------------------------------------
# config / service builders
# ----------------------------------------------------------------------------


def _config(**overrides: object) -> TrustworthyTimeConfig:
    base: dict[str, object] = {
        "max_time_source_precision_ms": 5,
        "max_time_transport_and_queue_uncertainty_ms": 10,
        "max_time_conservative_freshness_age_ms": 1000,
        "max_future_timestamp_tolerance_ms": 200,
        "max_process_suspension_ms": 0,
        "max_time_source_disagreement_ms": 50,
        "min_time_independent_reference_count": 1,
        "max_clock_domain_conversion_uncertainty_ms": 50,
        "max_send_result_wait_ms": 5000,
        "max_critical_input_consumer_receipt_age_ms": 1000,
        "max_time_source_sequence_gap_ms": 50,
        "tz_db_version": "2026a",
        "trading_calendar_version": "cal-1",
        "verification_profile_version": "vp-0",
        "safety_profile_version": "sp-0",
    }
    base.update(overrides)
    return TrustworthyTimeConfig(**base)  # type: ignore[arg-type]


def _identity() -> RuntimeIdentity:
    return RuntimeIdentity(
        cell_id="cell-1", runtime_generation=0, process_nonce="nonce-1"
    )


def _build_service(
    *,
    monotonic: FakeMonotonicSource | None = None,
    config: TrustworthyTimeConfig | None = None,
    references: list[FakeReferenceReader] | None = None,
) -> TrustworthyTimeService:
    return TrustworthyTimeService(
        monotonic=monotonic if monotonic is not None else FakeMonotonicSource(1_000),
        references=references if references is not None else [FakeReferenceReader()],
        config=config if config is not None else _config(),
        identity=_identity(),
        evidence=FakeEvidenceAppendPort(),
    )


def _projection(
    *,
    config: TrustworthyTimeConfig | None = None,
    service: TrustworthyTimeService | None = None,
    session_context: SessionContext | None = None,
    instrument_class: str = "005930",
) -> RuntimeTimeProjection:
    return RuntimeTimeProjection(
        config=config if config is not None else _config(),
        time_service=service if service is not None else _build_service(config=config),
        session_owner=_FakeSessionOwner(session_context),
        instrument_class=instrument_class,
    )


# ----------------------------------------------------------------------------
# unknown wall_clock_now -> source_age None -> denied through the KERNEL's own path
# ----------------------------------------------------------------------------


def test_source_age_is_none_when_wall_clock_unknown() -> None:
    """A service that has only ``start()``-ed (never ``evaluate()``-d) stays
    ``HealthState.UNINITIALIZED``, so ``wall_clock_now()`` is honestly ``None`` (gated on
    TRUSTED) — this must not be papered over with ``as_of`` or any other substitute."""
    service = _build_service()
    service.start()
    projection = _projection(service=service)

    result = projection(as_of=1_700_000_000_000)

    assert result.source_age is None


def test_unknown_source_age_denies_admission_via_kernel_freshness_verdict() -> None:
    """Proves the denial through the REAL kernel predicate, not merely the dataclass field."""
    service = _build_service()
    service.start()
    projection = _projection(service=service)

    result = projection(as_of=1_700_000_000_000)

    verdict = freshness_verdict(
        source_age=result.source_age,
        delay_bounds=result.delay_bounds,
        max_age_bound=result.max_age_bound,
        future_tolerance=result.future_tolerance,
    )
    assert verdict is not FreshnessVerdict.FRESH


def test_unknown_source_age_denies_admission_via_kernel_time_admits() -> None:
    """The full four-check ``tos.engine.time_admits`` chain also denies — freshness is the
    FIRST check, so it fails before any of the other three coordinates matter."""
    service = _build_service()
    service.start()
    projection = _projection(service=service)

    result = projection(as_of=1_700_000_000_000)

    admitted, reason = time_admits(result)

    assert admitted is False
    assert reason is not None and "freshness" in reason.lower()


def test_wall_clock_unknown_when_as_of_is_none_too() -> None:
    service = _build_service()
    service.start()
    projection = _projection(service=service)

    result = projection(as_of=None)

    assert result.source_age is None


# ----------------------------------------------------------------------------
# source_age computed when both wall_clock_now() and as_of are known
# ----------------------------------------------------------------------------


def test_source_age_is_computed_when_both_known() -> None:
    monotonic = FakeMonotonicSource(1_000)
    service = _build_service(monotonic=monotonic)
    service.start()
    service.evaluate()  # -> SYNCHRONIZING
    monotonic.value = 1_010
    service.evaluate()  # -> TRUSTED (single stabilization step is enough — mirrors
    #    test_service.py's own "reaching_required_conditions" pattern)
    assert service.health_state is HealthState.TRUSTED
    wall_clock_now = service.wall_clock_now()
    assert wall_clock_now is not None

    projection = _projection(service=service)
    as_of = wall_clock_now - 37

    result = projection(as_of=as_of)

    assert result.source_age == 37


# ----------------------------------------------------------------------------
# session_context — carried verbatim, never fabricated
# ----------------------------------------------------------------------------


def test_none_session_context_is_carried_as_none_not_replaced() -> None:
    service = _build_service()
    service.start()
    projection = _projection(service=service, session_context=None)

    result = projection(as_of=None)

    assert result.session_context is None


def test_real_session_context_is_passed_through_verbatim() -> None:
    service = _build_service()
    service.start()
    context = SessionContext(phase="REGULAR", is_open=True, boundary_value=999)
    projection = _projection(service=service, session_context=context)

    result = projection(as_of=None)

    assert result.session_context is context


def test_session_owner_is_read_for_the_configured_instrument_class() -> None:
    service = _build_service()
    service.start()
    owner = _FakeSessionOwner(None)
    projection = RuntimeTimeProjection(
        config=_config(),
        time_service=service,
        session_owner=owner,
        instrument_class="FUTURES",
    )

    projection(as_of=None)

    assert owner.calls == ["FUTURES"]


# ----------------------------------------------------------------------------
# health_state — the service's own, verbatim
# ----------------------------------------------------------------------------


def test_health_state_is_the_services_own_uninitialized_before_evaluate() -> None:
    service = _build_service()
    service.start()
    projection = _projection(service=service)

    result = projection(as_of=None)

    assert result.health_state is HealthState.UNINITIALIZED


def test_health_state_is_the_services_own_trusted_after_evaluate() -> None:
    monotonic = FakeMonotonicSource(1_000)
    service = _build_service(monotonic=monotonic)
    service.start()
    service.evaluate()
    monotonic.value = 1_010
    service.evaluate()
    assert service.health_state is HealthState.TRUSTED
    projection = _projection(service=service)

    result = projection(as_of=None)

    assert result.health_state is HealthState.TRUSTED


# ----------------------------------------------------------------------------
# every bound comes from config — mutate one value, assert the projected field changes
# (proves there is no hardcoded literal anywhere in the binding)
# ----------------------------------------------------------------------------


def test_future_tolerance_comes_from_config() -> None:
    config = _config(max_future_timestamp_tolerance_ms=4242)
    service = _build_service(config=config)
    service.start()
    result = _projection(config=config, service=service)(as_of=None)

    assert result.future_tolerance == 4242


def test_maximum_consumer_age_ms_comes_from_config() -> None:
    config = _config(max_critical_input_consumer_receipt_age_ms=8181)
    service = _build_service(config=config)
    service.start()
    result = _projection(config=config, service=service)(as_of=None)

    assert result.maximum_consumer_age_ms == 8181


def test_max_age_bound_comes_from_config() -> None:
    config = _config(max_time_conservative_freshness_age_ms=6161)
    service = _build_service(config=config)
    service.start()
    result = _projection(config=config, service=service)(as_of=None)

    assert result.max_age_bound == 6161


@pytest.mark.parametrize(
    ("config_field", "slot_index"),
    [
        ("max_time_transport_and_queue_uncertainty_ms", 0),
        ("max_clock_domain_conversion_uncertainty_ms", 1),
        ("max_time_source_precision_ms", 2),
        ("max_time_source_sequence_gap_ms", 3),
    ],
)
def test_delay_bounds_slot_comes_from_the_matching_config_field(
    config_field: str, slot_index: int
) -> None:
    """Mutates exactly ONE of the four delay-bound config fields and asserts it lands in the
    correspondingly-ordered ``delay_bounds`` slot — proves the binding is per-field, not just
    "the tuple has four numbers"."""
    mutated_value = 9000 + slot_index
    config = _config(**{config_field: mutated_value})
    service = _build_service(config=config)
    service.start()
    result = _projection(config=config, service=service)(as_of=None)

    assert result.delay_bounds[slot_index] == mutated_value
    # every OTHER slot stays at the unmutated default — proves this isn't a coincidental match
    default_config = _config()
    default_bounds = _projection(
        config=default_config, service=_build_service(config=default_config)
    )(as_of=None).delay_bounds
    for other_slot in range(4):
        if other_slot != slot_index:
            assert result.delay_bounds[other_slot] == default_bounds[other_slot]


# ----------------------------------------------------------------------------
# dropping a delay_bounds term is REFUSED at construction, never silently summed as three
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    [
        "max_time_transport_and_queue_uncertainty_ms",
        "max_clock_domain_conversion_uncertainty_ms",
        "max_time_source_precision_ms",
        "max_time_source_sequence_gap_ms",
    ],
)
def test_missing_delay_bound_term_refuses_construction(missing_field: str) -> None:
    """``TrustworthyTimeConfig`` is a plain dataclass — nothing stops a caller from building one
    some other way with a field left ``None`` (``load_time_config`` is the only path that
    enforces completeness, and it lives in a different module). ``RuntimeTimeProjection`` must
    refuse on its OWN, not merely inherit that guarantee (see ``TimeProjectionConfigError``'s
    docstring)."""
    broken_config = replace(_config(), **{missing_field: None})  # type: ignore[arg-type]
    service = _build_service()
    service.start()

    with pytest.raises(TimeProjectionConfigError, match=missing_field):
        RuntimeTimeProjection(
            config=broken_config,
            time_service=service,
            session_owner=_FakeSessionOwner(None),
            instrument_class="005930",
        )


def test_missing_delay_bound_term_never_reaches_a_three_term_tuple() -> None:
    """Belt-and-suspenders: even if construction refused for the wrong reason, this proves no
    ``RuntimeTimeProjection`` carrying a 3-term ``delay_bounds`` is ever reachable."""
    broken_config = replace(
        _config(), max_time_source_sequence_gap_ms=None
    )  # type: ignore[arg-type]
    service = _build_service()
    service.start()

    with pytest.raises(TimeProjectionConfigError):
        RuntimeTimeProjection(
            config=broken_config,
            time_service=service,
            session_owner=_FakeSessionOwner(None),
            instrument_class="005930",
        )
    # no projection object was ever constructed to call — nothing to assert on further; the
    # exception above IS the assertion that a 3-term tuple can never be built.


# ----------------------------------------------------------------------------
# uncertainty_interval — honestly None (current TimeHealthSnapshot schema carries none)
# ----------------------------------------------------------------------------


def test_uncertainty_interval_is_none_before_any_evaluate() -> None:
    service = _build_service()
    service.start()
    projection = _projection(service=service)

    result = projection(as_of=None)

    assert result.uncertainty_interval is None


def test_uncertainty_interval_is_none_after_evaluate_too() -> None:
    """Current ``TimeHealthSnapshot`` (``tos/src/tos/time/snapshot.py``) carries no
    ``uncertainty_interval`` field at all, so this stays ``None`` even once a real snapshot
    exists — an honest absence, not a bug (see ``RuntimeTimeProjection._uncertainty_interval``'s
    docstring)."""
    monotonic = FakeMonotonicSource(1_000)
    service = _build_service(monotonic=monotonic)
    service.start()
    service.evaluate()
    monotonic.value = 1_010
    service.evaluate()
    assert service.current_snapshot() is not None
    projection = _projection(service=service)

    result = projection(as_of=None)

    assert result.uncertainty_interval is None


# ----------------------------------------------------------------------------
# snapshot_age_bound — deliberately left at the engine default (documented scope boundary)
# ----------------------------------------------------------------------------


def test_snapshot_age_bound_is_left_at_engine_default() -> None:
    service = _build_service()
    service.start()
    projection = _projection(service=service)

    result = projection(as_of=None)

    assert result.snapshot_age_bound is None
