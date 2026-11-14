"""``tos_runtime.compose._venue_wiring`` — boots the governed venue-constraint service and"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from tos.canonical import CanonicalizationScheme
from tos.egressgw import CandidateConstruction, VenueConstraintStage
from tos.engine import StageRequest, StageVerdict
from tos.ioc import AxisBinding, CanonicalBrokerCommand, ConformanceAxis
from tos.venue import (
    ActionClass,
    InstrumentRouteFields,
    OrderAdmissibilityDecision,
    OrderShapeFields,
    PriceBandTick,
    VenueConstraintPolicy,
    VenueConstraintSnapshot,
    VenueShapeConstraints,
)

from tos_runtime.brokercap import BrokerScopesConfig, InstanceDocument
from tos_runtime.calendar.config import CalendarConfig
from tos_runtime.compose._egress_coordinates import EgressCoordinatesConfig
from tos_runtime.compose._envelope_wiring import (
    SideDerivationRefused,
    resolve_construction_direction,
)
from tos_runtime.compose._kis_credential_wiring import (
    KisCredentialSessionsCell,
    kis_mock_credential_session,
    kis_quote_pacing,
)
from tos_runtime.compose._marketfeed_wiring import (
    KIS_QUOTE_TRANSPORT_CONFIG_NAME,
    resolve_kis_instance_rest_bases,
)
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._types import ConstructionConfig
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.codec import KIS_ORDER_CASH_WIRE_FIELDS
from tos_runtime.transport.kis_mock.config import KisMockTransportConfig
from tos_runtime.transport.kis_mock.credential_session import KisCredentialSessions
from tos_runtime.transport.kis_mock.token import EvidenceRecorder
from tos_runtime.transport.kis_quote.config import (
    load_kis_quote_transport_config,
    read_declared_instrument,
)
from tos_runtime.venue import (
    ORDER_CONSTRUCTION_POLICY_CONFIG_NAME,
    VENUE_POLICY_CONFIG_NAME,
    BandObservation,
    BandReader,
    BandSourceConfig,
    KisBandSourceReader,
    KisQuoteGetBandSource,
    LoadedOrderConstructionPolicy,
    LoadedVenuePolicy,
    ProducerJournalBandReader,
    ProducerJournalBandSource,
    VenueConstraintService,
    build_band_client,
    load_order_construction_policy,
    load_venue_constraint_policy,
    record_order_construction_policy_bound,
)
from tos_runtime.venue.construction_rules import ConstructionRules

if TYPE_CHECKING:
    from tos_runtime.compose._attempt_arm import AttemptArm

__all__ = [
    "BandReaderFactory",
    "VenueBandSourceUnwired",
    "VenuePolicyScopeMismatch",
    "VenueServiceStage",
    "build_band_reader_factory",
    "build_kis_band_reader_factory",
    "build_producer_journal_band_reader_factory",
    "build_venue_service",
]

BandReaderFactory = Callable[
    [BandSourceConfig, int | None, tuple[PriceBandTick, ...] | None], BandReader
]

_KIS_ORDER_CASH_WIRE_CODEC_KIND = "kis-order-cash-v1"


class VenueBandSourceUnwired(RuntimeError):
    """The loaded Venue Constraint Policy declares a ``_runtime.band_source`` but this compose"""


class VenuePolicyScopeMismatch(RuntimeError):
    """The loaded Venue Constraint Policy's own ``scope`` does not match this compose root's"""


def _cross_check_scope(
    loaded_policy: LoadedVenuePolicy,
    *,
    construction: ConstructionConfig,
    environment_label: str,
) -> None:
    scope = loaded_policy.scope
    if scope.instrument != construction.instrument:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.instrument {scope.instrument!r} != configured "
            f"construction.instrument {construction.instrument!r}"
        )
    if scope.account != construction.account:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.account {scope.account!r} != configured "
            f"construction.account {construction.account!r}"
        )
    if scope.environment != environment_label:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.environment {scope.environment!r} != this compose root's "
            f"environment_label {environment_label!r}"
        )
    if scope.instrument_class != construction.instrument_class:
        raise VenuePolicyScopeMismatch(
            f"venue policy scope.instrument_class {scope.instrument_class!r} != configured "
            f"construction.instrument_class {construction.instrument_class!r}"
        )


def _calendar_phase_tokens(
    calendar_config: CalendarConfig, instrument_class: str
) -> frozenset[str]:
    """Every session-phase token ``calendar_config`` can produce for ``instrument_class`` —"""
    tokens = {calendar_config.closed_phase}
    tokens.update(
        window.phase for window in calendar_config.sessions.get(instrument_class, ())
    )
    rule = calendar_config.futures_expiry.get(instrument_class)
    if rule is not None:
        tokens.add(rule.expired_phase)
    return frozenset(tokens)


def _cross_check_admitting_phase_tokens(
    policy: VenueConstraintPolicy,
    *,
    calendar_config: CalendarConfig,
    instrument_class: str,
) -> None:
    allowed = _calendar_phase_tokens(calendar_config, instrument_class)
    for rule in policy.admitting_phase_rules:
        unknown = rule.admitting_phases - allowed
        if unknown:
            raise VenuePolicyScopeMismatch(
                f"venue policy admitting_phase_rules names phase token(s) "
                f"{sorted(unknown)!r} for action {rule.action!r} that calendar.yaml does not "
                f"declare for instrument class {instrument_class!r} (declared: "
                f"{sorted(allowed)!r}) — an admit over a phase the calendar can never produce "
                "is a vacuous admit, refused at boot"
            )


def _cross_check_wire_codec(
    loaded_ocp: LoadedOrderConstructionPolicy, *, transport_kind: TransportKind
) -> None:
    if transport_kind is TransportKind.SYNTHETIC:
        if loaded_ocp.wire_codec_kind is not None:
            raise VenuePolicyScopeMismatch(
                f"Order Construction Policy _runtime.wire_codec is "
                f"{loaded_ocp.wire_codec_kind!r} but the active transport is 'synthetic' — "
                "a synthetic (non-broker-reaching) transport requires wire_codec: null"
            )
        return
    if (
        loaded_ocp.wire_codec_kind != _KIS_ORDER_CASH_WIRE_CODEC_KIND
        or loaded_ocp.wire_fields != KIS_ORDER_CASH_WIRE_FIELDS
    ):
        raise VenuePolicyScopeMismatch(
            f"Order Construction Policy _runtime.wire_codec (kind="
            f"{loaded_ocp.wire_codec_kind!r}, wire_fields={sorted(loaded_ocp.wire_fields)!r}) "
            f"does not exactly declare kind={_KIS_ORDER_CASH_WIRE_CODEC_KIND!r} and "
            f"wire_fields={sorted(KIS_ORDER_CASH_WIRE_FIELDS)!r} — required for the active "
            "'kis-mock' transport"
        )


def _cross_check_price_scale(
    loaded_policy: LoadedVenuePolicy,
    *,
    transport_kind: TransportKind,
    transport_config: KisMockTransportConfig | None,
) -> None:
    """A kis-mock boot sends ``ORD_UNPR = price / price_scale`` — ONE scale, the tree's."""
    if transport_kind is TransportKind.SYNTHETIC:
        return
    transport_price_scale = (
        None if transport_config is None else transport_config.price_scale
    )
    if loaded_policy.price_scale is None or (
        loaded_policy.price_scale != transport_price_scale
    ):
        raise VenuePolicyScopeMismatch(
            f"venue policy _runtime.price_scale {loaded_policy.price_scale!r} != "
            f"kis_mock_transport.yaml price_scale {transport_price_scale!r} — the wire "
            "price would be divided by a scale the sealed price is not in (an absent policy "
            "scale is refused too: there is nothing to check the transport against)"
        )


def _broker_capability_profile_facts(
    instance_document: InstanceDocument | None,
) -> tuple[str | None, str | None]:
    """``(broker_capability_profile_version, broker_capability_profile_digest)`` — real values"""
    if instance_document is None:
        return None, None
    profile_version = instance_document.profile.profile_version
    version = None if profile_version is None else profile_version.profile_version
    digest = instance_document.profile.canonical_digest
    return version, digest


def _load_and_activate_policies(
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    construction: ConstructionConfig,
    environment_label: str,
    calendar_config: CalendarConfig,
    transport_kind: TransportKind,
) -> tuple[LoadedVenuePolicy, LoadedOrderConstructionPolicy, str, str]:
    """Load both governed policy YAMLs and run every boot-time"""
    loaded_policy = load_venue_constraint_policy(
        config_dir / VENUE_POLICY_CONFIG_NAME,
        scheme=scheme,
        band_transport_instrument_reader=lambda: read_declared_instrument(
            config_dir / KIS_QUOTE_TRANSPORT_CONFIG_NAME
        ),
    )
    loaded_ocp = load_order_construction_policy(
        config_dir / ORDER_CONSTRUCTION_POLICY_CONFIG_NAME, scheme=scheme
    )
    p, o = loaded_policy.policy, loaded_ocp.policy
    assert p.policy_id is not None and p.policy_generation is not None
    assert p.canonical_digest is not None and o.canonical_digest is not None
    assert o.policy_id is not None and o.policy_generation is not None
    _cross_check_scope(
        loaded_policy, construction=construction, environment_label=environment_label
    )
    _cross_check_admitting_phase_tokens(
        loaded_policy.policy,
        calendar_config=calendar_config,
        instrument_class=loaded_policy.scope.instrument_class,
    )
    _cross_check_wire_codec(loaded_ocp, transport_kind=transport_kind)
    return loaded_policy, loaded_ocp, p.canonical_digest, o.canonical_digest


def build_kis_band_reader_factory(
    *,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
    monotonic: MonotonicSource,
    evidence_sink: EvidenceRecorder,
    credential_sessions_cell: KisCredentialSessionsCell,
    trading_date_reader: Callable[[], str | None],
) -> BandReaderFactory:
    """The production :data:`BandReaderFactory` — a KIS band reader on the ``kis_quote``"""

    def _factory(
        band_source: BandSourceConfig,
        tick_size: int | None,
        price_band_ticks: tuple[PriceBandTick, ...] | None,
    ) -> BandReader:
        assert isinstance(band_source, KisQuoteGetBandSource)
        mock_rest_base, real_rest_base = resolve_kis_instance_rest_bases(broker_scopes)
        transport_config = load_kis_quote_transport_config(
            config_dir / KIS_QUOTE_TRANSPORT_CONFIG_NAME,
            instance_mock_rest_base=mock_rest_base,
            instance_real_rest_base=real_rest_base,
        )
        client = build_band_client(transport_config, band_source)
        built: dict[str, KisBandSourceReader | None] = {"reader": None}

        def _build(sessions: KisCredentialSessions) -> None:
            built["reader"] = KisBandSourceReader(
                band_source=band_source,
                transport_config=transport_config,
                client=client,
                credential_session=kis_mock_credential_session(
                    sessions,
                    client=client,
                    token_endpoint_base=transport_config.endpoint_rest_base,
                    token_path=transport_config.token_path,
                    token_reissue_min_interval_s=(
                        transport_config.token_reissue_min_interval_s
                    ),
                    pacing=kis_quote_pacing(transport_config),
                ),
                monotonic=monotonic,
                evidence_sink=evidence_sink,
                trading_date_reader=trading_date_reader,
                tick_size=tick_size,
                price_band_ticks=price_band_ticks,
            )

        credential_sessions_cell.on_ready(_build)

        def _read() -> BandObservation | None:
            reader = built["reader"]
            if reader is None:
                raise VenueBandSourceUnwired(
                    "band source read attempted before this boot's KIS credential registry "
                    "existed — the band reader must never build a private session "
                    "(C-2 decision (C): one app key, one token lifecycle). Reaching input: "
                    '`kind: kis_quote_get` with "boot" in `read_on` — that instant is '
                    "__init__, before _finalize fills it. Use phase_change, or producer_journal"
                )
            return reader.read()

        return _read

    return _factory


def build_producer_journal_band_reader_factory(
    *,
    monotonic: MonotonicSource,
    evidence_sink: EvidenceRecorder,
    trading_date_reader: Callable[[], str | None],
) -> BandReaderFactory:
    """The production :data:`BandReaderFactory` for ``kind: "producer_journal"`` (CP-3 band"""

    def _factory(
        band_source: BandSourceConfig,
        tick_size: int | None,
        price_band_ticks: tuple[PriceBandTick, ...] | None,
    ) -> BandReader:
        assert isinstance(band_source, ProducerJournalBandSource)
        reader = ProducerJournalBandReader(
            band_source=band_source,
            monotonic=monotonic,
            evidence_sink=evidence_sink,
            trading_date_reader=trading_date_reader,
            tick_size=tick_size,
            price_band_ticks=price_band_ticks,
        )
        return reader.read

    return _factory


def build_band_reader_factory(
    *,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
    monotonic: MonotonicSource,
    evidence_sink: EvidenceRecorder,
    credential_sessions_cell: KisCredentialSessionsCell,
    trading_date_reader: Callable[[], str | None],
) -> BandReaderFactory:
    """The one :data:`BandReaderFactory` the compose root passes in — it dispatches on the"""
    kis_factory = build_kis_band_reader_factory(
        config_dir=config_dir,
        broker_scopes=broker_scopes,
        monotonic=monotonic,
        evidence_sink=evidence_sink,
        credential_sessions_cell=credential_sessions_cell,
        trading_date_reader=trading_date_reader,
    )
    journal_factory = build_producer_journal_band_reader_factory(
        monotonic=monotonic,
        evidence_sink=evidence_sink,
        trading_date_reader=trading_date_reader,
    )

    def _factory(
        band_source: BandSourceConfig,
        tick_size: int | None,
        price_band_ticks: tuple[PriceBandTick, ...] | None,
    ) -> BandReader:
        if isinstance(band_source, ProducerJournalBandSource):
            return journal_factory(band_source, tick_size, price_band_ticks)
        return kis_factory(band_source, tick_size, price_band_ticks)

    return _factory


def build_venue_service(
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    construction: ConstructionConfig,
    environment_label: str,
    session_phase_reader: Callable[[], str | None],
    tick_generation_reader: Callable[[], int | None],
    evidence_store: SqliteEvidenceStore,
    instance_document: InstanceDocument | None,
    egress_coordinates: EgressCoordinatesConfig,
    transport_kind: TransportKind,
    calendar_config: CalendarConfig,
    band_reader_factory: BandReaderFactory | None = None,
    trading_date_reader: Callable[[], str | None] | None = None,
    transport_config: KisMockTransportConfig | None,
) -> tuple[VenueConstraintService, LoadedOrderConstructionPolicy]:
    """Load, activate, cross-check, and construct the governed venue-constraint service"""
    loaded_policy, loaded_ocp, venue_digest, ocp_digest = _load_and_activate_policies(
        config_dir=config_dir,
        scheme=scheme,
        construction=construction,
        environment_label=environment_label,
        calendar_config=calendar_config,
        transport_kind=transport_kind,
    )
    _cross_check_price_scale(
        loaded_policy,
        transport_kind=transport_kind,
        transport_config=transport_config,
    )
    profile_version, profile_digest = _broker_capability_profile_facts(
        instance_document
    )
    route_fields = InstrumentRouteFields(
        canonical_instrument_id=construction.instrument,
        venue_listing=loaded_policy.scope.venue,
        market_segment=loaded_policy.scope.market_segment,
        currency=loaded_policy.scope.currency,
        account_mapping=construction.account,
        environment=environment_label,
        broker=loaded_policy.scope.broker,
        route=egress_coordinates.route_identity,
    )
    band_reader: BandReader | None = None
    if loaded_policy.band_source is not None:
        if band_reader_factory is None:
            raise VenueBandSourceUnwired(
                f"{config_dir / VENUE_POLICY_CONFIG_NAME}: _runtime.band_source is declared "
                "but this compose root supplied no band_reader_factory — refusing to boot a "
                "policy whose declared source would never be read"
            )
        band_reader = band_reader_factory(
            loaded_policy.band_source,
            loaded_policy.policy.shape_constraints.tick_size,
            loaded_policy.policy.shape_constraints.price_band_ticks,
        )
    service = VenueConstraintService(
        loaded_policy=loaded_policy,
        scheme=scheme,
        session_phase_reader=session_phase_reader,
        tick_generation_reader=tick_generation_reader,
        evidence_store=evidence_store,
        environment_label=environment_label,
        route_fields=route_fields,
        broker_capability_profile_version=profile_version,
        broker_capability_profile_digest=profile_digest,
        activated_member_digest=venue_digest,
        band_reader=band_reader,
        trading_date_reader=(
            None if loaded_policy.band_source is None else trading_date_reader
        ),
    )
    record_order_construction_policy_bound(evidence_store, loaded_ocp, ocp_digest)
    return service, loaded_ocp


def _derived_shape_quantity(
    candidate_command: CanonicalBrokerCommand | None,
) -> int | None:
    """The QUANTITY axis value ``construct_candidate_command`` already bound onto the command"""
    if candidate_command is None:
        return None
    raw = candidate_command.axis_value(ConformanceAxis.QUANTITY)
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except (InvalidOperation, ValueError):
        return None
    if value != value.to_integral_value():
        return None
    return int(value)


def _authorized_axis_value(
    authorized_axes: tuple[AxisBinding, ...], axis: ConformanceAxis
) -> str | None:
    """The single bound value for ``axis`` in ``authorized_axes`` — ``None`` if absent. The one"""
    for binding in authorized_axes:
        if binding.axis == axis:
            return binding.value
    return None


def _shape_side_and_position_effect(
    construction_rules: ConstructionRules,
    action_class: ActionClass | None,
) -> tuple[str | None, str | None]:
    """``(side, position_effect)`` for ``action_class``, sourced from the OCP's own"""
    if action_class is None:
        return None, None
    try:
        direction = resolve_construction_direction(
            construction_rules, action_class=action_class
        )
    except SideDerivationRefused:
        return None, None
    mapped = construction_rules.action_class_shape.get((action_class, direction))
    if mapped is None:
        return None, None
    return mapped.side, mapped.position_effect


def _shape_order_type_and_tif(
    construction_rules: ConstructionRules,
) -> tuple[str | None, str | None]:
    """``(order_type, tif)`` sourced from ``ConstructionRules.authorized_axes`` (a′) wave"""
    return (
        _authorized_axis_value(
            construction_rules.authorized_axes, ConformanceAxis.ORDER_TYPE
        ),
        _authorized_axis_value(construction_rules.authorized_axes, ConformanceAxis.TIF),
    )


def _observed_silently_rounded() -> bool:
    """``False``, always — an observation of the RUNTIME's own behaviour, not a relayed"""
    return False


class _ConstructionStageReader(Protocol):
    """The narrow read surface :class:`VenueServiceStage` needs off a"""

    @property
    def construction(self) -> CandidateConstruction | None: ...


class VenueServiceStage:
    """Step 3, folded against a live :class:`~tos_runtime.venue.VenueConstraintService`"""

    def __init__(
        self,
        service: VenueConstraintService,
        construction_stage: _ConstructionStageReader,
        action_class: ActionClass,
        shape_price_field_key: str | None,
        *,
        shape: OrderShapeFields | None = None,
        construction_rules: ConstructionRules | None = None,
        attempt_reader: Callable[[], AttemptArm | None] | None = None,
    ) -> None:
        self._service = service
        self._attempt_reader = attempt_reader or (lambda: None)
        self._construction_stage = construction_stage
        self._action_class = action_class
        self._shape = shape if shape is not None else OrderShapeFields()
        self._shape_price_field_key = shape_price_field_key
        self._construction_rules = construction_rules
        self._last_stage: VenueConstraintStage | None = None

    def __call__(self, request: StageRequest) -> StageVerdict:
        snapshot = self._service.snapshot()
        arm = self._attempt_reader()
        action_class = self._action_class if arm is None else arm.action_class
        stage0 = VenueConstraintStage(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=action_class,
            snapshot=snapshot,
            policy=self._service.policy,
            shape=self._shape,
            constraints=self._service.shape_constraints,
            decision=None,
            shape_price_field_key=self._shape_price_field_key,
        )
        stage0(request)
        resolved = stage0.resolved_shape
        construction = self._construction_stage.construction
        candidate_command = None if construction is None else construction.command
        shape_for_decision = self._sourced_shape(resolved, candidate_command)
        decision = self._service.decide(
            action_class=action_class,
            shape=shape_for_decision,
            candidate_command=candidate_command,
        )
        stage = VenueConstraintStage(
            observed_session_phase=snapshot.observed_session_phase,
            action_class=action_class,
            snapshot=snapshot,
            policy=self._service.policy,
            shape=shape_for_decision,
            constraints=self._service.shape_constraints,
            decision=decision,
            shape_price_field_key=self._shape_price_field_key,
        )
        self._last_stage = stage
        return stage(request)

    def _sourced_shape(
        self,
        resolved: OrderShapeFields | None,
        candidate_command: CanonicalBrokerCommand | None,
    ) -> OrderShapeFields | None:
        """Build the exact shape both folds judge — ``resolved`` (fold #1's price-projected"""
        if resolved is None:
            return None
        updates: dict[str, object] = {
            "quantity": _derived_shape_quantity(candidate_command),
            "silently_rounded": _observed_silently_rounded(),
        }
        if self._construction_rules is not None:
            arm = self._attempt_reader()
            side, position_effect = (
                _shape_side_and_position_effect(
                    self._construction_rules, self._action_class
                )
                if arm is None
                else (arm.side, arm.position_effect)
            )
            order_type, tif = _shape_order_type_and_tif(self._construction_rules)
            updates["side"] = side
            updates["position_effect"] = position_effect
            updates["order_type"] = order_type
            updates["tif"] = tif
        return resolved.model_copy(update=updates)

    @property
    def resolved_shape(self) -> OrderShapeFields | None:
        return None if self._last_stage is None else self._last_stage.resolved_shape

    @property
    def shape_constraints(self) -> VenueShapeConstraints | None:
        return self._service.shape_constraints

    @property
    def policy(self) -> VenueConstraintPolicy:
        return self._service.policy

    @property
    def last_snapshot(self) -> VenueConstraintSnapshot | None:
        return self._service.last_snapshot

    @property
    def last_decision(self) -> OrderAdmissibilityDecision | None:
        return self._service.last_decision
