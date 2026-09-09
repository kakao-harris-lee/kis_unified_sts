"""``tos_runtime.compose`` engine-driver wiring — TOS Phase 3 Wave 1 Lane A-R.

Split out of ``_wiring.py``/``root.py`` for the size budget
(``tools/tos_size_budget.py`` — ``_wiring.py`` was already registered at 1116
lines before this wave; see ``config/tos_size_budget.yaml``), not for any
behavioural reason: :func:`build_engine_driver` is called from
``_wiring.py``'s own ``_finalize`` exactly once, in the design #40 §5 order
this compose root already documents (engine core wired first, driver last —
the driver needs the composed core AND gateway to exist).

Owns three things:

1. :func:`load_engine_driver_config` — the ``replay_window_events`` boot-time
   cost bound (plan §1.1; see ``tos/runtime/config/engine_driver.example.yaml``).
2. :func:`build_engine_driver` — constructs the durable
   :class:`~tos_runtime.engine.inbox.SqliteEventInbox` (its own sqlite file,
   SEPARATE from the evidence store — D3 failure-domain separation, operator-
   confirmed item 2) and the :class:`~tos_runtime.engine.driver.EngineDriver`
   bound to the already-composed core and gateway.
3. :func:`wire_engine_and_driver` — since TOS Phase 3 Wave 2 Lane B-R, also
   constructs the kernel's REQUIRED ``EngineCore(preconditions=...)`` argument
   (design #31 §9-10; plan §2.1): a
   :class:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions`
   for the live core, over the already-composed
   :class:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService` and the
   caller-resolved restricted-live governance posture (``config_dir``'s
   ``coordinator_preconditions.yaml`` — loaded by the caller, ``_wiring.py``'s
   ``_finalize``, the same pattern ``engine_driver.yaml`` already follows), and
   a side-effect-free
   :class:`~tos_runtime.compose._preconditions._ReplayPreconditions` for the
   boot-time replay core (see :class:`_ReplayStage`'s own docstring for why
   the replay core needs its OWN stand-ins throughout, not the real ones).

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib
(``pathlib``, ``yaml``) + ``tos.canonical``/``tos.egressgw``/``tos.engine``/
``tos.liveauth`` (transitively, via ``_preconditions``) + ``tos_runtime.*``
only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport
from tos.canonical import CanonicalizationScheme
from tos.egressgw import BrokerEgressGateway
from tos.engine import (
    CommitmentStep,
    EngineConfiguration,
    EngineCore,
    NullEvidenceSink,
    Stage,
    StrategyRegistry,
)
from tos.engine.records import StageRequest, StageVerdict
from tos.engine.vocabulary import StageAuthorityClass, StageOutcome
from tos.workload import RuntimeIdentity

from tos_runtime.authority.epoch import SafetyAuthorityEpochService
from tos_runtime.compose._boot_integrity import verify_engine_replay_or_halt
from tos_runtime.compose._preconditions import (
    RuntimeCoordinatorPreconditions,
    _ReplayPreconditions,
)
from tos_runtime.compose.context import ComposeContextResolver
from tos_runtime.engine.driver import EngineDriver
from tos_runtime.engine.inbox import SqliteEventInbox
from tos_runtime.engine.orthostate_projection import OrthostateProjector
from tos_runtime.engine.replay import ReplayVerdict
from tos_runtime.evidence.emergency import EmergencyAppendLog
from tos_runtime.evidence.sinks import (
    EngineEvidenceSinkAdapter,
    GatewayEvidenceSinkAdapter,
)
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.posttrade.config import FinalityConfig
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.rcl.obligation import CapacityObligationRecorder
from tos_runtime.rcl.projection import SqliteReservationProjectionReader
from tos_runtime.time.sources import MonotonicSource

__all__ = [
    "ENGINE_DRIVER_CONFIG_NAME",
    "INBOX_FILE_NAME",
    "EngineDriverConfig",
    "EngineDriverConfigError",
    "WiredEngine",
    "build_engine_driver",
    "load_engine_driver_config",
    "verify_replay_or_halt",
    "wire_engine_and_driver",
]

ENGINE_DRIVER_CONFIG_NAME = "engine_driver.yaml"

#: The durable event inbox's own sqlite file name — a SEPARATE file from
#: ``evidence.sqlite3`` (module docstring item 2 / D3 failure-domain
#: separation).
INBOX_FILE_NAME = "inbox.sqlite3"


class EngineDriverConfigError(Exception):
    """Raised when the engine-driver config is missing, malformed, or
    carries an unfilled (named-TBD) field — fail-closed at load, never a
    silent default."""


@dataclass(frozen=True)
class EngineDriverConfig:
    """The one operator-configured engine-driver bound (module docstring)."""

    replay_window_events: int


def _require_positive_int(raw: Any, field: str, path: Path) -> int:
    value = raw.get(field) if isinstance(raw, dict) else None
    if isinstance(value, bool) or not isinstance(value, int):
        raise EngineDriverConfigError(
            f"{path}: {field!r} is missing, still null (named-TBD), or not "
            "an int — refusing to start until an operator supplies a "
            "concrete value"
        )
    if value <= 0:
        raise EngineDriverConfigError(
            f"{path}: {field!r} must be a positive int (got {value!r}) — a "
            "zero/negative replay window is not a smaller window, it is a "
            "silently-disabled one"
        )
    return value


def load_engine_driver_config(path: Path) -> EngineDriverConfig:
    """Load + fail-closed-validate the engine-driver config from ``path``.

    Raises:
        EngineDriverConfigError: The file is missing/unreadable/not valid
            YAML/not a mapping, the key is absent, still ``null``, not an
            int, or not a positive int.
    """
    if not path.is_file():
        raise EngineDriverConfigError(f"engine-driver config file not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise EngineDriverConfigError(
            f"engine-driver config file could not be read: {path}"
        ) from exc
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise EngineDriverConfigError(
            f"engine-driver config file is not valid YAML: {path}"
        ) from exc
    if not isinstance(raw, dict):
        raise EngineDriverConfigError(
            f"engine-driver config file must be a top-level mapping: {path}"
        )
    return EngineDriverConfig(
        replay_window_events=_require_positive_int(raw, "replay_window_events", path)
    )


def build_engine_driver(
    *,
    data_dir: Path,
    core: EngineCore,
    gateway: BrokerEgressGateway,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    scheme: CanonicalizationScheme,
    continuity_id: str,
    monotonic_source: MonotonicSource,
    max_send_result_wait_ms: int,
    finality_config: FinalityConfig,
    authority_epoch_current: Callable[[], bool | None],
) -> tuple[SqliteEventInbox, EngineDriver]:
    """Construct the durable inbox and the engine driver, bound to ``gateway``.

    Args:
        data_dir: Directory for the inbox's own sqlite file (SEPARATE from
            the evidence store's — module docstring item 2).
        core: The already-composed :class:`~tos.engine.EngineCore`.
        gateway: The already-composed send boundary whose retained
            ``.results`` the driver drains.
        evidence_store: The durable evidence store the driver appends
            ``EVENT_HANDLING_STARTED``/``EVENT_CONSUMED`` receipts into.
        emergency_log: The sqlite-independent dual-path HALT log (independent review finding #3
            — the driver's "possibly live" crash-window case).
        scheme: The canonicalization scheme for event identity and the
            outcome-digest stand-in.
        continuity_id: The single stream continuity every coordinate this
            driver issues carries.
        monotonic_source: The injected monotonic clock for timeout
            injection.
        max_send_result_wait_ms: The injected wait bound before a SENT_UNCONFIRMED hand-off is
            timed out (independent review finding #14 — always a concrete positive int; compose
            already supplies one via ``TrustworthyTimeConfig``, itself non-optional).
        finality_config: The caller-resolved (``_wiring.py``'s ``_finalize``, loaded from
            ``config_dir``'s ``finality.yaml`` — the ``engine_driver.yaml``/
            ``coordinator_preconditions.yaml`` precedent this module's own docstring item 3
            already names) SYNTHETIC post-trade finality policy
            (:mod:`tos_runtime.posttrade.config`). Feeds the
            :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer` this driver is
            wired with (team-lead CR-4 dispatch, plan §2.2) — REQUIRED, no default, so an
            unfilled config value refuses boot rather than silently omitting finality projection.
        authority_epoch_current: The SAME Safety-Authority-epoch check
            :class:`~tos_runtime.compose._preconditions.RuntimeCoordinatorPreconditions` performs
            for the kernel's own Coordinator gate (``preconditions.authority_epoch_current``,
            forwarded by the caller) — feeds
            :class:`~tos_runtime.engine.orthostate_projection.OrthostateProjector`'s CPL-6 side
            condition (its own module docstring: "CPL-6 needs a LIVE authority-epoch reading",
            bug found wiring this driver reachable end to end). **What this callable actually
            means, precisely (2026-09-09 wave-2 review finding #7 fix):** whether the epoch this
            runtime was BOUND TO at composition time (``RuntimeCoordinatorPreconditions``'s own
            ``_bound_epoch``, captured once when it was constructed, never re-read per tick) is
            still ``>=`` the CURRENT epoch floor — i.e. whether the Safety Authority epoch this
            runtime composed under is still current, not merely whether the epoch log is
            readable right now. An earlier version of this callable re-derived the claim from the
            SAME just-read floor it then compared against (a ``floor >= floor`` tautology), which
            could only ever detect an unreadable log — never a genuinely stale epoch (e.g. a
            failover after this runtime booted). A caller reading this docstring should take
            "CPL-6 side condition is ``True``" to mean "this runtime's own bound epoch has not
            been superseded", not merely "the log is up".

    Returns:
        ``(inbox, driver)`` — the driver is already bound to ``gateway``.
    """
    inbox = SqliteEventInbox(data_dir / INBOX_FILE_NAME, scheme=scheme)
    orthostate_projector = OrthostateProjector(
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        authority_epoch_current=authority_epoch_current,
    )
    finality_producer = SyntheticFinalityProducer(config=finality_config, scheme=scheme)
    driver = EngineDriver(
        core=core,
        inbox=inbox,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=scheme,
        continuity_id=continuity_id,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
        orthostate_projector=orthostate_projector,
        finality_producer=finality_producer,
    )
    driver.bind_gateway(gateway)
    return inbox, driver


class _ReplayStage:
    """A genuinely side-effect-free stand-in for a REAL commitment-flow ``Stage``, used ONLY by
    the boot-time replay core (independent review finding #2, 2026-09-09).

    **The bug this fixes.** The replay core factory used to receive the SAME ``stages`` dict the
    live core uses. ``sink=NullEvidenceSink()`` on the replay ``EngineCore`` only silences the
    engine's OWN evidence sink — every REAL stage (the step-4 approval stage, the step-9 RCL
    commit, etc.) carries its OWN sink bound to the real durable
    :class:`~tos_runtime.evidence.store.SqliteEvidenceStore`, independent of what the engine's own
    sink is. Replaying with the real stages therefore RE-RAN every real stage's side effects on
    every boot: a single-use Independent Approval got re-consumed, risk decisions got re-written,
    evidence kinds like ``IAP_CONSUMPTION``/``ARE_DECISION``/``AFG_DECISION``/``ARE_SNAPSHOT``/
    ``RCL_APPEND`` all doubled per replayed tick (measured directly: two replayed ``DECISION_TICK``
    events produced a ``+2`` delta on each of those five kinds).

    **Why this is safe for the outcome-digest comparison replay exists to make.**
    ``EventResult.outcome_digest`` (``tos/src/tos/engine/core.py``) is ALWAYS the DECISION
    PIPELINE's own :attr:`~tos.engine.pipeline.PipelineResult.outcome_digest`
    (``EventResult.pipeline``), computed by ``run_decision_pipeline`` INSIDE
    ``EngineCore._run_entries`` — strictly BEFORE ``run_commitment_flow`` (the 19-step
    stage-by-stage flow this class stands in for) is even called. Swapping every injected stage
    for one that returns a restrictive ``UNKNOWN`` verdict therefore cannot change the digest
    replay compares: the pipeline result the digest is read off is already fixed by the time the
    first stage would run. It only changes what happens AFTER that point — and
    ``StageOutcome.UNKNOWN`` is a positive-admit-gate stop (``run_commitment_flow``'s own rule 2:
    "deny / UNKNOWN / missing / absent / raised ⇒ immediate stop"), so the flow halts at the very
    FIRST injected step (right after step 1, the already-emitted proposal) — no real stage's
    ``__call__`` ever runs during replay, so none of their bound sinks ever fire, and no ledger
    mutation (``ledger.bind_attempt``/``commit_unbound`` — both gated behind an ``ADMIT`` verdict
    this stand-in never returns) happens either. Runtime tests (``test_compose_root.py``) verify
    this claim directly: the five evidence-kind counts above stay byte-identical across a reboot
    that reaches a real hand-off.

    ``authority_class=NON_AUTHORITATIVE_PROVISIONAL`` is honest — this stand-in never held real
    authority in the first place, whichever real stage's slot it fills in for.
    """

    def __call__(self, request: StageRequest) -> StageVerdict:
        """Return a restrictive ``UNKNOWN`` verdict for ``request.step`` — no I/O, no mutation."""
        return StageVerdict(
            step=request.step,
            outcome=StageOutcome.UNKNOWN,
            authority_class=StageAuthorityClass.NON_AUTHORITATIVE_PROVISIONAL,
            reason=(
                "tos_runtime boot-time replay stand-in (independent review finding #2) — no "
                "I/O, no mutation; halts the flow at the first injected step so no real stage's "
                "bound evidence sink or ledger mutation ever fires during replay"
            ),
        )


def verify_replay_or_halt(
    *,
    inbox: SqliteEventInbox,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    registry: StrategyRegistry,
    stages: dict[CommitmentStep, Stage],
    configuration: EngineConfiguration,
    scheme: CanonicalizationScheme,
    window_events: int,
) -> ReplayVerdict:
    """Build the side-effect-free replay core factory and run the boot-time replay check.

    Split out of ``_wiring.py``'s ``_finalize`` purely for the size budget (its own function-size
    limit) — the replay core factory closes over ``registry``/``configuration`` the SAME way
    ``_finalize`` builds its real ``core``, but with ``transmit=None``, a discarding sink, AND
    (independent review finding #2) a genuinely side-effect-free :class:`_ReplayStage` standing in
    for every real injected stage — NEVER the real ``stages`` dict, which would re-run every real
    stage's own bound evidence sink and ledger mutation on every boot (see :class:`_ReplayStage`'s
    own docstring for the full measurement and why the outcome-digest comparison is unaffected).
    """

    def _replay_core_factory() -> EngineCore:
        replay_stage = _ReplayStage()
        return EngineCore(
            registry=registry,
            stages=dict.fromkeys(stages, replay_stage),
            configuration=configuration,
            # TOS Phase 3 Wave 2 Lane B-R: the replay core gets its OWN
            # side-effect-free preconditions stand-in — never the real
            # RuntimeCoordinatorPreconditions, which would re-evaluate TODAY's
            # epoch/authorization state instead of reproducing the live run's
            # already-recorded admission (see _ReplayPreconditions's own
            # docstring). transport_nature is omitted (None) — the stand-in
            # ignores it unconditionally.
            preconditions=_ReplayPreconditions(),
            transmit=None,
            sink=NullEvidenceSink(),
            scheme=scheme,
        )

    return verify_engine_replay_or_halt(
        inbox,
        evidence_store,
        emergency_log,
        _replay_core_factory,
        scheme=scheme,
        window_events=window_events,
    )


@dataclass
class WiredEngine:
    """Every artifact :func:`wire_engine_and_driver` assembles — handed straight into
    :class:`~tos_runtime.compose._types.ComposedRuntime`'s matching fields by ``_finalize``.
    """

    gateway: BrokerEgressGateway
    transport: SyntheticPaperTransport
    core: EngineCore
    resolved_registry: StrategyRegistry
    inbox: SqliteEventInbox
    driver: EngineDriver


def _build_preconditions(
    authority_epoch_service: SafetyAuthorityEpochService, live_authorization_state: str
) -> RuntimeCoordinatorPreconditions:
    """The live core's RFC-002 §10.7 Coordinator positive gates (design #31 §9-10; plan §2.1).

    Read fresh on every ``DECISION_TICK`` — never a runtime-authored currentness/authorization
    comparison; both delegate to the kernel's own ``tos.authority``/``tos.liveauth`` predicates
    (see :class:`RuntimeCoordinatorPreconditions`'s own docstring).

    Args:
        authority_epoch_service: The already-composed
            :class:`~tos_runtime.authority.epoch.SafetyAuthorityEpochService` for this runtime's
            authority domain.
        live_authorization_state: The caller-resolved, already-validated restricted-live
            governance posture (``CoordinatorPreconditionsConfig.live_authorization_state``).
    """
    return RuntimeCoordinatorPreconditions(
        epoch_service=authority_epoch_service,
        live_authorization_state=live_authorization_state,
    )


def wire_engine_and_driver(
    *,
    data_dir: Path,
    context_resolver: ComposeContextResolver,
    identity: RuntimeIdentity,
    evidence_store: SqliteEvidenceStore,
    emergency_log: EmergencyAppendLog,
    projection: SqliteReservationProjectionReader,
    stages: dict[CommitmentStep, Stage],
    configuration: EngineConfiguration,
    registry: StrategyRegistry | None,
    scheme: CanonicalizationScheme,
    continuity_id: str,
    monotonic_source: MonotonicSource,
    max_send_result_wait_ms: int,
    authority_epoch_service: SafetyAuthorityEpochService,
    live_authorization_state: str,
    finality_config: FinalityConfig,
) -> WiredEngine:
    """The gateway + ``EngineCore`` + durable inbox/driver wiring — split out of ``_wiring.py``'s
    ``_finalize`` purely for the size budget; no behavioural difference from having this inline
    there. Builds, in order: the obligation recorder + gateway evidence sink -> the synthetic
    transport + ``BrokerEgressGateway`` -> the resolved registry + engine evidence sink ->
    the ``RuntimeCoordinatorPreconditions`` (design #31 §9-10; plan §2.1, via
    :func:`_build_preconditions`) -> ``EngineCore`` (steps 2-11/13/14 + this gateway as
    ``transmit`` + the Coordinator gate) -> the durable inbox +
    :class:`~tos_runtime.engine.driver.EngineDriver`, bound to both (TOS Phase 3 Wave 1 Lane A-R,
    plan §1.1: "engine core wired first, driver last").

    Args:
        authority_epoch_service: Forwarded to :func:`_build_preconditions` — see its own
            docstring.
        live_authorization_state: Forwarded to :func:`_build_preconditions` — see its own
            docstring.
        finality_config: Forwarded to :func:`build_engine_driver` — see its own docstring
            (team-lead CR-4 dispatch, plan §2.2).
    """
    # Kernel round #1 §3 (lane B): the reservation id bound to any attempt in THIS compose root
    # is always this same formula — the SAME one _build_realized_stages' AtomicCommitStage
    # reservation_id_provider and _build_currentness_stages' TransmissionCapabilityStage
    # context_reader already use — because this compose root wires exactly one InstrumentKey
    # (context_resolver.instrument_key) for its whole process lifetime (see
    # tos_runtime.rcl.obligation's own module docstring, "Reservation-id resolution").
    instrument_key = context_resolver.instrument_key
    obligation_recorder = CapacityObligationRecorder(
        store=evidence_store,
        emergency_log=emergency_log,
        projection=projection,
        reservation_id_resolver=lambda _attempt_id: (
            f"resv-{instrument_key.account}-{instrument_key.instrument}"
        ),
    )
    # Independent review finding #8: wiring on_refusal here means a SEND_REFUSED whose
    # obligation this recorder cannot verify (e.g. the rcl projection's sqlite read fails) now
    # raises out of GatewayEvidenceSinkAdapter.record and transitively out of
    # BrokerEgressGateway.__call__ — deliberate, fail-closed (sinks.py's own module + record()
    # docstrings carry the full rationale).
    gateway_sink = GatewayEvidenceSinkAdapter(
        evidence_store, runtime_identity=identity, on_refusal=obligation_recorder
    )
    transport = SyntheticPaperTransport(
        SyntheticFillPolicy(fill_numerator=1, fill_denominator=1, lot_size=Decimal("1"))
    )
    gateway = BrokerEgressGateway(
        contexts=context_resolver, transport=transport, sink=gateway_sink
    )

    resolved_registry = registry if registry is not None else StrategyRegistry()
    engine_sink = EngineEvidenceSinkAdapter(evidence_store, runtime_identity=identity)
    preconditions = _build_preconditions(
        authority_epoch_service, live_authorization_state
    )
    core = EngineCore(
        registry=resolved_registry,
        stages=stages,
        configuration=configuration,
        preconditions=preconditions,
        transmit=gateway,
        transport_nature=context_resolver.transport_nature,
        sink=engine_sink,
    )

    inbox, driver = build_engine_driver(
        data_dir=data_dir,
        core=core,
        gateway=gateway,
        evidence_store=evidence_store,
        emergency_log=emergency_log,
        scheme=scheme,
        continuity_id=continuity_id,
        monotonic_source=monotonic_source,
        max_send_result_wait_ms=max_send_result_wait_ms,
        finality_config=finality_config,
        authority_epoch_current=preconditions.authority_epoch_current,
    )
    return WiredEngine(
        gateway=gateway,
        transport=transport,
        core=core,
        resolved_registry=resolved_registry,
        inbox=inbox,
        driver=driver,
    )
