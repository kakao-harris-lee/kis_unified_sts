"""Transport-kind selection + KIS MOCK compose wiring (TOS KIS MOCK transport plan T2 lane C —
compose wiring, ``docs/plans/2026-09-10-tos-kis-mock-transport-plan.md`` §4 row T2, §8 "T2 must").

**What this module owns.** Everything ``compose --transport {synthetic,kis-mock}`` needs beyond
what T1 (the adapter package, :mod:`tos_runtime.transport.kis_mock`) and T2 lanes A/B (the codec
digest binding, :mod:`tos_runtime.compose._request_digest`; the Coordinator non-live admission,
:mod:`tos_runtime.compose._nonlive_admission`) already landed:

1. :class:`TransportKind` — the two-member closed vocabulary ``compose_paper_runtime``'s new
   ``transport_kind`` keyword accepts.
2. :func:`load_transport_config` — loads ``kis_mock_transport.yaml`` for ``kis-mock`` (``None``
   for ``synthetic``), resolving the host-seal facts (plan §2 decision 5) from the Broker
   Capability Profile INSTANCE documents rather than trusting the config file to name its own
   host.
3. :func:`refuse_transport_scope_mismatch` / :func:`refuse_custody_principal_mismatch` — the two
   boot-time consistency refusals that keep the transport kind and the active broker scope (and
   its custody principal) from ever disagreeing about whether this runtime reaches a real broker.
4. :func:`resolve_transport_boot` — the single call site :mod:`tos_runtime.compose._wiring` uses
   to run all of the above during boot, kept to ONE call so that module's own size budget stays
   net-negative (its own module docstring's constraint).
5. :class:`SealRegistry` — the ``SendSeal`` capture/lookup seam between the kernel gateway's own
   ``SEND_SEALED`` evidence record and :class:`~tos_runtime.transport.kis_mock.adapter.
   KisMockTransport`'s injected ``SealLookup`` port.
6. :func:`build_transport` — constructs either transport (the ``SyntheticPaperTransport``
   construction moved out of :mod:`tos_runtime.compose._engine_wiring` here unchanged, module
   docstring item 2 below, or a fully-wired ``KisMockTransport``).

**Why the scope/transport consistency check does not re-author the tuple check.** Condition 3 of
:func:`~tos_runtime.compose._nonlive_admission.nonlive_broker_consuming_admitted` ("every
capability tuple MOCK-shaped under BROKER_SIMULATION") is EXACTLY the shape a ``kis-mock``
transport's active scope must have — :func:`refuse_transport_scope_mismatch` imports and reuses
that module's own private ``_capability_tuples_mock_simulation`` helper directly rather than
re-typing the same five-line predicate a second time (two independently-maintained copies of a
security-relevant condition is worse than one shared one, even a private one).

**Custody-manifest principal, no substitution.** :class:`~tos_runtime.custody.file_custody.
CustodyManifest` performs NO ``{environment_label}`` token substitution of its own (unlike
:func:`~tos_runtime.brokercap.scopes.load_broker_scopes`, which does) — see
``custody.manifest.example.yaml``'s own updated comment. :func:`refuse_custody_principal_mismatch`
therefore compares the manifest's OWN (already-concrete, per-deployment) principal string against
``active_scope.principal`` (already ``{environment_label}``-substituted by the broker-scopes
loader) byte-for-byte; a real deployment's manifest must write the concrete substituted value.

Firewall (``tools/tos_firewall_check.py`` R1, runtime scope): stdlib (``dataclasses``, ``enum``,
``pathlib``) + ``tos.brokeradapter``/``tos.egressgw`` + ``tos_runtime.brokercap``/
``tos_runtime.custody``/``tos_runtime.evidence``/``tos_runtime.time``/``tos_runtime.transport.
kis_mock``/``tos_runtime.workload`` (transitively, via ``tos.workload``) only. No ``shared.*``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any

from tos.brokeradapter import SyntheticFillPolicy, SyntheticPaperTransport, Transport
from tos.egressgw import SendSeal
from tos.egressgw.records import GatewayEvidenceRecord
from tos.workload import RuntimeIdentity

from tos_runtime.brokercap.instance import InstanceDocument, load_instance_documents
from tos_runtime.brokercap.scopes import BrokerScope, BrokerScopesConfig
from tos_runtime.brokercap.scopes import transport_nature as scope_transport_nature
from tos_runtime.compose._nonlive_admission import _capability_tuples_mock_simulation
from tos_runtime.custody.file_custody import FileCustody
from tos_runtime.custody.ports import CredentialCustody
from tos_runtime.evidence.store import SqliteEvidenceStore
from tos_runtime.time.sources import MonotonicSource
from tos_runtime.transport.kis_mock.adapter import EvidenceRecorder, KisMockTransport
from tos_runtime.transport.kis_mock.client import build_client
from tos_runtime.transport.kis_mock.config import (
    KisMockTransportConfig,
    load_kis_mock_transport_config,
)

__all__ = [
    "KIS_MOCK_TRANSPORT_CONFIG_NAME",
    "SealRegistry",
    "TransportBootResult",
    "TransportKind",
    "TransportWiringError",
    "build_transport",
    "load_transport_config",
    "refuse_custody_principal_mismatch",
    "refuse_transport_scope_mismatch",
    "resolve_transport_boot",
]

#: The canonical config-file name under a compose ``config_dir`` for the KIS MOCK transport
#: config (mirrors ``_engine_wiring.ENGINE_DRIVER_CONFIG_NAME``'s own convention).
KIS_MOCK_TRANSPORT_CONFIG_NAME = "kis_mock_transport.yaml"

#: The two custody scopes a ``kis-mock`` boot requires (plan §2 decision 4) — kept as a single
#: source of truth here rather than repeating the literal pair at every call site.
_KIS_MOCK_CUSTODY_SCOPES = ("kis_mock.app_key", "kis_mock.app_secret")

#: The Broker Capability Profile INSTANCE document environment name every KIS MOCK boot's host
#: seal excludes (plan §2 decision 5) — the same literal ``environment_binding.BROKER_PRODUCTION``
#: maps to everywhere else in this codebase (``broker_scopes.example.yaml``).
_REAL_ENVIRONMENT = "REAL_PROD"


class TransportKind(StrEnum):
    """The closed vocabulary ``compose --transport`` accepts (T2 lane C)."""

    SYNTHETIC = "synthetic"
    KIS_MOCK = "kis-mock"


class TransportWiringError(Exception):
    """A transport-kind / scope-consistency / custody-principal / host-seal fact could not be
    proven at boot — fail-closed, never a silent default (module docstring)."""


# ===========================================================================
# Transport config loading — host seal (plan §2 decision 5)
# ===========================================================================


def _document_for_environment(
    documents: tuple[InstanceDocument, ...], environment: str
) -> InstanceDocument | None:
    """The single ``documents`` entry whose own ``environment`` equals ``environment``, or
    ``None`` when zero or more than one match — never an ambiguous pick."""
    matches = [
        document for document in documents if document.environment == environment
    ]
    return matches[0] if len(matches) == 1 else None


def load_transport_config(
    kind: TransportKind,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
) -> KisMockTransportConfig | None:
    """Load ``kis_mock_transport.yaml`` for ``kis-mock`` (``None`` for ``synthetic``).

    The two REST-base host-seal facts (plan §2 decision 5) come from the Broker Capability
    Profile INSTANCE documents, never the config file itself: this function loads EVERY document
    at ``broker_scopes.instance_path`` (:func:`~tos_runtime.brokercap.instance
    .load_instance_documents`), takes the active scope's own bound document (its
    ``instance.environment``) as the MOCK fact and the fixed :data:`_REAL_ENVIRONMENT` document as
    the REAL fact, and passes both into
    :func:`~tos_runtime.transport.kis_mock.config.load_kis_mock_transport_config` along with
    ``codec_bound=True`` — this module's own attestation that :func:`build_transport` (via this
    module's caller) actually binds
    :class:`~tos_runtime.compose._request_digest.KisWireCodecDigest` into the compose context
    resolver for a ``kis-mock`` boot (T2 lane A's own gate).

    Args:
        kind: The selected transport kind.
        config_dir: The compose config directory (``kis_mock_transport.yaml`` lives directly
            under it).
        broker_scopes: The already-loaded scope table — ``active_scope.instance`` and
            ``instance_path`` supply the two host-seal facts.

    Returns:
        ``None`` for ``synthetic``; the fully-valued config for ``kis-mock``.

    Raises:
        TransportWiringError: ``kind`` is ``kis-mock`` and the active scope declares no
            ``instance`` block, ``broker_scopes.instance_path`` is unset, the MOCK or REAL
            document cannot be uniquely resolved, or either document's own ``rest_base`` is
            unknown — the host seal cannot be proven without every one of these facts.
        BrokerInstanceConfigError: The instance file cannot be loaded (propagated, not swallowed).
        KisMockTransportConfigError: The transport config itself fails fail-closed validation
            (propagated, not swallowed).
    """
    if kind is TransportKind.SYNTHETIC:
        return None
    scope = broker_scopes.active_scope
    if scope.instance is None or broker_scopes.instance_path is None:
        raise TransportWiringError(
            "kis-mock transport requires the active scope's own INSTANCE binding "
            f"({scope.name!r}.instance) and broker_scopes.instance_path — the host seal "
            "cannot be proven without both; refusing to boot"
        )
    documents = load_instance_documents(broker_scopes.instance_path)
    mock_document = _document_for_environment(documents, scope.instance.environment)
    real_document = _document_for_environment(documents, _REAL_ENVIRONMENT)
    if mock_document is None or mock_document.rest_base is None:
        raise TransportWiringError(
            f"kis-mock transport: no unique INSTANCE document for environment "
            f"{scope.instance.environment!r} with a known rest_base at "
            f"{broker_scopes.instance_path} — refusing to boot"
        )
    if real_document is None or real_document.rest_base is None:
        raise TransportWiringError(
            f"kis-mock transport: no unique INSTANCE document for environment "
            f"{_REAL_ENVIRONMENT!r} with a known rest_base at {broker_scopes.instance_path} "
            "— the REAL host cannot be excluded without it; refusing to boot"
        )
    return load_kis_mock_transport_config(
        config_dir / KIS_MOCK_TRANSPORT_CONFIG_NAME,
        instance_mock_rest_base=mock_document.rest_base,
        instance_real_rest_base=real_document.rest_base,
        codec_bound=True,
    )


# ===========================================================================
# Boot-time consistency refusals
# ===========================================================================


def refuse_transport_scope_mismatch(
    kind: TransportKind, broker_scopes: BrokerScopesConfig
) -> None:
    """Refuse boot when ``kind`` and the active scope disagree about whether this runtime reaches
    a real broker (plan §2 decisions 5/7 — one source of truth).

    ``kis-mock`` requires the active scope's own derived
    :class:`~tos.egressgw.TransportNature` to have ``reaches_broker is True`` AND every one of the
    scope's own capability tuples to be MOCK-shaped under ``BROKER_SIMULATION`` — reusing
    :mod:`tos_runtime.compose._nonlive_admission`'s own private tuple-check helper (module
    docstring: "do not re-author the tuple check"), never a second, independently-typed copy of a
    security-relevant condition. ``synthetic`` requires ``reaches_broker is False``.

    Raises:
        TransportWiringError: The active scope's shape does not match ``kind``.
    """
    scope = broker_scopes.active_scope
    nature = scope_transport_nature(scope)
    if kind is TransportKind.KIS_MOCK:
        if nature.reaches_broker is not True or not _capability_tuples_mock_simulation(
            scope
        ):
            raise TransportWiringError(
                f"kis-mock transport requires active scope {scope.name!r} to be "
                "broker-reaching with every capability tuple MOCK-shaped under "
                "BROKER_SIMULATION — refusing to boot"
            )
    else:
        if nature.reaches_broker is not False:
            raise TransportWiringError(
                f"synthetic transport requires active scope {scope.name!r} to be "
                "non-broker-reaching (reaches_broker is False) — refusing to boot"
            )


def refuse_custody_principal_mismatch(
    kind: TransportKind, custody: FileCustody, active_scope: BrokerScope
) -> None:
    """Refuse boot when a ``kis-mock`` custody scope's own manifest principal does not equal the
    active scope's own principal (plan §2 decision 4 — "one principal names both the credential
    and the route"). A no-op for ``synthetic``.

    Args:
        kind: The selected transport kind.
        custody: The already-constructed :class:`~tos_runtime.custody.file_custody.FileCustody` —
            :meth:`~tos_runtime.custody.file_custody.FileCustody.scope_principal` is used, never
            :meth:`~tos_runtime.custody.file_custody.FileCustody.load` (zero secret I/O for this
            check).
        active_scope: The active broker scope.

    Raises:
        TransportWiringError: Either scope's manifest principal does not equal
            ``active_scope.principal``.
        CustodyScopeNotProvisioned: A ``kis_mock.*`` scope is not provisioned (propagated —
            :data:`~tos_runtime.custody.file_custody.PROVISIONED_SCOPES` must already carry it,
            module docstring).
        CustodyLoadRefused: The manifest does not configure a ``kis_mock.*`` scope (propagated).
    """
    if kind is not TransportKind.KIS_MOCK:
        return
    for scope_name in _KIS_MOCK_CUSTODY_SCOPES:
        principal = custody.scope_principal(scope_name)
        if principal != active_scope.principal:
            raise TransportWiringError(
                f"custody scope {scope_name!r} principal {principal!r} does not equal "
                f"active scope {active_scope.name!r}'s own principal "
                f"{active_scope.principal!r} — one principal must name both the "
                "credential and the route (plan §2 decision 4); refusing to boot"
            )


@dataclass(frozen=True)
class TransportBootResult:
    """:func:`resolve_transport_boot`'s return value.

    Attributes:
        transport_config: The loaded KIS MOCK transport config (``None`` for ``synthetic``).
        extra_config_files: The transport-specific config file(s) boot-integrity attestation
            (:func:`~tos_runtime.compose._boot_integrity.record_operator_attested_inputs`) should
            record a digest row for — empty for ``synthetic``, ``(kis_mock_transport.yaml,)`` for
            ``kis-mock``.
    """

    transport_config: KisMockTransportConfig | None
    extra_config_files: tuple[Path, ...]


def resolve_transport_boot(
    kind: TransportKind,
    config_dir: Path,
    broker_scopes: BrokerScopesConfig,
    custody: FileCustody,
) -> TransportBootResult:
    """The ONE call site :mod:`tos_runtime.compose._wiring` uses during boot for every
    transport-kind fact this module owns (module docstring item 4) — load the config, run both
    consistency refusals, and report which extra file(s) boot-integrity should attest.

    Args:
        kind: The selected transport kind.
        config_dir: The compose config directory.
        broker_scopes: The already-loaded scope table.
        custody: The already-constructed custody port.

    Returns:
        The :class:`TransportBootResult`.

    Raises:
        TransportWiringError: Any of the refusals above.
    """
    transport_config = load_transport_config(kind, config_dir, broker_scopes)
    refuse_transport_scope_mismatch(kind, broker_scopes)
    refuse_custody_principal_mismatch(kind, custody, broker_scopes.active_scope)
    extra_config_files = (
        (config_dir / KIS_MOCK_TRANSPORT_CONFIG_NAME,)
        if kind is TransportKind.KIS_MOCK
        else ()
    )
    return TransportBootResult(
        transport_config=transport_config, extra_config_files=extra_config_files
    )


# ===========================================================================
# SendSeal capture — the adapter's injected SealLookup port
# ===========================================================================


@dataclass
class SealRegistry:
    """Captures the kernel gateway's own ``SEND_SEALED`` evidence record's
    :class:`~tos.egressgw.SendSeal`, keyed by ``attempt_id``, and serves it back to
    :class:`~tos_runtime.transport.kis_mock.adapter.KisMockTransport`'s injected ``SealLookup``
    port — SINGLE-USE (:meth:`__call__` pops): a second lookup for the same attempt returns
    ``None``, mirroring the kernel gateway's own at-most-one-send-per-attempt discipline. Never
    reconstructs a seal from any other source.
    """

    _seals: dict[str, SendSeal] = field(default_factory=dict)

    def capture(self, record: GatewayEvidenceRecord) -> None:
        """The :class:`~tos_runtime.evidence.sinks.GatewayEvidenceSinkAdapter` ``on_record``
        observer — captures ``record.send_seal`` for a ``kind == "SEND_SEALED"`` record only; a
        no-op for every other kind (the adapter wires this unconditionally, module docstring).
        """
        if (
            record.kind == "SEND_SEALED"
            and record.attempt_id is not None
            and record.send_seal is not None
        ):
            self._seals[record.attempt_id] = record.send_seal

    def __call__(self, attempt_id: str) -> SendSeal | None:
        """The adapter's own ``SealLookup.__call__`` — single-use (``dict.pop``)."""
        return self._seals.pop(attempt_id, None)


def _evidence_recorder(
    store: SqliteEvidenceStore, runtime_identity: RuntimeIdentity
) -> EvidenceRecorder:
    """Adapt :class:`~tos_runtime.transport.kis_mock.adapter.KisMockTransport`'s injected
    ``EvidenceRecorder`` Protocol (``record(kind, fields)``) onto
    :meth:`~tos_runtime.evidence.store.SqliteEvidenceStore.append` — the same
    ``kind``-as-``record_class`` default every other bare adapter in this compose root uses when
    no operator-configured taxonomy exists (CLAUDE.md "configuration-driven only" — there is no
    such taxonomy for this adapter's own evidence kinds yet). Returns a plain function — a
    structural (``Protocol``) match for ``EvidenceRecorder``'s own ``__call__`` shape, typed
    explicitly as that Protocol (rather than a bare ``Callable``) so mypy resolves the match.
    """

    def _record(kind: str, fields: Mapping[str, Any]) -> None:
        store.append(
            dict(fields),
            kind=kind,
            record_class=kind,
            runtime_identity=runtime_identity,
        )

    return _record


# ===========================================================================
# Transport construction
# ===========================================================================


def build_transport(
    kind: TransportKind,
    *,
    transport_config: KisMockTransportConfig | None,
    custody: CredentialCustody,
    monotonic: MonotonicSource,
    seal_lookup: SealRegistry,
    evidence_store: SqliteEvidenceStore,
    runtime_identity: RuntimeIdentity,
) -> Transport:
    """Construct the selected transport (module docstring item 6).

    ``synthetic`` builds the SAME ``SyntheticPaperTransport(SyntheticFillPolicy(...))``
    :mod:`tos_runtime.compose._engine_wiring` used to construct inline (moved here unchanged, no
    behavioural difference). ``kis-mock`` builds a fully-wired
    :class:`~tos_runtime.transport.kis_mock.adapter.KisMockTransport`, using
    :func:`~tos_runtime.transport.kis_mock.client.build_client` as its own module docstring
    requires (reviewer F3 — the ONLY sanctioned production client construction path; an injected
    client stays a test seam this compose root never uses).

    Args:
        kind: The selected transport kind.
        transport_config: The loaded KIS MOCK config (required, non-``None``, for ``kis-mock``;
            ignored for ``synthetic``).
        custody: The credential port — ``kis_mock.app_key``/``kis_mock.app_secret`` scopes
            (already provisioned, :data:`~tos_runtime.custody.file_custody.PROVISIONED_SCOPES`).
        monotonic: The injected monotonic clock (pacing + token bookkeeping).
        seal_lookup: The :class:`SealRegistry` this same boot wires as the gateway evidence sink's
            ``on_record`` observer — the SAME instance, so what the gateway captures is exactly
            what this transport can look up.
        evidence_store: The durable evidence store the adapted ``EvidenceRecorder`` appends into.
        runtime_identity: Bound onto every evidence record the adapted recorder appends.

    Returns:
        The constructed transport, structurally satisfying the kernel's
        :class:`~tos.brokeradapter.Transport` Protocol either way.

    Raises:
        AssertionError: ``kind`` is ``kis-mock`` and ``transport_config`` is ``None`` — a caller
            contract violation (:func:`resolve_transport_boot` always returns a non-``None``
            config for ``kis-mock``; this is a defensive narrow, not a reachable runtime state).
    """
    if kind is TransportKind.SYNTHETIC:
        return SyntheticPaperTransport(
            SyntheticFillPolicy(
                fill_numerator=1, fill_denominator=1, lot_size=Decimal("1")
            )
        )
    assert transport_config is not None, (
        "build_transport: kis-mock requires a non-None transport_config — "
        "resolve_transport_boot always supplies one"
    )
    client = build_client(transport_config)
    return KisMockTransport(
        config=transport_config,
        client=client,
        custody=custody,
        app_key_scope="kis_mock.app_key",
        app_secret_scope="kis_mock.app_secret",
        monotonic=monotonic,
        seal_lookup=seal_lookup,
        evidence_sink=_evidence_recorder(evidence_store, runtime_identity),
    )
