"""``compose_paper_runtime`` — the ONE composition root (design #40 D1.1;
slice plan §4 item 1).

"composition root 는 `tos_runtime.compose` 단 하나 — 커널 Protocol 심을
구현체와 한 자리에서 결선한다." This module is that one place. It wires, in
the stated order (slice plan §4):

    identity -> release admission (refuse => raise, nothing constructed) ->
    custody -> evidence store (``FileKeyProvider``) -> emergency log
    -> Trustworthy Time service (``start()``) -> RCL log (``acquire_epoch`` +
    generation seed) -> Safety Authority epoch service -> Intent Registry
    -> risk services (Aggregate Risk Authority + Action Flow Governor)
    -> currentness (assembler + proof issuer) -> ``EngineCore`` (real
    ``Stage``s for steps 4, 6-10, 13, 14; the kernel's OWN existing
    implementations for steps 2, 3, 5, 11) -> ``BrokerEgressGateway`` (the
    compose-root ``SendBoundaryContext`` resolver,
    :mod:`tos_runtime.compose.context`) -> ``SyntheticPaperTransport``
    -> the TOS Phase 5 W1 recovery barrier
    (:func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier` — see
    that module's own docstring for why this runs here, right after ``_finalize``,
    rather than literally "before the engine driver is wired": the durable inbox
    the barrier reads does not exist any earlier in this function).

    **Release admission is moved ahead of custody/evidence/RCL, reported
    deviation from the plan's literal listed order.** See the "identity +
    release admission FIRST" comment inside this function for why: the
    gate's only real input is this process's own
    :class:`~tos.workload.RuntimeIdentity` (pure computation, no I/O) plus
    the static ``release.yaml`` snapshot — it depends on neither the
    evidence store nor the RCL log — and the compose end-to-end test's
    scenario 7 requires "release admission refusal ⇒ compose raises before
    any service starts (assert no sqlite files created)", which is only
    achievable if the gate runs before any sqlite file is opened. The
    listed order's actual intent — "nothing past this gate is
    constructed" — is preserved exactly; only its position relative to
    custody/evidence/RCL construction moved earlier.

**Steps 2/3/5/11 reuse the kernel's own, already-shipped Order Construction
stages** (``tos.egressgw.{OrderConstructionStage,VenueConstraintStage,
EconomicEffectStage,ConformanceProofStage}`` — the same four classes
``tos/tests/slice/_slice_fixtures.py::construction_stages`` wires for the
kernel's own end-to-end test). They are **not** stand-ins
(``tos.engine.standins.ProvisionalStandIn``): each is backed by a real,
already-shipped kernel predicate call (design #34 §3.2), so using them here
keeps this composition's own ``NON_AUTHORITATIVE_PROVISIONAL`` count at
exactly zero for every one of steps 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14 —
see the compose end-to-end test's ``test_stand_in_zero_across_the_wired_steps``.

**Order-construction facts are genuinely per-strategy configuration** (an
Authorized Construction Envelope, a sizing bound, a venue policy/snapshot/
decision, an order shape + its constraints) — there is no Phase-2 runtime
that derives these (Order Construction Policy governance, RFC-002 §9.1:553,
is a separate, still-unratified artifact; a real venue-constraint service is
Phase 4+). :class:`ConstructionConfig` is therefore an explicit, caller-
supplied parameter group (mirroring how ``_slice_fixtures.py`` injects the
same facts for the kernel's own e2e test) rather than a fifth positional
argument invented to look like it comes from a file that does not exist yet.

Firewall (tools/tos_firewall_check.py R1, runtime scope): stdlib + ``tos.*``
+ ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from tos.canonical import EV_L1_PROVISIONAL_VERSION, get_scheme
from tos.engine import (
    StageRequest,
    StrategyRegistry,
)

from tos_runtime.compose._finalize_wiring import _finalize
from tos_runtime.compose._recovery_wiring import apply_recovery_barrier
from tos_runtime.compose._release_wiring import apply_release_wiring
from tos_runtime.compose._request_digest import KisWireCodecDigest
from tos_runtime.compose._transport_wiring import TransportKind
from tos_runtime.compose._types import (
    ComposedRuntime,
    ConstructionConfig,
    ReleaseAdmissionRefused,
)
from tos_runtime.compose._wiring import (
    _boot_services,
    _build_construction_stages,
    _build_context_resolver,
    _build_realized_stages,
    _build_stage_map,
)
from tos_runtime.risk.aggregate import (
    AggregateRiskDecisionInputs,
)
from tos_runtime.risk.flow import ActionFlowDecisionInputs
from tos_runtime.time.sources import (
    MonotonicSource,
)

__all__ = [
    "ComposedRuntime",
    "ConstructionConfig",
    "ReleaseAdmissionRefused",
    "TransportKind",
    "compose_paper_runtime",
]

_SCHEME = get_scheme(EV_L1_PROVISIONAL_VERSION)

#: Config file names expected directly under ``config_dir`` (each shaped like
#: its ``tos/runtime/config/*.example.yaml`` counterpart).
_TIME_CONFIG_NAME = "time.yaml"
_AUTHORITY_CONFIG_NAME = "authority.yaml"
_RISK_CONFIG_NAME = "risk.yaml"
_CURRENTNESS_CONFIG_NAME = "currentness.yaml"
_RELEASE_CONFIG_NAME = "release.yaml"

#: Where operator-authored Independent Approval decisions live, keyed by
#: proposal digest (``tos_runtime.authority.iap`` module docstring:
#: "approvals/<proposal_digest>.yaml").
_APPROVALS_DIRNAME = "approvals"


def compose_paper_runtime(
    config_dir: Path,
    data_dir: Path,
    custody_root: Path,
    environment_label: str,
    *,
    construction: ConstructionConfig,
    aggregate_risk_inputs_provider: Callable[
        [StageRequest], AggregateRiskDecisionInputs | None
    ],
    action_flow_inputs_provider: Callable[
        [StageRequest], ActionFlowDecisionInputs | None
    ],
    registry: StrategyRegistry | None = None,
    authority_domain: str = "trading",
    continuity_id: str = "paper-runtime",
    monotonic_source: MonotonicSource | None = None,
    allow_no_strategies: bool = False,
    transport_kind: TransportKind = TransportKind.SYNTHETIC,
) -> ComposedRuntime:
    """Wire the whole Phase 2 paper-runtime service chain, in order (module
    docstring: exact order + every reported deviation).

    Args:
        config_dir: Directory holding every ``*.yaml`` config (every named-TBD filled).
        data_dir: Directory for the RCL log / evidence store / emergency log.
        custody_root: The D4 custody directory.
        environment_label: Boot-argument environment label (never ``os.environ`` — D1.1).
        construction: Per-strategy Order Construction facts (steps 2/3/5/11) — :class:`ConstructionConfig`.
        aggregate_risk_inputs_provider: Supplies step 6's inputs (``None`` => restrictive UNKNOWN).
        action_flow_inputs_provider: Supplies step 7's inputs, analogously.
        registry: An injected strategy registry — mutually exclusive with a populated strategies directory.
        authority_domain: The Safety Authority epoch's governed domain name.
        continuity_id: The ordering-event continuity id.
        allow_no_strategies: ``False`` refuses with neither source (finding #8).
        transport_kind: ``synthetic`` (the default) or ``kis-mock`` (TOS KIS MOCK transport plan
            T2 lane C — :mod:`tos_runtime.compose._transport_wiring`). Boot refuses when this
            disagrees with the active broker scope's own shape
            (:func:`~tos_runtime.compose._transport_wiring.refuse_transport_scope_mismatch`) or,
            for ``kis-mock``, when the custody principal for either KIS MOCK scope does not match
            the active scope's own principal
            (:func:`~tos_runtime.compose._transport_wiring.refuse_custody_principal_mismatch`).

    Returns:
        The fully wired :class:`ComposedRuntime`.
    Raises:
        ReleaseAdmissionRefused / config or custody exceptions / StrategyRegistryResolutionRefused
        / :class:`~tos_runtime.compose._transport_wiring.TransportWiringError`.
    """
    uid = os.getuid()
    boot = _boot_services(
        config_dir,
        data_dir,
        custody_root,
        environment_label,
        uid,
        authority_domain,
        monotonic_source,
        registry,
        allow_no_strategies,
        transport_kind,
    )

    construction_stages = _build_construction_stages(construction)
    realized = _build_realized_stages(
        infra=boot.infra,
        rcl=boot.rcl,
        risk=boot.risk,
        construction_stages=construction_stages,
        construction=construction,
        aggregate_risk_inputs_provider=aggregate_risk_inputs_provider,
        action_flow_inputs_provider=action_flow_inputs_provider,
        custody_root=custody_root,
        environment_label=environment_label,
        uid=uid,
    )
    # Late-bind the ACTION_FLOW dimension reader's cell now step 9's VerdictRecorder exists.
    boot.risk.action_flow_dimension_state.step9_recorder = realized.step9_recorder
    stages = _build_stage_map(construction_stages, realized)

    # T2 lane C: a kis-mock boot binds the genuine KIS wire-codec digest into the context
    # resolver (closing the T2 lane A gap for THIS wiring path) — synthetic keeps the stand-in.
    request_bytes_digest_source = (
        KisWireCodecDigest(
            field_map=boot.transport_config.field_map,
            static_body_fields=boot.transport_config.static_body_fields,
        )
        if boot.transport_config is not None
        else None
    )
    context_resolver = _build_context_resolver(
        construction_stages=construction_stages,
        realized=realized,
        flow_governor=boot.risk.flow_governor,
        currentness_assembler=boot.risk.currentness_assembler,
        proof_issuer=boot.risk.proof_issuer,
        pending_dimension_specs=boot.risk.pending_dimension_specs,
        egress_attestations=boot.risk.egress_attestations,
        egress_coordinates=boot.egress_coordinates,
        broker_scopes=boot.broker_scopes,
        instance_document=boot.instance_document,
        construction=construction,
        environment_label=environment_label,
        continuity_id=continuity_id,
        request_bytes_digest_source=request_bytes_digest_source,
    )

    composed = _finalize(
        config_dir=config_dir,
        data_dir=data_dir,
        infra=boot.infra,
        rcl=boot.rcl,
        risk=boot.risk,
        construction_stages=construction_stages,
        realized=realized,
        stages=stages,
        context_resolver=context_resolver,
        identity=boot.identity,
        registry=boot.registry,
        release_admitted=boot.release_admitted,
        continuity_id=continuity_id,
        broker_scopes=boot.broker_scopes,
        instance_document=boot.instance_document,
        transport_kind=transport_kind,
        transport_config=boot.transport_config,
    )
    # TOS Phase 5 W2-R (plan §10 row ①③) — attach the finality release consumer BEFORE the
    # recovery barrier runs (see apply_release_wiring's own docstring for why running before a
    # possible driver detach is harmless).
    composed = apply_release_wiring(
        composed,
        config_dir=config_dir,
        scheme=_SCHEME,
        monotonic_source=boot.infra.monotonic_source,
    )
    return apply_recovery_barrier(
        composed,
        config_dir=config_dir,
        data_dir=data_dir,
        custody_root=custody_root,
        scheme=_SCHEME,
    )
