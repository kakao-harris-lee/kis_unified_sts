"""Finality release-consumer compose wiring (TOS Phase 5 W2-R; plan §10 row ①③).

Called from :func:`~tos_runtime.compose.root.compose_paper_runtime` immediately after
``_finalize`` returns a fully-wired :class:`~tos_runtime.compose._types.ComposedRuntime` —
mirrors :mod:`tos_runtime.compose._recovery_wiring`'s own precedent (see that module's own
docstring "Why a separate module, not a block inside ``_finalize``"): the durable RCL log /
evidence store / inbox / time service / instrument key this consumer depends on are ALL already
public fields on that runtime, and ``_wiring.py``'s own size-budget ceiling
(``config/tos_size_budget.yaml`` — registered at 1197 lines) must not grow for this wave (plan
§4's own "``_wiring.py``는 성장 금지"), so this module reaches ``ComposedRuntime``'s already-
public surface — and attaches the built consumer via
:meth:`~tos_runtime.engine.driver.EngineDriver.bind_release_consumer` — rather than adding a new
parameter to :func:`~tos_runtime.compose._engine_wiring.wire_engine_and_driver`/
:func:`~tos_runtime.compose._engine_wiring.build_engine_driver`.

**Independently RE-LOADS ``finality.yaml`` for ``release_proof_wait_ms``** — the SAME accepted
pattern :func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier` already uses,
re-loading ``engine_driver.yaml`` a second time in a second wiring module (that function's own
body). Config loading is cheap and idempotent, so a second load in a second wiring module is a
duplication of a read, never a duplication of authority — ``_wiring.py``'s own ``_finalize``
loads the SAME file once already for :class:`~tos_runtime.posttrade.finality.SyntheticFinalityProducer`'s
own construction; both loads see the identical operator-approved file.

**Reuses :mod:`tos_runtime.recovery.reconciliation`'s own private factories** —
``_build_reconciliation_service`` (the SAME ``reservation_id_for_attempt`` bridge
:mod:`tos_runtime.recovery.reconciliation`'s own module docstring "second identity gap" section
describes) and ``_build_freshness_marker`` — never a second, possibly-diverging construction
(team-lead directive, plan §10 row ①③: "construct the service EXACTLY the way
``recovery/reconciliation.py:216`` does").

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``pathlib``) +
``tos.canonical`` + ``tos_runtime.*`` only. No ``shared.*``.
"""

from __future__ import annotations

from pathlib import Path

from tos.canonical import CanonicalizationScheme

from tos_runtime.compose._dimension_readers import _PostTradeDimensionState
from tos_runtime.compose._types import ComposedRuntime
from tos_runtime.posttrade.config import load_finality_config
from tos_runtime.posttrade.finality import SyntheticFinalityProducer
from tos_runtime.posttrade.release_consumer import FinalityReleaseConsumer
from tos_runtime.rcl.projection import SqliteReservationProjectionReader

# TOS Phase 5 W1 factory reuse (team-lead directive, plan §10 row ①③) — see this module's own
# docstring "Reuses tos_runtime.recovery.reconciliation's own private factories".
from tos_runtime.recovery.reconciliation import (  # noqa: SLF001
    _build_reconciliation_service,
)
from tos_runtime.time.sources import MonotonicSource

__all__ = ["FINALITY_CONFIG_NAME", "apply_release_wiring"]

#: The config file name (mirrors ``_wiring.py``'s own ``_FINALITY_CONFIG_NAME`` literal — module
#: docstring's "independently re-loads" section).
FINALITY_CONFIG_NAME = "finality.yaml"


def apply_release_wiring(
    runtime: ComposedRuntime,
    *,
    config_dir: Path,
    scheme: CanonicalizationScheme,
    monotonic_source: MonotonicSource,
    post_trade_dimension_state: _PostTradeDimensionState,
) -> ComposedRuntime:
    """Build the TOS Phase 5 W2-R :class:`~tos_runtime.posttrade.release_consumer
    .FinalityReleaseConsumer` and attach it to ``runtime.driver``.

    Args:
        runtime: The just-``_finalize``d :class:`~tos_runtime.compose._types.ComposedRuntime`
            (mutated in place via ``runtime.driver.bind_release_consumer`` and returned) — its
            ``.driver`` is still real at the call site :func:`~tos_runtime.compose.root
            .compose_paper_runtime` uses (this wiring runs BEFORE
            :func:`~tos_runtime.compose._recovery_wiring.apply_recovery_barrier`, which may
            later set ``.driver`` to ``None`` on a HOLD verdict — attaching a consumer to a
            driver that is then detached is harmless: a detached driver's
            ``core.handle``/``run_once`` is never reachable at all, so the consumer bound to it
            never runs either).
        config_dir: The SAME directory ``compose_paper_runtime`` was given — read again here
            only for ``finality.yaml``'s own ``release_proof_wait_ms`` (module docstring).
        scheme: The SAME canonicalization scheme this runtime composed with.
        monotonic_source: The SAME injected monotonic clock this runtime composed with (module
            docstring — never a fresh ``ProcessMonotonicSource()``, which would desynchronize
            this consumer's obligation-expiry clock from the driver's own timeout clock in a
            test that injects a fake one).
        post_trade_dimension_state: The POST_TRADE currentness dimension reader's late-bound
            cell (Phase 5 W3.2, plan §2 decision 5 —
            :class:`~tos_runtime.compose._dimension_readers._PostTradeDimensionState`) —
            filled in with the built consumer below, or left ``None`` (module docstring's
            "consumer not wired" case) when ``runtime.driver`` is already ``None``.

    Returns:
        ``runtime`` itself. A no-op (returns ``runtime`` unchanged) when ``runtime.driver`` is
        already ``None`` — nothing to attach a consumer to, and
        ``post_trade_dimension_state.consumer`` stays ``None``.
    """
    if runtime.driver is None:
        return runtime
    finality_config = load_finality_config(config_dir / FINALITY_CONFIG_NAME)
    instrument_key = runtime.context_resolver.instrument_key
    recon_service = _build_reconciliation_service(
        runtime.rcl_log,
        runtime.evidence_store,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
    )
    consumer = FinalityReleaseConsumer(
        rcl_log=runtime.rcl_log,
        projection=SqliteReservationProjectionReader(runtime.rcl_log),
        evidence_store=runtime.evidence_store,
        inbox=runtime.inbox,
        recon_service=recon_service,
        time_service=runtime.time_service,
        finality_producer=SyntheticFinalityProducer(
            config=finality_config, scheme=scheme
        ),
        scheme=scheme,
        monotonic_source=monotonic_source,
        account=instrument_key.account,
        instrument=instrument_key.instrument,
        release_proof_wait_ms=finality_config.release_proof_wait_ms,
    )
    runtime.driver.bind_release_consumer(consumer)
    post_trade_dimension_state.consumer = consumer
    return runtime
